"""Tests for operator value-binding verifier execution preflight.

Purpose: prove verifier execution can be requested as a no-effect preflight
without running a verifier, validating refs, verifying evidence, admitting
records, or granting execution authority.
Governance scope: verifier execution request preparation, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant verifier execution preflight builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the verifier execution preflight schema.
  - Verifier execution request preparation does not execute the verifier.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight import (
    _validate_verifier_execution_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VERIFIER_EXECUTION_PREFLIGHT_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_blocks_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    schema = _load_schema(VERIFIER_EXECUTION_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    coverage = {
        evidence_kind: {
            record["requirement_kind"]
            for record in envelope["verifier_execution_preflights"]
            if record["evidence_kind"] == evidence_kind
        }
        for evidence_kind in {record["evidence_kind"] for record in envelope["verifier_execution_preflights"]}
    }

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_verifier_execution_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["verifier_execution_preflight_count"] == 20
    assert envelope["summary"]["submitted_verifier_ref_count"] == 20
    assert envelope["summary"]["verifier_execution_request_prepared_count"] == 20
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["verifier_execution_started_count"] == 0
    assert envelope["summary"]["verifier_execution_completed_count"] == 0
    assert envelope["summary"]["verifier_result_count"] == 0
    assert envelope["summary"]["validated_verifier_ref_count"] == 0
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["verifier_execution_preflight_state"] == "verifier_execution_requested_not_run_not_validated"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert set(coverage) == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert all(requirement_kinds == EXPECTED_REQUIREMENT_KINDS for requirement_kinds in coverage.values())
    assert envelope["effect_boundary"]["verifier_execution_request_preparation_allowed"] is True
    assert envelope["effect_boundary"]["verifier_execution_allowed"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["verifier_ref_validated"] is False
    assert envelope["effect_boundary"]["evidence_verified"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_rejects_empty_source_records() -> None:
    validation_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    validation_preflight["verifier_validation_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope(
            generated_at="2026-06-14T00:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight=validation_preflight,
        )

    assert "requires at least one verifier validation preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_rejects_source_validation_drift() -> None:
    validation_preflight = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    )
    validation_preflight["effect_boundary"]["verifier_ref_validated"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope(
            generated_at="2026-06-14T00:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight=validation_preflight,
        )

    assert "verifier validation preflight effect_boundary.verifier_ref_validated must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_rejects_source_ready_for_execution() -> None:
    validation_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    validation_preflight["verifier_validation_preflights"][0]["verifier_validation_preflight"]["ready_for_verifier_execution"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope(
            generated_at="2026-06-14T00:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight=validation_preflight,
        )

    assert "verifier_validation_preflight.ready_for_verifier_execution must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["verifier_execution_preflights"][0]["verifier_execution_preflight"]["verifier_execution_started"] = True

    errors = _validate_verifier_execution_preflight_semantics(envelope, receipt_schema)

    assert errors
    assert any("verifier_execution_preflight.verifier_execution_started must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_rejects_authority_drift() -> None:
    validation_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    validation_preflight["verifier_validation_preflights"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope(
            generated_at="2026-06-14T00:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight=validation_preflight,
        )

    assert "verifier validation preflight authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_rejects_secret_values() -> None:
    validation_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    validation_preflight["verifier_validation_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight_envelope(
            generated_at="2026-06-14T00:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight=validation_preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
