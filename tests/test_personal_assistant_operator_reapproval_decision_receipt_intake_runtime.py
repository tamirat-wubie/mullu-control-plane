"""Tests for personal-assistant operator reapproval decision receipt intake.

Purpose: prove future operator reapproval decision receipt intake is recorded
as blocked no-effect evidence.
Governance scope: receipt-absence refs, receipt intake requirements, blocked
execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt intake builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the intake schema.
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
    build_default_personal_assistant_operator_reapproval_decision_receipt_intake,
    build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_intake import (
    _validate_operator_reapproval_decision_receipt_intake_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
INTAKE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_intake.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_intake_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    intake_schema = _load_schema(INTAKE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    intake = envelope["intakes"][0]

    assert _validate_schema_instance(intake_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_intake_semantics(envelope, receipt_schema) == ()
    assert envelope["intake_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_absence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_intake_preflight_allowed"] is True
    assert envelope["effect_boundary"]["decision_receipt_required"] is True
    assert envelope["effect_boundary"]["decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_identity_ref_present"] is False
    assert envelope["effect_boundary"]["operator_signature_ref_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert intake["absence_witness_ref"]["decision_receipt_required"] is True
    assert intake["absence_witness_ref"]["decision_receipt_present"] is False
    assert intake["receipt_intake_request"]["accepted_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert intake["receipt_intake_request"]["operator_decision_value_present"] is False
    assert intake["receipt_intake_request"]["operator_signature_ref_present"] is False
    assert intake["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_operator_reapproval_decision_receipt_intake"
    )
    assert intake["execution_admission_block"]["dispatch_allowed"] is False
    assert intake["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_intake_rejects_empty_source_absences() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    absence["absences"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=absence,
        )

    assert "requires at least one absence witness" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_intake_rejects_source_effect_boundary_drift() -> None:
    absence = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_absence())
    absence["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=absence,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_intake_rejects_claimed_decision_receipt_in_source() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    absence["absences"][0]["absence_witness"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=absence,
        )

    assert "absence_witness.operator_decision_value_present must be false" in str(exc_info.value)
    assert absence["absences"][0]["absence_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_intake_rejects_cross_approval_refs() -> None:
    absence = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    absence["absences"][0]["receipt_contract_ref"][
        "required_receipt_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision/pa_approval_other"
    envelope["intakes"][0]["absence_witness_ref"][
        "required_receipt_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=absence,
        )

    assert "required_receipt_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_intake_semantics(envelope, receipt_schema) == (
        "intakes[0].absence_witness_ref.required_receipt_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_receipt_intake_rejects_raw_private_fields_and_secret_values() -> None:
    raw_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    secret_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_absence()
    raw_absence["absences"][0]["raw_decision_receipt"] = "private operator decision receipt"
    secret_absence["absences"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=raw_absence,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_intake_envelope(
            generated_at="2026-06-14T00:12:00+00:00",
            operator_reapproval_decision_receipt_absence=secret_absence,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision receipt" not in str(raw_exc.value)
