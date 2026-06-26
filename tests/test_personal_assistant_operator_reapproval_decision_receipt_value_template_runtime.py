"""Tests for personal-assistant operator reapproval decision receipt value template.

Purpose: prove submitted-value templates are recorded as blocked no-effect
evidence and cannot grant authority.
Governance scope: value-absence refs, template-only value fields, blocked
execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt value-template builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-template schema.
  - Templates are not accepted as operator decision values.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_template,
    build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_template import (
    _validate_operator_reapproval_decision_receipt_value_template_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_TEMPLATE_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_template.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_template_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    value_template_schema = _load_schema(VALUE_TEMPLATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    template = envelope["templates"][0]

    assert _validate_schema_instance(value_template_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_value_template_semantics(envelope, receipt_schema) == ()
    assert envelope["template_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_value_absence"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_template_witness_allowed"] is True
    assert envelope["effect_boundary"]["operator_submitted_value_required"] is True
    assert envelope["effect_boundary"]["operator_value_collected"] is False
    assert envelope["effect_boundary"]["template_accepted_as_value"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert template["value_absence_ref"]["absence_reason"] == "operator_reapproval_decision_receipt_value_absent"
    assert template["template_controls"]["template_only"] is True
    assert template["template_controls"]["accepts_template_as_value"] is False
    assert [item["decision_value"] for item in template["decision_value_templates"]] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert all(item["accepted_as_operator_value"] is False for item in template["decision_value_templates"])
    assert template["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_template_only_operator_reapproval_decision_receipt_value"
    )
    assert template["execution_admission_block"]["dispatch_allowed"] is False
    assert template["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_template_rejects_empty_source_absences() -> None:
    value_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    value_absence["absences"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
            generated_at="2026-06-14T00:15:00+00:00",
            operator_reapproval_decision_receipt_value_absence=value_absence,
        )

    assert "requires at least one absence" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_template_rejects_source_effect_boundary_drift() -> None:
    value_absence = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence())
    value_absence["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
            generated_at="2026-06-14T00:15:00+00:00",
            operator_reapproval_decision_receipt_value_absence=value_absence,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_template_rejects_claimed_decision_value_in_source() -> None:
    value_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    value_absence["absences"][0]["value_request_ref"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
            generated_at="2026-06-14T00:15:00+00:00",
            operator_reapproval_decision_receipt_value_absence=value_absence,
        )

    assert "value_request_ref.operator_decision_value_present must be false" in str(exc_info.value)
    assert value_absence["absences"][0]["absence_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_template_rejects_cross_approval_refs() -> None:
    value_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    value_absence["absences"][0]["value_request_ref"][
        "value_request_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision-value-request/pa_approval_other"
    envelope["templates"][0]["value_absence_ref"]["absence_reason"] = "wrong_absence"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
            generated_at="2026-06-14T00:15:00+00:00",
            operator_reapproval_decision_receipt_value_absence=value_absence,
        )

    assert "value_request_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_value_template_semantics(envelope, receipt_schema) == (
        "templates[0].value_absence_ref.absence_reason must record value absence",
    )


def test_runtime_operator_reapproval_decision_receipt_value_template_rejects_secret_values() -> None:
    secret_value_absence = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence()
    secret_value_absence["absences"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_template_envelope(
            generated_at="2026-06-14T00:15:00+00:00",
            operator_reapproval_decision_receipt_value_absence=secret_value_absence,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
