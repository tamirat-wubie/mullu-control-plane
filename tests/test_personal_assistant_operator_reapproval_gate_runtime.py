"""Tests for personal-assistant operator reapproval gate runtime envelopes.

Purpose: prove connector/lease witness evidence can produce no-effect operator
reapproval request and wait-state refs before execution-worker admission.
Governance scope: reapproval request refs, wait-state refs, connector/lease
refs, receipt alignment, private payload redaction, and Foundation Mode
boundaries.
Dependencies: mcoi_runtime.personal_assistant operator reapproval gate builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the operator reapproval schema.
  - Fresh operator decisions are not claimed.
  - Dispatch and execution-worker admission remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_connector_lease_witness,
    build_default_personal_assistant_operator_reapproval_gate,
    build_personal_assistant_operator_reapproval_gate_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_gate import (
    _validate_operator_reapproval_gate_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
GATE_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_operator_reapproval_gate.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_gate_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_gate()
    gate_schema = _load_schema(GATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    gate = envelope["gates"][0]

    assert _validate_schema_instance(gate_schema, envelope) == []
    assert _validate_operator_reapproval_gate_semantics(envelope, receipt_schema) == ()
    assert envelope["gate_count"] == 1
    assert envelope["source_projection"] == "connector_lease_witness"
    assert envelope["effect_boundary"]["operator_reapproval_gate_allowed"] is True
    assert envelope["effect_boundary"]["operator_reapproval_request_packet_allowed"] is True
    assert envelope["effect_boundary"]["fresh_operator_decision_required"] is True
    assert envelope["effect_boundary"]["operator_reapproval_present"] is False
    assert envelope["effect_boundary"]["fresh_operator_decision_present"] is False
    assert envelope["effect_boundary"]["execution_worker_admission_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False
    assert gate["connector_lease_witness_ref"]["connector_witness_ref_bound"] is True
    assert gate["connector_lease_witness_ref"]["dispatch_lease_ref_bound"] is True
    assert gate["reapproval_request"]["fresh_operator_decision_required"] is True
    assert gate["reapproval_request"]["fresh_operator_decision_present"] is False
    assert gate["reapproval_request"]["operator_reapproval_receipt_present"] is False
    assert gate["wait_state"]["state"] == "awaiting_operator_reapproval"
    assert gate["wait_state"]["dispatch_allowed_while_waiting"] is False
    assert gate["execution_admission_block"]["execution_worker_admission_state"] == "blocked_pending_operator_reapproval"
    assert gate["execution_admission_block"]["execution_worker_admission_allowed"] is False
    assert gate["receipt"]["decision"] == "deferred"


def test_runtime_operator_reapproval_gate_rejects_empty_source_witnesses() -> None:
    connector_witness = build_default_personal_assistant_connector_lease_witness()
    connector_witness["witnesses"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=connector_witness,
        )

    assert "requires at least one connector/lease witness" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_gate_rejects_source_receipt_drift() -> None:
    connector_witness = build_default_personal_assistant_connector_lease_witness()
    connector_witness["witnesses"][0]["receipt"]["decision"] = "allowed"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=connector_witness,
        )

    assert "connector/lease receipt must be deferred" in str(exc_info.value)
    assert connector_witness["witnesses"][0]["witness_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_gate_rejects_source_effect_boundary_drift() -> None:
    connector_witness = copy.deepcopy(build_default_personal_assistant_connector_lease_witness())
    connector_witness["effect_boundary"]["execution_worker_admission_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=connector_witness,
        )

    assert "effect_boundary.execution_worker_admission_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_gate_rejects_reapproval_drift_in_source() -> None:
    connector_witness = build_default_personal_assistant_connector_lease_witness()
    connector_witness["witnesses"][0]["operator_reapproval_gate"]["operator_reapproval_present"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=connector_witness,
        )

    assert "operator_reapproval_gate.operator_reapproval_present must be false" in str(exc_info.value)
    assert connector_witness["witnesses"][0]["witness_id"] in str(exc_info.value)


def test_runtime_operator_reapproval_gate_rejects_raw_private_fields_and_secret_values() -> None:
    raw_witness = build_default_personal_assistant_connector_lease_witness()
    secret_witness = build_default_personal_assistant_connector_lease_witness()
    raw_witness["witnesses"][0]["raw_operator_decision"] = "private operator decision"
    secret_witness["witnesses"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=raw_witness,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_gate_envelope(
            generated_at="2026-06-14T00:08:00+00:00",
            connector_lease_witness=secret_witness,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private operator decision" not in str(raw_exc.value)
