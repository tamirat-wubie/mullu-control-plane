"""Tests for Component Harness promotion lifecycle-transition decision reports.

Purpose: prove a denied route-binding decision can feed one denial-only
lifecycle-transition decision while lifecycle state change, promotion approval,
authority grants, route binding, and terminal closure remain blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_lifecycle_transition_decision_report
and promotion lifecycle-transition decision report runtime.
Invariants: lifecycle-transition decisions are not lifecycle transition
receipts; denied lifecycle decisions cannot change component state.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_lifecycle_transition_decision_report import (
    build_component_route_family_promotion_lifecycle_transition_decision_report,
)
from scripts.validate_component_route_family_promotion_lifecycle_transition_decision_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_lifecycle_transition_decision_report,
    write_component_route_family_promotion_lifecycle_transition_decision_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_lifecycle_transition_decision_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _lifecycle_transition_decision(payload: dict[str, object]) -> dict[str, object]:
    decisions = payload["lifecycle_transition_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    decision = decisions[0]
    assert isinstance(decision, dict)
    return decision


def test_component_route_family_promotion_lifecycle_transition_decision_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report()
    output_path = tmp_path / "component-route-family-promotion-lifecycle-transition-decision-validation.json"

    written_path = write_component_route_family_promotion_lifecycle_transition_decision_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.lifecycle_transition_decision_count == 1
    assert validation.lifecycle_transition_denial_count == 1
    assert validation.lifecycle_transition_authorization_count == 0
    assert validation.lifecycle_state_change_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_lifecycle_transition_decision_report_validation.json"


def test_component_route_family_promotion_lifecycle_transition_decision_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_lifecycle_transition_decision_report()
    decision = _lifecycle_transition_decision(example)

    assert example == projection
    assert example["lifecycle_transition_decision_state"] == "denied_pending_route_binding_witness"
    assert example["promotion_decision"] == "blocked_lifecycle_transition_not_authorized"
    assert example["current_lifecycle_state"] == "approval_required"
    assert example["requested_lifecycle_state"] == "approved_live_action"
    assert example["resulting_lifecycle_state"] == "approval_required"
    assert example["lifecycle_transition_authorized"] is False
    assert example["lifecycle_state_changed"] is False
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert example["ready_for_promotion"] is False
    assert example["summary"]["lifecycle_transition_decision_count"] == 1
    assert example["summary"]["lifecycle_transition_denial_count"] == 1
    assert example["summary"]["lifecycle_transition_authorization_count"] == 0
    assert example["summary"]["lifecycle_state_change_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert decision["gate_id"] == "lifecycle_transition_gate"
    assert decision["decision_state"] == "denied"
    assert decision["authority_fuse_blocks_promotion"] is True
    assert decision["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert decision["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["requires_external_authority_upgrade_evidence"] is True
    assert decision["lifecycle_transition_authorized"] is False
    assert decision["lifecycle_state_changed"] is False
    assert decision["requires_lifecycle_transition_receipt"] is True


def test_component_route_family_promotion_lifecycle_transition_decision_report_reject_state_change_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _lifecycle_transition_decision(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["lifecycle_transition_authorized"] = True
    payload["lifecycle_state_changed"] = True
    payload["resulting_lifecycle_state"] = "approved_live_action"
    payload["ready_for_promotion"] = True
    decision["lifecycle_transition_authorized"] = True
    decision["lifecycle_state_changed"] = True
    decision["resulting_lifecycle_state"] = "approved_live_action"
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "resulting_lifecycle_state must remain approval_required" in serialized_errors
    assert "lifecycle_transition_authorized must be false" in serialized_errors
    assert "lifecycle_state_changed must be false" in serialized_errors
    assert "ready_for_promotion" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_lifecycle_transition_decision_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["lifecycle_transition_decisions"] = []

    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "lifecycle_transition_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_lifecycle_transition_decision_report_reject_proof_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _lifecycle_transition_decision(payload)
    decision["decision_basis"] = "live_operator_lifecycle_transition"
    decision["proof_state"] = "Unknown"
    decision["record_evidence_satisfied"] = False
    decision["source_route_binding_decision_denied"] = False
    decision["source_route_binding_decision_refs"] = []
    decision["accepted_record_refs"] = []

    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be route_binding_decision_denial" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "record_evidence_satisfied must be true" in serialized_errors
    assert "source_route_binding_decision_denied must be true" in serialized_errors
    assert "source_route_binding_decision_refs must contain only the source route-binding decision id" in serialized_errors
    assert "accepted_record_refs must contain only the source record id" in serialized_errors


def test_component_route_family_promotion_lifecycle_transition_decision_report_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _lifecycle_transition_decision(payload)
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    decision["authority_fuse_blocks_promotion"] = False
    decision["requires_external_authority_upgrade_evidence"] = False
    decision["authority_fuse_refs"] = ["component_authority_fuse.other_component.foundation.v1"]
    decision["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one target component fuse" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "requires_external_authority_upgrade_evidence must be true" in serialized_errors
    assert "lifecycle transition decision authority_fuse_refs must match report authority_fuse_refs" in serialized_errors


def test_component_route_family_promotion_lifecycle_transition_decision_report_reject_lifecycle_receipt_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _lifecycle_transition_decision(payload)
    payload["lifecycle_transition_receipt_refs"] = ["receipt://component-lifecycle-transition/governed_connector_framework"]
    payload["route_binding_receipt_refs"] = ["receipt://component-route-binding/governed_connector_framework"]
    payload["router_inventory_delta_refs"] = ["router-inventory://delta/governed_connector_framework"]
    payload["lifecycle_transition_decision_is_not_lifecycle_receipt"] = False
    decision["lifecycle_transition_receipt_refs"] = [
        "receipt://component-lifecycle-transition/governed_connector_framework"
    ]
    decision["route_binding_receipt_refs"] = ["receipt://component-route-binding/governed_connector_framework"]
    decision["router_inventory_delta_refs"] = ["router-inventory://delta/governed_connector_framework"]
    decision["decision_is_not_lifecycle_receipt"] = False
    decision["lifecycle_state_changed"] = True

    validation = validate_component_route_family_promotion_lifecycle_transition_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "lifecycle_transition_receipt_refs must remain empty" in serialized_errors
    assert "route_binding_receipt_refs must remain empty" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "lifecycle_transition_decision_is_not_lifecycle_receipt must be true" in serialized_errors
    assert "lifecycle_state_changed must be false" in serialized_errors
    assert "decision_is_not_lifecycle_receipt must be true" in serialized_errors
    assert "summary.lifecycle_state_change_count" in serialized_errors
