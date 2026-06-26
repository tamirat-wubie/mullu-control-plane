"""Tests for personal-assistant operator reapproval decision intake runtime.

Purpose: prove operator reapproval gate evidence can produce no-effect future
decision intake refs before execution-worker admission.
Governance scope: reapproval gate refs, future decision intake refs, receipt
alignment, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval decision
intake builders and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the decision intake schema.
  - Fresh operator decisions and identity refs are not claimed.
  - Dispatch and execution-worker admission remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_intake,
    build_default_personal_assistant_operator_reapproval_gate,
    build_personal_assistant_operator_reapproval_decision_intake_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_intake import (
    _validate_operator_reapproval_decision_intake_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
INTAKE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_intake.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_intake_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_intake()
    intake_schema = _load_schema(INTAKE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    intake = envelope["intakes"][0]

    assert _validate_schema_instance(intake_schema, envelope) == []
    assert _validate_operator_reapproval_decision_intake_semantics(envelope, receipt_schema) == ()
    assert envelope["intake_count"] == 1
    assert envelope["source_projection"] == "operator_reapproval_gate"
    assert envelope["effect_boundary"]["operator_reapproval_decision_intake_allowed"] is True
    assert envelope["effect_boundary"]["fresh_operator_decision_required"] is True
    assert envelope["effect_boundary"]["fresh_operator_decision_present"] is False
    assert envelope["effect_boundary"]["operator_identity_ref_present"] is False
    assert envelope["effect_boundary"]["operator_reapproval_receipt_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert intake["operator_reapproval_gate_ref"]["wait_state"] == "awaiting_operator_reapproval"
    assert intake["operator_reapproval_gate_ref"]["fresh_operator_decision_present"] is False
    assert intake["decision_intake_request"]["decision_value_present"] is False
    assert intake["decision_intake_request"]["decision_receipt_required"] is True
    assert intake["decision_intake_request"]["decision_receipt_present"] is False
    assert intake["execution_admission_block"]["execution_worker_admission_state"] == (
        "blocked_pending_operator_reapproval_decision"
    )
    assert intake["execution_admission_block"]["execution_worker_admission_allowed"] is False
    assert intake["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_decision_intake_rejects_empty_source_gates() -> None:
    gate = build_default_personal_assistant_operator_reapproval_gate()
    gate["gates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=gate,
        )

    assert "requires at least one gate" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_intake_rejects_source_effect_boundary_drift() -> None:
    gate = copy.deepcopy(build_default_personal_assistant_operator_reapproval_gate())
    gate["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=gate,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_intake_rejects_claimed_decision_in_source() -> None:
    gate = build_default_personal_assistant_operator_reapproval_gate()
    gate["gates"][0]["reapproval_request"]["fresh_operator_decision_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=gate,
        )

    assert "reapproval_request.fresh_operator_decision_present must be false" in str(exc_info.value)
    assert gate["gates"][0]["gate_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_intake_rejects_non_waiting_gate() -> None:
    gate = build_default_personal_assistant_operator_reapproval_gate()
    gate["gates"][0]["wait_state"]["state"] = "operator_reapproval_bound"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=gate,
        )

    assert "wait_state.state must await operator reapproval" in str(exc_info.value)
    assert gate["gates"][0]["gate_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_decision_intake_rejects_cross_approval_refs() -> None:
    request_drift_gate = build_default_personal_assistant_operator_reapproval_gate()
    wait_drift_gate = build_default_personal_assistant_operator_reapproval_gate()
    envelope = build_default_personal_assistant_operator_reapproval_decision_intake()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    request_drift_gate["gates"][0]["reapproval_request"][
        "reapproval_request_ref"
    ] = "approval://personal-assistant/reapproval-request/pa_approval_other"
    wait_drift_gate["gates"][0]["wait_state"][
        "wait_state_id"
    ] = "wait://personal-assistant/operator-reapproval/pa_approval_other"
    envelope["intakes"][0]["operator_reapproval_gate_ref"][
        "reapproval_request_ref"
    ] = "approval://personal-assistant/reapproval-request/pa_approval_other"

    with pytest.raises(PersonalAssistantInvariantError) as request_exc:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=request_drift_gate,
        )
    with pytest.raises(PersonalAssistantInvariantError) as wait_exc:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=wait_drift_gate,
        )

    assert "reapproval_request_ref must match approval_id" in str(request_exc.value)
    assert "wait_state_id must match approval_id" in str(wait_exc.value)
    assert _validate_operator_reapproval_decision_intake_semantics(envelope, receipt_schema) == (
        "intakes[0].operator_reapproval_gate_ref.reapproval_request_ref must match approval_id",
    )


def test_runtime_operator_reapproval_decision_intake_rejects_raw_private_fields_and_secret_values() -> None:
    raw_gate = build_default_personal_assistant_operator_reapproval_gate()
    secret_gate = build_default_personal_assistant_operator_reapproval_gate()
    raw_gate["gates"][0]["raw_operator_decision"] = "private operator decision"
    secret_gate["gates"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=raw_gate,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_intake_envelope(
            generated_at="2026-06-14T00:09:00+00:00",
            operator_reapproval_gate=secret_gate,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision" not in str(raw_exc.value)
