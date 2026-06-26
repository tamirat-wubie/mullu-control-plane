"""Tests for operator value-binding verifier execution approval request.

Purpose: prove verifier execution approval can be requested without collecting
an operator decision, running a verifier, verifying evidence, or granting
execution authority.
Governance scope: approval request packet, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant verifier execution approval request builders
and schema validation helpers.
Invariants:
  - Runtime envelope validates against the verifier execution approval request schema.
  - Approval request preparation does not collect an approval decision.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request import (
    _validate_verifier_execution_approval_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VERIFIER_EXECUTION_APPROVAL_REQUEST_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIREMENT_KINDS = {
    "verifier_identity_ref",
    "verification_method_ref",
    "evidence_integrity_hash_ref",
    "source_ref_reachability_witness_ref",
    "decision_receipt_crosscheck_ref",
}


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_blocks_decision_and_execution() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request()
    schema = _load_schema(VERIFIER_EXECUTION_APPROVAL_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    coverage = {
        evidence_kind: {
            record["requirement_kind"]
            for record in envelope["verifier_execution_approval_requests"]
            if record["evidence_kind"] == evidence_kind
        }
        for evidence_kind in {record["evidence_kind"] for record in envelope["verifier_execution_approval_requests"]}
    }

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_verifier_execution_approval_request_semantics(envelope, receipt_schema) == ()
    assert envelope["verifier_execution_approval_request_count"] == 20
    assert envelope["summary"]["approval_requested_count"] == 20
    assert envelope["summary"]["operator_decision_present_count"] == 0
    assert envelope["summary"]["operator_approval_grant_count"] == 0
    assert envelope["summary"]["operator_approval_rejection_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["verifier_execution_started_count"] == 0
    assert envelope["summary"]["verifier_result_count"] == 0
    assert envelope["summary"]["validated_verifier_ref_count"] == 0
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["approval_request_state"] == "approval_requested_not_decided_not_run"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert set(coverage) == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert all(requirement_kinds == EXPECTED_REQUIREMENT_KINDS for requirement_kinds in coverage.values())
    assert envelope["effect_boundary"]["operator_approval_request_preparation_allowed"] is True
    assert envelope["effect_boundary"]["operator_approval_decision_present"] is False
    assert envelope["effect_boundary"]["operator_approval_granted"] is False
    assert envelope["effect_boundary"]["verifier_execution_allowed"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["verifier_ref_validated"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_rejects_empty_source_records() -> None:
    execution_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    execution_preflight["verifier_execution_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
            generated_at="2026-06-14T00:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=execution_preflight,
        )

    assert "requires at least one verifier execution preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_rejects_source_execution_drift() -> None:
    execution_preflight = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    )
    execution_preflight["effect_boundary"]["verifier_execution_started"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
            generated_at="2026-06-14T00:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=execution_preflight,
        )

    assert "verifier execution preflight effect_boundary.verifier_execution_started must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_rejects_source_result_drift() -> None:
    execution_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    execution_preflight["verifier_execution_preflights"][0]["verifier_execution_preflight"]["verifier_result_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
            generated_at="2026-06-14T00:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=execution_preflight,
        )

    assert "verifier_execution_preflight.verifier_result_present must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["verifier_execution_approval_requests"][0]["approval_request"]["operator_approval_granted"] = True

    errors = _validate_verifier_execution_approval_request_semantics(envelope, receipt_schema)

    assert errors
    assert any("approval_request.operator_approval_granted must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_rejects_authority_drift() -> None:
    execution_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    execution_preflight["verifier_execution_preflights"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
            generated_at="2026-06-14T00:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=execution_preflight,
        )

    assert "verifier execution preflight authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_rejects_secret_values() -> None:
    execution_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight()
    execution_preflight["verifier_execution_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_approval_request_envelope(
            generated_at="2026-06-14T00:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_preflight=execution_preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
