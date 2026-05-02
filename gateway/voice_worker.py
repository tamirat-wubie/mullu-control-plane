"""Gateway Voice Worker - transcript-only voice boundary.

Purpose: Hosts signed voice-worker execution for transcript creation,
    synthesis references, and governed voice intent classification.
Governance scope: no audio storage, PII redaction, transcript receipts,
    no direct tool execution, and confirmation marking for effect-bearing
    intents.
Dependencies: FastAPI, gateway canonical hashing, and injected voice
    processing adapters.
Invariants:
  - Unsigned requests are rejected before voice processing.
  - Audio content is never returned or stored by this worker contract.
  - Voice intent classification only creates text intent for the normal
    governed pipeline.
  - Effect-bearing voice intent is marked for user confirmation.
  - Responses are signed and include receipt evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature
from gateway.command_spine import canonical_hash


@dataclass(frozen=True, slots=True)
class VoiceWorkerPolicy:
    """Policy envelope for one restricted voice worker."""

    worker_id: str = "voice-worker"
    allowed_actions: tuple[str, ...] = (
        "voice.speech_to_text",
        "voice.text_to_speech",
        "voice.intent_classification",
        "voice.intent_confirm",
        "voice.meeting_summarize",
        "voice.action_items_extract",
    )
    max_audio_bytes: int = 10_000_000
    redact_pii: bool = True
    store_audio: bool = False
    approval_required_for_effects: bool = True

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        if self.max_audio_bytes <= 0:
            raise ValueError("max_audio_bytes must be > 0")
        if self.redact_pii is not True:
            raise ValueError("voice worker must redact PII")
        if self.store_audio is not False:
            raise ValueError("voice worker must not store audio")
        if self.approval_required_for_effects is not True:
            raise ValueError("voice worker must require approval for effects")


@dataclass(frozen=True, slots=True)
class VoiceActionRequest:
    """Signed request for one voice action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    session_id: str
    audio_base64: str = ""
    transcript_text: str = ""
    response_text: str = ""
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        _require_text(self.session_id, "session_id")
        if self.action != self.capability_id:
            raise ValueError("voice action must match capability_id")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class VoiceTranscriptObservation:
    """Observation returned by speech-to-text processing."""

    succeeded: bool
    transcript: str = ""
    confidence: float = 0.0
    adapter_id: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class VoiceSynthesisObservation:
    """Observation returned by text-to-speech processing."""

    succeeded: bool
    audio_ref: str = ""
    audio_hash: str = ""
    duration_ms: int = 0
    adapter_id: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be >= 0")


@dataclass(frozen=True, slots=True)
class VoiceActionReceipt:
    """Receipt proving voice worker action and observation."""

    receipt_id: str
    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    worker_id: str
    session_id: str
    transcript_hash: str
    redaction_hash: str
    intent_summary_hash: str
    text_hash: str
    audio_hash: str
    audio_ref: str
    confidence: float
    requires_confirmation: bool
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VoiceActionResponse:
    """Signed voice-worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: VoiceActionReceipt
    error: str = ""


class VoiceProcessingAdapter(Protocol):
    """Protocol implemented by concrete STT/TTS adapters."""

    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        """Transcribe audio into text."""
        ...

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        """Create a synthesis reference for text."""
        ...


class UnavailableVoiceAdapter:
    """Fail-closed adapter used until a concrete voice provider is installed."""

    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        return VoiceTranscriptObservation(
            succeeded=False,
            adapter_id="unavailable",
            error="voice transcription adapter unavailable",
        )

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        return VoiceSynthesisObservation(
            succeeded=False,
            adapter_id="unavailable",
            error="voice synthesis adapter unavailable",
        )


def create_voice_worker_app(
    *,
    adapter: VoiceProcessingAdapter | None = None,
    policy: VoiceWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted voice worker FastAPI app."""
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_VOICE_WORKER_SECRET", "")
    if not secret:
        raise ValueError("voice worker signing secret is required")
    resolved_policy = policy or VoiceWorkerPolicy()
    resolved_adapter = adapter or UnavailableVoiceAdapter()
    app = FastAPI(title="Mullu Voice Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/voice/execute")
    async def execute_voice_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Voice-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid voice request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("voice request body must be an object")
            voice_request = voice_action_request_from_mapping(raw)
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

        response = execute_voice_request(voice_request, adapter=resolved_adapter, policy=resolved_policy)
        response_body = json.dumps(
            voice_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Voice-Response-Signature": response_signature},
        )

    app.state.voice_policy = resolved_policy
    app.state.voice_adapter = resolved_adapter
    return app


