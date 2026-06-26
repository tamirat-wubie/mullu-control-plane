"""Tests for verifier execution operator decision-value absence.

Purpose: prove operator decision value absence is projected without collecting
or admitting an operator decision value.
Governance scope: decision-value absence, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant decision-value absence builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the decision-value absence schema.
  - No operator approval or rejection is produced.
  - Verifier execution and authority grant remain blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence import (
    _validate_decision_value_absence_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_ABSENCE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_absence_blocks_value_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence()
    schema = _load_schema(DECISION_VALUE_ABSENCE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_absence_semantics(envelope, receipt_schema) == ()
    assert envelope["decision_value_absence_count"] == 20
    assert envelope["summary"]["operator_decision_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_absent_count"] == 20
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_decision_present_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["operator_approval_rejection_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["verifier_execution_started_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["decision_value_absence_state"] == "operator_decision_value_absent_not_collected_not_admitted"
    assert envelope["effect_boundary"]["operator_decision_absence_projection_allowed"] is True
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_decision_value_collected"] is False
    assert envelope["effect_boundary"]["operator_approval_granted"] is False
    assert envelope["effect_boundary"]["operator_approval_rejected"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_decision_value_absence_rejects_empty_source_records() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight()
    preflight["decision_intake_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence_envelope(
            generated_at="2026-06-14T01:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight=preflight,
        )

    assert "requires at least one decision-intake preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_absence_rejects_source_value_drift() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight()
    preflight["decision_intake_preflights"][0]["decision_intake_preflight"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence_envelope(
            generated_at="2026-06-14T01:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight=preflight,
        )

    assert "decision_intake_preflight.operator_decision_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_absence_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["decision_value_absences"][0]["decision_value_absence"]["operator_approval_granted"] = True

    errors = _validate_decision_value_absence_semantics(envelope, receipt_schema)

    assert errors
    assert any("decision_value_absence.operator_approval_granted must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_absence_rejects_secret_values() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight()
    preflight["decision_intake_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence_envelope(
            generated_at="2026-06-14T01:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight=preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
