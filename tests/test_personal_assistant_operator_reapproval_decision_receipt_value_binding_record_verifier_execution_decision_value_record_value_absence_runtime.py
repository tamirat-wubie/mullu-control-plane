"""Tests for verifier execution operator decision-value record value absence.

Purpose: prove actual operator value absence is projected after the record
value collection gate without collecting or admitting an operator value.
Governance scope: decision-value record value absence, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant record-value-absence builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the record-value-absence schema.
  - No collection gate, value record, verifier execution, or authority is
    admitted.
  - Secret-like values and raw private payloads are rejected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence import (
    _validate_decision_value_record_value_absence_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_RECORD_VALUE_ABSENCE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_record_value_absence_blocks_record_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
    schema = _load_schema(DECISION_VALUE_RECORD_VALUE_ABSENCE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_absence = envelope["record_value_absences"][0]["record_value_absence"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_record_value_absence_semantics(envelope, receipt_schema) == ()
    assert envelope["record_value_absence_count"] == 20
    assert envelope["summary"]["record_contract_ready_count"] == 20
    assert envelope["summary"]["actual_operator_decision_value_absent_count"] == 20
    assert envelope["summary"]["record_value_absence_admission_count"] == 0
    assert envelope["summary"]["record_value_collection_gate_satisfied_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["operator_decision_value_storage_count"] == 0
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["record_value_absence_state"] == "operator_decision_value_record_value_absent_not_collected_not_admitted"
    assert envelope["effect_boundary"]["operator_decision_value_record_value_absence_projection_allowed"] is True
    assert envelope["effect_boundary"]["actual_operator_decision_value_absent"] is True
    assert envelope["effect_boundary"]["record_value_collection_gate_satisfied"] is False
    assert envelope["effect_boundary"]["operator_value_record_created"] is False
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert first_absence["requires_record_value_collection_gate_satisfied"] is True
    assert first_absence["requires_actual_operator_value"] is True
    assert first_absence["actual_operator_decision_value_absent"] is True


def test_runtime_verifier_execution_decision_value_record_value_absence_rejects_empty_source_records() -> None:
    collection_gate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate()
    collection_gate["record_value_collection_gates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence_envelope(
            generated_at="2026-06-14T01:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate=collection_gate,
        )

    assert "requires at least one record value collection gate" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_record_value_absence_rejects_source_collection_gate_satisfaction_drift() -> None:
    collection_gate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate()
    collection_gate["record_value_collection_gates"][0]["record_value_collection_gate"]["record_value_collection_gate_satisfied"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence_envelope(
            generated_at="2026-06-14T01:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate=collection_gate,
        )

    assert "record_value_collection_gate.record_value_collection_gate_satisfied must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_record_value_absence_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["record_value_absences"][0]["record_value_absence"]["actual_operator_decision_value_absent"] = False
    envelope["record_value_absences"][0]["record_value_absence"]["operator_value_record_created"] = True

    errors = _validate_decision_value_record_value_absence_semantics(envelope, receipt_schema)

    assert errors
    assert any("record_value_absence.actual_operator_decision_value_absent must be true" in error for error in errors)
    assert any("record_value_absence.operator_value_record_created must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_record_value_absence_rejects_secret_values() -> None:
    collection_gate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate()
    collection_gate["record_value_collection_gates"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence_envelope(
            generated_at="2026-06-14T01:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_collection_gate=collection_gate,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
