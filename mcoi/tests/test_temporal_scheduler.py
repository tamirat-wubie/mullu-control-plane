"""Purpose: tests for the in-memory TemporalSchedulerEngine.
Governance scope: frozen-clock scheduling, leases, wake-time temporal policy,
    closure receipts, and bounded denial reasons.
Dependencies: temporal_scheduler, temporal_runtime, event_spine.
Invariants:
  - Future actions are not due.
  - Leases prevent duplicate due dispatch.
  - Wake-time policy is re-checked.
  - Expired and missed actions emit receipts.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest, TemporalPolicyVerdict
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import (
    ScheduleDecisionVerdict,
    ScheduledActionState,
    TemporalSchedulerEngine,
)


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now

    def set(self, now: str) -> None:
        self.now = now


def _engine(clock: MutableClock) -> TemporalSchedulerEngine:
    temporal = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    return TemporalSchedulerEngine(temporal, clock=clock)


def _action(
    *,
    execute_at: str = "2026-05-04T14:00:00+00:00",
    expires_at: str = "",
    approval_expires_at: str = "",
    evidence_fresh_until: str = "",
    retry_after: str = "",
    max_attempts: int = 0,
    attempt_count: int = 0,
) -> TemporalActionRequest:
    return TemporalActionRequest(
        action_id="act-1",
        tenant_id="tenant-a",
        actor_id="user-a",
        action_type="reminder",
        requested_at="2026-05-04T13:00:00+00:00",
        execute_at=execute_at,
        expires_at=expires_at,
        approval_expires_at=approval_expires_at,
        evidence_fresh_until=evidence_fresh_until,
        retry_after=retry_after,
        max_attempts=max_attempts,
        attempt_count=attempt_count,
    )


def test_register_requires_execute_at() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    action = _action(execute_at="")

    with pytest.raises(RuntimeCoreInvariantError, match="execute_at is required"):
        scheduler.register("sched-1", action)
    assert scheduler.action_count == 0
    assert scheduler.receipt_count == 0


def test_future_action_is_stored_but_not_due() -> None:
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    scheduled = scheduler.register("sched-1", _action())

    assert scheduled.state == ScheduledActionState.PENDING
    assert scheduler.due_actions() == ()
    assert scheduler.summary()["pending"] == 1


def test_due_action_becomes_visible_at_execute_at() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    due = scheduler.due_actions()
    assert len(due) == 1
    assert due[0].schedule_id == "sched-1"
    assert due[0].execute_at == "2026-05-04T14:00:00+00:00"


def test_lease_prevents_duplicate_worker_execution() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    lease = scheduler.acquire_lease("sched-1", "worker-a")
    duplicate = scheduler.acquire_lease("sched-1", "worker-b")

    assert lease is not None
    assert duplicate is None
    assert scheduler.due_actions() == ()
    assert scheduler.get("sched-1").state == ScheduledActionState.RUNNING


def test_wake_time_policy_allows_due_action() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.DUE
    assert receipt.reason == "temporal_policy_passed"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.ALLOW.value
    assert receipt.temporal_decision_id.startswith("dec-temp-action")


def test_expired_action_never_runs() -> None:
    clock = MutableClock("2026-05-04T15:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            expires_at="2026-05-04T15:00:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.EXPIRED
    assert receipt.reason == "command_expired"
    assert scheduler.get("sched-1").state == ScheduledActionState.EXPIRED


def test_approval_expired_at_wake_time_blocks_action() -> None:
    clock = MutableClock("2026-05-04T15:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            approval_expires_at="2026-05-04T15:00:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "approval_expired"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DENY.value
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED


def test_retry_before_retry_after_defers_again() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(
            execute_at="2026-05-04T14:00:00+00:00",
            retry_after="2026-05-04T14:10:00+00:00",
        ),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.NOT_DUE
    assert receipt.reason == "retry_window_not_open"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DEFER.value
    assert scheduler.get("sched-1").state == ScheduledActionState.PENDING


def test_max_attempts_denies_at_wake_time() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(max_attempts=3, attempt_count=3),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "retry_attempts_exhausted"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.DENY.value
    assert scheduler.receipt_count == 1


def test_completed_action_does_not_run_twice() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    completed = scheduler.mark_completed("sched-1", worker_id="worker-a")
    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-b")

    assert completed.verdict == ScheduleDecisionVerdict.COMPLETED
    assert receipt.reason == "already_completed"
    assert scheduler.due_actions() == ()
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED


def test_stale_evidence_escalates_and_blocks() -> None:
    clock = MutableClock("2026-05-04T14:01:00+00:00")
    scheduler = _engine(clock)
    scheduler.register(
        "sched-1",
        _action(evidence_fresh_until="2026-05-04T14:00:00+00:00"),
    )

    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "evidence_stale"
    assert receipt.temporal_verdict == TemporalPolicyVerdict.ESCALATE.value
    assert scheduler.get("sched-1").state == ScheduledActionState.BLOCKED


def test_missed_action_records_missed_run_receipt() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())

    receipt = scheduler.mark_missed("sched-1", worker_id="worker-a")

    assert receipt.verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipt.reason == "missed_run"
    assert scheduler.get("sched-1").state == ScheduledActionState.MISSED
    assert scheduler.recent_receipts()[0].receipt_id == receipt.receipt_id
