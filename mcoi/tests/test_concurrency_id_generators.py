"""Concurrency regressions: in-memory ID generators must be thread-safe.

FastAPI runs sync route handlers in a threadpool, so the in-memory managers are
hit concurrently. EventBus.publish and ReplayRecorder.record_frame increment a
counter and format an id from it (`evt-N`, `frame-N`); an unlocked `+= 1` is a
read-modify-write that can lose increments under concurrency, emitting DUPLICATE
ids (an audit-integrity problem). ReplayRecorder.start_trace is a check-then-set
that, unlocked, lets two threads both "create" the same trace. Both are now
guarded by a lock.

These tests drive real threads and assert id uniqueness / single-winner -- they
fail (probabilistically) if the locks are removed.
"""

from __future__ import annotations

import threading

from mcoi_runtime.core.event_bus import EventBus
from mcoi_runtime.core.execution_replay import ReplayRecorder


_CLOCK = "2026-01-01T00:00:00+00:00"


def test_event_bus_concurrent_publish_emits_unique_event_ids():
    bus = EventBus(clock=lambda: _CLOCK)
    collected: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        local = [bus.publish("evt.type", tenant_id="t").event_id for _ in range(100)]
        with guard:
            collected.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 800
    assert len(set(collected)) == 800  # no lost increments -> no duplicate ids


def test_replay_recorder_concurrent_record_emits_unique_frame_ids():
    recorder = ReplayRecorder(clock=lambda: _CLOCK)
    collected: list[str] = []
    guard = threading.Lock()

    def worker(trace_id: str) -> None:
        recorder.start_trace(trace_id)
        local = [recorder.record_frame(trace_id, "op", {}, {}).frame_id for _ in range(50)]
        with guard:
            collected.extend(local)

    threads = [threading.Thread(target=worker, args=(f"trace-{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 400
    assert len(set(collected)) == 400


def test_replay_recorder_concurrent_start_same_trace_has_one_winner():
    recorder = ReplayRecorder(clock=lambda: _CLOCK)
    winners: list[bool] = []
    guard = threading.Lock()

    def worker() -> None:
        try:
            recorder.start_trace("shared-trace")
        except ValueError:
            return  # "trace already started" -- lost the race, correctly rejected
        with guard:
            winners.append(True)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1  # exactly one thread created the trace (no double-create)
