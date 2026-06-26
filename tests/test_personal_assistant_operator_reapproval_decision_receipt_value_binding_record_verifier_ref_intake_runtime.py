"""Tests for operator value-binding verifier ref intake.

Purpose: prove verifier refs can be recorded as refs only without validating
the refs, satisfying verification requirements, verifying evidence, admitting
records, or granting execution authority.
Governance scope: verifier-ref intake, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant verifier-ref intake builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the verifier ref intake schema.
  - Verifier refs remain unvalidated and unbound.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake import (
    _validate_verifier_ref_intake_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VERIFIER_REF_INTAKE_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_blocks_validation() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    schema = _load_schema(VERIFIER_REF_INTAKE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    coverage = {
        evidence_kind: {record["requirement_kind"] for record in envelope["verifier_ref_records"] if record["evidence_kind"] == evidence_kind}
        for evidence_kind in {record["evidence_kind"] for record in envelope["verifier_ref_records"]}
    }

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_verifier_ref_intake_semantics(envelope, receipt_schema) == ()
    assert envelope["verifier_ref_record_count"] == 20
    assert envelope["summary"]["submitted_verifier_ref_count"] == 20
    assert envelope["summary"]["validated_verifier_ref_count"] == 0
    assert envelope["summary"]["satisfied_verification_requirement_count"] == 0
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["intake_state"] == "verifier_refs_recorded_not_validated_not_bound"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert set(coverage) == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert all(requirement_kinds == EXPECTED_REQUIREMENT_KINDS for requirement_kinds in coverage.values())
    assert envelope["effect_boundary"]["verifier_ref_recording_allowed"] is True
    assert envelope["effect_boundary"]["verifier_ref_validated"] is False
    assert envelope["effect_boundary"]["evidence_verified"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_rejects_empty_source_records() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    preflight["verification_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
            generated_at="2026-06-14T00:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=preflight,
        )

    assert "requires at least one verifier ref record" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_rejects_source_verification_drift() -> None:
    preflight = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    )
    preflight["effect_boundary"]["evidence_verified"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
            generated_at="2026-06-14T00:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=preflight,
        )

    assert "evidence verification preflight effect_boundary.evidence_verified must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_rejects_requirement_drift() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    preflight["verification_preflights"][0]["verification_preflight"]["verification_requirements"][0]["ref_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
            generated_at="2026-06-14T00:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=preflight,
        )

    assert "verification requirement ref_present must be False" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["verifier_ref_records"][0]["verifier_ref"]["verifier_ref_validated"] = True

    errors = _validate_verifier_ref_intake_semantics(envelope, receipt_schema)

    assert errors
    assert any("verifier_ref.verifier_ref_validated must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_rejects_authority_drift() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    preflight["verification_preflights"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
            generated_at="2026-06-14T00:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=preflight,
        )

    assert "evidence verification preflight authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_rejects_secret_values() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    preflight["verification_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_ref_intake_envelope(
            generated_at="2026-06-14T00:35:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight=preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
