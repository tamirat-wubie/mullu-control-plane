"""Phase 202C — Rate limiter tests."""

import pytest
from mcoi_runtime.governance.guards.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    TokenBucket,
)


class TestTokenBucket:
    def test_initial_full(self):
        bucket = TokenBucket(RateLimitConfig(max_tokens=10))
        assert bucket.remaining >= 9.0  # Allow for tiny time delta

    def test_consume(self):
        bucket = TokenBucket(RateLimitConfig(max_tokens=10, refill_rate=0.001))
        allowed, remaining = bucket.try_consume(1)
        assert allowed is True
        assert remaining < 10.0

    def test_exhaust(self):
        bucket = TokenBucket(RateLimitConfig(max_tokens=3, refill_rate=0.001))
        bucket.try_consume(1)
        bucket.try_consume(1)
        bucket.try_consume(1)
        allowed, _ = bucket.try_consume(1)
        assert allowed is False

    def test_burst_limit(self):
        bucket = TokenBucket(RateLimitConfig(max_tokens=100, burst_limit=5))
        allowed, _ = bucket.try_consume(10)  # Exceeds burst limit
        assert allowed is False


class TestRateLimiter:
    def test_allow(self):
        limiter = RateLimiter(default_config=RateLimitConfig(max_tokens=10, refill_rate=0.001))
        result = limiter.check("tenant-1", "/api/v1/complete")
        assert result.allowed is True
        assert result.tenant_id == "tenant-1"

    def test_deny_after_exhaustion(self):
        config = RateLimitConfig(max_tokens=2, refill_rate=0.001)
        limiter = RateLimiter(default_config=config)
        limiter.check("t1", "/api")
        limiter.check("t1", "/api")
        result = limiter.check("t1", "/api")
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_tenant_isolation(self):
        config = RateLimitConfig(max_tokens=2, refill_rate=0.001)
        limiter = RateLimiter(default_config=config)
        limiter.check("t1", "/api")
        limiter.check("t1", "/api")
        # t1 exhausted, t2 should still be fine
        result = limiter.check("t2", "/api")
        assert result.allowed is True

    def test_endpoint_isolation(self):
        config = RateLimitConfig(max_tokens=1, refill_rate=0.001)
        limiter = RateLimiter(default_config=config)
        limiter.check("t1", "/api/a")
        result = limiter.check("t1", "/api/b")  # Different endpoint
        assert result.allowed is True

    def test_per_endpoint_config(self):
        limiter = RateLimiter()
        limiter.configure_endpoint("/api/fast", RateLimitConfig(max_tokens=100))
        limiter.configure_endpoint("/api/slow", RateLimitConfig(max_tokens=2, refill_rate=0.001))
        # Fast endpoint allows many
        for _ in range(50):
            limiter.check("t1", "/api/fast")
        # Slow endpoint exhausts quickly
        limiter.check("t1", "/api/slow")
        limiter.check("t1", "/api/slow")
        result = limiter.check("t1", "/api/slow")
        assert result.allowed is False

    def test_counts(self):
        config = RateLimitConfig(max_tokens=1, refill_rate=0.001)
        limiter = RateLimiter(default_config=config)
        limiter.check("t1", "/api")  # allowed
        limiter.check("t1", "/api")  # denied
        assert limiter.allowed_count == 1
        assert limiter.denied_count == 1

    def test_status(self):
        limiter = RateLimiter()
        limiter.configure_endpoint("/api/complete", RateLimitConfig())
        limiter.check("t1", "/api/complete")
        status = limiter.status()
        assert status["total_allowed"] == 1
        assert status["active_buckets"] == 1
        assert "/api/complete" in status["configured_endpoints"]
