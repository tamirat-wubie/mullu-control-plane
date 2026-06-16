"""Tests for router-inventory delta witness requirement reports.

Purpose: prove router-inventory delta witness requirements remain unmet and do
not mint witnesses, apply deltas, mutate router inventory, or grant authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness requirements validator and
runtime projection.
Invariants: requirement reports are not evidence, authorization, witnesses,
deltas, route bindings, authority grants, promotion approvals, or closure.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_requirements import (
    build_component_route_family_promotion_router_inventory_delta_witness_requirements,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_requirements import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_requirements,
    write_component_route_family_promotion_router_inventory_delta_witness_requirements_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_witness_requirements.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _requirements(payload: dict[str, object]) -> list[dict[str, object]]:
    requirements = payload["witness_requirements"]
    assert isinstance(requirements, list)
    assert len(requirements) == 6
    assert all(isinstance(record, dict) for record in requirements)
    return requirements


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements()
    output_path = tmp_path / "router-inventory-delta-witness-requirements-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_witness_requirements_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.requirement_count == 6
    assert validation.unmet_requirement_count == 6
    assert validation.witness_mint_count == 0
    assert validation.router_inventory_mutation_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_requirements_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_witness_requirements()
    requirements = _requirements(example)

    assert example == projection
    assert example["witness_status"] == "requirements_unmet"
    assert example["requirements_report_is_not_witness"] is True
    assert example["witness_minted"] is False
    assert example["delta_applied"] is False
    assert example["router_inventory_mutated"] is False
    assert example["selected_component_binding_created"] is False
    assert example["summary"]["requirement_count"] == 6
    assert example["summary"]["unmet_requirement_count"] == 6
    assert example["summary"]["witness_mint_count"] == 0
    assert requirements[0]["requirement_artifact"] == "router_inventory_delta_operator_approval"


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_reject_witness_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requirement = _requirements(payload)[0]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["witness_status"] = "witness_minted"
    payload["witness_minted"] = True
    payload["router_inventory_delta_witness_refs"] = ["witness://router-delta"]
    requirement["requirement_state"] = "satisfied"
    requirement["proof_state"] = "Pass"
    requirement["satisfied"] = True
    requirement["witness_minted"] = True
    requirement["witness_refs"] = ["witness://router-delta"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "witness_status must be requirements_unmet" in serialized_errors
    assert "witness_minted must be false" in serialized_errors
    assert "router_inventory_delta_witness_refs must remain empty" in serialized_errors
    assert "requirement requirement_state must be unmet" in serialized_errors
    assert "requirement proof_state must be Unknown" in serialized_errors
    assert "requirement satisfied must be false" in serialized_errors
    assert "requirement witness_refs must remain empty" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_reject_missing_requirement(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["witness_requirements"] = _requirements(payload)[:-1]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "witness_requirements must contain six requirements" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requirement = _requirements(payload)[0]
    payload["source_router_inventory_delta_candidate_refs"] = []
    requirement["source_candidate_refs"] = []
    requirement["target_component_id"] = "other_component"
    requirement["requirement_artifact"] = "unknown_requirement"

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_router_inventory_delta_candidate_refs must contain one candidate" in serialized_errors
    assert "source_candidate_refs must match source candidate" in serialized_errors
    assert "requirement target_component_id must be gmail_account_binding_gate" in serialized_errors
    assert "requirement_artifact must be in required set" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_requirements_reject_mutation_authority_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requirement = _requirements(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    requirement["router_inventory_mutated"] = True
    requirement["delta_applied"] = True
    requirement["authority_granted"] = True
    requirement["router_inventory_delta_refs"] = ["delta://router"]
    requirement["authority_grant_refs"] = ["grant://authority"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "requirement router_inventory_mutated must be false" in serialized_errors
    assert "requirement delta_applied must be false" in serialized_errors
    assert "requirement authority_granted must be false" in serialized_errors
    assert "requirement router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
