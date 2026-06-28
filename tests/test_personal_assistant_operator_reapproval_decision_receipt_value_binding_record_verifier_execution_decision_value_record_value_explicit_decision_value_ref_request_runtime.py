"""Tests for verifier execution explicit decision value-ref request.

Purpose: prove required operator decision refs can be requested without being
collected, bound, stored, or treated as execution authority.
Governance scope: value-ref request projection, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-ref request builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the value-ref request schema.
  - Required refs are requested as absent evidence refs, not accepted values.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_REQUEST_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_request_blocks_collection() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
    schema = _load_schema(VALUE_REF_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_request_semantics(envelope, receipt_schema) == ()
    assert envelope["required_ref_request_count"] == 4
    assert envelope["summary"]["required_ref_requested_count"] == 4
    assert envelope["summary"]["required_ref_collected_count"] == 0
    assert envelope["summary"]["required_ref_present_count"] == 0
    assert envelope["summary"]["required_ref_bound_count"] == 0
    assert envelope["summary"]["required_ref_accepted_count"] == 0
    assert envelope["summary"]["required_ref_stored_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(request["ref_name"] for request in envelope["required_ref_requests"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(request["missing"] is True for request in envelope["required_ref_requests"])
    assert all(request["collected"] is False for request in envelope["required_ref_requests"])
    assert all(request["present"] is False for request in envelope["required_ref_requests"])
    assert all(request["bound"] is False for request in envelope["required_ref_requests"])
    assert all(request["grants_authority"] is False for request in envelope["required_ref_requests"])
    assert envelope["receipt"]["metadata"]["required_value_refs_requested"] is True
    assert envelope["receipt"]["metadata"]["required_value_refs_collected"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_explicit_decision_value_ref_request_rejects_missing_source_status() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
    ledger["required_ref_statuses"] = [
        status for status in ledger["required_ref_statuses"] if status["ref_name"] != "operator_signature_ref"
    ]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope(
            generated_at="2026-06-14T02:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger=ledger,
        )

    assert "canonical required refs" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_request_rejects_source_authority_drift() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
    ledger["required_ref_statuses"][0]["present"] = True
    ledger["required_ref_statuses"][0]["grants_authority"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope(
            generated_at="2026-06-14T02:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger=ledger,
        )

    assert "operator_decision_value_ref status.present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_request_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["required_ref_requests"][0]["collected"] = True
    envelope["required_ref_requests"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_request_semantics(envelope, receipt_schema)

    assert errors
    assert any("required_ref_requests[0].collected must be False" in error for error in errors)
    assert any("required_ref_requests[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_request_rejects_secret_values() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
    ledger["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_envelope(
            generated_at="2026-06-14T02:05:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger=ledger,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
