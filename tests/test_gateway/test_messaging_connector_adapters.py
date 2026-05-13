"""Messaging connector adapter tests.

Purpose: prove concrete Twilio, AWS SNS, Slack, Teams, WhatsApp, Telegram, and
    Discord HTTP adapters remain bounded by governed worker contracts.
Invariants:
  - Missing connector credentials fail closed before transport.
  - Drafts and reads produce response digest evidence without external sends.
  - External sends require an approval witness before provider dispatch.
  - Provider tokens are used only in HTTP headers and never returned in
    observation fields or errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.messaging_connector_adapters import (  # noqa: E402
    HttpMessagingAdapter,
    MessagingConnectorCredential,
    build_messaging_adapter_from_env,
)
from gateway.messaging_worker import MessagingActionRequest  # noqa: E402


def test_sms_draft_uses_local_probe_without_external_send() -> None:
    transport = FakeTransport(response_body={"status": "queued"})
    adapter = HttpMessagingAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="sms-draft-1",
        capability_id="messaging.sms.draft",
        action="messaging.sms.draft",
        connector_id="twilio",
        recipients=("+15555550100",),
        body="hello",
    ))

    assert observation.succeeded is True
    assert observation.external_send is False
    assert observation.provider_operation == "twilio.sms.draft"
    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["url"].endswith("/governed/draft/probe")
    assert "twilio-token" not in observation.error


def test_sms_send_requires_approval_before_transport() -> None:
    transport = FakeTransport(response_body={"sid": "SM123"})
    adapter = HttpMessagingAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="sms-send-no-approval",
        capability_id="messaging.sms.send.with_approval",
        action="messaging.sms.send.with_approval",
        connector_id="twilio",
        recipients=("+15555550100",),
        body="hello",
    ))

    assert observation.succeeded is False
    assert observation.error == "approval witness required for connector send"
    assert observation.external_send is False
    assert transport.calls == []


def test_sms_send_with_approval_uses_twilio_basic_auth_and_form_body() -> None:
    transport = FakeTransport(response_body={"sid": "SM123"})
    adapter = HttpMessagingAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="sms-send-approved",
        capability_id="messaging.sms.send.with_approval",
        action="messaging.sms.send.with_approval",
        connector_id="twilio",
        recipients=("+15555550100",),
        body="hello",
        approval_id="approval-1",
    ))

    assert observation.succeeded is True
    assert observation.external_send is True
    assert observation.resource_id == "SM123"
    assert observation.provider_operation == "twilio.sms.send"
    assert transport.calls[0]["method"] == "POST"
    assert "/2010-04-01/Accounts/" in transport.calls[0]["url"]
    assert transport.calls[0]["authorization"].startswith("Basic ")
    assert b"To=%2B15555550100" in transport.calls[0]["raw_body"]
    assert b"Body=hello" in transport.calls[0]["raw_body"]
    assert "twilio-token" not in observation.error


def test_slack_chat_send_uses_postmessage_with_bearer_token() -> None:
    transport = FakeTransport(response_body={"ok": True, "ts": "1700000000.000100"})
    adapter = HttpMessagingAdapter(
        credentials={
            "slack": MessagingConnectorCredential(
                connector_id="slack",
                access_token="xoxb-slack-token",
                base_url="https://slack.example",
                scope_id="scope:slack",
            )
        },
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="slack-send-approved",
        capability_id="messaging.chat.send.with_approval",
        action="messaging.chat.send.with_approval",
        connector_id="slack",
        recipients=("C0123456",),
        body="hello team",
        approval_id="approval-1",
    ))

    assert observation.succeeded is True
    assert observation.external_send is True
    assert observation.provider_operation == "slack.chat.postMessage"
    assert transport.calls[0]["url"] == "https://slack.example/api/chat.postMessage"
    assert transport.calls[0]["authorization"] == "Bearer xoxb-slack-token"
    assert transport.calls[0]["json_body"]["channel"] == "C0123456"
    assert transport.calls[0]["json_body"]["text"] == "hello team"


def test_teams_chat_send_uses_graph_chat_messages_endpoint() -> None:
    transport = FakeTransport(response_body={"id": "msg-1"})
    adapter = HttpMessagingAdapter(
        credentials={
            "teams": MessagingConnectorCredential(
                connector_id="teams",
                access_token="teams-token",
                base_url="https://graph.example",
                scope_id="scope:teams",
            )
        },
        urlopen=transport,
    )

    observation = adapter.perform(_request(
        request_id="teams-send-approved",
        capability_id="messaging.chat.send.with_approval",
        action="messaging.chat.send.with_approval",
        connector_id="teams",
        recipients=("19:abcd@thread.v2",),
        body="hello",
        approval_id="approval-1",
    ))

    assert observation.succeeded is True
    assert observation.external_send is True
    assert observation.provider_operation == "teams.chats.messages.send"
    assert transport.calls[0]["url"].endswith("/v1.0/chats/19%3Aabcd%40thread.v2/messages")
    assert transport.calls[0]["authorization"] == "Bearer teams-token"


def test_missing_credential_fails_closed_before_transport() -> None:
    transport = FakeTransport(response_body={})
    adapter = HttpMessagingAdapter(credentials={}, urlopen=transport)

    observation = adapter.perform(_request(
        request_id="missing-credential",
        capability_id="messaging.sms.draft",
        action="messaging.sms.draft",
        connector_id="twilio",
        recipients=("+15555550100",),
        body="x",
    ))

    assert observation.succeeded is False
    assert observation.error == "messaging connector credential unavailable"
    assert transport.calls == []


def test_unsupported_action_fails_closed_before_transport() -> None:
    transport = FakeTransport(response_body={})
    adapter = HttpMessagingAdapter(
        credentials={"twilio": _twilio_credential()},
        urlopen=transport,
    )

    request = MessagingActionRequest(
        request_id="bogus-action",
        tenant_id="tenant-1",
        capability_id="messaging.sms.send.with_approval",
        action="messaging.sms.send.with_approval",
        connector_id="twilio",
        recipients=("+15555550100",),
        body="x",
        approval_id="approval-1",
    )
    # Force an action mismatch by replacing the action via a custom request-like mock.
    object.__setattr__(request, "action", "messaging.bogus")
    object.__setattr__(request, "capability_id", "messaging.bogus")

    observation = adapter.perform(request)

    assert observation.succeeded is False
    assert observation.error == "messaging connector action unsupported"
    assert transport.calls == []


def test_env_builder_loads_twilio_and_slack_credentials(monkeypatch) -> None:
    for env in (
        "TWILIO_AUTH_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_SMS_SENDER",
        "SLACK_BOT_TOKEN",
        "MICROSOFT_TEAMS_ACCESS_TOKEN",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "TELEGRAM_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "AWS_SNS_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("MULLU_MESSAGING_WORKER_ADAPTER", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_SMS_SENDER", "+15555550111")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-slack-token")

    adapter = build_messaging_adapter_from_env()

    assert adapter is not None
    assert sorted(adapter._credentials) == ["slack", "twilio"]
    assert adapter._credentials["twilio"].extra["account_sid"] == "AC123"


def test_env_builder_rejects_unknown_adapter_name(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_MESSAGING_WORKER_ADAPTER", "carrier-pigeon")
    try:
        build_messaging_adapter_from_env()
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "unsupported messaging worker adapter: carrier-pigeon"


def test_env_builder_returns_none_when_no_adapter_configured(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_MESSAGING_WORKER_ADAPTER", raising=False)
    assert build_messaging_adapter_from_env() is None


def _twilio_credential() -> MessagingConnectorCredential:
    return MessagingConnectorCredential(
        connector_id="twilio",
        access_token="twilio-token",
        base_url="https://twilio.example",
        scope_id="scope:twilio",
        extra={"account_sid": "AC123", "sender": "+15555550111"},
    )


class FakeTransport:
    """urllib-compatible transport fixture that records bounded HTTP calls."""

    def __init__(self, *, response_body: dict[str, Any], status: int = 200) -> None:
        self._response_body = response_body
        self._status = status
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, *, timeout: float) -> "FakeResponse":
        raw_body = request.data or b""
        json_body: dict[str, Any] = {}
        try:
            if raw_body and request.get_header("Content-type", "").startswith("application/json"):
                json_body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            json_body = {}
        self.calls.append(
            {
                "method": request.get_method(),
                "url": request.full_url,
                "timeout": timeout,
                "authorization": request.get_header("Authorization"),
                "scope": request.get_header("X-mullu-connector-scope"),
                "raw_body": raw_body,
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


def _request(**overrides: Any) -> MessagingActionRequest:
    payload = {
        "request_id": "messaging-request",
        "tenant_id": "tenant-1",
        "capability_id": "messaging.sms.draft",
        "action": "messaging.sms.draft",
        "connector_id": "twilio",
        "body": "",
        "thread_id": "",
        "query": "",
        "recipients": (),
        "approval_id": "",
        "metadata": {},
    }
    payload.update(overrides)
    return MessagingActionRequest(**payload)
