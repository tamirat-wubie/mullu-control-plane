"""Concurrency regression tests for the gateway ApprovalRouter.

Background: FastAPI dispatches sync handlers across a threadpool, so the
ApprovalRouter methods run concurrently. Several methods iterate the shared
``_pending`` dict (get_pending / summary / _prune_expired_pending) while others
size-mutate it (request_approval inserts a new key; resolve / lookup_request /
eviction pop). Without a lock this races as
``RuntimeError("dictionary changed size during iteration")`` -- a spurious 500.

These tests drive the iterate paths against the mutate paths from many threads
and assert no BaseException escapes. They are written to FAIL against the
pre-fix (lock-free) implementation: stash gateway/approval.py and rerun to see
the negative control raise.
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

from gateway.approval import ApprovalRouter, ApprovalStatus, RiskTier  # noqa: E402


# Fixed clock inside the timeout window so seeded entries stay pending
# (do not get pruned) and remain resident for readers to iterate over.
_FIXED_NOW = "2026-06-03T12:00:00.000000+00:00"


def _fixed_clock() -> str:
    return _FIXED_NOW


@pytest.fixture(autouse=True)
def _fast_thread_switch():
    """Force frequent thread switches to expose dict-iteration races."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _seed_pending(router: ApprovalRouter, count: int) -> None:
    """Pre-seed ``count`` HIGH-risk pending requests."""
    for i in range(count):
        router.request_approval(
            tenant_id=f"t{i % 5}",
            identity_id=f"u{i}",
            channel="slack",
            action_description=f"delete record {i}",  # 'delete' -> HIGH -> pending
            body="please remove it",
        )


def _run_threads(workers: list[threading.Thread], *, deadline: float) -> None:
    for thread in workers:
        thread.start()
    for thread in workers:
        # Generous join; the bodies stop themselves at ``deadline``.
        thread.join(timeout=deadline + 30.0)
    still_alive = [t for t in workers if t.is_alive()]
    assert not still_alive, f"threads did not finish (possible deadlock): {len(still_alive)}"


def test_concurrent_iterate_and_mutate_pending_is_safe():
    """get_pending / summary must not crash while requests are added/resolved."""
    router = ApprovalRouter(clock=_fixed_clock, timeout_seconds=300)
    _seed_pending(router, 500)
    assert router.pending_count == 500

    errors: list[str] = []
    barrier = threading.Barrier(6)
    stop = threading.Event()
    seq = itertools.count(1000)
    deadline = time.monotonic() + 2.0

    def reader() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                router.get_pending("t1")
                router.summary()
                _ = router.total_requests
                _ = router.pending_count
        except BaseException as exc:  # noqa: BLE001 - capture any escape
            errors.append(repr(exc))
            stop.set()

    def writer() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                n = next(seq)
                router.request_approval(
                    tenant_id="t1",
                    identity_id=f"w{n}",
                    channel="slack",
                    action_description=f"delete thing {n}",
                    body="remove",
                )
                router.resolve(f"apr-{n}", approved=True)
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    workers = [threading.Thread(target=reader) for _ in range(3)]
    workers += [threading.Thread(target=writer) for _ in range(3)]
    _run_threads(workers, deadline=deadline)

    assert not errors, f"concurrent access raised: {errors[:3]}"


def test_concurrent_lookup_and_resolve_is_safe():
    """lookup_request + resolve racing against request_approval inserts."""
    router = ApprovalRouter(clock=_fixed_clock, timeout_seconds=300)
    _seed_pending(router, 400)

    errors: list[str] = []
    barrier = threading.Barrier(6)
    stop = threading.Event()
    seq = itertools.count(5000)
    deadline = time.monotonic() + 2.0

    def adder() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                n = next(seq)
                req = router.request_approval(
                    tenant_id="t2",
                    identity_id=f"a{n}",
                    channel="slack",
                    action_description=f"transfer payment {n}",  # HIGH
                    body="execute now",
                )
                router.lookup_request(req.request_id)
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    def closer() -> None:
        barrier.wait()
        try:
            while time.monotonic() < deadline and not stop.is_set():
                for req in router.get_pending():
                    router.resolve(req.request_id, approved=False)
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))
            stop.set()

    workers = [threading.Thread(target=adder) for _ in range(3)]
    workers += [threading.Thread(target=closer) for _ in range(3)]
    _run_threads(workers, deadline=deadline)

    assert not errors, f"concurrent lookup/resolve raised: {errors[:3]}"


def test_single_threaded_behavior_preserved():
    """Locking must not change the single-threaded contract."""
    router = ApprovalRouter(clock=_fixed_clock, timeout_seconds=300)

    auto = router.request_approval(
        tenant_id="t1",
        identity_id="u1",
        channel="slack",
        action_description="read the calendar",  # LOW -> auto-approve
        body="show me",
    )
    assert auto.status == ApprovalStatus.APPROVED
    assert auto.risk_tier == RiskTier.LOW

    pending = router.request_approval(
        tenant_id="t1",
        identity_id="u2",
        channel="slack",
        action_description="delete the record",  # HIGH -> pending
        body="remove it",
    )
    assert pending.status == ApprovalStatus.PENDING
    assert router.pending_count == 1
    assert pending in router.get_pending("t1")

    resolved = router.resolve(pending.request_id, approved=True)
    assert resolved is not None
    assert resolved.status == ApprovalStatus.APPROVED
    assert router.pending_count == 0

    summary = router.summary()
    assert summary["pending"] == 0
    assert summary["total"] == 2
