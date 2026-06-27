"""Tests for verifier execution operator decision-value template.

Purpose: prove operator decision value templates are projected without
collecting, submitting, admitting, or executing an operator decision value.
Governance scope: decision-value template, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant decision-value template builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the decision-value template schema.
  - No operator approval or rejection is produced.
  - Verifier execution and authority grant remain blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template import (
    _validate_decision_value_template_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
DECISION_VALUE_TEMPLATE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_decision_value_template_blocks_value_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
    schema = _load_schema(DECISION_VALUE_TEMPLATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_template = envelope["decision_value_templates"][0]["decision_value_template"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_decision_value_template_semantics(envelope, receipt_schema) == ()
    assert envelope["decision_value_template_count"] == 20
    assert envelope["summary"]["operator_decision_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_required_count"] == 20
    assert envelope["summary"]["operator_decision_value_template_count"] == 20
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_decision_value_collected_count"] == 0
    assert envelope["summary"]["operator_decision_value_submitted_count"] == 0
    assert envelope["summary"]["operator_decision_value_admitted_count"] == 0
    assert envelope["summary"]["operator_decision_present_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["operator_approval_rejection_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["decision_value_template_state"] == "operator_decision_value_template_prepared_not_collected_not_admitted"
    assert envelope["effect_boundary"]["operator_decision_value_template_projection_allowed"] is True
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_decision_value_collected"] is False
    assert envelope["effect_boundary"]["operator_decision_value_submitted"] is False
    assert envelope["effect_boundary"]["operator_decision_value_admitted"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert first_template["accepted_decision_values"] == ["approved", "rejected", "revise_requested", "expired"]
    assert first_template["allowed_decision_values"] == ["approved", "rejected", "revise_requested", "expired"]
    assert first_template["required_fields"] == [
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    ]


def test_runtime_verifier_execution_decision_value_template_rejects_empty_source_records() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request()
    request["decision_value_requests"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template_envelope(
            generated_at="2026-06-14T01:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request=request,
        )

    assert "requires at least one decision-value request" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_template_rejects_source_value_drift() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request()
    request["decision_value_requests"][0]["decision_value_request"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template_envelope(
            generated_at="2026-06-14T01:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request=request,
        )

    assert "decision_value_request.operator_decision_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_decision_value_template_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["decision_value_templates"][0]["decision_value_template"]["operator_approval_granted"] = True

    errors = _validate_decision_value_template_semantics(envelope, receipt_schema)

    assert errors
    assert any("decision_value_template.operator_approval_granted must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_decision_value_template_rejects_secret_values() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request()
    request["decision_value_requests"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_template_envelope(
            generated_at="2026-06-14T01:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_request=request,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
