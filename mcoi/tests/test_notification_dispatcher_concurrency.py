"""Concurrency regression tests for NotificationDispatcher.

Pre-fix, send() cleaned + iterated _recent_hashes with no lock while other
threads inserted a new dedup key and deleted expired ones. With a sub-
millisecond dedup window the expiry-delete path fires constantly, so concurrent
sends raced the iteration in _clean_dedup_cache and raised either
RuntimeError("dictionary changed size during iteration") or KeyError on the
del. These tests drive that race from many threads and assert no BaseException
escapes; they MUST fail on the unlocked implementation.
"""
from __future__ import annotations

import sys
import threading

import pytest

from mcoi_runtime.core.notification_dispatcher import (
    Notification,
    NotificationChannel,
    NotificationDispatcher,
    NotificationPriority,
)


@pytest.fixture(autouse=True)
def _tiny_switch_interval():
    # Force the interpreter to switch threads aggressively so the
    # iterate-vs-mutate window is hit reliably within a short test.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def _make_notification(index: int) -> Notification:
    # Distinct recipient + subject per index => distinct dedup_hash => every
    # send inserts a fresh key (drives the size-mutate insert path), and the
    # tiny dedup window means earlier keys expire and get deleted concurrently.
    return Notification(
        notification_id="n-%d" % index,
        channel=NotificationChannel.WEBHOOK,
        recipient="user-%d@example.test" % index,
        subject="subject-%d" % index,
        body="body",
        priority=NotificationPriority.NORMAL,
    )


def test_concurrent_send_does_not_corrupt_dedup_cache():
    # Sub-millisecond window so _clean_dedup_cache hits the del path on almost
    # every send while other threads insert new keys.
    dispatcher = NotificationDispatcher(dedup_window_seconds=0.0001)
    dispatcher.register_channel(NotificationChannel.WEBHOOK, lambda n: True)

    errors: list[BaseException] = []
    start = threading.Event()
    sends_per_thread = 400
    thread_count = 8

    def worker(worker_id: int) -> None:
        start.wait()
        try:
            for i in range(sends_per_thread):
                dispatcher.send(_make_notification(worker_id * sends_per_thread + i))
        except BaseException as exc:  # noqa: BLE001 - we want to catch ANY escape
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(w,)) for w in range(thread_count)
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, "send() raised under concurrency: %r" % (errors[:3],)


def test_single_threaded_send_sanity():
    dispatcher = NotificationDispatcher(dedup_window_seconds=60.0)
    dispatcher.register_channel(NotificationChannel.WEBHOOK, lambda n: True)

    first = dispatcher.send(_make_notification(1))
    assert first.delivered is True

    # Same recipient+subject within the window => suppressed.
    duplicate = Notification(
        notification_id="n-dup",
        channel=NotificationChannel.WEBHOOK,
        recipient="user-1@example.test",
        subject="subject-1",
        body="other body",
        priority=NotificationPriority.NORMAL,
    )
    second = dispatcher.send(duplicate)
    assert second.delivered is False
    assert "Deduplicated" in second.error
