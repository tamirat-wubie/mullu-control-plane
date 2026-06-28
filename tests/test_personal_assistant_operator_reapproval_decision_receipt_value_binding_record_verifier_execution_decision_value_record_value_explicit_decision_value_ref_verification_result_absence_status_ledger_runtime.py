"""Tests for verifier execution explicit decision value-ref result absence ledger.

Purpose: prove absent verification results remain compactly visible as ledger
status without becoming accepted values, stored records, execution, or authority.
Governance scope: verification-result absence status ledger, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant verification result absence ledger builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the absence status ledger schema.
  - Verification result absence remains status only.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_verification_result_absence_status_ledger_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_absence_status_ledger_blocks_authority() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
    schema = _load_schema(VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_verification_result_absence_status_ledger_semantics(envelope, receipt_schema) == ()
    assert envelope["absence_status_count"] == 4
    assert envelope["summary"]["verification_result_requested_count"] == 4
    assert envelope["summary"]["verification_result_absence_recorded_count"] == 4
    assert envelope["summary"]["verification_result_absence_status_ledgered_count"] == 4
    assert envelope["summary"]["verification_result_present_count"] == 0
    assert envelope["summary"]["submitted_ref_only_count"] == 4
    assert envelope["summary"]["verified_ref_count"] == 0
    assert envelope["summary"]["accepted_ref_count"] == 0
    assert envelope["summary"]["bound_ref_count"] == 0
    assert envelope["summary"]["validated_ref_count"] == 0
    assert envelope["summary"]["stored_ref_count"] == 0
    assert envelope["summary"]["raw_result_payload_count"] == 0
    assert envelope["summary"]["raw_operator_value_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(status["ref_name"] for status in envelope["absence_statuses"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(status["verification_result_absence_status_ledgered"] is True for status in envelope["absence_statuses"])
    assert all(status["verification_result_present"] is False for status in envelope["absence_statuses"])
    assert all(status["verified"] is False for status in envelope["absence_statuses"])
    assert all(status["accepted"] is False for status in envelope["absence_statuses"])
    assert all(status["grants_authority"] is False for status in envelope["absence_statuses"])
    assert envelope["receipt"]["metadata"]["verification_result_absence_status_ledgered"] is True
    assert envelope["receipt"]["metadata"]["verification_result_present"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_absence_status_ledger_rejects_missing_source_record() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence()
    source["absence_records"] = [
        item for item in source["absence_records"] if item["ref_name"] != "operator_signature_ref"
    ]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope(
            generated_at="2026-06-14T02:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence=source,
        )

    assert "canonical required refs" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_absence_status_ledger_rejects_source_authority_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence()
    source["effect_boundary"]["authority_granted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope(
            generated_at="2026-06-14T02:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence=source,
        )

    assert "effect_boundary.authority_granted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_absence_status_ledger_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["absence_statuses"][0]["verification_result_present"] = True
    envelope["absence_statuses"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_verification_result_absence_status_ledger_semantics(envelope, receipt_schema)

    assert errors
    assert any("absence_statuses[0].verification_result_present must be False" in error for error in errors)
    assert any("absence_statuses[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_absence_status_ledger_rejects_secret_values() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence()
    source["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_envelope(
            generated_at="2026-06-14T02:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence=source,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
