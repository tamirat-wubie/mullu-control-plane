"""Concurrency regression: DistributedRuntimeEngine under the threadpool.

The engine had NO lock: read methods iterate its record dicts
(workers_for_tenant, distributed_snapshot, state_hash, ...) while writers insert
them, raising "dictionary changed size during iteration". One engine-wide
re-entrant lock now serializes all access. This test reproduces the crash (fails
pre-fix) and keeps a single-threaded sanity check.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.distributed_runtime import DistributedRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine

_AT = "2026-01-01T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _force_thread_switches():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _engine() -> DistributedRuntimeEngine:
    return DistributedRuntimeEngine(EventSpineEngine(clock=lambda: _AT))


def test_concurrent_register_and_iterate_no_crash():
    engine = _engine()
    # Pre-seed so the readers iterate a non-trivial dict from t=0; barrier starts
    # everyone together for maximum overlap; bounded counts keep it fast.
    for i in range(500):
        engine.register_worker(f"seed-{i}", "t1", "W")

    errors: list[str] = []
    guard = threading.Lock()
    barrier = threading.Barrier(6)

    def registrar(w: int) -> None:
        barrier.wait()
        try:
            for i in range(300):
                engine.register_worker(f"w-{w}-{i}", "t1", "W")
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(repr(exc))

    def reader() -> None:
        barrier.wait()
        try:
            for _ in range(150):
                engine.workers_for_tenant("t1")
                engine.state_hash()
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=registrar, args=(w,)) for w in range(3)]
    threads += [threading.Thread(target=reader) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent distributed runtime raised: {errors[:1]}"


def test_register_and_query_single_threaded():
    engine = _engine()
    engine.register_worker("w1", "t1", "W1")
    assert len(engine.workers_for_tenant("t1")) == 1
