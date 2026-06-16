"""Tests for Component Harness promotion router-inventory delta candidates.

Purpose: prove a missing-evidence ledger can define one dry-run selected
component router-inventory delta candidate while router inventory remains
unchanged and promotion evidence remains unsatisfied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_router_inventory_delta_candidate
and promotion router-inventory delta candidate runtime.
Invariants: delta candidates are not delta witnesses, route bindings,
authority grants, promotion approvals, terminal closure, or router mutations.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_candidate import (
    build_component_route_family_promotion_router_inventory_delta_candidate,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_candidate import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_candidate,
    write_component_route_family_promotion_router_inventory_delta_candidate_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_router_inventory_delta_candidate.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _candidate(payload: dict[str, object]) -> dict[str, object]:
    candidates = payload["router_inventory_delta_candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, dict)
    return candidate


def test_component_route_family_promotion_router_inventory_delta_candidate_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_router_inventory_delta_candidate()
    output_path = tmp_path / "component-route-family-promotion-router-inventory-delta-candidate-validation.json"

    written_path = write_component_route_family_promotion_router_inventory_delta_candidate_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.candidate_count == 1
    assert validation.applied_delta_count == 0
    assert validation.router_inventory_mutation_count == 0
    assert validation.selected_component_binding_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_router_inventory_delta_candidate_validation.json"


def test_component_route_family_promotion_router_inventory_delta_candidate_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_router_inventory_delta_candidate()
    candidate = _candidate(example)

    assert example == projection
    assert example["candidate_status"] == "draft_not_applied"
    assert example["evidence_status"] == "candidate_defined_not_witnessed"
    assert example["router_inventory_delta_candidate_is_not_delta"] is True
    assert example["delta_applied"] is False
    assert example["router_inventory_mutated"] is False
    assert example["selected_component_binding_created"] is False
    assert example["summary"]["candidate_count"] == 1
    assert example["summary"]["applied_delta_count"] == 0
    assert example["summary"]["router_inventory_mutation_count"] == 0
    assert candidate["artifact_id"] == "selected_component_bound_router_inventory_delta"
    assert candidate["proposed_delta"]["would_require_separate_witness"] is True


def test_component_route_family_promotion_router_inventory_delta_candidate_reject_delta_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidate = _candidate(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["candidate_status"] = "applied"
    payload["delta_applied"] = True
    payload["ready_for_promotion"] = True
    candidate["candidate_state"] = "applied"
    candidate["delta_applied"] = True
    candidate["evidence_present"] = True
    candidate["candidate_is_not_delta"] = False

    validation = validate_component_route_family_promotion_router_inventory_delta_candidate(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "candidate_status must be draft_not_applied" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "ready_for_promotion must be false" in serialized_errors
    assert "candidate candidate_state must be draft_not_applied" in serialized_errors
    assert "candidate evidence_present must be false" in serialized_errors
    assert "candidate candidate_is_not_delta must be true" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_candidate_reject_missing_candidate(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["router_inventory_delta_candidates"] = []

    validation = validate_component_route_family_promotion_router_inventory_delta_candidate(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_delta_candidates must contain exactly one candidate" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_candidate_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidate = _candidate(payload)
    payload["source_missing_evidence_record_refs"] = []
    candidate["source_missing_evidence_refs"] = []
    candidate["source_evidence_state"] = "present"
    candidate["source_proof_state"] = "Pass"
    candidate["proposed_delta"]["would_bind_component_id"] = "other_component"

    validation = validate_component_route_family_promotion_router_inventory_delta_candidate(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_missing_evidence_record_refs must match source missing evidence id" in serialized_errors
    assert "source_missing_evidence_refs must contain only the source missing evidence id" in serialized_errors
    assert "candidate source_evidence_state must be missing" in serialized_errors
    assert "candidate source_proof_state must be Unknown" in serialized_errors
    assert "proposed_delta would_bind_component_id must match target component" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_candidate_reject_witness_mutation_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidate = _candidate(payload)
    payload["router_inventory_mutated"] = True
    payload["router_inventory_delta_refs"] = ["delta://governed_connector_framework"]
    payload["selected_component_binding_refs"] = ["binding://gmail_account_binding_gate"]
    payload["router_inventory_delta_candidate_is_not_witness"] = False
    candidate["router_inventory_mutated"] = True
    candidate["selected_component_binding_created"] = True
    candidate["witness_emitted"] = True
    candidate["witness_refs"] = ["witness://router-inventory-delta"]
    candidate["router_inventory_delta_refs"] = ["delta://governed_connector_framework"]

    validation = validate_component_route_family_promotion_router_inventory_delta_candidate(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "selected_component_binding_refs must remain empty" in serialized_errors
    assert "router_inventory_delta_candidate_is_not_witness must be true" in serialized_errors
    assert "candidate router_inventory_mutated must be false" in serialized_errors
    assert "candidate selected_component_binding_created must be false" in serialized_errors
    assert "candidate witness_emitted must be false" in serialized_errors
    assert "candidate witness_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
