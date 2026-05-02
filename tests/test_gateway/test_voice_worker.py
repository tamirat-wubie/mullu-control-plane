"""Voice worker contract tests.

Tests: signed transcript-only voice requests, redaction, confirmation marking,
adapter fail-closed behavior, and no direct tool execution.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402
from gateway.voice_worker import (  # noqa: E402
    VoiceActionRequest,
    VoiceSynthesisObservation,
    VoiceTranscriptObservation,
    VoiceWorkerPolicy,
    create_voice_worker_app,
    execute_voice_request,
    voice_action_request_from_mapping,
)


class FakeVoiceAdapter:
    """Voice adapter fixture that returns deterministic observations."""

    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        return VoiceTranscriptObservation(
            succeeded=True,
            transcript="Call me at 555-010-2222 about the support case.",
            confidence=0.92,
            adapter_id="fake-stt",
        )

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        audio_hash = "hash-" + str(len(text))
        return VoiceSynthesisObservation(
            succeeded=True,
            audio_ref=f"voice-artifact:{audio_hash}",
            audio_hash=audio_hash,
            duration_ms=1200,
            adapter_id="fake-tts",
        )


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "voice-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "voice.intent_classification",
        "action": "voice.intent_classification",
        "session_id": "voice-session-1",
        "audio_base64": "",
        "transcript_text": "Please summarize the support case.",
        "response_text": "",
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_voice_worker_executes_signed_intent_classification_request() -> None:
    secret = "voice-secret"
    app = create_voice_worker_app(adapter=FakeVoiceAdapter(), signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload(transcript_text="Please send email to user@example.com about the payment."))

    response = client.post(
        "/voice/execute",
        content=body,
        headers={"X-Mullu-Voice-Signature": sign_capability_payload(body, secret)},
    )

    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Voice-Response-Signature"],
        secret,
    )
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["transcript"] == "Please send email to [redacted-email] about the payment."
    assert payload["result"]["target_runtime"] == "governed_pipeline"
    assert payload["result"]["requires_confirmation"] is True
    assert payload["result"]["tool_execution_performed"] is False
    assert payload["receipt"]["verification_status"] == "passed"


def test_voice_worker_rejects_bad_signature() -> None:
    app = create_voice_worker_app(adapter=FakeVoiceAdapter(), signing_secret="voice-secret")
    client = TestClient(app)

    response = client.post(
        "/voice/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Voice-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid voice request signature"
    assert "X-Mullu-Voice-Response-Signature" not in response.headers


def test_voice_worker_speech_to_text_redacts_and_does_not_store_audio() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-stt",
            capability_id="voice.speech_to_text",
            action="voice.speech_to_text",
            transcript_text="",
            audio_base64=base64.b64encode(b"voice-bytes").decode("ascii"),
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["transcript"] == "Call me at [redacted-phone] about the support case."
    assert response.result["store_audio"] is False
    assert response.receipt.audio_ref == ""
    assert response.receipt.audio_hash
    assert response.receipt.confidence == 0.92


def test_voice_worker_text_to_speech_returns_reference_not_audio_content() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-tts",
            capability_id="voice.text_to_speech",
            action="voice.text_to_speech",
            transcript_text="",
            response_text="Call user@example.com after approval.",
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["audio_ref"].startswith("voice-artifact:hash-")
    assert response.result["store_audio"] is False
    assert "audio_base64" not in response.result
    assert response.receipt.audio_ref == response.result["audio_ref"]
    assert response.receipt.text_hash


def test_voice_worker_blocks_direct_tool_execution_metadata() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-tool",
            metadata={"execute_tools": True},
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "voice external effect is forbidden"
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.evidence_refs[0].startswith("voice_action:")


def test_voice_worker_default_adapter_fails_closed_for_audio_transcription() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-unavailable",
            capability_id="voice.speech_to_text",
            action="voice.speech_to_text",
            transcript_text="",
            audio_base64=base64.b64encode(b"voice-bytes").decode("ascii"),
        )
    )

    response = execute_voice_request(
        request,
        adapter=create_voice_worker_app(signing_secret="voice-secret").state.voice_adapter,
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "voice transcription adapter unavailable"
    assert response.receipt.verification_status == "failed"
    assert response.receipt.transcript_hash == ""
    assert response.result["adapter_id"] == "unavailable"


def test_voice_worker_intent_confirm_records_confirmation_without_execution() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-confirm",
            capability_id="voice.intent_confirm",
            action="voice.intent_confirm",
            transcript_text="Please send email to user@example.com after approval.",
            approval_id="approval-123",
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["confirmation_status"] == "confirmed"
    assert response.result["requires_confirmation"] is True
    assert response.result["tool_execution_performed"] is False
    assert response.result["transcript"] == "Please send email to [redacted-email] after approval."
    assert response.receipt.requires_confirmation is True


def test_voice_worker_meeting_summary_is_text_only() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-meeting-summary",
            capability_id="voice.meeting_summarize",
            action="voice.meeting_summarize",
            transcript_text=(
                "Alice reviewed the launch risk. Bob agreed to update the runbook. "
                "Carol asked for a follow up on Friday. Extra details remain in transcript."
            ),
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["meeting_summary"].startswith("Alice reviewed")
    assert "tool_execution_performed" in response.result
    assert response.result["tool_execution_performed"] is False
    assert response.result["requires_confirmation"] is False
    assert response.receipt.intent_summary_hash


def test_voice_worker_extracts_action_items_without_task_creation() -> None:
    request = voice_action_request_from_mapping(
        _payload(
            request_id="voice-request-action-items",
            capability_id="voice.action_items_extract",
            action="voice.action_items_extract",
            transcript_text=(
                "Status was reviewed. Action item: Alice updates the policy. "
                "Please follow up with Bob. The dashboard is stable."
            ),
        )
    )

    response = execute_voice_request(
        request,
        adapter=FakeVoiceAdapter(),
        policy=VoiceWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.result["action_items"] == [
        "Action item: Alice updates the policy.",
        "Please follow up with Bob.",
    ]
    assert response.result["tool_execution_performed"] is False
    assert response.result["requires_confirmation"] is False
    assert response.receipt.verification_status == "passed"
