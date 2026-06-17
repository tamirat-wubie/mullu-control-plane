"""Tests for Component Harness promotion approval candidates validation.

Purpose: prove blocked promotion gates have draft-only approval candidates
without approving promotion, mutating router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_approval_candidates
and promotion approval candidates runtime.
Invariants: approval candidates remain not-approved, non-mutating,
non-authoritative, and blocking until governed approval artifacts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_approval_candidates import (
    build_component_route_family_promotion_approval_candidates,
)
from scripts.validate_component_route_family_promotion_approval_candidates import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_approval_candidates,
    write_component_route_family_promotion_approval_candidates_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_approval_candidates.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _candidates(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    candidates = payload["approval_candidates"]
    assert isinstance(candidates, list)
    return {
        str(candidate["gate_id"]): candidate
        for candidate in candidates
        if isinstance(candidate, dict)
    }


def test_component_route_family_promotion_approval_candidates_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_approval_candidates()
    output_path = tmp_path / "component-route-family-promotion-approval-candidates-validation.json"

    written_path = write_component_route_family_promotion_approval_candidates_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.approval_candidate_count == 4
    assert validation.approval_evidence_required_count >= 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_approval_candidates_validation.json"


def test_component_route_family_promotion_approval_candidates_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_approval_candidates()
    candidates = _candidates(example)

    assert example == projection
    assert example["approval_candidates_are_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["mutates_router_inventory"] is False
    assert candidates["route_binding_gate"]["approval_state"] == "not_approved"
    assert candidates["lifecycle_gate"]["candidate_kind"] == "lifecycle_transition"
    assert candidates["authority_upgrade_gate"]["grants_connector_authority"] is False
    assert candidates["product_specific_boundary_gate"]["candidate_kind"] == "product_specific_ownership"
    assert "product_specific_ownership_decision" in example["approval_evidence_required"]


def test_component_route_family_promotion_approval_candidates_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidates = _candidates(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    candidates["authority_upgrade_gate"]["grants_connector_authority"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_approval_candidates(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_approval_candidates_rejects_missing_candidate(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidates = payload["approval_candidates"]
    assert isinstance(candidates, list)
    payload["approval_candidates"] = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_approval_candidates(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_candidates must cover exactly" in serialized_errors
    assert "summary.approval_candidate_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_approval_candidates_rejects_approval_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    candidates = _candidates(payload)
    product_candidate = candidates["product_specific_boundary_gate"]
    product_candidate["approval_state"] = "approved"
    product_candidate["candidate_state"] = "approved_live_action"
    product_candidate["proof_state"] = "Pass"
    product_candidate["satisfies_requirement"] = True
    product_candidate["blocks_promotion"] = False
    payload["approval_evidence_required"].remove("product_specific_ownership_decision")

    validation = validate_component_route_family_promotion_approval_candidates(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_state must be not_approved" in serialized_errors
    assert "candidate_state must be draft_only" in serialized_errors
    assert "proof_state must be Unknown" in serialized_errors
    assert "must not satisfy requirement" in serialized_errors
    assert "approval_evidence_required omits required approval artifacts" in serialized_errors
