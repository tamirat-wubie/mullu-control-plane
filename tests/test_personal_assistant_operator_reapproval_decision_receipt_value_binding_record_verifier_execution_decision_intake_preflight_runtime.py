"""Tests for verifier execution operator decision-intake preflight.

Purpose: prove operator decision intake is preflighted without collecting or
admitting an operator decision value.
Governance scope: decision-intake preflight, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant decision-intake preflight builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the decision-intake preflight schema.
  - No operator approval or rejection is produced.
  - Verifier execution and authority grant remain blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight import (
    _validate_decision_intake_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_INTAKE_PREFLIGHT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_intake_preflight_blocks_decision_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight()
    schema = _load_schema(DECISION_INTAKE_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_intake_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["decision_intake_preflight_count"] == 20
    assert envelope["summary"]["operator_decision_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_decision_present_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["operator_approval_rejection_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["verifier_execution_started_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["decision_intake_preflight_state"] == "operator_decision_required_not_present_not_admitted"
    assert envelope["effect_boundary"]["operator_decision_requirement_check_allowed"] is True
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_approval_granted"] is False
    assert envelope["effect_boundary"]["operator_approval_rejected"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_decision_intake_preflight_rejects_empty_source_records() -> None:
    approval_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request()
    approval_request["verifier_execution_approval_requests"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight_envelope(
            generated_at="2026-06-14T00:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request=approval_request,
        )

    assert "requires at least one verifier execution approval request" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_intake_preflight_rejects_source_decision_drift() -> None:
    approval_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request()
    approval_request["verifier_execution_approval_requests"][0]["approval_request"]["operator_decision_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight_envelope(
            generated_at="2026-06-14T00:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request=approval_request,
        )

    assert "approval_request.operator_decision_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_intake_preflight_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["decision_intake_preflights"][0]["decision_intake_preflight"]["operator_approval_granted"] = True

    errors = _validate_decision_intake_preflight_semantics(envelope, receipt_schema)

    assert errors
    assert any("decision_intake_preflight.operator_approval_granted must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_intake_preflight_rejects_secret_values() -> None:
    approval_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request()
    approval_request["verifier_execution_approval_requests"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_intake_preflight_envelope(
            generated_at="2026-06-14T00:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request=approval_request,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
