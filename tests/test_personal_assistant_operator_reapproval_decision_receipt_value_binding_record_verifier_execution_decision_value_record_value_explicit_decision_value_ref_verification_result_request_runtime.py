"""Tests for verifier execution explicit decision value-ref verification result request.

Purpose: prove verification result requests remain status-only and do not
become result presence, verification, acceptance, binding, storage, or
executable authority.
Governance scope: value-ref verification result request, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-ref verification result request builders
and schema validation helpers.
Invariants:
  - Runtime envelope validates against the result request schema.
  - Verification result request does not serialize verification result payloads.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_verification_result_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_VERIFICATION_RESULT_REQUEST_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_request_blocks_result_presence() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request()
    schema = _load_schema(VALUE_REF_VERIFICATION_RESULT_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_verification_result_request_semantics(envelope, receipt_schema) == ()
    assert envelope["result_request_record_count"] == 4
    assert envelope["summary"]["verification_preflight_checked_count"] == 4
    assert envelope["summary"]["verification_result_requested_count"] == 4
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
    assert tuple(record["ref_name"] for record in envelope["result_request_records"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(record["verification_result_requested"] is True for record in envelope["result_request_records"])
    assert all(record["verification_result_present"] is False for record in envelope["result_request_records"])
    assert all(record["verified"] is False for record in envelope["result_request_records"])
    assert all(record["accepted"] is False for record in envelope["result_request_records"])
    assert all(record["grants_authority"] is False for record in envelope["result_request_records"])
    assert envelope["receipt"]["metadata"]["verification_result_requested"] is True
    assert envelope["receipt"]["metadata"]["verification_result_present"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_request_rejects_missing_source_record() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight()
    source["verification_records"] = [
        item for item in source["verification_records"] if item["ref_name"] != "operator_signature_ref"
    ]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request_envelope(
            generated_at="2026-06-14T02:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight=source,
        )

    assert "canonical required refs" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_request_rejects_source_verification_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight()
    source["verification_records"][0]["verified"] = True
    source["verification_records"][0]["grants_authority"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request_envelope(
            generated_at="2026-06-14T02:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight=source,
        )

    assert "operator_decision_value_ref verification_record.verified must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_request_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["result_request_records"][0]["verification_result_present"] = True
    envelope["result_request_records"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_verification_result_request_semantics(envelope, receipt_schema)

    assert errors
    assert any("result_request_records[0].verification_result_present must be False" in error for error in errors)
    assert any("result_request_records[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_verification_result_request_rejects_secret_values() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight()
    source["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_request_envelope(
            generated_at="2026-06-14T02:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_preflight=source,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
