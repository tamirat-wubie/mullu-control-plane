"""Tests for router-inventory delta witness remediation plans.

Purpose: prove witness remediation plans remain plan-only and do not submit or
accept evidence, authorize minting, mint witnesses, apply deltas, or mutate
router inventory.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness remediation plan validator and
runtime projection.
Invariants: remediation plans are not evidence, authorization, witnesses,
deltas, authority grants, promotion approvals, or closure claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_plan import (
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan,
    write_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_witness_remediation_plan.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _steps(payload: dict[str, object]) -> list[dict[str, object]]:
    steps = payload["remediation_steps"]
    assert isinstance(steps, list)
    assert len(steps) == 6
    assert all(isinstance(record, dict) for record in steps)
    return steps


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan()
    output_path = tmp_path / "router-inventory-delta-witness-remediation-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.remediation_step_count == 6
    assert validation.planned_step_count == 6
    assert validation.accepted_evidence_count == 0
    assert validation.witness_mint_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_witness_remediation_plan()
    steps = _steps(example)

    assert example == projection
    assert example["remediation_plan_state"] == "planned_not_executed"
    assert example["remediation_plan_is_not_evidence"] is True
    assert example["evidence_submitted"] is False
    assert example["evidence_accepted"] is False
    assert example["witness_minting_authorized"] is False
    assert example["witness_minted"] is False
    assert example["router_inventory_mutated"] is False
    assert example["summary"]["remediation_step_count"] == 6
    assert example["summary"]["planned_step_count"] == 6
    assert steps[0]["requirement_artifact"] == "router_inventory_delta_operator_approval"


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_evidence_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    step = _steps(payload)[0]
    payload["evidence_submitted"] = True
    payload["evidence_accepted"] = True
    payload["requirements_satisfied"] = True
    payload["accepted_evidence_refs"] = ["evidence://accepted"]
    step["evidence_submitted"] = True
    step["evidence_accepted"] = True
    step["requirement_satisfied"] = True
    step["accepted_evidence_refs"] = ["evidence://accepted"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_submitted must be false" in serialized_errors
    assert "evidence_accepted must be false" in serialized_errors
    assert "requirements_satisfied must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "step evidence_submitted must be false" in serialized_errors
    assert "step evidence_accepted must be false" in serialized_errors
    assert "step requirement_satisfied must be false" in serialized_errors
    assert "step accepted_evidence_refs must remain empty" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_missing_step(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["remediation_steps"] = _steps(payload)[:-1]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "remediation_steps must contain six steps" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    step = _steps(payload)[0]
    payload["source_minting_denial_decision_refs"] = []
    step["source_denial_decision_refs"] = []
    step["source_denial_decision_id"] = "unknown_denial"
    step["target_component_id"] = "other_component"
    step["requirement_artifact"] = "unknown_requirement"

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_minting_denial_decision_refs must contain one decision" in serialized_errors
    assert "step source_denial_decision_refs must match source denial" in serialized_errors
    assert "step target_component_id must be gmail_account_binding_gate" in serialized_errors
    assert "step requirement_artifact must be in required set" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_mutation_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    step = _steps(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    step["router_inventory_mutated"] = True
    step["delta_applied"] = True
    step["authority_granted"] = True
    step["router_inventory_delta_refs"] = ["delta://router"]
    step["authority_grant_refs"] = ["grant://authority"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "step router_inventory_mutated must be false" in serialized_errors
    assert "step delta_applied must be false" in serialized_errors
    assert "step authority_granted must be false" in serialized_errors
    assert "step router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
