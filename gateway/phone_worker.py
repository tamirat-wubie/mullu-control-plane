"""Gateway Phone Worker - bounded PSTN/VOIP call execution contract.

Purpose: host signed phone call operations behind approval, connector scope,
    and receipt boundaries.
Governance scope: connector allowlisting, place/transfer approval, raw callee
    redaction, adapter isolation, transcript redaction, and receipt emission.
Dependencies: FastAPI, gateway canonical hashing, and an injected connector
    adapter.
Invariants:
  - Unsigned requests are rejected before adapter invocation.
  - Connector IDs must be allowlisted before execution.
  - Outbound place and transfer actions require approval.
  - Receipts hash callees and transcripts instead of exposing raw values.
  - The worker delegates effects only to the injected adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import Response

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Request = Any  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature
from gateway.command_spine import canonical_hash


@dataclass(frozen=True, slots=True)
class PhoneWorkerPolicy:
    """Policy envelope for one restricted phone worker."""

    worker_id: str = "phone-worker"
    allowed_actions: tuple[str, ...] = (
        "phone.call.place.with_approval",
        "phone.call.receive",
        "phone.call.transfer.with_approval",
        "phone.call.terminate",
        "phone.call.transcript_record",
    )
    allowed_connector_ids: tuple[str, ...] = ("twilio", "vonage")
    approval_required_actions: tuple[str, ...] = (
        "phone.call.place.with_approval",
        "phone.call.transfer.with_approval",
    )
    max_callees: int = 1
    max_transcript_chars: int = 65536

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        _validate_text_tuple(self.allowed_connector_ids, "allowed_connector_ids")
        object.__setattr__(self, "approval_required_actions", tuple(self.approval_required_actions))
        for action in self.approval_required_actions:
            _require_text(action, "approval_required_actions")
        if self.max_callees <= 0:
            raise ValueError("max_callees must be > 0")
        if self.max_transcript_chars <= 0:
            raise ValueError("max_transcript_chars must be > 0")


@dataclass(frozen=True, slots=True)
class PhoneActionRequest:
    """Signed request for one phone connector action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    connector_id: str
    call_id: str = ""
    callees: tuple[str, ...] = ()
    callers: tuple[str, ...] = ()
    transcript: str = ""
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        _require_text(self.connector_id, "connector_id")
        if self.action != self.capability_id:
            raise ValueError("phone action must match capability_id")
        object.__setattr__(self, "callees", tuple(str(value) for value in self.callees))
        object.__setattr__(self, "callers", tuple(str(value) for value in self.callers))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for value in self.callees:
            _require_text(value, "callees")
        for value in self.callers:
            _require_text(value, "callers")


@dataclass(frozen=True, slots=True)
class PhoneActionObservation:
    """Observation returned by a concrete phone adapter."""

    succeeded: bool
    connector_id: str
    provider_operation: str
    resource_id: str = ""
    response_digest: str = ""
    external_call: bool = False
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        _require_text(self.connector_id, "connector_id")
        _require_text(self.provider_operation, "provider_operation")
        if not isinstance(self.external_call, bool):
            raise ValueError("external_call must be a boolean")


@dataclass(frozen=True, slots=True)
class PhoneActionReceipt:
    """Receipt proving connector action policy and observed effect."""

    receipt_id: str
    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    worker_id: str
    connector_id: str
    provider_operation: str
    resource_id: str
    response_digest: str
    call_id_hash: str
    transcript_hash: str
    callee_hashes: tuple[str, ...]
    caller_hashes: tuple[str, ...]
    external_call: bool
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]
    approval_id: str = ""


@dataclass(frozen=True, slots=True)
class PhoneActionResponse:
    """Signed phone worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: PhoneActionReceipt
    error: str = ""


class PhoneConnectorAdapter(Protocol):
    """Protocol implemented by concrete Twilio, Vonage, etc. adapters."""

    def perform(self, request: PhoneActionRequest) -> PhoneActionObservation:
        """Perform one connector action and return observed effects."""
        ...


class UnavailablePhoneAdapter:
    """Fail-closed adapter used until real connectors are installed."""

    def perform(self, request: PhoneActionRequest) -> PhoneActionObservation:
        return PhoneActionObservation(
            succeeded=False,
            connector_id=request.connector_id,
            provider_operation=request.action,
            error="phone adapter unavailable",
        )


def create_phone_worker_app(
    *,
    adapter: PhoneConnectorAdapter | None = None,
    policy: PhoneWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted phone worker FastAPI app."""
    _require_fastapi()
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_PHONE_WORKER_SECRET", "")
    if not secret:
        raise ValueError("phone worker signing secret is required")
    resolved_policy = policy or PhoneWorkerPolicy()
    resolved_adapter = adapter or UnavailablePhoneAdapter()
    app = FastAPI(title="Mullu Phone Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/phone/execute")
    async def execute_phone_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Phone-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid phone request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("phone request body must be an object")
            action_request = phone_action_request_from_mapping(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError, KeyError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

        response = execute_phone_request(action_request, adapter=resolved_adapter, policy=resolved_policy)
        response_body = json.dumps(
            phone_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Phone-Response-Signature": response_signature},
        )

    app.state.phone_policy = resolved_policy
    app.state.phone_adapter = resolved_adapter
    return app


def execute_phone_request(
    request: PhoneActionRequest,
    *,
    adapter: PhoneConnectorAdapter,
    policy: PhoneWorkerPolicy,
) -> PhoneActionResponse:
    """Execute one phone request under worker policy."""
    denial = _policy_denial(request, policy)
    if denial:
        observation = PhoneActionObservation(
            succeeded=False,
            connector_id=request.connector_id,
            provider_operation=request.action,
            error=denial,
        )
        receipt = _receipt_for(
            request=request,
            policy=policy,
            observation=observation,
            forbidden_effects_observed=False,
            verification_status="blocked",
        )
        return PhoneActionResponse(
            request_id=request.request_id,
            status="blocked",
            result={"error": denial},
            receipt=receipt,
            error=denial,
        )

    observation = adapter.perform(request)
    forbidden_effect = _observation_forbidden(request, observation, policy)
    succeeded = observation.succeeded and not forbidden_effect
    verification_status = "passed" if succeeded else "failed"
    receipt = _receipt_for(
        request=request,
        policy=policy,
        observation=observation,
        forbidden_effects_observed=forbidden_effect,
        verification_status=verification_status,
    )
    return PhoneActionResponse(
        request_id=request.request_id,
        status="succeeded" if succeeded else "failed",
        result={
            "connector_id": observation.connector_id,
            "provider_operation": observation.provider_operation,
            "resource_id": observation.resource_id,
            "response_digest": observation.response_digest,
            "external_call": observation.external_call,
        },
        receipt=receipt,
        error="" if succeeded else observation.error or "phone verification failed",
    )


def phone_action_request_from_mapping(raw: dict[str, Any]) -> PhoneActionRequest:
    """Parse a phone request payload into a typed request."""
    return PhoneActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        connector_id=str(raw["connector_id"]),
        call_id=str(raw.get("call_id", "")),
        callees=tuple(raw.get("callees", ())),
        callers=tuple(raw.get("callers", ())),
        transcript=str(raw.get("transcript", "")),
        approval_id=str(raw.get("approval_id", "")),
        metadata=dict(raw.get("metadata", {})),
    )


