"""Tests for Phase 223B — Webhook Retry with Exponential Backoff."""
from __future__ import annotations

import pytest

from mcoi_runtime.core.webhook_retry import (
    DeliveryStatus,
    RetryPolicy,
    WebhookDelivery,
    WebhookRetryEngine,
    DeliveryAttempt,
)


class TestRetryPolicy:
    def test_default_values(self):
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay_seconds == 1.0

    def test_frozen(self):
        p = RetryPolicy()
        with pytest.raises(AttributeError):
            p.max_retries = 5  # type: ignore[misc]

    def test_delay_increases_with_attempt(self):
        p = RetryPolicy(base_delay_seconds=1.0, jitter_factor=0.0, max_delay_seconds=100.0)
        d0 = p.delay_for_attempt(0)
        d1 = p.delay_for_attempt(1)
        d2 = p.delay_for_attempt(2)
        assert d0 < d1 < d2

    def test_delay_capped_at_max(self):
        p = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=5.0, jitter_factor=0.0)
        d10 = p.delay_for_attempt(10)
        assert d10 == 5.0


class TestWebhookDelivery:
    def test_initial_state(self):
        d = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        assert d.status == DeliveryStatus.PENDING
        assert d.attempt_count == 0
        assert d.last_attempt is None

    def test_to_dict(self):
        d = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        out = d.to_dict()
        assert out["delivery_id"] == "d1"
        assert out["status"] == "pending"


class TestWebhookRetryEngine:
    def test_successful_delivery(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=3))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={"a": 1})
        result = engine.deliver(delivery, send_fn=lambda url, payload: (True, 200, ""))
        assert result.status == DeliveryStatus.DELIVERED
        assert result.attempt_count == 1

    def test_retry_then_success(self):
        call_count = {"n": 0}
        def flaky_send(url, payload):
            call_count["n"] += 1
            if call_count["n"] < 3:
                return (False, 500, "server error")
            return (True, 200, "")

        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=3))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        result = engine.deliver(delivery, send_fn=flaky_send)
        assert result.status == DeliveryStatus.DELIVERED
        assert result.attempt_count == 3

    def test_all_retries_exhausted(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=2))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        result = engine.deliver(delivery, send_fn=lambda url, payload: (False, 503, "unavailable"))
        assert result.status == DeliveryStatus.DEAD_LETTER
        assert result.attempt_count == 3  # initial + 2 retries
        assert engine.dead_letter_count == 1

    def test_exception_in_send(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=0))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        def explode(url, payload):
            raise ConnectionError("refused")
        result = engine.deliver(delivery, send_fn=explode)
        assert result.status == DeliveryStatus.DEAD_LETTER
        assert "refused" in result.attempts[0].error

    def test_get_delivery(self):
        engine = WebhookRetryEngine()
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        engine.deliver(delivery, send_fn=lambda u, p: (True, 200, ""))
        assert engine.get_delivery("d1") is delivery
        assert engine.get_delivery("nonexistent") is None

    def test_summary(self):
        engine = WebhookRetryEngine()
        delivery = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        engine.deliver(delivery, send_fn=lambda u, p: (True, 200, ""))
        s = engine.summary()
        assert s["total_deliveries"] == 1
        assert s["total_delivered"] == 1
        assert s["total_failed"] == 0

    def test_dead_letters_list(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=0))
        d1 = WebhookDelivery(delivery_id="d1", webhook_url="http://x", event_type="test", payload={})
        engine.deliver(d1, send_fn=lambda u, p: (False, 500, "fail"))
        assert len(engine.dead_letters) == 1
        assert engine.dead_letters[0].delivery_id == "d1"
