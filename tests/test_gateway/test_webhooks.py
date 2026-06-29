"""Gateway Webhook Endpoint Tests.

Tests: HTTP webhook endpoints for all channels using FastAPI TestClient.
"""

import hashlib
import hmac
import json
import copy
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from gateway.audit_trace_verifier import _recompute_event_hash  # noqa: E402
from gateway.authority_obligation_mesh import (  # noqa: E402
    ApprovalChain,
    ApprovalChainStatus,
    ApprovalPolicy,
    EscalationPolicy,
    Obligation,
    ObligationStatus,
    TeamOwnership,
)
from gateway.command_spine import (  # noqa: E402
    ClosureDisposition,
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
)
from gateway.capability_fabric import build_capability_admission_gate_from_env  # noqa: E402
from gateway.plan import one_step_plan  # noqa: E402
from gateway.plan_executor import CapabilityPlanExecutor, CapabilityPlanStepResult  # noqa: E402
from gateway.server import (  # noqa: E402
    _validated_whqr_replay_binding,
    create_gateway_app,
)
from gateway.router import TenantMapping  # noqa: E402
from gateway.search_governance import SearchDecisionRequest, build_search_decision_receipt  # noqa: E402
from gateway.skill_dispatch import FunctionCapabilityHandler  # noqa: E402
from gateway.worker_failure_receipt import build_worker_failure_receipt  # noqa: E402
from gateway.worker_mesh import WorkerDispatchReceipt  # noqa: E402
from mcoi_runtime.contracts.governed_capability_fabric import (  # noqa: E402
    CommandCapabilityAdmissionStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine  # noqa: E402
from mcoi_runtime.core.governed_session import Platform  # noqa: E402
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier  # noqa: E402
from mcoi_runtime.core.rbac_defaults import seed_default_permissions  # noqa: E402
from mcoi_runtime.governance.guards.access import AccessRuntimeEngine  # noqa: E402
from mcoi_runtime.governance.guards.tenant_gating import (  # noqa: E402
    TenantGatingRegistry,
    TenantStatus,
)
from mcoi_runtime.governance.guards.budget import (  # noqa: E402
    TenantBudgetManager,
    TenantBudgetPolicy,
)
from mcoi_runtime.persistence.postgres_governance_stores import InMemoryTenantGatingStore  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


LATEST_ANCHOR_SCHEMA = _ROOT / "schemas" / "latest_anchor_read_model.schema.json"
COMMAND_INTERPRETATION_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "command_interpretation_receipt_read_model.schema.json"
)
OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_receipt_viewer_read_model.schema.json"
)
OPERATOR_APPROVAL_HISTORY_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_approval_history_read_model.schema.json"
)
OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_plan_review_read_model.schema.json"
)
OPERATOR_BUDGET_REPORT_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_budget_report_read_model.schema.json"
)
OPERATOR_PLAN_RECEIPT_EXPORT_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_plan_receipt_export_read_model.schema.json"
)
OPERATOR_PLAN_RECEIPT_BUNDLE_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "operator_plan_receipt_bundle_read_model.schema.json"
)
CURRENT_TASK_READ_MODEL_SCHEMA = (
    _ROOT / "schemas" / "current_task_read_model.schema.json"
)
WHQR_CANONICAL_HASH = "sha256:" + ("a" * 64)
WHQR_SEMANTICS_HASH = "sha256:" + ("b" * 64)
WHQR_REPLAY_REF = f"whqr://replay/{WHQR_CANONICAL_HASH}"
INTERPRETATION_RECEIPT_SCHEMA = _ROOT / "schemas" / "interpretation_receipt.schema.json"
INTERPRETED_REQUEST_SCHEMA = _ROOT / "schemas" / "interpreted_request.schema.json"


def _replace_command_event_with_recomputed_hash(event, **changes):
    tampered = replace(event, **changes)
    event_hash = _recompute_event_hash(tampered)
    return replace(tampered, event_hash=event_hash, event_id=f"evt-{event_hash[:16]}")


class StubPlatform:
    def __init__(self, response="Governed response"):
        self._response = response

    def connect(self, *, identity_id, tenant_id):
        return StubSession(self._response)


class AccessRuntimePlatform(StubPlatform):
    def __init__(self, response="Governed response"):
        super().__init__(response)
        self._access_runtime = AccessRuntimeEngine(EventSpineEngine())
        seed_default_permissions(self._access_runtime)


class GovernedDeploymentPlatform(AccessRuntimePlatform):
    def __init__(self, response="Governed response"):
        super().__init__(response)
        self._tenant_gating = TenantGatingRegistry(
            store=InMemoryTenantGatingStore(),
            allow_unknown_tenants=False,
        )


class StubSession:
    def __init__(self, response):
        self._response = response

    def llm(self, prompt, **kwargs):
        return type(
            "R",
            (),
            {"content": self._response, "succeeded": True, "error": "", "cost": 0.0},
        )()

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


def _bind_uao_fixture_to_universal_action_detail(
    record: dict,
) -> dict:
    recovery_plan = record["recovery_plan"]
    causal_repair_admission_ref = (
        recovery_plan.get("causal_repair_admission_ref")
        or f"causal-repair-admission-certificate://{record['action_id']}"
    )
    causal_repair_admission_status = recovery_plan.get(
        "causal_repair_admission_status",
        "not_required",
    )
    causal_repair_admission_reason = (
        recovery_plan.get("causal_repair_admission_reason") or ""
    )
    universal_detail = {
        "action_id": record["action_id"],
        "blocked": record["decision"]["status"] != "allow",
        "block_reason": ""
        if record["decision"]["status"] == "allow"
        else record["decision"]["reason_code"],
        "action_envelope": copy.deepcopy(record["action_envelope"]),
        "trace_ref": record["trace_ref"],
        "admission_receipt_ref": record["admission_receipt_ref"],
        "execution_receipt_ref": record["execution_receipt_ref"],
        "closure_state": record["closure_state"],
        "goal_certificate_id": f"goal-certificate://{record['action_id']}",
        "world_certificate_id": f"world-certificate://{record['action_id']}",
        "plan_certificate_id": f"plan-certificate://{record['action_id']}",
        "simulation_certificate_id": f"simulation-certificate://{record['action_id']}",
        "effect_prediction_certificate_id": (
            f"effect-prediction-certificate://{record['action_id']}"
        ),
        "effect_plan_id": f"effect-plan://{record['action_id']}",
        "recovery_plan_certificate_id": (
            f"recovery-plan-certificate://{record['action_id']}"
        ),
        "recovery_plan_id": f"recovery-plan://{record['action_id']}",
        "causal_repair_admission_certificate_id": causal_repair_admission_ref,
        "causal_repair_admission_status": causal_repair_admission_status,
        "causal_repair_admission_reason": causal_repair_admission_reason,
        "intent_certificate_id": f"intent-certificate://{record['action_id']}",
        "intent_hash": f"typed-intent://{record['action_id']}",
        "operating_substrate_certificate_id": (
            f"operating-substrate-certificate://{record['action_id']}"
        ),
        "operating_substrate_projection_id": (
            f"operating-substrate-projection://{record['action_id']}"
        ),
        "operating_substrate_reason": "projection_allows_execution",
        "world_support_evidence_refs": tuple(
            record["action_envelope"]["evidence_refs"]
        ),
        "operating_substrate_evidence_refs": (
            f"operating-substrate-evidence://{record['action_id']}",
        ),
        "capability_status": "accepted",
        "capability_id": record["action_envelope"]["capability_refs"][0],
        "governed_action_id": f"governed-action://{record['action_id']}",
        "dispatch_ledger_hash": f"dispatch-ledger://{record['action_id']}",
        "terminal_certificate_id": f"terminal-certificate://{record['action_id']}",
        "whqr_replay_binding": record["closure"].get("whqr_replay_binding") or {},
        "learning_admission_id": f"learning-admission://{record['action_id']}",
        "reconciliation_ref": record["closure"]["reconciliation_ref"] or "",
        "memory_ref": record["closure"]["memory_ref"] or "",
        "life_meaning_judgment": copy.deepcopy(record["life_meaning_judgment"]),
    }
    proof_hash = _uao_fixture_proof_hash(universal_detail)
    universal_detail["proof_hash"] = proof_hash
    record["orchestration_id"] = stable_identifier(
        "universal-action-orchestration",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "trace_ref": record["trace_ref"],
        },
    )
    delta_ref = stable_identifier(
        "universal-action-delta",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "closure_state": record["closure_state"],
        },
    )
    record["lineage"]["delta_ref"] = delta_ref
    for delta in (
        record["lineage"]["accepted_deltas"] + record["lineage"]["rejected_deltas"]
    ):
        delta["delta_id"] = delta_ref
    return universal_detail


def _uao_fixture_proof_hash(universal_detail: dict) -> str:
    payload = {
        "action_id": universal_detail["action_id"],
        "blocked": universal_detail["blocked"],
        "block_reason": universal_detail["block_reason"],
        "action_envelope": dict(universal_detail["action_envelope"]),
        "trace_ref": universal_detail["trace_ref"],
        "admission_receipt_ref": universal_detail["admission_receipt_ref"],
        "execution_receipt_ref": universal_detail["execution_receipt_ref"],
        "closure_state": universal_detail["closure_state"],
        "goal_certificate_id": universal_detail["goal_certificate_id"],
        "world_certificate_id": universal_detail["world_certificate_id"],
        "plan_certificate_id": universal_detail["plan_certificate_id"],
        "simulation_certificate_id": universal_detail["simulation_certificate_id"],
        "effect_prediction_certificate_id": universal_detail[
            "effect_prediction_certificate_id"
        ],
        "effect_plan_id": universal_detail["effect_plan_id"],
        "recovery_plan_certificate_id": universal_detail[
            "recovery_plan_certificate_id"
        ],
        "recovery_plan_id": universal_detail["recovery_plan_id"],
        "causal_repair_admission_certificate_id": universal_detail[
            "causal_repair_admission_certificate_id"
        ],
        "causal_repair_admission_status": universal_detail[
            "causal_repair_admission_status"
        ],
        "causal_repair_admission_reason": universal_detail[
            "causal_repair_admission_reason"
        ],
        "intent_certificate_id": universal_detail["intent_certificate_id"],
        "intent_hash": universal_detail["intent_hash"],
        "operating_substrate_certificate_id": universal_detail[
            "operating_substrate_certificate_id"
        ],
        "operating_substrate_projection_id": universal_detail[
            "operating_substrate_projection_id"
        ],
        "operating_substrate_reason": universal_detail["operating_substrate_reason"],
        "world_support_evidence_refs": tuple(
            universal_detail["world_support_evidence_refs"]
        ),
        "operating_substrate_evidence_refs": tuple(
            universal_detail["operating_substrate_evidence_refs"]
        ),
        "capability_status": universal_detail["capability_status"],
        "capability_id": universal_detail["capability_id"],
        "governed_action_id": universal_detail["governed_action_id"],
        "dispatch_ledger_hash": universal_detail["dispatch_ledger_hash"],
        "terminal_certificate_id": universal_detail["terminal_certificate_id"],
        "whqr_replay_binding": dict(universal_detail["whqr_replay_binding"]),
        "learning_admission_id": universal_detail["learning_admission_id"],
        "reconciliation_ref": universal_detail["reconciliation_ref"],
        "memory_ref": universal_detail["memory_ref"],
        "life_meaning_judgment": dict(universal_detail["life_meaning_judgment"]),
    }
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return stable_identifier("universal-action-proof", {"payload": encoded})


def _rebind_uao_fixture_record_to_proof_hash(record: dict, proof_hash: str) -> None:
    record["orchestration_id"] = stable_identifier(
        "universal-action-orchestration",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "trace_ref": record["trace_ref"],
        },
    )
    delta_ref = stable_identifier(
        "universal-action-delta",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "closure_state": record["closure_state"],
        },
    )
    record["lineage"]["delta_ref"] = delta_ref
    for delta in (
        record["lineage"]["accepted_deltas"] + record["lineage"]["rejected_deltas"]
    ):
        delta["delta_id"] = delta_ref


def _uao_closure_confirmation(
    *,
    closure_state: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: dict | None = None,
) -> str:
    whqr_replay_binding = whqr_replay_binding or {}
    return stable_identifier(
        "universal-action-closure-confirmation",
        {
            "closure_state": closure_state,
            "reconciliation_ref": reconciliation_ref or "",
            "memory_ref": memory_ref or "",
            "whqr_replay_ref": whqr_replay_binding.get("replay_ref", ""),
            "whqr_canonical_hash": whqr_replay_binding.get("canonical_hash", ""),
            "whqr_semantics_hash": whqr_replay_binding.get("semantics_hash", ""),
            "whqr_version": whqr_replay_binding.get("version", ""),
        },
    )


def _slack_signature(*, secret: str, timestamp: str, body: str) -> str:
    return (
        "v0="
        + hmac.new(
            secret.encode(),
            f"v0:{timestamp}:{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
    )


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
    refs = (
        [capability_refs] if isinstance(capability_refs, str) else list(capability_refs)
    )
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


def _create_completed_receipt_viewer_command(ledger, *, idempotency_key: str):
    command = ledger.create_command(
        tenant_id="t1",
        actor_id="u1",
        source="web",
        conversation_id=f"conversation-{idempotency_key}",
        idempotency_key=idempotency_key,
        intent="llm_completion",
        payload={
            "body": "operator viewer raw body must stay hidden",
            "interpretation_receipt": {
                "receipt_id": f"interpretation-receipt-{idempotency_key}",
                "request_id": f"interpreted-request-{idempotency_key}",
                "raw_message_hash": f"raw-message-hash-{idempotency_key}",
                "normalized_text_hash": f"normalized-text-hash-{idempotency_key}",
                "interpreted_intent": "llm_completion",
                "confidence": 0.91,
                "created_at": "2026-04-24T12:00:00+00:00",
            },
            "interpreted_request": {
                "request_id": f"interpreted-request-{idempotency_key}",
                "tenant_id": "t1",
                "actor_id": "u1",
                "channel": "web",
                "conversation_id": f"conversation-{idempotency_key}",
                "raw_message_hash": f"raw-message-hash-{idempotency_key}",
                "intent_class": "action_request",
                "capability_id": "llm_completion",
                "extracted_slots": {"capability_id": "llm_completion"},
                "missing_slots": [],
                "constraints": ["tenant_bound"],
                "search_needed": False,
                "action_needed": True,
                "risk_estimate": "low",
                "approval_required": False,
                "confidence": 0.91,
                "interpreter_kind": "deterministic_rule",
                "rejected_interpretations": [],
                "created_at": "2026-04-24T12:00:00+00:00",
            },
        },
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "bounded receipt viewer output", "succeeded": True},
    )
    ledger.promote_provider_receipts_to_graph(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Operator receipt viewer command completed with reconciled evidence.",
        verified=True,
    )
    closure = ledger.close_success_response_evidence(
        command.command_id,
        claim_id=claim.claim_id,
    )
    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.COMMITTED,
        response_evidence_closure=closure,
    )
    return command, certificate


def _worker_failure_receipt_payload(command_id: str) -> dict:
    worker_receipt = WorkerDispatchReceipt(
        receipt_id=f"worker-receipt-{command_id}",
        request_id=f"worker-request-{command_id}",
        worker_id="operator-viewer-worker",
        capability="repository.inspect_read_only",
        tenant_id="t1",
        lease_id=f"worker-lease-{command_id}",
        operation="inspect",
        command_id=command_id,
        status="failed",
        reason="worker_timeout",
        input_hash="sha256:" + "1" * 64,
        output_hash="sha256:" + "2" * 64,
        evidence_refs=["worker:evidence:partial"],
        verification_ref="verification:operator-viewer-worker",
        recovery_ref="recovery:operator-review",
        terminal_closure_required=True,
        dispatched_at="2026-06-17T13:01:00+00:00",
        receipt_hash="sha256:" + "3" * 64,
        metadata={"receipt_is_not_terminal_closure": True},
    )
    return build_worker_failure_receipt(
        worker_receipt,
        attempted_units=5,
        completed_units=2,
        generated_at="2026-06-17T13:02:00+00:00",
    ).to_dict()


def _configure_fabric_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    capability_refs: list[str],
    capability_payloads: list[dict],
    use_pack: bool,
) -> None:
    capsule_path = tmp_path / "domain_capsule.json"
    capsule_path.write_text(
        json.dumps(_fabric_capsule_payload(capability_refs)), encoding="utf-8"
    )
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", str(capsule_path))
    if use_pack:
        pack_path = tmp_path / "capability_pack.json"
        pack_path.write_text(
            json.dumps({"capabilities": capability_payloads}), encoding="utf-8"
        )
        monkeypatch.setenv(
            "MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", str(pack_path)
        )
    else:
        capability_path = tmp_path / "capability.json"
        capability_path.write_text(json.dumps(capability_payloads[0]), encoding="utf-8")
        monkeypatch.setenv(
            "MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH", str(capability_path)
        )


@pytest.fixture
def gateway_app():
    app = create_gateway_app(platform=StubPlatform())
    # Register a test tenant
    app.state.router.register_tenant_mapping(
        TenantMapping(
            channel="whatsapp",
            sender_id="+1234567890",
            tenant_id="t1",
            identity_id="u1",
        )
    )
    app.state.router.register_tenant_mapping(
        TenantMapping(
            channel="telegram",
            sender_id="98765",
            tenant_id="t1",
            identity_id="u1",
        )
    )
    app.state.router.register_tenant_mapping(
        TenantMapping(
            channel="web",
            sender_id="web-user",
            tenant_id="t1",
            identity_id="u1",
        )
    )
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


