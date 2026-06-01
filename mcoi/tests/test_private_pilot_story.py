"""Purpose: verify the read-only governed private pilot story.

Governance scope: OrgOS request, UAO envelope, governor-chain cohesion, SDLC
gate evidence, receipt closure, and dashboard view projection.
Dependencies: private pilot story core, workflow runtime, and software receipt
router.
Invariants:
  - The story is read-only and grants no execution authority.
  - The descriptor preserves the canonical pilot handoff order.
  - UAO approved, blocked, and rehearsal branches keep trace and receipt refs.
  - HTTP access requires the MUSIA read dependency path.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers import software_receipts
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_dev_mode,
    configure_musia_jwt,
)
from mcoi_runtime.app.routers.software_receipts import router
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowDescriptor,
    WorkflowStatus,
)
from mcoi_runtime.core.private_pilot_story import (
    CANONICAL_PRIVATE_PILOT_STAGES,
    PILOT_PACKET_INPUT_KEY,
    PILOT_PACKET_OUTPUT_KEY,
    PRIVATE_PILOT_WORKFLOW_ID,
    LIVE_REHEARSAL_ACTION_SOURCE,
    PrivatePilotStoryError,
    PrivatePilotStoryRequest,
    build_private_pilot_descriptor,
    build_private_pilot_live_rehearsal_uao_record,
    build_private_pilot_story,
    load_private_pilot_uao_records,
    validate_private_pilot_descriptor,
)
from mcoi_runtime.core.workflow import WorkflowEngine
from scripts.validate_universal_action_orchestration import validate_orchestration


NOW = "2026-06-01T00:00:00+00:00"


class RecordingPrivatePilotExecutor:
    """Minimal observation executor used to prove pilot handoff behavior."""

    def __init__(self) -> None:
        self.executed: list[str] = []
        self.inputs_by_stage: dict[str, dict[str, object]] = {}

    def execute_stage(
        self,
        stage_id: str,
        stage_type: str,
        skill_id: str | None,
        inputs: dict[str, object],
    ) -> StageExecutionResult:
        self.executed.append(stage_id)
        self.inputs_by_stage[stage_id] = dict(inputs)
        return StageExecutionResult(
            stage_id=stage_id,
            status=StageStatus.COMPLETED,
            output={
                PILOT_PACKET_OUTPUT_KEY: f"{stage_id}:pilot-packet",
                "stage_type": stage_type,
                "skill_id": skill_id,
            },
            started_at=NOW,
            completed_at=NOW,
        )


def _client() -> TestClient:
    configure_musia_auth(None)
    configure_musia_jwt(None)
    configure_musia_dev_mode(True)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _live_admission_preview(*, decision: str = "defer") -> dict[str, object]:
    return {
        "admission_preview_id": "orgos-handoff-action-admission-preview-test",
        "case_id": "case-demo",
        "step_id": "engineering_runtime_witness",
        "read_only": True,
        "governed": True,
        "decision": decision,
        "reason_code": "evidence_missing" if decision != "allow" else "plan_step_gate_allowed",
        "decision_set": ["allow", "block", "defer", "escalate", "simulate"],
        "decision_scope": "handoff_action_preview",
        "execution_authority_granted": False,
        "dispatch_authority_granted": False,
        "receipt_binding_authority_granted": decision == "allow",
        "proposed_action": "bind_worker_receipt",
        "requested_by_role_id": "engineering.owner",
        "gate_preview": {
            "preview_id": "org-step-gate-preview-test",
            "case_id": "case-demo",
            "step_id": "engineering_runtime_witness",
            "status": "allowed" if decision == "allow" else "blocked",
            "reason": "allowed" if decision == "allow" else "evidence_missing",
            "checked_preconditions": ["launch_boundary_defined"],
            "missing_preconditions": [],
            "authority_rule_ids": ["authority.engineering.gateway_runtime.verify"],
            "evidence_refs": ["evidence:engineering_gateway_witness"],
            "approval_refs": [],
            "previewed_at": NOW,
            "metadata": {"mutates_state": False},
        },
        "handoff": {
            "step_id": "engineering_runtime_witness",
            "department_id": "engineering",
            "responsible_role_id": "engineering.owner",
            "capability_id": "engineering.gateway_runtime.verify",
            "action": "verify_gateway_runtime",
            "expected_effect": "gateway_runtime_witnessed",
            "preconditions": ["launch_boundary_defined"],
            "postconditions": ["runtime_witness_collected"],
            "approvals_required": [],
            "predecessor_step_ids": ["product_launch_boundary"],
            "rollback_plan_id": "rollback.gateway_runtime_witness",
            "gate_status": "allowed" if decision == "allow" else "blocked",
            "handoff_status": "ready_for_worker_receipt" if decision == "allow" else "awaiting_evidence",
            "next_action": "bind_worker_receipt" if decision == "allow" else "collect_required_evidence",
            "dispatch_authority": False,
            "evidence_refs": ["evidence:engineering_gateway_witness"],
            "missing_evidence": [] if decision == "allow" else ["engineering_runtime_conformance"],
            "worker_receipt_count": 0,
            "worker_receipt_bindings": [],
            "worker_receipt_url": "/api/v1/cases/case-demo/plan-steps/engineering_runtime_witness/worker-receipt",
        },
        "causal_decision_trace": {
            "intent": "bind_worker_receipt",
            "actor": "engineering.owner",
            "tenant": "tenant-private",
            "entities": {
                "case_id": "case-demo",
                "step_id": "engineering_runtime_witness",
                "department_id": "engineering",
                "capability_id": "engineering.gateway_runtime.verify",
            },
            "assumptions": ["preview_only", "no_worker_dispatch", "no_case_state_mutation"],
            "evidence_refs": ["evidence:engineering_gateway_witness"],
            "constraints": ["checked_preconditions", "capability_certification"],
            "conflicts": [] if decision == "allow" else ["evidence_missing"],
            "guard_verdicts": {
                "identity_valid": "Pass",
                "tenant_valid": "Pass",
                "authority_valid": "Pass",
                "policy_allows": "Pass" if decision == "allow" else "blocked_by_gate",
                "risk_acceptable": "Pass",
                "budget_available": "not_required_for_read_only_preview",
                "evidence_sufficient": "Pass" if decision == "allow" else "Fail(evidence_missing)",
                "temporal_window_valid": "not_required_for_read_only_preview",
                "capability_certified": "Pass",
                "recovery_available": "Pass",
                "receipt_emittable": "Pass" if decision == "allow" else "not_requested",
            },
            "decision": decision,
            "reason_code": "evidence_missing" if decision != "allow" else "plan_step_gate_allowed",
            "receipt_ref": None,
            "closure_state": "preview_only",
        },
        "metadata": {"test": True},
    }


def test_private_pilot_descriptor_links_expected_sequence_without_execution_power() -> None:
    descriptor = build_private_pilot_descriptor(created_at=NOW)
    stage_ids = tuple(stage.stage_id for stage in descriptor.stages)

    assert descriptor.workflow_id == PRIVATE_PILOT_WORKFLOW_ID
    assert descriptor.created_at == NOW
    assert stage_ids == tuple(stage.stage_id for stage in CANONICAL_PRIVATE_PILOT_STAGES)
    assert all(stage.stage_type is StageType.OBSERVATION for stage in descriptor.stages)
    assert all(stage.skill_id is None for stage in descriptor.stages)
    assert descriptor.stages[0].predecessors == ()
    assert descriptor.stages[-1].predecessors == ("receipt_closure",)
    assert len(descriptor.bindings) == len(descriptor.stages) - 1
    assert validate_private_pilot_descriptor(descriptor) == ()


def test_private_pilot_story_links_orgos_uao_governors_sdlc_and_dashboards() -> None:
    story = build_private_pilot_story(
        PrivatePilotStoryRequest(
            tenant_id="tenant-private",
            org_id="org-demo",
            case_id="case-demo",
            actor_id="operator:demo",
        ),
        created_at=NOW,
    )
    branches = {branch["branch_id"]: branch for branch in story["uao_branches"]}

    assert story["read_only"] is True
    assert story["governed"] is True
    assert story["valid"] is True
    assert story["composition_outcome"] == "SolvedVerified"
    assert story["pilot_execution_outcome"] == "AwaitingEvidence"
    assert story["authority_boundary"]["execution_authority_granted"] is False
    assert story["authority_boundary"]["live_capabilities_invoked"] is False
    assert story["stage_count"] == 6
    assert story["stages"][0]["stage_id"] == "orgos_request"
    assert story["stages"][-1]["stage_id"] == "dashboard_view"
    assert story["orgos"]["department_registry_ref"] == "/api/v1/orgs/org-demo/department-registry"
    assert story["orgos"]["authority_map_view_ref"] == "/api/v1/orgs/org-demo/authority-map/view"
    assert branches["approved"]["decision_status"] == "allow"
    assert branches["approved"]["execution_allowed"] is True
    assert branches["approved"]["reconciliation_ref"] == (
        "reconciliation://uao_public_status_refresh"
    )
    assert branches["approved"]["memory_ref"] == (
        "memory://status-page/public-status-refresh"
    )
    assert branches["blocked"]["decision_status"] == "block"
    assert branches["blocked"]["execution_allowed"] is False
    assert branches["blocked"]["reconciliation_ref"] == (
        "reconciliation://uao_invoice_payment_blocked"
    )
    assert branches["blocked"]["memory_ref"] == "memory://invoice-123/payment-blocked"
    assert branches["rehearsal"]["decision_status"] == "simulate"
    assert branches["rehearsal"]["execution_allowed"] is False
    assert branches["rehearsal"]["reconciliation_ref"] == ""
    assert branches["rehearsal"]["memory_ref"] == ""
    assert story["governor_chain"]["valid"] is True
    assert story["governor_chain"]["stage_count"] == 7
    assert story["sdlc_dashboard"]["read_only"] is True
    assert story["sdlc_dashboard"]["stage_count"] == 11
    assert "/software/receipts/sdlc/dashboard" in story["dashboard_refs"]
    assert "/software/receipts/private-pilot/story" in story["dashboard_refs"]
    assert story["receipt_count"] >= 1
    assert story["causal_decision_trace_ref_count"] >= 3


def test_private_pilot_live_rehearsal_record_validates_as_uao_simulation() -> None:
    request = PrivatePilotStoryRequest(
        tenant_id="tenant-private",
        org_id="org-demo",
        case_id="case-demo",
        actor_id="engineering.owner",
    )

    record = build_private_pilot_live_rehearsal_uao_record(
        request,
        (_live_admission_preview(decision="defer"),),
        created_at=NOW,
    )
    errors = validate_orchestration(record)
    story = build_private_pilot_story(
        request,
        uao_records={
            **load_private_pilot_uao_records(),
            "rehearsal": record,
        },
        created_at=NOW,
    )
    branches = {branch["branch_id"]: branch for branch in story["uao_branches"]}

    assert errors == []
    assert record["decision"]["status"] == "simulate"
    assert record["effect_bearing"] is False
    assert record["execution_receipt_ref"] is None
    assert record["action_envelope"]["source"] == LIVE_REHEARSAL_ACTION_SOURCE
    assert record["action_envelope"]["tenant"] == "tenant-private"
    assert record["pipeline_stages"][5]["status"] == "simulated"
    assert branches["rehearsal"]["source_ref"] == LIVE_REHEARSAL_ACTION_SOURCE
    assert branches["rehearsal"]["closure_state"] == "closed_simulated"


def test_private_pilot_live_rehearsal_rejects_cross_tenant_preview() -> None:
    request = PrivatePilotStoryRequest(
        tenant_id="tenant-private",
        org_id="org-demo",
        case_id="case-demo",
        actor_id="engineering.owner",
    )
    preview = _live_admission_preview(decision="allow")
    preview["causal_decision_trace"]["tenant"] = "tenant-other"  # type: ignore[index]

    with pytest.raises(PrivatePilotStoryError) as exc_info:
        build_private_pilot_live_rehearsal_uao_record(request, (preview,), created_at=NOW)

    assert "tenant binding changed" in str(exc_info.value)


def test_private_pilot_validation_rejects_reordered_stage_graph() -> None:
    descriptor = build_private_pilot_descriptor(created_at=NOW)
    reordered = WorkflowDescriptor(
        workflow_id=descriptor.workflow_id,
        name=descriptor.name,
        description=descriptor.description,
        stages=(descriptor.stages[1], descriptor.stages[0], *descriptor.stages[2:]),
        bindings=descriptor.bindings,
        created_at=descriptor.created_at,
    )

    violations = validate_private_pilot_descriptor(reordered)

    assert "private pilot stage order changed" in violations
    assert "orgos_request stage identifier changed" in violations
    assert "uao_envelope stage identifier changed" in violations
    assert "orgos_request predecessor binding changed" in violations


def test_private_pilot_uao_loader_rejects_malformed_rehearsal_branch(tmp_path) -> None:
    records = load_private_pilot_uao_records()
    invalid_rehearsal = dict(records["rehearsal"])
    invalid_rehearsal["decision"] = dict(invalid_rehearsal["decision"])
    invalid_rehearsal["decision"]["status"] = "allow"
    invalid_path = tmp_path / "invalid_rehearsal.json"
    invalid_path.write_text(json.dumps(invalid_rehearsal), encoding="utf-8")

    with pytest.raises(PrivatePilotStoryError) as exc_info:
        load_private_pilot_uao_records({"rehearsal": invalid_path})

    message = str(exc_info.value)
    assert "UAO branch rehearsal decision status changed" in message
    assert str(tmp_path) not in message
    assert "invalid_rehearsal" not in message


def test_private_pilot_workflow_runtime_preserves_packet_handoff() -> None:
    descriptor = build_private_pilot_descriptor(created_at=NOW)
    engine = WorkflowEngine(clock=lambda: NOW)
    executor = RecordingPrivatePilotExecutor()

    record = engine.start_workflow(descriptor)
    while record.status is WorkflowStatus.RUNNING:
        record = engine.execute_next_stage(descriptor, record, executor)

    expected_stage_ids = [stage.stage_id for stage in CANONICAL_PRIVATE_PILOT_STAGES]
    assert record.status is WorkflowStatus.COMPLETED
    assert executor.executed == expected_stage_ids
    assert len(record.stage_results) == len(expected_stage_ids)
    assert PILOT_PACKET_INPUT_KEY not in executor.inputs_by_stage["orgos_request"]
    assert executor.inputs_by_stage["uao_envelope"][PILOT_PACKET_INPUT_KEY] == (
        "orgos_request:pilot-packet"
    )
    assert executor.inputs_by_stage["dashboard_view"][PILOT_PACKET_INPUT_KEY] == (
        "receipt_closure:pilot-packet"
    )


def test_private_pilot_story_route_returns_read_only_summary() -> None:
    client = _client()

    response = client.get(
        "/software/receipts/private-pilot/story",
        params={"org_id": "org-http", "case_id": "case-http"},
        headers={"X-Tenant-ID": "tenant-http"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "private_pilot_story"
    assert body["tenant_id"] == "tenant-http"
    assert body["governed"] is True
    assert body["stage_count"] == body["story"]["stage_count"]
    assert body["uao_branch_count"] == 3
    assert body["story"]["request"]["org_id"] == "org-http"
    assert body["story"]["request"]["case_id"] == "case-http"
    assert body["story"]["read_only"] is True
    assert body["story"]["authority_boundary"]["external_mutation_allowed"] is False


def test_private_pilot_story_route_bounds_projection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_story_projection(request: PrivatePilotStoryRequest) -> dict[str, object]:
        raise PrivatePilotStoryError("missing UAO pilot artifact for approved")

    monkeypatch.setattr(
        software_receipts,
        "build_private_pilot_story",
        reject_story_projection,
    )
    client = _client()

    response = client.get(
        "/software/receipts/private-pilot/story",
        headers={"X-Tenant-ID": "tenant-http"},
    )
    detail = response.json()["detail"]

    assert response.status_code == 503
    assert detail == {"error": "private pilot story unavailable", "type": "PrivatePilotStoryError"}
    assert "approved" not in str(detail)
