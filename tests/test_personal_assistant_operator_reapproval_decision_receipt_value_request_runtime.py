"""Tests for personal-assistant operator reapproval decision receipt value request.

Purpose: prove future operator reapproval decision receipt value requests are
recorded as blocked no-effect evidence.
Governance scope: receipt-intake refs, decision value requirements, blocked
execution, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
receipt value-request builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the value-request schema.
  - Missing operator decision values do not admit execution workers.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_intake,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_request,
    build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_request import (
    _validate_operator_reapproval_decision_receipt_value_request_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REQUEST_SCHEMA_PATH = (
    ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_request.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_request_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    value_request_schema = _load_schema(VALUE_REQUEST_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    value_request = envelope["value_requests"][0]

    assert _validate_schema_instance(value_request_schema, envelope) == []
    assert _validate_operator_reapproval_decision_receipt_value_request_semantics(envelope, receipt_schema) == ()
    assert envelope["value_request_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_decision_receipt_intake"
    assert envelope["effect_boundary"]["operator_reapproval_decision_receipt_value_request_allowed"] is True
    assert envelope["effect_boundary"]["decision_receipt_value_required"] is True
    assert envelope["effect_boundary"]["decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_identity_ref_present"] is False
    assert envelope["effect_boundary"]["operator_signature_ref_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert value_request["receipt_intake_ref"]["decision_receipt_required"] is True
    assert value_request["receipt_intake_ref"]["decision_receipt_present"] is False
    assert value_request["decision_value_request"]["accepted_decision_values"] == [
        "approved",
        "rejected",
        "revised",
        "expired",
    ]
    assert value_request["decision_value_request"]["operator_decision_value_required"] is True
    assert value_request["decision_value_request"]["operator_decision_value_present"] is False
    assert value_request["decision_value_request"]["operator_signature_ref_present"] is False
    assert value_request["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_operator_reapproval_decision_receipt_value"
    )
    assert value_request["execution_admission_block"]["dispatch_allowed"] is False
    assert value_request["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_receipt_value_request_rejects_empty_source_intakes() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    intake["intakes"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=intake,
        )

    assert "requires at least one intake" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_request_rejects_source_effect_boundary_drift() -> None:
    intake = copy.deepcopy(build_default_personal_assistant_operator_reapproval_decision_receipt_intake())
    intake["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=intake,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_request_rejects_claimed_decision_value_in_source() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    intake["intakes"][0]["receipt_intake_request"]["operator_decision_value_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=intake,
        )

    assert "receipt_intake_request.operator_decision_value_present must be false" in str(exc_info.value)
    assert intake["intakes"][0]["intake_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_request_rejects_cross_approval_refs() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_request()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    intake["intakes"][0]["receipt_intake_request"][
        "receipt_intake_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision-intake/pa_approval_other"
    envelope["value_requests"][0]["receipt_intake_ref"][
        "receipt_intake_ref"
    ] = "receipt://personal-assistant/operator-reapproval-decision-intake/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=intake,
        )

    assert "receipt_intake_ref must match approval_id" in str(exc_info.value)
    assert _validate_operator_reapproval_decision_receipt_value_request_semantics(envelope, receipt_schema) == (
        "value_requests[0].receipt_intake_ref.receipt_intake_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_receipt_value_request_rejects_raw_private_fields_and_secret_values() -> None:
    raw_intake = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    secret_intake = build_default_personal_assistant_operator_reapproval_decision_receipt_intake()
    raw_intake["intakes"][0]["raw_decision_receipt"] = "private operator decision receipt"
    secret_intake["intakes"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=raw_intake,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_request_envelope(
            generated_at="2026-06-14T00:13:00+00:00",
            operator_reapproval_decision_receipt_intake=secret_intake,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision receipt" not in str(raw_exc.value)
