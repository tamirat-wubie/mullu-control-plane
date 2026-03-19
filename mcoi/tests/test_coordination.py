"""Purpose: verify coordination contracts and engine — delegation, handoff, merge, conflict.
Governance scope: coordination plane tests only.
Dependencies: coordination contracts, coordination engine.
Invariants: provenance preserved; conflicts recorded; delegation explicit.
"""

from __future__ import annotations

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
)
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


_CLOCK = "2026-03-19T00:00:00+00:00"


# --- Contract tests ---

def test_delegation_request_validates() -> None:
    req = DelegationRequest(
        delegation_id="del-1",
        delegator_id="agent-a",
        delegate_id="agent-b",
        goal_id="goal-1",
        action_scope="execute_shell",
    )
    assert req.delegation_id == "del-1"


def test_delegation_request_rejects_self_delegation() -> None:
    with pytest.raises(ValueError, match="different"):
        DelegationRequest(
            delegation_id="del-1",
            delegator_id="agent-a",
            delegate_id="agent-a",
            goal_id="goal-1",
            action_scope="scope",
        )


def test_handoff_rejects_same_party() -> None:
    with pytest.raises(ValueError, match="different"):
        HandoffRecord(
            handoff_id="ho-1",
            from_party="agent-a",
            to_party="agent-a",
            goal_id="goal-1",
            context_ids=("ctx-1",),
            handed_off_at=_CLOCK,
        )


def test_handoff_requires_context_ids() -> None:
    with pytest.raises(ValueError, match="context_ids"):
        HandoffRecord(
            handoff_id="ho-1",
            from_party="a",
            to_party="b",
            goal_id="g-1",
            context_ids=(),
            handed_off_at=_CLOCK,
        )


def test_merge_requires_two_sources() -> None:
    with pytest.raises(ValueError, match="two source"):
        MergeDecision(
            merge_id="m-1",
            goal_id="g-1",
            source_ids=("only-one",),
            outcome=MergeOutcome.MERGED,
            reason="r",
            resolved_at=_CLOCK,
        )


def test_conflict_requires_two_conflicting() -> None:
    with pytest.raises(ValueError, match="two conflicting"):
        ConflictRecord(
            conflict_id="c-1",
            goal_id="g-1",
            conflicting_ids=("one",),
            strategy=ConflictStrategy.ESCALATE,
            resolved=False,
        )


def test_conflict_resolved_requires_resolution_id() -> None:
    with pytest.raises(ValueError, match="resolution_id"):
        ConflictRecord(
            conflict_id="c-1",
            goal_id="g-1",
            conflicting_ids=("a", "b"),
            strategy=ConflictStrategy.MANUAL,
            resolved=True,
            resolution_id=None,
        )


# --- Engine tests ---

def test_delegation_request_and_resolve() -> None:
    engine = CoordinationEngine()
    req = DelegationRequest(
        delegation_id="del-1",
        delegator_id="a",
        delegate_id="b",
        goal_id="g-1",
        action_scope="scope",
    )
    engine.request_delegation(req)

    result = DelegationResult(
        delegation_id="del-1",
        status=DelegationStatus.ACCEPTED,
        reason="available",
        resolved_at=_CLOCK,
    )
    engine.resolve_delegation(result)

    assert engine.get_delegation("del-1") is not None
    assert engine.get_delegation_result("del-1").status is DelegationStatus.ACCEPTED


def test_duplicate_delegation_rejected() -> None:
    engine = CoordinationEngine()
    req = DelegationRequest(
        delegation_id="del-1", delegator_id="a",
        delegate_id="b", goal_id="g-1", action_scope="s",
    )
    engine.request_delegation(req)
    with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
        engine.request_delegation(req)


def test_resolve_unknown_delegation_rejected() -> None:
    engine = CoordinationEngine()
    with pytest.raises(RuntimeCoreInvariantError, match="not found"):
        engine.resolve_delegation(DelegationResult(
            delegation_id="nonexistent",
            status=DelegationStatus.REJECTED,
            reason="nope",
            resolved_at=_CLOCK,
        ))


def test_handoff_recorded() -> None:
    engine = CoordinationEngine()
    handoff = HandoffRecord(
        handoff_id="ho-1",
        from_party="agent-a",
        to_party="agent-b",
        goal_id="g-1",
        context_ids=("exec-1", "ver-1"),
        handed_off_at=_CLOCK,
    )
    engine.record_handoff(handoff)
    assert engine.get_handoff("ho-1") is not None
    assert engine.get_handoff("ho-1").context_ids == ("exec-1", "ver-1")


def test_merge_recorded() -> None:
    engine = CoordinationEngine()
    merge = MergeDecision(
        merge_id="m-1",
        goal_id="g-1",
        source_ids=("res-a", "res-b"),
        outcome=MergeOutcome.MERGED,
        reason="no conflicts",
        resolved_at=_CLOCK,
    )
    engine.record_merge(merge)
    assert engine.get_merge("m-1") is not None


def test_conflict_recorded_and_listed() -> None:
    engine = CoordinationEngine()

    unresolved = ConflictRecord(
        conflict_id="c-1",
        goal_id="g-1",
        conflicting_ids=("a", "b"),
        strategy=ConflictStrategy.ESCALATE,
        resolved=False,
    )
    resolved = ConflictRecord(
        conflict_id="c-2",
        goal_id="g-1",
        conflicting_ids=("x", "y"),
        strategy=ConflictStrategy.PREFER_LATEST,
        resolved=True,
        resolution_id="res-1",
    )
    engine.record_conflict(unresolved)
    engine.record_conflict(resolved)

    unresolved_list = engine.list_unresolved_conflicts()
    assert len(unresolved_list) == 1
    assert unresolved_list[0].conflict_id == "c-1"
