"""Purpose: verify managed temporal scheduler background loop.
Governance scope: bounded tick execution, error capture, and stop lifecycle.
Dependencies: temporal scheduler background loop and worker.
Invariants:
  - tick_once delegates to run_once with the configured limit.
  - worker exceptions are bounded into observable error state.
  - start is idempotent while running.
  - stop clears the managed thread reference.
"""

from __future__ import annotations

from mcoi_runtime.core.temporal_scheduler_background import TemporalSchedulerBackgroundLoop


class WorkerStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.limits: list[int] = []

    def run_once(self, *, limit: int):
        self.limits.append(limit)
        if self.fail:
            raise RuntimeError("tick failed")
        return ("result-a", "result-b")


def test_tick_once_records_processed_count() -> None:
    worker = WorkerStub()
    loop = TemporalSchedulerBackgroundLoop(worker=worker, interval_seconds=10, limit=7)

    tick = loop.tick_once()

    assert tick.tick_index == 1
    assert tick.processed_count == 2
    assert tick.error == ""
    assert worker.limits == [7]
    assert loop.summary()["processed_count"] == 2


def test_tick_once_bounds_worker_error() -> None:
    worker = WorkerStub(fail=True)
    loop = TemporalSchedulerBackgroundLoop(worker=worker, interval_seconds=10, limit=3)

    tick = loop.tick_once()
    summary = loop.summary()

    assert tick.processed_count == 0
    assert "temporal scheduler background error" in tick.error
    assert "tick failed" not in tick.error
    assert summary["error_count"] == 1
    assert summary["last_error"] == tick.error
    assert worker.limits == [3]


def test_start_is_idempotent_and_stop_clears_thread() -> None:
    worker = WorkerStub()
    loop = TemporalSchedulerBackgroundLoop(worker=worker, interval_seconds=0.05, limit=1)

    first_start = loop.start()
    second_start = loop.start()
    stopped = loop.stop()

    assert first_start is True
    assert second_start is False
    assert stopped["running"] is False
    assert stopped["governed"] is True
    assert loop.running is False


def test_background_loop_rejects_invalid_bounds() -> None:
    worker = WorkerStub()

    try:
        TemporalSchedulerBackgroundLoop(worker=worker, interval_seconds=0, limit=1)
    except ValueError as exc:
        assert "interval_seconds" in str(exc)
    else:
        raise AssertionError("zero interval should fail closed")

    try:
        TemporalSchedulerBackgroundLoop(worker=worker, interval_seconds=1, limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("zero limit should fail closed")
