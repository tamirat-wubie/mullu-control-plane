"""Tests for personal-assistant replay/rollback witness runtime envelopes.

Purpose: prove worker/replay preflight evidence can produce no-effect replay,
rollback, and idempotency witness evidence before execution-worker admission.
Governance scope: replay refs, rollback refs, idempotency refs, receipt
alignment, private payload redaction, and Foundation Mode boundaries.
Dependencies: mcoi_runtime.personal_assistant replay/rollback witness builders
and schema validation helpers.
Invariants:
  - Runtime envelope output validates against the replay/rollback schema.
  - Replay and rollback plans are recorded as refs and digests only.
  - Worker binding, dispatch, replay execution, connector mutation, sends,
    memory writes, and system writes stay false.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_replay_rollback_witness,
    build_default_personal_assistant_worker_replay_preflight,
    build_personal_assistant_replay_rollback_witness_envelope,
)
from scripts.validate_personal_assistant_replay_rollback_witness import (
    _validate_replay_rollback_witness_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
WITNESS_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_replay_rollback_witness.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_replay_rollback_witness_validates_against_schema_and_semantics() -> None:
    envelope = build_default_personal_assistant_replay_rollback_witness()
    witness_schema = _load_schema(WITNESS_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    witness = envelope["witnesses"][0]

    assert _validate_schema_instance(witness_schema, envelope) == []
    assert _validate_replay_rollback_witness_semantics(envelope, receipt_schema) == ()
    assert envelope["witness_count"] == 1
    assert envelope["source_projection"] == "worker_replay_preflight"
    assert envelope["effect_boundary"]["replay_rollback_witness_allowed"] is True
    assert envelope["effect_boundary"]["replay_plan_binding_allowed"] is True
    assert envelope["effect_boundary"]["rollback_plan_binding_allowed"] is True
    assert envelope["effect_boundary"]["idempotency_ref_binding_allowed"] is True
    assert envelope["effect_boundary"]["worker_binding_allowed"] is False
    assert envelope["effect_boundary"]["dispatch_lease_binding_allowed"] is False
    assert envelope["effect_boundary"]["replay_execution_allowed"] is False
    assert envelope["effect_boundary"]["rollback_execution_allowed"] is False
    assert envelope["effect_boundary"]["execution_allowed"] is False
    assert witness["worker_replay_preflight_ref"]["preflight_receipt_state"] == "deferred"
    assert witness["replay_plan_witness"]["replay_plan_state"] == "recorded_validated"
    assert witness["replay_plan_witness"]["replay_plan_validated"] is True
    assert witness["replay_plan_witness"]["replay_payload_projection"] == "digest_only"
    assert witness["replay_plan_witness"]["replay_execution_allowed"] is False
    assert witness["rollback_plan_witness"]["rollback_plan_state"] == "recorded_validated"
    assert witness["rollback_plan_witness"]["rollback_plan_validated"] is True
    assert witness["rollback_plan_witness"]["rollback_execution_allowed"] is False
    assert witness["idempotency_witness"]["idempotency_key_present"] is True
    assert witness["idempotency_witness"]["idempotency_key_serialized"] is False
    assert witness["dispatch_blockers"]["execution_worker_bound"] is False
    assert witness["dispatch_blockers"]["dispatch_lease_present"] is False
    assert witness["dispatch_blockers"]["operator_reapproval_required"] is True
    assert witness["receipt"]["decision"] == "deferred"


def test_runtime_replay_rollback_witness_rejects_empty_preflights() -> None:
    preflight = build_default_personal_assistant_worker_replay_preflight()
    preflight["preflights"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=preflight,
        )

    assert "requires at least one worker/replay preflight" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_replay_rollback_witness_rejects_preflight_receipt_drift() -> None:
    preflight = build_default_personal_assistant_worker_replay_preflight()
    preflight["preflights"][0]["receipt"]["decision"] = "allowed"

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=preflight,
        )

    assert "preflight receipt must be deferred" in str(exc_info.value)
    assert preflight["preflights"][0]["preflight_id"] in str(exc_info.value)


def test_runtime_replay_rollback_witness_rejects_source_effect_boundary_drift() -> None:
    preflight = copy.deepcopy(build_default_personal_assistant_worker_replay_preflight())
    preflight["effect_boundary"]["worker_binding_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=preflight,
        )

    assert "effect_boundary.worker_binding_allowed must be false" in str(exc_info.value)
    assert "bind worker" not in str(exc_info.value).lower()


def test_runtime_replay_rollback_witness_rejects_replay_preflight_drift() -> None:
    preflight = build_default_personal_assistant_worker_replay_preflight()
    preflight["preflights"][0]["replay_preflight"]["replay_plan_validated"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=preflight,
        )

    assert "replay_preflight.replay_plan_validated must be false" in str(exc_info.value)
    assert preflight["preflights"][0]["preflight_id"] in str(exc_info.value)


def test_runtime_replay_rollback_witness_rejects_raw_private_fields_and_secret_values() -> None:
    raw_preflight = build_default_personal_assistant_worker_replay_preflight()
    secret_preflight = build_default_personal_assistant_worker_replay_preflight()
    raw_preflight["preflights"][0]["raw_replay_plan"] = "private replay instructions"
    secret_preflight["preflights"][0]["receipt"]["actions_taken"].append("rotate Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=raw_preflight,
        )
    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_replay_rollback_witness_envelope(
            generated_at="2026-06-14T00:06:00+00:00",
            worker_replay_preflight=secret_preflight,
        )

    assert "raw private or secret field is forbidden" in str(raw_exc.value)
    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "private replay instructions" not in str(raw_exc.value)
