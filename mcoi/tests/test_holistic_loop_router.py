"""Purpose: verify the holistic loop read-model HTTP router.
Governance scope: read-only loop registry exposure, blocker preservation, and
default router mounting.
Dependencies: FastAPI TestClient and holistic loop router.
Invariants:
  - The HTTP surface exposes registered loops without mutation routes.
  - Missing evidence is reported as blockers, not verified closure.
  - Default router mounting includes the loop read model.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.loops import router
from mcoi_runtime.app.server_http import include_default_routers


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_loop_read_model_exposes_registered_blocked_loops() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model")
    payload = response.json()

    assert response.status_code == 200
    assert payload["read_model_id"] == "holistic_loop_read_model"
    assert payload["status"] == "blocked"
    assert payload["blocked_count"] == 6
    assert payload["returned_count"] == 6
    assert {loop["loop_id"] for loop in payload["loops"]} == {
        "audit_proof_verification_loop",
        "authority_obligation_loop",
        "deployment_witness_loop",
        "runtime_conformance_loop",
        "cognitive_outcome_loop",
        "governed_code_change_loop",
    }
    assert all(loop["open_blockers"] for loop in payload["loops"])
    assert all(loop["risk_binding"] for loop in payload["loops"])
    assert all(loop["status_binding"] for loop in payload["loops"])
    assert all(loop["transition_bindings"] for loop in payload["loops"])
    assert all(loop["mode_binding"] for loop in payload["loops"])
    assert all(loop["authority_bindings"] for loop in payload["loops"])
    assert all(loop["missing_authority"] for loop in payload["loops"])
    assert all(loop["evidence_bindings"] for loop in payload["loops"])
    assert all(loop["closure_condition_bindings"] for loop in payload["loops"])
    assert all(loop["closure_evidence_pack"] for loop in payload["loops"])
    assert all(loop["operator_closure_readiness_view"] for loop in payload["loops"])
    assert all(loop["proof_obligation_view"] for loop in payload["loops"])
    assert all(loop["audit_evolution_view"] for loop in payload["loops"])
    assert all(loop["recovery_readiness_view"] for loop in payload["loops"])
    assert all(loop["rollback_binding"] for loop in payload["loops"])
    assert all(loop["learning_binding"] for loop in payload["loops"])
    assert all(loop["step_receipts"] for loop in payload["loops"])
    assert all(loop["receipt_lineage_bindings"] for loop in payload["loops"])
    assert all(
        {binding["authority_ref"] for binding in loop["authority_bindings"]}
        == set(loop["required_authority"])
        for loop in payload["loops"]
    )
    assert all(
        {binding["evidence_ref"] for binding in loop["evidence_bindings"]}
        == set(loop["required_evidence"])
        for loop in payload["loops"]
    )
    assert all(
        {binding["closure_ref"] for binding in loop["closure_condition_bindings"]}
        == set(loop["closure_conditions"])
        for loop in payload["loops"]
    )
    assert all(
        loop["risk_binding"]["risk_ref"] == loop["risk_class"]
        and loop["risk_binding"]["read_only"] is True
        and loop["risk_binding"]["terminal_closure"] is False
        and loop["risk_binding"]["hazard_refs"]
        and loop["risk_binding"]["mitigation_refs"]
        and loop["risk_binding"]["monitor_refs"]
        for loop in payload["loops"]
    )
    assert all(
        loop["status_binding"]["projected_status"] == loop["status"]
        and set(loop["status_binding"]["blocker_refs"]) == set(loop["open_blockers"])
        and loop["status_binding"]["read_only"] is True
        and loop["status_binding"]["status_transition"] is False
        and loop["status_binding"]["terminal_closure"] is False
        and loop["status_binding"]["verification_refs"]
        and loop["status_binding"]["closure_gate_refs"]
        for loop in payload["loops"]
    )
    assert all(
        {binding["transition_ref"] for binding in loop["transition_bindings"]}
        == {
            "open_to_blocked_on_missing_requirements",
            "blocked_to_verified_after_requirements",
            "verified_to_closed_requires_terminal_closure",
        }
        for loop in payload["loops"]
    )
    assert all(
        set(binding["blocker_refs"]) == set(loop["open_blockers"])
        and set(binding["required_authority_refs"]) <= set(loop["required_authority"])
        and set(binding["required_evidence_refs"]) <= set(loop["required_evidence"])
        and loop["rollback_policy"] in binding["rollback_refs"]
        and binding["read_only"] is True
        and binding["executes_transition"] is False
        and binding["terminal_closure"] is False
        for loop in payload["loops"]
        for binding in loop["transition_bindings"]
    )
    assert all(
        loop["mode_binding"]["projected_mode"] == loop["mode"]
        and loop["mode"] in loop["mode_binding"]["allowed_modes"]
        and loop["mode_binding"]["read_only"] is True
        and loop["mode_binding"]["mode_transition"] is False
        and loop["mode_binding"]["terminal_closure"] is False
        and loop["mode_binding"]["separation_refs"]
        and loop["mode_binding"]["real_execution_guard_refs"]
        for loop in payload["loops"]
    )
    assert all(
        binding["read_only"] is True and binding["terminal_closure"] is False
        for loop in payload["loops"]
        for binding in loop["authority_bindings"]
    )
    assert all(
        binding["read_only"] is True and binding["terminal_closure"] is False
        for loop in payload["loops"]
        for binding in loop["evidence_bindings"]
    )
    assert all(
        binding["read_only"] is True
        and binding["terminal_closure"] is False
        and binding["required_evidence_refs"]
        and binding["required_authority_refs"]
        for loop in payload["loops"]
        for binding in loop["closure_condition_bindings"]
    )
    assert all(
        loop["rollback_binding"]["rollback_ref"] == loop["rollback_policy"]
        and loop["rollback_binding"]["read_only"] is True
        and loop["rollback_binding"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        loop["learning_binding"]["learning_ref"] == loop["learning_policy"]
        and loop["learning_binding"]["read_only"] is True
        and loop["learning_binding"]["terminal_closure"] is False
        and loop["learning_binding"]["evidence_input_refs"]
        and loop["learning_binding"]["admission_refs"]
        and loop["learning_binding"]["retention_refs"]
        for loop in payload["loops"]
    )
    assert all(
        receipt["metadata"]["read_only"] is True
        and receipt["metadata"]["synthetic_projection"] is True
        and receipt["metadata"]["terminal_closure"] is False
        for loop in payload["loops"]
        for receipt in loop["step_receipts"]
    )
    assert all(
        {
            binding["step"]: binding["receipt_hash"]
            for binding in loop["receipt_lineage_bindings"]
        }
        == {
            receipt["step"]: receipt["output_hash"]
            for receipt in loop["step_receipts"]
        }
        for loop in payload["loops"]
    )
    assert all(
        set(binding["blocker_refs"]) == set(loop["open_blockers"])
        and set(binding["observed_evidence_refs"]) == set(loop["evidence_refs"])
        and set(binding["required_evidence_refs"]) <= set(loop["required_evidence"])
        and binding["receipt_ref"] in binding["source_receipt_refs"]
        and binding["read_only"] is True
        and binding["emits_receipt"] is False
        and binding["terminal_closure"] is False
        for loop in payload["loops"]
        for binding in loop["receipt_lineage_bindings"]
    )
    assert all(
        set(loop["closure_evidence_pack"]["required_evidence_refs"])
        == set(loop["required_evidence"])
        and set(loop["closure_evidence_pack"]["observed_evidence_refs"])
        == set(loop["evidence_refs"])
        and set(loop["closure_evidence_pack"]["missing_evidence_refs"])
        == set(loop["missing_evidence"])
        and set(loop["closure_evidence_pack"]["required_authority_refs"])
        == set(loop["required_authority"])
        and set(loop["closure_evidence_pack"]["observed_authority_refs"])
        == set(loop["authority_refs"])
        and set(loop["closure_evidence_pack"]["missing_authority_refs"])
        == set(loop["missing_authority"])
        and set(loop["closure_evidence_pack"]["blocker_refs"])
        == set(loop["open_blockers"])
        and set(loop["closure_evidence_pack"]["closure_condition_refs"])
        == set(loop["closure_conditions"])
        and set(loop["closure_evidence_pack"]["receipt_lineage_refs"])
        == {binding["lineage_ref"] for binding in loop["receipt_lineage_bindings"]}
        and loop["closure_evidence_pack"]["read_only"] is True
        and loop["closure_evidence_pack"]["emits_receipt"] is False
        and loop["closure_evidence_pack"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        loop["operator_closure_readiness_view"]["projected_status"] == loop["status"]
        and set(loop["operator_closure_readiness_view"]["blocker_refs"])
        == set(loop["open_blockers"])
        and set(loop["operator_closure_readiness_view"]["evidence_gap_refs"])
        == set(loop["missing_evidence"])
        and set(loop["operator_closure_readiness_view"]["authority_gap_refs"])
        == set(loop["missing_authority"])
        and set(loop["operator_closure_readiness_view"]["closure_condition_refs"])
        == set(loop["closure_conditions"])
        and loop["operator_closure_readiness_view"]["rollback_ref"]
        == loop["rollback_policy"]
        and loop["operator_closure_readiness_view"]["readiness_state"]
        == "blocked_by_unresolved_gaps"
        and loop["operator_closure_readiness_view"]["next_proof_action"]
        == "resolve_blockers_before_terminal_closure_review"
        and "closure_evidence_pack" in loop["operator_closure_readiness_view"]["next_proof_refs"]
        and "closure_report" in loop["operator_closure_readiness_view"]["next_proof_refs"]
        and loop["operator_closure_readiness_view"]["read_only"] is True
        and loop["operator_closure_readiness_view"]["mutation_route"] is False
        and loop["operator_closure_readiness_view"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        set(loop["proof_obligation_view"]["required_evidence_refs"])
        == set(loop["required_evidence"])
        and set(loop["proof_obligation_view"]["satisfied_evidence_refs"])
        == set(loop["evidence_refs"])
        and set(loop["proof_obligation_view"]["missing_evidence_refs"])
        == set(loop["missing_evidence"])
        and set(loop["proof_obligation_view"]["required_authority_refs"])
        == set(loop["required_authority"])
        and set(loop["proof_obligation_view"]["satisfied_authority_refs"])
        == set(loop["authority_refs"])
        and set(loop["proof_obligation_view"]["missing_authority_refs"])
        == set(loop["missing_authority"])
        and set(loop["proof_obligation_view"]["closure_condition_refs"])
        == set(loop["closure_conditions"])
        and set(loop["proof_obligation_view"]["validator_refs"])
        == set(loop["closure_evidence_pack"]["validator_refs"])
        and set(loop["proof_obligation_view"]["proof_surface_refs"])
        == set(loop["closure_evidence_pack"]["proof_surface_refs"])
        and set(loop["proof_obligation_view"]["blocker_refs"])
        == set(loop["open_blockers"])
        and loop["proof_obligation_view"]["obligation_state"]
        == "blocked_by_missing_proof"
        and loop["proof_obligation_view"]["read_only"] is True
        and loop["proof_obligation_view"]["executes_validator"] is False
        and loop["proof_obligation_view"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        set(loop["audit_evolution_view"]["receipt_refs"])
        == {receipt["output_hash"] for receipt in loop["step_receipts"]}
        and set(loop["audit_evolution_view"]["receipt_lineage_refs"])
        == {binding["lineage_ref"] for binding in loop["receipt_lineage_bindings"]}
        and set(loop["audit_evolution_view"]["audit_blocker_refs"])
        == set(loop["open_blockers"])
        and loop["audit_evolution_view"]["learning_policy_ref"]
        == loop["learning_policy"]
        and set(loop["audit_evolution_view"]["learning_candidate_refs"])
        == set(loop["closure_report"]["learning_candidates"])
        and loop["learning_policy"]
        in loop["audit_evolution_view"]["learning_candidate_refs"]
        and set(loop["audit_evolution_view"]["learning_evidence_input_refs"])
        == set(loop["learning_binding"]["evidence_input_refs"])
        and set(loop["audit_evolution_view"]["learning_admission_refs"])
        == set(loop["learning_binding"]["admission_refs"])
        and set(loop["audit_evolution_view"]["learning_retention_refs"])
        == set(loop["learning_binding"]["retention_refs"])
        and set(loop["audit_evolution_view"]["proof_surface_refs"])
        == (
            set(loop["closure_evidence_pack"]["proof_surface_refs"])
            | set(loop["learning_binding"]["proof_surface_refs"])
        )
        and loop["audit_evolution_view"]["audit_state"]
        == "audit_blocked_by_unresolved_gaps"
        and loop["audit_evolution_view"]["read_only"] is True
        and loop["audit_evolution_view"]["emits_receipt"] is False
        and loop["audit_evolution_view"]["admits_learning"] is False
        and loop["audit_evolution_view"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        loop["recovery_readiness_view"]["rollback_ref"] == loop["rollback_policy"]
        and loop["recovery_readiness_view"]["rollback_available"]
        is loop["closure_report"]["rollback_available"]
        and loop["recovery_readiness_view"]["closure_report_ref"] == "closure_report"
        and loop["recovery_readiness_view"]["closure_evidence_pack_ref"]
        == loop["closure_evidence_pack"]["pack_ref"]
        and set(loop["recovery_readiness_view"]["blocker_refs"])
        == set(loop["open_blockers"])
        and set(loop["recovery_readiness_view"]["receipt_lineage_refs"])
        == set(loop["closure_evidence_pack"]["receipt_lineage_refs"])
        and set(loop["recovery_readiness_view"]["recovery_source_refs"])
        == set(loop["rollback_binding"]["source_refs"])
        and set(loop["recovery_readiness_view"]["recovery_validator_refs"])
        == set(loop["rollback_binding"]["validator_refs"])
        and set(loop["recovery_readiness_view"]["recovery_proof_surface_refs"])
        == (
            set(loop["closure_evidence_pack"]["proof_surface_refs"])
            | set(loop["rollback_binding"]["proof_surface_refs"])
        )
        and loop["recovery_readiness_view"]["recovery_state"]
        == "recovery_blocked_by_unresolved_gaps"
        and loop["recovery_readiness_view"]["next_recovery_action"]
        == "resolve_blockers_before_recovery_or_terminal_review"
        and loop["recovery_readiness_view"]["read_only"] is True
        and loop["recovery_readiness_view"]["executes_rollback"] is False
        and loop["recovery_readiness_view"]["opens_incident"] is False
        and loop["recovery_readiness_view"]["terminal_closure"] is False
        for loop in payload["loops"]
    )
    assert all(
        set(receipt["errors"]) == set(loop["open_blockers"])
        for loop in payload["loops"]
        for receipt in loop["step_receipts"]
    )
    assert all(loop["closure_report"]["closed"] is False for loop in payload["loops"])
    assert all(
        set(loop["closure_report"]["unresolved_gaps"]) == set(loop["open_blockers"])
        for loop in payload["loops"]
    )
    assert payload["read_only"] is True
    assert payload["report_is_not_terminal_closure"] is True


def test_loop_read_model_limit_is_bounded_and_truncated() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model", params={"limit": 2})
    payload = response.json()

    assert response.status_code == 200
    assert payload["returned_count"] == 2
    assert payload["total_count"] == 6
    assert payload["truncated"] is True
    assert payload["blocked_count"] == 2
    assert len(payload["loops"]) == 2


def test_loop_read_model_rejects_invalid_limit_without_server_error() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model", params={"limit": 0})
    payload = response.json()

    assert response.status_code == 422
    assert "detail" in payload
    assert "Traceback" not in response.text


def test_loop_read_model_has_no_mutation_companion() -> None:
    client = _client()

    post_response = client.post("/api/v1/loops/read-model", json={})
    put_response = client.put("/api/v1/loops/read-model", json={})
    delete_response = client.delete("/api/v1/loops/read-model")

    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405
    assert "Traceback" not in post_response.text


def test_default_router_mounts_loop_read_model() -> None:
    app = FastAPI()
    include_default_routers(app)
    client = TestClient(app)

    response = client.get("/api/v1/loops/read-model", params={"limit": 1})
    payload = response.json()

    assert response.status_code == 200
    assert payload["read_model_id"] == "holistic_loop_read_model"
    assert payload["returned_count"] == 1
    assert payload["governed"] is True
