"""Per-Identity Rate Limiting Tests — Dual-gate enforcement.

Verifies that per-identity rate limits prevent a single user from
exhausting a shared tenant quota, while tenant-level limits still
apply as the outer gate.
"""

import pytest
from mcoi_runtime.core.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
)


# ── Dual-gate enforcement ──────────────────────────────────────

class TestIdentityRateLimiting:
    def _limiter(
        self,
        tenant_tokens: int = 10,
        identity_tokens: int = 3,
        refill: float = 0.001,
    ) -> RateLimiter:
        return RateLimiter(
            default_config=RateLimitConfig(max_tokens=tenant_tokens, refill_rate=refill),
            identity_config=RateLimitConfig(max_tokens=identity_tokens, refill_rate=refill),
        )

    def test_identity_allowed_within_quota(self):
        limiter = self._limiter()
        result = limiter.check("t1", "/api", identity_id="user1")
        assert result.allowed is True

    def test_identity_denied_when_exhausted(self):
        limiter = self._limiter(identity_tokens=2)
        limiter.check("t1", "/api", identity_id="user1")
        limiter.check("t1", "/api", identity_id="user1")
        result = limiter.check("t1", "/api", identity_id="user1")
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_identity_isolation_within_tenant(self):
        """Two identities in the same tenant have independent buckets."""
        limiter = self._limiter(identity_tokens=2)
        # Exhaust user1
        limiter.check("t1", "/api", identity_id="user1")
        limiter.check("t1", "/api", identity_id="user1")
        result_u1 = limiter.check("t1", "/api", identity_id="user1")
        assert result_u1.allowed is False
        # user2 still has quota
        result_u2 = limiter.check("t1", "/api", identity_id="user2")
        assert result_u2.allowed is True

    def test_tenant_limit_still_enforced(self):
        """Even with per-identity headroom, tenant-level exhaustion blocks."""
        limiter = self._limiter(tenant_tokens=3, identity_tokens=10)
        # All three use different identities, but tenant quota is 3
        limiter.check("t1", "/api", identity_id="a")
        limiter.check("t1", "/api", identity_id="b")
        limiter.check("t1", "/api", identity_id="c")
        result = limiter.check("t1", "/api", identity_id="d")
        assert result.allowed is False

    def test_no_identity_id_skips_identity_check(self):
        """Without identity_id, only tenant-level is enforced."""
        limiter = self._limiter(tenant_tokens=5, identity_tokens=1)
        # No identity — should use tenant bucket only
        for _ in range(4):
            result = limiter.check("t1", "/api")
            assert result.allowed is True

    def test_identity_denied_count_tracked(self):
        limiter = self._limiter(identity_tokens=1)
        limiter.check("t1", "/api", identity_id="user1")
        limiter.check("t1", "/api", identity_id="user1")  # denied by identity
        assert limiter.identity_denied_count == 1
        assert limiter.denied_count == 1  # total denied also incremented

    def test_cross_tenant_identity_isolation(self):
        """Same identity_id in different tenants has separate buckets."""
        limiter = self._limiter(identity_tokens=1)
        limiter.check("t1", "/api", identity_id="shared-user")
        result_t1 = limiter.check("t1", "/api", identity_id="shared-user")
        assert result_t1.allowed is False
        result_t2 = limiter.check("t2", "/api", identity_id="shared-user")
        assert result_t2.allowed is True

    def test_per_endpoint_identity_config(self):
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.001),
        )
        limiter.configure_endpoint(
            "/api/expensive",
            RateLimitConfig(max_tokens=100, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.001),
        )
        # /api/expensive has per-identity limit of 2
        limiter.check("t1", "/api/expensive", identity_id="u1")
        limiter.check("t1", "/api/expensive", identity_id="u1")
        result = limiter.check("t1", "/api/expensive", identity_id="u1")
        assert result.allowed is False
        # /api/other has no per-identity config — no identity gating
        for _ in range(10):
            r = limiter.check("t1", "/api/other", identity_id="u1")
            assert r.allowed is True

    def test_remaining_shows_identity_bucket(self):
        """When identity-limited, remaining reflects identity bucket."""
        limiter = self._limiter(tenant_tokens=100, identity_tokens=3)
        limiter.check("t1", "/api", identity_id="u1")
        result = limiter.check("t1", "/api", identity_id="u1")
        assert result.remaining_tokens <= 1  # Started with 3, consumed 2

    def test_status_reflects_identity_config(self):
        limiter = self._limiter()
        status = limiter.status()
        assert status["identity_limiting_enabled"] is True
        # Without identity config
        plain = RateLimiter()
        assert plain.status()["identity_limiting_enabled"] is False

    def test_identity_denied_shows_in_status(self):
        limiter = self._limiter(identity_tokens=1)
        limiter.check("t1", "/api", identity_id="u1")
        limiter.check("t1", "/api", identity_id="u1")  # denied
        status = limiter.status()
        assert status["identity_denied"] == 1

    def test_bucket_eviction_with_identity_buckets(self):
        """Identity buckets are evicted via LRU just like tenant buckets."""
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=5, refill_rate=0.001),
            max_buckets=10,
        )
        # Create many identity buckets — should not crash
        for i in range(20):
            limiter.check("t1", "/api", identity_id=f"user-{i}")
        assert limiter.status()["active_buckets"] <= 10

    def test_empty_identity_id_treated_as_no_identity(self):
        """Empty string identity_id means no per-identity check."""
        limiter = self._limiter(tenant_tokens=5, identity_tokens=1)
        # Empty identity — should not use identity bucket
        limiter.check("t1", "/api", identity_id="")
        result = limiter.check("t1", "/api", identity_id="")
        assert result.allowed is True  # Tenant still has quota


