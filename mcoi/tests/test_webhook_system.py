"""Phase 203B — Webhook system tests."""

import pytest
from mcoi_runtime.core.webhook_system import WebhookManager, WebhookSubscription

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestWebhookManager:
    def test_subscribe(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed",),
        )
        mgr.subscribe(sub)
        assert mgr.subscription_count == 1

    def test_duplicate_subscribe_raises(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(subscription_id="sub-1", tenant_id="t1", url="http://x", events=("task.completed",))
        mgr.subscribe(sub)
        with pytest.raises(ValueError):
            mgr.subscribe(sub)

    def test_unsubscribe(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        sub = WebhookSubscription(subscription_id="sub-1", tenant_id="t1", url="http://x", events=("task.completed",))
        mgr.subscribe(sub)
        assert mgr.unsubscribe("sub-1") is True
        assert mgr.subscription_count == 0

    def test_emit_queues_delivery(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="t1")
        assert len(deliveries) == 1
        assert deliveries[0].event == "task.completed"
        assert deliveries[0].status == "queued"

    def test_emit_no_match(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.failed", {"task_id": "t1"}, tenant_id="t1")
        assert len(deliveries) == 0

    def test_emit_tenant_filter(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="t2")
        assert len(deliveries) == 0

    def test_emit_wildcard_tenant(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="*",
            url="http://x", events=("task.completed",),
        ))
        deliveries = mgr.emit("task.completed", {"task_id": "t1"}, tenant_id="any-tenant")
        assert len(deliveries) == 1

    def test_emit_with_secret_signature(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",), secret="my-secret",
        ))
        deliveries = mgr.emit("task.completed", {"data": "test"}, tenant_id="t1")
        assert deliveries[0].signature  # Non-empty HMAC

    def test_disabled_subscription_skipped(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",), enabled=False,
        ))
        deliveries = mgr.emit("task.completed", {}, tenant_id="t1")
        assert len(deliveries) == 0

    def test_delivery_history(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(
            subscription_id="sub-1", tenant_id="t1",
            url="http://x", events=("task.completed",),
        ))
        mgr.emit("task.completed", {}, tenant_id="t1")
        mgr.emit("task.completed", {}, tenant_id="t1")
        history = mgr.delivery_history()
        assert len(history) == 2

    def test_multiple_subscriptions(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        mgr.subscribe(WebhookSubscription(subscription_id="s1", tenant_id="t1", url="http://a", events=("task.completed",)))
        mgr.subscribe(WebhookSubscription(subscription_id="s2", tenant_id="t1", url="http://b", events=("task.completed",)))
        deliveries = mgr.emit("task.completed", {}, tenant_id="t1")
        assert len(deliveries) == 2

    def test_summary(self):
        mgr = WebhookManager(clock=FIXED_CLOCK)
        summary = mgr.summary()
        assert "subscriptions" in summary
        assert "events" in summary
