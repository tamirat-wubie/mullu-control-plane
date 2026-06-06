"""Tests for Phase 223B — Webhook Retry with Exponential Backoff."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.agent import router as agent_router
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.webhook_retry import (
    DeliveryStatus,
    RetryPolicy,
    WebhookDelivery,
    WebhookRetryEngine,
)


PUBLIC_WEBHOOK_URL = "https://93.184.216.34/hook"


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
        d = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        assert d.status == DeliveryStatus.PENDING
        assert d.attempt_count == 0
        assert d.last_attempt is None

    def test_to_dict(self):
        raw_url = "https://example.com/hook?token=secret-token"
        d = WebhookDelivery(delivery_id="d1", webhook_url=raw_url, event_type="test", payload={})
        out = d.to_dict()
        assert out["delivery_id"] == "d1"
        assert out["status"] == "pending"
        assert out["webhook_url_redacted"] is True
        assert len(out["webhook_url_hash"]) == 64
        assert "webhook_url" not in out
        assert raw_url not in str(out)
        assert "secret-token" not in str(out)


class TestWebhookRetryEngine:
    def test_successful_delivery(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=3))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={"a": 1})
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
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        result = engine.deliver(delivery, send_fn=flaky_send)
        assert result.status == DeliveryStatus.DELIVERED
        assert result.attempt_count == 3

    def test_all_retries_exhausted(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=2))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        result = engine.deliver(delivery, send_fn=lambda url, payload: (False, 503, "unavailable"))
        assert result.status == DeliveryStatus.DEAD_LETTER
        assert result.attempt_count == 3  # initial + 2 retries
        assert engine.dead_letter_count == 1

    def test_exception_in_send(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=0))
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        def explode(url, payload):
            raise ConnectionError("refused")
        result = engine.deliver(delivery, send_fn=explode)
        assert result.status == DeliveryStatus.DEAD_LETTER
        assert result.attempts[0].error == "delivery error (ConnectionError)"

    def test_get_delivery(self):
        engine = WebhookRetryEngine()
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        engine.deliver(delivery, send_fn=lambda u, p: (True, 200, ""))
        assert engine.get_delivery("d1") is delivery
        assert engine.get_delivery("nonexistent") is None

    def test_summary(self):
        engine = WebhookRetryEngine()
        delivery = WebhookDelivery(delivery_id="d1", webhook_url=PUBLIC_WEBHOOK_URL, event_type="test", payload={})
        engine.deliver(delivery, send_fn=lambda u, p: (True, 200, ""))
        s = engine.summary()
        assert s["total_deliveries"] == 1
        assert s["total_delivered"] == 1
        assert s["total_failed"] == 0

    def test_dead_letters_list(self):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=0))
        raw_url = "https://93.184.216.34/hook?token=secret-token"
        d1 = WebhookDelivery(delivery_id="d1", webhook_url=raw_url, event_type="test", payload={})
        engine.deliver(d1, send_fn=lambda u, p: (False, 500, "fail"))
        dead_letter_view = engine.dead_letters[0].to_dict()
        assert len(engine.dead_letters) == 1
        assert engine.dead_letters[0].delivery_id == "d1"
        assert dead_letter_view["webhook_url_redacted"] is True
        assert "webhook_url" not in dead_letter_view
        assert raw_url not in str(dead_letter_view)
        assert "secret-token" not in str(dead_letter_view)

    @pytest.mark.parametrize(("url", "error"), [
        ("ftp://example.com/hook", "delivery blocked (invalid URL)"),
        ("http://169.254.169.254/latest/meta-data/", "delivery blocked (private/internal URL)"),
    ])
    def test_delivery_url_policy_blocks_before_send(self, url, error):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=3))
        delivery = WebhookDelivery(
            delivery_id="d-blocked",
            webhook_url=url,
            event_type="test",
            payload={"secret": "payload"},
        )
        calls: list[str] = []

        def send_fn(candidate_url, payload):
            calls.append(candidate_url)
            return True, 200, ""

        result = engine.deliver(delivery, send_fn=send_fn)
        summary = engine.summary()

        assert calls == []
        assert result.status == DeliveryStatus.DEAD_LETTER
        assert result.attempt_count == 1
        assert result.attempts[0].error == error
        assert result.attempts[0].status_code is None
        assert engine.dead_letter_count == 1
        assert engine.dead_letters[0].delivery_id == "d-blocked"
        assert summary["total_delivered"] == 0
        assert summary["total_failed"] == 1

    def test_dead_letter_route_redacts_webhook_url(self, monkeypatch):
        engine = WebhookRetryEngine(policy=RetryPolicy(max_retries=0))
        raw_url = "https://93.184.216.34/hook?token=secret-token"
        delivery = WebhookDelivery(
            delivery_id="d-route",
            webhook_url=raw_url,
            event_type="test",
            payload={"secret": "payload"},
        )
        engine.deliver(delivery, send_fn=lambda _url, _payload: (False, 500, "fail"))
        metrics = type("Metrics", (), {"inc": lambda self, _name: None})()
        monkeypatch.setattr(deps, "webhook_retry", engine)
        monkeypatch.setattr(deps, "metrics", metrics)
        app = FastAPI()
        app.include_router(agent_router)

        response = TestClient(app).get("/api/v1/webhooks/retry/dead-letters")
        body = response.json()

        assert response.status_code == 200
        assert body["count"] == 1
        assert body["dead_letters"][0]["delivery_id"] == "d-route"
        assert body["dead_letters"][0]["webhook_url_redacted"] is True
        assert "webhook_url" not in body["dead_letters"][0]
        assert raw_url not in str(body)
        assert "secret-token" not in str(body)
        assert body["governed"] is True
