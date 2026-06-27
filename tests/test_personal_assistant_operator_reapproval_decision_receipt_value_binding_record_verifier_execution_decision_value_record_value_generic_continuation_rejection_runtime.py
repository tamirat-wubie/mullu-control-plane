"""Tests for verifier execution record value generic continuation rejection.

Purpose: prove generic continuation cannot satisfy operator decision-value
record value requirements or grant verifier execution authority.
Governance scope: generic-continuation rejection, private-payload redaction,
and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant generic-continuation rejection builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the generic-continuation rejection schema.
  - Generic continuation is rejected as a non-value input.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection import (
    EXPECTED_RULE_IDS,
    _validate_generic_continuation_rejection_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
GENERIC_CONTINUATION_REJECTION_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_record_value_generic_continuation_rejection_blocks_value_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
    schema = _load_schema(GENERIC_CONTINUATION_REJECTION_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_rejection = envelope["generic_continuation_rejections"][0]["generic_continuation_rejection"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_generic_continuation_rejection_semantics(envelope, receipt_schema) == ()
    assert envelope["generic_continuation_rejection_count"] == 20
    assert envelope["summary"]["generic_continuation_rejected_count"] == 20
    assert envelope["summary"]["actual_operator_decision_value_absent_count"] == 20
    assert envelope["summary"]["generic_continuation_accepted_as_value_count"] == 0
    assert envelope["summary"]["operator_decision_value_present_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["summary"]["rule_count"] == 100
    assert envelope["generic_continuation_rejection_state"] == "generic_continuation_rejected_not_operator_value"
    assert envelope["effect_boundary"]["generic_continuation_rejected"] is True
    assert envelope["effect_boundary"]["generic_continuation_accepted_as_value"] is False
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_value_record_created"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert tuple(rule["rule_id"] for rule in first_rejection["rejection_rules"]) == EXPECTED_RULE_IDS
    assert all(rule["decision"] == "reject" for rule in first_rejection["rejection_rules"])
    assert all(rule["grants_authority"] is False for rule in first_rejection["rejection_rules"])


def test_runtime_verifier_execution_record_value_generic_continuation_rejection_rejects_empty_source_records() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
    absence["record_value_absences"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope(
            generated_at="2026-06-14T01:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence=absence,
        )

    assert "requires at least one record value absence" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_record_value_generic_continuation_rejection_rejects_source_value_presence_drift() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
    absence["record_value_absences"][0]["record_value_absence"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope(
            generated_at="2026-06-14T01:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence=absence,
        )

    assert "record_value_absence.operator_decision_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_record_value_generic_continuation_rejection_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["generic_continuation_rejections"][0]["generic_continuation_rejection"]["generic_continuation_accepted_as_value"] = True
    envelope["generic_continuation_rejections"][0]["generic_continuation_rejection"]["rejection_rules"][0]["grants_authority"] = True

    errors = _validate_generic_continuation_rejection_semantics(envelope, receipt_schema)

    assert errors
    assert any("generic_continuation_rejection.generic_continuation_accepted_as_value must be false" in error for error in errors)
    assert any("rejection_rules[0] must grant no authority" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_record_value_generic_continuation_rejection_rejects_secret_values() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence()
    absence["record_value_absences"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_envelope(
            generated_at="2026-06-14T01:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence=absence,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
