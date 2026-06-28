"""Tests for verifier execution explicit decision value-ref preflight.

Purpose: prove required operator decision value refs remain absent and unbound
before any value-binding step.
Governance scope: value-ref preflight, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-ref preflight builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the value-ref preflight schema.
  - Required refs are declared as absent slots, not accepted values.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_PREFLIGHT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_preflight_blocks_binding() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
    schema = _load_schema(VALUE_REF_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_preflight = envelope["explicit_decision_value_ref_preflights"][0]["explicit_decision_value_ref_preflight"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["explicit_decision_value_ref_preflight_count"] == 20
    assert envelope["summary"]["required_value_ref_slot_count"] == 80
    assert envelope["summary"]["required_value_ref_absent_count"] == 80
    assert envelope["summary"]["required_value_ref_present_count"] == 0
    assert envelope["summary"]["required_value_ref_bound_count"] == 0
    assert envelope["summary"]["explicit_decision_value_ref_preflight_satisfied_count"] == 0
    assert envelope["summary"]["explicit_operator_decision_value_bound_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["explicit_decision_value_ref_preflight_state"] == "explicit_decision_value_refs_absent_not_bound"
    assert envelope["effect_boundary"]["required_value_refs_declared"] is True
    assert envelope["effect_boundary"]["required_value_refs_absent"] is True
    assert envelope["effect_boundary"]["explicit_decision_value_ref_preflight_satisfied"] is False
    assert envelope["effect_boundary"]["explicit_decision_value_refs_present"] is False
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_value_record_created"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert tuple(slot["ref_name"] for slot in first_preflight["required_value_refs"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(slot["required"] is True for slot in first_preflight["required_value_refs"])
    assert all(slot["present"] is False for slot in first_preflight["required_value_refs"])
    assert all(slot["grants_authority"] is False for slot in first_preflight["required_value_refs"])


def test_runtime_verifier_execution_explicit_decision_value_ref_preflight_rejects_empty_source_records() -> None:
    candidate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
    candidate["explicit_decision_candidates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope(
            generated_at="2026-06-14T01:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate=candidate,
        )

    assert "requires at least one explicit decision candidate" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_preflight_rejects_source_candidate_drift() -> None:
    candidate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
    candidate["explicit_decision_candidates"][0]["explicit_decision_candidate"]["required_value_refs"] = ["operator_decision_value_ref"]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope(
            generated_at="2026-06-14T01:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate=candidate,
        )

    assert "required_value_refs drifted" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_preflight_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["explicit_decision_value_ref_preflights"][0]["explicit_decision_value_ref_preflight"]["required_value_refs"][0]["present"] = True
    envelope["explicit_decision_value_ref_preflights"][0]["explicit_decision_value_ref_preflight"]["required_value_refs"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_preflight_semantics(envelope, receipt_schema)

    assert errors
    assert any("required_value_refs[0].present must be false" in error for error in errors)
    assert any("required_value_refs[0].grants_authority must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_preflight_rejects_secret_values() -> None:
    candidate = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
    candidate["explicit_decision_candidates"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_envelope(
            generated_at="2026-06-14T01:55:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate=candidate,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
