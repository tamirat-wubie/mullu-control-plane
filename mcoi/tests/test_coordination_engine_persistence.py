"""Purpose: verify coordination engine checkpoint/restore with governed guards.
Governance scope: coordination engine persistence integration tests only.
Dependencies: coordination engine, coordination store, coordination contracts.
Invariants: explicit save/load; expired lease rejected; policy drift triggers review;
  retry cap enforced; no store raises invariant error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
    RestoreStatus,
)
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.persistence import CoordinationStore


_T0 = "2026-03-30T00:00:00+00:00"
_T1 = "2026-03-30T00:30:00+00:00"
_T_EXPIRED = "2026-03-30T02:00:00+00:00"


def _make_clock(times: list[str]) -> callable:
    idx = [0]

    def clock() -> str:
        t = times[idx[0] % len(times)]
        idx[0] += 1
        return t

    return clock


def _populated_engine(
    tmp_path: Path,
    clock: callable | None = None,
) -> CoordinationEngine:
    store = CoordinationStore(tmp_path)
    engine = CoordinationEngine(
        clock=clock or _make_clock([_T0]),
        coordination_store=store,
        policy_pack_id="pack-v1",
    )
    engine.request_delegation(DelegationRequest(
        delegation_id="del-1",
        delegator_id="agent-a",
        delegate_id="agent-b",
        goal_id="goal-1",
        action_scope="execute_shell",
    ))
    engine.resolve_delegation(DelegationResult(
        delegation_id="del-1",
        status=DelegationStatus.ACCEPTED,
        reason="approved",
        resolved_at=_T0,
    ))
    engine.record_handoff(HandoffRecord(
        handoff_id="ho-1",
        from_party="agent-a",
        to_party="agent-b",
        goal_id="goal-1",
        context_ids=("ctx-1",),
        handed_off_at=_T0,
    ))
    engine.record_merge(MergeDecision(
        merge_id="mg-1",
        goal_id="goal-1",
        source_ids=("src-1", "src-2"),
        outcome=MergeOutcome.MERGED,
        reason="combined",
        resolved_at=_T0,
    ))
    engine.record_conflict(ConflictRecord(
        conflict_id="cf-1",
        goal_id="goal-1",
        conflicting_ids=("a", "b"),
        strategy=ConflictStrategy.ESCALATE,
        resolved=False,
    ))
    return engine


# --- Happy path round-trip ---


def test_save_restore_round_trip(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    checkpoint = engine.save_checkpoint("cp-1")
    assert checkpoint.checkpoint_id == "cp-1"
    assert len(checkpoint.delegations) == 1
    assert len(checkpoint.delegation_results) == 1
    assert len(checkpoint.handoffs) == 1
    assert len(checkpoint.merges) == 1
    assert len(checkpoint.conflicts) == 1

    # New engine from same store
    engine2 = CoordinationEngine(
        clock=_make_clock([_T1]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="pack-v1",
    )
    assert engine2.delegation_count == 0

    outcome = engine2.restore_checkpoint("cp-1", current_policy_pack_id="pack-v1")
    assert outcome.status == RestoreStatus.RESUMED
    assert engine2.delegation_count == 1
    assert engine2.handoff_count == 1
    assert engine2.merge_count == 1
    assert engine2.get_delegation("del-1") is not None
    assert engine2.get_delegation_result("del-1") is not None
    assert engine2.get_handoff("ho-1") is not None
    assert engine2.get_merge("mg-1") is not None
    assert engine2.get_conflict("cf-1") is not None


# --- Expired lease ---


def test_expired_lease_rejected(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path, clock=_make_clock([_T0]))
    engine.save_checkpoint("cp-exp", lease_duration_seconds=3600)

    engine2 = CoordinationEngine(
        clock=_make_clock([_T_EXPIRED]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="pack-v1",
    )
    outcome = engine2.restore_checkpoint("cp-exp")
    assert outcome.status == RestoreStatus.EXPIRED
    assert outcome.reason == "checkpoint lease expired"
    assert _T_EXPIRED not in outcome.reason
    assert engine2.delegation_count == 0


# --- Policy pack drift ---


def test_policy_pack_drift_needs_review(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    engine.save_checkpoint("cp-drift")

    engine2 = CoordinationEngine(
        clock=_make_clock([_T1]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="pack-v2",
    )
    outcome = engine2.restore_checkpoint("cp-drift", current_policy_pack_id="pack-v2")
    assert outcome.status == RestoreStatus.NEEDS_REVIEW
    assert outcome.reason == "checkpoint policy pack drift"
    assert "pack-v1" not in outcome.reason
    assert "pack-v2" not in outcome.reason
    assert engine2.delegation_count == 0


# --- Retry cap ---


def test_max_retries_aborts(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    engine.save_checkpoint("cp-retry")

    for _ in range(3):
        engine.increment_retry("cp-retry")

    engine2 = CoordinationEngine(
        clock=_make_clock([_T1]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="pack-v1",
    )
    outcome = engine2.restore_checkpoint("cp-retry", current_policy_pack_id="pack-v1")
    assert outcome.status == RestoreStatus.ABORTED
    assert outcome.reason == "checkpoint retry limit exceeded"
    assert "3" not in outcome.reason


# --- No store configured ---


def test_save_without_store_raises() -> None:
    engine = CoordinationEngine()
    with pytest.raises(RuntimeCoreInvariantError, match="no coordination store"):
        engine.save_checkpoint("cp-1")


def test_restore_without_store_raises() -> None:
    engine = CoordinationEngine()
    with pytest.raises(RuntimeCoreInvariantError, match="no coordination store"):
        engine.restore_checkpoint("cp-1")


# --- Empty state round-trip ---


def test_empty_state_round_trip(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    engine = CoordinationEngine(
        clock=_make_clock([_T0]),
        coordination_store=store,
        policy_pack_id="default",
    )
    engine.save_checkpoint("cp-empty")

    engine2 = CoordinationEngine(
        clock=_make_clock([_T1]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="default",
    )
    outcome = engine2.restore_checkpoint("cp-empty", current_policy_pack_id="default")
    assert outcome.status == RestoreStatus.RESUMED
    assert engine2.delegation_count == 0
    assert engine2.handoff_count == 0


# --- Idempotent restore ---


def test_idempotent_restore(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    engine.save_checkpoint("cp-idem")

    engine2 = CoordinationEngine(
        clock=_make_clock([_T1, _T1]),
        coordination_store=CoordinationStore(tmp_path),
        policy_pack_id="pack-v1",
    )
    out1 = engine2.restore_checkpoint("cp-idem", current_policy_pack_id="pack-v1")
    out2 = engine2.restore_checkpoint("cp-idem", current_policy_pack_id="pack-v1")
    assert out1.status == RestoreStatus.RESUMED
    assert out2.status == RestoreStatus.RESUMED
    assert engine2.delegation_count == 1


# --- Summary ---


def test_engine_summary(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    summary = engine.summary()
    assert summary["delegations"] == 1
    assert summary["handoffs"] == 1
    assert summary["merges"] == 1
    assert summary["conflicts"] == 1
    assert summary["unresolved_conflicts"] == 1


# --- Increment retry ---


def test_increment_retry_updates_count(tmp_path: Path) -> None:
    engine = _populated_engine(tmp_path)
    engine.save_checkpoint("cp-inc")

    updated = engine.increment_retry("cp-inc")
    assert updated.retry_count == 1

    updated2 = engine.increment_retry("cp-inc")
    assert updated2.retry_count == 2
