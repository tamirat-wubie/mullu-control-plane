"""Email/calendar worker contract tests.

Tests: signed bounded connector requests, approval gates, connector allowlists,
receipt redaction, and forbidden write observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_isolation import sign_capability_payload, verify_capability_signature  # noqa: E402
from gateway.email_calendar_worker import (  # noqa: E402
    EmailCalendarActionObservation,
    EmailCalendarWorkerPolicy,
    _default_adapter,
    create_email_calendar_worker_app,
    email_calendar_action_request_from_mapping,
    execute_email_calendar_request,
)


class FakeEmailCalendarAdapter:
    """Connector adapter fixture that returns deterministic observations."""

    def __init__(
        self,
        *,
        connector_id: str = "",
        external_write: bool = False,
    ) -> None:
        self.requests = []
        self._connector_id = connector_id
        self._external_write = external_write

    def perform(self, request):
        self.requests.append(request)
        connector_id = self._connector_id or request.connector_id
        return EmailCalendarActionObservation(
            succeeded=True,
            connector_id=connector_id,
            provider_operation=request.action,
            resource_id=f"resource-{request.request_id}",
            response_digest="digest-1",
            external_write=self._external_write,
        )


def _payload(**overrides) -> dict:
    payload = {
        "request_id": "email-calendar-request-1",
        "tenant_id": "tenant-1",
        "capability_id": "email.draft",
        "action": "email.draft",
        "connector_id": "gmail",
        "subject": "Weekly report",
        "body": "Draft body",
        "query": "",
        "event_id": "",
        "start_time": "",
        "end_time": "",
        "recipients": ["user@example.com"],
        "attendees": [],
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def _body(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_email_calendar_worker_executes_signed_draft_request() -> None:
    secret = "email-calendar-secret"
    adapter = FakeEmailCalendarAdapter()
    app = create_email_calendar_worker_app(adapter=adapter, signing_secret=secret)
    client = TestClient(app)
    body = _body(_payload())

    response = client.post(
        "/email-calendar/execute",
        content=body,
        headers={"X-Mullu-Email-Calendar-Signature": sign_capability_payload(body, secret)},
    )

    payload = response.json()
    assert response.status_code == 200
    assert verify_capability_signature(
        response.content,
        response.headers["X-Mullu-Email-Calendar-Response-Signature"],
        secret,
    )
    assert payload["status"] == "succeeded"
    assert payload["receipt"]["capability_id"] == "email.draft"
    assert payload["receipt"]["connector_id"] == "gmail"
    assert payload["receipt"]["recipient_hashes"] != ["user@example.com"]
    assert payload["receipt"]["verification_status"] == "passed"
    assert adapter.requests[0].tenant_id == "tenant-1"


def test_email_calendar_worker_rejects_bad_signature() -> None:
    app = create_email_calendar_worker_app(adapter=FakeEmailCalendarAdapter(), signing_secret="email-calendar-secret")
    client = TestClient(app)

    response = client.post(
        "/email-calendar/execute",
        content=_body(_payload()),
        headers={"X-Mullu-Email-Calendar-Signature": "hmac-sha256:bad"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid email/calendar request signature"
    assert "X-Mullu-Email-Calendar-Response-Signature" not in response.headers


def test_email_send_requires_approval_before_adapter() -> None:
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-send",
            capability_id="email.send.with_approval",
            action="email.send.with_approval",
        )
    )
    adapter = FakeEmailCalendarAdapter(external_write=True)

    response = execute_email_calendar_request(
        request,
        adapter=adapter,
        policy=EmailCalendarWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "email/calendar action requires approval"
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.approval_id == ""
    assert adapter.requests == []


def test_email_send_with_approval_executes_as_external_write() -> None:
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-send-approved",
            capability_id="email.send.with_approval",
            action="email.send.with_approval",
            approval_id="approval-1",
        )
    )

    response = execute_email_calendar_request(
        request,
        adapter=FakeEmailCalendarAdapter(external_write=True),
        policy=EmailCalendarWorkerPolicy(),
    )

    assert response.status == "succeeded"
    assert response.receipt.external_write is True
    assert response.receipt.approval_id == "approval-1"
    assert response.receipt.forbidden_effects_observed is False
    assert response.receipt.evidence_refs[0].startswith("email_calendar_action:")


def test_calendar_invite_requires_approval() -> None:
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-invite",
            capability_id="calendar.invite",
            action="calendar.invite",
            connector_id="google_calendar",
            recipients=[],
            attendees=["attendee@example.com"],
        )
    )

    response = execute_email_calendar_request(
        request,
        adapter=FakeEmailCalendarAdapter(external_write=True),
        policy=EmailCalendarWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "email/calendar action requires approval"
    assert response.receipt.attendee_hashes != ("attendee@example.com",)
    assert response.receipt.verification_status == "blocked"
    assert response.receipt.forbidden_effects_observed is False


def test_worker_blocks_unallowlisted_connector_before_adapter() -> None:
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-connector",
            connector_id="unknown_mail",
        )
    )
    adapter = FakeEmailCalendarAdapter()

    response = execute_email_calendar_request(
        request,
        adapter=adapter,
        policy=EmailCalendarWorkerPolicy(),
    )

    assert response.status == "blocked"
    assert response.error == "email/calendar connector is not allowlisted"
    assert response.receipt.verification_status == "blocked"
    assert adapter.requests == []


def test_read_action_fails_if_adapter_observes_external_write() -> None:
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-read-write",
            capability_id="email.read",
            action="email.read",
            recipients=[],
            query="from:finance@example.com",
        )
    )

    response = execute_email_calendar_request(
        request,
        adapter=FakeEmailCalendarAdapter(external_write=True),
        policy=EmailCalendarWorkerPolicy(),
    )

    assert response.status == "failed"
    assert response.error == "email/calendar verification failed"
    assert response.receipt.external_write is True
    assert response.receipt.forbidden_effects_observed is True
    assert response.receipt.verification_status == "failed"


def test_default_adapter_uses_configured_connector_mode_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "production")
    monkeypatch.delenv("GMAIL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MICROSOFT_GRAPH_ACCESS_TOKEN", raising=False)
    adapter = _default_adapter()
    request = email_calendar_action_request_from_mapping(
        _payload(
            request_id="email-calendar-default-adapter",
            capability_id="email.search",
            action="email.search",
            recipients=[],
            query="newer_than:1d",
        )
    )

    response = execute_email_calendar_request(
        request,
        adapter=adapter,
        policy=EmailCalendarWorkerPolicy(),
    )

    assert adapter is not None
    assert response.status == "failed"
    assert response.error == "connector credential unavailable"
    assert response.receipt.verification_status == "failed"
    assert response.receipt.external_write is False
