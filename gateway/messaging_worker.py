"""Gateway Messaging Worker - bounded SMS/chat connector execution contract.

Purpose: host signed SMS and IM/chat operations behind approval, connector
    scope, and receipt boundaries.
Governance scope: connector allowlisting, draft/send separation, send approval,
    raw recipient redaction, adapter isolation, and receipt emission.
Dependencies: FastAPI, gateway canonical hashing, and an injected connector
    adapter.
Invariants:
  - Unsigned requests are rejected before adapter invocation.
  - Connector IDs must be allowlisted before execution.
  - SMS and chat send actions require approval.
  - Receipts hash recipients and bodies instead of exposing raw values.
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


_SMS_ACTIONS = ("messaging.sms.send.with_approval", "messaging.sms.draft")
_CHAT_ACTIONS = (
    "messaging.chat.send.with_approval",
    "messaging.chat.draft",
    "messaging.thread.read",
)
_SMS_CONNECTORS = ("twilio", "aws_sns")
_CHAT_CONNECTORS = ("slack", "teams", "whatsapp", "telegram", "discord")


@dataclass(frozen=True, slots=True)
class MessagingWorkerPolicy:
    """Policy envelope for one restricted messaging worker."""

    worker_id: str = "messaging-worker"
    allowed_actions: tuple[str, ...] = (
        "messaging.sms.send.with_approval",
        "messaging.sms.draft",
        "messaging.chat.send.with_approval",
        "messaging.chat.draft",
        "messaging.thread.read",
    )
    allowed_connector_ids: tuple[str, ...] = (
        "twilio",
        "aws_sns",
        "slack",
        "teams",
        "whatsapp",
        "telegram",
        "discord",
    )
    approval_required_actions: tuple[str, ...] = (
        "messaging.sms.send.with_approval",
        "messaging.chat.send.with_approval",
    )
    max_recipients: int = 50
    max_body_chars: int = 4096

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        _validate_text_tuple(self.allowed_connector_ids, "allowed_connector_ids")
        object.__setattr__(self, "approval_required_actions", tuple(self.approval_required_actions))
        for action in self.approval_required_actions:
            _require_text(action, "approval_required_actions")
        if self.max_recipients <= 0:
            raise ValueError("max_recipients must be > 0")
        if self.max_body_chars <= 0:
            raise ValueError("max_body_chars must be > 0")


@dataclass(frozen=True, slots=True)
class MessagingActionRequest:
    """Signed request for one messaging connector action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    connector_id: str
    body: str = ""
    thread_id: str = ""
    query: str = ""
    recipients: tuple[str, ...] = ()
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        _require_text(self.connector_id, "connector_id")
        if self.action != self.capability_id:
            raise ValueError("messaging action must match capability_id")
        object.__setattr__(self, "recipients", tuple(str(value) for value in self.recipients))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for value in self.recipients:
            _require_text(value, "recipients")


@dataclass(frozen=True, slots=True)
class MessagingActionObservation:
    """Observation returned by a concrete messaging adapter."""

    succeeded: bool
    connector_id: str
    provider_operation: str
    resource_id: str = ""
    response_digest: str = ""
    external_send: bool = False
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        _require_text(self.connector_id, "connector_id")
        _require_text(self.provider_operation, "provider_operation")
        if not isinstance(self.external_send, bool):
            raise ValueError("external_send must be a boolean")


@dataclass(frozen=True, slots=True)
class MessagingActionReceipt:
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
    body_hash: str
    query_hash: str
    thread_id_hash: str
    recipient_hashes: tuple[str, ...]
    external_send: bool
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]
    approval_id: str = ""


@dataclass(frozen=True, slots=True)
class MessagingActionResponse:
    """Signed messaging worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: MessagingActionReceipt
    error: str = ""


class MessagingConnectorAdapter(Protocol):
    """Protocol implemented by concrete Twilio, SNS, Slack, Teams, etc. adapters."""

    def perform(self, request: MessagingActionRequest) -> MessagingActionObservation:
        """Perform one connector action and return observed effects."""
        ...


class UnavailableMessagingAdapter:
    """Fail-closed adapter used until real connectors are installed."""

    def perform(self, request: MessagingActionRequest) -> MessagingActionObservation:
        return MessagingActionObservation(
            succeeded=False,
            connector_id=request.connector_id,
            provider_operation=request.action,
            error="messaging adapter unavailable",
        )


_MESSAGING_WORKER_ERROR_CODES = {
    "messaging request body must be an object": (
        "invalid messaging request body",
        "invalid_messaging_request_body",
    ),
}


def _messaging_worker_error_detail(exc: BaseException) -> dict[str, object]:
    error, error_code = _MESSAGING_WORKER_ERROR_CODES.get(
        str(exc),
        ("invalid messaging execution request", "invalid_messaging_execution_request"),
    )
    return {"error": error, "error_code": error_code, "governed": True}


def create_messaging_worker_app(
    *,
    adapter: MessagingConnectorAdapter | None = None,
    policy: MessagingWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted messaging worker FastAPI app."""
    _require_fastapi()
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_MESSAGING_WORKER_SECRET", "")
    if not secret:
        raise ValueError("messaging worker signing secret is required")
    resolved_policy = policy or MessagingWorkerPolicy()
    resolved_adapter = adapter or UnavailableMessagingAdapter()
    app = FastAPI(title="Mullu Messaging Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/messaging/execute")
    async def execute_messaging_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Messaging-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid messaging request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("messaging request body must be an object")
            action_request = messaging_action_request_from_mapping(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError, KeyError) as exc:
            raise HTTPException(422, detail=_messaging_worker_error_detail(exc)) from exc

        response = execute_messaging_request(action_request, adapter=resolved_adapter, policy=resolved_policy)
        response_body = json.dumps(
            messaging_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Messaging-Response-Signature": response_signature},
        )

    app.state.messaging_policy = resolved_policy
    app.state.messaging_adapter = resolved_adapter
    return app


