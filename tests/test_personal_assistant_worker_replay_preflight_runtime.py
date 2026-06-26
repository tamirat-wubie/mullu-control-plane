"""Tests for personal-assistant worker/replay preflight runtime envelopes.

Purpose: prove execution gate evidence can produce a no-effect worker/replay
preflight envelope without binding workers or executing replay.
Governance scope: execution-worker controls, replay prerequisites, receipt
alignment, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant worker/replay preflight builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the worker/replay schema.
  - Execution gates remain necessary but not sufficient for live dispatch.
  - Worker binding, replay execution, connector mutation, sends, memory writes,
    and system writes stay false.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_execution_gate,
    build_default_personal_assistant_worker_replay_preflight,
    build_personal_assistant_worker_replay_preflight_envelope,
)
from scripts.validate_personal_assistant_worker_replay_preflight import (
    _validate_worker_replay_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_worker_replay_preflight.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_worker_replay_preflight_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_worker_replay_preflight()
    preflight_schema = _load_schema(PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    preflight = envelope["preflights"][0]

    assert _validate_schema_instance(preflight_schema, envelope) == []
    assert _validate_worker_replay_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["preflight_count"] == 1
    assert envelope["source_projection"] == "execution_gate_evidence"
    assert envelope["effect_boundary"]["worker_replay_preflight_allowed"] is True
    assert envelope["effect_boundary"]["worker_binding_allowed"] is False
    assert envelope["effect_boundary"]["replay_execution_allowed"] is False
    assert envelope["effect_boundary"]["execution_allowed"] is False
    assert envelope["effect_boundary"]["external_send_allowed"] is False
    assert envelope["effect_boundary"]["connector_mutation_allowed"] is False
    assert preflight["execution_gate_ref"]["gate_receipt_state"] == "deferred"
    assert preflight["execution_gate_ref"]["payload_digest_only"] is True
    assert preflight["worker_preflight"]["worker_binding_allowed"] is False
    assert preflight["worker_preflight"]["execution_worker_bound"] is False
    assert preflight["worker_preflight"]["live_connector_witness_present"] is False
    assert preflight["worker_preflight"]["dispatch_lease_present"] is False
    assert preflight["worker_preflight"]["operator_reapproval_required"] is True
    assert preflight["replay_preflight"]["replay_plan_state"] == "required_not_recorded"
    assert preflight["replay_preflight"]["replay_plan_validated"] is False
    assert preflight["replay_preflight"]["rollback_plan_required"] is True
    assert preflight["replay_preflight"]["idempotency_key_present"] is False
    assert preflight["replay_preflight"]["replay_execution_allowed"] is False
    assert preflight["receipt"]["decision"] == "deferred"


def test_runtime_worker_replay_preflight_rejects_empty_execution_gates() -> None:
    gate_evidence = build_default_personal_assistant_execution_gate()
    gate_evidence["gates"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_worker_replay_preflight_envelope(
            generated_at="2026-06-14T00:05:00+00:00",
            execution_gate_evidence=gate_evidence,
        )

    assert "requires at least one execution gate" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_worker_replay_preflight_rejects_gate_receipt_drift() -> None:
    gate_evidence = build_default_personal_assistant_execution_gate()
    gate_evidence["gates"][0]["receipt"]["decision"] = "allowed"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_worker_replay_preflight_envelope(
            generated_at="2026-06-14T00:05:00+00:00",
            execution_gate_evidence=gate_evidence,
        )

    assert "gate receipt must be deferred" in str(exc_info.value)
    assert gate_evidence["gates"][0]["gate_id"] in str(exc_info.value)


def test_runtime_worker_replay_preflight_rejects_source_effect_boundary_drift() -> None:
    gate_evidence = copy.deepcopy(build_default_personal_assistant_execution_gate())
    gate_evidence["effect_boundary"]["external_send_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_worker_replay_preflight_envelope(
            generated_at="2026-06-14T00:05:00+00:00",
            execution_gate_evidence=gate_evidence,
        )

    assert "effect_boundary.external_send_allowed must be false" in str(exc_info.value)
    assert "external send" not in str(exc_info.value).lower()


def test_runtime_worker_replay_preflight_rejects_raw_private_fields_and_secret_values() -> None:
    raw_evidence = build_default_personal_assistant_execution_gate()
    secret_evidence = build_default_personal_assistant_execution_gate()
    raw_evidence["gates"][0]["raw_message"] = "private mailbox body"
    secret_evidence["gates"][0]["receipt"]["actions_taken"].append("rotate Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_worker_replay_preflight_envelope(
            generated_at="2026-06-14T00:05:00+00:00",
            execution_gate_evidence=raw_evidence,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_worker_replay_preflight_envelope(
            generated_at="2026-06-14T00:05:00+00:00",
            execution_gate_evidence=secret_evidence,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private mailbox body" not in str(raw_exc.value)
