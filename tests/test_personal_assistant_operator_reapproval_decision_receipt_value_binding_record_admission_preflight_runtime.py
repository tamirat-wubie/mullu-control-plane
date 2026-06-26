"""Tests for personal-assistant operator decision value-binding record preflights.

Purpose: prove admission preflights block value-binding records while operator
value, identity, signature, and receipt evidence are absent.
Governance scope: record-guard refs, missing-evidence detection, blocked
admission, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant value-binding record admission
preflight builders and schema validation helpers.
Invariants:
  - Runtime envelope validates against the value-binding record admission schema.
  - Admission preflights do not create or admit value-binding records.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight import (
    _validate_value_binding_record_admission_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_blocks_missing_evidence() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight()
    schema = _load_schema(VALUE_BINDING_RECORD_ADMISSION_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    preflight = envelope["admission_preflights"][0]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_record_admission_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["admission_preflight_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_record_guard"
    assert envelope["assurance"]["outcome"] == "GovernanceBlocked"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_record_admission_preflight_allowed"] is True
    assert envelope["effect_boundary"]["missing_operator_evidence_detection_allowed"] is True
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["binding_record_admitted"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert preflight["value_binding_record_guard_ref"]["guard_outcome"] == "AwaitingEvidence"
    assert preflight["missing_operator_evidence"]["operator_submitted_value_present"] is False
    assert preflight["missing_operator_evidence"]["operator_identity_ref_present"] is False
    assert preflight["missing_operator_evidence"]["operator_signature_ref_present"] is False
    assert preflight["missing_operator_evidence"]["decision_receipt_ref_present"] is False
    assert preflight["missing_operator_evidence"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert preflight["admission_decision"]["decision"] == "blocked"
    assert preflight["admission_decision"]["outcome"] == "GovernanceBlocked"
    assert preflight["admission_decision"]["binding_record_created"] is False
    assert preflight["admission_decision"]["binding_record_admitted"] is False
    assert preflight["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_missing_governed_operator_value_binding_record_evidence"
    )
    assert preflight["execution_admission_block"]["dispatch_allowed"] is False
    assert preflight["receipt"]["decision"] == "blocked"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_rejects_empty_guard_source() -> None:
    guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    guard["record_guards"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
            generated_at="2026-06-14T00:21:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_guard=guard,
        )

    assert "requires at least one record guard" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_rejects_source_boundary_drift() -> None:
    guard = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    )
    guard["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
            generated_at="2026-06-14T00:21:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_guard=guard,
        )

    assert "value binding record guard effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_rejects_claimed_record_creation() -> None:
    guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    guard["record_guards"][0]["record_candidate_requirements"]["binding_record_created"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
            generated_at="2026-06-14T00:21:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_guard=guard,
        )

    assert "record_candidate_requirements.binding_record_created must be false" in str(exc_info.value)
    assert guard["record_guards"][0]["record_guard_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_rejects_mutated_decision_values() -> None:
    guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    guard["record_guards"][0]["record_candidate_requirements"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
            generated_at="2026-06-14T00:21:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_guard=guard,
        )

    assert "allowed_decision_values must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_rejects_secret_values() -> None:
    guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    guard["record_guards"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_admission_preflight_envelope(
            generated_at="2026-06-14T00:21:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_guard=guard,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
