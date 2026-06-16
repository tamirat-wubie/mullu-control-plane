"""Tests for router-inventory delta witness minting preflight reports.

Purpose: prove router-inventory delta witness minting remains blocked while
source witness requirements are unmet.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness minting preflight validator and
runtime projection.
Invariants: minting preflight reports are not witnesses, deltas, evidence,
authority grants, promotion approvals, router mutations, or closure claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_minting_preflight import (
    build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight,
    write_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_witness_minting_preflight.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _checks(payload: dict[str, object]) -> list[dict[str, object]]:
    checks = payload["minting_preflight_checks"]
    assert isinstance(checks, list)
    assert len(checks) == 6
    assert all(isinstance(record, dict) for record in checks)
    return checks


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight()
    output_path = tmp_path / "router-inventory-delta-witness-minting-preflight-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.preflight_check_count == 6
    assert validation.blocked_check_count == 6
    assert validation.witness_mint_count == 0
    assert validation.router_inventory_mutation_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_witness_minting_preflight()
    checks = _checks(example)

    assert example == projection
    assert example["minting_preflight_state"] == "blocked_requirements_unmet"
    assert example["minting_preflight_is_not_witness"] is True
    assert example["requirements_unmet"] is True
    assert example["witness_minting_authorized"] is False
    assert example["witness_minted"] is False
    assert example["delta_applied"] is False
    assert example["router_inventory_mutated"] is False
    assert example["summary"]["preflight_check_count"] == 6
    assert example["summary"]["blocked_check_count"] == 6
    assert checks[0]["requirement_artifact"] == "router_inventory_delta_operator_approval"


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_witness_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    check = _checks(payload)[0]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["minting_preflight_state"] = "witness_minting_authorized"
    payload["witness_minting_authorized"] = True
    payload["witness_minted"] = True
    payload["router_inventory_delta_witness_refs"] = ["witness://router-delta"]
    check["check_state"] = "passed"
    check["proof_state"] = "Pass"
    check["satisfied"] = True
    check["witness_minting_authorized"] = True
    check["witness_minted"] = True
    check["witness_refs"] = ["witness://router-delta"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "minting_preflight_state must be blocked_requirements_unmet" in serialized_errors
    assert "witness_minting_authorized must be false" in serialized_errors
    assert "witness_minted must be false" in serialized_errors
    assert "router_inventory_delta_witness_refs must remain empty" in serialized_errors
    assert "check check_state must be blocked" in serialized_errors
    assert "check proof_state must be Unknown" in serialized_errors
    assert "check satisfied must be false" in serialized_errors
    assert "check witness_refs must remain empty" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_missing_check(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["minting_preflight_checks"] = _checks(payload)[:-1]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "minting_preflight_checks must contain six checks" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    check = _checks(payload)[0]
    payload["source_witness_requirement_refs"] = []
    payload["source_witness_requirements_report_refs"] = []
    check["source_requirement_refs"] = []
    check["source_requirement_id"] = "unknown_requirement"
    check["target_component_id"] = "other_component"
    check["requirement_artifact"] = "unknown_requirement"

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_witness_requirement_refs must contain six source requirements" in serialized_errors
    assert "source_witness_requirements_report_refs must contain one report" in serialized_errors
    assert "check source_requirement_refs must match source requirement" in serialized_errors
    assert "check source_requirement_id must be listed by report" in serialized_errors
    assert "check target_component_id must be gmail_account_binding_gate" in serialized_errors
    assert "check requirement_artifact must be in required set" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_mutation_authority_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    check = _checks(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    check["router_inventory_mutated"] = True
    check["delta_applied"] = True
    check["authority_granted"] = True
    check["router_inventory_delta_refs"] = ["delta://router"]
    check["authority_grant_refs"] = ["grant://authority"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "check router_inventory_mutated must be false" in serialized_errors
    assert "check delta_applied must be false" in serialized_errors
    assert "check authority_granted must be false" in serialized_errors
    assert "check router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