def phone_action_response_payload(response: PhoneActionResponse) -> dict[str, Any]:
    """Serialize a phone worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": dict(response.result),
        "receipt": {
            **asdict(response.receipt),
            "callee_hashes": list(response.receipt.callee_hashes),
            "caller_hashes": list(response.receipt.caller_hashes),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _policy_denial(request: PhoneActionRequest, policy: PhoneWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "phone action is not allowlisted"
    if request.connector_id not in policy.allowed_connector_ids:
        return "phone connector is not allowlisted"
    if request.action in policy.approval_required_actions and not request.approval_id:
        return "phone action requires approval"
    if len(request.callees) > policy.max_callees:
        return "phone callee count exceeds policy"
    if len(request.transcript) > policy.max_transcript_chars:
        return "phone transcript exceeds policy"
    if request.action == "phone.call.place.with_approval" and not request.callees:
        return "phone call place requires callees"
    if request.action == "phone.call.transfer.with_approval" and not (request.call_id and request.callees):
        return "phone call transfer requires call_id and callees"
    if request.action in {"phone.call.terminate", "phone.call.transcript_record"} and not request.call_id:
        return "phone action requires call_id"
    if request.action == "phone.call.receive" and not request.callers:
        return "phone call receive requires callers"
    if request.action == "phone.call.transcript_record" and not request.transcript:
        return "phone transcript record requires transcript"
    return ""


def _observation_forbidden(
    request: PhoneActionRequest,
    observation: PhoneActionObservation,
    policy: PhoneWorkerPolicy,
) -> bool:
    if observation.connector_id != request.connector_id:
        return True
    if observation.connector_id not in policy.allowed_connector_ids:
        return True
    if observation.external_call and request.action not in policy.approval_required_actions:
        return True
    if observation.external_call and not request.approval_id:
        return True
    return False


def _receipt_for(
    *,
    request: PhoneActionRequest,
    policy: PhoneWorkerPolicy,
    observation: PhoneActionObservation,
    forbidden_effects_observed: bool,
    verification_status: str,
) -> PhoneActionReceipt:
    call_id_hash = _sha256(request.call_id)
    transcript_hash = _sha256(request.transcript)
    callee_hashes = tuple(_sha256(value) for value in request.callees)
    caller_hashes = tuple(_sha256(value) for value in request.callers)
    receipt_material = {
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "connector_id": observation.connector_id,
        "provider_operation": observation.provider_operation,
        "resource_id": observation.resource_id,
        "response_digest": observation.response_digest,
        "callee_hashes": callee_hashes,
        "caller_hashes": caller_hashes,
        "external_call": observation.external_call,
        "forbidden_effects_observed": forbidden_effects_observed,
        "verification_status": verification_status,
    }
    receipt_hash = canonical_hash(receipt_material)
    return PhoneActionReceipt(
        receipt_id=f"phone-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        connector_id=observation.connector_id,
        provider_operation=observation.provider_operation,
        resource_id=observation.resource_id,
        response_digest=observation.response_digest,
        call_id_hash=call_id_hash,
        transcript_hash=transcript_hash,
        callee_hashes=callee_hashes,
        caller_hashes=caller_hashes,
        external_call=observation.external_call,
        forbidden_effects_observed=forbidden_effects_observed,
        verification_status=verification_status,
        evidence_refs=(f"phone_action:{receipt_hash[:16]}",),
        approval_id=request.approval_id,
    )


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


def _require_fastapi() -> None:
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("fastapi is required to create the phone worker HTTP app")


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_PHONE_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-phone-worker-secret"
    return create_phone_worker_app(adapter=_default_adapter(), signing_secret=secret)


def _default_adapter() -> PhoneConnectorAdapter | None:
    adapter_name = os.environ.get("MULLU_PHONE_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name in {"http", "production", "twilio", "vonage"}:
        from gateway.phone_connector_adapters import build_phone_adapter_from_env

        return build_phone_adapter_from_env()
    raise ValueError(f"unsupported phone worker adapter: {adapter_name}")


app = _default_app() if _FASTAPI_AVAILABLE else None
