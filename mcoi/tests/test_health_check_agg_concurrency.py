"""Concurrency regression: HealthCheckAggregator under the threadpool.

run() iterated self._checks while a concurrent register inserted / unregister
popped -- which raised "dictionary changed size during iteration", a spurious
500 on the health endpoint. run() now snapshots _checks under a lock and runs
each user check_fn (real I/O) on the snapshot, outside the lock. This test
reproduces the crash (it fails pre-fix) and asserts aggregation still works
single-threaded.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.health_check_agg import (
    HealthCheckAggregator,
    HealthCheckDef,
    HealthStatus,
)


@pytest.fixture(autouse=True)
def _force_thread_switches():
    # Amplify thread switching so the iterate-vs-mutate race surfaces reliably.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_run_concurrent_with_register_has_no_dict_crash():
    # Writers register distinct check names so the dict keeps growing while
    # run() iterates -- the collision window for "changed size during iteration".
    agg = HealthCheckAggregator()
    errors: list[str] = []
    guard = threading.Lock()

    def _probe() -> dict[str, str]:
        return {"status": "healthy"}

    def writer(w: int) -> None:
        try:
            for i in range(2000):
                name = f"w{w}-chk{i}"
                agg.register(HealthCheckDef(name=name, check_fn=_probe))
                # Drop a now-stale check to also exercise the size-shrink path.
                agg.unregister(f"w{w}-chk{i - 1}")
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    def runner() -> None:
        try:
            for _ in range(2000):
                agg.run()
        except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
            with guard:
                errors.append(repr(exc))

    threads: list[threading.Thread] = []
    for w in range(4):
        threads.append(threading.Thread(target=writer, args=(w,)))
        threads.append(threading.Thread(target=runner))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Pre-fix this raised RuntimeError("dictionary changed size during iteration").
    assert errors == [], f"concurrent HealthCheckAggregator access raised: {errors[:1]}"


def test_aggregate_single_threaded():
    agg = HealthCheckAggregator()
    agg.register(HealthCheckDef(name="ok", check_fn=lambda: {"status": "healthy"}))
    agg.register(
        HealthCheckDef(name="slow", check_fn=lambda: {"status": "degraded"}, weight=1.0)
    )
    assert agg.check_count == 2
    result = agg.run()
    # Worst-case status across {healthy, degraded} is degraded.
    assert result.status == HealthStatus.DEGRADED
    # Equal weights: (100 + 50) / 2 == 75.
    assert result.score == pytest.approx(75.0)
    assert {c.name for c in result.checks} == {"ok", "slow"}
    agg.unregister("slow")
    assert agg.check_count == 1
    healthy = agg.run()
    assert healthy.status == HealthStatus.HEALTHY
    assert healthy.score == pytest.approx(100.0)
