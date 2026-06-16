"""Tests for Component Harness promotion approval intake validation.

Purpose: prove blocked promotion candidates expose open operator evidence
intake requests without approving promotion, mutating router inventory, or
granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_approval_intake
and promotion approval intake runtime.
Invariants: approval intake requests remain open, not submitted, not approved,
non-authoritative, and blocking until governed approval verification exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_approval_intake import (
    build_component_route_family_promotion_approval_intake,
)
from scripts.validate_component_route_family_promotion_approval_intake import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_approval_intake,
    write_component_route_family_promotion_approval_intake_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_approval_intake.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _requests(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    requests = payload["approval_requests"]
    assert isinstance(requests, list)
    return {
        str(request["gate_id"]): request
        for request in requests
        if isinstance(request, dict)
    }


def test_component_route_family_promotion_approval_intake_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_approval_intake()
    output_path = tmp_path / "component-route-family-promotion-approval-intake-validation.json"

    written_path = write_component_route_family_promotion_approval_intake_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.intake_request_count == 4
    assert validation.submitted_evidence_count == 0
    assert validation.approval_artifact_requirement_count == 8
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_approval_intake_validation.json"


def test_component_route_family_promotion_approval_intake_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_approval_intake()
    requests = _requests(example)

    assert example == projection
    assert example["approval_intake_is_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["mutates_router_inventory"] is False
    assert example["summary"]["submitted_evidence_count"] == 0
    assert requests["route_binding_gate"]["intake_state"] == "open"
    assert requests["lifecycle_gate"]["request_kind"] == "lifecycle_transition"
    assert requests["authority_upgrade_gate"]["grants_connector_authority"] is False
    assert requests["product_specific_boundary_gate"]["request_kind"] == "product_specific_ownership"
    assert "gmail_account_binding_evidence_receipt" in example["operator_submission_channels"]


def test_component_route_family_promotion_approval_intake_rejects_authority_overclaim(
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

    validation = validate_component_route_family_promotion_approval_intake(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_approval_intake_rejects_missing_request(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requests = payload["approval_requests"]
    assert isinstance(requests, list)
    payload["approval_requests"] = [
        request
        for request in requests
        if isinstance(request, dict) and request.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_approval_intake(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_requests must cover exactly" in serialized_errors
    assert "summary.intake_request_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_approval_intake_rejects_submission_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requests = _requests(payload)
    product_request = requests["product_specific_boundary_gate"]
    product_request["approval_state"] = "approved"
    product_request["evidence_submission_state"] = "accepted"
    product_request["proof_state"] = "Pass"
    product_request["satisfies_requirement"] = True
    product_request["blocks_promotion"] = False
    product_request["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    payload["operator_submission_channels"].remove("product_specific_ownership_decision")

    validation = validate_component_route_family_promotion_approval_intake(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "approval_state must be not_approved" in serialized_errors
    assert "evidence_submission_state must be not_submitted" in serialized_errors
    assert "proof_state must be Unknown" in serialized_errors
    assert "must not satisfy requirement" in serialized_errors
    assert "submitted_evidence_refs must be empty" in serialized_errors
    assert "operator_submission_channels must match approval_evidence_required" in serialized_errors
