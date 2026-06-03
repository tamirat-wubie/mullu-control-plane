"""Concurrency regression: EventSpineEngine under the threadpool.

Several read methods iterate _events / _subscriptions / _reactions / _envelopes
(list_events, state_hash, snapshot, matching_subscriptions, ...) while writers
insert/clear them, which raised "dictionary changed size during iteration". One
engine-wide re-entrant lock now serializes all access. This test reproduces the
crash (fails pre-fix) and keeps a single-threaded sanity check.
"""

from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
)
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


def _event(eid: str) -> EventRecord:
    return EventRecord(
        event_id=eid,
        event_type=EventType.JOB_STATE_TRANSITION,
        source=EventSource.JOB_RUNTIME,
        correlation_id="corr-1",
        payload={"detail": "x"},
        emitted_at=_AT,
    )


def _sub(sid: str) -> EventSubscription:
    return EventSubscription(
        subscription_id=sid,
        event_type=EventType.JOB_STATE_TRANSITION,
        subscriber_id="x",
        reaction_id="r",
        created_at=_AT,
    )


def test_concurrent_subscribe_and_match_no_crash():
    # matching_subscriptions iterates self._subscriptions with a Python for-loop
    # (long window) -- the reliable iterate-vs-mutate site. Writers churn
    # subscribe/unsubscribe (size changes); a barrier + pre-seed maximize overlap.
    spine = EventSpineEngine(clock=lambda: _AT)
    for i in range(500):
        spine.subscribe(_sub(f"seed-{i}"))

    errors: list[str] = []
    guard = threading.Lock()
    barrier = threading.Barrier(6)
    probe = _event("probe")

    def writer(w: int) -> None:
        barrier.wait()
        try:
            for i in range(300):
                sid = f"w-{w}-{i}"
                spine.subscribe(_sub(sid))
                spine.unsubscribe(sid)
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(repr(exc))

    def reader() -> None:
        barrier.wait()
        try:
            for _ in range(150):
                spine.matching_subscriptions(probe)
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(repr(exc))

    threads = [threading.Thread(target=writer, args=(w,)) for w in range(3)]
    threads += [threading.Thread(target=reader) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == [], f"concurrent event spine raised: {errors[:1]}"


def test_emit_and_list_single_threaded():
    spine = EventSpineEngine(clock=lambda: _AT)
    spine.emit(_event("e-1"))
    assert len(spine.list_events()) == 1