def execute_voice_request(
    request: VoiceActionRequest,
    *,
    adapter: VoiceProcessingAdapter,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    """Execute one voice request under policy."""
    try:
        denial = _policy_denial(request, policy)
    except ValueError as exc:
        denial = str(exc)
    if denial:
        return _blocked_response(request, policy, denial)

    if request.action == "voice.speech_to_text":
        return _execute_speech_to_text(request, adapter=adapter, policy=policy)
    if request.action == "voice.text_to_speech":
        return _execute_text_to_speech(request, adapter=adapter, policy=policy)
    if request.action == "voice.intent_classification":
        return _execute_intent_classification(request, policy=policy)
    if request.action == "voice.intent_confirm":
        return _execute_intent_confirm(request, policy=policy)
    if request.action == "voice.meeting_summarize":
        return _execute_meeting_summarize(request, policy=policy)
    if request.action == "voice.action_items_extract":
        return _execute_action_items_extract(request, policy=policy)
    return _blocked_response(request, policy, "voice action is not allowlisted")


def voice_action_request_from_mapping(raw: dict[str, Any]) -> VoiceActionRequest:
    """Parse a voice request payload into a typed request."""
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be an object")
    return VoiceActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        session_id=str(raw["session_id"]),
        audio_base64=str(raw.get("audio_base64", "")),
        transcript_text=str(raw.get("transcript_text", "")),
        response_text=str(raw.get("response_text", "")),
        approval_id=str(raw.get("approval_id", "")),
        metadata=dict(metadata),
    )


