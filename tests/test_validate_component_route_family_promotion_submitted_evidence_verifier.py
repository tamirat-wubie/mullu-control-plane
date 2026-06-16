"""Tests for Component Harness promotion submitted-evidence verifier validation.

Purpose: prove blocked promotion intake requests remain awaiting submitted
evidence without approving promotion, mutating router inventory, or granting
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_submitted_evidence_verifier
and promotion submitted-evidence verifier runtime.
Invariants: verifier requests remain awaiting submitted evidence,
not verified, non-authoritative, and blocking until submitted-evidence record
contracts exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_verifier import (
    build_component_route_family_promotion_submitted_evidence_verifier,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_verifier import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_submitted_evidence_verifier,
    write_component_route_family_promotion_submitted_evidence_verifier_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_submitted_evidence_verifier.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _requests(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    requests = payload["verification_requests"]
    assert isinstance(requests, list)
    return {
        str(request["gate_id"]): request
        for request in requests
        if isinstance(request, dict)
    }


def test_component_route_family_promotion_submitted_evidence_verifier_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_submitted_evidence_verifier()
    output_path = tmp_path / "component-route-family-promotion-submitted-evidence-verifier-validation.json"

    written_path = write_component_route_family_promotion_submitted_evidence_verifier_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.verification_request_count == 4
    assert validation.submitted_evidence_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.rejected_evidence_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_submitted_evidence_verifier_validation.json"


def test_component_route_family_promotion_submitted_evidence_verifier_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_submitted_evidence_verifier()
    requests = _requests(example)

    assert example == projection
    assert example["submitted_evidence_verifier_is_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["mutates_router_inventory"] is False
    assert example["summary"]["submitted_evidence_count"] == 0
    assert example["summary"]["blocking_request_count"] == 4
    assert requests["route_binding_gate"]["verifier_state"] == "awaiting_submitted_evidence"
    assert requests["lifecycle_gate"]["verification_state"] == "not_verified"
    assert requests["authority_upgrade_gate"]["grants_connector_authority"] is False
    assert requests["product_specific_boundary_gate"]["verifier_kind"] == "product_specific_ownership"
    assert "submitted_evidence_record_schema_valid" in requests["route_binding_gate"]["verification_criteria"]


def test_component_route_family_promotion_submitted_evidence_verifier_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requests = _requests(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    requests["authority_upgrade_gate"]["grants_connector_authority"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_submitted_evidence_verifier(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_verifier_rejects_missing_request(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requests = payload["verification_requests"]
    assert isinstance(requests, list)
    payload["verification_requests"] = [
        request
        for request in requests
        if isinstance(request, dict) and request.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_submitted_evidence_verifier(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "verification_requests must cover exactly" in serialized_errors
    assert "summary.verification_request_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_verifier_rejects_submission_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requests = _requests(payload)
    product_request = requests["product_specific_boundary_gate"]
    payload["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_request["verifier_state"] = "verified"
    product_request["verification_state"] = "accepted"
    product_request["proof_state"] = "Pass"
    product_request["satisfies_requirement"] = True
    product_request["blocks_promotion"] = False
    product_request["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_request["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    payload["operator_submission_channels"].remove("product_specific_ownership_decision")

    validation = validate_component_route_family_promotion_submitted_evidence_verifier(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "submitted_evidence_refs must be empty" in serialized_errors
    assert "verifier_state must be awaiting_submitted_evidence" in serialized_errors
    assert "verification_state must be not_verified" in serialized_errors
    assert "proof_state must be Unknown" in serialized_errors
    assert "must not satisfy requirement" in serialized_errors
    assert "operator_submission_channels must match approval_evidence_required" in serialized_errors
