"""Tests for personal-assistant operator decision receipt value binding guards.

Purpose: prove binding guards are recorded as blocked no-effect evidence and
cannot bind operator values or grant authority.
Governance scope: value-template refs, future value-binding requirements,
blocked execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt value-binding guard builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-binding guard schema.
  - Guards are not accepted as operator decision values.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_template,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard import (
    _validate_operator_reapproval_decision_receipt_value_binding_guard_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_BINDING_GUARD_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_guard.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard()
    value_binding_guard_schema = _load_schema(VALUE_BINDING_GUARD_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    guard = envelope["binding_guards"][0]

    assert _validate_schema_instance(value_binding_guard_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_value_binding_guard_semantics(envelope, receipt_schema) == ()
    assert envelope["binding_guard_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_template"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_binding_guard_allowed"] is True
    assert envelope["effect_boundary"]["operator_submitted_value_required"] is True
    assert envelope["effect_boundary"]["operator_value_collected"] is False
    assert envelope["effect_boundary"]["operator_value_bound"] is False
    assert envelope["effect_boundary"]["binding_guard_accepted_as_value"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert guard["value_template_ref"]["operator_value_bound"] is False
    assert guard["admissible_value_binding"]["allowed_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert guard["admissible_value_binding"]["accepted_value_present"] is False
    assert guard["admissible_value_binding"]["grants_execution_authority"] is False
    assert guard["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_governed_operator_value_binding"
    )
    assert guard["execution_admission_block"]["dispatch_allowed"] is False
    assert guard["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_rejects_empty_source_templates() -> None:
    value_template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    value_template["templates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
            generated_at="2026-06-14T00:16:00+00:00",
            operator_reapproval_decision_receipt_value_template=value_template,
        )

    assert "requires at least one template" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_rejects_source_effect_boundary_drift() -> None:
    value_template = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_template())
    value_template["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
            generated_at="2026-06-14T00:16:00+00:00",
            operator_reapproval_decision_receipt_value_template=value_template,
        )

    assert "value template effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_rejects_claimed_bound_value_in_source() -> None:
    value_template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    value_template["templates"][0]["decision_value_templates"][0]["accepted_as_operator_value"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
            generated_at="2026-06-14T00:16:00+00:00",
            operator_reapproval_decision_receipt_value_template=value_template,
        )

    assert "decision_value_templates[0].accepted_as_operator_value must be false" in str(exc_info.value)
    assert value_template["templates"][0]["template_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_rejects_mutated_decision_values() -> None:
    value_template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    value_template["templates"][0]["decision_value_templates"][0]["decision_value"] = "send_now"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
            generated_at="2026-06-14T00:16:00+00:00",
            operator_reapproval_decision_receipt_value_template=value_template,
        )

    assert "decision_value_templates must preserve allowed decision values" in str(exc_info.value)
    assert "send_now" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_guard_rejects_secret_values() -> None:
    secret_value_template = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    secret_value_template["templates"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard_envelope(
            generated_at="2026-06-14T00:16:00+00:00",
            operator_reapproval_decision_receipt_value_template=secret_value_template,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