class TestDeploymentTenantMappings:
    def test_deployment_tenant_mapping_requires_authority(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.delenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
            },
        )

        assert resp.status_code == 403
        assert resp.json()["detail"] == "Deployment authority access not authorized"
        assert app.state.tenant_identity_store.count() == 0

    def test_deployment_tenant_mapping_persists_authorized_binding(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
        app = create_gateway_app(platform=StubPlatform())
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            headers={"X-Mullu-Deployment-Secret": "deployment-secret"},
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
                "roles": ["deployment_canary"],
                "metadata": {"purpose": "deployment_witness_canary"},
            },
        )

        data = resp.json()
        mapping = app.state.tenant_identity_store.resolve(
            "web",
            "deployment-canary-session",
        )
        assert resp.status_code == 200
        assert data["status"] == "stored"
        assert data["active_mappings"] == 1
        assert data["roles"] == ["deployment_canary"]
        assert mapping is not None
        assert mapping.tenant_id == "tenant-canary"
        assert mapping.metadata["purpose"] == "deployment_witness_canary"
        assert data["platform_identity"]["available"] is False
        assert data["platform_identity"]["reason"] == "platform_access_runtime_not_available"

    def test_deployment_tenant_mapping_seeds_platform_tenant_and_rbac_identity(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
        platform = GovernedDeploymentPlatform()
        app = create_gateway_app(platform=platform)
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            headers={"X-Mullu-Deployment-Secret": "deployment-secret"},
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
                "roles": ["deployment_canary", "operator"],
                "platform_roles": ["operator", "deployment_canary"],
                "metadata": {"purpose": "deployment_witness_canary"},
            },
        )

        data = resp.json()
        identity = platform._access_runtime.get_identity("identity-canary")
        bindings = platform._access_runtime.bindings_for_identity("identity-canary")
        gate = platform._tenant_gating.get_status("tenant-canary")
        mapping = app.state.tenant_identity_store.resolve("web", "deployment-canary-session")
        assert resp.status_code == 200
        assert data["status"] == "stored"
        assert data["platform_tenant"]["available"] is True
        assert data["platform_tenant"]["tenant_registered"] is True
        assert data["platform_tenant"]["status"] == "active"
        assert data["platform_identity"]["available"] is True
        assert data["platform_identity"]["identity_registered"] is True
        assert data["platform_identity"]["roles_bound"] == ["operator"]
        assert data["platform_identity"]["skipped_roles"] == ["deployment_canary"]
        assert gate is not None
        assert gate.status == TenantStatus.ACTIVE
        assert platform._tenant_gating.denial_reason("tenant-canary") is None
        assert identity.tenant_id == "tenant-canary"
        assert identity.enabled is True
        assert len(bindings) == 1
        assert bindings[0].role_id == "operator"
        assert bindings[0].scope_ref_id == "tenant-canary"
        assert mapping is not None
        assert mapping.roles == ("deployment_canary", "operator")

    def test_deployment_tenant_mapping_unblocks_platform_connect(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
        access_runtime = AccessRuntimeEngine(EventSpineEngine())
        seed_default_permissions(access_runtime)
        tenant_gating = TenantGatingRegistry(
            store=InMemoryTenantGatingStore(),
            allow_unknown_tenants=False,
        )
        platform = Platform(
            clock=lambda: "2026-06-07T00:00:00Z",
            access_runtime=access_runtime,
            tenant_gating=tenant_gating,
        )
        app = create_gateway_app(platform=platform)
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            headers={"X-Mullu-Deployment-Secret": "deployment-secret"},
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
                "roles": ["operator"],
                "platform_roles": ["operator"],
            },
        )
        session = platform.connect(
            identity_id="identity-canary",
            tenant_id="tenant-canary",
        )
        closure = session.close()

        assert resp.status_code == 200
        assert resp.json()["platform_tenant"]["status"] == "active"
        assert tenant_gating.denial_reason("tenant-canary") is None
        assert closure.tenant_id == "tenant-canary"
        assert closure.identity_id == "identity-canary"

    def test_deployment_tenant_mapping_rejects_blocked_platform_tenant(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
        platform = GovernedDeploymentPlatform()
        platform._tenant_gating.register(
            "tenant-canary",
            status=TenantStatus.SUSPENDED,
            reason="canary intentionally blocked",
        )
        app = create_gateway_app(platform=platform)
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            headers={"X-Mullu-Deployment-Secret": "deployment-secret"},
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
                "roles": ["operator"],
            },
        )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "platform tenant gate not active"
        assert app.state.tenant_identity_store.count() == 0
        with pytest.raises(RuntimeCoreInvariantError):
            platform._access_runtime.get_identity("identity-canary")

    def test_deployment_tenant_mapping_rejects_platform_identity_tenant_mismatch(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
        platform = AccessRuntimePlatform()
        platform._access_runtime.register_identity(
            "identity-canary",
            "identity-canary",
            tenant_id="other-tenant",
        )
        app = create_gateway_app(platform=platform)
        local_client = TestClient(app)

        resp = local_client.post(
            "/deployment/tenant-mappings",
            headers={"X-Mullu-Deployment-Secret": "deployment-secret"},
            json={
                "channel": "web",
                "sender_id": "deployment-canary-session",
                "tenant_id": "tenant-canary",
                "identity_id": "identity-canary",
                "roles": ["operator"],
            },
        )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "platform identity tenant mismatch"
        assert app.state.tenant_identity_store.count() == 0


# ═══ WhatsApp ═══


class TestWhatsAppWebhook:
    def test_verify_not_configured(self, client):
        # WhatsApp not configured (no env var) — 503
        resp = client.get(
            "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=t&hub.challenge=c"
        )
        assert resp.status_code == 503

    def test_receive_not_configured(self, client):
        resp = client.post("/webhook/whatsapp", content=b"{}")
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
        resp = client.get(
            "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=verify_me&hub.challenge=test123"
        )
        assert resp.status_code == 200
        assert resp.text == "test123"

    def test_verify_invalid_token(self):
        app = create_gateway_app(platform=StubPlatform())
        client = TestClient(app)
        resp = client.get(
            "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=c"
        )
        assert resp.status_code == 403

    def test_receive_with_message_returns_request_receipt(self):
        app = create_gateway_app(platform=StubPlatform(response="WA reply"))
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="whatsapp",
                sender_id="+1234567890",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        client = TestClient(app)
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "+1234567890",
                                        "id": "wamid.1",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
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
        resp = client.post("/webhook/telegram", content=b"{}")
        assert resp.status_code == 503

    def test_receive_with_message(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        app = create_gateway_app(platform=StubPlatform(response="TG reply"))
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="telegram",
                sender_id="98765",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        client = TestClient(app)
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 98765},
                "chat": {"id": 98765},
                "text": "Hello",
            },
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
        resp = client.post("/webhook/slack", content=b"{}")
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
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="slack",
                sender_id="U123",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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
        resp = client.post("/webhook/discord", content=b"{}")
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
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="discord",
                sender_id="D123",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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
            "/webhook/web",
            content=json.dumps({}),
            headers={"X-Session-Token": "test-token"},
        )
        assert resp.status_code == 400

    def test_fabric_admission_accepts_single_capability_source(
        self, monkeypatch, tmp_path
    ):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=False,
        )
        app = create_gateway_app(
            platform=StubPlatform(response="Fabric governed response")
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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
        audits_resp = client.get(
            "/capability-fabric/admission-audits?tenant_id=t1&status=accepted"
        )

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

    def test_fabric_admission_accepts_capability_pack_source(
        self, monkeypatch, tmp_path
    ):
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
        app = create_gateway_app(
            platform=StubPlatform(response="Pack governed response")
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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

        gate = build_capability_admission_gate_from_env(
            clock=lambda: "2026-04-29T00:00:00Z"
        )
        assert gate is not None
        read_model = gate.read_model()
        accepted = gate.admit(
            command_id="cmd-default-creative", intent_name="creative.document_generate"
        )
        rejected = gate.admit(
            command_id="cmd-default-missing", intent_name="creative.missing"
        )

        assert read_model["capsule_count"] == 13
        assert read_model["capability_count"] == 81
        assert len(read_model["governed_capability_records"]) == 81
        assert len(read_model["capability_maturity_assessments"]) == 81
        assert read_model["capability_maturity_counts"]["C3"] == 79
        assert read_model["capability_maturity_counts"]["C6"] == 2
        assert read_model["production_ready_count"] == 2
        assert read_model["autonomy_ready_count"] == 0
        assert accepted.status is CommandCapabilityAdmissionStatus.ACCEPTED
        assert accepted.capability_id == "creative.document_generate"
        assert accepted.domain == "creative"
        assert "document_id" in accepted.evidence_required
        assert rejected.status is CommandCapabilityAdmissionStatus.REJECTED
        assert rejected.capability_id == ""
        assert "no installed capability" in rejected.reason

    def test_command_capability_admission_read_model_reports_accepted_witness(
        self, monkeypatch, tmp_path
    ):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=True,
        )
        app = create_gateway_app(
            platform=StubPlatform(response="Audit governed response")
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "fabric-audit-accepted"},
        )
        certificate = app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        audit_resp = client.get(
            f"/commands/{certificate.command_id}/capability-admission"
        )

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

    def test_fabric_admission_rejects_missing_pack_capability(
        self, monkeypatch, tmp_path
    ):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["llm_completion", "financial.balance_check"],
            capability_payloads=[_fabric_capability_payload("llm_completion")],
            use_pack=True,
        )

        with pytest.raises(ValueError, match="missing capabilities"):
            create_gateway_app(platform=StubPlatform())

    def test_fabric_admission_blocks_uninstalled_runtime_intent(
        self, monkeypatch, tmp_path
    ):
        _configure_fabric_env(
            monkeypatch,
            tmp_path,
            capability_refs=["financial.balance_check"],
            capability_payloads=[_fabric_capability_payload("financial.balance_check")],
            use_pack=True,
        )
        app = create_gateway_app(platform=StubPlatform(response="should not execute"))
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        client = TestClient(app)

        resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "fabric-runtime-reject"},
        )
        audits_resp = client.get(
            "/capability-fabric/admission-audits?tenant_id=t1&status=rejected"
        )

        assert resp.status_code == 200
        assert resp.json()["metadata"]["error"] == "capability_admission_rejected"
        assert (
            resp.json()["body"]
            == "This command requires capability review before execution."
        )
        assert "llm_completion" in resp.json()["metadata"]["reason"]
        assert audits_resp.status_code == 200
        assert audits_resp.json()["count"] == 1
        assert audits_resp.json()["admission_audits"][0]["status"] == "rejected"

    # ═══ Approval Callback ═══

    def test_capability_plan_read_model_reports_terminal_certificate(self):
        app = create_gateway_app(platform=StubPlatform(response="unused fallback"))
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router._skills.register(
            FunctionCapabilityHandler(
                "enterprise.knowledge_search",
                lambda context, params: {
                    "response": "Knowledge searched.",
                    "chunks": ["policy"],
                    "scores": [1.0],
                    "total_chunks_searched": 1,
                    "receipt_status": "searched",
                },
            )
        )
        app.state.router._skills.register(
            FunctionCapabilityHandler(
                "enterprise.task_schedule",
                lambda context, params: {
                    "response": "Task scheduled: task-1",
                    "task_id": "task-1",
                    "receipt_status": "scheduled",
                },
            )
        )
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps(
                {
                    "body": "search knowledge docs and search knowledge policy",
                    "user_id": "web-user",
                }
            ),
            headers={"X-Session-Token": "plan-read-model-token"},
        )
        plan_id = msg_resp.json()["metadata"]["plan_id"]
        read_model_resp = client.get("/capability-plans/read-model")
        closure_resp = client.get(f"/capability-plans/{plan_id}/closure")
        plan_review_resp = client.get(
            f"/operator/plan-review/read-model?tenant_id=t1&plan_id={plan_id}"
        )
        receipt_bundle_resp = client.get("/operator/plan-review/receipts/read-model?tenant_id=t1")
        receipt_bundle_html_resp = client.get("/operator/plan-review/receipts?tenant_id=t1")
        receipt_export_resp = client.get(
            f"/operator/plan-review/{plan_id}/receipts/read-model"
        )
        receipt_export_html_resp = client.get(
            f"/operator/plan-review/{plan_id}/receipts"
        )
        missing_resp = client.get("/capability-plans/missing-plan/closure")

        assert msg_resp.status_code == 200
        assert msg_resp.json()["metadata"]["plan_terminal_certificate_id"].startswith(
            "plan-cert-"
        )
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
        assert closure_resp.json()["plan_evidence_bundle"]["bundle_id"].startswith(
            "plan-evidence-bundle-"
        )
        assert closure_resp.json()["plan_evidence_bundle"]["plan_id"] == plan_id
        assert (
            closure_resp.json()["plan_evidence_bundle"]["certificate_id"]
            == closure_resp.json()["plan_terminal_certificate"]["certificate_id"]
        )
        assert len(closure_resp.json()["plan_evidence_bundle"]["step_command_ids"]) == 2
        assert (
            len(
                closure_resp.json()["plan_evidence_bundle"][
                    "step_terminal_certificate_ids"
                ]
            )
            == 2
        )
        assert closure_resp.json()["plan_evidence_bundle"]["evidence_refs"]
        assert closure_resp.json()["witness_count"] == 1
        assert closure_resp.json()["recovery_attempt_count"] == 0
        assert closure_resp.json()["plan_recovery_attempts"] == []
        assert (
            closure_resp.json()["plan_witnesses"][0]["detail"]["cause"]
            == "plan_terminal_certificate_issued"
        )
        assert plan_review_resp.status_code == 200
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA),
            plan_review_resp.json(),
        ) == []
        assert plan_review_resp.json()["plans"][0]["receipt_export_href"] == (
            f"/operator/plan-review/{plan_id}/receipts"
        )
        assert receipt_bundle_resp.status_code == 200
        receipt_bundle = receipt_bundle_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_RECEIPT_BUNDLE_READ_MODEL_SCHEMA),
            receipt_bundle,
        ) == []
        assert receipt_bundle["schema_ref"] == (
            "urn:mullusi:schema:operator-plan-receipt-bundle-read-model:1"
        )
        assert receipt_bundle["plan_export_count"] == 1
        assert receipt_bundle["certified_export_count"] == 1
        assert receipt_bundle["evidence_bundle_count"] == 1
        assert receipt_bundle["step_command_count"] == 2
        assert receipt_bundle["receipt_group_count"] == 2
        assert receipt_bundle["receipt_count"] >= 2
        assert receipt_bundle["missing_step_command_ids"] == []
        assert receipt_bundle["plan_export_summaries"][0]["plan_id"] == plan_id
        assert receipt_bundle["plan_export_summaries"][0]["receipt_export_href"] == (
            f"/operator/plan-review/{plan_id}/receipts"
        )
        assert receipt_bundle["plan_exports"][0]["plan_id"] == plan_id
        assert receipt_bundle["raw_message_exposed"] is False
        assert receipt_bundle["execution_allowed"] is False
        assert receipt_bundle["write_allowed"] is False
        assert receipt_bundle_html_resp.status_code == 200
        assert "Mullu Plan Receipt Bundle" in receipt_bundle_html_resp.text
        assert receipt_export_resp.status_code == 200
        receipt_export = receipt_export_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_RECEIPT_EXPORT_READ_MODEL_SCHEMA),
            receipt_export,
        ) == []
        assert receipt_export["status"] == "certified"
        assert receipt_export["evidence_bundle_available"] is True
        assert receipt_export["plan_evidence_bundle"]["plan_id"] == plan_id
        assert receipt_export["step_command_count"] == 2
        assert receipt_export["receipt_group_count"] == 2
        assert receipt_export["receipt_count"] >= 2
        assert receipt_export["missing_step_command_ids"] == []
        assert receipt_export["raw_message_exposed"] is False
        assert receipt_export["execution_allowed"] is False
        assert receipt_export["write_allowed"] is False
        assert receipt_export_html_resp.status_code == 200
        assert "Mullu Plan Receipt Export" in receipt_export_html_resp.text
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
        retry_witness = app.state.plan_ledger.record_failure(
            plan=retry_plan, execution=retry_execution
        )

        filtered_resp = client.get(
            "/capability-plans/read-model?recovery_action=wait_for_approval"
        )
        paged_resp = client.get(
            "/capability-plans/read-model?failed_witness_limit=1&failed_witness_offset=1"
        )
        empty_resp = client.get(
            "/capability-plans/read-model?recovery_action=compensate_or_review"
        )

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
        assert (
            filtered_resp.json()["failed_plan_witnesses"][0]["witness_id"]
            == witness.witness_id
        )
        assert filtered_resp.json()["failed_plan_witnesses"][0]["detail"][
            "recovery_decision"
        ]["approval_required"]
        assert paged_resp.status_code == 200
        assert paged_resp.json()["failed_plan_witness_page"] == {
            "total": 2,
            "limit": 1,
            "offset": 1,
            "next_offset": None,
        }
        assert len(paged_resp.json()["failed_plan_witnesses"]) == 1
        assert (
            paged_resp.json()["failed_plan_witnesses"][0]["witness_id"]
            == retry_witness.witness_id
        )
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
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="web-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router._skills.register(
            FunctionCapabilityHandler(
                "enterprise.knowledge_search",
                lambda context, params: {
                    "response": "Knowledge searched.",
                    "chunks": ["policy"],
                    "scores": [1.0],
                    "total_chunks_searched": 1,
                    "receipt_status": "searched",
                },
            )
        )
        client = TestClient(app)

        blocked_resp = client.post(
            "/webhook/web",
            content=json.dumps(
                {
                    "body": "search knowledge docs and schedule review",
                    "user_id": "web-user",
                }
            ),
            headers={"X-Session-Token": "plan-recover-token"},
        )
        plan_id = blocked_resp.json()["metadata"]["plan_id"]
        request_id = blocked_resp.json()["metadata"]["plan_error"].split(
            "approval_required:", 1
        )[1]
        approval_resp = app.state.router.handle_approval_callback(
            request_id, approved=True, resolved_by="operator-1"
        )
        recover_resp = client.post(f"/capability-plans/{plan_id}/recover")
        repeat_recover_resp = client.post(f"/capability-plans/{plan_id}/recover")
        second_recover_resp = client.post("/capability-plans/missing-plan/recover")
        read_model_resp = client.get("/capability-plans/read-model")
        rejected_read_model_resp = client.get(
            "/capability-plans/read-model?recovery_attempt_status=rejected"
        )
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
        assert recover_resp.json()["plan_terminal_certificate_id"].startswith(
            "plan-cert-"
        )
        assert repeat_recover_resp.status_code == 409
        assert (
            repeat_recover_resp.json()["detail"]
            == "plan already has terminal certificate"
        )
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
        assert (
            rejected_read_model_resp.json()["recovery_attempt_status_filter"]
            == "rejected"
        )
        assert [
            attempt["status"]
            for attempt in rejected_read_model_resp.json()["recovery_attempts"]
        ] == [
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
        assert [
            attempt["status"]
            for attempt in closure_resp.json()["plan_recovery_attempts"]
        ] == [
            "succeeded",
            "rejected",
        ]
        assert (
            closure_resp.json()["plan_recovery_attempts"][0]["reason"]
            == "plan_recovered"
        )
        assert (
            closure_resp.json()["plan_recovery_attempts"][1]["reason"]
            == "plan_already_certified"
        )

    def test_operator_plan_review_exposes_budget_history_and_links(self):
        app = create_gateway_app(platform=StubPlatform(response="unused fallback"))
        client = TestClient(app)

        preview_resp = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs plan-review-secret-14 and schedule "
                    "review plan-review-secret-14"
                ),
            },
        )
        preview_plan_id = re.search(r"\b(plan-[a-f0-9]{16})\b", preview_resp.text).group(1)
        preview_model_resp = client.get(
            "/operator/plan-review/read-model?tenant_id=t1"
            "&status=preview_ready&budget_gate=budget_reserved"
        )
        preview_html_resp = client.get(
            f"/operator/plan-review?tenant_id=t1&status=preview_ready"
            f"&budget_gate=budget_reserved&search={preview_plan_id}"
        )
        preview_detail_resp = client.get(
            f"/operator/plan-review/{preview_plan_id}?tenant_id=t1"
        )

        assert preview_resp.status_code == 200
        assert preview_model_resp.status_code == 200
        preview_data = preview_model_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA),
            preview_data,
        ) == []
        preview_rows = {
            row["plan_id"]: row for row in preview_data["plans"]
        }
        assert preview_plan_id in preview_rows
        assert preview_rows[preview_plan_id]["status"] == "preview_ready"
        assert preview_rows[preview_plan_id]["budget_required"] is True
        assert preview_rows[preview_plan_id]["budget_gate"] == "budget_reserved"
        assert preview_rows[preview_plan_id]["budget_evidence_state"] == "preview_budget"
        assert "step-2" in preview_rows[preview_plan_id]["required_by_steps"]
        assert preview_rows[preview_plan_id]["execution_spend_allowed"] is False
        assert preview_html_resp.status_code == 200
        assert "Mullu Plan Review" in preview_html_resp.text
        assert "Plan Review Filters" in preview_html_resp.text
        assert 'value="preview_ready" selected' in preview_html_resp.text
        assert 'value="budget_reserved" selected' in preview_html_resp.text
        assert f"/operator/plan-review/{preview_plan_id}?tenant_id=t1" in preview_html_resp.text
        assert preview_detail_resp.status_code == 200
        assert "Mullu Plan Review Detail" in preview_detail_resp.text

        failed_plan = one_step_plan(
            capability_id="enterprise.task_schedule",
            params={"title": "Review plan review evidence"},
            tenant_id="t1",
            identity_id="u1",
            goal="schedule plan-review-secret-15",
        )
        failed_execution = CapabilityPlanExecutor(
            lambda step, completed: CapabilityPlanStepResult(
                step_id=step.step_id,
                capability_id=step.capability_id,
                succeeded=False,
                command_id="cmd-plan-review-failed",
                error="approval_required:apr-plan-review",
            )
        ).execute(failed_plan)
        witness = app.state.plan_ledger.record_failure(
            plan=failed_plan,
            execution=failed_execution,
        )
        attempt = app.state.plan_ledger.record_recovery_attempt(
            plan_id=failed_plan.plan_id,
            recovery_action="wait_for_approval",
            status="succeeded",
            reason="plan_recovered",
            witness_id=witness.witness_id,
            terminal_certificate_id="plan-cert-review-manual",
        )

        failed_model_resp = client.get(
            f"/operator/plan-review/read-model?tenant_id=t1"
            f"&plan_id={failed_plan.plan_id}&status=failed"
        )
        recovered_model_resp = client.get(
            f"/operator/plan-review/read-model?tenant_id=t1"
            f"&plan_id={failed_plan.plan_id}&status=recovered"
        )
        invalid_status_resp = client.get(
            "/operator/plan-review/read-model?status=unknown_status"
        )
        invalid_budget_resp = client.get(
            "/operator/plan-review/read-model?budget_gate=over_budget"
        )
        overlong_search_resp = client.get(
            "/operator/plan-review/read-model?search=" + ("x" * 129)
        )

        assert failed_model_resp.status_code == 200
        failed_data = failed_model_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA),
            failed_data,
        ) == []
        assert failed_data["count"] == 1
        assert failed_data["plans"][0]["review_type"] == "failed_witness"
        assert failed_data["plans"][0]["budget_gate"] == "budget_reserved"
        assert failed_data["plans"][0]["budget_evidence_state"] == (
            "witness_plan_snapshot"
        )
        assert failed_data["plans"][0]["recovery_action"] == "wait_for_approval"
        assert recovered_model_resp.status_code == 200
        recovered_data = recovered_model_resp.json()
        assert recovered_data["count"] == 1
        assert recovered_data["plans"][0]["attempt_id"] == attempt.attempt_id
        assert recovered_data["plans"][0]["status"] == "recovered"
        assert recovered_data["plans"][0]["certificate_id"] == (
            "plan-cert-review-manual"
        )
        assert invalid_status_resp.status_code == 400
        assert "status must be one of" in invalid_status_resp.json()["detail"]
        assert invalid_budget_resp.status_code == 400
        assert "budget_gate must be one of" in invalid_budget_resp.json()["detail"]
        assert overlong_search_resp.status_code == 400
        assert overlong_search_resp.json()["detail"] == (
            "search must be 128 characters or fewer"
        )
        assert "plan-review-secret-14" not in json.dumps(
            {
                "preview": preview_data,
                "html": preview_html_resp.text,
                "detail": preview_detail_resp.text,
            },
            sort_keys=True,
        )
        assert "plan-review-secret-15" not in json.dumps(
            {
                "failed": failed_data,
                "recovered": recovered_data,
            },
            sort_keys=True,
        )

    def test_operator_plan_review_overlays_live_tenant_budget_report(self):
        budget_manager = TenantBudgetManager(
            clock=lambda: "2026-06-16T12:00:00+00:00",
        )
        budget_manager.set_policy(
            TenantBudgetPolicy(tenant_id="t1", max_cost=4.0, max_calls=8)
        )
        budget_manager.ensure_budget("t1")
        budget_manager.record_spend("t1", 1.25)
        app = create_gateway_app(
            platform=StubPlatform(response="unused fallback"),
            tenant_budget_reporter=budget_manager,
        )
        client = TestClient(app)

        preview_resp = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs budget-report-secret-21 and schedule "
                    "review budget-report-secret-21"
                ),
            },
        )
        plan_id = re.search(r"\b(plan-[a-f0-9]{16})\b", preview_resp.text).group(1)
        read_model_resp = client.get(
            f"/operator/plan-review/read-model?tenant_id=t1&plan_id={plan_id}"
        )

        assert preview_resp.status_code == 200
        assert read_model_resp.status_code == 200
        read_model = read_model_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA),
            read_model,
        ) == []
        assert read_model["count"] == 1
        row = read_model["plans"][0]
        assert row["budget_evidence_state"] == "tenant_budget_report"
        assert row["used_cost_source"] == "tenant_budget_report"
        assert row["used_cost_units"] == 1.25
        assert row["limit_cost_units"] == 4.0
        assert row["remaining_cost_units"] == 2.75
        assert row["budget_report_href"] == "/operator/plan-review/budget/t1"
        assert row["execution_spend_allowed"] is False
        assert "step-2" in row["required_by_steps"]
        assert "budget-report-secret-21" not in json.dumps(
            read_model,
            sort_keys=True,
        )
        budget_read_model_resp = client.get(f"{row['budget_report_href']}/read-model")
        budget_html_resp = client.get(row["budget_report_href"])
        budget_read_model = budget_read_model_resp.json()
        assert budget_read_model_resp.status_code == 200
        assert budget_html_resp.status_code == 200
        assert _validate_schema_instance(
            _load_schema(OPERATOR_BUDGET_REPORT_READ_MODEL_SCHEMA),
            budget_read_model,
        ) == []
        assert budget_read_model["status"] == "available"
        assert budget_read_model["report"]["spent_cost_units"] == 1.25
        assert budget_read_model["report"]["limit_cost_units"] == 4.0
        assert budget_read_model["report"]["remaining_cost_units"] == 2.75
        assert budget_read_model["execution_allowed"] is False
        assert budget_read_model["write_allowed"] is False
        assert "budget-report-secret-21" not in json.dumps(
            budget_read_model,
            sort_keys=True,
        )

    def test_operator_plan_review_surfaces_budget_reporter_errors(self):
        class FailingBudgetReporter:
            def report(self, tenant_id):
                raise RuntimeError(f"budget store unavailable for {tenant_id}")

        app = create_gateway_app(
            platform=StubPlatform(response="unused fallback"),
            tenant_budget_reporter=FailingBudgetReporter(),
        )
        client = TestClient(app)

        preview_resp = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs budget-error-secret-22 and schedule "
                    "review budget-error-secret-22"
                ),
            },
        )
        plan_id = re.search(r"\b(plan-[a-f0-9]{16})\b", preview_resp.text).group(1)
        read_model_resp = client.get(
            f"/operator/plan-review/read-model?tenant_id=t1&plan_id={plan_id}"
        )

        assert preview_resp.status_code == 200
        assert read_model_resp.status_code == 200
        read_model = read_model_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_PLAN_REVIEW_READ_MODEL_SCHEMA),
            read_model,
        ) == []
        assert read_model["plans"][0]["budget_evidence_state"] == (
            "tenant_budget_report_error"
        )
        assert read_model["plans"][0]["used_cost_source"] == (
            "tenant_budget_report_error"
        )
        assert "budget-error-secret-22" not in json.dumps(
            read_model,
            sort_keys=True,
        )


