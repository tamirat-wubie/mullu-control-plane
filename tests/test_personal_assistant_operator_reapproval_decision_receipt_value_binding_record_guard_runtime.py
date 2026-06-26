"""Tests for personal-assistant operator decision value-binding record guards.

Purpose: prove binding record guards are requirements-only evidence and cannot
bind operator values or grant authority.
Governance scope: binding-contract refs, future record candidate requirements,
blocked execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant value-binding record guard builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-binding record guard schema.
  - Record guards are not accepted as operator decision values.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard import (
    _validate_value_binding_record_guard_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_RECORD_GUARD_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_validates_as_requirements_only() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard()
    schema = _load_schema(VALUE_BINDING_RECORD_GUARD_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    guard = envelope["record_guards"][0]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_record_guard_semantics(envelope, receipt_schema) == ()
    assert envelope["record_guard_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_contract"
    assert envelope["assurance"]["outcome"] == "AwaitingEvidence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_record_guard_allowed"] is True
    assert envelope["effect_boundary"]["candidate_value_binding_record_requirements_allowed"] is True
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_record_candidate_accepted"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert guard["binding_contract_ref"]["contract_outcome"] == "AwaitingEvidence"
    assert guard["binding_contract_ref"]["operator_value_bound"] is False
    assert guard["record_candidate_requirements"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert guard["record_candidate_requirements"]["requires_explicit_operator_value"] is True
    assert guard["record_candidate_requirements"]["operator_value_bound"] is False
    assert guard["record_candidate_requirements"]["binding_record_candidate_accepted"] is False
    assert guard["record_candidate_requirements"]["binding_record_created"] is False
    assert guard["record_candidate_requirements"]["grants_execution_authority"] is False
    assert guard["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_value_binding_record_admission_preflight"
    )
    assert guard["execution_admission_block"]["dispatch_allowed"] is False
    assert guard["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_rejects_empty_contract_source() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    contract["binding_contracts"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope(
            generated_at="2026-06-14T00:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_contract=contract,
        )

    assert "requires at least one binding contract" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_rejects_source_boundary_drift() -> None:
    contract = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    )
    contract["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope(
            generated_at="2026-06-14T00:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_contract=contract,
        )

    assert "value binding contract effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_rejects_claimed_bound_value() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    contract["binding_contracts"][0]["binding_requirements"]["operator_value_bound"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope(
            generated_at="2026-06-14T00:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_contract=contract,
        )

    assert "binding_requirements.operator_value_bound must be false" in str(exc_info.value)
    assert contract["binding_contracts"][0]["binding_contract_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_rejects_mutated_decision_values() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    contract["binding_contracts"][0]["binding_requirements"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope(
            generated_at="2026-06-14T00:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_contract=contract,
        )

    assert "allowed_decision_values must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_guard_rejects_secret_values() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    contract["binding_contracts"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_guard_envelope(
            generated_at="2026-06-14T00:20:00+00:00",
            operator_reapproval_decision_receipt_value_binding_contract=contract,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
