"""Tests for Phase 223A — Rate Limit Response Headers."""
from __future__ import annotations

import pytest

from mcoi_runtime.core.rate_limit_headers import (
    RateLimitHeaderProvider,
    RateLimitInfo,
)


class TestRateLimitInfo:
    def test_to_headers(self):
        info = RateLimitInfo(limit=60, remaining=45, reset_at=1700000000.0)
        h = info.to_headers()
        assert h["X-RateLimit-Limit"] == "60"
        assert h["X-RateLimit-Remaining"] == "45"
        assert h["X-RateLimit-Reset"] == "1700000000"
        assert "Retry-After" not in h

    def test_exhausted(self):
        info = RateLimitInfo(limit=60, remaining=0, reset_at=1700000000.0, retry_after=30.0)
        assert info.is_exhausted
        h = info.to_headers()
        assert "Retry-After" in h

    def test_remaining_never_negative(self):
        info = RateLimitInfo(limit=10, remaining=-5, reset_at=1700000000.0)
        h = info.to_headers()
        assert h["X-RateLimit-Remaining"] == "0"

    def test_frozen(self):
        info = RateLimitInfo(limit=60, remaining=45, reset_at=1700000000.0)
        with pytest.raises(AttributeError):
            info.limit = 100  # type: ignore[misc]


class TestRateLimitHeaderProvider:
    def test_consume_decrements(self):
        provider = RateLimitHeaderProvider(default_limit=10, window_seconds=60.0)
        info = provider.consume("client-1", tokens=1)
        assert info.limit == 10
        assert info.remaining <= 10

    def test_consume_multiple(self):
        provider = RateLimitHeaderProvider(default_limit=10, window_seconds=60.0)
        info1 = provider.consume("client-1", tokens=3)
        info2 = provider.consume("client-1", tokens=3)
        assert info2.remaining < info1.remaining

    def test_peek_does_not_consume(self):
        provider = RateLimitHeaderProvider(default_limit=10, window_seconds=60.0)
        before = provider.peek("client-1")
        after = provider.peek("client-1")
        assert after.remaining >= before.remaining  # refill may increase

    def test_separate_clients(self):
        provider = RateLimitHeaderProvider(default_limit=10, window_seconds=60.0)
        provider.consume("client-1", tokens=5)
        info2 = provider.consume("client-2", tokens=1)
        assert info2.remaining >= 8  # client-2 is fresh

    def test_tracked_clients(self):
        provider = RateLimitHeaderProvider()
        provider.consume("a")
        provider.consume("b")
        assert provider.tracked_clients == 2

    def test_summary(self):
        provider = RateLimitHeaderProvider(default_limit=100, window_seconds=120.0)
        s = provider.summary()
        assert s["default_limit"] == 100
        assert s["window_seconds"] == 120.0
        assert s["tracked_clients"] == 0

    def test_exhaustion_triggers_retry_after(self):
        provider = RateLimitHeaderProvider(default_limit=2, window_seconds=60.0)
        provider.consume("client-1", tokens=2)
        info = provider.consume("client-1", tokens=1)
        assert info.remaining == 0
        assert info.retry_after is not None
