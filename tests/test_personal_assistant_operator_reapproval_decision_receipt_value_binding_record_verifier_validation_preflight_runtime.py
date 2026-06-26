"""Tests for operator value-binding verifier validation preflight.

Purpose: prove verifier refs can be shape/scope checked without validating the
refs, satisfying verification requirements, verifying evidence, admitting
records, or granting execution authority.
Governance scope: verifier validation preflight, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant verifier validation preflight builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the verifier validation preflight schema.
  - Shape/scope checks do not become verifier validation or authority binding.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight import (
    _validate_verifier_validation_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VERIFIER_VALIDATION_PREFLIGHT_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_blocks_validation() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    schema = _load_schema(VERIFIER_VALIDATION_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    coverage = {
        evidence_kind: {
            record["requirement_kind"]
            for record in envelope["verifier_validation_preflights"]
            if record["evidence_kind"] == evidence_kind
        }
        for evidence_kind in {record["evidence_kind"] for record in envelope["verifier_validation_preflights"]}
    }

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_verifier_validation_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["verifier_validation_preflight_count"] == 20
    assert envelope["summary"]["submitted_verifier_ref_count"] == 20
    assert envelope["summary"]["shape_checked_verifier_ref_count"] == 20
    assert envelope["summary"]["scope_checked_verifier_ref_count"] == 20
    assert envelope["summary"]["validated_verifier_ref_count"] == 0
    assert envelope["summary"]["bound_verifier_ref_count"] == 0
    assert envelope["summary"]["satisfied_verification_requirement_count"] == 0
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["validation_preflight_state"] == "verifier_refs_scoped_for_validation_not_validated_not_bound"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert set(coverage) == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert all(requirement_kinds == EXPECTED_REQUIREMENT_KINDS for requirement_kinds in coverage.values())
    assert envelope["effect_boundary"]["verifier_ref_shape_check_allowed"] is True
    assert envelope["effect_boundary"]["verifier_ref_scope_check_allowed"] is True
    assert envelope["effect_boundary"]["verifier_ref_validated"] is False
    assert envelope["effect_boundary"]["evidence_verified"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_rejects_empty_source_records() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    intake["verifier_ref_records"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope(
            generated_at="2026-06-14T00:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake=intake,
        )

    assert "requires at least one verifier ref record" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_rejects_source_validation_drift() -> None:
    intake = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake())
    intake["effect_boundary"]["verifier_ref_validated"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope(
            generated_at="2026-06-14T00:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake=intake,
        )

    assert "verifier ref intake effect_boundary.verifier_ref_validated must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_rejects_malformed_verifier_ref() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    intake["verifier_ref_records"][0]["submitted_verifier_ref"] = "verifier-ref://personal-assistant/unscoped"
    intake["verifier_ref_records"][0]["verifier_ref"]["submitted_verifier_ref"] = "verifier-ref://personal-assistant/unscoped"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope(
            generated_at="2026-06-14T00:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake=intake,
        )

    assert "submitted_verifier_ref must preserve governed verifier-ref shape" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["verifier_validation_preflights"][0]["verifier_validation_preflight"]["verifier_ref_validated"] = True

    errors = _validate_verifier_validation_preflight_semantics(envelope, receipt_schema)

    assert errors
    assert any("verifier_validation_preflight.verifier_ref_validated must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_rejects_authority_drift() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    intake["verifier_ref_records"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope(
            generated_at="2026-06-14T00:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake=intake,
        )

    assert "verifier ref intake authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_rejects_secret_values() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    intake["verifier_ref_records"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_validation_preflight_envelope(
            generated_at="2026-06-14T00:40:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake=intake,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
