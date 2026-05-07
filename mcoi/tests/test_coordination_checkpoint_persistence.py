"""Purpose: verify coordination checkpoint persistence round-trips.
Governance scope: persistence layer coordination checkpoint tests only.
Dependencies: coordination contracts, coordination store, serialization.
Invariants: atomic writes; fail-closed on corruption; path traversal blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.coordination import (
    CoordinationCheckpoint,
    DelegationRequest,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
    ConflictRecord,
    ConflictStrategy,
)
from mcoi_runtime.persistence import CoordinationStore
from mcoi_runtime.persistence.errors import CorruptedDataError, PathTraversalError


_CLOCK = "2026-03-30T00:00:00+00:00"
_LEASE = "2026-03-30T01:00:00+00:00"


def _sample_checkpoint(
    checkpoint_id: str = "cp-1",
    *,
    with_records: bool = False,
) -> CoordinationCheckpoint:
    delegations = ()
    handoffs = ()
    merges = ()
    conflicts = ()
    if with_records:
        delegations = (
            DelegationRequest(
                delegation_id="del-1",
                delegator_id="agent-a",
                delegate_id="agent-b",
                goal_id="goal-1",
                action_scope="execute_shell",
            ),
        )
        handoffs = (
            HandoffRecord(
                handoff_id="ho-1",
                from_party="agent-a",
                to_party="agent-b",
                goal_id="goal-1",
                context_ids=("ctx-1",),
                handed_off_at=_CLOCK,
            ),
        )
        merges = (
            MergeDecision(
                merge_id="mg-1",
                goal_id="goal-1",
                source_ids=("src-1", "src-2"),
                outcome=MergeOutcome.MERGED,
                reason="combined results",
                resolved_at=_CLOCK,
            ),
        )
        conflicts = (
            ConflictRecord(
                conflict_id="cf-1",
                goal_id="goal-1",
                conflicting_ids=("a", "b"),
                strategy=ConflictStrategy.ESCALATE,
                resolved=False,
            ),
        )
    return CoordinationCheckpoint(
        checkpoint_id=checkpoint_id,
        delegations=delegations,
        delegation_results=(),
        handoffs=handoffs,
        merges=merges,
        conflicts=conflicts,
        created_at=_CLOCK,
        lease_expires_at=_LEASE,
        retry_count=0,
        policy_pack_id="default",
    )


def test_save_load_round_trip_empty(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    cp = _sample_checkpoint()
    store.save_state("cp-1", cp)
    loaded = store.load_state("cp-1", CoordinationCheckpoint)
    assert loaded.checkpoint_id == cp.checkpoint_id
    assert loaded.delegations == ()
    assert loaded.lease_expires_at == cp.lease_expires_at
    assert loaded.retry_count == 0


def test_save_load_round_trip_with_records(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    cp = _sample_checkpoint(with_records=True)
    store.save_state("cp-full", cp)
    loaded = store.load_state("cp-full", CoordinationCheckpoint)
    assert len(loaded.delegations) == 1
    assert loaded.delegations[0].delegation_id == "del-1"
    assert len(loaded.handoffs) == 1
    assert loaded.handoffs[0].handoff_id == "ho-1"
    assert len(loaded.merges) == 1
    assert loaded.merges[0].outcome == MergeOutcome.MERGED
    assert len(loaded.conflicts) == 1
    assert loaded.conflicts[0].strategy == ConflictStrategy.ESCALATE


def test_list_states_returns_sorted(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    for cid in ("cp-c", "cp-a", "cp-b"):
        store.save_state(cid, _sample_checkpoint(cid))
    assert store.list_states() == ("cp-a", "cp-b", "cp-c")


def test_corrupted_json_raises(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "cp-bad.json").write_text("not valid json", encoding="utf-8")
    with pytest.raises(CorruptedDataError):
        store.load_state("cp-bad", CoordinationCheckpoint)


def test_path_traversal_blocked(tmp_path: Path) -> None:
    store = CoordinationStore(tmp_path)
    with pytest.raises(PathTraversalError):
        store.save_state("../escape", _sample_checkpoint())
