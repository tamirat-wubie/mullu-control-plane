"""Tests for operator value-binding submitted evidence ref intake.

Purpose: prove submitted evidence refs are recorded without raw value storage,
evidence acceptance, binding-record admission, or execution authority.
Governance scope: status-ledger refs, submitted-evidence refs, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant submitted evidence ref intake builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the submitted evidence ref intake schema.
  - Submitted evidence refs are ref-only and not accepted.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake import (
    _validate_submitted_evidence_ref_intake_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
SUBMITTED_EVIDENCE_REF_INTAKE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_records_refs_only() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    schema = _load_schema(SUBMITTED_EVIDENCE_REF_INTAKE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    evidence_kinds = {record["evidence_kind"] for record in envelope["submission_records"]}

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_submitted_evidence_ref_intake_semantics(envelope, receipt_schema) == ()
    assert envelope["submission_record_count"] == 4
    assert envelope["summary"]["submitted_evidence_count"] == 4
    assert envelope["summary"]["submitted_evidence_ref_count"] == 4
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["intake_state"] == "submitted_refs_recorded_not_accepted"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert evidence_kinds == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert envelope["effect_boundary"]["submitted_evidence_refs_present"] is True
    assert envelope["effect_boundary"]["evidence_submitted"] is True
    assert envelope["effect_boundary"]["evidence_ref_only"] is True
    assert envelope["effect_boundary"]["raw_operator_value_present"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_rejects_empty_status_records() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    ledger["status_records"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
            generated_at="2026-06-14T00:24:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=ledger,
        )

    assert "requires at least one submitted evidence ref record" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_rejects_source_submission_drift() -> None:
    ledger = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    )
    ledger["effect_boundary"]["evidence_submitted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
            generated_at="2026-06-14T00:24:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=ledger,
        )

    assert "evidence request status ledger effect_boundary.evidence_submitted must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_rejects_source_acceptance_drift() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    ledger["status_records"][0]["status"]["evidence_accepted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
            generated_at="2026-06-14T00:24:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=ledger,
        )

    assert "evidence request status.evidence_accepted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_rejects_source_authority_drift() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    ledger["status_records"][0]["authority_status"]["authority_granted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
            generated_at="2026-06-14T00:24:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=ledger,
        )

    assert "evidence request authority_status.authority_granted must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_rejects_secret_values() -> None:
    ledger = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    ledger["status_records"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_envelope(
            generated_at="2026-06-14T00:24:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger=ledger,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
