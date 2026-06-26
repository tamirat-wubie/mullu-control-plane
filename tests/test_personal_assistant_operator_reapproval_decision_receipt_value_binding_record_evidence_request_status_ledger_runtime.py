"""Tests for operator value-binding evidence request status ledgers.

Purpose: prove the status ledger records requested/not-submitted evidence
request state without submission, acceptance, binding, or execution authority.
Governance scope: request refs, status records, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant value-binding evidence request status ledger
builders and schema validation helpers.
Invariants:
  - Runtime envelope validates against the status ledger schema.
  - Status records do not submit or accept operator evidence.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger import (
    _validate_value_binding_record_evidence_request_status_ledger_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
STATUS_LEDGER_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_records_requested_not_submitted() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger()
    schema = _load_schema(STATUS_LEDGER_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_record_evidence_request_status_ledger_semantics(envelope, receipt_schema) == ()
    assert envelope["status_record_count"] == 4
    assert envelope["summary"]["requested_not_submitted_count"] == 4
    assert envelope["summary"]["submitted_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["ledger_state"] == "requested_not_submitted"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_allowed"] is True
    assert envelope["effect_boundary"]["status_ledger_is_submission"] is False
    assert envelope["effect_boundary"]["evidence_submitted"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_rejects_empty_requests() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    request["evidence_requests"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
            generated_at="2026-06-14T00:23:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request=request,
        )

    assert "requires at least one status record" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_rejects_source_submission_overclaim() -> None:
    request = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    )
    request["effect_boundary"]["evidence_submitted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
            generated_at="2026-06-14T00:23:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request=request,
        )

    assert "value binding evidence request effect_boundary.evidence_submitted must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_rejects_slot_acceptance_overclaim() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    request["evidence_requests"][0]["submission_state"]["evidence_accepted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
            generated_at="2026-06-14T00:23:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request=request,
        )

    assert "evidence request submission_state.evidence_accepted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_rejects_raw_value_request() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    request["evidence_requests"][0]["request_contract"]["raw_value_requested"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
            generated_at="2026-06-14T00:23:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request=request,
        )

    assert "evidence request contract.raw_value_requested must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_rejects_secret_values() -> None:
    request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    request["evidence_requests"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger_envelope(
            generated_at="2026-06-14T00:23:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_evidence_request=request,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
