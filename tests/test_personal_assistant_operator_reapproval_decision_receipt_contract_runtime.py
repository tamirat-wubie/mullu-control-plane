"""Tests for personal-assistant operator reapproval decision receipt contracts.

Purpose: prove operator reapproval decision intake evidence can produce
no-effect future receipt contracts before execution-worker admission.
Governance scope: decision intake refs, future receipt requirements, receipt
alignment, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt contract builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the receipt contract schema.
  - Fresh operator decisions, identity refs, and signatures are not claimed.
  - Dispatch and execution-worker admission remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_intake,
    build_default_personal_assistant_operator_reapproval_decision_receipt_contract,
    build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_contract import (
    _validate_operator_reapproval_decision_receipt_contract_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_contract.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_contract_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    contract_schema = _load_schema(CONTRACT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    contract = envelope["contracts"][0]

    assert _validate_schema_instance(contract_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_contract_semantics(envelope, receipt_schema) == ()
    assert envelope["contract_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_intake"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_contract_allowed"] is True
    assert envelope["effect_boundary"]["decision_receipt_required"] is True
    assert envelope["effect_boundary"]["decision_receipt_present"] is False
    assert envelope["effect_boundary"]["fresh_operator_decision_present"] is False
    assert envelope["effect_boundary"]["operator_identity_ref_present"] is False
    assert envelope["effect_boundary"]["operator_signature_ref_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert contract["decision_intake_ref"]["wait_state"] == "awaiting_operator_reapproval"
    assert contract["decision_intake_ref"]["decision_receipt_present"] is False
    assert contract["required_receipt_contract"]["decision_receipt_present"] is False
    assert contract["required_receipt_contract"]["raw_operator_decision_serialized"] is False
    assert contract["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_operator_reapproval_decision_receipt"
    )
    assert contract["execution_admission_block"]["execution_worker_admission_allowed"] is False
    assert contract["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_contract_rejects_empty_source_intakes() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_intake()
    intake["intakes"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=intake,
        )

    assert "requires at least one intake" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_contract_rejects_source_effect_boundary_drift() -> None:
    intake = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_intake())
    intake["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=intake,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_contract_rejects_claimed_decision_receipt_in_source() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_intake()
    intake["intakes"][0]["decision_intake_request"]["decision_receipt_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=intake,
        )

    assert "decision_intake_request.decision_receipt_present must be false" in str(exc_info.value)
    assert intake["intakes"][0]["intake_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_contract_rejects_cross_approval_refs() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_intake()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_contract()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    intake["intakes"][0]["decision_intake_request"][
        "intake_request_ref"
    ] = "approval://personal-assistant/reapproval-decision-intake/pa_approval_other"
    envelope["contracts"][0]["decision_intake_ref"][
        "intake_request_ref"
    ] = "approval://personal-assistant/reapproval-decision-intake/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=intake,
        )

    assert "intake_request_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_contract_semantics(envelope, receipt_schema) == (
        "contracts[0].decision_intake_ref.intake_request_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_receipt_contract_rejects_raw_private_fields_and_secret_values() -> None:
    raw_intake = build_default_personal_assistant_operator_reapproval_decision_intake()
    secret_intake = build_default_personal_assistant_operator_reapproval_decision_intake()
    raw_intake["intakes"][0]["raw_decision_receipt"] = "private operator decision receipt"
    secret_intake["intakes"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=raw_intake,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_contract_envelope(
            generated_at="2026-06-14T00:10:00+00:00",
            operator_reapproval_decision_intake=secret_intake,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision receipt" not in str(raw_exc.value)
