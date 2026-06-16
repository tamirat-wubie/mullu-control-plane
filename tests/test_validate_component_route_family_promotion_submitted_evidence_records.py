"""Tests for Component Harness promotion submitted-evidence records validation.

Purpose: prove submitted-evidence record envelopes remain template-only without
accepting evidence, mutating router inventory, approving promotion, or granting
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_submitted_evidence_records
and promotion submitted-evidence record runtime.
Invariants: record envelopes remain template-only, not submitted, not verified,
non-authoritative, and blocking until submitted payload examples and acceptance
rules exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_records import (
    build_component_route_family_promotion_submitted_evidence_records,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_records import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_submitted_evidence_records,
    write_component_route_family_promotion_submitted_evidence_records_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_submitted_evidence_records.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _envelopes(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    envelopes = payload["record_envelopes"]
    assert isinstance(envelopes, list)
    return {
        str(envelope["gate_id"]): envelope
        for envelope in envelopes
        if isinstance(envelope, dict)
    }


def test_component_route_family_promotion_submitted_evidence_records_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_submitted_evidence_records()
    output_path = tmp_path / "component-route-family-promotion-submitted-evidence-records-validation.json"

    written_path = write_component_route_family_promotion_submitted_evidence_records_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.record_envelope_count == 4
    assert validation.submitted_record_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.rejected_evidence_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_submitted_evidence_records_validation.json"


def test_component_route_family_promotion_submitted_evidence_records_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_submitted_evidence_records()
    envelopes = _envelopes(example)

    assert example == projection
    assert example["submitted_evidence_records_are_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["mutates_router_inventory"] is False
    assert example["summary"]["submitted_record_count"] == 0
    assert example["summary"]["blocking_envelope_count"] == 4
    assert envelopes["route_binding_gate"]["envelope_state"] == "template_only"
    assert envelopes["lifecycle_gate"]["submission_state"] == "not_submitted"
    assert envelopes["authority_upgrade_gate"]["grants_connector_authority"] is False
    assert envelopes["product_specific_boundary_gate"]["record_kind"] == "product_specific_ownership"
    assert "submitted_evidence_id" in envelopes["route_binding_gate"]["payload_field_names"]
    assert "terminal_closure_claim" in envelopes["authority_upgrade_gate"]["payload_field_names"]


def test_component_route_family_promotion_submitted_evidence_records_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    envelopes = _envelopes(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    envelopes["authority_upgrade_gate"]["grants_connector_authority"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_records_rejects_missing_envelope(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    envelopes = payload["record_envelopes"]
    assert isinstance(envelopes, list)
    payload["record_envelopes"] = [
        envelope
        for envelope in envelopes
        if isinstance(envelope, dict) and envelope.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "record_envelopes must cover exactly" in serialized_errors
    assert "summary.record_envelope_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_records_rejects_payload_submission_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    envelopes = _envelopes(payload)
    product_envelope = envelopes["product_specific_boundary_gate"]
    payload["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_envelope["envelope_state"] = "submitted"
    product_envelope["submission_state"] = "submitted"
    product_envelope["verification_state"] = "verified"
    product_envelope["proof_state"] = "Pass"
    product_envelope["satisfies_requirement"] = True
    product_envelope["blocks_promotion"] = False
    product_envelope["payload_values_present"] = True
    product_envelope["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_envelope["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    payload["operator_submission_channels"].remove("product_specific_ownership_decision")

    validation = validate_component_route_family_promotion_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "submitted_evidence_refs must be empty" in serialized_errors
    assert "envelope_state must be template_only" in serialized_errors
    assert "submission_state must be not_submitted" in serialized_errors
    assert "verification_state must be not_verified" in serialized_errors
    assert "proof_state must be Unknown" in serialized_errors
    assert "payload_values_present must be false" in serialized_errors
    assert "operator_submission_channels must match approval_evidence_required" in serialized_errors
