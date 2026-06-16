"""Tests for router-inventory delta witness minting denial reports.

Purpose: prove blocked minting preflights produce denial-only decisions without
minting witnesses, applying deltas, mutating router inventory, or granting
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness minting denial validator and
runtime projection.
Invariants: denial reports are not witnesses, deltas, evidence, authority
grants, promotion approvals, router mutations, or closure claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_denial_report import (
    build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report,
    write_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_witness_minting_denial.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _decisions(payload: dict[str, object]) -> list[dict[str, object]]:
    decisions = payload["minting_denial_decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) == 1
    assert all(isinstance(record, dict) for record in decisions)
    return decisions


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report()
    output_path = tmp_path / "router-inventory-delta-witness-minting-denial-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.denial_decision_count == 1
    assert validation.witness_minting_denial_count == 1
    assert validation.witness_mint_count == 0
    assert validation.router_inventory_mutation_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report()
    decision = _decisions(example)[0]

    assert example == projection
    assert example["denial_report_state"] == "denied_requirements_unmet"
    assert example["denial_report_is_not_witness"] is True
    assert example["witness_minting_denied"] is True
    assert example["witness_minting_authorized"] is False
    assert example["witness_minted"] is False
    assert example["delta_applied"] is False
    assert example["router_inventory_mutated"] is False
    assert example["summary"]["denial_decision_count"] == 1
    assert example["summary"]["witness_minting_denial_count"] == 1
    assert decision["decision_state"] == "denied"
    assert decision["proof_state"] == "Pass"


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_witness_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _decisions(payload)[0]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["denial_report_state"] = "witness_minted"
    payload["witness_minting_authorized"] = True
    payload["witness_minted"] = True
    payload["router_inventory_delta_witness_refs"] = ["witness://router-delta"]
    decision["decision_state"] = "approved"
    decision["witness_minting_authorized"] = True
    decision["witness_minted"] = True
    decision["router_inventory_delta_witness_refs"] = ["witness://router-delta"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "denial_report_state must be denied_requirements_unmet" in serialized_errors
    assert "witness_minting_authorized must be false" in serialized_errors
    assert "witness_minted must be false" in serialized_errors
    assert "router_inventory_delta_witness_refs must remain empty" in serialized_errors
    assert "denial decision decision_state must be denied" in serialized_errors
    assert "denial decision witness_minting_authorized must be false" in serialized_errors
    assert "denial decision witness_minted must be false" in serialized_errors
    assert "denial decision router_inventory_delta_witness_refs must remain empty" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_missing_decision(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["minting_denial_decisions"] = []

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "minting_denial_decisions must contain exactly one decision" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _decisions(payload)[0]
    payload["source_minting_preflight_refs"] = []
    payload["source_minting_preflight_check_refs"] = []
    payload["missing_witness_requirements"] = []
    decision["source_minting_preflight_refs"] = []
    decision["source_minting_preflight_check_refs"] = []
    decision["missing_witness_requirements"] = []
    decision["target_component_id"] = "other_component"

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_minting_preflight_refs must match source preflight id" in serialized_errors
    assert "missing_witness_requirements must match required witness set" in serialized_errors
    assert "denial decision source_minting_preflight_refs must match source preflight" in serialized_errors
    assert "denial decision source_minting_preflight_check_refs must contain six refs" in serialized_errors
    assert "denial decision missing_witness_requirements must match required witness set" in serialized_errors
    assert "denial decision target_component_id must be gmail_account_binding_gate" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_mutation_authority_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    decision = _decisions(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    decision["router_inventory_mutated"] = True
    decision["delta_applied"] = True
    decision["authority_granted"] = True
    decision["router_inventory_delta_refs"] = ["delta://router"]
    decision["authority_grant_refs"] = ["grant://authority"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "denial decision router_inventory_mutated must be false" in serialized_errors
    assert "denial decision delta_applied must be false" in serialized_errors
    assert "denial decision authority_granted must be false" in serialized_errors
    assert "denial decision router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
