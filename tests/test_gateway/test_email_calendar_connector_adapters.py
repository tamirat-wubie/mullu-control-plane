"""Email/calendar connector adapter tests.

Purpose: prove concrete Gmail, Google Calendar, and Graph HTTP adapters remain
bounded by governed worker contracts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.email_calendar_connector_adapters.
Invariants:
  - Missing connector credentials fail closed before transport.
  - Read-only probes produce response digest evidence without external writes.
  - External sends require an approval witness before provider dispatch.
  - Provider tokens are used only in HTTP headers and never returned.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.email_calendar_connector_adapters import (  # noqa: E402
    ConnectorCredential,
    HttpEmailCalendarAdapter,
    build_email_calendar_adapter_from_env,
)
from gateway.email_calendar_worker import EmailCalendarActionRequest  # noqa: E402


def test_gmail_search_uses_read_only_http_request_with_digest() -> None:
    transport = FakeTransport(response_body={"messages": [{"id": "msg-1"}]})
    adapter = HttpEmailCalendarAdapter(
        credentials={
            "gmail": ConnectorCredential(
                connector_id="gmail",
                access_token="gmail-token",
                base_url="https://gmail.example",
                scope_id="scope:gmail",
            )
        },
        urlopen=transport,
    )
    request = _request(
        request_id="gmail-search-1",
        capability_id="email.search",
        action="email.search",
        connector_id="gmail",
        query="from:ops@example.com",
    )

    observation = adapter.perform(request)

    assert observation.succeeded is True
    assert observation.connector_id == "gmail"
    assert observation.provider_operation == "email.search"
    assert observation.resource_id == "msg-1"
    assert len(observation.response_digest) == 64
    assert observation.external_write is False
    assert transport.calls[0]["method"] == "GET"
    assert "from%3Aops%40example.com" in transport.calls[0]["url"]
    assert transport.calls[0]["authorization"] == "Bearer gmail-token"
    assert "gmail-token" not in observation.response_digest


def test_gmail_send_requires_approval_before_transport() -> None:
    transport = FakeTransport(response_body={"id": "sent-1"})
    adapter = HttpEmailCalendarAdapter(
        credentials={
            "gmail": ConnectorCredential(
                connector_id="gmail",
                access_token="gmail-token",
                base_url="https://gmail.example",
                scope_id="scope:gmail",
            )
        },
        urlopen=transport,
    )
    request = _request(
        request_id="gmail-send-blocked",
        capability_id="email.send.with_approval",
        action="email.send.with_approval",
        connector_id="gmail",
        recipients=("user@example.com",),
        subject="Status",
        body="Ready",
    )

    observation = adapter.perform(request)

    assert observation.succeeded is False
    assert observation.error == "approval witness required for connector write"
    assert observation.external_write is False
    assert observation.provider_operation == "email.send.with_approval"
    assert transport.calls == []


def test_gmail_send_with_approval_posts_message_body() -> None:
    transport = FakeTransport(response_body={"id": "sent-1"})
    adapter = HttpEmailCalendarAdapter(
        credentials={
            "gmail": ConnectorCredential(
                connector_id="gmail",
                access_token="gmail-token",
                base_url="https://gmail.example",
                scope_id="scope:gmail",
            )
        },
        urlopen=transport,
    )
    request = _request(
        request_id="gmail-send-approved",
        capability_id="email.send.with_approval",
        action="email.send.with_approval",
        connector_id="gmail",
        recipients=("user@example.com",),
        subject="Status",
        body="Ready",
        approval_id="approval-1",
    )

    observation = adapter.perform(request)
    body = transport.calls[0]["json_body"]

    assert observation.succeeded is True
    assert observation.resource_id == "sent-1"
    assert observation.external_write is True
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"] == "https://gmail.example/gmail/v1/users/me/messages/send"
    assert "raw" in body
    assert transport.calls[0]["authorization"] == "Bearer gmail-token"


def test_google_calendar_schedule_posts_event_with_attendees() -> None:
    transport = FakeTransport(response_body={"id": "event-1"})
    adapter = HttpEmailCalendarAdapter(
        credentials={
            "google_calendar": ConnectorCredential(
                connector_id="google_calendar",
                access_token="calendar-token",
                base_url="https://calendar.example",
                scope_id="scope:calendar",
            )
        },
        urlopen=transport,
    )
    request = _request(
        request_id="calendar-schedule-1",
        capability_id="calendar.schedule",
        action="calendar.schedule",
        connector_id="google_calendar",
        attendees=("attendee@example.com",),
        subject="Planning",
        body="Agenda",
        start_time="2026-05-01T15:00:00Z",
        end_time="2026-05-01T15:30:00Z",
        approval_id="approval-1",
    )

    observation = adapter.perform(request)
    body = transport.calls[0]["json_body"]

    assert observation.succeeded is True
    assert observation.resource_id == "event-1"
    assert observation.external_write is True
    assert body["summary"] == "Planning"
    assert body["attendees"] == [{"email": "attendee@example.com"}]
    assert body["start"]["dateTime"] == "2026-05-01T15:00:00Z"
    assert transport.calls[0]["method"] == "POST"


def test_missing_connector_credential_fails_closed_without_transport() -> None:
    transport = FakeTransport(response_body={"messages": [{"id": "msg-1"}]})
    adapter = HttpEmailCalendarAdapter(credentials={}, urlopen=transport)
    request = _request(
        request_id="missing-credential-1",
        capability_id="email.search",
        action="email.search",
        connector_id="gmail",
    )

    observation = adapter.perform(request)

    assert observation.succeeded is False
    assert observation.connector_id == "gmail"
    assert observation.provider_operation == "email.search"
    assert observation.error == "connector credential unavailable"
    assert transport.calls == []


def test_env_builder_enables_configured_connectors_only(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "production")
    monkeypatch.delenv("EMAIL_CALENDAR_CONNECTOR_TOKEN", raising=False)
    monkeypatch.delenv("EMAIL_CALENDAR_CONNECTOR_ID", raising=False)
    monkeypatch.setenv("GMAIL_ACCESS_TOKEN", "gmail-token")
    monkeypatch.delenv("GOOGLE_CALENDAR_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("MICROSOFT_GRAPH_ACCESS_TOKEN", "graph-token")

    adapter = build_email_calendar_adapter_from_env()

    assert isinstance(adapter, HttpEmailCalendarAdapter)
    assert sorted(adapter._credentials) == ["gmail", "microsoft_graph"]
    assert adapter._credentials["gmail"].base_url == "https://gmail.googleapis.com"
    assert adapter._credentials["microsoft_graph"].scope_id == "oauth:microsoft_graph"


def test_env_builder_accepts_governed_connector_token(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "production")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_TOKEN", "governed-token")
    monkeypatch.delenv("EMAIL_CALENDAR_CONNECTOR_ID", raising=False)
    monkeypatch.delenv("GMAIL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MICROSOFT_GRAPH_ACCESS_TOKEN", raising=False)

    adapter = build_email_calendar_adapter_from_env()

    assert isinstance(adapter, HttpEmailCalendarAdapter)
    assert sorted(adapter._credentials) == ["gmail"]
    assert adapter._credentials["gmail"].access_token == "governed-token"
    assert adapter._credentials["gmail"].scope_id == "governed:gmail"


def test_env_builder_rejects_unsupported_governed_connector_id(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_EMAIL_CALENDAR_WORKER_ADAPTER", "production")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_TOKEN", "governed-token")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_ID", "unknown")
    monkeypatch.delenv("GMAIL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MICROSOFT_GRAPH_ACCESS_TOKEN", raising=False)

    try:
        build_email_calendar_adapter_from_env()
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "EMAIL_CALENDAR_CONNECTOR_ID is unsupported"
    assert "governed-token" not in error
    assert "unknown" not in error


class FakeTransport:
    """urllib-compatible transport fixture that records bounded HTTP calls."""

    def __init__(self, *, response_body: dict[str, Any], status: int = 200) -> None:
        self._response_body = response_body
        self._status = status
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, *, timeout: float) -> "FakeResponse":
        json_body = json.loads(request.data.decode("utf-8")) if request.data else {}
        self.calls.append(
            {
                "method": request.get_method(),
                "url": request.full_url,
                "timeout": timeout,
                "authorization": request.get_header("Authorization"),
                "scope": request.get_header("X-mullu-connector-scope"),
                "json_body": json_body,
            }
        )
        return FakeResponse(status=self._status, body=self._response_body)


class FakeResponse:
    """Minimal HTTP response fixture."""

    def __init__(self, *, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def _request(**overrides: Any) -> EmailCalendarActionRequest:
    payload = {
        "request_id": "email-calendar-request",
        "tenant_id": "tenant-1",
        "capability_id": "email.search",
        "action": "email.search",
        "connector_id": "gmail",
        "subject": "",
        "body": "",
        "query": "",
        "event_id": "",
        "start_time": "",
        "end_time": "",
        "recipients": (),
        "attendees": (),
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return EmailCalendarActionRequest(**payload)
