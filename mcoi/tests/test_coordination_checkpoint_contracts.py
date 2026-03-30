"""Purpose: verify coordination checkpoint and restore contracts.
Governance scope: coordination checkpoint contract tests only.
Dependencies: coordination contracts.
Invariants: checkpoints carry lease/retry/policy; restore outcomes are typed.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.coordination import (
    CoordinationCheckpoint,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
    ConflictRecord,
    ConflictStrategy,
    RestoreOutcome,
    RestoreStatus,
)


_CLOCK = "2026-03-30T00:00:00+00:00"
_LEASE = "2026-03-30T01:00:00+00:00"


def _sample_delegation() -> DelegationRequest:
    return DelegationRequest(
        delegation_id="del-1",
        delegator_id="agent-a",
        delegate_id="agent-b",
        goal_id="goal-1",
        action_scope="execute_shell",
    )


def _sample_handoff() -> HandoffRecord:
    return HandoffRecord(
        handoff_id="ho-1",
        from_party="agent-a",
        to_party="agent-b",
        goal_id="goal-1",
        context_ids=("ctx-1",),
        handed_off_at=_CLOCK,
    )


# --- RestoreStatus enum ---


def test_restore_status_has_five_members() -> None:
    assert len(RestoreStatus) == 5
    assert set(RestoreStatus) == {
        RestoreStatus.RESUMED,
        RestoreStatus.EXPIRED,
        RestoreStatus.INVALID,
        RestoreStatus.NEEDS_REVIEW,
        RestoreStatus.ABORTED,
    }


# --- CoordinationCheckpoint ---


def test_checkpoint_creation_valid() -> None:
    cp = CoordinationCheckpoint(
        checkpoint_id="cp-1",
        delegations=(_sample_delegation(),),
        delegation_results=(),
        handoffs=(_sample_handoff(),),
        merges=(),
        conflicts=(),
        created_at=_CLOCK,
        lease_expires_at=_LEASE,
        retry_count=0,
        policy_pack_id="default",
    )
    assert cp.checkpoint_id == "cp-1"
    assert len(cp.delegations) == 1
    assert len(cp.handoffs) == 1
    assert cp.retry_count == 0
    assert cp.policy_pack_id == "default"


def test_checkpoint_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        CoordinationCheckpoint(
            checkpoint_id="",
            delegations=(),
            delegation_results=(),
            handoffs=(),
            merges=(),
            conflicts=(),
            created_at=_CLOCK,
            lease_expires_at=_LEASE,
            retry_count=0,
            policy_pack_id="default",
        )


def test_checkpoint_rejects_negative_retry() -> None:
    with pytest.raises(ValueError):
        CoordinationCheckpoint(
            checkpoint_id="cp-1",
            delegations=(),
            delegation_results=(),
            handoffs=(),
            merges=(),
            conflicts=(),
            created_at=_CLOCK,
            lease_expires_at=_LEASE,
            retry_count=-1,
            policy_pack_id="default",
        )


def test_checkpoint_rejects_empty_policy_pack() -> None:
    with pytest.raises(ValueError):
        CoordinationCheckpoint(
            checkpoint_id="cp-1",
            delegations=(),
            delegation_results=(),
            handoffs=(),
            merges=(),
            conflicts=(),
            created_at=_CLOCK,
            lease_expires_at=_LEASE,
            retry_count=0,
            policy_pack_id="",
        )


def test_checkpoint_freezes_restore_conditions() -> None:
    cp = CoordinationCheckpoint(
        checkpoint_id="cp-1",
        delegations=(),
        delegation_results=(),
        handoffs=(),
        merges=(),
        conflicts=(),
        created_at=_CLOCK,
        lease_expires_at=_LEASE,
        retry_count=0,
        policy_pack_id="default",
        restore_conditions={"key": "value"},
    )
    with pytest.raises(TypeError):
        cp.restore_conditions["key"] = "mutated"  # type: ignore[index]


def test_checkpoint_is_frozen() -> None:
    cp = CoordinationCheckpoint(
        checkpoint_id="cp-1",
        delegations=(),
        delegation_results=(),
        handoffs=(),
        merges=(),
        conflicts=(),
        created_at=_CLOCK,
        lease_expires_at=_LEASE,
        retry_count=0,
        policy_pack_id="default",
    )
    with pytest.raises(AttributeError):
        cp.checkpoint_id = "mutated"  # type: ignore[misc]


def test_checkpoint_empty_state() -> None:
    cp = CoordinationCheckpoint(
        checkpoint_id="cp-empty",
        delegations=(),
        delegation_results=(),
        handoffs=(),
        merges=(),
        conflicts=(),
        created_at=_CLOCK,
        lease_expires_at=_LEASE,
        retry_count=0,
        policy_pack_id="default",
    )
    assert cp.delegations == ()
    assert cp.handoffs == ()
    assert cp.merges == ()
    assert cp.conflicts == ()


# --- RestoreOutcome ---


def test_restore_outcome_creation() -> None:
    outcome = RestoreOutcome(
        checkpoint_id="cp-1",
        status=RestoreStatus.RESUMED,
        reason="checkpoint restored successfully",
        restored_at=_CLOCK,
    )
    assert outcome.status == RestoreStatus.RESUMED
    assert outcome.reason == "checkpoint restored successfully"


def test_restore_outcome_rejects_invalid_status() -> None:
    with pytest.raises(ValueError, match="RestoreStatus"):
        RestoreOutcome(
            checkpoint_id="cp-1",
            status="not_a_status",  # type: ignore[arg-type]
            reason="test",
            restored_at=_CLOCK,
        )


def test_restore_outcome_rejects_empty_reason() -> None:
    with pytest.raises(ValueError):
        RestoreOutcome(
            checkpoint_id="cp-1",
            status=RestoreStatus.EXPIRED,
            reason="",
            restored_at=_CLOCK,
        )


@pytest.mark.parametrize("status", list(RestoreStatus))
def test_restore_outcome_accepts_all_statuses(status: RestoreStatus) -> None:
    outcome = RestoreOutcome(
        checkpoint_id="cp-1",
        status=status,
        reason=f"test-{status.value}",
        restored_at=_CLOCK,
    )
    assert outcome.status == status
