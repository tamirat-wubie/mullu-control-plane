"""Gateway Webhook Endpoint Tests.

Tests: HTTP webhook endpoints for all channels using FastAPI TestClient.
"""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from gateway.authority_obligation_mesh import (  # noqa: E402
    ApprovalChain,
    ApprovalChainStatus,
    Obligation,
    ObligationStatus,
)
from gateway.command_spine import CommandState  # noqa: E402
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


def _assert_gateway_request_receipt(
    receipt: dict,
    *,
    channel: str,
    path: str,
    message_id_prefix: str = "",
    sender_expected: bool = True,
) -> None:
    assert receipt["receipt_type"] == "gateway_request_receipt_v1"
    assert receipt["channel"] == channel
    assert receipt["path"] == path
    assert receipt["body_hash"]
    assert receipt["receipt_hash"]
    assert receipt["receipt_id"].startswith("gateway-request-")
    if message_id_prefix:
        assert receipt["message_id"].startswith(message_id_prefix)
    else:
        assert receipt["message_id"] == ""
    if sender_expected:
        assert receipt["sender_id_hash"]
    else:
        assert receipt["sender_id_hash"] == ""


def _slack_signature(*, secret: str, timestamp: str, body: str) -> str:
    return "v0=" + hmac.new(
        secret.encode(),
        f"v0:{timestamp}:{body}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _fabric_capability_payload(capability_id: str) -> dict:
    return {
        "capability_id": capability_id,
        "domain": "gateway",
        "version": "1.0.0",
        "input_schema_ref": f"schemas/gateway/{capability_id}.input.schema.json",
        "output_schema_ref": f"schemas/gateway/{capability_id}.output.schema.json",
        "effect_model": {
            "expected_effects": ["gateway_response_emitted"],
            "forbidden_effects": ["unauthorized_state_mutation"],
            "reconciliation_required": False,
        },
        "evidence_model": {
            "required_evidence": ["command_id", "trace_id", "output_hash"],
            "terminal_certificate_required": True,
        },
        "authority_policy": {
            "required_roles": ["tenant_member"],
            "approval_chain": [],
            "separation_of_duty": False,
        },
        "isolation_profile": {
            "execution_plane": "model_provider",
            "network_allowlist": ["api.mullusi.com"],
            "secret_scope": "tenant:gateway:model_provider",
        },
        "recovery_plan": {
            "rollback_capability": "",
            "compensation_capability": "create_correction_response",
            "review_required_on_failure": True,
        },
        "cost_model": {
            "budget_class": "gateway_model_call",
            "max_estimated_cost": 0.25,
        },
        "obligation_model": {
            "owner_team": "gateway_ops",
            "failure_due_seconds": 3600,
            "escalation_route": "gateway_ops_lead",
        },
        "certification_status": "certified",
        "metadata": {"risk_tier": "low"},
        "extensions": {},
    }


def _fabric_capsule_payload(capability_refs: str | list[str]) -> dict:
    refs = [capability_refs] if isinstance(capability_refs, str) else list(capability_refs)
    return {
        "capsule_id": "gateway.web_chat",
        "domain": "gateway",
        "version": "1.0.0",
        "ontology_refs": ["ontology/gateway/web_chat"],
        "capability_refs": refs,
        "policy_refs": ["policies/gateway/member_access"],
        "evidence_rules": ["gateway_response_evidence_required"],
        "approval_rules": ["tenant_member_required"],
        "recovery_rules": ["correction_response_available"],
        "test_fixture_refs": ["fixtures/gateway/web_chat_success"],
        "read_model_refs": ["read_models/gateway/command_closure"],
        "operator_view_refs": ["views/gateway/effects"],
        "owner_team": "gateway_ops",
        "certification_status": "certified",
        "metadata": {"purpose": "Gateway web chat fabric test capsule"},
        "extensions": {},
    }


def _configure_fabric_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    capability_refs: list[str],
    capability_payloads: list[dict],
    use_pack: bool,
) -> None:
    capsule_path = tmp_path / "domain_capsule.json"
    capsule_path.write_text(json.dumps(_fabric_capsule_payload(capability_refs)), encoding="utf-8")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", str(capsule_path))
    if use_pack:
        pack_path = tmp_path / "capability_pack.json"
        pack_path.write_text(json.dumps({"capabilities": capability_payloads}), encoding="utf-8")
        monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", str(pack_path))
    else:
        capability_path = tmp_path / "capability.json"
        capability_path.write_text(json.dumps(capability_payloads[0]), encoding="utf-8")
        monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH", str(capability_path))


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

    def test_receive_with_message_returns_request_receipt(self):
        app = create_gateway_app(platform=StubPlatform(response="WA reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="+1234567890",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "+1234567890",
                            "id": "wamid.1",
                            "type": "text",
                            "text": {"body": "Hello"},
                        }]
                    }
                }]
            }]
        }
        resp = client.post("/webhook/whatsapp", content=json.dumps(payload))
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "WA reply"
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="whatsapp",
            path="/webhook/whatsapp",
            message_id_prefix="wamid.",
        )


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
        data = resp.json()
        assert data["response"] == "TG reply"
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="telegram",
            path="/webhook/telegram",
            message_id_prefix="tg-",
        )

    def test_ignored_update_returns_request_receipt(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        app = create_gateway_app(platform=StubPlatform(response="ignored"))
        client = TestClient(app)
        resp = client.post("/webhook/telegram", content=json.dumps({"update_id": 2}))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="telegram",
            path="/webhook/telegram",
            sender_expected=False,
        )


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

    def test_receive_with_message_returns_request_receipt(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-123")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        app = create_gateway_app(platform=StubPlatform(response="Slack reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="slack", sender_id="U123",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message",
                "user": "U123",
                "channel": "C1",
                "text": "Hello",
                "ts": "1710000000.000100",
            },
        }
        body = json.dumps(payload)
        timestamp = str(int(time.time()))
        resp = client.post(
            "/webhook/slack",
            content=body,
            headers={
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": _slack_signature(
                    secret="secret",
                    timestamp=timestamp,
                    body=body,
                ),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Slack reply"
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="slack",
            path="/webhook/slack",
            message_id_prefix="slack-",
        )


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

    def test_receive_with_command_returns_request_receipt(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-123")
        app = create_gateway_app(platform=StubPlatform(response="Discord reply"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="discord", sender_id="D123",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)
        payload = {
            "type": 2,
            "id": "interaction-1",
            "guild_id": "G1",
            "channel_id": "C1",
            "member": {"user": {"id": "D123"}},
            "data": {"name": "hello"},
        }
        resp = client.post("/webhook/discord", content=json.dumps(payload))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["content"] == "Discord reply"
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="discord",
            path="/webhook/discord",
            message_id_prefix="discord-",
        )


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
        _assert_gateway_request_receipt(
            data["request_receipt"],
            channel="web",
            path="/webhook/web",
            message_id_prefix="web-",
        )
        assert "x-session-token" not in data["request_receipt"]["safe_header_names"]

    def test_missing_token_rejected(self, client):
        resp = client.post("/webhook/web", content=json.dumps({}))
        assert resp.status_code == 401

    def test_empty_message_rejected(self, client):
        resp = client.post(
            "/webhook/web", content=json.dumps({}),
            headers={"X-Session-Token": "test-token"},
        )
        assert resp.status_code == 400

    def test_fabric_admission_accepts_single_capability_source(self, monkeypatch, tmp_path):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=False,
        )
        app = create_gateway_app(platform=StubPlatform(response="Fabric governed response"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)

        resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "sess1"},
        )

        assert app.state.capability_admission_gate is not None
        assert resp.status_code == 200
        assert resp.json()["body"] == "Fabric governed response"
        command_id = resp.json()["message_id"].removeprefix("resp-")
        audit_resp = client.get(f"/commands/{command_id}/capability-admission")
        audits_resp = client.get("/capability-fabric/admission-audits?tenant_id=t1&status=accepted")

        assert audit_resp.status_code == 200
        assert audit_resp.json()["status"] == "accepted"
        assert audit_resp.json()["capability_id"] == "llm_completion"
        assert audit_resp.json()["admission_event_hash"]
        assert audits_resp.status_code == 200
        assert audits_resp.json()["count"] == 1
        assert audits_resp.json()["admission_audits"][0]["command_id"] == command_id

    def test_capability_fabric_read_model_reports_disabled_state(self, client):
        resp = client.get("/capability-fabric/read-model")

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["capsule_count"] == 0
        assert data["capability_count"] == 0

    def test_fabric_admission_accepts_capability_pack_source(self, monkeypatch, tmp_path):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion"],
            capability_payloads=[
                _fabric_capability_payload("llm_completion"),
                _fabric_capability_payload("financial.balance_check"),
            ],
            use_pack=True,
        )
        app = create_gateway_app(platform=StubPlatform(response="Pack governed response"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)

        resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "sess1"},
        )

        assert app.state.capability_admission_gate is not None
        assert resp.status_code == 200
        assert resp.json()["body"] == "Pack governed response"

    def test_command_capability_admission_read_model_reports_accepted_witness(self, monkeypatch, tmp_path):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=True,
        )
        app = create_gateway_app(platform=StubPlatform(response="Audit governed response"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "fabric-audit-accepted"},
        )
        certificate = app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        audit_resp = client.get(f"/commands/{certificate.command_id}/capability-admission")

        assert msg_resp.status_code == 200
        assert audit_resp.status_code == 200
        audit = audit_resp.json()
        assert audit["command_id"] == certificate.command_id
        assert audit["fabric_configured"] is True
        assert audit["status"] == "accepted"
        assert audit["capability_id"] == "llm_completion"
        assert audit["capability_registry_entry"]["capability_id"] == "llm_completion"
        assert audit["admission_event_hash"]
        assert audit["registry_event_hash"]

    def test_fabric_admission_rejects_missing_pack_capability(self, monkeypatch, tmp_path):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion", "financial.balance_check"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=True,
        )

        with pytest.raises(ValueError, match="missing capabilities"):
            create_gateway_app(platform=StubPlatform())

    def test_fabric_admission_blocks_uninstalled_runtime_intent(self, monkeypatch, tmp_path):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["financial.balance_check"],
            capability_payloads=[_fabric_capability_payload("financial.balance_check")],
            use_pack=True,
        )
        app = create_gateway_app(platform=StubPlatform(response="should not execute"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        client = TestClient(app)

        resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "fabric-runtime-reject"},
        )
        audits_resp = client.get("/capability-fabric/admission-audits?tenant_id=t1&status=rejected")

        assert resp.status_code == 200
        assert resp.json()["metadata"]["error"] == "capability_admission_rejected"
        assert resp.json()["body"] == "This command requires capability review before execution."
        assert "llm_completion" in resp.json()["metadata"]["reason"]
        assert audits_resp.status_code == 200
        assert audits_resp.json()["count"] == 1
        assert audits_resp.json()["admission_audits"][0]["status"] == "rejected"


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

    def test_gateway_witness(self, client):
        resp = client.get("/gateway/witness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["environment"]
        assert data["runtime_status"] == "healthy"
        assert data["gateway_status"] in {"healthy", "degraded"}
        assert "latest_command_event_hash" in data
        assert "latest_terminal_certificate_id" in data
        assert data["signature_key_id"]
        assert data["signature"].startswith("hmac-sha256:")

    def test_runtime_witness_alias(self, client):
        resp = client.get("/runtime/witness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["witness_id"].startswith("runtime-witness-")
        assert data["signature"].startswith("hmac-sha256:")

    def test_authority_witness_read_model(self, client):
        resp = client.get("/authority/witness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_approval_chain_count"] == 0
        assert data["open_obligation_count"] == 0
        assert data["unowned_high_risk_capability_count"] == 0

    def test_authority_operator_console_renders_empty_state(self, client):
        resp = client.get("/authority/operator")

        assert resp.status_code == 200
        assert "Mullu Authority Operator Console" in resp.text
        assert "Responsibility Witness" in resp.text
        assert "No records" in resp.text

    def test_authority_operator_secret_required_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_AUTHORITY_OPERATOR_SECRET", "authority-secret")
        app = create_gateway_app(platform=StubPlatform())
        local_client = TestClient(app)

        denied = local_client.get("/authority/witness")
        allowed = local_client.get(
            "/authority/witness",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        console_allowed = local_client.get(
            "/authority/operator",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        audit_allowed = local_client.get(
            "/authority/operator-audit?authorized=false",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )

        assert denied.status_code == 403
        assert denied.json()["detail"] == "Authority operator access not authorized"
        assert allowed.status_code == 200
        assert allowed.json()["open_obligation_count"] == 0
        assert console_allowed.status_code == 200
        assert "Mullu Authority Operator Console" in console_allowed.text
        assert audit_allowed.status_code == 200
        assert audit_allowed.json()["count"] == 1
        assert audit_allowed.json()["operator_audit_events"][0]["path"] == "/authority/witness"
        assert audit_allowed.json()["operator_audit_events"][0]["authorized"] is False
        assert "authority-secret" not in json.dumps(audit_allowed.json())

    def test_authority_operator_identity_role_allowed_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.delenv("MULLU_AUTHORITY_OPERATOR_SECRET", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="authority-user",
            tenant_id="t1", identity_id="authority-1",
            roles=("authority_operator",),
        ))
        local_client = TestClient(app)

        allowed = local_client.get(
            "/authority/witness",
            headers={
                "X-Mullu-Authority-Channel": "web",
                "X-Mullu-Authority-Sender-Id": "authority-user",
                "X-Mullu-Authority-Tenant-Id": "t1",
            },
        )
        denied_wrong_tenant = local_client.get(
            "/authority/witness",
            headers={
                "X-Mullu-Authority-Channel": "web",
                "X-Mullu-Authority-Sender-Id": "authority-user",
                "X-Mullu-Authority-Tenant-Id": "other-tenant",
            },
        )

        assert allowed.status_code == 200
        assert allowed.json()["open_obligation_count"] == 0
        assert denied_wrong_tenant.status_code == 403
        assert denied_wrong_tenant.json()["detail"] == "Authority operator access not authorized"

    def test_authority_operator_identity_role_denied_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.delenv("MULLU_AUTHORITY_OPERATOR_SECRET", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="member-user",
            tenant_id="t1", identity_id="member-1",
            roles=("tenant_member",),
        ))
        local_client = TestClient(app)

        denied = local_client.get(
            "/authority/operator",
            headers={
                "X-Mullu-Authority-Channel": "web",
                "X-Mullu-Authority-Sender-Id": "member-user",
                "X-Mullu-Authority-Tenant-Id": "t1",
            },
        )

        assert denied.status_code == 403
        assert denied.json()["detail"] == "Authority operator access not authorized"

    def test_authority_approval_chain_read_model(self, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "make a payment of $50", "user_id": "web-user"}),
            headers={"X-Session-Token": "authority-chain-token"},
        )
        assert msg_resp.status_code == 200

        list_resp = client.get("/authority/approval-chains?status=pending")
        paged_resp = client.get("/authority/approval-chains?status=pending&limit=1&offset=0")
        assert list_resp.status_code == 200
        assert paged_resp.status_code == 200
        chains = list_resp.json()["approval_chains"]
        assert chains
        command_id = chains[0]["command_id"]
        command_resp = client.get(f"/commands/{command_id}/authority")
        witness_resp = client.get("/authority/witness")
        console_resp = client.get("/authority/operator")

        assert any(chain["command_id"] == command_id for chain in chains)
        assert paged_resp.json()["count"] == 1
        assert paged_resp.json()["total"] >= 1
        assert paged_resp.json()["limit"] == 1
        assert paged_resp.json()["offset"] == 0
        assert command_resp.status_code == 200
        command_data = command_resp.json()
        assert command_data["approval_chain"]["command_id"] == command_id
        assert command_data["approval_chain"]["status"] == "pending"
        assert witness_resp.json()["pending_approval_chain_count"] >= 1
        assert console_resp.status_code == 200
        assert command_id in console_resp.text
        assert "pending" in console_resp.text

    def test_authority_operator_audit_read_model(self, client):
        witness_resp = client.get("/authority/witness")
        obligations_resp = client.get("/authority/obligations?limit=1")
        audit_resp = client.get("/authority/operator-audit?limit=2&offset=0")
        filtered_resp = client.get("/authority/operator-audit?path=/authority/witness&authorized=true")
        invalid_resp = client.get("/authority/operator-audit?authorized=maybe")
        console_resp = client.get("/authority/operator")

        assert witness_resp.status_code == 200
        assert obligations_resp.status_code == 200
        assert audit_resp.status_code == 200
        assert audit_resp.json()["count"] == 2
        assert audit_resp.json()["total"] >= 3
        assert audit_resp.json()["limit"] == 2
        assert audit_resp.json()["offset"] == 0
        assert audit_resp.json()["next_offset"] == 2
        assert any(
            event["path"] == "/authority/witness" and event["authorized"] is True
            for event in filtered_resp.json()["operator_audit_events"]
        )
        assert all("sender_id" not in event for event in audit_resp.json()["operator_audit_events"])
        assert invalid_resp.status_code == 400
        assert invalid_resp.json()["detail"] == "authorized must be true or false"
        assert console_resp.status_code == 200
        assert "Operator Audit" in console_resp.text

    def test_authority_obligation_and_escalation_read_models(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "authority-obligation-read-model-token"},
        )
        assert msg_resp.status_code == 200
        certificate = gateway_app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        obligation = Obligation(
            obligation_id="obligation-test-read-model",
            command_id=certificate.command_id,
            tenant_id="t1",
            owner_id="u1",
            owner_team="ops",
            obligation_type="case_review",
            due_at="2026-04-24T12:00:00+00:00",
            status=ObligationStatus.OPEN,
            evidence_required=("case_disposition",),
            escalation_policy_id="default",
            terminal_certificate_id="terminal-test-read-model",
        )
        gateway_app.state.authority_mesh_store.save_obligation(obligation)
        gateway_app.state.authority_mesh_store.append_escalation_event({
            "event_id": "obl-escalation-test-read-model",
            "obligation_id": obligation.obligation_id,
            "command_id": obligation.command_id,
            "tenant_id": obligation.tenant_id,
            "owner_id": obligation.owner_id,
            "owner_team": obligation.owner_team,
            "escalated_at": "2026-04-24T13:00:00+00:00",
        })
        second_obligation = Obligation(
            obligation_id="obligation-test-read-model-second",
            command_id=certificate.command_id,
            tenant_id="t1",
            owner_id="u2",
            owner_team="ops",
            obligation_type="operator_followup",
            due_at="2026-04-25T12:00:00+00:00",
            status=ObligationStatus.OPEN,
            evidence_required=("case_disposition",),
            escalation_policy_id="default",
            terminal_certificate_id="terminal-test-read-model",
        )
        gateway_app.state.authority_mesh_store.save_obligation(second_obligation)
        compensation_obligation = Obligation(
            obligation_id="obligation-test-read-model-compensation",
            command_id=certificate.command_id,
            tenant_id="t1",
            owner_id="u3",
            owner_team="finance_ops",
            obligation_type="compensation_review",
            due_at="2026-04-26T12:00:00+00:00",
            status=ObligationStatus.OPEN,
            evidence_required=("compensation_receipt", "compensation_reviewer_attestation"),
            escalation_policy_id="default",
            terminal_certificate_id="terminal-test-read-model",
        )
        gateway_app.state.authority_mesh_store.save_obligation(compensation_obligation)
        gateway_app.state.authority_mesh_store.append_escalation_event({
            "event_id": "obl-escalation-test-read-model-second",
            "obligation_id": second_obligation.obligation_id,
            "command_id": second_obligation.command_id,
            "tenant_id": second_obligation.tenant_id,
            "owner_id": second_obligation.owner_id,
            "owner_team": second_obligation.owner_team,
            "escalated_at": "2026-04-25T13:00:00+00:00",
        })

        obligations_resp = client.get("/authority/obligations?tenant_id=t1&status=open&limit=1")
        case_obligations_resp = client.get("/authority/obligations?tenant_id=t1&obligation_type=case_review")
        compensation_obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&obligation_type=compensation_review"
        )
        missing_evidence_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": []},
        )
        satisfy_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": ["case:read-model-closed"]},
        )
        command_resp = client.get(f"/commands/{obligation.command_id}/authority")
        escalations_resp = client.get(f"/authority/escalations?command_id={obligation.command_id}&limit=1")
        satisfied_resp = client.get("/authority/obligations?tenant_id=t1&status=satisfied")
        witness_resp = client.get("/authority/witness")
        console_resp = client.get("/authority/operator")

        assert obligations_resp.status_code == 200
        assert obligations_resp.json()["count"] == 1
        assert obligations_resp.json()["total"] == 3
        assert obligations_resp.json()["limit"] == 1
        assert obligations_resp.json()["offset"] == 0
        assert obligations_resp.json()["next_offset"] == 1
        assert obligations_resp.json()["obligations"][0]["obligation_id"] == obligation.obligation_id
        assert case_obligations_resp.status_code == 200
        assert case_obligations_resp.json()["count"] == 1
        assert case_obligations_resp.json()["obligations"][0]["obligation_type"] == "case_review"
        assert compensation_obligations_resp.status_code == 200
        assert compensation_obligations_resp.json()["count"] == 1
        assert compensation_obligations_resp.json()["obligations"][0]["owner_team"] == "finance_ops"
        assert (
            compensation_obligations_resp.json()["obligations"][0]["evidence_required"]
            == ["compensation_receipt", "compensation_reviewer_attestation"]
        )
        assert missing_evidence_resp.status_code == 400
        assert satisfy_resp.status_code == 200
        assert satisfy_resp.json()["status"] == "satisfied"
        assert satisfy_resp.json()["obligation"]["status"] == "satisfied"
        assert satisfy_resp.json()["evidence_refs"] == ["case:read-model-closed"]
        assert command_resp.status_code == 200
        assert command_resp.json()["obligations"][0]["owner_team"] == "ops"
        assert command_resp.json()["obligations"][0]["status"] == "satisfied"
        assert escalations_resp.status_code == 200
        assert escalations_resp.json()["escalation_events"][0]["obligation_id"] == obligation.obligation_id
        assert escalations_resp.json()["count"] == 1
        assert escalations_resp.json()["total"] == 2
        assert escalations_resp.json()["next_offset"] == 1
        assert satisfied_resp.json()["count"] == 1
        assert witness_resp.json()["requires_review_count"] == 0
        assert console_resp.status_code == 200
        assert obligation.obligation_id in console_resp.text
        assert "case_review" in console_resp.text

    def test_authority_obligation_satisfaction_rejects_missing_obligation(self, client):
        resp = client.post(
            "/authority/obligations/missing-obligation/satisfy",
            json={"evidence_refs": ["case:missing"]},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "obligation not found"

    def test_escalate_overdue_authority_obligations_records_transition(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "authority-escalate-overdue-token"},
        )
        assert msg_resp.status_code == 200
        certificate = gateway_app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        obligation = Obligation(
            obligation_id="obligation-test-escalate-overdue",
            command_id=certificate.command_id,
            tenant_id="t1",
            owner_id="u1",
            owner_team="ops",
            obligation_type="case_review",
            due_at="2026-04-24T12:00:00+00:00",
            status=ObligationStatus.OPEN,
            evidence_required=("case_disposition",),
            escalation_policy_id="default",
            terminal_certificate_id=certificate.certificate_id,
        )
        gateway_app.state.authority_mesh_store.save_obligation(obligation)

        resp = client.post("/authority/obligations/escalate-overdue")
        updated = gateway_app.state.authority_mesh_store.load_obligation(obligation.obligation_id)
        events = gateway_app.state.command_ledger.events_for(certificate.command_id)

        assert resp.status_code == 200
        assert resp.json()["status"] == "escalated"
        assert any(item["obligation_id"] == obligation.obligation_id for item in resp.json()["obligations"])
        assert resp.json()["authority_witness"]["escalated_obligation_count"] >= 1
        assert updated is not None
        assert updated.status is ObligationStatus.ESCALATED
        assert events[-1].next_state is CommandState.OBLIGATIONS_ESCALATED
        assert gateway_app.state.authority_mesh_store.list_escalation_events()

    def test_expire_overdue_authority_approval_chains_records_transition(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "make a payment of $50", "user_id": "web-user"}),
            headers={"X-Session-Token": "authority-expire-chain-token"},
        )
        command_id = msg_resp.json()["metadata"]["command_id"]
        chain = gateway_app.state.authority_obligation_mesh.approval_chain_for(command_id)
        assert chain is not None
        expired_chain = ApprovalChain(
            chain_id=chain.chain_id,
            command_id=chain.command_id,
            tenant_id=chain.tenant_id,
            policy_id=chain.policy_id,
            required_roles=chain.required_roles,
            required_approver_count=chain.required_approver_count,
            approvals_received=chain.approvals_received,
            status=ApprovalChainStatus.PENDING,
            due_at="2026-04-24T12:00:00+00:00",
        )
        gateway_app.state.authority_mesh_store.save_approval_chain(expired_chain)

        resp = client.post("/authority/approval-chains/expire-overdue")
        updated = gateway_app.state.authority_obligation_mesh.approval_chain_for(command_id)
        events = gateway_app.state.command_ledger.events_for(command_id)

        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"
        assert resp.json()["count"] == 1
        assert resp.json()["approval_chains"][0]["status"] == "expired"
        assert resp.json()["authority_witness"]["expired_approval_chain_count"] >= 1
        assert updated is not None
        assert updated.status.value == "expired"
        assert events[-1].next_state is CommandState.DENIED

    def test_command_closure_read_model(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "closure-token"},
        )
        assert msg_resp.status_code == 200
        certificate = gateway_app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        command_id = certificate.command_id

        resp = client.get(f"/commands/{command_id}/closure")
        assert resp.status_code == 200
        data = resp.json()
        assert data["command_id"] == command_id
        assert data["terminal_certificate"]["disposition"] == "committed"
        assert data["terminal_certificate"]["evidence_refs"]
        assert len(data["events"]) >= 3
        witnesses = data["proof_coverage_witnesses"]
        invariant_ids = {witness["invariant_id"] for witness in witnesses}
        assert "command_lifecycle_events_are_hash_linked" in invariant_ids
        assert "terminal_closure_requires_evidence_refs" in invariant_ids
        assert all(witness["matrix_surface_id"] == "gateway_capability_fabric" for witness in witnesses)
        assert witnesses[0]["witness_refs"]
        assert witnesses[1]["evidence_refs"] == data["terminal_certificate"]["evidence_refs"]

    def test_latest_anchor_read_model(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "anchor-token"},
        )
        assert msg_resp.status_code == 200
        anchor = gateway_app.state.router.anchor_command_events(
            signing_secret="anchor-secret",
            signature_key_id="test-anchor",
        )

        resp = client.get("/anchors/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anchor_id"] == anchor.anchor_id
        assert data["event_count"] > 0
        assert data["signature"].startswith("hmac-sha256:")
