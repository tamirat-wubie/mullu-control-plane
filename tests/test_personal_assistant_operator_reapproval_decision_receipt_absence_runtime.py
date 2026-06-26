"""Tests for personal-assistant operator reapproval decision receipt absence.

Purpose: prove missing operator reapproval decision receipts are recorded as
blocked no-effect evidence.
Governance scope: receipt-contract refs, receipt absence, blocked execution,
private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt absence builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the absence schema.
  - Missing operator decision receipts do not admit execution workers.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_contract,
    build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_absence import (
    _validate_operator_reapproval_decision_receipt_absence_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
ABSENCE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_absence.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_absence_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    absence_schema = _load_schema(ABSENCE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    absence = envelope["absences"][0]

    assert _validate_schema_instance(absence_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_absence_semantics(envelope, receipt_schema) == ()
    assert envelope["absence_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_contract"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_absence_witness_allowed"] is True
    assert envelope["effect_boundary"]["decision_receipt_required"] is True
    assert envelope["effect_boundary"]["decision_receipt_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert absence["receipt_contract_ref"]["decision_receipt_required"] is True
    assert absence["receipt_contract_ref"]["decision_receipt_present"] is False
    assert absence["absence_witness"]["absence_reason"] == "operator_reapproval_decision_receipt_absent"
    assert absence["absence_witness"]["operator_decision_value_present"] is False
    assert absence["absence_witness"]["execution_worker_admission_allowed"] is False
    assert absence["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_missing_operator_reapproval_decision_receipt"
    )
    assert absence["execution_admission_block"]["dispatch_allowed"] is False
    assert absence["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_absence_rejects_empty_source_contracts() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    contract["contracts"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=contract,
        )

    assert "requires at least one contract" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_absence_rejects_source_effect_boundary_drift() -> None:
    contract = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_contract())
    contract["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=contract,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_absence_rejects_claimed_decision_receipt_in_source() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    contract["contracts"][0]["required_receipt_contract"]["decision_receipt_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=contract,
        )

    assert "required_receipt_contract.decision_receipt_present must be false" in str(exc_info.value)
    assert contract["contracts"][0]["contract_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_absence_rejects_cross_approval_refs() -> None:
    contract = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    contract["contracts"][0]["required_receipt_contract"][
        "required_receipt_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision/pa_approval_other"
    envelope["absences"][0]["receipt_contract_ref"][
        "required_receipt_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=contract,
        )

    assert "required_receipt_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_absence_semantics(envelope, receipt_schema) == (
        "absences[0].receipt_contract_ref.required_receipt_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_receipt_absence_rejects_raw_private_fields_and_secret_values() -> None:
    raw_contract = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    secret_contract = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    raw_contract["contracts"][0]["raw_decision_receipt"] = "private operator decision receipt"
    secret_contract["contracts"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=raw_contract,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_absence_envelope(
            generated_at="2026-06-14T00:11:00+00:00",
            operator_reapproval_decision_receipt_contract=secret_contract,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision receipt" not in str(raw_exc.value)
