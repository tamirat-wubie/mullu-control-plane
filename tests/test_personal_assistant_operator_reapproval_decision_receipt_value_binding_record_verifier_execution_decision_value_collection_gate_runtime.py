"""Tests for verifier execution operator decision-value collection gate.

Purpose: prove collection remains blocked until an actual explicit operator
decision value exists.
Governance scope: decision-value collection gate, private-payload redaction,
and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant collection-gate builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the collection-gate schema.
  - No collection route or template-as-value path is admitted.
  - Verifier execution and authority grant remain blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate import (
    _validate_decision_value_collection_gate_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_COLLECTION_GATE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_collection_gate_blocks_collection_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate()
    schema = _load_schema(DECISION_VALUE_COLLECTION_GATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_gate = envelope["collection_gates"][0]["collection_gate"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_collection_gate_semantics(envelope, receipt_schema) == ()
    assert envelope["collection_gate_count"] == 20
    assert envelope["summary"]["operator_decision_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_required_count"] == 20
    assert envelope["summary"]["actual_operator_decision_value_required_count"] == 20
    assert envelope["summary"]["collection_gate_creation_count"] == 20
    assert envelope["summary"]["collection_route_admission_count"] == 0
    assert envelope["summary"]["template_accepted_as_value_count"] == 0
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_decision_value_collected_count"] == 0
    assert envelope["summary"]["operator_decision_value_submitted_count"] == 0
    assert envelope["summary"]["operator_decision_value_admitted_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["collection_gate_state"] == "operator_decision_value_collection_gate_blocked_awaiting_explicit_operator_value"
    assert envelope["effect_boundary"]["operator_decision_value_collection_gate_projection_allowed"] is True
    assert envelope["effect_boundary"]["collection_route_admitted"] is False
    assert envelope["effect_boundary"]["template_accepted_as_value"] is False
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert first_gate["accepted_decision_values"] == ["approved", "rejected", "revise_requested", "expired"]
    assert first_gate["rejected_input_kinds"] == ["generic_continuation", "template_packet"]
    assert first_gate["accepts_generic_continuation"] is False
    assert first_gate["accepts_template_packet"] is False


def test_runtime_verifier_execution_decision_value_collection_gate_rejects_empty_source_records() -> None:
    template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
    template["decision_value_templates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope(
            generated_at="2026-06-14T01:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template=template,
        )

    assert "requires at least one decision-value template" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_collection_gate_rejects_source_value_drift() -> None:
    template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
    template["decision_value_templates"][0]["decision_value_template"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope(
            generated_at="2026-06-14T01:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template=template,
        )

    assert "decision_value_template.operator_decision_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_collection_gate_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["collection_gates"][0]["collection_gate"]["collection_route_admitted"] = True
    envelope["collection_gates"][0]["collection_gate"]["template_accepted_as_value"] = True

    errors = _validate_decision_value_collection_gate_semantics(envelope, receipt_schema)

    assert errors
    assert any("collection_gate.collection_route_admitted must be false" in error for error in errors)
    assert any("collection_gate.template_accepted_as_value must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_collection_gate_rejects_secret_values() -> None:
    template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
    template["decision_value_templates"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_collection_gate_envelope(
            generated_at="2026-06-14T01:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template=template,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
