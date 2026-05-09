"""Webhook endpoint tests for SMS, Teams, and phone channels.

Tests: /webhook/sms, /webhook/teams, /webhook/phone — configuration gating,
signature verification, message routing, and ignored-event handling.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import TenantMapping  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402


class StubPlatform:
    def __init__(self, response: str = "Governed response") -> None:
        self._response = response

    def connect(self, *, identity_id: str, tenant_id: str) -> "StubSession":
        return StubSession(self._response)


class StubSession:
    def __init__(self, response: str) -> None:
        self._response = response

    def llm(self, prompt: str, **_: object) -> object:
        return type("R", (), {"content": self._response, "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        pass


def _twilio_signature(token: str, url: str, params: dict[str, str]) -> str:
    signed = url
    for key in sorted(params):
        signed += key + str(params[key])
    digest = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _teams_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ── /webhook/sms ──


class TestSmsWebhookUnconfigured:
    def test_returns_503_without_twilio_credentials(self, monkeypatch) -> None:
        for env in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"):
            monkeypatch.delenv(env, raising=False)
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post("/webhook/sms", data={"From": "+1", "Body": "hi", "MessageSid": "SM1"})
        assert resp.status_code == 503


class TestSmsWebhookConfigured:
    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth-token")
        monkeypatch.setenv("TWILIO_SMS_SENDER", "+15555550111")
        monkeypatch.setenv("TWILIO_WEBHOOK_URL", "http://testserver/webhook/sms")

    def test_rejects_request_without_signature(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post(
            "/webhook/sms",
            data={"From": "+15555550100", "To": "+15555550111", "Body": "hi", "MessageSid": "SM1"},
        )
        assert resp.status_code == 403

    def test_routes_signed_message_to_governed_router(self) -> None:
        app = create_gateway_app(platform=StubPlatform(response="SMS reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="sms", sender_id="+15555550100",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        params = {
            "From": "+15555550100",
            "To": "+15555550111",
            "Body": "hello",
            "MessageSid": "SM1",
        }
        signature = _twilio_signature(
            "auth-token", "http://testserver/webhook/sms", params,
        )
        resp = client.post(
            "/webhook/sms",
            data=params,
            headers={"X-Twilio-Signature": signature},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "SMS reply"
        assert data["request_receipt"]["channel"] == "sms"
        assert data["request_receipt"]["path"] == "/webhook/sms"

    def test_ignored_payload_returns_status_ignored(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        params = {"MessageSid": "SM2"}  # missing From + Body — adapter returns None
        signature = _twilio_signature(
            "auth-token", "http://testserver/webhook/sms", params,
        )
        resp = client.post(
            "/webhook/sms",
            data=params,
            headers={"X-Twilio-Signature": signature},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── /webhook/teams ──


class TestTeamsWebhookUnconfigured:
    def test_returns_503_without_teams_credentials(self, monkeypatch) -> None:
        monkeypatch.delenv("MICROSOFT_TEAMS_ACCESS_TOKEN", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post("/webhook/teams", content=b"{}")
        assert resp.status_code == 503


class TestTeamsWebhookConfigured:
    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("MICROSOFT_TEAMS_ACCESS_TOKEN", "teams-token")
        monkeypatch.setenv("MICROSOFT_TEAMS_SHARED_SECRET", "shared-secret")

    def test_rejects_request_without_signature(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post("/webhook/teams", content=json.dumps({"type": "message"}))
        assert resp.status_code == 403

    def test_routes_signed_activity_to_governed_router(self) -> None:
        app = create_gateway_app(platform=StubPlatform(response="Teams reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="teams", sender_id="user-1",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        body = json.dumps({
            "type": "message",
            "id": "act-1",
            "from": {"id": "user-1", "name": "Alice"},
            "conversation": {"id": "19:abcd@thread.v2"},
            "text": "hello",
        }).encode("utf-8")
        signature = _teams_signature("shared-secret", body)
        resp = client.post(
            "/webhook/teams",
            content=body,
            headers={"X-Mullu-Teams-Signature": signature, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Teams reply"
        assert data["request_receipt"]["channel"] == "teams"

    def test_ignored_activity_returns_status_ignored(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        body = json.dumps({"type": "conversationUpdate", "id": "act-2"}).encode("utf-8")
        signature = _teams_signature("shared-secret", body)
        resp = client.post(
            "/webhook/teams",
            content=body,
            headers={"X-Mullu-Teams-Signature": signature, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── /webhook/phone ──


class TestPhoneWebhookUnconfigured:
    def test_returns_503_without_twilio_voice_credentials(self, monkeypatch) -> None:
        for env in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"):
            monkeypatch.delenv(env, raising=False)
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post("/webhook/phone", data={"CallSid": "CA1"})
        assert resp.status_code == 503


class TestPhoneWebhookConfigured:
    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth-token")
        monkeypatch.setenv("TWILIO_VOICE_CALLER_ID", "+15555550111")
        monkeypatch.setenv("TWILIO_VOICE_WEBHOOK_URL", "http://testserver/webhook/phone")

    def test_rejects_request_without_signature(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post(
            "/webhook/phone",
            data={"CallSid": "CA1", "From": "+15555550100", "CallStatus": "ringing"},
        )
        assert resp.status_code == 403

    def test_routes_signed_voice_event_to_governed_router(self) -> None:
        app = create_gateway_app(platform=StubPlatform(response="phone reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="phone", sender_id="+15555550100",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        params = {
            "CallSid": "CA1",
            "From": "+15555550100",
            "To": "+15555550111",
            "CallStatus": "ringing",
        }
        signature = _twilio_signature(
            "auth-token", "http://testserver/webhook/phone", params,
        )
        resp = client.post(
            "/webhook/phone",
            data=params,
            headers={"X-Twilio-Signature": signature},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "phone reply"
        assert data["request_receipt"]["channel"] == "phone"
        assert data["request_receipt"]["path"] == "/webhook/phone"

    def test_ignored_payload_returns_status_ignored(self) -> None:
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        params = {"CallSid": "CA2"}  # missing From — adapter returns None
        signature = _twilio_signature(
            "auth-token", "http://testserver/webhook/phone", params,
        )
        resp = client.post(
            "/webhook/phone",
            data=params,
            headers={"X-Twilio-Signature": signature},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── /health channel listing ──


class TestHealthChannelListing:
    def test_health_lists_new_channels_when_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "auth-token")
        monkeypatch.setenv("MICROSOFT_TEAMS_ACCESS_TOKEN", "teams-token")
        monkeypatch.setenv("MICROSOFT_TEAMS_SHARED_SECRET", "shared-secret")
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        configured = set(resp.json()["channels_configured"])
        assert {"sms", "teams", "phone"}.issubset(configured)
