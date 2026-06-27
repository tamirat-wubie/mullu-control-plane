"""Tests for verifier execution operator decision-value request.

Purpose: prove operator decision value requests are projected without
collecting, submitting, or admitting an operator decision value.
Governance scope: decision-value request, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant decision-value request builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the decision-value request schema.
  - No operator approval or rejection is produced.
  - Verifier execution and authority grant remain blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request import (
    _validate_decision_value_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_REQUEST_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_request_blocks_value_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request()
    schema = _load_schema(DECISION_VALUE_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_request = envelope["decision_value_requests"][0]["decision_value_request"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_request_semantics(envelope, receipt_schema) == ()
    assert envelope["decision_value_request_count"] == 20
    assert envelope["summary"]["operator_decision_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_request_count"] == 20
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_decision_present_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["operator_approval_rejection_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["decision_value_request_state"] == "operator_decision_value_requested_not_collected_not_admitted"
    assert envelope["effect_boundary"]["operator_decision_value_request_projection_allowed"] is True
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_decision_value_collected"] is False
    assert envelope["effect_boundary"]["operator_decision_value_submitted"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert first_request["accepted_decision_values"] == ["approved", "rejected", "revise_requested", "expired"]


def test_runtime_verifier_execution_decision_value_request_rejects_empty_source_records() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence()
    absence["decision_value_absences"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request_envelope(
            generated_at="2026-06-14T01:15:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence=absence,
        )

    assert "requires at least one decision-value absence" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_request_rejects_source_value_drift() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence()
    absence["decision_value_absences"][0]["decision_value_absence"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request_envelope(
            generated_at="2026-06-14T01:15:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence=absence,
        )

    assert "decision_value_absence.operator_decision_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_request_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["decision_value_requests"][0]["decision_value_request"]["operator_approval_granted"] = True

    errors = _validate_decision_value_request_semantics(envelope, receipt_schema)

    assert errors
    assert any("decision_value_request.operator_approval_granted must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_request_rejects_secret_values() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence()
    absence["decision_value_absences"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request_envelope(
            generated_at="2026-06-14T01:15:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_absence=absence,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
