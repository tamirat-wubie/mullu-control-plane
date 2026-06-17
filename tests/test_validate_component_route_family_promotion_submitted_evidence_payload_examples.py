"""Tests for Component Harness promotion submitted-evidence payload examples.

Purpose: prove submitted-evidence payload examples and acceptance rules remain
example-only, not submitted, not evaluated, and non-authoritative.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_submitted_evidence_payload_examples
and promotion submitted-evidence payload example runtime.
Invariants: payload examples remain concrete examples only; acceptance rules are
defined but not applied; no payload or rule grants authority or terminal
closure.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_payload_examples import (
    build_component_route_family_promotion_submitted_evidence_payload_examples,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_payload_examples import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_submitted_evidence_payload_examples,
    write_component_route_family_promotion_submitted_evidence_payload_examples_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_submitted_evidence_payload_examples.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _payload_examples(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    examples = payload["payload_examples"]
    assert isinstance(examples, list)
    return {
        str(example["gate_id"]): example
        for example in examples
        if isinstance(example, dict)
    }


def test_component_route_family_promotion_submitted_evidence_payload_examples_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples()
    output_path = tmp_path / "component-route-family-promotion-submitted-evidence-payload-examples-validation.json"

    written_path = write_component_route_family_promotion_submitted_evidence_payload_examples_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.payload_example_count == 4
    assert validation.submitted_payload_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.rejected_evidence_count == 0
    assert validation.acceptance_rule_count == 28
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_submitted_evidence_payload_examples_validation.json"


def test_component_route_family_promotion_submitted_evidence_payload_examples_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_submitted_evidence_payload_examples()
    examples = _payload_examples(example)
    route_payload = examples["route_binding_gate"]["example_payload"]
    authority_payload = examples["authority_upgrade_gate"]["example_payload"]
    assert isinstance(route_payload, dict)
    assert isinstance(authority_payload, dict)

    assert example == projection
    assert example["payload_examples_are_not_submitted_evidence"] is True
    assert example["acceptance_rules_are_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["summary"]["payload_example_count"] == 4
    assert example["summary"]["applied_acceptance_rule_count"] == 0
    assert examples["route_binding_gate"]["payload_values_present"] is True
    assert examples["route_binding_gate"]["payload_values_are_examples_only"] is True
    assert examples["route_binding_gate"]["submission_state"] == "not_submitted"
    assert route_payload["selected_component_bound_router_inventory_delta_ref"].startswith("example://")
    assert authority_payload["authority_claims"]["can_call_connector"] is False
    assert examples["product_specific_boundary_gate"]["acceptance_rules"][0]["rule_state"] == "defined_not_applied"


def test_component_route_family_promotion_submitted_evidence_payload_examples_reject_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    examples = _payload_examples(payload)
    authority_example = examples["authority_upgrade_gate"]
    authority_payload = authority_example["example_payload"]
    assert isinstance(authority_payload, dict)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    authority_example["grants_connector_authority"] = True
    authority_payload["authority_claims"]["can_call_connector"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples(
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


def test_component_route_family_promotion_submitted_evidence_payload_examples_reject_missing_payload(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload_examples = payload["payload_examples"]
    assert isinstance(payload_examples, list)
    payload["payload_examples"] = [
        example
        for example in payload_examples
        if isinstance(example, dict) and example.get("gate_id") != "lifecycle_gate"
    ]

    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "payload_examples must cover exactly" in serialized_errors
    assert "summary.payload_example_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_payload_examples_reject_submission_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    examples = _payload_examples(payload)
    product_example = examples["product_specific_boundary_gate"]
    payload["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_example["payload_state"] = "submitted"
    product_example["submission_state"] = "submitted"
    product_example["verification_state"] = "verified"
    product_example["acceptance_state"] = "accepted"
    product_example["proof_state"] = "Pass"
    product_example["satisfies_requirement"] = True
    product_example["blocks_promotion"] = False
    product_example["payload_example_is_not_submitted_evidence"] = False
    product_example["submitted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    product_example["accepted_evidence_refs"] = ["operator_evidence:product_specific_ownership_decision:v1"]
    payload["operator_submission_channels"].remove("product_specific_ownership_decision")

    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "submitted_evidence_refs must be empty" in serialized_errors
    assert "payload_state must be example_only" in serialized_errors
    assert "submission_state must be not_submitted" in serialized_errors
    assert "verification_state must be not_verified" in serialized_errors
    assert "acceptance_state must be not_evaluated" in serialized_errors
    assert "proof_state must be Unknown" in serialized_errors
    assert "payload_example_is_not_submitted_evidence must be true" in serialized_errors
    assert "operator_submission_channels must match approval_evidence_required" in serialized_errors


def test_component_route_family_promotion_submitted_evidence_payload_examples_reject_rule_application_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    examples = _payload_examples(payload)
    route_example = examples["route_binding_gate"]
    route_payload = route_example["example_payload"]
    route_rules = route_example["acceptance_rules"]
    assert isinstance(route_payload, dict)
    assert isinstance(route_rules, list)
    route_payload.pop("component_route_binding_receipt_ref")
    route_example["required_payload_fields"].remove("component_route_binding_receipt_ref")
    route_rules[0]["rule_state"] = "applied"
    route_rules[0]["proof_state"] = "Pass"
    route_rules[0]["grants_execution_authority"] = True
    route_rules[0]["source_payload_fields"] = ["field_not_present_on_payload"]

    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_payload_fields omits required fields" not in serialized_errors
    assert "acceptance rule state must be defined_not_applied" in serialized_errors
    assert "acceptance rule proof_state must be Unknown" in serialized_errors
    assert "acceptance rule grants_execution_authority must be false" in serialized_errors
    assert "acceptance rule source_payload_fields must exist on payload" in serialized_errors
    assert "summary.applied_acceptance_rule_count" in serialized_errors
    assert "summary.passing_acceptance_rule_count" in serialized_errors
