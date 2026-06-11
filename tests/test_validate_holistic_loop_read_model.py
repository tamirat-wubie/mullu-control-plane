"""Purpose: verify holistic loop read-model contract validation.
Governance scope: schema shape, current report validation, blocker/status
    consistency, and non-terminal closure fields.
Dependencies: scripts.validate_holistic_loop_read_model.
Invariants:
  - Current report output validates.
  - Count and blocker contradictions are rejected.
  - Closed or verified loops cannot carry missing evidence.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_holistic_loop_read_model as validator


def test_current_holistic_loop_read_model_contract_passes() -> None:
    errors = validator.validate_contract()
    report = validator.build_report()
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")

    assert errors == []
    assert schema["title"] == "Holistic Loop Read Model"
    assert report["report_id"] == "holistic_loop_read_model"
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert all(loop["risk_binding"] for loop in report["loops"])
    assert all(loop["status_binding"] for loop in report["loops"])
    assert all(loop["transition_bindings"] for loop in report["loops"])
    assert all(loop["mode_binding"] for loop in report["loops"])
    assert all(loop["authority_bindings"] for loop in report["loops"])
    assert all(loop["missing_authority"] for loop in report["loops"])
    assert all(loop["rollback_binding"] for loop in report["loops"])
    assert all(loop["learning_binding"] for loop in report["loops"])
    assert all(loop["closure_condition_bindings"] for loop in report["loops"])
    assert all(loop["step_receipts"] for loop in report["loops"])
    assert all(loop["receipt_lineage_bindings"] for loop in report["loops"])
    assert all(loop["closure_evidence_pack"] for loop in report["loops"])


def test_schema_rejects_missing_required_loop_field() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "open_blockers"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: open_blockers" in error for error in errors)
    assert "open_blockers" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_step_receipts() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "step_receipts"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: step_receipts" in error for error in errors)
    assert "step_receipts" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_receipt_lineage_bindings() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field
        for field in invalid_schema["$defs"]["loop_summary"]["required"]
        if field != "receipt_lineage_bindings"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: receipt_lineage_bindings" in error for error in errors)
    assert "receipt_lineage_bindings" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_closure_evidence_pack() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field
        for field in invalid_schema["$defs"]["loop_summary"]["required"]
        if field != "closure_evidence_pack"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: closure_evidence_pack" in error for error in errors)
    assert "closure_evidence_pack" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_operator_closure_readiness_view() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field
        for field in invalid_schema["$defs"]["loop_summary"]["required"]
        if field != "operator_closure_readiness_view"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any(
        "schema missing required loop field: operator_closure_readiness_view" in error
        for error in errors
    )
    assert "operator_closure_readiness_view" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_proof_obligation_view() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field
        for field in invalid_schema["$defs"]["loop_summary"]["required"]
        if field != "proof_obligation_view"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: proof_obligation_view" in error for error in errors)
    assert "proof_obligation_view" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_authority_bindings() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "authority_bindings"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: authority_bindings" in error for error in errors)
    assert "authority_bindings" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_rollback_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "rollback_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: rollback_binding" in error for error in errors)
    assert "rollback_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_risk_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "risk_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: risk_binding" in error for error in errors)
    assert "risk_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_learning_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "learning_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: learning_binding" in error for error in errors)
    assert "learning_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_mode_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "mode_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: mode_binding" in error for error in errors)
    assert "mode_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_status_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "status_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: status_binding" in error for error in errors)
    assert "status_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_transition_bindings() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "transition_bindings"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: transition_bindings" in error for error in errors)
    assert "transition_bindings" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_closure_condition_bindings() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field
        for field in invalid_schema["$defs"]["loop_summary"]["required"]
        if field != "closure_condition_bindings"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: closure_condition_bindings" in error for error in errors)
    assert "closure_condition_bindings" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_blocked_count_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["blocked_count"] = 0

    errors = validator.validate_report(invalid_report)

    assert "blocked_count does not match loop blockers" in errors
    assert invalid_report["blocked_count"] == 0
    assert report["blocked_count"] == 4


def test_status_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("report status must be blocked" in error for error in errors)
    assert invalid_report["status"] == "verified"
    assert invalid_report["blocked_count"] == report["blocked_count"]


def test_status_binding_must_match_projected_status() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status_binding"]["projected_status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("status_binding projected_status must match status" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "blocked"
    assert invalid_report["loops"][0]["status_binding"]["projected_status"] == "verified"


def test_status_binding_blockers_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status_binding"]["blocker_refs"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("status_binding blocker_refs must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["status_binding"]["blocker_refs"] == ["different_gap"]


def test_status_binding_cannot_claim_transition_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["status_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["status_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("status_binding read_only must be true" in error for error in errors)
    assert any("status_binding status_transition must be false" in error for error in errors)
    assert any("status_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["status_transition"] is True


def test_status_binding_requires_verification_and_closure_refs() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["status_binding"]
    invalid_binding["verification_refs"] = []
    invalid_binding["closure_gate_refs"] = []
    invalid_binding["source_refs"] = []

    errors = validator.validate_report(invalid_report)

    assert any("status_binding verification_refs" in error for error in errors)
    assert any("status_binding closure_gate_refs" in error for error in errors)
    assert any("status_binding source_refs" in error for error in errors)


def test_transition_binding_blockers_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["transition_bindings"][0]["blocker_refs"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("transition binding 0 blocker_refs must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["transition_bindings"][0]["blocker_refs"] == ["different_gap"]


def test_transition_binding_refs_must_be_declared_and_link_rollback() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["transition_bindings"][0]
    invalid_binding["required_authority_refs"] = ["undeclared_authority"]
    invalid_binding["required_evidence_refs"] = ["undeclared_evidence"]
    invalid_binding["rollback_refs"] = ["different_policy"]

    errors = validator.validate_report(invalid_report)

    assert any("unexpected authority ref: undeclared_authority" in error for error in errors)
    assert any("unexpected evidence ref: undeclared_evidence" in error for error in errors)
    assert any("rollback_refs must include rollback_policy" in error for error in errors)


def test_duplicate_transition_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["transition_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["transition_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate transition binding" in error for error in errors)
    assert len(invalid_report["loops"][0]["transition_bindings"]) > 3


def test_transition_binding_cannot_claim_execution_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["transition_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["executes_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("transition binding 0 read_only must be true" in error for error in errors)
    assert any("transition binding 0 executes_transition must be false" in error for error in errors)
    assert any("transition binding 0 terminal_closure must be false" in error for error in errors)


def test_receipt_lineage_binding_must_match_step_receipt_and_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["receipt_hash"] = "sha256:9999999999999999999999999999999999999999999999999999999999999999"
    invalid_binding["blocker_refs"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("receipt_hash must match step receipt" in error for error in errors)
    assert any("receipt lineage binding 0 blocker_refs must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]


def test_receipt_lineage_binding_refs_must_be_declared_and_observed() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["required_evidence_refs"] = ["undeclared_evidence"]
    invalid_binding["observed_evidence_refs"] = ["unexpected_observed_evidence"]
    invalid_binding["source_receipt_refs"] = ["different_receipt"]

    errors = validator.validate_report(invalid_report)

    assert any("unexpected evidence ref: undeclared_evidence" in error for error in errors)
    assert any("observed_evidence_refs must match evidence_refs" in error for error in errors)
    assert any("source_receipt_refs must include receipt_ref" in error for error in errors)


def test_duplicate_receipt_lineage_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["receipt_lineage_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["receipt_lineage_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate receipt lineage binding" in error for error in errors)
    assert len(invalid_report["loops"][0]["receipt_lineage_bindings"]) > len(
        invalid_report["loops"][0]["step_receipts"]
    )


def test_receipt_lineage_binding_cannot_emit_or_claim_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["receipt_lineage_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["emits_receipt"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("receipt lineage binding 0 read_only must be true" in error for error in errors)
    assert any("receipt lineage binding 0 emits_receipt must be false" in error for error in errors)
    assert any("receipt lineage binding 0 terminal_closure must be false" in error for error in errors)


def test_closure_evidence_pack_must_match_loop_closure_inputs() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    pack = invalid_report["loops"][0]["closure_evidence_pack"]
    pack["required_evidence_refs"] = ["undeclared_evidence"]
    pack["observed_evidence_refs"] = ["unexpected_evidence"]
    pack["missing_authority_refs"] = ["different_authority"]
    pack["blocker_refs"] = ["different_gap"]
    pack["receipt_lineage_refs"] = ["different_lineage"]
    pack["evidence_complete"] = True
    pack["authority_complete"] = True
    pack["closure_blocked"] = False

    errors = validator.validate_report(invalid_report)

    assert any("required_evidence_refs must match required_evidence" in error for error in errors)
    assert any("observed_evidence_refs must match evidence_refs" in error for error in errors)
    assert any("missing_authority_refs must match missing_authority" in error for error in errors)
    assert any("blocker_refs must match open_blockers" in error for error in errors)
    assert any("receipt_lineage_refs must match receipt lineage bindings" in error for error in errors)
    assert any("evidence_complete must match closure_report" in error for error in errors)
    assert any("authority_complete must match missing_authority" in error for error in errors)
    assert any("closure_blocked must match open_blockers" in error for error in errors)


def test_closure_evidence_pack_cannot_emit_or_claim_terminal_closure() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    pack = invalid_report["loops"][0]["closure_evidence_pack"]
    pack["read_only"] = False
    pack["emits_receipt"] = True
    pack["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("closure_evidence_pack read_only must be true" in error for error in errors)
    assert any("closure_evidence_pack emits_receipt must be false" in error for error in errors)
    assert any("closure_evidence_pack terminal_closure must be false" in error for error in errors)


def test_operator_closure_readiness_view_must_match_loop_gaps_and_next_action() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    view = invalid_report["loops"][0]["operator_closure_readiness_view"]
    view["projected_status"] = "verified"
    view["blocker_refs"] = ["different_gap"]
    view["evidence_gap_refs"] = ["different_evidence"]
    view["authority_gap_refs"] = ["different_authority"]
    view["closure_condition_refs"] = ["different_closure"]
    view["rollback_ref"] = "different_rollback"
    view["rollback_available"] = False
    view["readiness_state"] = "ready_for_terminal_closure_review"
    view["next_proof_action"] = "run_loop_specific_terminal_closure_workflow"
    view["next_proof_refs"] = ["different_ref"]

    errors = validator.validate_report(invalid_report)

    assert any("projected_status must match status" in error for error in errors)
    assert any("blocker_refs must match open_blockers" in error for error in errors)
    assert any("evidence_gap_refs must match missing_evidence" in error for error in errors)
    assert any("authority_gap_refs must match missing_authority" in error for error in errors)
    assert any("closure_condition_refs must match closure_conditions" in error for error in errors)
    assert any("rollback_ref must match rollback_policy" in error for error in errors)
    assert any("rollback_available must match closure_report" in error for error in errors)
    assert any("readiness_state must match blockers" in error for error in errors)
    assert any("next_proof_action must match blockers" in error for error in errors)
    assert any("next_proof_refs must include closure_evidence_pack" in error for error in errors)
    assert any("next_proof_refs must include closure_report" in error for error in errors)


def test_operator_closure_readiness_view_cannot_mutate_or_claim_terminal_closure() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    view = invalid_report["loops"][0]["operator_closure_readiness_view"]
    view["read_only"] = False
    view["mutation_route"] = True
    view["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("operator_closure_readiness_view read_only must be true" in error for error in errors)
    assert any("operator_closure_readiness_view mutation_route must be false" in error for error in errors)
    assert any("operator_closure_readiness_view terminal_closure must be false" in error for error in errors)


def test_proof_obligation_view_must_match_loop_proof_inputs() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    view = invalid_report["loops"][0]["proof_obligation_view"]
    view["required_evidence_refs"] = ["undeclared_evidence"]
    view["satisfied_evidence_refs"] = ["unexpected_evidence"]
    view["missing_evidence_refs"] = ["different_evidence"]
    view["required_authority_refs"] = ["undeclared_authority"]
    view["satisfied_authority_refs"] = ["unexpected_authority"]
    view["missing_authority_refs"] = ["different_authority"]
    view["closure_condition_refs"] = ["different_closure"]
    view["validator_refs"] = ["different_validator"]
    view["proof_surface_refs"] = ["different_surface"]
    view["blocker_refs"] = ["different_gap"]
    view["obligation_state"] = "proof_obligations_satisfied_terminal_review_required"

    errors = validator.validate_report(invalid_report)

    assert any("required_evidence_refs must match required_evidence" in error for error in errors)
    assert any("satisfied_evidence_refs must match evidence_refs" in error for error in errors)
    assert any("missing_evidence_refs must match missing_evidence" in error for error in errors)
    assert any("required_authority_refs must match required_authority" in error for error in errors)
    assert any("satisfied_authority_refs must match authority_refs" in error for error in errors)
    assert any("missing_authority_refs must match missing_authority" in error for error in errors)
    assert any("closure_condition_refs must match closure_conditions" in error for error in errors)
    assert any("validator_refs must match closure_evidence_pack" in error for error in errors)
    assert any("proof_surface_refs must match closure_evidence_pack" in error for error in errors)
    assert any("blocker_refs must match open_blockers" in error for error in errors)
    assert any("obligation_state must match blockers" in error for error in errors)


def test_proof_obligation_view_cannot_execute_validator_or_claim_terminal_closure() -> None:
    invalid_report = copy.deepcopy(validator.build_report())
    view = invalid_report["loops"][0]["proof_obligation_view"]
    view["read_only"] = False
    view["executes_validator"] = True
    view["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("proof_obligation_view read_only must be true" in error for error in errors)
    assert any("proof_obligation_view executes_validator must be false" in error for error in errors)
    assert any("proof_obligation_view terminal_closure must be false" in error for error in errors)


def test_missing_evidence_requires_matching_blocker() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["open_blockers"] = []

    errors = validator.validate_report(invalid_report)

    assert any("missing evidence lacks blocker" in error for error in errors)
    assert invalid_report["loops"][0]["missing_evidence"]
    assert invalid_report["loops"][0]["open_blockers"] == []


def test_missing_authority_requires_matching_blocker() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["open_blockers"] = [
        blocker
        for blocker in invalid_report["loops"][0]["open_blockers"]
        if not blocker.startswith("missing_authority:")
    ]

    errors = validator.validate_report(invalid_report)

    assert any("missing authority lacks blocker" in error for error in errors)
    assert invalid_report["loops"][0]["missing_authority"]
    assert all(
        not blocker.startswith("missing_authority:")
        for blocker in invalid_report["loops"][0]["open_blockers"]
    )


def test_missing_authority_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    missing_binding = invalid_report["loops"][0]["authority_bindings"].pop()

    errors = validator.validate_report(invalid_report)

    assert any("missing authority binding" in error for error in errors)
    assert missing_binding["authority_ref"] in invalid_report["loops"][0]["required_authority"]
    assert missing_binding not in invalid_report["loops"][0]["authority_bindings"]


def test_duplicate_authority_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["authority_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["authority_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate authority binding" in error for error in errors)
    assert invalid_report["loops"][0]["authority_bindings"][0]["authority_ref"]
    assert len(invalid_report["loops"][0]["authority_bindings"]) > len(
        invalid_report["loops"][0]["required_authority"]
    )


def test_missing_closure_condition_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    missing_binding = invalid_report["loops"][0]["closure_condition_bindings"].pop()

    errors = validator.validate_report(invalid_report)

    assert any("missing closure condition binding" in error for error in errors)
    assert missing_binding["closure_ref"] in invalid_report["loops"][0]["closure_conditions"]
    assert missing_binding not in invalid_report["loops"][0]["closure_condition_bindings"]


def test_duplicate_closure_condition_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["closure_condition_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["closure_condition_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate closure condition binding" in error for error in errors)
    assert invalid_report["loops"][0]["closure_condition_bindings"][0]["closure_ref"]
    assert len(invalid_report["loops"][0]["closure_condition_bindings"]) > len(
        invalid_report["loops"][0]["closure_conditions"]
    )


def test_closure_condition_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["closure_condition_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("closure condition binding 0 read_only must be true" in error for error in errors)
    assert any("closure condition binding 0 terminal_closure must be false" in error for error in errors)
    assert invalid_binding["terminal_closure"] is True


def test_closure_condition_binding_refs_must_be_declared() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["closure_condition_bindings"][0]
    invalid_binding["required_evidence_refs"] = ["undeclared_evidence"]
    invalid_binding["required_authority_refs"] = ["undeclared_authority"]

    errors = validator.validate_report(invalid_report)

    assert any("unexpected evidence ref: undeclared_evidence" in error for error in errors)
    assert any("unexpected authority ref: undeclared_authority" in error for error in errors)
    assert "undeclared_evidence" not in invalid_report["loops"][0]["required_evidence"]


def test_authority_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["authority_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("authority binding 0 read_only must be true" in error for error in errors)
    assert any("authority binding 0 terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_risk_binding_must_match_risk_class() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["risk_binding"]["risk_ref"] = "different_risk"

    errors = validator.validate_report(invalid_report)

    assert any("risk_binding risk_ref must match risk_class" in error for error in errors)
    assert invalid_report["loops"][0]["risk_class"] != invalid_report["loops"][0]["risk_binding"][
        "risk_ref"
    ]
    assert invalid_report["loops"][0]["risk_binding"]["risk_ref"] == "different_risk"


def test_risk_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["risk_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("risk_binding read_only must be true" in error for error in errors)
    assert any("risk_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_risk_binding_requires_hazards_mitigations_and_monitors() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["risk_binding"]
    invalid_binding["hazard_refs"] = []
    invalid_binding["mitigation_refs"] = []
    invalid_binding["monitor_refs"] = []

    errors = validator.validate_report(invalid_report)

    assert any("risk_binding hazard_refs" in error for error in errors)
    assert any("risk_binding mitigation_refs" in error for error in errors)
    assert any("risk_binding monitor_refs" in error for error in errors)


def test_rollback_binding_must_match_policy() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["rollback_binding"]["rollback_ref"] = "different_policy"

    errors = validator.validate_report(invalid_report)

    assert any("rollback_binding rollback_ref must match rollback_policy" in error for error in errors)
    assert invalid_report["loops"][0]["rollback_policy"] != invalid_report["loops"][0]["rollback_binding"][
        "rollback_ref"
    ]
    assert invalid_report["loops"][0]["rollback_binding"]["rollback_ref"] == "different_policy"


def test_learning_binding_must_match_policy() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["learning_binding"]["learning_ref"] = "different_policy"

    errors = validator.validate_report(invalid_report)

    assert any("learning_binding learning_ref must match learning_policy" in error for error in errors)
    assert invalid_report["loops"][0]["learning_policy"] != invalid_report["loops"][0]["learning_binding"][
        "learning_ref"
    ]
    assert invalid_report["loops"][0]["learning_binding"]["learning_ref"] == "different_policy"


def test_learning_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["learning_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("learning_binding read_only must be true" in error for error in errors)
    assert any("learning_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_learning_binding_requires_input_admission_and_retention_refs() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["learning_binding"]
    invalid_binding["evidence_input_refs"] = []
    invalid_binding["admission_refs"] = []
    invalid_binding["retention_refs"] = []

    errors = validator.validate_report(invalid_report)

    assert any("learning_binding evidence_input_refs" in error for error in errors)
    assert any("learning_binding admission_refs" in error for error in errors)
    assert any("learning_binding retention_refs" in error for error in errors)


def test_mode_binding_must_match_projected_mode() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["mode_binding"]["projected_mode"] = "real"

    errors = validator.validate_report(invalid_report)

    assert any("mode_binding projected_mode must match mode" in error for error in errors)
    assert invalid_report["loops"][0]["mode"] != invalid_report["loops"][0]["mode_binding"][
        "projected_mode"
    ]
    assert invalid_report["loops"][0]["mode_binding"]["projected_mode"] == "real"


def test_mode_binding_cannot_claim_transition_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["mode_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["mode_transition"] = True
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("mode_binding read_only must be true" in error for error in errors)
    assert any("mode_binding mode_transition must be false" in error for error in errors)
    assert any("mode_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["mode_transition"] is True


def test_mode_binding_requires_allowed_mode_and_separation_guards() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["mode_binding"]
    invalid_binding["allowed_modes"] = ["real"]
    invalid_binding["separation_refs"] = []
    invalid_binding["real_execution_guard_refs"] = []

    errors = validator.validate_report(invalid_report)

    assert any("mode_binding projected_mode must be allowed" in error for error in errors)
    assert any("mode_binding separation_refs" in error for error in errors)
    assert any("mode_binding real_execution_guard_refs" in error for error in errors)


def test_rollback_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["rollback_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("rollback_binding read_only must be true" in error for error in errors)
    assert any("rollback_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_missing_evidence_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    missing_binding = invalid_report["loops"][0]["evidence_bindings"].pop()

    errors = validator.validate_report(invalid_report)

    assert any("missing evidence binding" in error for error in errors)
    assert missing_binding["evidence_ref"] in invalid_report["loops"][0]["required_evidence"]
    assert missing_binding not in invalid_report["loops"][0]["evidence_bindings"]


def test_duplicate_evidence_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["evidence_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["evidence_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate evidence binding" in error for error in errors)
    assert invalid_report["loops"][0]["evidence_bindings"][0]["evidence_ref"]
    assert len(invalid_report["loops"][0]["evidence_bindings"]) > len(
        invalid_report["loops"][0]["required_evidence"]
    )


def test_evidence_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["evidence_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("read_only must be true" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_step_receipts_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_receipt = invalid_report["loops"][0]["step_receipts"][0]
    invalid_receipt["metadata"]["read_only"] = False
    invalid_receipt["metadata"]["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("step receipt 0 read_only must be true" in error for error in errors)
    assert any("step receipt 0 terminal_closure must be false" in error for error in errors)
    assert invalid_receipt["metadata"]["read_only"] is False


def test_step_receipt_errors_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["step_receipts"][0]["errors"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("step receipt 0 errors must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["step_receipts"][0]["errors"] == ["different_gap"]


def test_closure_report_cannot_claim_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_closure = invalid_report["loops"][0]["closure_report"]
    invalid_closure["closed"] = True
    invalid_closure["metadata"]["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("closure_report closed must be false" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_closure["closed"] is True


def test_closure_report_gaps_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["closure_report"]["unresolved_gaps"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("unresolved_gaps must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["closure_report"]["unresolved_gaps"] == ["different_gap"]


def test_closure_report_evidence_complete_must_match_missing_evidence() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["closure_report"]["evidence_complete"] = True

    errors = validator.validate_report(invalid_report)

    assert any("evidence_complete does not match missing evidence" in error for error in errors)
    assert invalid_report["loops"][0]["missing_evidence"]
    assert invalid_report["loops"][0]["closure_report"]["evidence_complete"] is True


def test_verified_loop_cannot_miss_evidence() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("verified or closed loop cannot miss evidence" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "verified"
    assert invalid_report["loops"][0]["missing_evidence"]


def test_verified_loop_cannot_miss_authority() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("verified or closed loop cannot miss authority" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "verified"
    assert invalid_report["loops"][0]["missing_authority"]


def test_unexpected_report_field_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["extra"] = "forbidden"

    errors = validator.validate_report(invalid_report)

    assert "report has unexpected field: extra" in errors
    assert invalid_report["extra"] == "forbidden"
    assert len(errors) >= 1


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] holistic_loop_read_model_current_output" in streams.out
    assert streams.err == ""


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(json_path, "payload")

    assert json_path.exists()
    assert json_path.name == "payload.json"