class TestApprovalWebhook:
    def test_approve_unknown_request(self, client):
        resp = client.post(
            "/webhook/approve/nonexistent",
            content=json.dumps(
                {
                    "approved": True,
                    "resolver_channel": "web",
                    "resolver_sender_id": "web-user",
                }
            ),
        )
        assert resp.status_code == 404

    def test_approve_valid_request(self, client):
        # First trigger a high-risk message to create pending approval
        app = client.app
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="operator",
                tenant_id="t1",
                identity_id="operator-1",
                approval_authority=True,
                metadata={"operator_session_present": True},
            )
        )
        client = TestClient(app)

        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps(
                {
                    "approved": True,
                    "resolver_channel": "web",
                    "resolver_sender_id": "operator",
                }
            ),
            headers={"X-Mullu-Approval-Secret": "approve-secret"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert "approved" in data["body"]
        assert data["metadata"]["approval_resolved"] is True
        assert data["metadata"]["approval_strength_decision"] == "allow"
        assert data["metadata"]["approval_strength"] == "operator_bound"
        assert data["metadata"]["required_approval_strength"] == "operator_bound"
        events = app.state.command_ledger.events_for(data["metadata"]["command_id"])
        approval_event = next(
            event for event in events if event.next_state == CommandState.APPROVED
        )
        assert approval_event.detail["approval_strength_decision"] == "allow"
        assert approval_event.detail["approval_strength"] == "operator_bound"
        assert (
            approval_event.detail["approval_strength_policy"]
            == "channel_approval_strength_policy.foundation"
        )

    def test_approval_callback_blocks_under_strength_high_risk_resolver(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="operator",
                tenant_id="t1",
                identity_id="operator-1",
                approval_authority=True,
            )
        )
        client = TestClient(app)
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps(
                {
                    "approved": True,
                    "resolver_channel": "web",
                    "resolver_sender_id": "operator",
                }
            ),
        )

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "approval_strength_denied"
        assert detail["approval_strength_decision"] == "block"
        assert "operator_session_missing" in detail["approval_strength_reasons"]
        assert (
            "operator_bound_approval_required"
            in detail["approval_strength_required_controls"]
        )
        assert app.state.router.pending_approvals == 1

    def test_approval_callback_strength_appears_in_operator_history(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="operator",
                tenant_id="t1",
                identity_id="operator-1",
                approval_authority=True,
                metadata={"operator_session_present": True},
            )
        )
        client = TestClient(app)
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        approve_resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps(
                {
                    "approved": True,
                    "resolver_channel": "web",
                    "resolver_sender_id": "operator",
                }
            ),
        )
        history_resp = client.get(
            f"/operator/approvals/read-model?tenant_id=t1&request_id={request_id}"
        )
        detail_resp = client.get(f"/operator/approvals/{request_id}?tenant_id=t1")

        assert approve_resp.status_code == 200
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_APPROVAL_HISTORY_READ_MODEL_SCHEMA),
            history_data,
        ) == []
        approval = history_data["approvals"][0]
        assert approval["approval_strength_policy"] == (
            "channel_approval_strength_policy.foundation"
        )
        assert approval["approval_strength_decision"] == "allow"
        assert approval["approval_strength"] == "operator_bound"
        assert approval["required_approval_strength"] == "operator_bound"
        assert approval["approval_strength_required_controls"] == []
        assert detail_resp.status_code == 200
        assert "operator_bound" in detail_resp.text
        assert "channel_approval_strength_policy.foundation" in detail_resp.text

    def test_approval_callback_requires_resolver_identity(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
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
        assert (
            resp.json()["detail"]
            == "resolver_channel and resolver_sender_id are required"
        )

    def test_approval_callback_denies_unauthorized_resolver(self):
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="risk-user",
                tenant_id="t1",
                identity_id="u1",
            )
        )
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="viewer",
                tenant_id="t1",
                identity_id="viewer-1",
            )
        )
        client = TestClient(app)
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "delete all files", "user_id": "risk-user"}),
            headers={"X-Session-Token": "sess-risk"},
        )
        request_id = msg_resp.json()["body"].split("Request ID: ", 1)[1]

        resp = client.post(
            f"/webhook/approve/{request_id}",
            content=json.dumps(
                {
                    "approved": True,
                    "resolver_channel": "web",
                    "resolver_sender_id": "viewer",
                }
            ),
        )

        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "approval_context_denied"
        assert detail["authority_reason"] == "resolver_lacks_approval_authority"


# ═══ Gateway Status ═══


