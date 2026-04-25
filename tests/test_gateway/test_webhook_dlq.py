"""Webhook DLQ tests.

Purpose: verify bounded delivery-failure summaries for retry witnesses.
Governance scope: dead-letter queue observability only.
Dependencies: gateway.webhook_dlq.
Invariants:
  - Raw delivery errors are not promoted into operator summary keys.
  - Retry failure and exhaustion reasons use bounded reason codes.
  - Successful retries do not create failure reasons.
"""

from gateway.webhook_dlq import WebhookDLQ, classify_delivery_error


def test_summary_reports_bounded_enqueue_reasons() -> None:
    clock_value = 1.0
    dlq = WebhookDLQ(clock=lambda: clock_value)

    dlq.enqueue(channel="web", recipient_id="user-secret", body="ok", error="connection timeout for user-secret")
    dlq.enqueue(channel="slack", recipient_id="user-secret", body="ok", error="HTTP 429 rate limit")
    summary = dlq.summary()

    assert summary["total_enqueued"] == 2
    assert summary["enqueue_reasons"] == {
        "rate_limited": 1,
        "timeout": 1,
    }
    assert "user-secret" not in summary["enqueue_reasons"]
    assert "connection timeout for user-secret" not in summary["enqueue_reasons"]


def test_retry_exhaustion_reports_bounded_failure_reasons() -> None:
    clock = {"now": 1.0}
    dlq = WebhookDLQ(clock=lambda: clock["now"], max_retries=1)

    dlq.enqueue(channel="web", recipient_id="user-1", body="ok", error="network unavailable")
    clock["now"] = 500.0
    result = dlq.process_retries(send_fn=lambda _channel, _recipient_id, _body: False)
    summary = dlq.summary()

    assert result["processed"] == 1
    assert result["failed"] == 1
    assert result["exhausted"] == 1
    assert summary["total_exhausted"] == 1
    assert summary["retry_failure_reasons"] == {"send_rejected": 1}
    assert summary["exhaustion_reasons"] == {"send_rejected": 1}


def test_successful_retry_does_not_record_failure_reason() -> None:
    clock = {"now": 1.0}
    dlq = WebhookDLQ(clock=lambda: clock["now"], max_retries=1)

    dlq.enqueue(channel="web", recipient_id="user-1", body="ok", error="forbidden")
    clock["now"] = 500.0
    result = dlq.process_retries(send_fn=lambda _channel, _recipient_id, _body: True)
    summary = dlq.summary()

    assert result["processed"] == 1
    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert summary["total_delivered"] == 1
    assert summary["retry_failure_reasons"] == {}
    assert summary["exhaustion_reasons"] == {}


def test_delivery_error_classifier_uses_stable_taxonomy() -> None:
    assert classify_delivery_error("") == "missing_error"
    assert classify_delivery_error("403 forbidden") == "permission_denied"
    assert classify_delivery_error("unknown opaque gateway error with id abc123") == "delivery_failed"
