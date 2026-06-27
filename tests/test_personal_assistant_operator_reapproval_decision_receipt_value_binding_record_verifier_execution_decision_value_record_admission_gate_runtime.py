"""Tests for verifier execution operator decision-value record admission gate.

Purpose: prove the future operator value-record admission gate is checked
but remains blocked until an actual explicit operator decision value exists.
Governance scope: decision-value record admission gate, private-payload redaction,
and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant record-admission-gate builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the record-admission-gate schema.
  - No admission gate, record path, collection gate, value record, or authority is
    admitted.
  - Verifier execution remains blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate import (
    _validate_decision_value_record_admission_gate_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_RECORD_ADMISSION_GATE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_record_admission_gate_blocks_record_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate()
    schema = _load_schema(DECISION_VALUE_RECORD_ADMISSION_GATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_admission_gate = envelope["record_admission_gates"][0]["record_admission_gate"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_record_admission_gate_semantics(envelope, receipt_schema) == ()
    assert envelope["record_admission_gate_count"] == 20
    assert envelope["summary"]["record_contract_ready_count"] == 20
    assert envelope["summary"]["record_admission_gate_creation_count"] == 20
    assert envelope["summary"]["record_admission_gate_admission_count"] == 0
    assert envelope["summary"]["record_path_admission_count"] == 0
    assert envelope["summary"]["collection_gate_satisfied_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["operator_value_record_admission_count"] == 0
    assert envelope["summary"]["operator_decision_value_storage_count"] == 0
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["record_admission_gate_state"] == "operator_decision_value_record_admission_gate_blocked_awaiting_actual_operator_value"
    assert envelope["effect_boundary"]["operator_decision_value_record_admission_gate_projection_allowed"] is True
    assert envelope["effect_boundary"]["record_contract_ready"] is True
    assert envelope["effect_boundary"]["record_admission_gate_admitted"] is False
    assert envelope["effect_boundary"]["record_path_admitted"] is False
    assert envelope["effect_boundary"]["operator_value_record_created"] is False
    assert envelope["effect_boundary"]["operator_value_record_admitted"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert first_admission_gate["accepted_record_kinds"] == [
        "explicit_operator_approval",
        "explicit_operator_rejection",
        "explicit_operator_revision_request",
        "explicit_operator_expiry",
    ]
    assert first_admission_gate["requires_record_path_admitted"] is True
    assert first_admission_gate["requires_collection_gate_satisfied"] is True
    assert first_admission_gate["requires_actual_operator_value"] is True


def test_runtime_verifier_execution_decision_value_record_admission_gate_rejects_empty_source_records() -> None:
    record_path = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path()
    record_path["record_paths"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate_envelope(
            generated_at="2026-06-14T01:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path=record_path,
        )

    assert "requires at least one record path" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_record_admission_gate_rejects_source_record_path_admission_drift() -> None:
    record_path = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path()
    record_path["record_paths"][0]["record_path"]["record_path_admitted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate_envelope(
            generated_at="2026-06-14T01:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path=record_path,
        )

    assert "record_path.record_path_admitted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_record_admission_gate_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["record_admission_gates"][0]["record_admission_gate"]["record_admission_gate_admitted"] = True
    envelope["record_admission_gates"][0]["record_admission_gate"]["operator_value_record_created"] = True

    errors = _validate_decision_value_record_admission_gate_semantics(envelope, receipt_schema)

    assert errors
    assert any("record_admission_gate.record_admission_gate_admitted must be false" in error for error in errors)
    assert any("record_admission_gate.operator_value_record_created must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_record_admission_gate_rejects_secret_values() -> None:
    record_path = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path()
    record_path["record_paths"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_admission_gate_envelope(
            generated_at="2026-06-14T01:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_path=record_path,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