class TestGatewayStatus:
    def test_gateway_whqr_replay_binding_rejects_unsupported_fields(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "0.1.0",
            "authority_override": "not-permitted",
        })

        assert binding == {}
        assert "authority_override" not in binding
        assert binding.get("replay_ref", "") == ""

    def test_gateway_whqr_replay_binding_rejects_empty_digest_refs(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": "whqr://replay/sha256:",
            "canonical_hash": "sha256:",
            "semantics_hash": "sha256:",
            "version": "0.1.0",
        })

        assert binding == {}
        assert binding.get("canonical_hash", "") == ""
        assert binding.get("semantics_hash", "") == ""

    def test_gateway_whqr_replay_binding_rejects_whitespace_digest_refs(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": "whqr://replay/sha256:   ",
            "canonical_hash": "sha256:   ",
            "semantics_hash": "sha256:\t",
            "version": "0.1.0",
        })

        assert binding == {}
        assert binding.get("replay_ref", "") == ""
        assert binding.get("canonical_hash", "") == ""

    def test_gateway_whqr_replay_binding_rejects_nonhex_digest_refs(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": "whqr://replay/sha256:" + ("g" * 64),
            "canonical_hash": "sha256:" + ("g" * 64),
            "semantics_hash": "sha256:" + ("A" * 64),
            "version": "0.1.0",
        })

        assert binding == {}
        assert binding.get("replay_ref", "") == ""
        assert binding.get("semantics_hash", "") == ""

    def test_gateway_whqr_replay_binding_rejects_leading_zero_version(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "01.002.0003",
        })

        assert binding == {}
        assert binding.get("version", "") == ""
        assert binding.get("replay_ref", "") == ""

    def test_gateway_whqr_replay_binding_rejects_non_ascii_decimal_version(self):
        binding = _validated_whqr_replay_binding({
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "\u0661.2.3",
        })

        assert binding == {}
        assert binding.get("version", "") == ""
        assert binding.get("canonical_hash", "") == ""

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
        assert (
            audit_allowed.json()["operator_audit_events"][0]["path"]
            == "/authority/witness"
        )
        assert audit_allowed.json()["operator_audit_events"][0]["authorized"] is False
        assert "authority-secret" not in json.dumps(audit_allowed.json())

    def test_authority_operator_identity_role_allowed_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.delenv("MULLU_AUTHORITY_OPERATOR_SECRET", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="authority-user",
                tenant_id="t1",
                identity_id="authority-1",
                roles=("authority_operator",),
            )
        )
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
        assert (
            denied_wrong_tenant.json()["detail"]
            == "Authority operator access not authorized"
        )

    def test_authority_operator_identity_role_denied_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.delenv("MULLU_AUTHORITY_OPERATOR_SECRET", raising=False)
        app = create_gateway_app(platform=StubPlatform())
        app.state.router.register_tenant_mapping(
            TenantMapping(
                channel="web",
                sender_id="member-user",
                tenant_id="t1",
                identity_id="member-1",
                roles=("tenant_member",),
            )
        )
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

    def test_authority_ownership_read_model_filters_owner_records(
        self, gateway_app, client
    ):
        gateway_app.state.authority_mesh_store.save_ownership(
            TeamOwnership(
                tenant_id="t1",
                resource_ref="financial.send_payment",
                owner_team="finance_ops",
                primary_owner_id="finance-manager-1",
                fallback_owner_id="tenant-owner-1",
                escalation_team="executive_ops",
            )
        )
        gateway_app.state.authority_mesh_store.save_ownership(
            TeamOwnership(
                tenant_id="t1",
                resource_ref="deploy.production",
                owner_team="platform_security",
                primary_owner_id="security-admin-1",
                fallback_owner_id="engineering-lead-1",
                escalation_team="engineering_ops",
            )
        )

        list_resp = client.get("/authority/ownership?tenant_id=t1&limit=1")
        team_resp = client.get("/authority/ownership?owner_team=finance_ops")
        resource_resp = client.get(
            "/authority/ownership?resource_ref=deploy.production"
        )
        owner_resp = client.get(
            "/authority/ownership?primary_owner_id=security-admin-1"
        )
        missing_resp = client.get("/authority/ownership?owner_team=missing-team")

        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 1
        assert list_resp.json()["total"] == 2
        assert list_resp.json()["next_offset"] == 1
        assert team_resp.status_code == 200
        assert team_resp.json()["count"] == 1
        assert team_resp.json()["ownership"][0]["owner_team"] == "finance_ops"
        assert resource_resp.status_code == 200
        assert (
            resource_resp.json()["ownership"][0]["resource_ref"] == "deploy.production"
        )
        assert owner_resp.status_code == 200
        assert (
            owner_resp.json()["ownership"][0]["primary_owner_id"] == "security-admin-1"
        )
        assert missing_resp.status_code == 200
        assert missing_resp.json()["count"] == 0

    def test_authority_policy_read_model_filters_approval_and_escalation_policies(
        self, gateway_app, client
    ):
        gateway_app.state.authority_mesh_store.save_approval_policy(
            ApprovalPolicy(
                policy_id="payment-high-risk-policy",
                tenant_id="t1",
                capability="financial.send_payment",
                risk_tier="high",
                required_roles=("financial_admin",),
                required_approver_count=2,
                separation_of_duty=True,
                timeout_seconds=300,
                escalation_policy_id="finance-escalation",
            )
        )
        gateway_app.state.authority_mesh_store.save_approval_policy(
            ApprovalPolicy(
                policy_id="deploy-high-risk-policy",
                tenant_id="t1",
                capability="deploy.production",
                risk_tier="high",
                required_roles=("security_admin",),
                required_approver_count=2,
                separation_of_duty=True,
                timeout_seconds=600,
                escalation_policy_id="platform-escalation",
            )
        )
        gateway_app.state.authority_mesh_store.save_escalation_policy(
            EscalationPolicy(
                policy_id="finance-escalation",
                tenant_id="t1",
                notify_after_seconds=300,
                escalate_after_seconds=900,
                incident_after_seconds=3600,
                fallback_owner_id="tenant-owner-1",
                escalation_team="executive_ops",
            )
        )

        list_resp = client.get("/authority/policies?tenant_id=t1&limit=1")
        capability_resp = client.get(
            "/authority/policies?capability=financial.send_payment"
        )
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
        assert (
            capability_resp.json()["approval_policies"][0]["capability"]
            == "financial.send_payment"
        )
        assert role_resp.status_code == 200
        assert role_resp.json()["approval_policies"][0]["required_roles"] == [
            "security_admin"
        ]
        assert escalation_resp.status_code == 200
        assert escalation_resp.json()["approval_count"] == 0
        assert escalation_resp.json()["escalation_count"] == 1
        assert (
            escalation_resp.json()["escalation_policies"][0]["escalation_team"]
            == "executive_ops"
        )
        assert missing_resp.status_code == 200
        assert missing_resp.json()["approval_count"] == 0
        assert missing_resp.json()["escalation_count"] == 0

    def test_authority_approval_chain_read_model(self, gateway_app, client):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps(
                {"body": "make a payment of $50", "user_id": "web-user"}
            ),
            headers={"X-Session-Token": "authority-chain-token"},
        )
        assert msg_resp.status_code == 200

        list_resp = client.get("/authority/approval-chains?status=pending")
        paged_resp = client.get(
            "/authority/approval-chains?status=pending&limit=1&offset=0"
        )
        assert list_resp.status_code == 200
        assert paged_resp.status_code == 200
        chains = list_resp.json()["approval_chains"]
        assert chains
        command_id = chains[0]["command_id"]
        policy_id = chains[0]["policy_id"]
        required_role = chains[0]["required_roles"][0]
        chain = gateway_app.state.authority_obligation_mesh.approval_chain_for(
            command_id
        )
        assert chain is not None
        gateway_app.state.authority_mesh_store.save_approval_chain(
            ApprovalChain(
                chain_id=chain.chain_id,
                command_id=chain.command_id,
                tenant_id=chain.tenant_id,
                policy_id=chain.policy_id,
                required_roles=chain.required_roles,
                required_approver_count=chain.required_approver_count,
                approvals_received=chain.approvals_received,
                status=chain.status,
                due_at="2026-04-24T12:00:00+00:00",
            )
        )
        policy_resp = client.get(f"/authority/approval-chains?policy_id={policy_id}")
        role_resp = client.get(
            f"/authority/approval-chains?required_role={required_role}"
        )
        missing_role_resp = client.get(
            "/authority/approval-chains?required_role=security_admin"
        )
        overdue_resp = client.get(
            "/authority/approval-chains?status=pending&overdue=true"
        )
        not_overdue_resp = client.get(
            f"/authority/approval-chains?command_id={command_id}&overdue=false"
        )
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
        assert any(
            chain["command_id"] == command_id
            for chain in policy_resp.json()["approval_chains"]
        )
        assert role_resp.status_code == 200
        assert any(
            chain["command_id"] == command_id
            for chain in role_resp.json()["approval_chains"]
        )
        assert missing_role_resp.status_code == 200
        assert missing_role_resp.json()["count"] == 0
        assert overdue_resp.status_code == 200
        assert any(
            chain["command_id"] == command_id
            for chain in overdue_resp.json()["approval_chains"]
        )
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
        filtered_resp = client.get(
            "/authority/operator-audit?path=/authority/witness&authorized=true"
        )
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
        assert all(
            "sender_id" not in event
            for event in audit_resp.json()["operator_audit_events"]
        )
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
        gateway_app.state.authority_mesh_store.append_escalation_event(
            {
                "event_id": "obl-escalation-test-read-model",
                "obligation_id": obligation.obligation_id,
                "command_id": obligation.command_id,
                "tenant_id": obligation.tenant_id,
                "owner_id": obligation.owner_id,
                "owner_team": obligation.owner_team,
                "escalated_at": "2026-04-24T13:00:00+00:00",
            }
        )
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
            evidence_required=(
                "compensation_receipt",
                "compensation_reviewer_attestation",
            ),
            escalation_policy_id="default",
            terminal_certificate_id="terminal-test-read-model",
        )
        gateway_app.state.authority_mesh_store.save_obligation(compensation_obligation)
        gateway_app.state.authority_mesh_store.append_escalation_event(
            {
                "event_id": "obl-escalation-test-read-model-second",
                "obligation_id": second_obligation.obligation_id,
                "command_id": second_obligation.command_id,
                "tenant_id": second_obligation.tenant_id,
                "owner_id": second_obligation.owner_id,
                "owner_team": second_obligation.owner_team,
                "escalated_at": "2026-04-25T13:00:00+00:00",
            }
        )

        obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&status=open&limit=1"
        )
        case_obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&obligation_type=case_review"
        )
        compensation_obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&obligation_type=compensation_review"
        )
        overdue_obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&status=open&overdue=true"
        )
        not_overdue_obligations_resp = client.get(
            "/authority/obligations?tenant_id=t1&overdue=false"
        )
        invalid_overdue_obligations_resp = client.get(
            "/authority/obligations?overdue=maybe"
        )
        missing_evidence_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": []},
        )
        satisfy_resp = client.post(
            f"/authority/obligations/{obligation.obligation_id}/satisfy",
            json={"evidence_refs": ["case_disposition:read-model-closed"]},
        )
        command_resp = client.get(f"/commands/{obligation.command_id}/authority")
        escalations_resp = client.get(
            f"/authority/escalations?command_id={obligation.command_id}&limit=1"
        )
        responsibility_resp = client.get(
            "/authority/responsibility?tenant_id=t1&limit=2"
        )
        satisfied_resp = client.get(
            "/authority/obligations?tenant_id=t1&status=satisfied"
        )
        witness_resp = client.get("/authority/witness")
        console_resp = client.get("/authority/operator")

        assert obligations_resp.status_code == 200
        assert obligations_resp.json()["count"] == 1
        assert obligations_resp.json()["total"] == 3
        assert obligations_resp.json()["limit"] == 1
        assert obligations_resp.json()["offset"] == 0
        assert obligations_resp.json()["next_offset"] == 1
        assert (
            obligations_resp.json()["obligations"][0]["obligation_id"]
            == obligation.obligation_id
        )
        assert case_obligations_resp.status_code == 200
        assert case_obligations_resp.json()["count"] == 1
        assert (
            case_obligations_resp.json()["obligations"][0]["obligation_type"]
            == "case_review"
        )
        assert compensation_obligations_resp.status_code == 200
        assert compensation_obligations_resp.json()["count"] == 1
        assert (
            compensation_obligations_resp.json()["obligations"][0]["owner_team"]
            == "finance_ops"
        )
        assert compensation_obligations_resp.json()["obligations"][0][
            "evidence_required"
        ] == ["compensation_receipt", "compensation_reviewer_attestation"]
        assert overdue_obligations_resp.status_code == 200
        assert overdue_obligations_resp.json()["count"] == 2
        assert {
            item["obligation_id"]
            for item in overdue_obligations_resp.json()["obligations"]
        } == {obligation.obligation_id, second_obligation.obligation_id}
        assert not_overdue_obligations_resp.status_code == 200
        assert not_overdue_obligations_resp.json()["count"] == 1
        assert (
            not_overdue_obligations_resp.json()["obligations"][0]["obligation_id"]
            == compensation_obligation.obligation_id
        )
        assert invalid_overdue_obligations_resp.status_code == 400
        assert (
            invalid_overdue_obligations_resp.json()["detail"]
            == "overdue must be true or false"
        )
        assert missing_evidence_resp.status_code == 400
        assert satisfy_resp.status_code == 200
        assert satisfy_resp.json()["status"] == "satisfied"
        assert satisfy_resp.json()["obligation"]["status"] == "satisfied"
        assert satisfy_resp.json()["evidence_refs"] == [
            "case_disposition:read-model-closed"
        ]
        assert command_resp.status_code == 200
        assert command_resp.json()["obligations"][0]["owner_team"] == "ops"
        assert command_resp.json()["obligations"][0]["status"] == "satisfied"
        assert escalations_resp.status_code == 200
        assert (
            escalations_resp.json()["escalation_events"][0]["obligation_id"]
            == obligation.obligation_id
        )
        assert escalations_resp.json()["count"] == 1
        assert escalations_resp.json()["total"] == 2
        assert escalations_resp.json()["next_offset"] == 1
        assert responsibility_resp.status_code == 200
        responsibility_payload = responsibility_resp.json()
        assert responsibility_payload["tenant_id"] == "t1"
        assert responsibility_payload["responsibility_debt_clear"] is False
        assert responsibility_payload["unresolved_obligation_count"] == 2
        assert responsibility_payload["escalation_event_count"] == 2
        assert (
            responsibility_payload["priority_obligations"][0]["obligation_id"]
            == second_obligation.obligation_id
        )
        assert (
            responsibility_payload["priority_obligations"][1]["obligation_id"]
            == compensation_obligation.obligation_id
        )
        assert (
            responsibility_payload["priority_escalation_events"][0]["event_id"]
            == "obl-escalation-test-read-model-second"
        )
        assert (
            "authority:obligations_read_model"
            in responsibility_payload["evidence_refs"]
        )
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

    def test_escalate_overdue_authority_obligations_records_transition(
        self, gateway_app, client
    ):
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
        updated = gateway_app.state.authority_mesh_store.load_obligation(
            obligation.obligation_id
        )
        events = gateway_app.state.command_ledger.events_for(certificate.command_id)

        assert resp.status_code == 200
        assert resp.json()["status"] == "escalated"
        assert any(
            item["obligation_id"] == obligation.obligation_id
            for item in resp.json()["obligations"]
        )
        assert resp.json()["authority_witness"]["escalated_obligation_count"] >= 1
        assert updated is not None
        assert updated.status is ObligationStatus.ESCALATED
        assert events[-1].next_state is CommandState.OBLIGATIONS_ESCALATED
        assert gateway_app.state.authority_mesh_store.list_escalation_events()

    def test_expire_overdue_authority_approval_chains_records_transition(
        self, gateway_app, client
    ):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps(
                {"body": "make a payment of $50", "user_id": "web-user"}
            ),
            headers={"X-Session-Token": "authority-expire-chain-token"},
        )
        command_id = msg_resp.json()["metadata"]["command_id"]
        chain = gateway_app.state.authority_obligation_mesh.approval_chain_for(
            command_id
        )
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
        updated = gateway_app.state.authority_obligation_mesh.approval_chain_for(
            command_id
        )
        events = gateway_app.state.command_ledger.events_for(command_id)

        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"
        assert resp.json()["count"] == 1
        assert resp.json()["approval_chains"][0]["status"] == "expired"
        assert resp.json()["authority_witness"]["expired_approval_chain_count"] >= 1
        assert updated is not None
        assert updated.status.value == "expired"
        assert events[-1].next_state is CommandState.DENIED

    def test_close_expired_authority_approval_chains_clears_debt(
        self, gateway_app, client
    ):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps(
                {"body": "make a payment of $50", "user_id": "web-user"}
            ),
            headers={"X-Session-Token": "authority-close-chain-token"},
        )
        command_id = msg_resp.json()["metadata"]["command_id"]
        chain = gateway_app.state.authority_obligation_mesh.approval_chain_for(
            command_id
        )
        assert chain is not None
        gateway_app.state.authority_mesh_store.save_approval_chain(ApprovalChain(
            chain_id=chain.chain_id,
            command_id=chain.command_id,
            tenant_id=chain.tenant_id,
            policy_id=chain.policy_id,
            required_roles=chain.required_roles,
            required_approver_count=chain.required_approver_count,
            approvals_received=chain.approvals_received,
            status=ApprovalChainStatus.EXPIRED,
            due_at="2026-04-24T12:00:00+00:00",
        ))

        resp = client.post(
            "/authority/approval-chains/close-expired",
            json={
                "evidence_refs": ["authority:expired_approval_chain_closure"],
                "command_id": command_id,
            },
        )
        updated = gateway_app.state.authority_obligation_mesh.approval_chain_for(
            command_id
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"
        assert resp.json()["count"] == 1
        assert resp.json()["approval_chains"][0]["status"] == "denied"
        assert resp.json()["authority_witness"]["expired_approval_chain_count"] == 0
        assert updated is not None
        assert updated.status is ApprovalChainStatus.DENIED

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
        whqr_metadata = {
            "whqr_canonical_hash": WHQR_CANONICAL_HASH,
            "whqr_semantics_hash": WHQR_SEMANTICS_HASH,
            "whqr_version": "0.1.0",
        }
        gateway_app.state.command_ledger._terminal_certificates[command_id] = replace(
            certificate,
            metadata={**certificate.metadata, **whqr_metadata},
        )

        resp = client.get(f"/commands/{command_id}/closure")
        assert resp.status_code == 200
        data = resp.json()
        assert data["command_id"] == command_id
        assert data["terminal_certificate"]["disposition"] == "committed"
        assert data["terminal_certificate"]["evidence_refs"]
        assert data["terminal_certificate"]["metadata"]["whqr_canonical_hash"] == (
            WHQR_CANONICAL_HASH
        )
        assert data["whqr_replay_binding"] == {
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "0.1.0",
        }
        assert data["whqr_replay_ref"] == WHQR_REPLAY_REF
        assert len(data["events"]) >= 3
        witnesses = data["proof_coverage_witnesses"]
        invariant_ids = {witness["invariant_id"] for witness in witnesses}
        assert "command_lifecycle_events_are_hash_linked" in invariant_ids
        assert "terminal_closure_requires_evidence_refs" in invariant_ids
        assert "terminal_closure_exposes_whqr_replay_ref" in invariant_ids
        assert (
            "successful_response_is_bound_to_response_evidence_closure" in invariant_ids
        )
        assert all(
            witness["matrix_surface_id"] == "gateway_capability_fabric"
            for witness in witnesses
        )
        assert witnesses[0]["witness_refs"]
        assert (
            witnesses[1]["evidence_refs"]
            == data["terminal_certificate"]["evidence_refs"]
        )
        whqr_witness = next(
            witness
            for witness in witnesses
            if witness["invariant_id"] == "terminal_closure_exposes_whqr_replay_ref"
        )
        assert whqr_witness["witness_ref"] == data["whqr_replay_ref"]
        assert whqr_witness["canonical_hash"] == WHQR_CANONICAL_HASH
        assert data["terminal_certificate"]["response_evidence_closure_id"]

    def test_command_closure_read_model_rejects_malformed_whqr_binding(
        self, gateway_app, client
    ):
        msg_resp = client.post(
            "/webhook/web",
            content=json.dumps({"body": "Hello from web", "user_id": "web-user"}),
            headers={"X-Session-Token": "closure-malformed-token"},
        )
        assert msg_resp.status_code == 200
        certificate = gateway_app.state.command_ledger.latest_terminal_certificate()
        assert certificate is not None
        command_id = certificate.command_id
        gateway_app.state.command_ledger._terminal_certificates[command_id] = replace(
            certificate,
            metadata={
                **certificate.metadata,
                "whqr_canonical_hash": "closure-whqr-canonical",
                "whqr_semantics_hash": "sha256:closure-whqr-semantics",
                "whqr_version": "0.1.0",
            },
        )

        resp = client.get(f"/commands/{command_id}/closure")

        assert resp.status_code == 200
        data = resp.json()
        assert data["whqr_replay_binding"] == {}
        assert data["whqr_replay_ref"] == ""
        invariant_ids = {
            witness["invariant_id"]
            for witness in data["proof_coverage_witnesses"]
        }
        assert "terminal_closure_exposes_whqr_replay_ref" not in invariant_ids

    def test_command_interpretation_receipt_read_model_bounds_raw_message(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-interpretation",
            idempotency_key="interpretation-receipt-read",
            intent="llm_completion",
            payload={
                "body": "do not expose raw body",
                "interpretation_receipt_id": "interpretation-receipt-aaaaaaaaaaaaaaaa",
                "interpretation_receipt": {
                    "receipt_id": "interpretation-receipt-aaaaaaaaaaaaaaaa",
                    "request_id": "interpreted-request-bbbbbbbbbbbbbbbb",
                    "raw_message_hash": "hash-raw-message-1",
                    "interpreted_intent": "llm_completion",
                    "extracted_slots": {
                        "capability_id": "llm_completion",
                        "raw_message": "do not expose nested receipt raw body",
                        "RawMessage": "do not expose mixed-case receipt raw body",
                    },
                    "missing_slots": [],
                    "confidence": 0.91,
                    "model_or_rule_used": "deterministic-rule-v1",
                    "rejected_interpretations": [],
                    "risk_precheck": "low",
                    "created_at": "2026-04-24T12:00:00+00:00",
                    "raw_message": "do not expose raw body",
                },
                "interpreted_request": {
                    "request_id": "interpreted-request-bbbbbbbbbbbbbbbb",
                    "tenant_id": "t1",
                    "actor_id": "u1",
                    "channel": "web",
                    "conversation_id": "conversation-interpretation",
                    "raw_message_hash": "hash-raw-message-1",
                    "intent_class": "action_request",
                    "capability_id": "llm_completion",
                    "extracted_slots": {
                        "capability_id": "llm_completion",
                        "body": "do not expose nested request raw body",
                        "raw-body": "do not expose hyphenated request raw body",
                        "raw_text": "do not expose nested raw text",
                        "rawText": "do not expose camel-case raw text",
                    },
                    "missing_slots": [],
                    "constraints": ["tenant_bound"],
                    "search_needed": False,
                    "action_needed": True,
                    "risk_estimate": "low",
                    "approval_required": False,
                    "confidence": 0.91,
                    "interpreter_kind": "deterministic_rule",
                    "rejected_interpretations": [],
                    "created_at": "2026-04-24T12:00:00+00:00",
                    "raw_message": "do not expose raw body",
                },
            },
        )

        resp = client.get(f"/commands/{command.command_id}/interpretation-receipt")

        assert resp.status_code == 200
        data = resp.json()
        assert data["command_id"] == command.command_id
        assert data["tenant_id"] == "t1"
        assert data["actor_id"] == "u1"
        assert (
            data["schema_ref"]
            == "urn:mullusi:schema:command-interpretation-receipt-read-model:1"
        )
        assert data["interpretation_receipt_id"] == "interpretation-receipt-aaaaaaaaaaaaaaaa"
        assert data["raw_message_exposed"] is False
        assert data["execution_allowed"] is False
        assert data["governed"] is True
        assert data["interpretation_receipt"]["raw_message_hash"] == "hash-raw-message-1"
        assert data["interpretation_receipt"]["interpreted_intent"] == "llm_completion"
        assert data["interpretation_receipt"]["extracted_slots"] == {"capability_id": "llm_completion"}
        assert data["interpreted_request"]["capability_id"] == "llm_completion"
        assert data["interpreted_request"]["extracted_slots"] == {"capability_id": "llm_completion"}
        assert data["interpreted_request"]["constraints"] == ["tenant_bound"]
        assert data["interpreted_request"]["action_needed"] is True
        assert _validate_schema_instance(
            _load_schema(COMMAND_INTERPRETATION_READ_MODEL_SCHEMA),
            data,
        ) == []
        assert _validate_schema_instance(
            _load_schema(INTERPRETATION_RECEIPT_SCHEMA),
            data["interpretation_receipt"],
        ) == []
        assert _validate_schema_instance(
            _load_schema(INTERPRETED_REQUEST_SCHEMA),
            data["interpreted_request"],
        ) == []
        assert "raw_message" not in data["interpretation_receipt"]
        assert "raw_message" not in data["interpreted_request"]
        assert "do not expose raw body" not in json.dumps(data, sort_keys=True)
        assert "do not expose nested" not in json.dumps(data, sort_keys=True)
        assert "do not expose mixed-case" not in json.dumps(data, sort_keys=True)
        assert "do not expose hyphenated" not in json.dumps(data, sort_keys=True)
        assert "do not expose camel-case" not in json.dumps(data, sort_keys=True)

    def test_command_interpretation_receipt_missing_returns_404(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-interpretation-missing",
            idempotency_key="interpretation-receipt-missing",
            intent="llm_completion",
            payload={"body": "no interpretation receipt"},
        )

        resp = client.get(f"/commands/{command.command_id}/interpretation-receipt")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "interpretation receipt not found"

    def test_command_interpretation_receipt_requires_operator_authority_in_production(
        self, monkeypatch
    ):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_AUTHORITY_OPERATOR_SECRET", "authority-secret")
        app = create_gateway_app(platform=StubPlatform())
        local_client = TestClient(app)
        command = app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-interpretation-production",
            idempotency_key="interpretation-receipt-production",
            intent="llm_completion",
            payload={
                "body": "production secret bounded body",
                "interpretation_receipt": {
                    "receipt_id": "interp-rcpt-prod-1",
                    "request_id": "req-interpret-prod-1",
                    "raw_message_hash": "hash-prod-message-1",
                    "interpreted_intent": "llm_completion",
                    "extracted_slots": {},
                    "missing_slots": [],
                    "confidence": 0.88,
                    "model_or_rule_used": "deterministic-rule-v1",
                    "rejected_interpretations": [],
                    "risk_precheck": {"risk_tier": "low"},
                    "created_at": "2026-04-24T12:00:00+00:00",
                },
                "interpreted_request": {
                    "request_id": "req-interpret-prod-1",
                    "tenant_id": "t1",
                    "actor_id": "u1",
                    "channel": "web",
                    "conversation_id": "conversation-interpretation-production",
                    "raw_message_hash": "hash-prod-message-1",
                    "intent_class": "llm_completion",
                    "capability_id": "llm_completion",
                    "extracted_slots": {},
                    "missing_slots": [],
                    "constraints": {},
                    "search_needed": False,
                    "action_needed": True,
                    "risk_estimate": "low",
                    "approval_required": False,
                    "confidence": 0.88,
                    "interpreter_kind": "deterministic_rule",
                    "rejected_interpretations": [],
                    "created_at": "2026-04-24T12:00:00+00:00",
                },
            },
        )

        denied = local_client.get(
            f"/commands/{command.command_id}/interpretation-receipt"
        )
        allowed = local_client.get(
            f"/commands/{command.command_id}/interpretation-receipt",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )

        assert denied.status_code == 403
        assert denied.json()["detail"] == "Authority operator access not authorized"
        assert allowed.status_code == 200
        assert allowed.json()["interpretation_receipt_id"] == "interp-rcpt-prod-1"
        assert allowed.json()["execution_allowed"] is False
        assert "production secret bounded body" not in json.dumps(
            allowed.json(), sort_keys=True
        )

    def test_command_interpretation_receipt_read_model_replays_from_command_store(
        self,
    ):
        store = InMemoryCommandLedgerStore()
        initial_ledger = CommandLedger(
            clock=lambda: "2026-04-24T12:00:00+00:00",
            store=store,
        )
        command = initial_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-interpretation-replay",
            idempotency_key="interpretation-receipt-replay",
            intent="llm_completion",
            payload={
                "body": "replay should not expose body",
                "interpretation_receipt": {
                    "receipt_id": "interp-rcpt-replay-1",
                    "request_id": "req-interpret-replay-1",
                    "raw_message_hash": "hash-replay-message-1",
                    "interpreted_intent": "llm_completion",
                    "extracted_slots": {"capability_id": "llm_completion"},
                    "missing_slots": [],
                    "confidence": 0.93,
                    "model_or_rule_used": "deterministic-rule-v1",
                    "rejected_interpretations": [],
                    "risk_precheck": {"risk_tier": "low"},
                    "created_at": "2026-04-24T12:00:00+00:00",
                },
                "interpreted_request": {
                    "request_id": "req-interpret-replay-1",
                    "tenant_id": "t1",
                    "actor_id": "u1",
                    "channel": "web",
                    "conversation_id": "conversation-interpretation-replay",
                    "raw_message_hash": "hash-replay-message-1",
                    "intent_class": "llm_completion",
                    "capability_id": "llm_completion",
                    "extracted_slots": {"capability_id": "llm_completion"},
                    "missing_slots": [],
                    "constraints": {"tenant_bound": True},
                    "search_needed": False,
                    "action_needed": True,
                    "risk_estimate": "low",
                    "approval_required": False,
                    "confidence": 0.93,
                    "interpreter_kind": "deterministic_rule",
                    "rejected_interpretations": [],
                    "created_at": "2026-04-24T12:00:00+00:00",
                },
            },
        )
        restarted_ledger = CommandLedger(
            clock=lambda: "2026-04-24T12:01:00+00:00",
            store=store,
        )
        app = create_gateway_app(
            platform=StubPlatform(),
            command_ledger_override=restarted_ledger,
        )
        local_client = TestClient(app)

        resp = local_client.get(
            f"/commands/{command.command_id}/interpretation-receipt"
        )

        assert app.state.command_ledger is restarted_ledger
        assert store.load_command(command.command_id) is not None
        assert resp.status_code == 200
        assert resp.json()["command_id"] == command.command_id
        assert resp.json()["interpretation_receipt_id"] == "interp-rcpt-replay-1"
        assert resp.json()["interpreted_request"]["raw_message_hash"] == "hash-replay-message-1"
        assert resp.json()["raw_message_exposed"] is False
        assert "replay should not expose body" not in json.dumps(
            resp.json(), sort_keys=True
        )

    def test_command_universal_action_proof_read_model(self, gateway_app, client):
        whqr_binding = {
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "0.1.0",
        }
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-proof",
            idempotency_key="universal-proof-read",
            intent="llm_completion",
            payload={"body": "run governed action"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": {
                    "action_id": "uact-1",
                    "blocked": False,
                    "block_reason": "",
                    "proof_hash": "proof-hash-1",
                    "capability_id": "shell_command",
                    "dispatch_ledger_hash": "dispatch-ledger-1",
                    "closure_state": "closed_allowed",
                    "reconciliation_ref": "reconciliation://uact-1",
                    "memory_ref": "memory://uact-1",
                    "whqr_replay_binding": whqr_binding,
                    "terminal_certificate_id": "",
                    "learning_admission_id": "",
                },
            },
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.TERMINALLY_CERTIFIED,
            detail={
                "cause": "universal_action_terminal_certificate",
                "terminal_certificate_id": "terminal-1",
                "terminal_disposition": "committed",
                "proof_hash": "proof-hash-1",
            },
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.LEARNING_DECIDED,
            detail={
                "cause": "universal_action_learning_decided",
                "learning_admission_id": "learn-1",
                "learning_status": "admit",
                "proof_hash": "proof-hash-1",
            },
        )

        resp = client.get(f"/commands/{command.command_id}/universal-action-proof")

        assert resp.status_code == 200
        data = resp.json()
        proof = data["universal_action_proof"]
        assert data["command_id"] == command.command_id
        assert data["proof_hash"] == "proof-hash-1"
        assert data["event_count"] == 4
        assert proof["blocked"] is False
        assert proof["action_id"] == "uact-1"
        assert proof["capability_id"] == "shell_command"
        assert proof["dispatch_ledger_hash"] == "dispatch-ledger-1"
        assert proof["closure_state"] == "closed_allowed"
        assert proof["reconciliation_ref"] == "reconciliation://uact-1"
        assert proof["memory_ref"] == "memory://uact-1"
        assert proof["whqr_replay_binding"] == whqr_binding
        assert data["whqr_replay_binding"] == whqr_binding
        assert data["whqr_replay_ref"] == WHQR_REPLAY_REF
        assert proof["terminal_certificate_id"] == "terminal-1"
        assert proof["terminal_disposition"] == "committed"
        assert proof["learning_admission_id"] == "learn-1"
        assert proof["learning_status"] == "admit"
        assert CommandState.DISPATCHED.value in data["state_sequence"]
        assert CommandState.LEARNING_DECIDED.value in data["state_sequence"]

    def test_command_universal_action_proof_read_model_rejects_malformed_whqr_binding(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-proof-malformed",
            idempotency_key="universal-proof-malformed",
            intent="llm_completion",
            payload={"body": "run governed action"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": {
                    "action_id": "uact-malformed",
                    "blocked": False,
                    "block_reason": "",
                    "proof_hash": "proof-hash-malformed",
                    "capability_id": "shell_command",
                    "dispatch_ledger_hash": "dispatch-ledger-malformed",
                    "closure_state": "closed_allowed",
                    "reconciliation_ref": "reconciliation://uact-malformed",
                    "memory_ref": "memory://uact-malformed",
                    "whqr_replay_binding": {
                        "replay_ref": "whqr://replay/sha256:proof-canonical-hash",
                        "canonical_hash": "proof-canonical-hash",
                        "semantics_hash": "sha256:proof-semantics-hash",
                        "version": "0.1.0",
                    },
                    "terminal_certificate_id": "",
                    "learning_admission_id": "",
                },
            },
        )

        resp = client.get(f"/commands/{command.command_id}/universal-action-proof")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "universal action proof not found"

    def test_command_universal_action_proof_missing_returns_404(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-proof-missing",
            idempotency_key="universal-proof-missing",
            intent="llm_completion",
            payload={"body": "no universal proof"},
        )

        resp = client.get(f"/commands/{command.command_id}/universal-action-proof")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "universal action proof not found"

    def test_command_universal_action_orchestration_read_model(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration",
            idempotency_key="universal-orchestration-read",
            intent="refresh_public_status_page",
            payload={"body": "refresh status page"},
        )
        record["action_envelope"]["intent"] = command.command_id
        record["closure"]["whqr_replay_binding"] = {
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "0.1.0",
        }
        for receipt in record["receipts"]:
            if receipt["kind"] == "closure":
                receipt["confirms"] = _uao_closure_confirmation(
                    closure_state=record["closure_state"],
                    reconciliation_ref=record["closure"]["reconciliation_ref"],
                    memory_ref=record["closure"]["memory_ref"],
                    whqr_replay_binding=record["closure"]["whqr_replay_binding"],
                )
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["command_id"] == command.command_id
        assert data["orchestration_id"] == record["orchestration_id"]
        assert data["decision_status"] == "allow"
        assert data["closure_state"] == "closed_allowed"
        assert data["reconciliation_ref"] == record["closure"]["reconciliation_ref"]
        assert data["memory_ref"] == record["closure"]["memory_ref"]
        assert data["whqr_replay_binding"] == record["closure"]["whqr_replay_binding"]
        assert data["whqr_replay_ref"] == WHQR_REPLAY_REF
        assert (
            data["whqr_replay_binding"]["replay_ref"]
            == WHQR_REPLAY_REF
        )
        assert data["universal_action_orchestration"]["raw_reasoning_included"] is False

    def test_command_universal_action_orchestration_missing_returns_404(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-orchestration-missing",
            idempotency_key="universal-orchestration-missing",
            intent="llm_completion",
            payload={"body": "no universal orchestration record"},
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )

    def test_command_universal_action_orchestration_malformed_record_returns_404(
        self, gateway_app, client
    ):
        malformed_record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        malformed_record["raw_reasoning_included"] = True
        malformed_record["chain_of_thought"] = "private reasoning must not replay"
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-malformed",
            idempotency_key="universal-orchestration-malformed",
            intent="refresh_public_status_page",
            payload={"body": "malformed status page replay"},
        )
        malformed_record["action_envelope"]["intent"] = command.command_id
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action_orchestration": malformed_record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_receipt_spoof_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-receipt-spoof",
            idempotency_key="universal-orchestration-receipt-spoof",
            intent="refresh_public_status_page",
            payload={"body": "receipt-spoofed status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        for stage in record["pipeline_stages"]:
            if stage["stage_kind"] == "closure":
                stage["receipt_ref"] = "receipt://spoofed-closure"
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_proof_spoof_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-proof-spoof",
            idempotency_key="universal-orchestration-proof-spoof",
            intent="refresh_public_status_page",
            payload={"body": "proof-spoofed status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        record["orchestration_id"] = "universal-action-orchestration-spoofed"
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_proof_hash_tamper_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-proof-hash-tamper",
            idempotency_key="universal-orchestration-proof-hash-tamper",
            intent="refresh_public_status_page",
            payload={"body": "proof-hash-tampered status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        spoofed_proof_hash = "universal-action-proof-spoofed"
        universal_detail["proof_hash"] = spoofed_proof_hash
        _rebind_uao_fixture_record_to_proof_hash(record, spoofed_proof_hash)
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_closure_memory_tamper_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-closure-memory-tamper",
            idempotency_key="universal-orchestration-closure-memory-tamper",
            intent="refresh_public_status_page",
            payload={"body": "closure-memory-tampered status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        spoofed_memory_ref = "memory://spoofed-gateway-closure-memory"
        record["memory_update"]["memory_ref"] = spoofed_memory_ref
        record["closure"]["memory_ref"] = spoofed_memory_ref
        next(
            stage for stage in record["pipeline_stages"] if stage["stage_kind"] == "memory"
        )["output_refs"] = [spoofed_memory_ref]
        next(
            stage for stage in record["pipeline_stages"] if stage["stage_kind"] == "closure"
        )["input_refs"] = [spoofed_memory_ref]
        for receipt in record["receipts"]:
            if receipt["kind"] == "closure":
                receipt["confirms"] = _uao_closure_confirmation(
                    closure_state=record["closure_state"],
                    reconciliation_ref=record["closure"]["reconciliation_ref"],
                    memory_ref=spoofed_memory_ref,
                )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_event_hash_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-event-hash",
            idempotency_key="universal-orchestration-event-hash",
            intent="refresh_public_status_page",
            payload={"body": "event-hash-tampered status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )
        target_index = next(
            index
            for index, event in enumerate(gateway_app.state.command_ledger._events)
            if event.command_id == command.command_id
            and event.detail.get("cause") == "universal_action_kernel_dispatched"
        )
        gateway_app.state.command_ledger._events[target_index] = replace(
            gateway_app.state.command_ledger._events[target_index],
            event_hash="0" * 64,
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_trace_tamper_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-trace-tamper",
            idempotency_key="universal-orchestration-trace-tamper",
            intent="refresh_public_status_page",
            payload={"body": "trace-tampered status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )
        target_index = next(
            index
            for index, event in enumerate(gateway_app.state.command_ledger._events)
            if event.command_id == command.command_id
            and event.detail.get("cause") == "universal_action_kernel_dispatched"
        )
        gateway_app.state.command_ledger._events[target_index] = (
            _replace_command_event_with_recomputed_hash(
                gateway_app.state.command_ledger._events[target_index],
                trace_id="trc-command-envelope-spoofed",
            )
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id).trace_id == (
            command.trace_id
        )

    def test_command_universal_action_orchestration_incomplete_pipeline_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-incomplete-pipeline",
            idempotency_key="universal-orchestration-incomplete-pipeline",
            intent="refresh_public_status_page",
            payload={"body": "incomplete-pipeline status page replay"},
        )
        record["action_envelope"]["intent"] = command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        record["pipeline_stages"] = [
            stage
            for stage in record["pipeline_stages"]
            if stage["stage_kind"] != "memory"
        ]
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert gateway_app.state.command_ledger.get(command.command_id) is not None

    def test_command_universal_action_orchestration_cross_command_returns_404(
        self, gateway_app, client
    ):
        record = json.loads(
            (
                _ROOT
                / "examples"
                / "universal_action_orchestration.allowed_status_publish.json"
            ).read_text(encoding="utf-8")
        )
        source_command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-source",
            idempotency_key="universal-orchestration-source",
            intent="refresh_public_status_page",
            payload={"body": "source status page replay"},
        )
        target_command = gateway_app.state.command_ledger.create_command(
            tenant_id="tenant_ops_demo",
            actor_id="service:status_page_worker",
            source="web",
            conversation_id="conversation-orchestration-target",
            idempotency_key="universal-orchestration-target",
            intent="refresh_public_status_page",
            payload={"body": "target status page replay"},
        )
        record["action_envelope"]["intent"] = source_command.command_id
        universal_detail = _bind_uao_fixture_to_universal_action_detail(record)
        gateway_app.state.command_ledger.transition(
            target_command.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": universal_detail,
                "universal_action_orchestration": record,
            },
        )

        resp = client.get(
            f"/commands/{target_command.command_id}/universal-action-orchestration"
        )

        assert resp.status_code == 404
        assert (
            resp.json()["detail"] == "universal action orchestration record not found"
        )
        assert (
            gateway_app.state.command_ledger.get(target_command.command_id) is not None
        )

    def test_operator_universal_actions_read_model_filters_proofs(
        self, gateway_app, client
    ):
        committed = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-proof-index-1",
            idempotency_key="universal-proof-index-1",
            intent="llm_completion",
            payload={"body": "committed proof"},
        )
        blocked = gateway_app.state.command_ledger.create_command(
            tenant_id="t2",
            actor_id="u2",
            source="web",
            conversation_id="conversation-proof-index-2",
            idempotency_key="universal-proof-index-2",
            intent="llm_completion",
            payload={"body": "blocked proof"},
        )
        gateway_app.state.command_ledger.transition(
            committed.command_id,
            CommandState.DISPATCHED,
            detail={
                "cause": "universal_action_kernel_dispatched",
                "universal_action": {
                    "action_id": "uact-committed",
                    "blocked": False,
                    "block_reason": "",
                    "proof_hash": "proof-hash-committed",
                    "capability_id": "shell_command",
                    "dispatch_ledger_hash": "dispatch-ledger-committed",
                    "closure_state": "closed_allowed",
                    "reconciliation_ref": "reconciliation://uact-committed",
                    "memory_ref": "memory://uact-committed",
                    "whqr_replay_binding": {
                        "replay_ref": WHQR_REPLAY_REF,
                        "canonical_hash": WHQR_CANONICAL_HASH,
                        "semantics_hash": WHQR_SEMANTICS_HASH,
                        "version": "0.1.0",
                    },
                },
            },
        )
        gateway_app.state.command_ledger.transition(
            blocked.command_id,
            CommandState.REQUIRES_REVIEW,
            detail={
                "cause": "universal_action_kernel_blocked",
                "universal_action": {
                    "action_id": "uact-blocked",
                    "blocked": True,
                    "block_reason": "open_world_contradictions",
                    "proof_hash": "proof-hash-blocked",
                    "capability_id": "shell_command",
                    "dispatch_ledger_hash": "",
                    "closure_state": "closed_blocked",
                    "reconciliation_ref": "",
                    "memory_ref": "",
                    "whqr_replay_binding": {},
                },
            },
        )

        all_resp = client.get("/operator/universal-actions/read-model")
        blocked_resp = client.get("/operator/universal-actions/read-model?blocked=true")
        tenant_resp = client.get("/operator/universal-actions/read-model?tenant_id=t1")
        invalid_resp = client.get(
            "/operator/universal-actions/read-model?blocked=maybe"
        )

        assert all_resp.status_code == 200
        assert all_resp.json()["total"] == 2
        assert {
            item["proof_hash"] for item in all_resp.json()["universal_action_proofs"]
        } == {
            "proof-hash-committed",
            "proof-hash-blocked",
        }
        assert blocked_resp.status_code == 200
        assert blocked_resp.json()["count"] == 1
        assert blocked_resp.json()["universal_action_proofs"][0]["blocked"] is True
        assert (
            blocked_resp.json()["universal_action_proofs"][0]["block_reason"]
            == "open_world_contradictions"
        )
        assert tenant_resp.status_code == 200
        assert tenant_resp.json()["count"] == 1
        committed_row = tenant_resp.json()["universal_action_proofs"][0]
        assert committed_row["tenant_id"] == "t1"
        assert committed_row["closure_state"] == "closed_allowed"
        assert committed_row["reconciliation_ref"] == "reconciliation://uact-committed"
        assert committed_row["memory_ref"] == "memory://uact-committed"
        assert committed_row["whqr_replay_binding"] == {
            "replay_ref": WHQR_REPLAY_REF,
            "canonical_hash": WHQR_CANONICAL_HASH,
            "semantics_hash": WHQR_SEMANTICS_HASH,
            "version": "0.1.0",
        }
        assert committed_row["whqr_replay_ref"] == WHQR_REPLAY_REF
        assert invalid_resp.status_code == 400
        assert invalid_resp.json()["detail"] == "blocked must be true or false"

    def test_operator_universal_actions_console_renders_proof_table(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-proof-console",
            idempotency_key="universal-proof-console",
            intent="llm_completion",
            payload={"body": "console proof"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.REQUIRES_REVIEW,
            detail={
                "cause": "universal_action_kernel_blocked",
                "universal_action": {
                    "action_id": "uact-console",
                    "blocked": True,
                    "block_reason": "open_world_contradictions",
                    "proof_hash": "proof-hash-console",
                    "capability_id": "shell_command",
                    "dispatch_ledger_hash": "",
                    "closure_state": "closed_blocked",
                    "reconciliation_ref": "reconciliation://uact-console",
                    "memory_ref": "memory://uact-console",
                    "whqr_replay_binding": {
                        "replay_ref": WHQR_REPLAY_REF,
                        "canonical_hash": WHQR_CANONICAL_HASH,
                        "semantics_hash": WHQR_SEMANTICS_HASH,
                        "version": "0.1.0",
                    },
                },
            },
        )

        resp = client.get("/operator/universal-actions?blocked=true")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Mullu Universal Action Proofs" in resp.text
        assert "/operator/universal-actions/read-model" in resp.text
        assert command.command_id in resp.text
        assert "proof-hash-console" in resp.text
        assert "open_world_contradictions" in resp.text
        assert "shell_command" in resp.text
        assert "closed_blocked" in resp.text
        assert "reconciliation://uact-console" in resp.text
        assert "memory://uact-console" in resp.text
        assert WHQR_REPLAY_REF in resp.text

    def test_operator_receipt_viewer_read_model_groups_bounded_receipts(
        self, gateway_app, client
    ):
        command, certificate = _create_completed_receipt_viewer_command(
            gateway_app.state.command_ledger,
            idempotency_key="receipt-viewer-read-model",
        )

        resp = client.get("/operator/receipts/read-model?tenant_id=t1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_ref"] == (
            "urn:mullusi:schema:operator-receipt-viewer-read-model:1"
        )
        assert data["raw_message_exposed"] is False
        assert data["execution_allowed"] is False
        assert data["write_allowed"] is False
        assert data["governed"] is True
        assert data["count"] >= 1
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            data,
        ) == []
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        receipt_types = {receipt["receipt_type"] for receipt in row["receipts"]}
        assert set(row["receipt_types"]) == receipt_types
        assert row["task_status"] == "completed"
        assert row["receipt_count"] >= row["event_count"]
        assert "interpretation_receipt" in receipt_types
        assert "command_event" in receipt_types
        assert "worker_receipt" in receipt_types
        assert "delivery_receipt" in receipt_types
        assert "terminal_closure_certificate" in receipt_types
        delivery_receipt = next(
            receipt
            for receipt in row["receipts"]
            if receipt["receipt_type"] == "delivery_receipt"
        )
        assert delivery_receipt["status"] == "delivery_status_not_recorded"
        assert delivery_receipt["details"]["delivery_status_observed"] is False
        terminal_receipt = next(
            receipt
            for receipt in row["receipts"]
            if receipt["receipt_type"] == "terminal_closure_certificate"
        )
        assert terminal_receipt["receipt_id"] == certificate.certificate_id
        assert terminal_receipt["evidence_refs"]["evidence_refs"]
        assert "operator viewer raw body must stay hidden" not in json.dumps(
            data, sort_keys=True
        )

    def test_operator_receipt_viewer_projects_search_decision_receipts(
        self, gateway_app, client
    ):
        raw_query = "latest governance docs"
        receipt = build_search_decision_receipt(
            SearchDecisionRequest(
                tenant_id="t1",
                actor_id="u1",
                query=raw_query,
                generated_at="2026-06-17T12:00:00+00:00",
                budget_limit_units=2.0,
                max_result_count=3,
            )
        ).to_dict()
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-search-decision-receipt",
            idempotency_key="search-decision-receipt",
            intent="enterprise.knowledge_search",
            payload={
                "body": raw_query,
                "search_decision_receipt": receipt,
                "search_decision_receipt_id": receipt["receipt_id"],
            },
        )

        resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=search_decision_receipt"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            data,
        ) == []
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        search_receipt = row["receipts"][0]
        assert row["receipt_types"] == ["search_decision_receipt"]
        assert search_receipt["receipt_id"] == receipt["receipt_id"]
        assert search_receipt["receipt_hash"] == receipt["receipt_hash"]
        assert search_receipt["status"] == "allow_search"
        assert search_receipt["details"]["query_hash"] == receipt["query_hash"]
        assert search_receipt["details"]["freshness_state"] == "source_required"
        assert search_receipt["details"]["retrieval_authority"] == "evidence_only"
        assert search_receipt["details"]["retrieval_instruction_authority_allowed"] is False
        assert search_receipt["evidence_refs"]["query_hash"] == receipt["query_hash"]
        assert raw_query not in json.dumps(data, sort_keys=True)

    def test_operator_receipt_viewer_projects_search_decision_from_event_output(
        self, gateway_app, client
    ):
        receipt = build_search_decision_receipt(
            SearchDecisionRequest(
                tenant_id="t1",
                actor_id="u1",
                query="search docs",
                generated_at="2026-06-17T12:05:00+00:00",
                budget_limit_units=1.0,
                max_result_count=5,
            )
        ).to_dict()
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-search-decision-event",
            idempotency_key="search-decision-event",
            intent="enterprise.knowledge_search",
            payload={"body": "search docs"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.OBSERVED,
            output={"response": "bounded search result", "total_chunks_searched": 1},
            detail={
                "search_decision_receipt": receipt,
                "search_decision_receipt_id": receipt["receipt_id"],
            },
        )

        resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=search_decision_receipt&receipt_status=allow_search"
        )

        assert resp.status_code == 200
        data = resp.json()
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        search_receipt = row["receipts"][0]
        assert search_receipt["receipt_type"] == "search_decision_receipt"
        assert search_receipt["receipt_id"] == receipt["receipt_id"]
        assert search_receipt["evidence_refs"]["source_event_hash"]
        assert search_receipt["details"]["budget_state"] == "allowed"
        assert "search docs" not in json.dumps(data, sort_keys=True)

    def test_operator_receipt_viewer_projects_search_receipt_panel(
        self, gateway_app, client
    ):
        raw_query = "search receipt raw query must stay hidden"
        raw_excerpt = "retrieved excerpt must stay hidden"
        search_receipt = {
            "receipt_id": "search-receipt-viewerpanel1",
            "receipt_version": "search_receipt.v1",
            "search_decision_ref": "receipt://search-decision/search-decision-viewerpanel1",
            "request_id": "worker-request-viewer-panel",
            "tenant_id": "t1",
            "actor_id": "u1",
            "created_at": "2026-06-17T12:10:00+00:00",
            "solver_outcome": "SolvedVerified",
            "receipt_state": "EVIDENCE_AVAILABLE",
            "search_state": "LOCAL_SEARCH",
            "freshness_result": {
                "freshness_required": False,
                "freshness_status": "not_required",
                "current_info_claim_allowed": False,
                "max_age_seconds": None,
                "proof_state": "Pass",
                "rationale_refs": ["policy:foundation-mode:local-search-freshness"],
            },
            "source_plan_result": {
                "selected_sources": ["local_docs"],
                "attempted_sources": ["local_docs"],
                "tenant_scope_verified": True,
                "external_retrieval_performed": False,
                "connector_scope_ref": None,
                "rationale_refs": ["policy:foundation-mode:read-only-search-worker"],
            },
            "cache_result": {
                "state": "not_checked",
                "cache_key_ref": None,
                "tenant_scoped": True,
                "stale_cache_used": False,
            },
            "budget_result": {
                "state": "within_budget",
                "actual_cost_class": "none",
                "approval_ref": None,
                "proof_state": "Pass",
                "rationale_refs": ["worker-budget:zero-cost-local-search"],
            },
            "evidence_summary": {
                "evidence_count": 1,
                "citation_count": 1,
                "conflict_count": 0,
                "stale_source_count": 0,
                "retrieval_error_count": 0,
                "content_body_included": False,
            },
            "evidence_items": [
                {
                    "evidence_ref": "evidence://local-docs/viewerpanel1",
                    "source_type": "local_docs",
                    "source_ref": "docs/78_search_receipt_contract.md#L1",
                    "citation_ref": "citation://local-docs/viewerpanel1",
                    "observed_at": "2026-06-17T12:10:00+00:00",
                    "fresh_until": None,
                    "freshness_status": "not_required",
                    "trust_tier": "local_governed",
                    "content_hash_ref": "hash://sha256/viewerpanel1",
                    "content_body": None,
                }
            ],
            "citation_refs": ["citation://local-docs/viewerpanel1"],
            "conflict_refs": [],
            "stale_source_refs": [],
            "retrieval_errors": [],
            "retrieval_safety_result": {
                "retrieved_content_authority": "evidence_only",
                "prompt_injection_guard_applied": True,
                "prompt_injection_detected": False,
                "source_instruction_authority_granted": False,
                "tool_instruction_from_source_allowed": False,
                "policy_instruction_from_source_allowed": False,
                "private_source_scope_verified": True,
                "conflict_handling": "cite_conflict",
            },
            "governance_guards": {
                "execution_authority_granted": False,
                "connector_authority_granted": False,
                "answer_claim_authority_granted": False,
                "terminal_closure": False,
                "raw_secret_material_included": False,
                "retrieved_instruction_authority_granted": False,
                "mfidel_atomicity_preserved": True,
            },
            "receipt_envelope": {
                "uao_ref": "uao://worker-search/command-viewer-panel",
                "causal_decision_trace_ref": "trace://worker-search/viewer-panel",
                "receipt_ref": "receipt://search-receipt/search-receipt-viewerpanel1",
            },
            "evidence_refs": ["knowledge-search:receipt:viewerpanel1"],
            "metadata": {
                "raw_query_exposed": False,
                "source_excerpt_body_excluded_from_receipt": True,
            },
        }
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-search-receipt-panel",
            idempotency_key="search-receipt-panel",
            intent="enterprise.knowledge_search",
            payload={"body": raw_query},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.OBSERVED,
            output={"response": "bounded search result"},
            detail={
                "execution_result": {
                    "output": {
                        "search_receipt": search_receipt,
                        "search_receipt_hash": "search-receipt-hash-viewerpanel1",
                        "results": [{"excerpt": raw_excerpt}],
                    }
                }
            },
        )

        resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=search_receipt&receipt_status=EVIDENCE_AVAILABLE"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            data,
        ) == []
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        receipt = row["receipts"][0]
        serialized = json.dumps(data, sort_keys=True)
        assert row["receipt_types"] == ["search_receipt"]
        assert receipt["receipt_type"] == "search_receipt"
        assert receipt["receipt_hash"] == "search-receipt-hash-viewerpanel1"
        assert receipt["details"]["evidence_summary"]["evidence_count"] == 1
        assert receipt["details"]["evidence_item_refs"][0]["citation_ref"] == (
            "citation://local-docs/viewerpanel1"
        )
        assert (
            receipt["details"]["evidence_item_refs"][0]["content_body_included"]
            is False
        )
        assert receipt["details"]["raw_query_exposed"] is False
        assert receipt["details"]["source_content_body_exposed"] is False
        assert raw_query not in serialized
        assert raw_excerpt not in serialized

    def test_operator_receipt_viewer_projects_worker_failure_drilldown(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-worker-failure-receipt",
            idempotency_key="worker-failure-receipt",
            intent="repository.inspect_read_only",
            payload={"body": "worker failure raw body must stay hidden"},
        )
        failure_receipt = _worker_failure_receipt_payload(command.command_id)
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.DENIED,
            detail={
                "cause": "worker_partial_completion",
                "worker_failure_receipt": failure_receipt,
                "worker_failure_receipt_id": failure_receipt["receipt_id"],
            },
        )

        resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=worker_failure_receipt"
            "&receipt_status=partial_completion"
        )
        current_resp = client.get("/operator/current-task/read-model?tenant_id=t1")

        assert resp.status_code == 200
        data = resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            data,
        ) == []
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        worker_failure = row["receipts"][0]
        assert row["receipt_types"] == ["worker_failure_receipt"]
        assert worker_failure["receipt_id"] == failure_receipt["receipt_id"]
        assert worker_failure["receipt_hash"] == failure_receipt["metadata"]["failure_hash"]
        assert worker_failure["status"] == "partial_completion"
        assert worker_failure["details"]["worker_dispatch_ref"] == (
            failure_receipt["worker_dispatch_ref"]
        )
        assert worker_failure["details"]["recovery_action_refs"] == [
            "recovery:operator-review"
        ]
        assert worker_failure["evidence_refs"]["source_receipt_hash"] == (
            failure_receipt["metadata"]["source_receipt_hash"]
        )
        assert worker_failure["evidence_refs"]["source_event_hash"]

        assert current_resp.status_code == 200
        current_data = current_resp.json()
        assert _validate_schema_instance(
            _load_schema(CURRENT_TASK_READ_MODEL_SCHEMA),
            current_data,
        ) == []
        task = next(
            item
            for item in current_data["tasks"]
            if item["command_id"] == command.command_id
        )
        assert task["worker_failure_receipt_id"] == failure_receipt["receipt_id"]
        assert task["worker_failure_state"] == "partial_completion"
        assert task["worker_failure_recovery_action"] == "safe_halt"
        assert "worker failure raw body must stay hidden" not in json.dumps(
            {"receipt": data, "current_task": current_data},
            sort_keys=True,
        )

    def test_operator_receipt_viewer_filters_type_status_task_and_search(
        self, gateway_app, client
    ):
        completed, _certificate = _create_completed_receipt_viewer_command(
            gateway_app.state.command_ledger,
            idempotency_key="receipt-filter-completed",
        )
        blocked = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-receipt-filter-blocked",
            idempotency_key="receipt-filter-blocked",
            intent="llm_completion",
            payload={"body": "receipt filter blocked body"},
        )
        gateway_app.state.command_ledger.transition(
            blocked.command_id,
            CommandState.DENIED,
            detail={"cause": "filter_denied"},
        )

        type_resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=delivery_receipt"
        )
        status_resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_status=denied"
        )
        task_resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1&task_status=blocked"
        )
        search_resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&search=terminal_closure_certificate"
        )
        html_resp = client.get(
            "/operator/receipts?tenant_id=t1"
            "&receipt_type=delivery_receipt&task_status=completed"
            "&search=delivery_receipt"
        )
        invalid_type_resp = client.get(
            "/operator/receipts/read-model?receipt_type=unknown_receipt"
        )
        invalid_task_resp = client.get(
            "/operator/receipts/read-model?task_status=unknown"
        )
        overlong_search_resp = client.get(
            "/operator/receipts/read-model?search=" + ("x" * 129)
        )

        assert type_resp.status_code == 200
        type_data = type_resp.json()
        assert type_data["receipt_type_filter"] == "delivery_receipt"
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            type_data,
        ) == []
        type_rows = {
            row["command_id"]: row for row in type_data["receipt_groups"]
        }
        assert completed.command_id in type_rows
        assert type_rows[completed.command_id]["receipt_types"] == [
            "delivery_receipt"
        ]
        assert type_rows[completed.command_id]["receipt_count"] == 1
        assert all(
            receipt["receipt_type"] == "delivery_receipt"
            for receipt in type_rows[completed.command_id]["receipts"]
        )

        assert status_resp.status_code == 200
        status_data = status_resp.json()
        status_rows = {
            row["command_id"]: row for row in status_data["receipt_groups"]
        }
        assert blocked.command_id in status_rows
        assert completed.command_id not in status_rows
        assert all(
            receipt["status"] == "denied"
            for receipt in status_rows[blocked.command_id]["receipts"]
        )

        assert task_resp.status_code == 200
        task_data = task_resp.json()
        task_rows = {
            row["command_id"]: row for row in task_data["receipt_groups"]
        }
        assert blocked.command_id in task_rows
        assert completed.command_id not in task_rows
        assert task_rows[blocked.command_id]["task_status"] == "blocked"

        assert search_resp.status_code == 200
        search_data = search_resp.json()
        search_rows = {
            row["command_id"]: row for row in search_data["receipt_groups"]
        }
        assert completed.command_id in search_rows
        assert search_data["search_filter"] == "terminal_closure_certificate"

        assert html_resp.status_code == 200
        assert "Receipt Filters" in html_resp.text
        assert 'name="receipt_type"' in html_resp.text
        assert 'value="delivery_receipt" selected' in html_resp.text
        assert 'name="task_status"' in html_resp.text
        assert 'value="completed" selected' in html_resp.text
        assert "receipt filter blocked body" not in json.dumps(
            {
                "type": type_data,
                "status": status_data,
                "task": task_data,
                "search": search_data,
                "html": html_resp.text,
            },
            sort_keys=True,
        )
        assert invalid_type_resp.status_code == 400
        assert "receipt_type must be one of" in invalid_type_resp.json()["detail"]
        assert invalid_task_resp.status_code == 400
        assert "task_status must be one of" in invalid_task_resp.json()["detail"]
        assert overlong_search_resp.status_code == 400
        assert overlong_search_resp.json()["detail"] == (
            "search must be 128 characters or fewer"
        )

    def test_operator_receipt_viewer_separates_execution_and_delivery_status(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-delivery-separated",
            idempotency_key="delivery-separated",
            intent="llm_completion",
            payload={"body": "delivery separated raw body"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.RESPONDED,
            detail={"success_claim": False},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.RESPONSE_EVIDENCE_CLOSED,
            detail={
                "delivery_status": "failed",
                "delivery_error_type": "adapter_exception",
                "delivery_succeeded": False,
                "delivery_attempted": True,
                "execution_status": "terminal_certified",
                "execution_delivery_separated": True,
                "terminal_certificate_id": "terminal-delivery-separated",
            },
        )

        resp = client.get(
            "/operator/receipts/read-model?tenant_id=t1"
            "&receipt_type=delivery_receipt&receipt_status=failed"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            data,
        ) == []
        row = next(
            item
            for item in data["receipt_groups"]
            if item["command_id"] == command.command_id
        )
        delivery_receipt = row["receipts"][0]
        assert delivery_receipt["status"] == "failed"
        assert delivery_receipt["details"]["execution_status"] == "terminal_certified"
        assert delivery_receipt["details"]["delivery_status"] == "failed"
        assert delivery_receipt["details"]["delivery_error_type"] == "adapter_exception"
        assert delivery_receipt["details"]["delivery_succeeded"] is False
        assert delivery_receipt["details"]["delivery_attempted"] is True
        assert delivery_receipt["details"]["execution_delivery_separated"] is True
        assert delivery_receipt["evidence_refs"]["delivery_event_hash"]

    def test_operator_approval_history_links_receipts_and_current_task(
        self, gateway_app, client
    ):
        pending_preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs approval-history-secret-12 and "
                    "schedule review approval-history-secret-12"
                ),
            },
        )
        pending_preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            pending_preview.text,
        ).group(1)
        pending_approved = client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": pending_preview_id},
        )
        waiting_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=waiting_for_approval"
        )
        waiting_task = waiting_resp.json()["tasks"][0]
        request_id = waiting_task["approval_request_id"]
        command_id = waiting_task["command_id"]

        history_resp = client.get(
            "/operator/approvals/read-model?tenant_id=t1&status=pending"
        )
        history_data = history_resp.json()
        html_resp = client.get(
            f"/operator/approvals?tenant_id=t1&status=pending&search={request_id}"
        )
        detail_resp = client.get(
            f"/operator/approvals/{request_id}?tenant_id=t1"
        )
        receipt_detail_resp = client.get(
            f"/operator/receipts/{command_id}?tenant_id=t1"
        )
        invalid_status_resp = client.get(
            "/operator/approvals/read-model?status=waiting"
        )
        overlong_search_resp = client.get(
            "/operator/approvals/read-model?search=" + ("x" * 129)
        )

        assert pending_preview.status_code == 200
        assert pending_approved.status_code == 200
        assert history_resp.status_code == 200
        assert _validate_schema_instance(
            _load_schema(OPERATOR_APPROVAL_HISTORY_READ_MODEL_SCHEMA),
            history_data,
        ) == []
        assert history_data["status_filter"] == "pending"
        assert history_data["status_counts"]["pending"] == 1
        assert history_data["approvals"][0]["approval_request_id"] == request_id
        assert history_data["approvals"][0]["status"] == "pending"
        assert history_data["approvals"][0]["receipt_href"] == (
            f"/operator/receipts/{command_id}?tenant_id=t1"
        )
        assert history_data["approvals"][0]["current_task_href"] == (
            "/operator/current-task?tenant_id=t1&status=waiting_for_approval"
        )
        assert html_resp.status_code == 200
        assert "Mullu Approval History" in html_resp.text
        assert "Approval Filters" in html_resp.text
        assert f"/operator/approvals/{request_id}?tenant_id=t1" in html_resp.text
        assert detail_resp.status_code == 200
        assert "Mullu Approval Detail" in detail_resp.text
        assert receipt_detail_resp.status_code == 200
        assert f"/operator/approvals/{request_id}" in receipt_detail_resp.text
        assert invalid_status_resp.status_code == 400
        assert "status must be one of" in invalid_status_resp.json()["detail"]
        assert overlong_search_resp.status_code == 400
        assert overlong_search_resp.json()["detail"] == (
            "search must be 128 characters or fewer"
        )
        assert "approval-history-secret-12" not in json.dumps(
            {
                "history": history_data,
                "html": html_resp.text,
                "detail": detail_resp.text,
                "receipt": receipt_detail_resp.text,
            },
            sort_keys=True,
        )

        recovered = client.post(
            "/operator/current-task/approval",
            data={"request_id": request_id, "decision": "approve"},
        )
        approved_history_resp = client.get(
            f"/operator/approvals/read-model?tenant_id=t1&request_id={request_id}"
        )

        assert recovered.status_code == 200
        assert "approval_approved_plan_recovered" in recovered.text
        approved_history = approved_history_resp.json()
        assert approved_history["count"] == 1
        assert approved_history["approvals"][0]["status"] == "approved"
        assert approved_history["approvals"][0]["resolved_at"]
        assert approved_history["approvals"][0]["current_task_href"] == (
            "/operator/current-task?tenant_id=t1&status=completed"
        )

        deny_preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs approval-history-secret-13 and "
                    "schedule review approval-history-secret-13"
                ),
            },
        )
        deny_preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            deny_preview.text,
        ).group(1)
        client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": deny_preview_id},
        )
        deny_waiting = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=waiting_for_approval"
        )
        deny_request_id = deny_waiting.json()["tasks"][0]["approval_request_id"]
        denied = client.post(
            "/operator/current-task/approval",
            data={"request_id": deny_request_id, "decision": "deny"},
        )
        denied_history_resp = client.get(
            f"/operator/approvals/read-model?tenant_id=t1&request_id={deny_request_id}"
        )

        assert denied.status_code == 200
        assert "approval_denied" in denied.text
        denied_history = denied_history_resp.json()
        assert denied_history["count"] == 1
        assert denied_history["approvals"][0]["status"] == "denied"
        assert denied_history["approvals"][0]["resolved_at"]
        assert "approval-history-secret-13" not in json.dumps(
            denied_history,
            sort_keys=True,
        )

    def test_operator_current_task_read_model_classifies_waiting_blocked_and_completed(
        self, gateway_app, client
    ):
        waiting = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-current-task-waiting",
            idempotency_key="current-task-waiting",
            intent="llm_completion",
            payload={"body": "waiting raw body"},
        )
        blocked = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-current-task-blocked",
            idempotency_key="current-task-blocked",
            intent="llm_completion",
            payload={"body": "blocked raw body"},
        )
        completed, certificate = _create_completed_receipt_viewer_command(
            gateway_app.state.command_ledger,
            idempotency_key="current-task-completed",
        )
        awaiting_evidence = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-current-task-awaiting-evidence",
            idempotency_key="current-task-awaiting-evidence",
            intent="llm_completion",
            payload={"body": "awaiting evidence raw body"},
        )
        gateway_app.state.command_ledger.transition(
            waiting.command_id,
            CommandState.PENDING_APPROVAL,
            detail={"cause": "operator_approval_required"},
        )
        gateway_app.state.command_ledger.transition(
            blocked.command_id,
            CommandState.DENIED,
            detail={"cause": "policy_denied"},
        )
        gateway_app.state.command_ledger.transition(
            awaiting_evidence.command_id,
            CommandState.RESPONDED,
            detail={"cause": "response_emitted_without_terminal_certificate"},
        )

        resp = client.get("/operator/current-task/read-model?tenant_id=t1")
        blocked_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=blocked"
        )
        invalid_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=unknown"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_ref"] == "urn:mullusi:schema:current-task-read-model:1"
        assert data["raw_message_exposed"] is False
        assert data["execution_allowed"] is False
        assert data["write_allowed"] is False
        assert data["governed"] is True
        assert _validate_schema_instance(
            _load_schema(CURRENT_TASK_READ_MODEL_SCHEMA),
            data,
        ) == []
        tasks = {task["command_id"]: task for task in data["tasks"]}
        assert tasks[waiting.command_id]["task_status"] == "waiting_for_approval"
        assert tasks[waiting.command_id]["response_state"] == "waiting_for_approval"
        assert tasks[waiting.command_id]["response_evidence_state"] == "approval_pending"
        assert tasks[waiting.command_id]["response_claim_allowed"] is False
        assert tasks[waiting.command_id]["response_evidence_refs"] == []
        assert tasks[waiting.command_id]["response_blocker"] == "approval_required"
        assert tasks[waiting.command_id]["waiting_for"] == "operator_approval"
        assert tasks[waiting.command_id]["next_action"] == "resolve_approval"
        assert tasks[waiting.command_id]["goal_intake_preview_id"] == ""
        assert tasks[waiting.command_id]["goal_hash"] == ""
        assert tasks[waiting.command_id]["plan_id"] == ""
        assert tasks[waiting.command_id]["plan_step_id"] == ""
        assert tasks[waiting.command_id]["approval_request_id"] == ""
        assert tasks[waiting.command_id]["approval_recovery_available"] is False
        assert tasks[blocked.command_id]["task_status"] == "blocked"
        assert tasks[blocked.command_id]["response_state"] == "blocked"
        assert tasks[blocked.command_id]["response_evidence_state"] == (
            "blocked_with_receipt"
        )
        assert tasks[blocked.command_id]["response_claim_allowed"] is False
        assert len(tasks[blocked.command_id]["response_evidence_refs"]) == 1
        assert tasks[blocked.command_id]["response_evidence_refs"][0].startswith(
            "receipt://denial_receipt/denial:evt-"
        )
        assert (
            tasks[blocked.command_id]["response_blocker"]
            == "explicit_blocker_receipt_required"
        )
        assert tasks[blocked.command_id]["task_blocked"] is True
        assert (
            tasks[blocked.command_id]["next_action"]
            == "inspect_denial_or_block_receipts"
        )
        assert tasks[completed.command_id]["task_status"] == "completed"
        assert tasks[completed.command_id]["response_state"] == "completed_verified"
        assert tasks[completed.command_id]["response_evidence_state"] == (
            "terminal_verified"
        )
        assert tasks[completed.command_id]["response_claim_allowed"] is True
        assert (
            tasks[completed.command_id]["response_terminal_certificate_id"]
            == certificate.certificate_id
        )
        assert tasks[completed.command_id]["response_evidence_refs"] == [
            f"terminal-certificate://{certificate.certificate_id}"
        ]
        assert tasks[completed.command_id]["response_blocker"] == ""
        assert tasks[completed.command_id]["task_terminal"] is True
        assert tasks[awaiting_evidence.command_id]["task_status"] == "completed"
        assert (
            tasks[awaiting_evidence.command_id]["response_state"]
            == "awaiting_terminal_evidence"
        )
        assert tasks[awaiting_evidence.command_id]["response_evidence_state"] == (
            "terminal_certificate_missing"
        )
        assert tasks[awaiting_evidence.command_id]["response_claim_allowed"] is False
        assert tasks[awaiting_evidence.command_id]["response_evidence_refs"] == []
        assert (
            tasks[awaiting_evidence.command_id]["response_blocker"]
            == "terminal_certificate_missing"
        )
        assert tasks[awaiting_evidence.command_id]["task_terminal"] is False
        assert data["status_counts"]["waiting_for_approval"] >= 1
        assert data["status_counts"]["blocked"] >= 1
        assert data["status_counts"]["completed"] >= 2
        assert "waiting raw body" not in json.dumps(data, sort_keys=True)
        assert "blocked raw body" not in json.dumps(data, sort_keys=True)
        assert "awaiting evidence raw body" not in json.dumps(data, sort_keys=True)
        assert blocked_resp.status_code == 200
        assert blocked_resp.json()["count"] == 1
        assert blocked_resp.json()["tasks"][0]["command_id"] == blocked.command_id
        assert invalid_resp.status_code == 400
        assert "status must be one of" in invalid_resp.json()["detail"]

    def test_operator_receipt_and_current_task_consoles_render_bounded_tables(
        self, gateway_app, client
    ):
        command = gateway_app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-receipt-current-html",
            idempotency_key="receipt-current-html",
            intent="llm_completion",
            payload={"body": "html raw body must stay hidden"},
        )
        gateway_app.state.command_ledger.transition(
            command.command_id,
            CommandState.PENDING_APPROVAL,
            detail={"cause": "operator_approval_required"},
        )

        receipts_resp = client.get("/operator/receipts?tenant_id=t1")
        detail_resp = client.get(
            f"/operator/receipts/{command.command_id}?tenant_id=t1"
        )
        missing_detail_resp = client.get(
            "/operator/receipts/cmd-missing-receipt-detail?tenant_id=t1"
        )
        current_resp = client.get("/operator/current-task?tenant_id=t1")

        assert receipts_resp.status_code == 200
        assert "text/html" in receipts_resp.headers["content-type"]
        assert "Mullu Operator Receipt Viewer" in receipts_resp.text
        assert "/operator/receipts/read-model" in receipts_resp.text
        assert command.command_id in receipts_resp.text
        assert (
            f"/operator/receipts/{command.command_id}?tenant_id=t1"
            in receipts_resp.text
        )
        assert "html raw body must stay hidden" not in receipts_resp.text
        assert detail_resp.status_code == 200
        assert "text/html" in detail_resp.headers["content-type"]
        assert "Mullu Receipt Detail" in detail_resp.text
        assert command.command_id in detail_resp.text
        assert "command_event" in detail_resp.text
        assert "details" in detail_resp.text
        assert "evidence_refs" in detail_resp.text
        assert "html raw body must stay hidden" not in detail_resp.text
        assert missing_detail_resp.status_code == 404
        assert missing_detail_resp.json()["detail"] == (
            "command receipt group not found"
        )
        assert current_resp.status_code == 200
        assert "text/html" in current_resp.headers["content-type"]
        assert "Mullu Current Task State" in current_resp.text
        assert "/operator/current-task/read-model" in current_resp.text
        assert command.command_id in current_resp.text
        assert "waiting_for_approval" in current_resp.text
        assert "html raw body must stay hidden" not in current_resp.text

    def test_operator_goal_intake_previews_plan_without_command_write(
        self, gateway_app, client
    ):
        initial_commands = gateway_app.state.command_ledger.summary()["commands"]
        initial_plan_witnesses = gateway_app.state.plan_ledger.read_model()[
            "plan_witness_count"
        ]

        console_resp = client.get("/operator/goal-intake")
        preview_resp = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs secret-token-123 and send notification "
                    "to team secret-token-123"
                ),
            },
        )
        blocked_resp = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": "hello secret-token-456",
            },
        )

        assert console_resp.status_code == 200
        assert "text/html" in console_resp.headers["content-type"]
        assert "Mullu Goal Intake" in console_resp.text
        assert 'action="/operator/goal-intake/preview"' in console_resp.text
        assert "/operator/current-task" in console_resp.text
        assert preview_resp.status_code == 200
        assert "text/html" in preview_resp.headers["content-type"]
        assert "preview_ready" in preview_resp.text
        assert "enterprise.knowledge_search" in preview_resp.text
        assert "enterprise.notification_send" in preview_resp.text
        assert "external_webhook" in preview_resp.text
        assert "Budget Required" in preview_resp.text
        assert "Execution Allowed" in preview_resp.text
        assert "/operator/goal-intake/approve" in preview_resp.text
        assert "/operator/goal-intake/deny" in preview_resp.text
        assert "secret-token-123" not in preview_resp.text
        assert blocked_resp.status_code == 200
        assert "goal_not_compilable" in blocked_resp.text
        assert "secret-token-456" not in blocked_resp.text
        assert gateway_app.state.command_ledger.summary()["commands"] == initial_commands
        assert (
            gateway_app.state.plan_ledger.read_model()["plan_witness_count"]
            == initial_plan_witnesses
        )

    def test_operator_goal_intake_approve_and_deny_are_explicit_handoffs(
        self, gateway_app, client
    ):
        initial_commands = gateway_app.state.command_ledger.summary()["commands"]
        initial_witnesses = gateway_app.state.plan_ledger.read_model()[
            "plan_witness_count"
        ]

        deny_preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": "search knowledge docs and send notification to team deny-secret-1",
            },
        )
        deny_preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            deny_preview.text,
        ).group(1)
        denied = client.post(
            "/operator/goal-intake/deny",
            data={"preview_id": deny_preview_id},
        )

        assert denied.status_code == 200
        assert "denied" in denied.text
        assert "operator_denied" in denied.text
        assert "deny-secret-1" not in denied.text
        assert gateway_app.state.command_ledger.summary()["commands"] == initial_commands
        assert (
            gateway_app.state.plan_ledger.read_model()["plan_witness_count"]
            == initial_witnesses
        )

        approve_preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": (
                    "search knowledge docs approve-secret-2 and send notification "
                    "to team approve-secret-2"
                ),
            },
        )
        approve_preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            approve_preview.text,
        ).group(1)
        approved = client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": approve_preview_id},
        )
        repeated = client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": approve_preview_id},
        )

        assert approved.status_code == 200
        assert "handoff_submitted" in approved.text
        assert "approved" in approved.text
        assert "operator_approved" in approved.text
        assert "plan_id" in approved.text
        assert "approve-secret-2" not in approved.text
        assert gateway_app.state.command_ledger.summary()["commands"] > initial_commands
        assert (
            gateway_app.state.plan_ledger.read_model()["plan_witness_count"]
            > initial_witnesses
        )
        assert repeated.status_code == 200
        assert "preview_already_decided" in repeated.text
        assert "approve-secret-2" not in repeated.text

    def test_operator_goal_intake_current_task_binding_and_approval_recovery(
        self, gateway_app, client
    ):
        goal = (
            "search knowledge docs current-task-secret-3 and schedule review "
            "current-task-secret-3"
        )
        preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": goal,
            },
        )
        preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            preview.text,
        ).group(1)
        approved = client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": preview_id},
        )

        waiting_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=waiting_for_approval"
        )
        waiting_html = client.get(
            "/operator/current-task?tenant_id=t1&status=waiting_for_approval"
        )

        assert preview.status_code == 200
        assert approved.status_code == 200
        assert "handoff_submitted" in approved.text
        assert waiting_resp.status_code == 200
        waiting_data = waiting_resp.json()
        assert _validate_schema_instance(
            _load_schema(CURRENT_TASK_READ_MODEL_SCHEMA),
            waiting_data,
        ) == []
        assert waiting_data["count"] == 1
        waiting_task = waiting_data["tasks"][0]
        assert waiting_task["source"] == "operator_goal_intake"
        assert waiting_task["goal_intake_preview_id"] == preview_id
        assert waiting_task["goal_hash"]
        assert waiting_task["plan_id"].startswith("plan-")
        assert waiting_task["plan_step_id"] == "step-2"
        assert waiting_task["approval_request_id"].startswith("apr-")
        assert waiting_task["approval_recovery_available"] is True
        assert "current-task-secret-3" not in json.dumps(
            waiting_data,
            sort_keys=True,
        )
        assert waiting_html.status_code == 200
        assert 'action="/operator/current-task/approval"' in waiting_html.text
        assert 'value="approve"' in waiting_html.text
        assert 'value="deny"' in waiting_html.text
        assert waiting_task["approval_request_id"] in waiting_html.text
        assert "current-task-secret-3" not in waiting_html.text

        recovered = client.post(
            "/operator/current-task/approval",
            data={
                "request_id": waiting_task["approval_request_id"],
                "decision": "approve",
            },
        )
        closure_resp = client.get(
            f"/capability-plans/{waiting_task['plan_id']}/closure"
        )
        completed_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=completed"
        )

        assert recovered.status_code == 200
        assert "approval_approved_plan_recovered" in recovered.text
        assert "current-task-secret-3" not in recovered.text
        assert closure_resp.status_code == 200
        assert closure_resp.json()["plan_id"] == waiting_task["plan_id"]
        assert closure_resp.json()["plan_terminal_certificate"][
            "certificate_id"
        ].startswith("plan-cert-")
        completed_tasks = {
            task["command_id"]: task for task in completed_resp.json()["tasks"]
        }
        assert waiting_task["command_id"] in completed_tasks
        assert (
            completed_tasks[waiting_task["command_id"]][
                "approval_recovery_available"
            ]
            is False
        )
        assert "current-task-secret-3" not in json.dumps(
            completed_resp.json(),
            sort_keys=True,
        )

    def test_operator_receipt_viewer_derives_plan_approval_worker_and_denial_receipts(
        self, gateway_app, client
    ):
        goal = (
            "search knowledge docs receipt-secret-7 and schedule review "
            "receipt-secret-7"
        )
        preview = client.post(
            "/operator/goal-intake/preview",
            data={
                "tenant_id": "t1",
                "identity_id": "u1",
                "channel": "web",
                "sender_id": "web-user",
                "goal": goal,
            },
        )
        preview_id = re.search(
            r'name="preview_id" value="([^"]+)"',
            preview.text,
        ).group(1)
        approved = client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": preview_id},
        )
        waiting_resp = client.get(
            "/operator/current-task/read-model?tenant_id=t1&status=waiting_for_approval"
        )
        waiting_task = waiting_resp.json()["tasks"][0]
        receipts_resp = client.get(
            "/operator/receipts/read-model"
            f"?tenant_id=t1&command_id={waiting_task['command_id']}"
        )

        assert preview.status_code == 200
        assert approved.status_code == 200
        assert receipts_resp.status_code == 200
        receipt_data = receipts_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            receipt_data,
        ) == []
        assert receipt_data["count"] == 1
        row = receipt_data["receipt_groups"][0]
        receipt_types = {receipt["receipt_type"] for receipt in row["receipts"]}
        assert set(row["receipt_types"]) == receipt_types
        assert {
            "plan_step_receipt",
            "approval_receipt",
            "worker_receipt",
            "command_event",
        }.issubset(receipt_types)
        assert "denial_receipt" not in receipt_types

        plan_receipt = next(
            receipt
            for receipt in row["receipts"]
            if receipt["receipt_type"] == "plan_step_receipt"
        )
        approval_receipt = next(
            receipt
            for receipt in row["receipts"]
            if receipt["receipt_type"] == "approval_receipt"
        )
        worker_receipt = next(
            receipt
            for receipt in row["receipts"]
            if receipt["receipt_type"] == "worker_receipt"
        )
        assert plan_receipt["details"]["plan_id"] == waiting_task["plan_id"]
        assert plan_receipt["details"]["plan_step_id"] == "step-2"
        assert plan_receipt["details"]["goal_intake_preview_id"] == preview_id
        assert plan_receipt["details"]["goal_hash_present"] is True
        assert (
            plan_receipt["evidence_refs"]["goal_intake_preview_id"]
            == preview_id
        )
        assert approval_receipt["status"] == "pending"
        assert (
            approval_receipt["details"]["approval_request_id"]
            == waiting_task["approval_request_id"]
        )
        assert approval_receipt["evidence_refs"]["approval_request_id"].startswith(
            "apr-"
        )
        assert worker_receipt["details"]["capability_id"]
        assert worker_receipt["details"]["param_names"]
        assert worker_receipt["details"]["params_hash"]
        assert "receipt-secret-7" not in json.dumps(receipt_data, sort_keys=True)

        denied = client.post(
            "/operator/current-task/approval",
            data={
                "request_id": waiting_task["approval_request_id"],
                "decision": "deny",
            },
        )
        denied_receipts_resp = client.get(
            "/operator/receipts/read-model"
            f"?tenant_id=t1&command_id={waiting_task['command_id']}"
        )

        assert denied.status_code == 200
        assert "approval_denied" in denied.text
        denied_data = denied_receipts_resp.json()
        assert _validate_schema_instance(
            _load_schema(OPERATOR_RECEIPT_VIEWER_READ_MODEL_SCHEMA),
            denied_data,
        ) == []
        denied_row = denied_data["receipt_groups"][0]
        denied_receipt_types = {
            receipt["receipt_type"] for receipt in denied_row["receipts"]
        }
        denied_approval = next(
            receipt
            for receipt in denied_row["receipts"]
            if receipt["receipt_type"] == "approval_receipt"
        )
        denial_receipt = next(
            receipt
            for receipt in denied_row["receipts"]
            if receipt["receipt_type"] == "denial_receipt"
        )
        assert "denial_receipt" in denied_receipt_types
        assert denied_approval["status"] == "denied"
        assert (
            denial_receipt["evidence_refs"]["approval_request_id"]
            == waiting_task["approval_request_id"]
        )
        assert denied_row["task_status"] == "blocked"
        assert "receipt-secret-7" not in json.dumps(denied_data, sort_keys=True)

    def test_operator_receipt_viewer_requires_operator_authority_in_production(
        self, monkeypatch
    ):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
        monkeypatch.setenv("MULLU_AUTHORITY_OPERATOR_SECRET", "authority-secret")
        app = create_gateway_app(platform=StubPlatform())
        local_client = TestClient(app)
        command = app.state.command_ledger.create_command(
            tenant_id="t1",
            actor_id="u1",
            source="web",
            conversation_id="conversation-receipt-production",
            idempotency_key="receipt-viewer-production",
            intent="llm_completion",
            payload={"body": "production receipt body"},
        )

        denied_receipts = local_client.get("/operator/receipts/read-model")
        denied_receipt_detail = local_client.get(
            f"/operator/receipts/{command.command_id}"
        )
        denied_approvals = local_client.get("/operator/approvals/read-model")
        denied_approval_detail = local_client.get(
            "/operator/approvals/apr-prod-denied"
        )
        denied_plan_review = local_client.get("/operator/plan-review/read-model")
        denied_plan_review_detail = local_client.get("/operator/plan-review/plan-prod")
        denied_current = local_client.get("/operator/current-task/read-model")
        denied_current_approval = local_client.post(
            "/operator/current-task/approval",
            data={"request_id": "apr-prod-denied", "decision": "approve"},
        )
        denied_goal_intake = local_client.get("/operator/goal-intake")
        denied_goal_approve = local_client.post(
            "/operator/goal-intake/approve",
            data={"preview_id": "preview-prod-denied"},
        )
        denied_goal_deny = local_client.post(
            "/operator/goal-intake/deny",
            data={"preview_id": "preview-prod-denied"},
        )
        allowed_receipts = local_client.get(
            "/operator/receipts/read-model",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_receipt_detail = local_client.get(
            f"/operator/receipts/{command.command_id}",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_approvals = local_client.get(
            "/operator/approvals/read-model",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_approval_detail = local_client.get(
            "/operator/approvals/apr-prod-denied",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_plan_review = local_client.get(
            "/operator/plan-review/read-model",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_plan_review_detail = local_client.get(
            "/operator/plan-review/plan-prod",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_current = local_client.get(
            "/operator/current-task/read-model",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )
        allowed_goal_intake = local_client.get(
            "/operator/goal-intake",
            headers={"X-Mullu-Authority-Secret": "authority-secret"},
        )

        assert denied_receipts.status_code == 403
        assert denied_receipt_detail.status_code == 403
        assert denied_approvals.status_code == 403
        assert denied_approval_detail.status_code == 403
        assert denied_plan_review.status_code == 403
        assert denied_plan_review_detail.status_code == 403
        assert denied_current.status_code == 403
        assert denied_current_approval.status_code == 403
        assert denied_goal_intake.status_code == 403
        assert denied_goal_approve.status_code == 403
        assert denied_goal_deny.status_code == 403
        assert denied_receipts.json()["detail"] == (
            "Authority operator access not authorized"
        )
        assert allowed_receipts.status_code == 200
        assert allowed_receipt_detail.status_code == 200
        assert "Mullu Receipt Detail" in allowed_receipt_detail.text
        assert allowed_approvals.status_code == 200
        assert allowed_approval_detail.status_code == 404
        assert allowed_approval_detail.json()["detail"] == (
            "approval history not found"
        )
        assert allowed_plan_review.status_code == 200
        assert allowed_plan_review_detail.status_code == 404
        assert allowed_plan_review_detail.json()["detail"] == (
            "plan review history not found"
        )
        assert allowed_current.status_code == 200
        assert allowed_goal_intake.status_code == 200
        assert "Mullu Goal Intake" in allowed_goal_intake.text
        assert allowed_receipts.json()["receipt_groups"][0]["command_id"] == (
            command.command_id
        )
        assert allowed_current.json()["tasks"][0]["command_id"] == command.command_id
        assert "production receipt body" not in json.dumps(
            allowed_receipts.json(), sort_keys=True
        )
        assert "production receipt body" not in allowed_receipt_detail.text
        assert "production receipt body" not in json.dumps(
            allowed_current.json(), sort_keys=True
        )

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
        assert data["anchor_present"] is True
        assert data["anchor_id"] == anchor.anchor_id
        assert data["event_count"] > 0
        assert data["signature"].startswith("hmac-sha256:")
        assert data["governed"] is True
        assert _validate_schema_instance(_load_schema(LATEST_ANCHOR_SCHEMA), data) == []

    def test_latest_anchor_read_model_reports_absent_anchor(self, client):
        resp = client.get("/anchors/latest")

        assert resp.status_code == 200
        data = resp.json()
        assert data["anchor_present"] is False
        assert data["anchor_id"] == ""
        assert data["event_count"] == 0
        assert data["governed"] is True
        assert _validate_schema_instance(_load_schema(LATEST_ANCHOR_SCHEMA), data) == []