def execute_messaging_request(
    request: MessagingActionRequest,
    *,
    adapter: MessagingConnectorAdapter,
    policy: MessagingWorkerPolicy,
) -> MessagingActionResponse:
    """Execute one messaging request under worker policy."""
    denial = _policy_denial(request, policy)
    if denial:
        observation = MessagingActionObservation(
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
        return MessagingActionResponse(
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
    return MessagingActionResponse(
        request_id=request.request_id,
        status="succeeded" if succeeded else "failed",
        result={
            "connector_id": observation.connector_id,
            "provider_operation": observation.provider_operation,
            "resource_id": observation.resource_id,
            "response_digest": observation.response_digest,
            "external_send": observation.external_send,
        },
        receipt=receipt,
        error="" if succeeded else observation.error or "messaging verification failed",
    )


def messaging_action_request_from_mapping(raw: dict[str, Any]) -> MessagingActionRequest:
    """Parse a messaging request payload into a typed request."""
    return MessagingActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        connector_id=str(raw["connector_id"]),
        body=str(raw.get("body", "")),
        thread_id=str(raw.get("thread_id", "")),
        query=str(raw.get("query", "")),
        recipients=tuple(raw.get("recipients", ())),
        approval_id=str(raw.get("approval_id", "")),
        metadata=dict(raw.get("metadata", {})),
    )


def messaging_action_response_payload(response: MessagingActionResponse) -> dict[str, Any]:
    """Serialize a messaging worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": dict(response.result),
        "receipt": {
            **asdict(response.receipt),
            "recipient_hashes": list(response.receipt.recipient_hashes),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _policy_denial(request: MessagingActionRequest, policy: MessagingWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "messaging action is not allowlisted"
    if request.connector_id not in policy.allowed_connector_ids:
        return "messaging connector is not allowlisted"
    if request.action in _SMS_ACTIONS and request.connector_id not in _SMS_CONNECTORS:
        return "messaging sms action requires sms-capable connector"
    if request.action in _CHAT_ACTIONS and request.connector_id not in _CHAT_CONNECTORS:
        return "messaging chat action requires chat-capable connector"
    if request.action in policy.approval_required_actions and not request.approval_id:
        return "messaging action requires approval"
    if request.action != "messaging.thread.read" and len(request.recipients) > policy.max_recipients:
        return "messaging recipient count exceeds policy"
    if len(request.body) > policy.max_body_chars:
        return "messaging body exceeds policy"
    if request.action in {"messaging.sms.send.with_approval", "messaging.chat.send.with_approval"} and not request.recipients:
        return "messaging send requires recipients"
    if request.action == "messaging.thread.read" and not request.thread_id:
        return "messaging thread read requires thread_id"
    return ""


def _observation_forbidden(
    request: MessagingActionRequest,
    observation: MessagingActionObservation,
    policy: MessagingWorkerPolicy,
) -> bool:
    if observation.connector_id != request.connector_id:
        return True
    if observation.connector_id not in policy.allowed_connector_ids:
        return True
    if observation.external_send and request.action not in policy.approval_required_actions:
        return True
    if observation.external_send and not request.approval_id:
        return True
    return False


def _receipt_for(
    *,
    request: MessagingActionRequest,
    policy: MessagingWorkerPolicy,
    observation: MessagingActionObservation,
    forbidden_effects_observed: bool,
    verification_status: str,
) -> MessagingActionReceipt:
    body_hash = _sha256(request.body)
    query_hash = _sha256(request.query)
    thread_id_hash = _sha256(request.thread_id)
    recipient_hashes = tuple(_sha256(value.lower()) for value in request.recipients)
    receipt_material = {
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "connector_id": observation.connector_id,
        "provider_operation": observation.provider_operation,
        "resource_id": observation.resource_id,
        "response_digest": observation.response_digest,
        "recipient_hashes": recipient_hashes,
        "external_send": observation.external_send,
        "forbidden_effects_observed": forbidden_effects_observed,
        "verification_status": verification_status,
    }
    receipt_hash = canonical_hash(receipt_material)
    return MessagingActionReceipt(
        receipt_id=f"messaging-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        connector_id=observation.connector_id,
        provider_operation=observation.provider_operation,
        resource_id=observation.resource_id,
        response_digest=observation.response_digest,
        body_hash=body_hash,
        query_hash=query_hash,
        thread_id_hash=thread_id_hash,
        recipient_hashes=recipient_hashes,
        external_send=observation.external_send,
        forbidden_effects_observed=forbidden_effects_observed,
        verification_status=verification_status,
        evidence_refs=(f"messaging_action:{receipt_hash[:16]}",),
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
        raise RuntimeError("fastapi is required to create the messaging worker HTTP app")


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_MESSAGING_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-messaging-worker-secret"
    return create_messaging_worker_app(adapter=_default_adapter(), signing_secret=secret)


def _default_adapter() -> MessagingConnectorAdapter | None:
    adapter_name = os.environ.get("MULLU_MESSAGING_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name in {"http", "production", "twilio", "slack", "teams"}:
        from gateway.messaging_connector_adapters import build_messaging_adapter_from_env

        return build_messaging_adapter_from_env()
    raise ValueError(f"unsupported messaging worker adapter: {adapter_name}")


app = _default_app() if _FASTAPI_AVAILABLE else None
