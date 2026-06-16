"""Tests for router-inventory delta witness remediation evidence requests.

Purpose: prove remediation evidence requests remain request-only and do not
submit, accept, or reject evidence; authorize minting; mint witnesses; apply
deltas; or mutate router inventory.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness remediation evidence request
validator and runtime projection.
Invariants: evidence requests are not evidence submissions, acceptances,
authorizations, witnesses, deltas, authority grants, approvals, or closure
claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request import (
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request,
    write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _slots(payload: dict[str, object]) -> list[dict[str, object]]:
    slots = payload["evidence_requests"]
    assert isinstance(slots, list)
    assert len(slots) == 6
    assert all(isinstance(record, dict) for record in slots)
    return slots


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request()
    output_path = tmp_path / "router-inventory-delta-witness-remediation-evidence-request-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.evidence_request_count == 6
    assert validation.requested_slot_count == 6
    assert validation.submitted_evidence_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.witness_mint_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request()
    slots = _slots(example)

    assert example == projection
    assert example["evidence_request_state"] == "requested_not_submitted"
    assert example["evidence_request_is_not_submission"] is True
    assert example["evidence_request_is_not_acceptance"] is True
    assert example["evidence_submitted"] is False
    assert example["evidence_accepted"] is False
    assert example["witness_minted"] is False
    assert example["router_inventory_mutated"] is False
    assert example["summary"]["evidence_request_count"] == 6
    assert example["summary"]["requested_slot_count"] == 6
    assert slots[0]["requirement_artifact"] == "router_inventory_delta_operator_approval"


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_submission_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    slot = _slots(payload)[0]
    payload["evidence_submitted"] = True
    payload["submitted_evidence_refs"] = ["evidence://submitted"]
    slot["evidence_submitted"] = True
    slot["submitted_evidence_refs"] = ["evidence://submitted"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_submitted must be false" in serialized_errors
    assert "submitted_evidence_refs must remain empty" in serialized_errors
    assert "slot evidence_submitted must be false" in serialized_errors
    assert "slot submitted_evidence_refs must remain empty" in serialized_errors
    assert "summary.submitted_evidence_count" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_acceptance_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    slot = _slots(payload)[0]
    payload["evidence_accepted"] = True
    payload["requirements_satisfied"] = True
    payload["accepted_evidence_refs"] = ["evidence://accepted"]
    slot["evidence_accepted"] = True
    slot["requirement_satisfied"] = True
    slot["accepted_evidence_refs"] = ["evidence://accepted"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "requirements_satisfied must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "slot evidence_accepted must be false" in serialized_errors
    assert "slot requirement_satisfied must be false" in serialized_errors
    assert "slot accepted_evidence_refs must remain empty" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_missing_slot(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["evidence_requests"] = _slots(payload)[:-1]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_requests must contain six slots" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_mutation_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    slot = _slots(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    slot["router_inventory_mutated"] = True
    slot["delta_applied"] = True
    slot["authority_granted"] = True
    slot["router_inventory_delta_refs"] = ["delta://router"]
    slot["authority_grant_refs"] = ["grant://authority"]

    validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "slot router_inventory_mutated must be false" in serialized_errors
    assert "slot delta_applied must be false" in serialized_errors
    assert "slot authority_granted must be false" in serialized_errors
    assert "slot router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
