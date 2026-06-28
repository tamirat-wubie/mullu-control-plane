"""Tests for verifier execution explicit decision value-ref submitted-ref intake.

Purpose: prove submitted explicit decision refs are recorded as ref identifiers
only and do not become accepted, bound, stored, or executable values.
Governance scope: value-ref submitted-ref intake, private-payload redaction,
and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-ref submitted-ref intake builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the submitted-ref intake schema.
  - Submitted refs are ref-only identifiers, not raw operator values.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_submitted_ref_intake_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_SUBMITTED_REF_INTAKE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_explicit_decision_value_ref_submitted_ref_intake_blocks_acceptance() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake()
    schema = _load_schema(VALUE_REF_SUBMITTED_REF_INTAKE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_submitted_ref_intake_semantics(envelope, receipt_schema) == ()
    assert envelope["submitted_ref_record_count"] == 4
    assert envelope["summary"]["submitted_ref_recorded_count"] == 4
    assert envelope["summary"]["submitted_ref_only_count"] == 4
    assert envelope["summary"]["accepted_ref_count"] == 0
    assert envelope["summary"]["bound_ref_count"] == 0
    assert envelope["summary"]["validated_ref_count"] == 0
    assert envelope["summary"]["stored_ref_count"] == 0
    assert envelope["summary"]["raw_ref_payload_count"] == 0
    assert envelope["summary"]["raw_operator_value_count"] == 0
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(record["ref_name"] for record in envelope["submitted_ref_records"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(record["submitted_ref_recorded"] is True for record in envelope["submitted_ref_records"])
    assert all(record["submitted_ref_only"] is True for record in envelope["submitted_ref_records"])
    assert all(record["accepted"] is False for record in envelope["submitted_ref_records"])
    assert all(record["bound"] is False for record in envelope["submitted_ref_records"])
    assert all(record["grants_authority"] is False for record in envelope["submitted_ref_records"])
    assert envelope["receipt"]["metadata"]["submitted_ref_only"] is True
    assert envelope["receipt"]["metadata"]["explicit_decision_value_refs_accepted"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_verifier_execution_explicit_decision_value_ref_submitted_ref_intake_rejects_missing_source_request() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
    request["required_ref_requests"] = [
        item for item in request["required_ref_requests"] if item["ref_name"] != "operator_signature_ref"
    ]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope(
            generated_at="2026-06-14T02:10:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request=request,
        )

    assert "canonical required refs" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_submitted_ref_intake_rejects_source_acceptance_drift() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
    request["required_ref_requests"][0]["accepted"] = True
    request["required_ref_requests"][0]["grants_authority"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope(
            generated_at="2026-06-14T02:10:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request=request,
        )

    assert "operator_decision_value_ref request.accepted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_explicit_decision_value_ref_submitted_ref_intake_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["submitted_ref_records"][0]["accepted"] = True
    envelope["submitted_ref_records"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_submitted_ref_intake_semantics(envelope, receipt_schema)

    assert errors
    assert any("submitted_ref_records[0].accepted must be False" in error for error in errors)
    assert any("submitted_ref_records[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_explicit_decision_value_ref_submitted_ref_intake_rejects_secret_values() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request()
    request["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_submitted_ref_intake_envelope(
            generated_at="2026-06-14T02:10:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request=request,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