def voice_action_response_payload(response: VoiceActionResponse) -> dict[str, Any]:
    """Serialize a voice worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": dict(response.result),
        "receipt": {
            **asdict(response.receipt),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _execute_speech_to_text(
    request: VoiceActionRequest,
    *,
    adapter: VoiceProcessingAdapter,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    audio_bytes = _decode_audio(request)
    if request.transcript_text.strip():
        observation = VoiceTranscriptObservation(
            succeeded=True,
            transcript=request.transcript_text,
            confidence=1.0,
            adapter_id="provided-transcript",
        )
    else:
        observation = adapter.transcribe(request, audio_bytes)
    if not observation.succeeded:
        return _failed_response(
            request,
            policy,
            error=observation.error or "voice transcription failed",
            adapter_id=observation.adapter_id,
        )
    redacted = _redact_pii(observation.transcript)
    result = {
        "transcript": redacted,
        "transcript_hash": _sha256(redacted),
        "raw_transcript_hash": _sha256(observation.transcript),
        "redaction_hash": _sha256(redacted),
        "confidence": observation.confidence,
        "adapter_id": observation.adapter_id,
        "audio_hash": _sha256_bytes(audio_bytes) if audio_bytes else "",
        "audio_ref": "",
        "store_audio": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _execute_text_to_speech(
    request: VoiceActionRequest,
    *,
    adapter: VoiceProcessingAdapter,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    redacted_text = _redact_pii(request.response_text)
    observation = adapter.synthesize(request, redacted_text)
    if not observation.succeeded:
        return _failed_response(
            request,
            policy,
            error=observation.error or "voice synthesis failed",
            adapter_id=observation.adapter_id,
        )
    result = {
        "text_hash": _sha256(redacted_text),
        "redaction_hash": _sha256(redacted_text),
        "audio_ref": observation.audio_ref,
        "audio_hash": observation.audio_hash,
        "duration_ms": observation.duration_ms,
        "adapter_id": observation.adapter_id,
        "store_audio": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _execute_intent_classification(
    request: VoiceActionRequest,
    *,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    redacted = _redact_pii(request.transcript_text)
    risk_hint = _risk_hint(redacted)
    requires_confirmation = policy.approval_required_for_effects and risk_hint in {"high", "critical"}
    intent_summary = _summarize_intent(redacted)
    result = {
        "transcript": redacted,
        "transcript_hash": _sha256(redacted),
        "redaction_hash": _sha256(redacted),
        "intent_summary": intent_summary,
        "intent_summary_hash": _sha256(intent_summary),
        "risk_hint": risk_hint,
        "requires_confirmation": requires_confirmation,
        "target_runtime": "governed_pipeline",
        "tool_execution_performed": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _execute_intent_confirm(
    request: VoiceActionRequest,
    *,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    redacted = _redact_pii(request.transcript_text)
    risk_hint = _risk_hint(redacted)
    confirmed = bool(request.approval_id.strip()) and risk_hint in {"high", "critical"}
    intent_summary = _summarize_intent(redacted)
    result = {
        "transcript": redacted,
        "transcript_hash": _sha256(redacted),
        "redaction_hash": _sha256(redacted),
        "intent_summary": intent_summary,
        "intent_summary_hash": _sha256(intent_summary),
        "risk_hint": risk_hint,
        "requires_confirmation": risk_hint in {"high", "critical"},
        "confirmation_status": "confirmed" if confirmed else "pending",
        "approval_id_hash": _sha256(request.approval_id) if request.approval_id.strip() else "",
        "target_runtime": "governed_pipeline",
        "tool_execution_performed": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _execute_meeting_summarize(
    request: VoiceActionRequest,
    *,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    redacted = _redact_pii(request.transcript_text)
    sentences = _split_sentences(redacted)
    summary = " ".join(sentences[:3]) if sentences else _summarize_intent(redacted)
    result = {
        "transcript_hash": _sha256(redacted),
        "redaction_hash": _sha256(redacted),
        "meeting_summary": summary,
        "meeting_summary_hash": _sha256(summary),
        "intent_summary_hash": _sha256(summary),
        "requires_confirmation": False,
        "target_runtime": "governed_pipeline",
        "tool_execution_performed": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _execute_action_items_extract(
    request: VoiceActionRequest,
    *,
    policy: VoiceWorkerPolicy,
) -> VoiceActionResponse:
    redacted = _redact_pii(request.transcript_text)
    action_items = _extract_action_items(redacted)
    action_items_text = "\n".join(action_items)
    result = {
        "transcript_hash": _sha256(redacted),
        "redaction_hash": _sha256(redacted),
        "action_items": action_items,
        "action_items_hash": _sha256(action_items_text),
        "intent_summary_hash": _sha256(action_items_text),
        "requires_confirmation": False,
        "target_runtime": "governed_pipeline",
        "tool_execution_performed": False,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="passed")
    return VoiceActionResponse(request_id=request.request_id, status="succeeded", result=result, receipt=receipt)


def _blocked_response(request: VoiceActionRequest, policy: VoiceWorkerPolicy, reason: str) -> VoiceActionResponse:
    result = {
        "transcript_hash": "",
        "redaction_hash": "",
        "intent_summary_hash": "",
        "text_hash": "",
        "audio_hash": "",
        "audio_ref": "",
        "confidence": 0.0,
        "requires_confirmation": False,
        "error": reason,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="blocked")
    return VoiceActionResponse(
        request_id=request.request_id,
        status="blocked",
        result=result,
        receipt=receipt,
        error=reason,
    )


def _failed_response(
    request: VoiceActionRequest,
    policy: VoiceWorkerPolicy,
    *,
    error: str,
    adapter_id: str,
) -> VoiceActionResponse:
    result = {
        "transcript_hash": "",
        "redaction_hash": "",
        "intent_summary_hash": "",
        "text_hash": "",
        "audio_hash": "",
        "audio_ref": "",
        "confidence": 0.0,
        "requires_confirmation": False,
        "adapter_id": adapter_id,
        "error": error,
    }
    receipt = _receipt_for(request=request, policy=policy, result=result, verification_status="failed")
    return VoiceActionResponse(request_id=request.request_id, status="failed", result=result, receipt=receipt, error=error)


def _receipt_for(
    *,
    request: VoiceActionRequest,
    policy: VoiceWorkerPolicy,
    result: dict[str, Any],
    verification_status: str,
) -> VoiceActionReceipt:
    receipt_hash = canonical_hash({
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "transcript_hash": result.get("transcript_hash", ""),
        "text_hash": result.get("text_hash", ""),
        "audio_hash": result.get("audio_hash", ""),
        "intent_summary_hash": result.get("intent_summary_hash", ""),
        "verification_status": verification_status,
    })
    return VoiceActionReceipt(
        receipt_id=f"voice-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        session_id=request.session_id,
        transcript_hash=str(result.get("transcript_hash", "")),
        redaction_hash=str(result.get("redaction_hash", "")),
        intent_summary_hash=str(result.get("intent_summary_hash", "")),
        text_hash=str(result.get("text_hash", "")),
        audio_hash=str(result.get("audio_hash", "")),
        audio_ref=str(result.get("audio_ref", "")),
        confidence=float(result.get("confidence", 0.0)),
        requires_confirmation=bool(result.get("requires_confirmation", False)),
        forbidden_effects_observed=False,
        verification_status=verification_status,
        evidence_refs=(f"voice_action:{receipt_hash[:16]}",),
    )


def _policy_denial(request: VoiceActionRequest, policy: VoiceWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "voice action is not allowlisted"
    if any(bool(request.metadata.get(flag)) for flag in ("execute_tools", "send_external", "store_audio")):
        return "voice external effect is forbidden"
    if request.action == "voice.speech_to_text":
        audio = _decode_audio(request)
        if not request.transcript_text.strip() and not audio:
            return "voice transcript or audio input is required"
        if len(audio) > policy.max_audio_bytes:
            return "voice audio input exceeds size limit"
    if request.action == "voice.text_to_speech" and not request.response_text.strip():
        return "voice synthesis requires response_text"
    text_required_actions = {
        "voice.intent_classification",
        "voice.intent_confirm",
        "voice.meeting_summarize",
        "voice.action_items_extract",
    }
    if request.action in text_required_actions and not request.transcript_text.strip():
        return "voice intent classification requires transcript_text"
    return ""


def _decode_audio(request: VoiceActionRequest) -> bytes:
    if not request.audio_base64:
        return b""
    try:
        return base64.b64decode(request.audio_base64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("voice audio_base64 is invalid") from exc


def _redact_pii(text: str) -> str:
    redacted = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[redacted-email]", text)
    redacted = re.sub(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b", "[redacted-phone]", redacted)
    return redacted


def _risk_hint(transcript: str) -> str:
    lowered = transcript.lower()
    critical_terms = ("wire transfer", "delete production", "payment", "send money", "purchase")
    high_terms = ("deploy", "submit", "send email", "send message", "refund", "delete")
    if any(term in lowered for term in critical_terms):
        return "critical"
    if any(term in lowered for term in high_terms):
        return "high"
    return "low"


def _summarize_intent(transcript: str) -> str:
    compact = " ".join(transcript.split())
    if len(compact) <= 160:
        return compact
    return compact[:157].rstrip() + "..."


def _split_sentences(transcript: str) -> list[str]:
    compact = " ".join(transcript.split())
    if not compact:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", compact) if part.strip()]


def _extract_action_items(transcript: str) -> list[str]:
    items: list[str] = []
    for sentence in _split_sentences(transcript):
        lowered = sentence.lower()
        if any(marker in lowered for marker in ("action item", "todo", "follow up", "please ", "need to", "assign ")):
            items.append(sentence)
    return items[:20]


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field_name} must contain at least one item")
    for value in values:
        _require_text(value, field_name)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_VOICE_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-voice-worker-secret"
    return create_voice_worker_app(adapter=_default_adapter(), signing_secret=secret)


def _default_adapter() -> VoiceProcessingAdapter | None:
    adapter_name = os.environ.get("MULLU_VOICE_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name == "openai":
        from gateway.voice_openai_adapter import OpenAIVoiceAdapter

        return OpenAIVoiceAdapter()
    raise ValueError(f"unsupported voice worker adapter: {adapter_name}")


app = _default_app()