# ── Guard integration ──────────────────────────────────────────

class TestRateLimitGuardWithIdentity:
    def test_guard_passes_identity_from_context(self):
        from mcoi_runtime.core.governance_guard import create_rate_limit_guard
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=1, refill_rate=0.001),
        )
        guard = create_rate_limit_guard(limiter)
        ctx = {
            "tenant_id": "t1",
            "endpoint": "/api",
            "authenticated_subject": "user1",
        }
        # First call allowed
        r1 = guard.check(ctx)
        assert r1.allowed is True
        # Second call denied (identity exhausted)
        r2 = guard.check(ctx)
        assert r2.allowed is False

    def test_guard_uses_api_key_id_as_fallback(self):
        from mcoi_runtime.core.governance_guard import create_rate_limit_guard
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=1, refill_rate=0.001),
        )
        guard = create_rate_limit_guard(limiter)
        ctx = {
            "tenant_id": "t1",
            "endpoint": "/api",
            "authenticated_key_id": "key-abc",
        }
        r1 = guard.check(ctx)
        assert r1.allowed is True
        r2 = guard.check(ctx)
        assert r2.allowed is False

    def test_guard_no_identity_uses_tenant_only(self):
        from mcoi_runtime.core.governance_guard import create_rate_limit_guard
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=1, refill_rate=0.001),
        )
        guard = create_rate_limit_guard(limiter)
        ctx = {"tenant_id": "t1", "endpoint": "/api"}
        # No identity — should only use tenant bucket (2 tokens)
        r1 = guard.check(ctx)
        assert r1.allowed is True
        r2 = guard.check(ctx)
        assert r2.allowed is True
        r3 = guard.check(ctx)
        assert r3.allowed is False  # Tenant exhausted


# ── Backward compatibility ─────────────────────────────────────

class TestBackwardCompatibility:
    def test_existing_api_unchanged(self):
        """Existing callers without identity_id still work."""
        limiter = RateLimiter(default_config=RateLimitConfig(max_tokens=5, refill_rate=0.001))
        result = limiter.check("t1", "/api")
        assert result.allowed is True
        assert isinstance(result, RateLimitResult)

    def test_no_identity_config_means_no_identity_gating(self):
        """Without identity_config, identity_id parameter is ignored."""
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=5, refill_rate=0.001),
        )
        # Pass identity_id but no identity_config — should be ignored
        for _ in range(4):
            r = limiter.check("t1", "/api", identity_id="user1")
            assert r.allowed is True

    def test_configure_endpoint_without_identity(self):
        """configure_endpoint still works without identity_config."""
        limiter = RateLimiter()
        limiter.configure_endpoint("/api", RateLimitConfig(max_tokens=5))
        result = limiter.check("t1", "/api")
        assert result.allowed is True

    def test_store_integration_unchanged(self):
        """Store receives decisions for both tenant and identity checks."""
        decisions: list[tuple[str, bool]] = []

        class TestStore:
            def record_decision(self, bucket_key: str, allowed: bool) -> None:
                decisions.append((bucket_key, allowed))
            def get_counters(self) -> dict[str, int]:
                return {"allowed": sum(1 for _, a in decisions if a),
                        "denied": sum(1 for _, a in decisions if not a)}

        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=5, refill_rate=0.001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.001),
            store=TestStore(),
        )
        limiter.check("t1", "/api", identity_id="u1")
        assert len(decisions) == 1  # Store records tenant-level decision
        assert decisions[0][1] is True
