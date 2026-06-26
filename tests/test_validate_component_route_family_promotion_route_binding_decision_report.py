"""Tests for Component Harness promotion route-binding decision reports.

Purpose: prove a denied authority decision can feed one denial-only
route-binding decision while router inventory mutation, selected-component
binding, promotion approval, authority grants, and terminal closure remain
blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_route_binding_decision_report
and promotion route-binding decision report runtime.
Invariants: route-binding decisions are not router inventory deltas; denied
route binding cannot promote a route family.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_route_binding_decision_report import (
    build_component_route_family_promotion_route_binding_decision_report,
)
from scripts.validate_component_route_family_promotion_route_binding_decision_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_route_binding_decision_report,
    write_component_route_family_promotion_route_binding_decision_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_route_binding_decision_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _route_binding_decision(payload: dict[str, object]) -> dict[str, object]:
    decisions = payload["route_binding_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    decision = decisions[0]
    assert isinstance(decision, dict)
    return decision


def test_component_route_family_promotion_route_binding_decision_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_route_binding_decision_report()
    output_path = tmp_path / "component-route-family-promotion-route-binding-decision-report-validation.json"

    written_path = write_component_route_family_promotion_route_binding_decision_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.route_binding_decision_count == 1
    assert validation.route_binding_denial_count == 1
    assert validation.route_binding_authorization_count == 0
    assert validation.router_inventory_mutation_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_route_binding_decision_report_validation.json"


def test_component_route_family_promotion_route_binding_decision_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_route_binding_decision_report()
    decision = _route_binding_decision(example)

    assert example == projection
    assert example["route_binding_decision_state"] == "denied_pending_router_inventory_witness"
    assert example["promotion_decision"] == "blocked_route_binding_not_authorized"
    assert example["route_binding_authorized"] is False
    assert example["router_inventory_delta_authorized"] is False
    assert example["mutates_router_inventory"] is False
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert example["ready_for_promotion"] is False
    assert example["summary"]["route_binding_decision_count"] == 1
    assert example["summary"]["route_binding_denial_count"] == 1
    assert example["summary"]["route_binding_authorization_count"] == 0
    assert example["summary"]["router_inventory_mutation_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert decision["gate_id"] == "route_binding_gate"
    assert decision["decision_state"] == "denied"
    assert decision["authority_fuse_blocks_promotion"] is True
    assert decision["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert decision["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["requires_external_authority_upgrade_evidence"] is True
    assert decision["route_binding_authorized"] is False
    assert decision["requires_component_route_binding_receipt"] is True
    assert decision["requires_router_inventory_delta"] is True


def test_component_route_family_promotion_route_binding_decision_report_reject_route_authorization_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _route_binding_decision(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["route_binding_authorized"] = True
    payload["router_inventory_delta_authorized"] = True
    payload["ready_for_promotion"] = True
    decision["route_binding_authorized"] = True
    decision["router_inventory_delta_authorized"] = True
    decision["selected_component_binding_authorized"] = True
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_route_binding_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "route_binding_authorized must be false" in serialized_errors
    assert "router_inventory_delta_authorized must be false" in serialized_errors
    assert "selected_component_binding_authorized must be false" in serialized_errors
    assert "ready_for_promotion" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_route_binding_decision_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["route_binding_decisions"] = []

    validation = validate_component_route_family_promotion_route_binding_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "route_binding_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_route_binding_decision_report_reject_record_satisfaction_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _route_binding_decision(payload)
    decision["decision_basis"] = "live_operator_route_binding"
    decision["proof_state"] = "Unknown"
    decision["record_evidence_satisfied"] = False
    decision["source_authority_decision_denied"] = False
    decision["source_authority_decision_refs"] = []
    decision["accepted_record_refs"] = []

    validation = validate_component_route_family_promotion_route_binding_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be authority_decision_denial" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "record_evidence_satisfied must be true" in serialized_errors
    assert "source_authority_decision_denied must be true" in serialized_errors
    assert "source_authority_decision_refs must contain only the source authority decision id" in serialized_errors
    assert "accepted_record_refs must contain only the source record id" in serialized_errors


def test_component_route_family_promotion_route_binding_decision_report_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _route_binding_decision(payload)
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    decision["authority_fuse_blocks_promotion"] = False
    decision["requires_external_authority_upgrade_evidence"] = False
    decision["authority_fuse_refs"] = ["component_authority_fuse.other_component.foundation.v1"]
    decision["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_route_binding_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one target component fuse" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "requires_external_authority_upgrade_evidence must be true" in serialized_errors
    assert "route-binding decision authority_fuse_refs must match report authority_fuse_refs" in serialized_errors


def test_component_route_family_promotion_route_binding_decision_report_reject_router_inventory_mutation_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _route_binding_decision(payload)
    payload["route_binding_receipt_refs"] = ["receipt://component-route-binding/governed_connector_framework"]
    payload["router_inventory_delta_refs"] = ["router-inventory://delta/governed_connector_framework"]
    payload["selected_component_binding_refs"] = ["component://gmail_account_binding_gate"]
    payload["route_binding_decision_is_not_router_mutation"] = False
    decision["mutates_router_inventory"] = True
    decision["decision_is_not_router_mutation"] = False
    decision["route_binding_receipt_refs"] = ["receipt://component-route-binding/governed_connector_framework"]
    decision["router_inventory_delta_refs"] = ["router-inventory://delta/governed_connector_framework"]
    decision["selected_component_binding_refs"] = ["component://gmail_account_binding_gate"]

    validation = validate_component_route_family_promotion_route_binding_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "route_binding_receipt_refs must remain empty" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "selected_component_binding_refs must remain empty" in serialized_errors
    assert "route_binding_decision_is_not_router_mutation must be true" in serialized_errors
    assert "mutates_router_inventory must be false" in serialized_errors
    assert "decision_is_not_router_mutation must be true" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
