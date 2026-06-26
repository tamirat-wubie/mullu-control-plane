"""Tests for personal-assistant operator reapproval decision receipt value absence.

Purpose: prove missing operator reapproval decision receipt values are recorded
as blocked no-effect evidence.
Governance scope: value-request refs, receipt value absence, blocked execution,
private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt value-absence builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-absence schema.
  - Missing operator decision values do not admit execution workers.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_request,
    build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_absence import (
    _validate_operator_reapproval_decision_receipt_value_absence_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_ABSENCE_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_absence.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_absence_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    value_absence_schema = _load_schema(VALUE_ABSENCE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    absence = envelope["absences"][0]

    assert _validate_schema_instance(value_absence_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_value_absence_semantics(envelope, receipt_schema) == ()
    assert envelope["absence_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_request"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_absence_witness_allowed"] is True
    assert envelope["effect_boundary"]["decision_receipt_value_required"] is True
    assert envelope["effect_boundary"]["decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_identity_ref_present"] is False
    assert envelope["effect_boundary"]["operator_signature_ref_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert absence["value_request_ref"]["operator_decision_value_required"] is True
    assert absence["value_request_ref"]["operator_decision_value_present"] is False
    assert absence["value_request_ref"]["operator_signature_ref_present"] is False
    assert absence["absence_witness"]["absence_reason"] == "operator_reapproval_decision_receipt_value_absent"
    assert absence["absence_witness"]["decision_receipt_present"] is False
    assert absence["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_missing_operator_reapproval_decision_receipt_value"
    )
    assert absence["execution_admission_block"]["dispatch_allowed"] is False
    assert absence["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_absence_rejects_empty_source_value_requests() -> None:
    value_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    value_request["value_requests"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=value_request,
        )

    assert "requires at least one value request" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_absence_rejects_source_effect_boundary_drift() -> None:
    value_request = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_request())
    value_request["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=value_request,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_absence_rejects_claimed_decision_value_in_source() -> None:
    value_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    value_request["value_requests"][0]["decision_value_request"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=value_request,
        )

    assert "decision_value_request.operator_decision_value_present must be false" in str(exc_info.value)
    assert value_request["value_requests"][0]["value_request_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_absence_rejects_cross_approval_refs() -> None:
    value_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    value_request["value_requests"][0]["decision_value_request"][
        "value_request_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision-value-request/pa_approval_other"
    envelope["absences"][0]["value_request_ref"][
        "value_request_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision-value-request/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=value_request,
        )

    assert "value_request_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_value_absence_semantics(envelope, receipt_schema) == (
        "absences[0].value_request_ref.value_request_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_receipt_value_absence_rejects_raw_private_fields_and_secret_values() -> None:
    raw_value_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    secret_value_request = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    raw_value_request["value_requests"][0]["raw_decision_receipt"] = "private operator decision receipt"
    secret_value_request["value_requests"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=raw_value_request,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_absence_envelope(
            generated_at="2026-06-14T00:14:00+00:00",
            operator_reapproval_decision_receipt_value_request=secret_value_request,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision receipt" not in str(raw_exc.value)
