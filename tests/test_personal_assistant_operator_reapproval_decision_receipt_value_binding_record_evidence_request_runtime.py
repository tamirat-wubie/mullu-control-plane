"""Tests for personal-assistant operator value-binding record evidence requests.

Purpose: prove request-only operator evidence slots do not submit, accept, or
bind operator values after record admission preflight blocks.
Governance scope: admission-preflight refs, requested evidence slots, receipt
conformance, private-payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant value-binding record evidence
request builders and schema validation helpers.
Invariants:
  - Runtime envelope validates against the value-binding record evidence request
    schema.
  - Evidence requests do not serialize raw operator values or accept evidence.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request import (
    _validate_value_binding_record_evidence_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_RECORD_EVIDENCE_REQUEST_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_is_request_only() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request()
    schema = _load_schema(VALUE_BINDING_RECORD_EVIDENCE_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    evidence_kinds = {slot["evidence_kind"] for slot in envelope["evidence_requests"]}

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_record_evidence_request_semantics(envelope, receipt_schema) == ()
    assert envelope["evidence_request_count"] == 4
    assert envelope["summary"]["requested_slot_count"] == 4
    assert envelope["summary"]["submitted_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert evidence_kinds == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_record_admission_preflight"
    assert envelope["decision"] == "blocked"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_record_evidence_request_allowed"] is True
    assert envelope["effect_boundary"]["evidence_request_issued"] is True
    assert envelope["effect_boundary"]["evidence_request_is_submission"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["operator_value_collected"] is False
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["binding_record_admitted"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["assurance"]["outcome"] == "AwaitingEvidence"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_rejects_empty_preflights() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    preflight["admission_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
            generated_at="2026-06-14T00:22:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_admission_preflight=preflight,
        )

    assert "requires at least one slot" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_rejects_source_boundary_drift() -> None:
    preflight = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    )
    preflight["effect_boundary"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
            generated_at="2026-06-14T00:22:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_admission_preflight=preflight,
        )

    assert "value binding record admission preflight effect_boundary.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_rejects_claimed_operator_value() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    preflight["admission_preflights"][0]["missing_operator_evidence"]["operator_submitted_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
            generated_at="2026-06-14T00:22:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_admission_preflight=preflight,
        )

    assert "missing_operator_evidence.operator_submitted_value_present must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_rejects_mutated_decision_values() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    preflight["admission_preflights"][0]["missing_operator_evidence"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
            generated_at="2026-06-14T00:22:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_admission_preflight=preflight,
        )

    assert "allowed_decision_values must preserve policy" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_request_rejects_secret_values() -> None:
    preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    preflight["admission_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_request_envelope(
            generated_at="2026-06-14T00:22:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_admission_preflight=preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
