"""Purpose: verify temporal scheduler persistence.
Governance scope: scheduled action snapshots, run receipts, restart restore,
    and malformed file rejection.
Dependencies: temporal scheduler store and temporal scheduler engine.
Invariants:
  - File-backed state round-trips deterministically.
  - Duplicate matching receipts are idempotent.
  - Corrupt payloads fail closed.
  - Restored actions become due after restart.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import (
    ScheduleDecisionVerdict,
    ScheduledActionState,
    TemporalSchedulerEngine,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.temporal_scheduler_store import (
    FileTemporalSchedulerStore,
    TemporalSchedulerStore,
)


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now


def _engine(clock: MutableClock) -> TemporalSchedulerEngine:
    temporal = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    return TemporalSchedulerEngine(temporal, clock=clock)


def _action(action_id: str = "act-1") -> TemporalActionRequest:
    return TemporalActionRequest(
        action_id=action_id,
        tenant_id="tenant-a",
        actor_id="user-a",
        action_type="reminder",
        requested_at="2026-05-04T13:00:00+00:00",
        execute_at="2026-05-04T14:00:00+00:00",
    )


def test_memory_store_saves_actions_and_receipts() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduled = scheduler.register("sched-1", _action())
    assert scheduler.acquire_lease(scheduled.schedule_id, "worker-a") is not None
    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
    store = TemporalSchedulerStore()

    store.save_action(scheduler.get("sched-1"))
    store.append_receipt(receipt)
    repeated = store.append_receipt(receipt)

    assert store.get_action("sched-1").state == ScheduledActionState.RUNNING
    assert repeated == receipt
    assert store.list_receipts(schedule_id="sched-1") == (receipt,)
    assert store.summary()["by_verdict"][ScheduleDecisionVerdict.DUE.value] == 1


def test_duplicate_receipt_id_with_different_payload_fails_closed() -> None:
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduler.register("sched-1", _action())
    first = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
    second = scheduler.mark_completed("sched-1", worker_id="worker-a")
    store = TemporalSchedulerStore()

    store.append_receipt(first)
    forged = type(second)(
        receipt_id=first.receipt_id,
        schedule_id=second.schedule_id,
        tenant_id=second.tenant_id,
        verdict=second.verdict,
        reason=second.reason,
        evaluated_at=second.evaluated_at,
        worker_id=second.worker_id,
    )

    with pytest.raises(PersistenceError, match="receipt id collision"):
        store.append_receipt(forged)
    assert store.list_receipts() == (first,)
    assert store.summary()["receipt_count"] == 1


def test_file_store_round_trips_scheduler_state(tmp_path) -> None:
    path = tmp_path / "temporal_scheduler.json"
    clock = MutableClock("2026-05-04T14:00:00+00:00")
    scheduler = _engine(clock)
    scheduled = scheduler.register("sched-1", _action(), handler_name="reminder_handler")
    assert scheduler.acquire_lease(scheduled.schedule_id, "worker-a") is not None
    receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
    store = FileTemporalSchedulerStore(path)

    store.save_action(scheduler.get("sched-1"))
    store.append_receipt(receipt)
    reloaded = FileTemporalSchedulerStore(path)

    assert reloaded.get_action("sched-1").handler_name == "reminder_handler"
    assert reloaded.get_action("sched-1").state == ScheduledActionState.RUNNING
    assert reloaded.list_receipts() == (receipt,)
    assert reloaded.summary()["action_count"] == 1


def test_file_store_restore_actions_into_empty_scheduler(tmp_path) -> None:
    path = tmp_path / "temporal_scheduler.json"
    clock = MutableClock("2026-05-04T13:00:00+00:00")
    scheduler = _engine(clock)
    store = FileTemporalSchedulerStore(path)
    store.save_action(scheduler.register("sched-1", _action()))
    reloaded = FileTemporalSchedulerStore(path)
    restored_clock = MutableClock("2026-05-04T14:00:00+00:00")
    restored_scheduler = _engine(restored_clock)

    restored_scheduler.restore(reloaded.list_actions())
    due = restored_scheduler.due_actions()

    assert len(due) == 1
    assert due[0].schedule_id == "sched-1"
    assert restored_scheduler.get("sched-1").state == ScheduledActionState.PENDING
    assert reloaded.summary()["receipt_count"] == 0


def test_file_store_rejects_malformed_payload(tmp_path) -> None:
    path = tmp_path / "temporal_scheduler.json"
    path.write_text(json.dumps({"actions": [{"schedule_id": "incomplete"}], "receipts": []}), encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="invalid scheduled temporal action"):
        FileTemporalSchedulerStore(path)
    assert path.exists()
    assert "incomplete" in path.read_text(encoding="utf-8")
