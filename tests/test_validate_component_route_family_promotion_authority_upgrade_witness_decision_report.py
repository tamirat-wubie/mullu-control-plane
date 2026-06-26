"""Tests for Component Harness promotion authority-upgrade witness decisions.

Purpose: prove a denied lifecycle-transition decision can feed one denial-only
authority-upgrade decision while authority grants, authority-witness emission,
authority-envelope mutation, promotion approval, and terminal closure remain
blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_authority_upgrade_witness_decision_report
and promotion authority-upgrade witness decision report runtime.
Invariants: authority-upgrade decisions are not authority-upgrade witnesses;
denied authority decisions cannot change authority level.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_authority_upgrade_witness_decision_report import (
    build_component_route_family_promotion_authority_upgrade_witness_decision_report,
)
from scripts.validate_component_route_family_promotion_authority_upgrade_witness_decision_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_authority_upgrade_witness_decision_report,
    write_component_route_family_promotion_authority_upgrade_witness_decision_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_authority_upgrade_witness_decision_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _authority_upgrade_decision(payload: dict[str, object]) -> dict[str, object]:
    decisions = payload["authority_upgrade_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    decision = decisions[0]
    assert isinstance(decision, dict)
    return decision


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report()
    output_path = tmp_path / "component-route-family-promotion-authority-upgrade-decision-validation.json"

    written_path = write_component_route_family_promotion_authority_upgrade_witness_decision_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.authority_upgrade_decision_count == 1
    assert validation.authority_upgrade_denial_count == 1
    assert validation.authority_upgrade_authorization_count == 0
    assert validation.authority_level_change_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_authority_upgrade_witness_decision_report_validation.json"


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_authority_upgrade_witness_decision_report()
    decision = _authority_upgrade_decision(example)

    assert example == projection
    assert example["authority_upgrade_decision_state"] == "denied_pending_authority_upgrade_witness"
    assert example["promotion_decision"] == "blocked_authority_upgrade_not_authorized"
    assert example["current_authority_level"] == "approval_required"
    assert example["requested_authority_level"] == "approved_live_action"
    assert example["resulting_authority_level"] == "approval_required"
    assert example["authority_upgrade_authorized"] is False
    assert example["authority_level_changed"] is False
    assert example["authority_witness_emitted"] is False
    assert example["authority_envelope_mutated"] is False
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert example["ready_for_promotion"] is False
    assert example["summary"]["authority_upgrade_decision_count"] == 1
    assert example["summary"]["authority_upgrade_denial_count"] == 1
    assert example["summary"]["authority_upgrade_authorization_count"] == 0
    assert example["summary"]["authority_level_change_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert decision["gate_id"] == "authority_upgrade_gate"
    assert decision["decision_state"] == "denied"
    assert decision["authority_fuse_blocks_promotion"] is True
    assert decision["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert decision["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["requires_external_authority_upgrade_evidence"] is True
    assert decision["authority_upgrade_authorized"] is False
    assert decision["requires_authority_upgrade_witness"] is True


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_reject_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _authority_upgrade_decision(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["authority_upgrade_authorized"] = True
    payload["authority_level_changed"] = True
    payload["resulting_authority_level"] = "approved_live_action"
    payload["authority_granted"] = True
    payload["ready_for_promotion"] = True
    decision["authority_upgrade_authorized"] = True
    decision["authority_level_changed"] = True
    decision["resulting_authority_level"] = "approved_live_action"
    decision["authority_granted"] = True
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "resulting_authority_level must be approval_required" in serialized_errors
    assert "authority_upgrade_authorized must be false" in serialized_errors
    assert "authority_level_changed must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "ready_for_promotion" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["authority_upgrade_decisions"] = []

    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_upgrade_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_reject_proof_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _authority_upgrade_decision(payload)
    decision["decision_basis"] = "live_operator_authority_upgrade"
    decision["proof_state"] = "Unknown"
    decision["record_evidence_satisfied"] = False
    decision["source_lifecycle_transition_decision_denied"] = False
    decision["source_lifecycle_transition_decision_refs"] = []
    decision["accepted_record_refs"] = []

    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be lifecycle_transition_decision_denial" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "record_evidence_satisfied must be true" in serialized_errors
    assert "source_lifecycle_transition_decision_denied must be true" in serialized_errors
    assert "source_lifecycle_transition_decision_refs must contain only the source lifecycle decision id" in serialized_errors
    assert "accepted_record_refs must contain only the source record id" in serialized_errors


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _authority_upgrade_decision(payload)
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    decision["authority_fuse_blocks_promotion"] = False
    decision["requires_external_authority_upgrade_evidence"] = False
    decision["authority_fuse_refs"] = ["component_authority_fuse.other_component.foundation.v1"]
    decision["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one target component fuse" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "requires_external_authority_upgrade_evidence must be true" in serialized_errors
    assert "authority-upgrade decision authority_fuse_refs must match report authority_fuse_refs" in serialized_errors


def test_component_route_family_promotion_authority_upgrade_witness_decision_report_reject_witness_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _authority_upgrade_decision(payload)
    payload["authority_upgrade_witness_refs"] = ["receipt://authority-upgrade/governed_connector_framework"]
    payload["authority_envelope_mutation_refs"] = ["authority-envelope://mutation/gmail_account_binding_gate"]
    payload["authority_grant_refs"] = ["authority-grant://gmail_account_binding_gate"]
    payload["authority_upgrade_decision_is_not_authority_witness"] = False
    payload["authority_upgrade_decision_is_not_authority_envelope_mutation"] = False
    decision["authority_upgrade_witness_refs"] = ["receipt://authority-upgrade/governed_connector_framework"]
    decision["authority_envelope_mutation_refs"] = ["authority-envelope://mutation/gmail_account_binding_gate"]
    decision["authority_grant_refs"] = ["authority-grant://gmail_account_binding_gate"]
    decision["decision_is_not_authority_witness"] = False
    decision["authority_witness_emitted"] = True
    decision["authority_envelope_mutated"] = True

    validation = validate_component_route_family_promotion_authority_upgrade_witness_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_upgrade_witness_refs must remain empty" in serialized_errors
    assert "authority_envelope_mutation_refs must remain empty" in serialized_errors
    assert "authority_grant_refs must remain empty" in serialized_errors
    assert "authority_upgrade_decision_is_not_authority_witness must be true" in serialized_errors
    assert "authority_upgrade_decision_is_not_authority_envelope_mutation must be true" in serialized_errors
    assert "authority_witness_emitted must be false" in serialized_errors
    assert "authority_envelope_mutated must be false" in serialized_errors
    assert "summary.authority_witness_emission_count" in serialized_errors
