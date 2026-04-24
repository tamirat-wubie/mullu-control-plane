"""Tests for Phase 225B — Notification Dispatcher."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.notification_dispatcher import (
    Notification, NotificationChannel, NotificationDispatcher,
)


@pytest.fixture
def dispatcher():
    d = NotificationDispatcher(dedup_window_seconds=60.0)
    d.register_channel(NotificationChannel.WEBHOOK, lambda n: True)
    d.register_channel(NotificationChannel.IN_APP, lambda n: True)
    return d


class TestNotification:
    def test_dedup_hash_consistent(self):
        n1 = Notification("id1", NotificationChannel.WEBHOOK, "user@x", "Alert", "body")
        n2 = Notification("id2", NotificationChannel.WEBHOOK, "user@x", "Alert", "different body")
        assert n1.dedup_hash == n2.dedup_hash  # same channel+recipient+subject

    def test_dedup_hash_differs(self):
        n1 = Notification("id1", NotificationChannel.WEBHOOK, "user@x", "Alert A", "body")
        n2 = Notification("id2", NotificationChannel.WEBHOOK, "user@x", "Alert B", "body")
        assert n1.dedup_hash != n2.dedup_hash


class TestNotificationDispatcher:
    def test_send_success(self, dispatcher):
        n = Notification("n1", NotificationChannel.WEBHOOK, "hook-url", "Test", "body")
        record = dispatcher.send(n)
        assert record.delivered

    def test_deduplication(self, dispatcher):
        n1 = Notification("n1", NotificationChannel.WEBHOOK, "hook-url", "Alert", "body1")
        n2 = Notification("n2", NotificationChannel.WEBHOOK, "hook-url", "Alert", "body2")
        r1 = dispatcher.send(n1)
        r2 = dispatcher.send(n2)
        assert r1.delivered
        assert not r2.delivered
        assert "Deduplicated" in r2.error

    def test_no_handler(self, dispatcher):
        n = Notification("n1", NotificationChannel.EMAIL, "user@x", "Test", "body")
        record = dispatcher.send(n)
        assert not record.delivered
        assert "No handler" in record.error

    def test_handler_exception(self):
        d = NotificationDispatcher()
        d.register_channel(NotificationChannel.WEBHOOK, lambda n: (_ for _ in ()).throw(RuntimeError("fail")))
        n = Notification("n1", NotificationChannel.WEBHOOK, "hook-url", "Test", "body")
        record = d.send(n)
        assert not record.delivered
        assert record.error == "notification handler error (RuntimeError)"
        assert "fail" not in record.error

    def test_handler_returns_false(self):
        d = NotificationDispatcher()
        d.register_channel(NotificationChannel.WEBHOOK, lambda n: False)
        n = Notification("n1", NotificationChannel.WEBHOOK, "hook-url", "Test", "body")
        record = d.send(n)
        assert not record.delivered
        assert record.error == "notification handler returned false"
        assert d.summary()["total_failed"] == 1

    def test_different_channels_no_dedup(self, dispatcher):
        n1 = Notification("n1", NotificationChannel.WEBHOOK, "url", "Alert", "body")
        n2 = Notification("n2", NotificationChannel.IN_APP, "url", "Alert", "body")
        r1 = dispatcher.send(n1)
        r2 = dispatcher.send(n2)
        assert r1.delivered
        assert r2.delivered

    def test_summary(self, dispatcher):
        n = Notification("n1", NotificationChannel.WEBHOOK, "url", "Test", "body")
        dispatcher.send(n)
        s = dispatcher.summary()
        assert s["total_sent"] == 1
        assert s["registered_channels"] == 2
