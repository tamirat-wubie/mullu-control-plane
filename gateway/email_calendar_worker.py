"""Gateway Email/Calendar Worker - bounded connector execution contract.

Purpose: host signed email and calendar operations behind approval, connector
    scope, and receipt boundaries.
Governance scope: connector allowlisting, draft/send separation, calendar write
    approval, raw recipient redaction, adapter isolation, and receipt emission.
Dependencies: FastAPI, gateway canonical hashing, and an injected connector
    adapter.
Invariants:
  - Unsigned requests are rejected before adapter invocation.
  - Connector IDs must be allowlisted before execution.
  - External email send and calendar write actions require approval.
  - Receipts hash recipients and attendees instead of exposing raw addresses.
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
class EmailCalendarWorkerPolicy:
    """Policy envelope for one restricted email/calendar worker."""

    worker_id: str = "email-calendar-worker"
    allowed_actions: tuple[str, ...] = (
        "email.read",
        "email.search",
        "email.draft",
        "email.send.with_approval",
        "email.classify",
        "email.reply_suggest",
        "calendar.read",
        "calendar.conflict_check",
        "calendar.schedule",
        "calendar.reschedule",
        "calendar.invite",
    )
    allowed_connector_ids: tuple[str, ...] = ("gmail", "google_calendar", "microsoft_graph")
    approval_required_actions: tuple[str, ...] = (
        "email.send.with_approval",
        "calendar.schedule",
        "calendar.reschedule",
        "calendar.invite",
    )
    max_recipients: int = 50
    max_attendees: int = 100

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _validate_text_tuple(self.allowed_actions, "allowed_actions")
        _validate_text_tuple(self.allowed_connector_ids, "allowed_connector_ids")
        object.__setattr__(self, "approval_required_actions", tuple(self.approval_required_actions))
        for action in self.approval_required_actions:
            _require_text(action, "approval_required_actions")
        if self.max_recipients <= 0:
            raise ValueError("max_recipients must be > 0")
        if self.max_attendees <= 0:
            raise ValueError("max_attendees must be > 0")


@dataclass(frozen=True, slots=True)
class EmailCalendarActionRequest:
    """Signed request for one email or calendar connector action."""

    request_id: str
    tenant_id: str
    capability_id: str
    action: str
    connector_id: str
    subject: str = ""
    body: str = ""
    query: str = ""
    event_id: str = ""
    start_time: str = ""
    end_time: str = ""
    recipients: tuple[str, ...] = ()
    attendees: tuple[str, ...] = ()
    approval_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.action, "action")
        _require_text(self.connector_id, "connector_id")
        if self.action != self.capability_id:
            raise ValueError("email/calendar action must match capability_id")
        object.__setattr__(self, "recipients", tuple(str(value) for value in self.recipients))
        object.__setattr__(self, "attendees", tuple(str(value) for value in self.attendees))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for value in self.recipients:
            _require_text(value, "recipients")
        for value in self.attendees:
            _require_text(value, "attendees")


@dataclass(frozen=True, slots=True)
class EmailCalendarActionObservation:
    """Observation returned by a concrete email/calendar adapter."""

    succeeded: bool
    connector_id: str
    provider_operation: str
    resource_id: str = ""
    response_digest: str = ""
    external_write: bool = False
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        _require_text(self.connector_id, "connector_id")
        _require_text(self.provider_operation, "provider_operation")
        if not isinstance(self.external_write, bool):
            raise ValueError("external_write must be a boolean")


@dataclass(frozen=True, slots=True)
class EmailCalendarActionReceipt:
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
    subject_hash: str
    body_hash: str
    query_hash: str
    recipient_hashes: tuple[str, ...]
    attendee_hashes: tuple[str, ...]
    external_write: bool
    forbidden_effects_observed: bool
    verification_status: str
    evidence_refs: tuple[str, ...]
    approval_id: str = ""


@dataclass(frozen=True, slots=True)
class EmailCalendarActionResponse:
    """Signed email/calendar worker response."""

    request_id: str
    status: str
    result: dict[str, Any]
    receipt: EmailCalendarActionReceipt
    error: str = ""


class EmailCalendarConnectorAdapter(Protocol):
    """Protocol implemented by concrete Gmail, Graph, and calendar adapters."""

    def perform(self, request: EmailCalendarActionRequest) -> EmailCalendarActionObservation:
        """Perform one connector action and return observed effects."""
        ...


class UnavailableEmailCalendarAdapter:
    """Fail-closed adapter used until real connectors are installed."""

    def perform(self, request: EmailCalendarActionRequest) -> EmailCalendarActionObservation:
        return EmailCalendarActionObservation(
            succeeded=False,
            connector_id=request.connector_id,
            provider_operation=request.action,
            error="email/calendar adapter unavailable",
        )


def create_email_calendar_worker_app(
    *,
    adapter: EmailCalendarConnectorAdapter | None = None,
    policy: EmailCalendarWorkerPolicy | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Create the restricted email/calendar worker FastAPI app."""
    _require_fastapi()
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_EMAIL_CALENDAR_WORKER_SECRET", "")
    if not secret:
        raise ValueError("email/calendar worker signing secret is required")
    resolved_policy = policy or EmailCalendarWorkerPolicy()
    resolved_adapter = adapter or UnavailableEmailCalendarAdapter()
    app = FastAPI(title="Mullu Email Calendar Worker", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": resolved_policy.worker_id,
            "governed": True,
        }

    @app.post("/email-calendar/execute")
    async def execute_email_calendar_action(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Email-Calendar-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid email/calendar request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("email/calendar request body must be an object")
            action_request = email_calendar_action_request_from_mapping(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError, ValueError, KeyError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

        response = execute_email_calendar_request(action_request, adapter=resolved_adapter, policy=resolved_policy)
        response_body = json.dumps(
            email_calendar_action_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Email-Calendar-Response-Signature": response_signature},
        )

    app.state.email_calendar_policy = resolved_policy
    app.state.email_calendar_adapter = resolved_adapter
    return app


def execute_email_calendar_request(
    request: EmailCalendarActionRequest,
    *,
    adapter: EmailCalendarConnectorAdapter,
    policy: EmailCalendarWorkerPolicy,
) -> EmailCalendarActionResponse:
    """Execute one email/calendar request under worker policy."""
    denial = _policy_denial(request, policy)
    if denial:
        observation = EmailCalendarActionObservation(
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
        return EmailCalendarActionResponse(
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
    return EmailCalendarActionResponse(
        request_id=request.request_id,
        status="succeeded" if succeeded else "failed",
        result={
            "connector_id": observation.connector_id,
            "provider_operation": observation.provider_operation,
            "resource_id": observation.resource_id,
            "response_digest": observation.response_digest,
            "external_write": observation.external_write,
        },
        receipt=receipt,
        error="" if succeeded else observation.error or "email/calendar verification failed",
    )


def email_calendar_action_request_from_mapping(raw: dict[str, Any]) -> EmailCalendarActionRequest:
    """Parse an email/calendar request payload into a typed request."""
    return EmailCalendarActionRequest(
        request_id=str(raw["request_id"]),
        tenant_id=str(raw["tenant_id"]),
        capability_id=str(raw["capability_id"]),
        action=str(raw["action"]),
        connector_id=str(raw["connector_id"]),
        subject=str(raw.get("subject", "")),
        body=str(raw.get("body", "")),
        query=str(raw.get("query", "")),
        event_id=str(raw.get("event_id", "")),
        start_time=str(raw.get("start_time", "")),
        end_time=str(raw.get("end_time", "")),
        recipients=tuple(raw.get("recipients", ())),
        attendees=tuple(raw.get("attendees", ())),
        approval_id=str(raw.get("approval_id", "")),
        metadata=dict(raw.get("metadata", {})),
    )


def email_calendar_action_response_payload(response: EmailCalendarActionResponse) -> dict[str, Any]:
    """Serialize an email/calendar worker response."""
    return {
        "request_id": response.request_id,
        "status": response.status,
        "result": dict(response.result),
        "receipt": {
            **asdict(response.receipt),
            "recipient_hashes": list(response.receipt.recipient_hashes),
            "attendee_hashes": list(response.receipt.attendee_hashes),
            "evidence_refs": list(response.receipt.evidence_refs),
        },
        "error": response.error,
    }


def _policy_denial(request: EmailCalendarActionRequest, policy: EmailCalendarWorkerPolicy) -> str:
    if request.action not in policy.allowed_actions:
        return "email/calendar action is not allowlisted"
    if request.connector_id not in policy.allowed_connector_ids:
        return "email/calendar connector is not allowlisted"
    if request.action in policy.approval_required_actions and not request.approval_id:
        return "email/calendar action requires approval"
    if request.action.startswith("email.") and len(request.recipients) > policy.max_recipients:
        return "email recipient count exceeds policy"
    if request.action.startswith("calendar.") and len(request.attendees) > policy.max_attendees:
        return "calendar attendee count exceeds policy"
    if request.action == "email.send.with_approval" and not request.recipients:
        return "email send requires recipients"
    if request.action in {"calendar.schedule", "calendar.reschedule", "calendar.invite"} and not request.attendees:
        return "calendar write requires attendees"
    return ""


def _observation_forbidden(
    request: EmailCalendarActionRequest,
    observation: EmailCalendarActionObservation,
    policy: EmailCalendarWorkerPolicy,
) -> bool:
    if observation.connector_id != request.connector_id:
        return True
    if observation.connector_id not in policy.allowed_connector_ids:
        return True
    if observation.external_write and request.action not in policy.approval_required_actions:
        return True
    if observation.external_write and not request.approval_id:
        return True
    return False


def _receipt_for(
    *,
    request: EmailCalendarActionRequest,
    policy: EmailCalendarWorkerPolicy,
    observation: EmailCalendarActionObservation,
    forbidden_effects_observed: bool,
    verification_status: str,
) -> EmailCalendarActionReceipt:
    subject_hash = _sha256(request.subject)
    body_hash = _sha256(request.body)
    query_hash = _sha256(request.query)
    recipient_hashes = tuple(_sha256(value.lower()) for value in request.recipients)
    attendee_hashes = tuple(_sha256(value.lower()) for value in request.attendees)
    receipt_material = {
        "request_id": request.request_id,
        "capability_id": request.capability_id,
        "action": request.action,
        "connector_id": observation.connector_id,
        "provider_operation": observation.provider_operation,
        "resource_id": observation.resource_id,
        "response_digest": observation.response_digest,
        "recipient_hashes": recipient_hashes,
        "attendee_hashes": attendee_hashes,
        "external_write": observation.external_write,
        "forbidden_effects_observed": forbidden_effects_observed,
        "verification_status": verification_status,
    }
    receipt_hash = canonical_hash(receipt_material)
    return EmailCalendarActionReceipt(
        receipt_id=f"email-calendar-receipt-{receipt_hash[:16]}",
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        capability_id=request.capability_id,
        action=request.action,
        worker_id=policy.worker_id,
        connector_id=observation.connector_id,
        provider_operation=observation.provider_operation,
        resource_id=observation.resource_id,
        response_digest=observation.response_digest,
        subject_hash=subject_hash,
        body_hash=body_hash,
        query_hash=query_hash,
        recipient_hashes=recipient_hashes,
        attendee_hashes=attendee_hashes,
        external_write=observation.external_write,
        forbidden_effects_observed=forbidden_effects_observed,
        verification_status=verification_status,
        evidence_refs=(f"email_calendar_action:{receipt_hash[:16]}",),
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
        raise RuntimeError("fastapi is required to create the email/calendar worker HTTP app")


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_EMAIL_CALENDAR_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-email-calendar-worker-secret"
    return create_email_calendar_worker_app(adapter=_default_adapter(), signing_secret=secret)


def _default_adapter() -> EmailCalendarConnectorAdapter | None:
    adapter_name = os.environ.get("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "").strip().lower()
    if not adapter_name:
        return None
    if adapter_name in {"http", "google", "google_graph", "production"}:
        from gateway.email_calendar_connector_adapters import build_email_calendar_adapter_from_env

        return build_email_calendar_adapter_from_env()
    raise ValueError(f"unsupported email/calendar worker adapter: {adapter_name}")


app = _default_app() if _FASTAPI_AVAILABLE else None
