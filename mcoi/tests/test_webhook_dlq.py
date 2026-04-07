"""Webhook Dead-Letter Queue Tests — Retry failed channel sends."""

import pytest
from gateway.webhook_dlq import (
    DLQEntry,
    DLQEntryStatus,
    WebhookDLQ,
)


def _dlq(**kw):
    return WebhookDLQ(clock=kw.pop("clock", lambda: 0.0), **kw)


# ── Enqueue ────────────────────────────────────────────────────

class TestEnqueue:
    def test_enqueue_creates_entry(self):
        dlq = _dlq()
        entry = dlq.enqueue(
            channel="whatsapp", recipient_id="+1234",
            body="Your balance is $100", error="connection timeout",
        )
        assert entry.entry_id == "dlq-1"
        assert entry.channel == "whatsapp"
        assert entry.status == DLQEntryStatus.PENDING
        assert entry.attempt_count == 0
        assert dlq.entry_count == 1

    def test_enqueue_increments_sequence(self):
        dlq = _dlq()
        e1 = dlq.enqueue(channel="wa", recipient_id="+1", body="a", error="err")
        e2 = dlq.enqueue(channel="wa", recipient_id="+2", body="b", error="err")
        assert e1.entry_id == "dlq-1"
        assert e2.entry_id == "dlq-2"

    def test_enqueue_with_metadata(self):
        dlq = _dlq()
        entry = dlq.enqueue(
            channel="slack", recipient_id="U1", body="msg",
            error="rate limited", metadata={"thread_ts": "123"},
        )
        assert entry.metadata["thread_ts"] == "123"

    def test_to_dict(self):
        dlq = _dlq()
        entry = dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        d = entry.to_dict()
        assert d["entry_id"] == "dlq-1"
        assert d["status"] == "pending"
        assert d["channel"] == "wa"


# ── Retry processing ──────────────────────────────────────────

class TestRetryProcessing:
    def test_successful_retry(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0])
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="timeout")
        now[0] = 100.0  # Past retry delay
        result = dlq.process_retries(send_fn=lambda c, r, b: True)
        assert result["delivered"] == 1
        assert result["processed"] == 1

    def test_failed_retry_stays_pending(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0], max_retries=3)
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="timeout")
        now[0] = 100.0
        result = dlq.process_retries(send_fn=lambda c, r, b: False)
        assert result["failed"] == 1
        assert dlq.pending_count == 1

    def test_exhausted_after_max_retries(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0], max_retries=2)
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="timeout")
        # Retry twice
        for _ in range(3):
            now[0] += 1000
            dlq.process_retries(send_fn=lambda c, r, b: False)
        assert dlq.exhausted_count == 1
        assert dlq.pending_count == 0

    def test_retry_not_before_delay(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0])
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        # Don't advance time — retry should not trigger
        result = dlq.process_retries(send_fn=lambda c, r, b: True)
        assert result["processed"] == 0

    def test_batch_size_respected(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0])
        for i in range(10):
            dlq.enqueue(channel="wa", recipient_id=f"+{i}", body="msg", error="err")
        now[0] = 1000.0
        result = dlq.process_retries(send_fn=lambda c, r, b: True, batch_size=3)
        assert result["processed"] == 3

    def test_send_fn_exception_handled(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0])
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        now[0] = 100.0

        def exploding_send(c, r, b):
            raise ConnectionError("network down")

        result = dlq.process_retries(send_fn=exploding_send)
        assert result["failed"] == 1
        entry = dlq.get("dlq-1")
        assert "ConnectionError" in entry.last_error


# ── Manual retry ───────────────────────────────────────────────

