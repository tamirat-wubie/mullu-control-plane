"""Concurrency regression: CorrelationManager under the threadpool.

start() runs on every request and calls cleanup_stale(), which iterates
self._active_inserted_at while concurrent start()/complete() mutate it -- raising
"dictionary changed size during iteration". A lock now guards the _active /
_active_inserted_at / _completed mutations. This test reproduces the crash (fails
pre-fix) and keeps a single-threaded sanity check.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.request_correlation import CorrelationManager


@pytest.fixture(autouse=True)
def _force_thread_switches():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_start_and_complete_no_crash():
    manager = CorrelationManager(
        clock=lambda: "2026-01-01T00:00:00Z", active_ttl_seconds=3600.0
    )
    errors: list[str] = []
    guard = threading.Lock()

    def worker(w: int) -> None:
        try:
            for i in range(2000):
                ctx = manager.start(tenant_id=f"t{w}", endpoint="/x")
                if i % 2 == 0:
                    manager.complete(ctx.correlation_id)
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Pre-fix this raised RuntimeError("dictionary changed size during iteration").
    assert errors == [], f"concurrent correlation raised: {errors[:1]}"


def test_start_complete_single_threaded():
    manager = CorrelationManager(clock=lambda: "2026-01-01T00:00:00Z")
    ctx = manager.start(tenant_id="t", endpoint="/x")
    assert ctx.correlation_id.startswith("cor-")
    assert manager.get_context(ctx.correlation_id) is not None
    manager.complete(ctx.correlation_id)
    assert manager.get_context(ctx.correlation_id) is None
