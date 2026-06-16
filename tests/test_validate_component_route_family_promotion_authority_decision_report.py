"""Tests for Component Harness promotion authority decision reports.

Purpose: prove gate-satisfaction evidence can feed denial-only authority
decisions while action gates, route binding, lifecycle transition, promotion
approval, authority grants, and terminal closure remain blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_authority_decision_report
and promotion authority decision report runtime.
Invariants: authority decisions are denial-only; no decision grants live
authority or mutates router inventory.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_authority_decision_report import (
    build_component_route_family_promotion_authority_decision_report,
)
from scripts.validate_component_route_family_promotion_authority_decision_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_authority_decision_report,
    write_component_route_family_promotion_authority_decision_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_authority_decision_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _authority_decisions(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    authority_decisions = payload["authority_decisions"]
    assert isinstance(authority_decisions, list)
    return {
        str(authority_decision["gate_id"]): authority_decision
        for authority_decision in authority_decisions
        if isinstance(authority_decision, dict)
    }


def test_component_route_family_promotion_authority_decision_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_authority_decision_report()
    output_path = tmp_path / "component-route-family-promotion-authority-decision-report-validation.json"

    written_path = write_component_route_family_promotion_authority_decision_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.authority_decision_count == 4
    assert validation.authority_denial_count == 4
    assert validation.authority_grant_count == 0
    assert validation.promotion_approval_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_authority_decision_report_validation.json"


def test_component_route_family_promotion_authority_decision_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_authority_decision_report()
    decisions = _authority_decisions(example)
    route_decision = decisions["route_binding_gate"]
    authority_decision = decisions["authority_upgrade_gate"]

    assert example == projection
    assert example["authority_decision_state"] == "denied_pending_governed_witnesses"
    assert example["promotion_decision"] == "blocked_authority_not_granted"
    assert example["all_authority_decisions_denied"] is True
    assert example["all_authority_grants_blocked"] is True
    assert example["ready_for_promotion"] is False
    assert example["summary"]["authority_decision_count"] == 4
    assert example["summary"]["authority_denial_count"] == 4
    assert example["summary"]["authority_grant_count"] == 0
    assert example["summary"]["promotion_approval_count"] == 0
    assert route_decision["decision_state"] == "denied"
    assert route_decision["route_binding_authorized"] is False
    assert route_decision["requires_route_binding_decision"] is True
    assert authority_decision["connector_authority_authorized"] is False
    assert authority_decision["requires_authority_upgrade_witness"] is True


def test_component_route_family_promotion_authority_decision_report_reject_authority_grant_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decisions = _authority_decisions(payload)
    authority_gate = decisions["authority_upgrade_gate"]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    payload["authority_grant_refs"] = ["authority://promotion/grant"]
    authority_gate["authority_granted"] = True
    authority_gate["connector_authority_authorized"] = True
    authority_gate["can_call_connector"] = True
    authority_gate["authority_grant_refs"] = ["authority://promotion/grant"]
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_authority_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "ready_for_promotion" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "connector_authority_authorized must be false" in serialized_errors
    assert "authority_grant_refs must remain empty" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_authority_decision_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    authority_decisions = payload["authority_decisions"]
    assert isinstance(authority_decisions, list)
    payload["authority_decisions"] = [
        authority_decision
        for authority_decision in authority_decisions
        if isinstance(authority_decision, dict) and authority_decision.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_authority_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_decisions must cover exactly" in serialized_errors
    assert "summary.authority_decision_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_authority_decision_report_reject_record_satisfaction_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decisions = _authority_decisions(payload)
    route_gate = decisions["route_binding_gate"]
    route_gate["decision_basis"] = "live_operator_evidence"
    route_gate["proof_state"] = "Unknown"
    route_gate["record_evidence_satisfied"] = False
    route_gate["satisfied_gate_evaluation_refs"] = []
    route_gate["accepted_record_refs"] = []

    validation = validate_component_route_family_promotion_authority_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be record_evidence_only" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "record_evidence_satisfied must be true" in serialized_errors
    assert "satisfied_gate_evaluation_refs must contain only the source gate id" in serialized_errors
    assert "accepted_record_refs must contain only the source record id" in serialized_errors
    assert "summary.record_evidence_satisfied_gate_count" in serialized_errors


def test_component_route_family_promotion_authority_decision_report_reject_promotion_approval_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decisions = _authority_decisions(payload)
    product_gate = decisions["product_specific_boundary_gate"]
    payload["promotion_decision"] = "approved"
    payload["all_authority_decisions_denied"] = False
    payload["authority_decision_is_not_promotion_approval"] = False
    payload["route_binding_decision_refs"] = ["route-binding://promotion/governed_connector_framework"]
    payload["promotion_approval_refs"] = ["approval://promotion/product_specific_boundary_gate"]
    product_gate["blocks_promotion"] = False
    product_gate["decision_is_not_promotion_approval"] = False
    product_gate["route_binding_authorized"] = True
    product_gate["promotion_approval_refs"] = ["approval://promotion/product_specific_boundary_gate"]

    validation = validate_component_route_family_promotion_authority_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "promotion_decision must be blocked_authority_not_granted" in serialized_errors
    assert "all_authority_decisions_denied must be true" in serialized_errors
    assert "authority_decision_is_not_promotion_approval must be true" in serialized_errors
    assert "route_binding_decision_refs must remain empty" in serialized_errors
    assert "promotion_approval_refs must remain empty" in serialized_errors
    assert "blocks_promotion must be true" in serialized_errors
    assert "decision_is_not_promotion_approval must be true" in serialized_errors
    assert "route_binding_authorized must be false" in serialized_errors
    assert "summary.promotion_approval_count" in serialized_errors
