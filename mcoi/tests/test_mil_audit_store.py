"""Purpose: verify MIL audit persistence, replay lookup, and trace-store projection.
Governance scope: persistence-only MIL audit tests.
Dependencies: MIL contracts, static verifier, MIL audit store, and TraceStore.
Invariants: hash-chain anchoring is required; trace spines are parent-linked; TraceStore projection is idempotent and collision-safe.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.replay import ReplayMode
from mcoi_runtime.core.mil_static_verifier import verify_mil_program
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceWriteError
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore
from mcoi_runtime.persistence.trace_store import TraceStore


def _program() -> MILProgram:
    decision = PolicyDecision(
        "policy:allow:goal-1",
        "operator",
        "goal-1",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "allow"),),
        "2026-05-06T12:00:00Z",
    )
    return MILProgram(
        "mil:goal-1:shell_command",
        "goal-1",
        decision,
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-1"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-1", depends_on=("verify",)),
        ),
        "2026-05-06T12:00:01Z",
    )


def _append(store: MILAuditStore):
    program = _program()
    return store.append(
        program=program,
        verification=verify_mil_program(program),
        execution_id="exec-1",
        instruction_trace=("check:check_policy:goal-1", "proof:emit_proof:goal-1"),
        recorded_at="2026-05-06T12:00:02Z",
    )


def test_append_round_trips_and_anchors_record(tmp_path) -> None:
    store = MILAuditStore(tmp_path / "mil-audit")

    result = _append(store)
    loaded = store.load(result.record.record_id)

    assert loaded.record_id == result.record.record_id
    assert loaded.program_id == "mil:goal-1:shell_command"
    assert store.chain.validate().valid is True
    assert store.validate_record(result.record.record_id) is True


def test_replay_lookup_requires_hash_chain_anchor(tmp_path) -> None:
    store = MILAuditStore(tmp_path / "mil-audit")
    result = _append(store)
    chain_path = tmp_path / "mil-audit" / "chain" / f"{result.chain_entry.sequence_number:012d}.json"
    chain_path.unlink()

    with pytest.raises(CorruptedDataError, match="not anchored"):
        store.replay_lookup(result.record.record_id)


def test_replay_lookup_reconstructs_parent_linked_trace_spine(tmp_path) -> None:
    store = MILAuditStore(tmp_path / "mil-audit")
    result = _append(store)

    lookup = store.replay_lookup(result.record.record_id)
    event_types = tuple(entry.event_type for entry in lookup.trace_entries)

    assert lookup.replay_record.mode is ReplayMode.OBSERVATION_ONLY
    assert lookup.replay_record.trace_id == lookup.trace_entries[-1].trace_id
    assert event_types == (
        "whqr_policy_decision",
        "policy_decision",
        "mil_program",
        "mil_static_verification",
        "dispatch_execution",
        "mil_audit_record",
    )
    assert lookup.trace_entries[0].parent_trace_id is None
    assert lookup.trace_entries[-1].parent_trace_id == lookup.trace_entries[-2].trace_id


def test_persist_trace_spine_writes_trace_store_idempotently(tmp_path) -> None:
    audit_store = MILAuditStore(tmp_path / "mil-audit")
    trace_store = TraceStore(tmp_path / "traces")
    result = _append(audit_store)

    first = audit_store.persist_trace_spine(result.record.record_id, trace_store)
    second = audit_store.persist_trace_spine(result.record.record_id, trace_store)

    assert first.persisted_trace_ids == second.persisted_trace_ids
    assert set(trace_store.list_traces()) == set(first.persisted_trace_ids)
    assert trace_store.load_trace(first.persisted_trace_ids[-1]).event_type == "mil_audit_record"


def test_persist_trace_spine_fails_closed_on_trace_collision(tmp_path) -> None:
    audit_store = MILAuditStore(tmp_path / "mil-audit")
    trace_store = TraceStore(tmp_path / "traces")
    result = _append(audit_store)
    lookup = audit_store.replay_lookup(result.record.record_id)
    collision = replace(lookup.trace_entries[0], event_type="colliding_event")
    trace_store.append(collision)

    with pytest.raises(PersistenceWriteError, match="trace id collision"):
        audit_store.persist_trace_spine(result.record.record_id, trace_store)


def test_persist_trace_spine_rejects_non_trace_store(tmp_path) -> None:
    audit_store = MILAuditStore(tmp_path / "mil-audit")
    result = _append(audit_store)

    with pytest.raises(Exception, match="trace_store"):
        audit_store.persist_trace_spine(result.record.record_id, object())  # type: ignore[arg-type]
