"""Tests for personal-assistant operator decision value-binding contracts.

Purpose: prove binding contracts are requirements-only evidence and cannot
bind operator values or grant authority.
Governance scope: admission-preflight refs, future value-binding requirements,
blocked execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant value-binding contract builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-binding contract schema.
  - Binding contracts are not accepted as operator decision values.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract import (
    _validate_value_binding_contract_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_CONTRACT_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_contract.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_validates_as_requirements_only() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract()
    schema = _load_schema(VALUE_BINDING_CONTRACT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    contract = envelope["binding_contracts"][0]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_contract_semantics(envelope, receipt_schema) == ()
    assert envelope["binding_contract_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_admission_preflight"
    assert envelope["assurance"]["outcome"] == "AwaitingEvidence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_contract_allowed"] is True
    assert envelope["effect_boundary"]["future_value_binding_requirements_allowed"] is True
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_contract_accepted_as_value"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert contract["admission_preflight_ref"]["admission_outcome"] == "GovernanceBlocked"
    assert contract["admission_preflight_ref"]["operator_value_bound"] is False
    assert contract["binding_requirements"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert contract["binding_requirements"]["requires_explicit_operator_value"] is True
    assert contract["binding_requirements"]["operator_value_bound"] is False
    assert contract["binding_requirements"]["binding_record_created"] is False
    assert contract["binding_requirements"]["grants_execution_authority"] is False
    assert contract["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_governed_operator_value_binding_record"
    )
    assert contract["execution_admission_block"]["dispatch_allowed"] is False
    assert contract["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_rejects_empty_preflight_source() -> None:
    admission_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    admission_preflight["admission_preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
            generated_at="2026-06-14T00:19:00+00:00",
            operator_reapproval_decision_receipt_value_binding_admission_preflight=admission_preflight,
        )

    assert "requires at least one admission preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_rejects_source_boundary_drift() -> None:
    admission_preflight = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    )
    admission_preflight["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
            generated_at="2026-06-14T00:19:00+00:00",
            operator_reapproval_decision_receipt_value_binding_admission_preflight=admission_preflight,
        )

    assert "value binding admission preflight effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_rejects_claimed_bound_value() -> None:
    admission_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    admission_preflight["admission_preflights"][0]["value_binding_absence_ref"]["operator_value_bound"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
            generated_at="2026-06-14T00:19:00+00:00",
            operator_reapproval_decision_receipt_value_binding_admission_preflight=admission_preflight,
        )

    assert "value_binding_absence_ref.operator_value_bound must be false" in str(exc_info.value)
    assert admission_preflight["admission_preflights"][0]["admission_preflight_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_rejects_mutated_decision_values() -> None:
    admission_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    admission_preflight["admission_preflights"][0]["value_binding_absence_ref"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
            generated_at="2026-06-14T00:19:00+00:00",
            operator_reapproval_decision_receipt_value_binding_admission_preflight=admission_preflight,
        )

    assert "allowed_decision_values must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_contract_rejects_secret_values() -> None:
    admission_preflight = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    admission_preflight["admission_preflights"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_contract_envelope(
            generated_at="2026-06-14T00:19:00+00:00",
            operator_reapproval_decision_receipt_value_binding_admission_preflight=admission_preflight,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
