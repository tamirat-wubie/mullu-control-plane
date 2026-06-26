"""Tests for Component Harness promotion terminal-closure denial reports.

Purpose: prove a denied product-ownership decision can feed one denial-only
terminal-closure decision while terminal certificates, closure claims,
promotion approval, authority grants, route mutations, and execution remain
blocked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_terminal_closure_denial_report
and promotion terminal-closure denial report runtime.
Invariants: terminal-closure denial reports are not terminal certificates and
cannot claim terminal closure.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_terminal_closure_denial_report import (
    build_component_route_family_promotion_terminal_closure_denial_report,
)
from scripts.validate_component_route_family_promotion_terminal_closure_denial_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_terminal_closure_denial_report,
    write_component_route_family_promotion_terminal_closure_denial_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_terminal_closure_denial_report.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _terminal_decision(payload: dict[str, object]) -> dict[str, object]:
    decisions = payload["terminal_closure_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    decision = decisions[0]
    assert isinstance(decision, dict)
    return decision


def test_component_route_family_promotion_terminal_closure_denial_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_terminal_closure_denial_report()
    output_path = tmp_path / "component-route-family-promotion-terminal-closure-denial-validation.json"

    written_path = write_component_route_family_promotion_terminal_closure_denial_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.terminal_closure_decision_count == 1
    assert validation.terminal_closure_denial_count == 1
    assert validation.terminal_closure_authorization_count == 0
    assert validation.terminal_certificate_mint_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_terminal_closure_denial_report_validation.json"


def test_component_route_family_promotion_terminal_closure_denial_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_terminal_closure_denial_report()
    decision = _terminal_decision(example)

    assert example == projection
    assert example["terminal_closure_decision_state"] == "denied_pending_terminal_closure_certificate"
    assert example["promotion_decision"] == "blocked_terminal_closure_not_authorized"
    assert example["terminal_closure_denial_issued"] is True
    assert example["terminal_closure_authorized"] is False
    assert example["terminal_certificate_minted"] is False
    assert example["terminal_closure_claimed"] is False
    assert example["can_claim_terminal_closure"] is False
    assert example["terminal_closure_denial_is_not_terminal_certificate"] is True
    assert example["summary"]["terminal_closure_decision_count"] == 1
    assert example["summary"]["terminal_closure_denial_count"] == 1
    assert example["summary"]["terminal_closure_authorization_count"] == 0
    assert example["summary"]["terminal_certificate_mint_count"] == 0
    assert example["summary"]["authority_fuse_blocking_count"] == 1
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["gate_id"] == "terminal_closure_gate"
    assert decision["decision_state"] == "denied"
    assert decision["authority_fuse_blocks_promotion"] is True
    assert decision["requires_external_authority_upgrade_evidence"] is True
    assert decision["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert decision["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert decision["requires_terminal_closure_certificate"] is True


def test_component_route_family_promotion_terminal_closure_denial_report_reject_closure_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _terminal_decision(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["terminal_closure_authorized"] = True
    payload["terminal_certificate_minted"] = True
    payload["terminal_closure_claimed"] = True
    payload["can_claim_terminal_closure"] = True
    decision["terminal_closure_authorized"] = True
    decision["terminal_certificate_minted"] = True
    decision["terminal_closure_claimed"] = True
    decision["can_claim_terminal_closure"] = True
    if "terminal_closure" in payload["blocked_actions"]:
        payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "terminal_closure_authorized must be false" in serialized_errors
    assert "terminal_certificate_minted must be false" in serialized_errors
    assert "terminal_closure_claimed must be false" in serialized_errors
    assert "can_claim_terminal_closure must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_terminal_closure_denial_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["terminal_closure_decisions"] = []

    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_terminal_closure_denial_report_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _terminal_decision(payload)
    decision["decision_basis"] = "terminal_certificate_present"
    decision["proof_state"] = "Unknown"
    decision["source_product_ownership_decision_denied"] = False
    decision["source_product_ownership_decision_refs"] = []
    decision["source_authority_upgrade_decision_refs"] = []

    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_basis must be product_ownership_decision_denial" in serialized_errors
    assert "proof_state must be Pass" in serialized_errors
    assert "source_product_ownership_decision_denied must be true" in serialized_errors
    assert "source_product_ownership_decision_refs must contain only the source product id" in serialized_errors
    assert "source_authority_upgrade_decision_refs must contain only the source authority id" in serialized_errors


def test_component_route_family_promotion_terminal_closure_denial_report_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _terminal_decision(payload)
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    payload["summary"]["authority_fuse_blocking_count"] = 0
    decision["authority_fuse_blocks_promotion"] = False
    decision["requires_external_authority_upgrade_evidence"] = False
    decision["authority_fuse_refs"] = ["component_authority_fuse.drifted.v1"]
    decision["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one component authority-fuse ref" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "requires_external_authority_upgrade_evidence must be true" in serialized_errors
    assert "terminal decision authority_fuse_refs must match report authority_fuse_refs" in serialized_errors
    assert "summary.authority_fuse_blocking_count" in serialized_errors


def test_component_route_family_promotion_terminal_closure_denial_report_reject_certificate_witness_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _terminal_decision(payload)
    payload["terminal_closure_certificate_refs"] = ["terminal-certificate://governed_connector_framework"]
    payload["terminal_closure_witness_refs"] = ["receipt://terminal-closure/governed_connector_framework"]
    payload["promotion_approval_refs"] = ["promotion-approval://governed_connector_framework"]
    payload["terminal_closure_denial_is_not_terminal_certificate"] = False
    payload["terminal_closure_denial_is_not_terminal_closure"] = False
    decision["terminal_closure_certificate_refs"] = ["terminal-certificate://governed_connector_framework"]
    decision["terminal_closure_witness_refs"] = ["receipt://terminal-closure/governed_connector_framework"]
    decision["promotion_approval_refs"] = ["promotion-approval://governed_connector_framework"]
    decision["decision_is_not_terminal_certificate"] = False
    decision["terminal_closure_witness_emitted"] = True
    decision["promotion_approved"] = True

    validation = validate_component_route_family_promotion_terminal_closure_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_refs must remain empty" in serialized_errors
    assert "terminal_closure_witness_refs must remain empty" in serialized_errors
    assert "promotion_approval_refs must remain empty" in serialized_errors
    assert "terminal_closure_denial_is_not_terminal_certificate must be true" in serialized_errors
    assert "terminal_closure_denial_is_not_terminal_closure must be true" in serialized_errors
    assert "terminal_closure_witness_emitted must be false" in serialized_errors
    assert "promotion_approved must be false" in serialized_errors
    assert "summary.terminal_closure_witness_count" in serialized_errors
