"""Tests for Component Harness promotion operator-submitted evidence records.

Purpose: prove submitted-for-review evidence records apply acceptance rules as
record-only evidence while remaining blocked from promotion and authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_operator_submitted_evidence_records
and promotion operator-submitted evidence record runtime.
Invariants: accepted records remain non-authoritative; applied rules are not
execution authority; promotion gates are not satisfied by record acceptance.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_operator_submitted_evidence_records import (
    build_component_route_family_promotion_operator_submitted_evidence_records,
)
from scripts.validate_component_route_family_promotion_operator_submitted_evidence_records import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_operator_submitted_evidence_records,
    write_component_route_family_promotion_operator_submitted_evidence_records_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_operator_submitted_evidence_records.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _records(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    records = payload["operator_submitted_evidence_records"]
    assert isinstance(records, list)
    return {
        str(record["gate_id"]): record
        for record in records
        if isinstance(record, dict)
    }


def test_component_route_family_promotion_operator_submitted_evidence_records_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_operator_submitted_evidence_records()
    output_path = tmp_path / "component-route-family-promotion-operator-submitted-evidence-records-validation.json"

    written_path = write_component_route_family_promotion_operator_submitted_evidence_records_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.submitted_record_count == 4
    assert validation.accepted_record_count == 4
    assert validation.rejected_record_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.acceptance_rule_count == 28
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_operator_submitted_evidence_records_validation.json"


def test_component_route_family_promotion_operator_submitted_evidence_records_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_operator_submitted_evidence_records()
    records = _records(example)
    route_record = records["route_binding_gate"]
    route_payload = route_record["submitted_payload"]
    authority_record = records["authority_upgrade_gate"]
    authority_payload = authority_record["submitted_payload"]
    assert isinstance(route_payload, dict)
    assert isinstance(authority_payload, dict)

    assert example == projection
    assert example["accepted_records_are_not_promotion_authority"] is True
    assert example["foundation_fixture_records_are_not_live_operator_evidence"] is True
    assert example["ready_for_promotion"] is False
    assert example["summary"]["submitted_record_count"] == 4
    assert example["summary"]["accepted_record_count"] == 4
    assert example["summary"]["passing_acceptance_rule_count"] == 28
    assert example["summary"]["satisfied_requirement_count"] == 0
    assert route_record["acceptance_state"] == "accepted_record_only"
    assert route_record["blocks_promotion"] is True
    assert route_payload["component_route_binding_receipt_ref"].startswith("example://")
    assert authority_payload["authority_claims"]["can_call_connector"] is False
    assert authority_record["applied_acceptance_rules"][0]["rule_state"] == "applied"


def test_component_route_family_promotion_operator_submitted_evidence_records_reject_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = _records(payload)
    authority_record = records["authority_upgrade_gate"]
    authority_payload = authority_record["submitted_payload"]
    assert isinstance(authority_payload, dict)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    authority_record["grants_connector_authority"] = True
    authority_payload["authority_claims"]["can_call_connector"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_operator_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "grants_connector_authority must be false" in serialized_errors
    assert "authority_claims.can_call_connector must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_operator_submitted_evidence_records_reject_missing_record(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = payload["operator_submitted_evidence_records"]
    assert isinstance(records, list)
    payload["operator_submitted_evidence_records"] = [
        record
        for record in records
        if isinstance(record, dict) and record.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_operator_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_submitted_evidence_records must cover exactly" in serialized_errors
    assert "summary.submitted_record_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_operator_submitted_evidence_records_reject_unapplied_rule_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = _records(payload)
    route_record = records["route_binding_gate"]
    route_payload = route_record["submitted_payload"]
    route_rules = route_record["applied_acceptance_rules"]
    assert isinstance(route_payload, dict)
    assert isinstance(route_rules, list)
    route_payload.pop("component_route_binding_receipt_ref")
    route_record["required_payload_fields"].remove("component_route_binding_receipt_ref")
    route_rules[0]["rule_state"] = "defined_not_applied"
    route_rules[0]["proof_state"] = "Unknown"
    route_rules[0]["rule_result"] = "fail"
    route_rules[0]["source_payload_fields"] = ["field_not_present_on_payload"]
    route_rules[0]["grants_execution_authority"] = True

    validation = validate_component_route_family_promotion_operator_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_payload_fields omits required fields" not in serialized_errors
    assert "applied rule state must be applied" in serialized_errors
    assert "applied rule proof_state must be Pass" in serialized_errors
    assert "applied rule result must be pass" in serialized_errors
    assert "applied rule grants_execution_authority must be false" in serialized_errors
    assert "applied rule source_payload_fields must exist on submitted_payload" in serialized_errors
    assert "summary.applied_acceptance_rule_count" in serialized_errors
    assert "summary.passing_acceptance_rule_count" in serialized_errors


def test_component_route_family_promotion_operator_submitted_evidence_records_reject_promotion_satisfaction_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = _records(payload)
    product_record = records["product_specific_boundary_gate"]
    payload["accepted_records_are_not_promotion_authority"] = False
    payload["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_record["satisfies_requirement"] = True
    product_record["blocks_promotion"] = False
    product_record["accepted_record_is_not_promotion_authority"] = False
    product_record["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_record["promotion_approval_refs"] = ["approval://promotion/product_specific_boundary_gate"]

    validation = validate_component_route_family_promotion_operator_submitted_evidence_records(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "accepted records must not be promotion authority" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "must not satisfy requirement" in serialized_errors
    assert "must block promotion" in serialized_errors
    assert "accepted_record_is_not_promotion_authority must be true" in serialized_errors
    assert "promotion_approval_refs must remain empty" in serialized_errors
    assert "summary.satisfied_requirement_count" in serialized_errors
