"""Gateway deduplication tests."""

from gateway.dedup import MessageDeduplicator


def test_status_reports_bounded_miss_reasons() -> None:
    dedup = MessageDeduplicator(clock=lambda: 1.0)

    missing_id = dedup.check("web", "sender-secret", "")
    new_message = dedup.check("web", "sender-secret", "message-secret")
    status = dedup.status()

    assert missing_id.is_duplicate is False
    assert new_message.is_duplicate is False
    assert status["total_misses"] == 2
    assert status["miss_reasons"] == {
        "missing_message_id": 1,
        "new_message": 1,
    }
    assert "sender-secret" not in status["miss_reasons"]
    assert "message-secret" not in status["miss_reasons"]


def test_duplicate_hit_does_not_increment_miss_reasons() -> None:
    dedup = MessageDeduplicator(clock=lambda: 1.0)
    response = object()

    initial = dedup.check("web", "sender-1", "message-1")
    dedup.record("web", "sender-1", "message-1", response)
    duplicate = dedup.check("web", "sender-1", "message-1")
    status = dedup.status()

    assert initial.is_duplicate is False
    assert duplicate.is_duplicate is True
    assert duplicate.cached_response is response
    assert status["total_hits"] == 1
    assert status["total_misses"] == 1
    assert status["miss_reasons"] == {"new_message": 1}


def test_ttl_eviction_reports_bounded_reason() -> None:
    clock = {"now": 1.0}
    dedup = MessageDeduplicator(default_ttl=10.0, clock=lambda: clock["now"])

    dedup.record("web", "sender-secret", "message-secret", object())
    clock["now"] = 20.0
    status = dedup.status()

    assert status["active_entries"] == 0
    assert status["total_evicted"] == 1
    assert status["eviction_reasons"] == {"ttl_expired": 1}
    assert "sender-secret" not in status["eviction_reasons"]
    assert "message-secret" not in status["eviction_reasons"]


def test_capacity_eviction_reports_bounded_reason() -> None:
    dedup = MessageDeduplicator(max_entries=1, clock=lambda: 1.0)

    dedup.record("web", "sender-secret-1", "message-secret-1", object())
    dedup.record("web", "sender-secret-2", "message-secret-2", object())
    status = dedup.status()

    assert status["active_entries"] == 1
    assert status["total_evicted"] == 1
    assert status["eviction_reasons"] == {"capacity_pressure": 1}
    assert "sender-secret-1" not in status["eviction_reasons"]
    assert "message-secret-1" not in status["eviction_reasons"]
