"""Gateway Message Deduplication Tests — Idempotent message processing."""

import pytest
from gateway.dedup import (
    DedupEntry,
    DedupResult,
    MessageDeduplicator,
)


# ── Basic dedup ────────────────────────────────────────────────

class TestBasicDedup:
    def test_first_message_is_not_duplicate(self):
        dedup = MessageDeduplicator()
        result = dedup.check("whatsapp", "+1234", "msg-001")
        assert result.is_duplicate is False

    def test_same_message_is_duplicate(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "msg-001", "response-1")
        result = dedup.check("whatsapp", "+1234", "msg-001")
        assert result.is_duplicate is True
        assert result.cached_response == "response-1"

    def test_different_message_id_is_not_duplicate(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "msg-001", "resp-1")
        result = dedup.check("whatsapp", "+1234", "msg-002")
        assert result.is_duplicate is False

    def test_different_channel_is_not_duplicate(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "msg-001", "resp-1")
        result = dedup.check("telegram", "+1234", "msg-001")
        assert result.is_duplicate is False

    def test_different_sender_is_not_duplicate(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "msg-001", "resp-1")
        result = dedup.check("whatsapp", "+5678", "msg-001")
        assert result.is_duplicate is False

    def test_empty_message_id_never_deduped(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "", "resp")
        result = dedup.check("whatsapp", "+1234", "")
        assert result.is_duplicate is False

    def test_record_without_message_id_is_noop(self):
        dedup = MessageDeduplicator()
        dedup.record("whatsapp", "+1234", "", "resp")
        assert dedup.entry_count == 0


# ── TTL expiration ─────────────────────────────────────────────

class TestTTLExpiration:
    def test_expired_entry_not_duplicate(self):
        now = [0.0]
        dedup = MessageDeduplicator(default_ttl=5.0, clock=lambda: now[0])
        dedup.record("slack", "U1", "msg-1", "cached")
        now[0] = 10.0  # Past TTL
        result = dedup.check("slack", "U1", "msg-1")
        assert result.is_duplicate is False

    def test_within_ttl_is_duplicate(self):
        now = [0.0]
        dedup = MessageDeduplicator(default_ttl=10.0, clock=lambda: now[0])
        dedup.record("slack", "U1", "msg-1", "cached")
        now[0] = 5.0  # Within TTL
        result = dedup.check("slack", "U1", "msg-1")
        assert result.is_duplicate is True

    def test_custom_ttl_per_record(self):
        now = [0.0]
        dedup = MessageDeduplicator(default_ttl=60.0, clock=lambda: now[0])
        dedup.record("slack", "U1", "msg-1", "short", ttl=2.0)
        now[0] = 3.0  # Past custom TTL
        result = dedup.check("slack", "U1", "msg-1")
        assert result.is_duplicate is False

    def test_expired_entries_reaped(self):
        now = [0.0]
        dedup = MessageDeduplicator(default_ttl=1.0, clock=lambda: now[0])
        dedup.record("slack", "U1", "msg-1", "r1")
        dedup.record("slack", "U1", "msg-2", "r2")
        assert dedup.entry_count == 2
        now[0] = 5.0
        dedup.check("slack", "U1", "msg-3")  # Triggers reap
        assert dedup.entry_count == 0


# ── Capacity and bounding ─────────────────────────────────────

class TestCapacity:
    def test_bounded_entries(self):
        dedup = MessageDeduplicator(max_entries=5)
        for i in range(10):
            dedup.record("ch", "s1", f"msg-{i}", f"resp-{i}")
        assert dedup.entry_count <= 5

    def test_oldest_evicted_first(self):
        now = [0.0]
        dedup = MessageDeduplicator(max_entries=3, clock=lambda: now[0])
        dedup.record("ch", "s1", "msg-0", "r0")
        now[0] = 1.0
        dedup.record("ch", "s1", "msg-1", "r1")
        now[0] = 2.0
        dedup.record("ch", "s1", "msg-2", "r2")
        now[0] = 3.0
        dedup.record("ch", "s1", "msg-3", "r3")  # Evicts msg-0
        # msg-0 should be gone
        result = dedup.check("ch", "s1", "msg-0")
        assert result.is_duplicate is False
        # msg-3 should be present
        result = dedup.check("ch", "s1", "msg-3")
        assert result.is_duplicate is True

    def test_overwrite_same_key(self):
        dedup = MessageDeduplicator()
        dedup.record("ch", "s1", "msg-1", "old-resp")
        dedup.record("ch", "s1", "msg-1", "new-resp")
        result = dedup.check("ch", "s1", "msg-1")
        assert result.cached_response == "new-resp"


