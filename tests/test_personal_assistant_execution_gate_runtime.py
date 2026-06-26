"""Tests for personal-assistant execution-gate runtime envelopes.

Purpose: prove approved approval decisions can produce a no-effect dispatch
preflight envelope without executing personal-assistant actions.
Governance scope: execution gate evidence, approval-decision binding, receipt
alignment, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant execution gate builders and
schema validation helpers.
Invariants:
  - Runtime envelope output validates against the execution-gate schema.
  - Approved decisions are required but remain non-executing.
  - Connector execution, sends, mutation, memory writes, and system writes stay
    false before dispatch.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_approval_decision_evidence,
    build_default_personal_assistant_execution_gate,
    build_personal_assistant_execution_gate_envelope,
)
from scripts.validate_personal_assistant_execution_gate import _validate_execution_gate_semantics
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
GATE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_execution_gate.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_execution_gate_envelope_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_execution_gate()
    gate_schema = _load_schema(GATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    gate = envelope["gates"][0]

    assert _validate_schema_instance(gate_schema, envelope) == []
    assert _validate_execution_gate_semantics(envelope, receipt_schema) == ()
    assert envelope["gate_count"] == 1
    assert envelope["source_projection"] == "approval_decision_evidence"
    assert envelope["effect_boundary"]["execution_gate_evaluation_allowed"] is True
    assert envelope["effect_boundary"]["execution_allowed"] is False
    assert envelope["effect_boundary"]["external_send_allowed"] is False
    assert envelope["effect_boundary"]["connector_mutation_allowed"] is False
    assert gate["approval_decision_ref"]["decision"] == "approved"
    assert gate["approval_decision_ref"]["decision_receipt_state"] == "deferred"
    assert gate["dispatch_preconditions"]["live_connector_witness_present"] is False
    assert gate["dispatch_preconditions"]["execution_worker_bound"] is False
    assert gate["dispatch_preconditions"]["operator_reapproval_required"] is True
    assert gate["receipt"]["decision"] == "deferred"


def test_runtime_execution_gate_rejects_no_approved_decision() -> None:
    evidence = build_default_personal_assistant_approval_decision_evidence()
    evidence["decisions"] = [item for item in evidence["decisions"] if item["decision"] != "approved"]

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_execution_gate_envelope(
            generated_at="2026-06-14T00:04:00+00:00",
            approval_decision_evidence=evidence,
        )

    assert "requires at least one approved decision" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_execution_gate_rejects_decision_receipt_drift() -> None:
    evidence = build_default_personal_assistant_approval_decision_evidence()
    approved = next(item for item in evidence["decisions"] if item["decision"] == "approved")
    approved["receipt"]["decision"] = "allowed"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_execution_gate_envelope(
            generated_at="2026-06-14T00:04:00+00:00",
            approval_decision_evidence=evidence,
        )

    assert "decision receipt must be deferred" in str(exc_info.value)
    assert approved["decision_id"] in str(exc_info.value)


def test_runtime_execution_gate_rejects_raw_private_fields_and_secret_values() -> None:
    raw_evidence = build_default_personal_assistant_approval_decision_evidence()
    secret_evidence = build_default_personal_assistant_approval_decision_evidence()
    raw_approved = next(item for item in raw_evidence["decisions"] if item["decision"] == "approved")
    secret_approved = next(item for item in secret_evidence["decisions"] if item["decision"] == "approved")
    raw_approved["packet"]["raw_message"] = "private mailbox body"
    secret_approved["packet"]["proposed_actions"][0]["summary"] = "rotate Bearer secret-worker-token"

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_execution_gate_envelope(
            generated_at="2026-06-14T00:04:00+00:00",
            approval_decision_evidence=raw_evidence,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_execution_gate_envelope(
            generated_at="2026-06-14T00:04:00+00:00",
            approval_decision_evidence=secret_evidence,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private mailbox body" not in str(raw_exc.value)


def test_runtime_execution_gate_rejects_source_effect_boundary_drift() -> None:
    evidence = copy.deepcopy(build_default_personal_assistant_approval_decision_evidence())
    evidence["effect_boundary"]["external_send_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_execution_gate_envelope(
            generated_at="2026-06-14T00:04:00+00:00",
            approval_decision_evidence=evidence,
        )

    assert "effect_boundary.external_send_allowed must be false" in str(exc_info.value)
