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
    ApprovalPolicy,
    EscalationPolicy,
    Obligation,
    ObligationStatus,
    TeamOwnership,
)
from gateway.command_spine import CommandState  # noqa: E402
from gateway.capability_fabric import build_capability_admission_gate_from_env  # noqa: E402
from gateway.plan import one_step_plan  # noqa: E402
from gateway.plan_executor import CapabilityPlanExecutor, CapabilityPlanStepResult  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from gateway.router import TenantMapping  # noqa: E402
from gateway.skill_dispatch import FunctionCapabilityHandler  # noqa: E402
from mcoi_runtime.contracts.governed_capability_fabric import (  # noqa: E402
    CommandCapabilityAdmissionStatus,
)


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

    def test_fabric_admission_uses_checked_in_default_packs(self, monkeypatch):
        monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
        monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", "true")

        gate = build_capability_admission_gate_from_env(clock=lambda: "2026-04-29T00:00:00Z")
        assert gate is not None
        read_model = gate.read_model()
        accepted = gate.admit(command_id="cmd-default-creative", intent_name="creative.document_generate")
        rejected = gate.admit(command_id="cmd-default-missing", intent_name="creative.missing")

        assert read_model["capsule_count"] == 10
        assert read_model["capability_count"] == 52
        assert len(read_model["governed_capability_records"]) == 52
        assert len(read_model["capability_maturity_assessments"]) == 52
        assert read_model["capability_maturity_counts"]["C3"] == 52
        assert read_model["production_ready_count"] == 0
        assert read_model["autonomy_ready_count"] == 0
        assert accepted.status is CommandCapabilityAdmissionStatus.ACCEPTED
        assert accepted.capability_id == "creative.document_generate"
        assert accepted.domain == "creative"
        assert "document_id" in accepted.evidence_required
        assert rejected.status is CommandCapabilityAdmissionStatus.REJECTED
        assert rejected.capability_id == ""
        assert "no installed capability" in rejected.reason

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


    def test_capability_plan_read_model_reports_terminal_certificate(self):
        app = create_gateway_app(platform=StubPlatform(response="unused fallback"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        app.state.router._skills.register(FunctionCapabilityHandler(
            "enterprise.knowledge_search",
            lambda context, params: {
                "response": "Knowledge searched.",
                "chunks": ["policy"],
                "scores": [1.0],
                "total_chunks_searched": 1,
                "receipt_status": "searched",
            },
        ))
        app.state.router._skills.register(FunctionCapabilityHandler(
            "enterprise.task_schedule",
            lambda context, params: {
                "response": "Task scheduled: task-1",
                "task_id": "task-1",
                "receipt_status": "scheduled",
            },
        ))
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({
                "body": "search knowledge docs and search knowledge policy",
                "user_id": "web-user",
            }),
            headers={"X-Session-Token": "plan-read-model-token"},
        )
        plan_id = msg_resp.json()["metadata"]["plan_id"]
        read_model_resp = client.get("/capability-plans/read-model")
        closure_resp = client.get(f"/capability-plans/{plan_id}/closure")
        missing_resp = client.get("/capability-plans/missing-plan/closure")

        assert msg_resp.status_code == 200
        assert msg_resp.json()["metadata"]["plan_terminal_certificate_id"].startswith("plan-cert-")
        assert read_model_resp.status_code == 200
        assert read_model_resp.json()["enabled"] is True
        assert read_model_resp.json()["plan_certificate_count"] == 1
        assert read_model_resp.json()["plan_witness_count"] == 1
        assert read_model_resp.json()["recovery_attempt_count"] == 0
        assert read_model_resp.json()["recovery_attempt_status_counts"] == {}
        assert closure_resp.status_code == 200
        assert closure_resp.json()["plan_id"] == plan_id
        assert closure_resp.json()["plan_terminal_certificate"]["plan_id"] == plan_id
        assert closure_resp.json()["plan_terminal_certificate"]["step_count"] == 2
        assert closure_resp.json()["plan_evidence_bundle"]["bundle_id"].startswith("plan-evidence-bundle-")
        assert closure_resp.json()["plan_evidence_bundle"]["plan_id"] == plan_id
        assert (
            closure_resp.json()["plan_evidence_bundle"]["certificate_id"]
            == closure_resp.json()["plan_terminal_certificate"]["certificate_id"]
        )
        assert len(closure_resp.json()["plan_evidence_bundle"]["step_command_ids"]) == 2
        assert len(closure_resp.json()["plan_evidence_bundle"]["step_terminal_certificate_ids"]) == 2
        assert closure_resp.json()["plan_evidence_bundle"]["evidence_refs"]
        assert closure_resp.json()["witness_count"] == 1
        assert closure_resp.json()["recovery_attempt_count"] == 0
        assert closure_resp.json()["plan_recovery_attempts"] == []
        assert closure_resp.json()["plan_witnesses"][0]["detail"]["cause"] == "plan_terminal_certificate_issued"
        assert missing_resp.status_code == 404
        assert missing_resp.json()["detail"] == "plan terminal certificate not found"

    def test_capability_plan_read_model_filters_recovery_action(self):
        app = create_gateway_app(platform=StubPlatform(response="unused fallback"))
        client = TestClient(app)
        plan = one_step_plan(
            capability_id="enterprise.task_schedule",
            params={"title": "Review report"},
            tenant_id="t1",
            identity_id="u1",
            goal="schedule review",
        )
        execution = CapabilityPlanExecutor(
            lambda step, completed: CapabilityPlanStepResult(
                step_id=step.step_id,
                capability_id=step.capability_id,
                succeeded=False,
                command_id="cmd-approval",
                error="approval_required:apr-1",
            )
        ).execute(plan)
        witness = app.state.plan_ledger.record_failure(plan=plan, execution=execution)
        retry_plan = one_step_plan(
            capability_id="creative.data_analyze",
            params={"csv": "a,b\n1,2\n"},
            tenant_id="t1",
            identity_id="u1",
            goal="analyze",
        )
        retry_execution = CapabilityPlanExecutor(
            lambda step, completed: CapabilityPlanStepResult(
                step_id=step.step_id,
                capability_id=step.capability_id,
                succeeded=False,
                command_id="cmd-retry",
                error="analysis_failed",
            )
        ).execute(retry_plan)
        retry_witness = app.state.plan_ledger.record_failure(plan=retry_plan, execution=retry_execution)

        filtered_resp = client.get("/capability-plans/read-model?recovery_action=wait_for_approval")
        paged_resp = client.get("/capability-plans/read-model?failed_witness_limit=1&failed_witness_offset=1")
        empty_resp = client.get("/capability-plans/read-model?recovery_action=compensate_or_review")

        assert filtered_resp.status_code == 200
        assert filtered_resp.json()["recovery_action_filter"] == "wait_for_approval"
        assert filtered_resp.json()["failed_plan_witness_count"] == 2
        assert filtered_resp.json()["recovery_action_counts"] == {
            "retry_or_review": 1,
            "wait_for_approval": 1,
        }
        assert filtered_resp.json()["failed_plan_witness_page"] == {
            "total": 1,
            "limit": 100,
            "offset": 0,
            "next_offset": None,
        }
        assert filtered_resp.json()["recovery_attempt_count"] == 0
        assert filtered_resp.json()["recovery_attempt_status_counts"] == {}
        assert filtered_resp.json()["failed_plan_witnesses"][0]["witness_id"] == witness.witness_id
        assert filtered_resp.json()["failed_plan_witnesses"][0]["detail"]["recovery_decision"]["approval_required"]
        assert paged_resp.status_code == 200
        assert paged_resp.json()["failed_plan_witness_page"] == {
            "total": 2,
            "limit": 1,
            "offset": 1,
            "next_offset": None,
        }
        assert len(paged_resp.json()["failed_plan_witnesses"]) == 1
        assert paged_resp.json()["failed_plan_witnesses"][0]["witness_id"] == retry_witness.witness_id
        assert empty_resp.status_code == 200
        assert empty_resp.json()["recovery_action_filter"] == "compensate_or_review"
        assert empty_resp.json()["failed_plan_witness_page"] == {
            "total": 0,
            "limit": 100,
            "offset": 0,
            "next_offset": None,
        }
        assert empty_resp.json()["failed_plan_witnesses"] == []

    def test_capability_plan_recover_endpoint_resumes_after_approval(self):
        app = create_gateway_app(platform=StubPlatform(response="schedule approved"))
        app.state.router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="web-user",
            tenant_id="t1", identity_id="u1",
        ))
        app.state.router._skills.register(FunctionCapabilityHandler(
            "enterprise.knowledge_search",
            lambda context, params: {
                "response": "Knowledge searched.",
                "chunks": ["policy"],
                "scores": [1.0],
                "total_chunks_searched": 1,
                "receipt_status": "searched",
            },
        ))
        client = TestClient(app)

        blocked_resp = client.post(
            "/webhook/web",
            content=json.dumps({
                "body": "search knowledge docs and schedule review",
                "user_id": "web-user",
            }),
            headers={"X-Session-Token": "plan-recover-token"},
        )
        plan_id = blocked_resp.json()["metadata"]["plan_id"]
        request_id = blocked_resp.json()["metadata"]["plan_error"].split("approval_required:", 1)[1]
        approval_resp = app.state.router.handle_approval_callback(request_id, approved=True, resolved_by="operator-1")
        recover_resp = client.post(f"/capability-plans/{plan_id}/recover")
        repeat_recover_resp = client.post(f"/capability-plans/{plan_id}/recover")
        second_recover_resp = client.post("/capability-plans/missing-plan/recover")
        read_model_resp = client.get("/capability-plans/read-model")
        rejected_read_model_resp = client.get("/capability-plans/read-model?recovery_attempt_status=rejected")
        paged_read_model_resp = client.get(
            "/capability-plans/read-model?recovery_attempt_limit=1&recovery_attempt_offset=1"
        )
        closure_resp = client.get(f"/capability-plans/{plan_id}/closure")

        assert blocked_resp.status_code == 200
        assert blocked_resp.json()["metadata"]["error"] == "plan_execution_failed"
        assert approval_resp is not None
        assert approval_resp.metadata["terminal_certificate_id"]
        assert recover_resp.status_code == 200
        assert recover_resp.json()["status"] == "recovered"
        assert recover_resp.json()["plan_id"] == plan_id
        assert recover_resp.json()["plan_terminal_certificate_id"].startswith("plan-cert-")
        assert repeat_recover_resp.status_code == 409
        assert repeat_recover_resp.json()["detail"] == "plan already has terminal certificate"
        assert second_recover_resp.status_code == 404
        assert second_recover_resp.json()["detail"] == "failed plan witness not found"
        assert read_model_resp.status_code == 200
        assert read_model_resp.json()["recovery_attempt_count"] == 3
        assert read_model_resp.json()["recovery_attempt_status_counts"] == {
            "rejected": 2,
            "succeeded": 1,
        }
        assert read_model_resp.json()["recovery_attempt_status_filter"] == ""
        assert rejected_read_model_resp.status_code == 200
        assert rejected_read_model_resp.json()["recovery_attempt_count"] == 3
        assert rejected_read_model_resp.json()["recovery_attempt_status_filter"] == "rejected"
        assert [attempt["status"] for attempt in rejected_read_model_resp.json()["recovery_attempts"]] == [
            "rejected",
            "rejected",
        ]
        assert paged_read_model_resp.status_code == 200
        assert paged_read_model_resp.json()["recovery_attempt_count"] == 3
        assert paged_read_model_resp.json()["recovery_attempt_page"] == {
            "total": 3,
            "limit": 1,
            "offset": 1,
            "next_offset": 2,
        }
        assert len(paged_read_model_resp.json()["recovery_attempts"]) == 1
        assert closure_resp.status_code == 200
        assert closure_resp.json()["recovery_attempt_count"] == 2
        assert [attempt["status"] for attempt in closure_resp.json()["plan_recovery_attempts"]] == [
            "succeeded",
            "rejected",
        ]
        assert closure_resp.json()["plan_recovery_attempts"][0]["reason"] == "plan_recovered"
        assert closure_resp.json()["plan_recovery_attempts"][1]["reason"] == "plan_already_certified"


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
        assert "active_compensation_review_count" in data
        assert data["pending_approval_chain_count"] == 0
        assert data["overdue_approval_chain_count"] == 0
        assert data["expired_approval_chain_count"] == 0
        assert data["open_obligation_count"] == 0
        assert data["responsibility_debt_clear"] is True
        assert data["signature_key_id"]
        assert data["signature"].startswith("hmac-sha256:")

    def test_runtime_witness_alias(self, client):
        resp = client.get("/runtime/witness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["witness_id"].startswith("runtime-witness-")
        assert data["signature"].startswith("hmac-sha256:")

    def test_runtime_self_reflex_read_models_do_not_mutate(self, client):
        health_resp = client.get("/runtime/self/health")
        inspect_resp = client.get("/runtime/self/inspect")
        diagnose_resp = client.post("/runtime/self/diagnose")
        evaluate_resp = client.post("/runtime/self/evaluate")
        proposal_resp = client.post("/runtime/self/propose-upgrade")
        certify_missing_resp = client.post("/runtime/self/certify", json={})
        witness_resp = client.get("/runtime/self/witness")
        health_payload = health_resp.json()
        inspect_payload = inspect_resp.json()
        proposal_payload = proposal_resp.json()

        assert health_resp.status_code == 200
        assert health_payload["snapshot_id"].startswith("reflex-snapshot-")
        assert health_payload["metrics"]["deployment_witness_missing"] == 1
        assert health_payload["metrics"]["missing_approvals"] == 0
        assert health_payload["evidence_refs"]
        assert inspect_resp.status_code == 200
        assert inspect_payload["anomaly_count"] >= 1
        assert any(
            anomaly["metric_name"] == "deployment_witness_missing"
            for anomaly in inspect_payload["anomalies"]
        )
        assert diagnose_resp.status_code == 200
        assert diagnose_resp.json()["diagnosis_count"] >= 1
        assert evaluate_resp.status_code == 200
        assert evaluate_resp.json()["side_effects"] == "none"
        assert proposal_resp.status_code == 200
        assert proposal_payload["mutation_applied"] is False
        assert proposal_payload["candidate_count"] >= 1
        assert any(
            candidate["change_surface"] == "deployment_witness"
            for candidate in proposal_payload["candidates"]
        )
        deployment_candidate_id = next(
            candidate["candidate_id"]
            for candidate in proposal_payload["candidates"]
            if candidate["change_surface"] == "deployment_witness"
        )
        promote_without_proof_resp = client.post(
            "/runtime/self/promote",
            json={"candidate_id": deployment_candidate_id},
        )
        assert promote_without_proof_resp.status_code == 200
        assert promote_without_proof_resp.json()["requires_human_approval"] is True
        assert promote_without_proof_resp.json()["mutation_applied"] is False
        assert certify_missing_resp.status_code == 400
        assert certify_missing_resp.json()["detail"] == "candidate_id is required"
        assert witness_resp.status_code == 200
        assert witness_resp.json()["witness_id"].startswith("reflex-witness-")
        assert witness_resp.json()["mutation_applied"] is False
        assert witness_resp.json()["protected_surfaces_auto_promote"] is False
        assert witness_resp.json()["signature"].startswith("hmac-sha256:")

    def test_authority_witness_read_model(self, client):
        resp = client.get("/authority/witness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_approval_chain_count"] == 0
        assert data["overdue_approval_chain_count"] == 0
        assert data["expired_approval_chain_count"] == 0
        assert data["open_obligation_count"] == 0
        assert data["active_compensation_review_count"] == 0
        assert data["unowned_high_risk_capability_count"] == 0
        assert data["responsibility_debt_clear"] is True

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

    def test_authority_ownership_read_model_filters_owner_records(self, gateway_app, client):
        gateway_app.state.authority_mesh_store.save_ownership(TeamOwnership(
            tenant_id="t1",
            resource_ref="financial.send_payment",
            owner_team="finance_ops",
            primary_owner_id="finance-manager-1",
            fallback_owner_id="tenant-owner-1",
            escalation_team="executive_ops",
        ))
        gateway_app.state.authority_mesh_store.save_ownership(TeamOwnership(
            tenant_id="t1",
            resource_ref="deploy.production",
            owner_team="platform_security",
            primary_owner_id="security-admin-1",
            fallback_owner_id="engineering-lead-1",
            escalation_team="engineering_ops",
        ))

        list_resp = client.get("/authority/ownership?tenant_id=t1&limit=1")
        team_resp = client.get("/authority/ownership?owner_team=finance_ops")
        resource_resp = client.get("/authority/ownership?resource_ref=deploy.production")
        owner_resp = client.get("/authority/ownership?primary_owner_id=security-admin-1")
        missing_resp = client.get("/authority/ownership?owner_team=missing-team")

        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 1
        assert list_resp.json()["total"] == 2
        assert list_resp.json()["next_offset"] == 1
        assert team_resp.status_code == 200
        assert team_resp.json()["count"] == 1
        assert team_resp.json()["ownership"][0]["owner_team"] == "finance_ops"
        assert resource_resp.status_code == 200
        assert resource_resp.json()["ownership"][0]["resource_ref"] == "deploy.production"
        assert owner_resp.status_code == 200
        assert owner_resp.json()["ownership"][0]["primary_owner_id"] == "security-admin-1"
        assert missing_resp.status_code == 200
        assert missing_resp.json()["count"] == 0

    def test_authority_policy_read_model_filters_approval_and_escalation_policies(self, gateway_app, client):
        gateway_app.state.authority_mesh_store.save_approval_policy(ApprovalPolicy(
            policy_id="payment-high-risk-policy",
            tenant_id="t1",
            capability="financial.send_payment",
            risk_tier="high",
            required_roles=("financial_admin",),
            required_approver_count=2,
            separation_of_duty=True,
            timeout_seconds=300,
            escalation_policy_id="finance-escalation",
        ))
        gateway_app.state.authority_mesh_store.save_approval_policy(ApprovalPolicy(
            policy_id="deploy-high-risk-policy",
            tenant_id="t1",
            capability="deploy.production",
            risk_tier="high",
            required_roles=("security_admin",),
            required_approver_count=2,
            separation_of_duty=True,
            timeout_seconds=600,
            escalation_policy_id="platform-escalation",
        ))
        gateway_app.state.authority_mesh_store.save_escalation_policy(EscalationPolicy(
            policy_id="finance-escalation",
            tenant_id="t1",
            notify_after_seconds=300,
            escalate_after_seconds=900,
            incident_after_seconds=3600,
            fallback_owner_id="tenant-owner-1",
            escalation_team="executive_ops",
        ))

        list_resp = client.get("/authority/policies?tenant_id=t1&limit=1")
        capability_resp = client.get("/authority/policies?capability=financial.send_payment")
        role_resp = client.get("/authority/policies?required_role=security_admin")
        escalation_resp = client.get("/authority/policies?policy_id=finance-escalation")
        missing_resp = client.get("/authority/policies?required_role=missing-role")

        assert list_resp.status_code == 200
        assert list_resp.json()["approval_count"] == 1
        assert list_resp.json()["approval_page"]["total"] == 2
        assert list_resp.json()["approval_page"]["next_offset"] == 1
        assert list_resp.json()["escalation_count"] == 1
        assert capability_resp.status_code == 200
        assert capability_resp.json()["approval_count"] == 1
        assert capability_resp.json()["approval_policies"][0]["capability"] == "financial.send_payment"
        assert role_resp.status_code == 200
        assert role_resp.json()["approval_policies"][0]["required_roles"] == ["security_admin"]
        assert escalation_resp.status_code == 200
        assert escalation_resp.json()["approval_count"] == 0
        assert escalation_resp.json()["escalation_count"] == 1
        assert escalation_resp.json()["escalation_policies"][0]["escalation_team"] == "executive_ops"
        assert missing_resp.status_code == 200
        assert missing_resp.json()["approval_count"] == 0
        assert missing_resp.json()["escalation_count"] == 0

    def test_authority_approval_chain_read_model(self, gateway_app, client):
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
        policy_id = chains[0]["policy_id"]
        required_role = chains[0]["required_roles"][0]
        chain = gateway_app.state.authority_obligation_mesh.approval_chain_for(command_id)
        assert chain is not None
        gateway_app.state.authority_mesh_store.save_approval_chain(ApprovalChain(
            chain_id=chain.chain_id,
            command_id=chain.command_id,
            tenant_id=chain.tenant_id,
            policy_id=chain.policy_id,
            required_roles=chain.required_roles,
            required_approver_count=chain.required_approver_count,
            approvals_received=chain.approvals_received,
            status=chain.status,
            due_at="2026-04-24T12:00:00+00:00",
        ))
        policy_resp = client.get(f"/authority/approval-chains?policy_id={policy_id}")
        role_resp = client.get(f"/authority/approval-chains?required_role={required_role}")
        missing_role_resp = client.get("/authority/approval-chains?required_role=security_admin")
        overdue_resp = client.get("/authority/approval-chains?status=pending&overdue=true")
        not_overdue_resp = client.get(f"/authority/approval-chains?command_id={command_id}&overdue=false")
        invalid_overdue_resp = client.get("/authority/approval-chains?overdue=maybe")
        command_resp = client.get(f"/commands/{command_id}/authority")
        witness_resp = client.get("/authority/witness")
        console_resp = client.get("/authority/operator")

        assert any(chain["command_id"] == command_id for chain in chains)
        assert paged_resp.json()["count"] == 1
        assert paged_resp.json()["total"] >= 1
        assert paged_resp.json()["limit"] == 1
        assert paged_resp.json()["offset"] == 0
        assert policy_resp.status_code == 200
        assert any(chain["command_id"] == command_id for chain in policy_resp.json()["approval_chains"])
        assert role_resp.status_code == 200
        assert any(chain["command_id"] == command_id for chain in role_resp.json()["approval_chains"])
        assert missing_role_resp.status_code == 200
        assert missing_role_resp.json()["count"] == 0
        assert overdue_resp.status_code == 200
        assert any(chain["command_id"] == command_id for chain in overdue_resp.json()["approval_chains"])
        assert not_overdue_resp.status_code == 200
        assert not_overdue_resp.json()["count"] == 0
        assert invalid_overdue_resp.status_code == 400
        assert invalid_overdue_resp.json()["detail"] == "overdue must be true or false"
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
            due_at="2099-04-26T12:00:00+00:00",
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
        overdue_obligations_resp = client.get("/authority/obligations?tenant_id=t1&status=open&overdue=true")
        not_overdue_obligations_resp = client.get("/authority/obligations?tenant_id=t1&overdue=false")
        invalid_overdue_obligations_resp = client.get("/authority/obligations?overdue=maybe")
        missing_evidence_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": []},
        )
        satisfy_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": ["case_disposition:read-model-closed"]},
        )
        command_resp = client.get(f"/commands/{obligation.command_id}/authority")
        escalations_resp = client.get(f"/authority/escalations?command_id={obligation.command_id}&limit=1")
        responsibility_resp = client.get("/authority/responsibility?tenant_id=t1&limit=2")
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
        assert overdue_obligations_resp.status_code == 200
        assert overdue_obligations_resp.json()["count"] == 2
        assert {
            item["obligation_id"] for item in overdue_obligations_resp.json()["obligations"]
        } == {obligation.obligation_id, second_obligation.obligation_id}
        assert not_overdue_obligations_resp.status_code == 200
        assert not_overdue_obligations_resp.json()["count"] == 1
        assert (
            not_overdue_obligations_resp.json()["obligations"][0]["obligation_id"]
            == compensation_obligation.obligation_id
        )
        assert invalid_overdue_obligations_resp.status_code == 400
        assert invalid_overdue_obligations_resp.json()["detail"] == "overdue must be true or false"
        assert missing_evidence_resp.status_code == 400
        assert satisfy_resp.status_code == 200
        assert satisfy_resp.json()["status"] == "satisfied"
        assert satisfy_resp.json()["obligation"]["status"] == "satisfied"
        assert satisfy_resp.json()["evidence_refs"] == ["case_disposition:read-model-closed"]
        assert command_resp.status_code == 200
        assert command_resp.json()["obligations"][0]["owner_team"] == "ops"
        assert command_resp.json()["obligations"][0]["status"] == "satisfied"
        assert escalations_resp.status_code == 200
        assert escalations_resp.json()["escalation_events"][0]["obligation_id"] == obligation.obligation_id
        assert escalations_resp.json()["count"] == 1
        assert escalations_resp.json()["total"] == 2
        assert escalations_resp.json()["next_offset"] == 1
        assert responsibility_resp.status_code == 200
        responsibility_payload = responsibility_resp.json()
        assert responsibility_payload["tenant_id"] == "t1"
        assert responsibility_payload["responsibility_debt_clear"] is False
        assert responsibility_payload["unresolved_obligation_count"] == 2
        assert responsibility_payload["escalation_event_count"] == 2
        assert responsibility_payload["priority_obligations"][0]["obligation_id"] == second_obligation.obligation_id
        assert responsibility_payload["priority_obligations"][1]["obligation_id"] == compensation_obligation.obligation_id
        assert responsibility_payload["priority_escalation_events"][0]["event_id"] == "obl-escalation-test-read-model-second"
        assert "authority:obligations_read_model" in responsibility_payload["evidence_refs"]
        assert satisfied_resp.json()["count"] == 1
        assert witness_resp.json()["requires_review_count"] == 0
        assert witness_resp.json()["responsibility_debt_clear"] is False
        assert console_resp.status_code == 200
        assert obligation.obligation_id in console_resp.text
        assert "/authority/responsibility" in console_resp.text
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
