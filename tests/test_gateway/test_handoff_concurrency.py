"""Concurrency regression tests for the gateway HandoffRouter.

Background: FastAPI dispatches sync handlers across a threadpool, so the
HandoffRouter delegation methods run concurrently. delegate_to_specialist
iterates the shared ``_active_delegations`` dict (via _active_lease_count) and
then inserts/pops it, while kill_specialist_lease pops it. Without a lock this
races as ``RuntimeError("dictionary changed size during iteration")`` -- a
spurious 500.

These tests drive admission (which iterates then inserts) against lease
termination (which pops) from many threads and assert no BaseException escapes.
They are written to FAIL against the pre-fix (lock-free) implementation: stash
gateway/handoff.py and rerun to see the negative control raise.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.handoff import HandoffRouter, SpecialistWorkerSpec  # noqa: E402


@pytest.fixture(autouse=True)
def _fast_thread_switch():
    """Force frequent thread switches to expose dict-iteration races."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _make_router(*, max_active_leases: int = 10_000_000) -> HandoffRouter:
    router = HandoffRouter()
    # No handler => leases stay "accepted" and resident in _active_delegations,
    # so concurrent admission keeps the dict populated for the race window.
    router.register_specialist_worker(SpecialistWorkerSpec(
        worker_id="w1",
        role="research_agent",
        allowed_capabilities=("cap.read",),
        max_budget_cents=10_000,
        max_timeout_seconds=3_600,
        max_active_leases=max_active_leases,
        handler=None,
    ))
    return router


def _seed_leases(router: HandoffRouter, count: int) -> list[str]:
    lease_ids: list[str] = []
    for i in range(count):
        receipt = router.delegate_to_specialist(
            delegator_id="d1",
            worker_id="w1",
            goal_id=f"g{i}",
            capability_id="cap.read",
            tenant_id="t1",
            identity_id="u1",
            budget_cents=100,
            timeout_seconds=60,
        )
        lease_ids.append(receipt.lease_id)
    return lease_ids


def _run_threads(workers: list[threading.Thread], *, deadline: float) -> None:
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join(timeout=deadline + 30.0)
    still_alive = [t for t in workers if t.is_alive()]
    assert not still_alive, f"threads did not finish (possible deadlock): {len(still_alive)}"


def test_concurrent_delegate_and_kill_is_safe():
    """Admission (iterate + insert) racing against lease termination (pop)."""
    router = _make_router()
    seeded = _seed_leases(router, 500)

    errors: list[str] = []
    barrier = threading.Barrier(6)
    stop = threading.Event()
    gid = itertools.count(10_000)
    deadline = time.monotonic() + 2.0

    def adder() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                router.delegate_to_specialist(
                    delegator_id="d1",
                    worker_id="w1",
                    goal_id=f"g{next(gid)}",
                    capability_id="cap.read",
                    tenant_id="t1",
                    identity_id="u1",
                    budget_cents=100,
                    timeout_seconds=60,
                )
        except BaseException as exc:  # noqa: BLE001 - capture any escape
            errors.append(repr(exc))
            stop.set()

    def killer(local: list[str]) -> None:
        barrier.wait()
        index = 0
        try:
            while time.monotonic() < deadline and not stop.is_set():
                if index < len(local):
                    router.kill_specialist_lease(local[index], reason="test")
                    index += 1
                else:
                    snapshot = list(router._active_delegations.keys())[:1]
                    for lease_id in snapshot:
                        router.kill_specialist_lease(lease_id, reason="test")
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    workers = [threading.Thread(target=adder) for _ in range(3)]
    workers += [
        threading.Thread(target=killer, args=(seeded[i::3],)) for i in range(3)
    ]
    _run_threads(workers, deadline=deadline)

    assert not errors, f"concurrent delegate/kill raised: {errors[:3]}"


def test_concurrent_delegate_and_summary_is_safe():
    """summary reads while admission mutates _active_delegations."""
    router = _make_router()
    _seed_leases(router, 400)

    errors: list[str] = []
    barrier = threading.Barrier(6)
    stop = threading.Event()
    gid = itertools.count(50_000)
    deadline = time.monotonic() + 2.0

    def adder() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                receipt = router.delegate_to_specialist(
                    delegator_id="d1",
                    worker_id="w1",
                    goal_id=f"g{next(gid)}",
                    capability_id="cap.read",
                    tenant_id="t1",
                    identity_id="u1",
                    budget_cents=100,
                    timeout_seconds=60,
                )
                router.kill_specialist_lease(receipt.lease_id, reason="cycle")
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    def observer() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                router.summary()
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    workers = [threading.Thread(target=adder) for _ in range(3)]
    workers += [threading.Thread(target=observer) for _ in range(3)]
    _run_threads(workers, deadline=deadline)

    assert not errors, f"concurrent delegate/summary raised: {errors[:3]}"


def test_single_threaded_behavior_preserved():
    """Locking must not change the single-threaded delegation contract."""
    router = _make_router(max_active_leases=1)

    accepted = router.delegate_to_specialist(
        delegator_id="d1",
        worker_id="w1",
        goal_id="g1",
        capability_id="cap.read",
        tenant_id="t1",
        identity_id="u1",
        budget_cents=100,
        timeout_seconds=60,
    )
    assert accepted.status == "accepted"
    assert len(router._active_delegations) == 1

    # Second lease must be rejected at capacity (max_active_leases=1).
    rejected = router.delegate_to_specialist(
        delegator_id="d1",
        worker_id="w1",
        goal_id="g2",
        capability_id="cap.read",
        tenant_id="t1",
        identity_id="u1",
        budget_cents=100,
        timeout_seconds=60,
    )
    assert rejected.status == "rejected"
    assert rejected.reason == "worker lease capacity reached"

    cancelled = router.kill_specialist_lease(accepted.lease_id, reason="done")
    assert cancelled.status == "cancelled"
    assert len(router._active_delegations) == 0

    summary = router.summary()
    assert summary["active_specialist_leases"] == 0
    assert "w1" in summary["specialist_workers"]
