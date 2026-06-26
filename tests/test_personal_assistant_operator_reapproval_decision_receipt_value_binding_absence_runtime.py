"""Tests for personal-assistant operator decision value binding absence.

Purpose: prove binding absence witnesses are recorded as blocked no-effect
evidence and cannot bind operator values or grant authority.
Governance scope: value-binding guard refs, missing bound operator values,
blocked execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt value-binding absence builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-binding absence schema.
  - Binding absence witnesses are not accepted as operator decision values.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence import (
    _validate_operator_reapproval_decision_receipt_value_binding_absence_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_ABSENCE_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_absence.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence()
    value_binding_absence_schema = _load_schema(VALUE_BINDING_ABSENCE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    binding_absence = envelope["binding_absences"][0]

    assert _validate_schema_instance(value_binding_absence_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_value_binding_absence_semantics(envelope, receipt_schema) == ()
    assert envelope["binding_absence_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_guard"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_absence_witness_allowed"] is True
    assert envelope["effect_boundary"]["value_binding_guard_ref_binding_allowed"] is True
    assert envelope["effect_boundary"]["operator_submitted_value_required"] is True
    assert envelope["effect_boundary"]["operator_value_collected"] is False
    assert envelope["effect_boundary"]["explicit_operator_value_present"] is False
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["accepted_value_present"] is False
    assert envelope["effect_boundary"]["binding_absence_accepted_as_value"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert binding_absence["value_binding_guard_ref"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert binding_absence["value_binding_guard_ref"]["operator_value_bound"] is False
    assert binding_absence["binding_absence_witness"]["absence_reason"] == (
        "operator_reapproval_decision_receipt_value_binding_absent"
    )
    assert binding_absence["binding_absence_witness"]["operator_value_bound"] is False
    assert binding_absence["binding_absence_witness"]["authority_granted"] is False
    assert binding_absence["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_governed_operator_value_binding"
    )
    assert binding_absence["execution_admission_block"]["dispatch_allowed"] is False
    assert binding_absence["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_rejects_empty_source_guards() -> None:
    value_binding_guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard()
    value_binding_guard["binding_guards"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope(
            generated_at="2026-06-14T00:17:00+00:00",
            operator_reapproval_decision_receipt_value_binding_guard=value_binding_guard,
        )

    assert "requires at least one binding guard" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_rejects_source_effect_boundary_drift() -> None:
    value_binding_guard = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard())
    value_binding_guard["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope(
            generated_at="2026-06-14T00:17:00+00:00",
            operator_reapproval_decision_receipt_value_binding_guard=value_binding_guard,
        )

    assert "value binding guard effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_rejects_claimed_bound_value_in_source() -> None:
    value_binding_guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard()
    value_binding_guard["binding_guards"][0]["admissible_value_binding"]["accepted_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope(
            generated_at="2026-06-14T00:17:00+00:00",
            operator_reapproval_decision_receipt_value_binding_guard=value_binding_guard,
        )

    assert "admissible_value_binding.accepted_value_present must be false" in str(exc_info.value)
    assert value_binding_guard["binding_guards"][0]["binding_guard_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_rejects_mutated_decision_values() -> None:
    value_binding_guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard()
    value_binding_guard["binding_guards"][0]["admissible_value_binding"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope(
            generated_at="2026-06-14T00:17:00+00:00",
            operator_reapproval_decision_receipt_value_binding_guard=value_binding_guard,
        )

    assert "allowed_decision_values must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_absence_rejects_secret_values() -> None:
    secret_value_binding_guard = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard()
    secret_value_binding_guard["binding_guards"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence_envelope(
            generated_at="2026-06-14T00:17:00+00:00",
            operator_reapproval_decision_receipt_value_binding_guard=secret_value_binding_guard,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
