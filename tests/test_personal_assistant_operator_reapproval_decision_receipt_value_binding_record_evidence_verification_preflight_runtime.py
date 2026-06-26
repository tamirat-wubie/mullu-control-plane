"""Tests for operator value-binding evidence verification preflight.

Purpose: prove submitted evidence refs can be scoped for verifier requirements
without verifying evidence, accepting values, admitting records, or granting
execution authority.
Governance scope: submitted-evidence refs, verification preflight denial,
private-payload redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant evidence verification preflight builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the evidence verification preflight schema.
  - Verifier requirements are declared but unsatisfied.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight import (
    _validate_evidence_verification_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_VERIFICATION_PREFLIGHT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_blocks_verification() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    schema = _load_schema(EVIDENCE_VERIFICATION_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    evidence_kinds = {record["evidence_kind"] for record in envelope["verification_preflights"]}
    requirement_kinds = {
        requirement["requirement_kind"]
        for record in envelope["verification_preflights"]
        for requirement in record["verification_preflight"]["verification_requirements"]
    }

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_evidence_verification_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["verification_preflight_count"] == 4
    assert envelope["summary"]["submitted_evidence_count"] == 4
    assert envelope["summary"]["verification_requirement_count"] == 20
    assert envelope["summary"]["satisfied_verification_requirement_count"] == 0
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["verification_state"] == "submitted_refs_scoped_not_verified"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert evidence_kinds == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert requirement_kinds == EXPECTED_REQUIREMENT_KINDS
    assert envelope["effect_boundary"]["verification_requirement_planning_allowed"] is True
    assert envelope["effect_boundary"]["verifier_identity_bound"] is False
    assert envelope["effect_boundary"]["evidence_verified"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_rejects_empty_records() -> None:
    acceptance = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight()
    acceptance["acceptance_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_envelope(
            generated_at="2026-06-14T00:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight=acceptance,
        )

    assert "requires at least one acceptance preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_rejects_source_acceptance_drift() -> None:
    acceptance = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight()
    )
    acceptance["effect_boundary"]["evidence_verified"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_envelope(
            generated_at="2026-06-14T00:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight=acceptance,
        )

    assert "evidence acceptance preflight effect_boundary.evidence_verified must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_detects_requirement_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["verification_preflights"][0]["verification_preflight"]["verification_requirements"][0]["satisfied"] = True
    envelope["verification_preflights"][0]["verification_preflight"]["satisfied_verification_requirement_count"] = 1

    errors = _validate_evidence_verification_preflight_semantics(envelope, receipt_schema)

    assert errors
    assert any("verification_requirements[0].satisfied must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_rejects_authority_drift() -> None:
    acceptance = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight()
    acceptance["acceptance_preflights"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_envelope(
            generated_at="2026-06-14T00:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight=acceptance,
        )

    assert "evidence acceptance preflight authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_rejects_secret_values() -> None:
    acceptance = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight()
    acceptance["acceptance_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_envelope(
            generated_at="2026-06-14T00:30:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight=acceptance,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
