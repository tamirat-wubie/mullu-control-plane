"""Tests for personal-assistant operator value-binding admission preflight.

Purpose: prove admission preflight is blocked when governed operator value
binding is absent.
Governance scope: value-binding absence refs, admission denial, blocked
execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant value-binding admission preflight
builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the admission preflight schema.
  - Missing value binding produces GovernanceBlocked admission.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight import (
    _validate_value_binding_admission_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_ADMISSION_PREFLIGHT_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_validates_as_blocked() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight()
    schema = _load_schema(VALUE_BINDING_ADMISSION_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    preflight = envelope["admission_preflights"][0]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_value_binding_admission_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["admission_preflight_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_binding_absence"
    assert envelope["assurance"]["outcome"] == "GovernanceBlocked"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_admission_preflight_allowed"] is True
    assert envelope["effect_boundary"]["admission_decision_allowed"] is True
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["admission_approved"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert preflight["value_binding_absence_ref"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert preflight["value_binding_absence_ref"]["operator_value_bound"] is False
    assert preflight["admission_decision"]["decision"] == "blocked"
    assert preflight["admission_decision"]["outcome"] == "GovernanceBlocked"
    assert preflight["admission_decision"]["authority_granted"] is False
    assert preflight["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_missing_governed_operator_value_binding"
    )
    assert preflight["execution_admission_block"]["dispatch_allowed"] is False
    assert preflight["receipt"]["decision"] == "blocked"


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_rejects_empty_absence_source() -> None:
    value_binding_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence()
    value_binding_absence["binding_absences"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope(
            generated_at="2026-06-14T00:18:00+00:00",
            operator_reapproval_decision_receipt_value_binding_absence=value_binding_absence,
        )

    assert "requires at least one binding absence" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_rejects_source_boundary_drift() -> None:
    value_binding_absence = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence())
    value_binding_absence["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope(
            generated_at="2026-06-14T00:18:00+00:00",
            operator_reapproval_decision_receipt_value_binding_absence=value_binding_absence,
        )

    assert "value binding absence effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_rejects_claimed_bound_value() -> None:
    value_binding_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence()
    value_binding_absence["binding_absences"][0]["value_binding_guard_ref"]["operator_value_bound"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope(
            generated_at="2026-06-14T00:18:00+00:00",
            operator_reapproval_decision_receipt_value_binding_absence=value_binding_absence,
        )

    assert "value_binding_guard_ref.operator_value_bound must be false" in str(exc_info.value)
    assert value_binding_absence["binding_absences"][0]["binding_absence_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_rejects_mutated_decision_values() -> None:
    value_binding_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence()
    value_binding_absence["binding_absences"][0]["value_binding_guard_ref"]["allowed_decision_values"][0] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope(
            generated_at="2026-06-14T00:18:00+00:00",
            operator_reapproval_decision_receipt_value_binding_absence=value_binding_absence,
        )

    assert "allowed_decision_values must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_admission_preflight_rejects_secret_values() -> None:
    value_binding_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_absence()
    value_binding_absence["binding_absences"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight_envelope(
            generated_at="2026-06-14T00:18:00+00:00",
            operator_reapproval_decision_receipt_value_binding_absence=value_binding_absence,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
