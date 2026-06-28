"""Tests for verifier execution explicit decision value-ref status ledger.

Purpose: prove required operator decision refs remain compactly visible as
missing and unbound before any value-binding step.
Governance scope: value-ref status ledger, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-ref status ledger builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the value-ref status ledger schema.
  - Required refs are summarized as missing slots, not accepted values.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_status_ledger_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_STATUS_LEDGER_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_status_ledger_blocks_binding() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
    schema = _load_schema(VALUE_REF_STATUS_LEDGER_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_status_ledger_semantics(envelope, receipt_schema) == ()
    assert envelope["required_ref_status_count"] == 4
    assert envelope["summary"]["required_ref_missing_count"] == 4
    assert envelope["summary"]["required_ref_present_count"] == 0
    assert envelope["summary"]["required_ref_bound_count"] == 0
    assert envelope["summary"]["required_ref_validated_count"] == 0
    assert envelope["summary"]["source_preflight_item_count"] == 80
    assert envelope["summary"]["observed_slot_count"] == 80
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(status["ref_name"] for status in envelope["required_ref_statuses"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(status["missing"] is True for status in envelope["required_ref_statuses"])
    assert all(status["present"] is False for status in envelope["required_ref_statuses"])
    assert all(status["bound"] is False for status in envelope["required_ref_statuses"])
    assert all(status["grants_authority"] is False for status in envelope["required_ref_statuses"])
    assert envelope["receipt"]["metadata"]["required_value_refs_missing"] is True
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_explicit_decision_value_ref_status_ledger_rejects_missing_source_slot() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
    for record in preflight["explicit_decision_value_ref_preflights"]:
        record["explicit_decision_value_ref_preflight"]["required_value_refs"] = [
            slot
            for slot in record["explicit_decision_value_ref_preflight"]["required_value_refs"]
            if slot["ref_name"] != "operator_signature_ref"
        ]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope(
            generated_at="2026-06-14T02:00:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight=preflight,
        )

    assert "operator_signature_ref must be observed" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_status_ledger_rejects_source_authority_drift() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
    preflight["effect_boundary"]["authority_granted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope(
            generated_at="2026-06-14T02:00:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight=preflight,
        )

    assert "effect_boundary.authority_granted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_status_ledger_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["required_ref_statuses"][0]["present"] = True
    envelope["required_ref_statuses"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_status_ledger_semantics(envelope, receipt_schema)

    assert errors
    assert any("required_ref_statuses[0].present must be False" in error for error in errors)
    assert any("required_ref_statuses[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_status_ledger_rejects_secret_values() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight()
    preflight["explicit_decision_value_ref_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger_envelope(
            generated_at="2026-06-14T02:00:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight=preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
