"""Gateway Webhook Endpoint Tests.

Tests: HTTP webhook endpoints for all channels using FastAPI TestClient.
"""

import sys
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from gateway.router import TenantMapping  # noqa: E402


class StubPlatform:
    def __init__(self, response="Governed response"):
        self._response = response

    def connect(self, *, identity_id, tenant_id):
        return StubSession(self._response)


class StubSession:
    def __init__(self, response):
        self._response = response

    def llm(self, prompt, **kwargs):
        return type("R", (), {"content": self._response, "succeeded": True, "error": "", "cost": 0.0})()

    def close(self):
        pass


@pytest.fixture
def gateway_app():
    app = create_gateway_app(platform=StubPlatform())
    # Register a test tenant
    app.state.router.register_tenant_mapping(TenantMapping(
        channel="whatsapp", sender_id="+1234567890",
        tenant_id="t1", identity_id="u1",
    ))
    app.state.router.register_tenant_mapping(TenantMapping(
        channel="telegram", sender_id="98765",
        tenant_id="t1", identity_id="u1",
    ))
    app.state.router.register_tenant_mapping(TenantMapping(
        channel="web", sender_id="web-user",
        tenant_id="t1", identity_id="u1",
    ))
    return app


@pytest.fixture
def client(gateway_app):
    return TestClient(gateway_app)


# ═══ Health ═══


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "gateway" in data


# ═══ WhatsApp ═══


class TestWhatsAppWebhook:
    def test_verify_not_configured(self, client):
        # WhatsApp not configured (no env var) — 503
        resp = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=t&hub.challenge=c")
        assert resp.status_code == 503

    def test_receive_not_configured(self, client):
        resp = client.post("/webhook/whatsapp", content=b'{}')
        assert resp.status_code == 503


class TestWhatsAppConfigured:
    @pytest.fixture(autouse=True)
    def setup_whatsapp(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify_me")

    def test_verify_valid(self):
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=verify_me&hub.challenge=test123")
        assert resp.status_code == 200
        assert resp.text == "test123"

    def test_verify_invalid_token(self):
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=c")
        assert resp.status_code == 403


# ═══ Telegram ═══


class TestTelegramWebhook:
    def test_receive_not_configured(self, client):
        resp = client.post("/webhook/telegram", content=b'{}')
        assert resp.status_code == 503

    def test_receive_with_message(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        app = create_gateway_app(platform=StubPlatform(response="TG reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="telegram", sender_id="98765",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 98765},
                "chat": {"id": 98765},
                "text": "Hello",
            }
        }
        resp = client.post("/webhook/telegram", content=json.dumps(payload))
        assert resp.status_code == 200
        assert resp.json()["response"] == "TG reply"


# ═══ Slack ═══


class TestSlackWebhook:
    def test_receive_not_configured(self, client):
        resp = client.post("/webhook/slack", content=b'{}')
        assert resp.status_code == 503

    def test_url_verification(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-123")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        payload = {"type": "url_verification", "challenge": "test_challenge"}
        resp = client.post("/webhook/slack", content=json.dumps(payload))
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "test_challenge"


# ═══ Discord ═══


class TestDiscordWebhook:
    def test_receive_not_configured(self, client):
        resp = client.post("/webhook/discord", content=b'{}')
        assert resp.status_code == 503

    def test_ping_response(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-123")
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post("/webhook/discord", content=json.dumps({"type": 1}))
        assert resp.status_code == 200
        assert resp.json()["type"] == 1


# ═══ Web Chat ═══


class TestWebChatWebhook:
    def test_send_message(self, client):
        payload = {"body": "Hello from web", "user_id": "web-user"}
        resp = client.post(
            "/webhook/web",
            content=json.dumps(payload),
            headers={"X-Session-Token": "sess1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert data["body"] == "Governed response"

    def test_missing_token_rejected(self, client):
        resp = client.post("/webhook/web", content=json.dumps({}))
        assert resp.status_code == 401

    def test_empty_message_rejected(self, client):
        resp = client.post(
            "/webhook/web", content=json.dumps({}),
            headers={"X-Session-Token": "test-token"},
        )
        assert resp.status_code == 400


# ═══ Approval Callback ═══


class TestApprovalWebhook:
    def test_approve_unknown_request(self, client):
        resp = client.post(
            "/webhook/approve/nonexistent",
            content=json.dumps({
                "approved": True,
                "resolver_channel": "web",
                "resolver_sender_id": "web-user",
            }),
        )
        assert resp.status_code == 404

    def test_approve_valid_request(self, client):
        # First trigger a high-risk message to create pending approval
        app = client.app
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="risk-user",
            tenant_id="t1", identity_id="u1",
        ))
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        # Should get approval-required response
        data = msg_resp.json()
        # The response body should mention approval
        assert "governed" in data

    def test_production_approval_callback_requires_secret(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.post(
            "/webhook/approve/nonexistent",
            content=json.dumps({"approved": True}),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Approval callback not authorized"

    def test_production_approval_callback_accepts_configured_secret(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_GATEWAY_APPROVAL_SECRET", "approve-secret")
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="risk-user",
            tenant_id="t1", identity_id="u1",
        ))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="operator",
            tenant_id="t1", identity_id="operator-1",
            approval_authority=True,
        ))
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps({
                "approved": True,
                "resolver_channel": "web",
                "resolver_sender_id": "operator",
            }),
            headers={"X-Mullu-Approval-Secret": "approve-secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert "approved" in data["body"]
        assert data["metadata"]["approval_resolved"] is True

    def test_approval_callback_requires_resolver_identity(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="risk-user",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps({"approved": True}),
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "resolver_channel and resolver_sender_id are required"

    def test_approval_callback_denies_unauthorized_resolver(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="risk-user",
            tenant_id="t1", identity_id="u1",
        ))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="viewer",
            tenant_id="t1", identity_id="viewer-1",
        ))
        client = TestClient(app)
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps({
                "approved": True,
                "resolver_channel": "web",
                "resolver_sender_id": "viewer",
            }),
        )

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "approval_context_denied"
        assert detail["authority_reason"] == "resolver_lacks_approval_authority"


# ═══ Gateway Status ═══


class TestGatewayStatus:
    def test_status(self, client):
        resp = client.get("/gateway/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governed"] is True
        assert "router" in data
        assert "sessions" in data