class TestManualRetry:
    def test_manual_retry_success(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0], max_retries=1)
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        now[0] = 100.0
        dlq.process_retries(send_fn=lambda c, r, b: False)  # Exhaust
        assert dlq.exhausted_count == 1
        # Manual retry succeeds
        success = dlq.retry_entry("dlq-1", send_fn=lambda c, r, b: True)
        assert success is True
        entry = dlq.get("dlq-1")
        assert entry.status == DLQEntryStatus.DELIVERED

    def test_manual_retry_failure(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0], max_retries=1)
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        now[0] = 100.0
        dlq.process_retries(send_fn=lambda c, r, b: False)
        success = dlq.retry_entry("dlq-1", send_fn=lambda c, r, b: False)
        assert success is False

    def test_manual_retry_nonexistent(self):
        dlq = _dlq()
        assert dlq.retry_entry("nonexistent", send_fn=lambda c, r, b: True) is False


# ── Query ──────────────────────────────────────────────────────

class TestQuery:
    def test_query_all(self):
        dlq = _dlq()
        dlq.enqueue(channel="wa", recipient_id="+1", body="a", error="err")
        dlq.enqueue(channel="slack", recipient_id="U1", body="b", error="err")
        results = dlq.query()
        assert len(results) == 2

    def test_query_by_status(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0], max_retries=1)
        dlq.enqueue(channel="wa", recipient_id="+1", body="a", error="err")
        dlq.enqueue(channel="wa", recipient_id="+2", body="b", error="err")
        now[0] = 100.0
        dlq.process_retries(send_fn=lambda c, r, b: r == "+1")  # +1 succeeds, +2 fails→exhausted
        delivered = dlq.query(status=DLQEntryStatus.DELIVERED)
        assert len(delivered) == 1
        exhausted = dlq.query(status=DLQEntryStatus.EXHAUSTED)
        assert len(exhausted) == 1

    def test_query_by_channel(self):
        dlq = _dlq()
        dlq.enqueue(channel="wa", recipient_id="+1", body="a", error="err")
        dlq.enqueue(channel="slack", recipient_id="U1", body="b", error="err")
        results = dlq.query(channel="wa")
        assert len(results) == 1
        assert results[0].channel == "wa"

    def test_query_limit(self):
        dlq = _dlq()
        for i in range(10):
            dlq.enqueue(channel="wa", recipient_id=f"+{i}", body="msg", error="err")
        results = dlq.query(limit=3)
        assert len(results) == 3

    def test_get_entry(self):
        dlq = _dlq()
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        entry = dlq.get("dlq-1")
        assert entry is not None
        assert entry.channel == "wa"

    def test_get_nonexistent(self):
        dlq = _dlq()
        assert dlq.get("nonexistent") is None


# ── Capacity ───────────────────────────────────────────────────

class TestCapacity:
    def test_bounded(self):
        dlq = _dlq(max_entries=5)
        for i in range(10):
            dlq.enqueue(channel="wa", recipient_id=f"+{i}", body="msg", error="err")
        assert dlq.entry_count <= 5

    def test_purge_delivered(self):
        now = [0.0]
        dlq = WebhookDLQ(clock=lambda: now[0])
        dlq.enqueue(channel="wa", recipient_id="+1", body="a", error="err")
        dlq.enqueue(channel="wa", recipient_id="+2", body="b", error="err")
        now[0] = 100.0
        dlq.process_retries(send_fn=lambda c, r, b: True)
        purged = dlq.purge_delivered()
        assert purged == 2
        assert dlq.entry_count == 0


# ── Summary ────────────────────────────────────────────────────

class TestSummary:
    def test_summary_fields(self):
        dlq = _dlq()
        dlq.enqueue(channel="wa", recipient_id="+1", body="msg", error="err")
        s = dlq.summary()
        assert s["total_entries"] == 1
        assert s["total_enqueued"] == 1
        assert "by_status" in s
        assert s["by_status"]["pending"] == 1


# ── Validation ─────────────────────────────────────────────────

class TestValidation:
    def test_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries"):
            WebhookDLQ(clock=lambda: 0.0, max_retries=-1)
