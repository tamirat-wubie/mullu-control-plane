"""Tests for Component Harness promotion gate-satisfaction evaluator reports.

Purpose: prove record-only evidence can satisfy evidence gates while action
gates, promotion approval, router mutation, authority, and terminal closure
remain blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_gate_satisfaction_evaluator
and promotion gate-satisfaction evaluator runtime.
Invariants: record-evidence gate satisfaction is not promotion authority; action
gates stay unsatisfied; no evaluator output grants live authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_gate_satisfaction_evaluator import (
    build_component_route_family_promotion_gate_satisfaction_evaluator,
)
from scripts.validate_component_route_family_promotion_gate_satisfaction_evaluator import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_gate_satisfaction_evaluator,
    write_component_route_family_promotion_gate_satisfaction_evaluator_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_gate_satisfaction_evaluator.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _evaluations(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    evaluations = payload["gate_evaluations"]
    assert isinstance(evaluations, list)
    return {
        str(evaluation["gate_id"]): evaluation
        for evaluation in evaluations
        if isinstance(evaluation, dict)
    }


def test_component_route_family_promotion_gate_satisfaction_evaluator_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator()
    output_path = tmp_path / "component-route-family-promotion-gate-satisfaction-evaluator-validation.json"

    written_path = write_component_route_family_promotion_gate_satisfaction_evaluator_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.gate_evaluation_count == 4
    assert validation.record_evidence_satisfied_gate_count == 4
    assert validation.action_satisfied_gate_count == 0
    assert validation.authority_decision_count == 0
    assert validation.authority_grant_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_gate_satisfaction_evaluator_validation.json"


def test_component_route_family_promotion_gate_satisfaction_evaluator_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_gate_satisfaction_evaluator()
    evaluations = _evaluations(example)
    route_gate = evaluations["route_binding_gate"]
    authority_gate = evaluations["authority_upgrade_gate"]

    assert example == projection
    assert example["all_record_evidence_gates_satisfied"] is True
    assert example["all_action_gates_satisfied"] is False
    assert example["gate_satisfaction_is_not_promotion_authority"] is True
    assert example["authority_fuse_enforced"] is True
    assert example["authority_fuse_refs"] == example["authority_fuse_blocking_refs"]
    assert len(example["authority_fuse_refs"]) == 1
    assert example["ready_for_promotion"] is False
    assert example["summary"]["record_evidence_satisfied_gate_count"] == 4
    assert example["summary"]["action_satisfied_gate_count"] == 0
    assert example["summary"]["authority_decision_count"] == 0
    assert example["summary"]["promotion_approval_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert route_gate["satisfaction_state"] == "satisfied_record_only"
    assert route_gate["satisfies_evidence_requirement"] is True
    assert route_gate["satisfies_action_requirement"] is False
    assert route_gate["authority_fuse_blocks_promotion"] is True
    assert route_gate["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert authority_gate["grants_connector_authority"] is False
    assert authority_gate["requires_separate_authority_decision"] is True
    assert authority_gate["requires_external_authority_upgrade_evidence"] is True


def test_component_route_family_promotion_gate_satisfaction_evaluator_reject_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    evaluations = _evaluations(payload)
    authority_gate = evaluations["authority_upgrade_gate"]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    payload["authority_fuse_enforced"] = False
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = []
    authority_gate["grants_connector_authority"] = True
    authority_gate["requires_separate_authority_decision"] = False
    authority_gate["authority_fuse_blocks_promotion"] = False
    authority_gate["authority_fuse_refs"] = []
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "authority_fuse_enforced must be true" in serialized_errors
    assert "authority_fuse_refs must contain exactly one target component fuse" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "requires_separate_authority_decision must be true" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "authority_fuse_refs must contain exactly one authority fuse" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_gate_satisfaction_evaluator_reject_missing_gate(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    evaluations = payload["gate_evaluations"]
    assert isinstance(evaluations, list)
    payload["gate_evaluations"] = [
        evaluation
        for evaluation in evaluations
        if isinstance(evaluation, dict) and evaluation.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "gate_evaluations must cover exactly" in serialized_errors
    assert "summary.gate_evaluation_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_gate_satisfaction_evaluator_reject_record_satisfaction_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    evaluations = _evaluations(payload)
    route_gate = evaluations["route_binding_gate"]
    route_gate["evaluation_state"] = "not_evaluated"
    route_gate["satisfaction_state"] = "not_satisfied"
    route_gate["record_evidence_satisfies_gate"] = False
    route_gate["satisfies_evidence_requirement"] = False
    route_gate["proof_state"] = "Unknown"
    route_gate["accepted_record_refs"] = []

    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evaluation_state must be evaluated" in serialized_errors
    assert "satisfaction_state must be satisfied_record_only" in serialized_errors
    assert "record_evidence_satisfies_gate must be true" in serialized_errors
    assert "satisfies_evidence_requirement must be true" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "accepted_record_refs must contain only the source record id" in serialized_errors
    assert "summary.record_evidence_satisfied_gate_count" in serialized_errors


def test_component_route_family_promotion_gate_satisfaction_evaluator_reject_promotion_authority_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    evaluations = _evaluations(payload)
    product_gate = evaluations["product_specific_boundary_gate"]
    payload["all_action_gates_satisfied"] = True
    payload["gate_satisfaction_is_not_promotion_authority"] = False
    payload["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    payload["promotion_approval_refs"] = ["approval://promotion/product_specific_boundary_gate"]
    product_gate["satisfies_action_requirement"] = True
    product_gate["blocks_promotion"] = False
    product_gate["gate_satisfaction_is_not_promotion_authority"] = False
    product_gate["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_gate["promotion_approval_refs"] = ["approval://promotion/product_specific_boundary_gate"]

    validation = validate_component_route_family_promotion_gate_satisfaction_evaluator(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "all_action_gates_satisfied must be false" in serialized_errors
    assert "gate_satisfaction_is_not_promotion_authority must be true" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "promotion_approval_refs must remain empty" in serialized_errors
    assert "satisfies_action_requirement must be false" in serialized_errors
    assert "blocks_promotion must be true" in serialized_errors
    assert "summary.action_satisfied_gate_count" in serialized_errors
