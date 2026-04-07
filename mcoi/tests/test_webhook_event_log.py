"""Webhook Event Log Tests."""

import pytest
from gateway.event_log import WebhookEvent, WebhookEventLog


def _log():
    return WebhookEventLog(clock=lambda: "2026-04-07T12:00:00Z")


class TestRecording:
    def test_record_event(self):
        log = _log()
        evt = log.record(channel="wa", sender_id="+1", message_id="m1", body='{"text":"hi"}', status="processed")
        assert evt.event_id == "evt-1"
        assert evt.channel == "wa"
        assert evt.body_hash != ""

    def test_headers_redacted(self):
        log = _log()
        evt = log.record(channel="wa", sender_id="+1", headers={"Authorization": "Bearer secret", "X-Custom": "safe"}, status="processed")
        assert evt.headers["Authorization"] == "[REDACTED]"
        assert evt.headers["X-Custom"] == "safe"

    def test_body_preview_capped(self):
        log = _log()
        long_body = "x" * 500
        evt = log.record(channel="wa", sender_id="+1", body=long_body, status="processed")
        assert len(evt.body_preview) == 200


class TestQuery:
    def test_query_by_channel(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", status="processed")
        log.record(channel="slack", sender_id="U1", status="processed")
        results = log.query(channel="wa")
        assert len(results) == 1

    def test_query_by_status(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", status="processed")
        log.record(channel="wa", sender_id="+2", status="error")
        results = log.query(status="error")
        assert len(results) == 1

    def test_query_by_sender(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", status="processed")
        log.record(channel="wa", sender_id="+2", status="processed")
        results = log.query(sender_id="+1")
        assert len(results) == 1

    def test_query_limit(self):
        log = _log()
        for i in range(10):
            log.record(channel="wa", sender_id=f"+{i}", status="processed")
        assert len(log.query(limit=3)) == 3

    def test_query_most_recent_first(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", message_id="first", status="processed")
        log.record(channel="wa", sender_id="+2", message_id="second", status="processed")
        results = log.query()
        assert results[0].message_id == "second"

    def test_get_by_id(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", status="processed")
        assert log.get("evt-1") is not None
        assert log.get("nonexistent") is None

    def test_find_by_body_hash(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", body="same", status="processed")
        log.record(channel="wa", sender_id="+2", body="same", status="duplicate")
        results = log.find_by_body_hash(log.get("evt-1").body_hash)
        assert len(results) == 2


class TestCapacity:
    def test_bounded(self):
        log = WebhookEventLog(clock=lambda: "now", max_events=5)
        for i in range(10):
            log.record(channel="wa", sender_id=f"+{i}", status="processed")
        assert log.event_count <= 5


class TestSummary:
    def test_summary(self):
        log = _log()
        log.record(channel="wa", sender_id="+1", status="processed")
        log.record(channel="wa", sender_id="+2", status="error")
        s = log.summary()
        assert s["total_events"] == 2
        assert s["by_status"]["processed"] == 1
        assert s["by_status"]["error"] == 1

    def test_to_dict(self):
        log = _log()
        evt = log.record(channel="wa", sender_id="+1", status="processed")
        d = evt.to_dict()
        assert d["channel"] == "wa"
        assert d["status"] == "processed"