# ── Hit/miss tracking ─────────────────────────────────────────

class TestHitTracking:
    def test_hit_and_miss_counts(self):
        dedup = MessageDeduplicator()
        dedup.check("ch", "s1", "msg-1")  # miss
        dedup.record("ch", "s1", "msg-1", "resp")
        dedup.check("ch", "s1", "msg-1")  # hit
        dedup.check("ch", "s1", "msg-2")  # miss
        assert dedup.hit_count == 1
        assert dedup.miss_count == 2

    def test_hit_rate(self):
        dedup = MessageDeduplicator()
        dedup.record("ch", "s1", "msg-1", "resp")
        dedup.check("ch", "s1", "msg-1")  # hit
        dedup.check("ch", "s1", "msg-2")  # miss
        assert dedup.hit_rate() == 0.5

    def test_hit_rate_empty(self):
        dedup = MessageDeduplicator()
        assert dedup.hit_rate() == 0.0

    def test_is_seen_helper(self):
        dedup = MessageDeduplicator()
        dedup.record("ch", "s1", "msg-1", "resp")
        assert dedup.is_seen("ch", "s1", "msg-1") is True
        assert dedup.is_seen("ch", "s1", "msg-2") is False


# ── Status ─────────────────────────────────────────────────────

class TestStatus:
    def test_status_fields(self):
        dedup = MessageDeduplicator(default_ttl=60.0)
        dedup.record("ch", "s1", "msg-1", "resp")
        status = dedup.status()
        assert status["active_entries"] == 1
        assert status["total_hits"] == 0
        assert status["total_misses"] == 0
        assert status["default_ttl"] == 60.0
        assert "capacity" in status


# ── Validation ─────────────────────────────────────────────────

class TestValidation:
    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError, match="default_ttl"):
            MessageDeduplicator(default_ttl=-1.0)

    def test_zero_max_entries_rejected(self):
        with pytest.raises(ValueError, match="max_entries"):
            MessageDeduplicator(max_entries=0)


# ── GatewayRouter integration ─────────────────────────────────

class TestGatewayRouterDedup:
    def _router(self):
        from gateway.router import GatewayRouter, GatewayMessage, TenantMapping

        class StubPlatform:
            def connect(self, *, identity_id, tenant_id, **kw):
                class StubSession:
                    def llm(self, prompt):
                        from dataclasses import dataclass

                        @dataclass
                        class R:
                            succeeded = True
                            content = "42"
                            cost = 0.01
                            model_name = "stub"
                            input_tokens = 10
                            output_tokens = 10
                            error = ""
                        return R()

                    def close(self):
                        pass
                return StubSession()

        router = GatewayRouter(
            platform=StubPlatform(),
            clock=lambda: "2026-04-07T12:00:00Z",
        )
        router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="+1234",
            tenant_id="t1", identity_id="user1",
        ))
        return router

    def test_duplicate_message_returns_cached(self):
        from gateway.router import GatewayMessage
        router = self._router()
        msg = GatewayMessage(
            message_id="msg-001", channel="whatsapp",
            sender_id="+1234", body="What is 2+2?",
        )
        resp1 = router.handle_message(msg)
        resp2 = router.handle_message(msg)
        # Second call should return cached response
        assert resp2.body == resp1.body
        assert router.duplicate_count == 1

    def test_different_messages_not_deduped(self):
        from gateway.router import GatewayMessage
        router = self._router()
        msg1 = GatewayMessage(
            message_id="msg-001", channel="whatsapp",
            sender_id="+1234", body="hello",
        )
        msg2 = GatewayMessage(
            message_id="msg-002", channel="whatsapp",
            sender_id="+1234", body="world",
        )
        router.handle_message(msg1)
        router.handle_message(msg2)
        assert router.duplicate_count == 0

    def test_dedup_in_summary(self):
        from gateway.router import GatewayMessage
        router = self._router()
        msg = GatewayMessage(
            message_id="msg-001", channel="whatsapp",
            sender_id="+1234", body="test",
        )
        router.handle_message(msg)
        router.handle_message(msg)  # Duplicate
        summary = router.summary()
        assert summary["duplicate_count"] == 1
        assert "dedup" in summary
        assert summary["dedup"]["total_hits"] == 1
