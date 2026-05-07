"""Purpose: verify governed temporal scheduler worker execution.
Governance scope: due-action leasing, handler dispatch, failure closure,
    receipt persistence, and proof certification.
Dependencies: temporal scheduler, temporal scheduler worker, scheduler store,
    proof bridge, and temporal runtime.
Invariants:
  - Handlers run only after a due scheduler receipt.
  - Missing handlers close with a bounded failure reason.
  - Handler exceptions do not leak untrusted text into receipts.
  - Optional proof certification records evaluation and closure transitions.
"""

from __future__ import annotations

import json

from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.proof_bridge import ProofBridge
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import (
    ScheduleDecisionVerdict,
    ScheduledActionState,
    ScheduledTemporalAction,
    TemporalSchedulerEngine,
)
from mcoi_runtime.core.temporal_scheduler_worker import TemporalSchedulerWorker
from mcoi_runtime.persistence.temporal_scheduler_store import TemporalSchedulerStore


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


def _scheduler(clock: MutableClock) -> TemporalSchedulerEngine:
    temporal = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    return TemporalSchedulerEngine(temporal, clock=clock)


def _action(*, action_id: str = "act-1") -> TemporalActionRequest:
    return TemporalActionRequest(
        action_id=action_id,
        tenant_id="tenant-a",
        actor_id="user-a",
        action_type="reminder",
        requested_at="2026-05-04T13:00:00+00:00",
        execute_at="2026-05-04T14:00:00+00:00",
    )


def test_worker_completes_due_action_and_certifies_proofs() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _scheduler(clock)
    store = TemporalSchedulerStore()
    bridge = ProofBridge(clock=clock)
    calls: list[str] = []
    scheduler.register("sched-1", _action(), handler_name="reminder_handler")

    worker = TemporalSchedulerWorker(
        scheduler=scheduler,
        store=store,
        worker_id="worker-a",
        handlers={
            "reminder_handler": lambda action: calls.append(action.schedule_id),
        },
        proof_bridge=bridge,
    )
    results = worker.run_once()

    assert len(results) == 1
    assert calls == ["sched-1"]
    assert results[0].evaluation_receipt.verdict == ScheduleDecisionVerdict.DUE
    assert results[0].closure_receipt.verdict == ScheduleDecisionVerdict.COMPLETED
    assert tuple(proof.decision for proof in results[0].proofs) == ("running", "completed")
    assert scheduler.get("sched-1").state == ScheduledActionState.COMPLETED
    assert store.get_action("sched-1").state == ScheduledActionState.COMPLETED
    assert store.summary()["receipt_count"] == 2
    assert bridge.lineage_count == 1


def test_worker_missing_handler_closes_with_bounded_failure() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _scheduler(clock)
    store = TemporalSchedulerStore()
    scheduler.register("sched-1", _action(), handler_name="missing_private_handler")

    worker = TemporalSchedulerWorker(
        scheduler=scheduler,
        store=store,
        worker_id="worker-a",
        handlers={},
    )
    results = worker.run_once()
    receipts = store.list_receipts(schedule_id="sched-1")

    assert len(results) == 1
    assert results[0].closure_receipt.reason == "missing_handler"
    assert scheduler.get("sched-1").state == ScheduledActionState.FAILED
    assert receipts[-1].verdict == ScheduleDecisionVerdict.BLOCKED
    assert receipts[-1].reason == "missing_handler"
    assert "missing_private_handler" not in json.dumps([receipt.reason for receipt in receipts])


def test_worker_handler_exception_closes_without_leaking_exception_text() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _scheduler(clock)
    store = TemporalSchedulerStore()
    scheduler.register("sched-1", _action(), handler_name="failing_handler")

    def failing_handler(_: ScheduledTemporalAction) -> None:
        raise RuntimeError("handler-secret-token")

    worker = TemporalSchedulerWorker(
        scheduler=scheduler,
        store=store,
        worker_id="worker-a",
        handlers={"failing_handler": failing_handler},
    )
    results = worker.run_once()
    serialized_receipts = json.dumps([
        {
            "reason": receipt.reason,
            "verdict": receipt.verdict.value,
            "worker_id": receipt.worker_id,
        }
        for receipt in store.list_receipts(schedule_id="sched-1")
    ], sort_keys=True)

    assert len(results) == 1
    assert results[0].closure_receipt.reason == "handler_error"
    assert scheduler.get("sched-1").state == ScheduledActionState.FAILED
    assert store.summary()["by_verdict"][ScheduleDecisionVerdict.BLOCKED.value] == 1
    assert "handler-secret-token" not in serialized_receipts
