"""Tests for Component Harness promotion product-ownership decisions.

Purpose: prove a denied authority-upgrade decision can feed one denial-only
product-specific ownership decision while product ownership, product bundle
binding, authority grants, route mutations, promotion approval, and terminal
closure remain blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_product_ownership_decision_report
and promotion product-ownership decision report runtime.
Invariants: product-ownership decisions are not ownership witnesses; generic
connector surfaces are not product-specific authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (
    build_component_route_family_promotion_product_ownership_decision_report,
)
from scripts.validate_component_route_family_promotion_product_ownership_decision_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_product_ownership_decision_report,
    write_component_route_family_promotion_product_ownership_decision_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_product_ownership_decision_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _product_ownership_decision(payload: dict[str, object]) -> dict[str, object]:
    decisions = payload["product_ownership_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    decision = decisions[0]
    assert isinstance(decision, dict)
    return decision


def test_component_route_family_promotion_product_ownership_decision_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_product_ownership_decision_report()
    output_path = tmp_path / "component-route-family-promotion-product-ownership-decision-validation.json"

    written_path = write_component_route_family_promotion_product_ownership_decision_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.product_ownership_decision_count == 1
    assert validation.product_ownership_denial_count == 1
    assert validation.product_ownership_authorization_count == 0
    assert validation.product_bundle_binding_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_product_ownership_decision_report_validation.json"


def test_component_route_family_promotion_product_ownership_decision_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_product_ownership_decision_report()
    decision = _product_ownership_decision(example)

    assert example == projection
    assert example["product_ownership_decision_state"] == "denied_pending_product_specific_ownership_witness"
    assert example["promotion_decision"] == "blocked_product_ownership_not_authorized"
    assert example["target_product_bundle_id"] == "personal_assistant_v0"
    assert example["product_ownership_decision_issued"] is True
    assert example["product_ownership_authorized"] is False
    assert example["product_bundle_binding_authorized"] is False
    assert example["product_ownership_witness_emitted"] is False
    assert example["product_route_ownership_bound"] is False
    assert example["generic_connector_surface_is_not_product_specific_authority"] is True
    assert example["summary"]["product_ownership_decision_count"] == 1
    assert example["summary"]["product_ownership_denial_count"] == 1
    assert example["summary"]["product_ownership_authorization_count"] == 0
    assert example["summary"]["product_bundle_binding_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["gate_id"] == "product_specific_ownership_gate"
    assert decision["decision_state"] == "denied"
    assert decision["authority_fuse_blocks_promotion"] is True
    assert decision["requires_external_authority_upgrade_evidence"] is True
    assert decision["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert decision["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["requires_product_ownership_witness"] is True


def test_component_route_family_promotion_product_ownership_decision_report_reject_ownership_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _product_ownership_decision(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["product_ownership_authorized"] = True
    payload["product_bundle_binding_authorized"] = True
    payload["product_route_ownership_bound"] = True
    payload["ready_for_promotion"] = True
    decision["product_ownership_authorized"] = True
    decision["product_bundle_binding_authorized"] = True
    decision["product_route_ownership_bound"] = True
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_product_ownership_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "product_ownership_authorized must be false" in serialized_errors
    assert "product_bundle_binding_authorized must be false" in serialized_errors
    assert "product_route_ownership_bound must be false" in serialized_errors
    assert "ready_for_promotion" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_product_ownership_decision_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["product_ownership_decisions"] = []

    validation = validate_component_route_family_promotion_product_ownership_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "product_ownership_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_product_ownership_decision_report_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _product_ownership_decision(payload)
    decision["decision_basis"] = "live_product_owner_approval"
    decision["proof_state"] = "Unknown"
    decision["source_authority_upgrade_decision_denied"] = False
    decision["source_authority_upgrade_decision_refs"] = []
    decision["source_lifecycle_transition_decision_refs"] = []

    validation = validate_component_route_family_promotion_product_ownership_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be authority_upgrade_decision_denial" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "source_authority_upgrade_decision_denied must be true" in serialized_errors
    assert "source_authority_upgrade_decision_refs must contain only the source authority-upgrade id" in serialized_errors
    assert "source_lifecycle_transition_decision_refs must contain only the source lifecycle decision id" in serialized_errors


def test_component_route_family_promotion_product_ownership_decision_report_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _product_ownership_decision(payload)
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.foundation.v1"]
    payload["summary"]["authority_fuse_blocking_count"] = 0
    decision["authority_fuse_blocks_promotion"] = False
    decision["requires_external_authority_upgrade_evidence"] = False
    decision["authority_fuse_refs"] = ["component_authority_fuse.drifted.v1"]
    decision["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_product_ownership_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one component authority-fuse ref" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "requires_external_authority_upgrade_evidence must be true" in serialized_errors
    assert "product-ownership decision authority_fuse_refs must match report authority_fuse_refs" in serialized_errors
    assert "summary.authority_fuse_blocking_count" in serialized_errors


def test_component_route_family_promotion_product_ownership_decision_report_reject_witness_binding_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _product_ownership_decision(payload)
    payload["product_ownership_witness_refs"] = ["receipt://product-ownership/personal_assistant_v0"]
    payload["product_bundle_binding_refs"] = ["product-bundle://personal_assistant_v0/governed_connector_framework"]
    payload["authority_grant_refs"] = ["authority-grant://gmail_account_binding_gate"]
    payload["product_ownership_decision_is_not_product_ownership_witness"] = False
    payload["product_ownership_decision_is_not_product_bundle_binding"] = False
    decision["product_ownership_witness_refs"] = ["receipt://product-ownership/personal_assistant_v0"]
    decision["product_bundle_binding_refs"] = ["product-bundle://personal_assistant_v0/governed_connector_framework"]
    decision["authority_grant_refs"] = ["authority-grant://gmail_account_binding_gate"]
    decision["decision_is_not_product_ownership_witness"] = False
    decision["product_ownership_witness_emitted"] = True
    decision["authority_granted"] = True

    validation = validate_component_route_family_promotion_product_ownership_decision_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "product_ownership_witness_refs must remain empty" in serialized_errors
    assert "product_bundle_binding_refs must remain empty" in serialized_errors
    assert "authority_grant_refs must remain empty" in serialized_errors
    assert "product_ownership_decision_is_not_product_ownership_witness must be true" in serialized_errors
    assert "product_ownership_decision_is_not_product_bundle_binding must be true" in serialized_errors
    assert "product_ownership_witness_emitted must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "summary.product_ownership_witness_count" in serialized_errors
