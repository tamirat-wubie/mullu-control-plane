"""v4.34.0 — atomic identity-level rate limit enforcement (audit F11 identity-level).

Pre-v4.34 ``RateLimiter.check`` had a bifurcated dispatch: tenant-level
enforcement was delegated to the store when ``try_consume`` was
overridden (v4.29 / F11 tenant), but **identity-level** enforcement
always used the in-process ``TokenBucket`` from ``self._buckets``.
Cross-replica deployments with per-identity rate limits configured
saw the same multiplier-by-N bug for identity buckets that v4.29
closed for tenant buckets.

v4.34 extends the v4.29 dispatch to identity-level. The same
``store_owned`` flag computed for tenant-level controls identity-
level too — if the store provides an atomic primitive, it provides
one for both bucket levels (the primitive takes a ``bucket_key``,
so the identity bucket key is just a different key).

This is the smallest possible doctrine-compliant change: no new
contract, no new method, no new test infrastructure. Just extend
the dispatch we already proved correct in v4.29 to the identity-
level branch.
"""
from __future__ import annotations

import threading

import pytest

from mcoi_runtime.governance.guards.rate_limit import (
    RateLimitConfig,
    RateLimitStore,
    RateLimiter,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryRateLimitStore,
)


# ============================================================
# Identity-level dispatch through the atomic store
# ============================================================


class TestIdentityDispatch:
    def test_identity_check_delegates_to_store(self):
        """When the store overrides ``try_consume``, the identity-
        level enforcement uses the store, not the limiter's
        in-memory ``_buckets``."""
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        # First two from identity "u1" succeed. Third denied at
        # identity level (tenant has plenty).
        r1 = limiter.check("t1", "/x", identity_id="u1")
        r2 = limiter.check("t1", "/x", identity_id="u1")
        r3 = limiter.check("t1", "/x", identity_id="u1")
        assert r1.allowed is True
        assert r2.allowed is True
        assert r3.allowed is False
        # Limiter's in-memory bucket cache stays empty for both
        # tenant-level AND identity-level keys.
        assert "t1:/x" not in limiter._buckets
        assert "t1:u1:/x" not in limiter._buckets
        assert limiter.identity_denied_count == 1

    def test_identity_check_falls_through_when_store_doesnt_override(self):
        """A custom store that doesn't override ``try_consume``
        leaves identity-level enforcement on the in-process
        TokenBucket (legacy behavior)."""
        class CounterOnlyStore(RateLimitStore):
            def record_decision(self, key, allowed):
                pass

        store = CounterOnlyStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        r1 = limiter.check("t1", "/x", identity_id="u1")
        r2 = limiter.check("t1", "/x", identity_id="u1")
        r3 = limiter.check("t1", "/x", identity_id="u1")
        assert [r1.allowed, r2.allowed, r3.allowed] == [True, True, False]
        # Both bucket types live in limiter._buckets in legacy mode.
        assert "t1:/x" in limiter._buckets
        assert "t1:u1:/x" in limiter._buckets

    def test_identity_check_with_no_store_uses_in_memory(self):
        """No store → both levels use in-memory TokenBucket."""
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
        )
        r1 = limiter.check("t1", "/x", identity_id="u1")
        r2 = limiter.check("t1", "/x", identity_id="u1")
        r3 = limiter.check("t1", "/x", identity_id="u1")
        assert [r1.allowed, r2.allowed, r3.allowed] == [True, True, False]


# ============================================================
# Independence — different identities, different tenants
# ============================================================


class TestIdentityIndependence:
    def test_two_identities_independent_under_store(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        # u1 exhausts; u2 still has full bucket.
        limiter.check("t1", "/x", identity_id="u1")
        limiter.check("t1", "/x", identity_id="u1")
        u1_third = limiter.check("t1", "/x", identity_id="u1")
        u2_first = limiter.check("t1", "/x", identity_id="u2")
        assert u1_third.allowed is False
        assert u2_first.allowed is True

    def test_same_identity_different_tenants_independent(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        # "u1" under tenant t1 exhausts; "u1" under tenant t2 still has full.
        limiter.check("t1", "/x", identity_id="u1")
        limiter.check("t1", "/x", identity_id="u1")
        t1_third = limiter.check("t1", "/x", identity_id="u1")
        t2_first = limiter.check("t2", "/x", identity_id="u1")
        assert t1_third.allowed is False
        assert t2_first.allowed is True


# ============================================================
# Concurrency — identity bucket strictly capped under store
# ============================================================


class TestConcurrentIdentityEnforcement:
    def test_50_threads_one_identity_strict_cap(self):
        """50 concurrent requests for the same identity → exactly
        ``identity_max_tokens`` succeed."""
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=1000, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=5, refill_rate=0.0001),
            store=store,
        )
        results: list[bool] = []
        results_lock = threading.Lock()

        def worker():
            r = limiter.check("t1", "/x", identity_id="u1")
            with results_lock:
                results.append(r.allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # The identity bucket caps at 5 — exactly 5 succeed regardless
        # of OS scheduling. Pre-v4.34 this would fork bucket state
        # across replicas; v4.34 enforces it at the store.
        assert sum(results) == 5

    def test_concurrent_two_identities_independent_caps(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=1000, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=3, refill_rate=0.0001),
            store=store,
        )
        results: dict[str, list[bool]] = {"u1": [], "u2": []}
        lock = threading.Lock()

        def worker(identity: str):
            r = limiter.check("t1", "/x", identity_id=identity)
            with lock:
                results[identity].append(r.allowed)

        threads = (
            [threading.Thread(target=worker, args=("u1",)) for _ in range(20)]
            + [threading.Thread(target=worker, args=("u2",)) for _ in range(20)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each identity caps at 3 independently.
        assert sum(results["u1"]) == 3
        assert sum(results["u2"]) == 3


# ============================================================
# Dual-gate semantics preserved
# ============================================================


class TestDualGate:
    def test_tenant_denial_short_circuits_identity_check(self):
        """If tenant-level denies, identity-level isn't checked —
        so the identity bucket isn't consumed."""
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=10, refill_rate=0.0001),
            store=store,
        )
        # Burn the tenant cap.
        limiter.check("t1", "/x", identity_id="u1")
        limiter.check("t1", "/x", identity_id="u1")
        # Third call: tenant denies, identity bucket should NOT be
        # consumed.
        r = limiter.check("t1", "/x", identity_id="u1")
        assert r.allowed is False
        # Now elevate tenant cap by waiting (no — refill is tiny).
        # Verify identity bucket is intact: drop the tenant store
        # and check identity directly.
        # (Easier: confirm 2 of 10 identity tokens were consumed —
        # one for each successful tenant-allowed call.)
        # This is hard to inspect via public API; instead, drop
        # the tenant config and check identity capacity is what
        # we expect.
        # Verify by directly calling try_consume on the store at
        # the identity key to see remaining tokens.
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001)
        # The two allowed checks above consumed 2 tokens at the
        # identity bucket. Burst-consume 8 more to drain.
        for _ in range(8):
            allowed, _ = store.try_consume("t1:u1:/x", 1, cfg)
            assert allowed is True
        # Bucket should now be empty.
        allowed, _ = store.try_consume("t1:u1:/x", 1, cfg)
        assert allowed is False

    def test_identity_denial_increments_identity_counter(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=1, refill_rate=0.0001),
            store=store,
        )
        limiter.check("t1", "/x", identity_id="u1")  # allowed
        r = limiter.check("t1", "/x", identity_id="u1")  # identity-denied
        assert r.allowed is False
        assert limiter.identity_denied_count == 1


# ============================================================
# Per-endpoint identity config still works through the store
# ============================================================


class TestPerEndpointIdentityConfig:
    def test_per_endpoint_identity_config_uses_store(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            store=store,
        )
        # Tighter identity config for /critical, none for /default.
        limiter.configure_endpoint(
            "/critical",
            RateLimitConfig(max_tokens=100, refill_rate=0.0001),
            identity_config=RateLimitConfig(max_tokens=1, refill_rate=0.0001),
        )
        r1 = limiter.check("t1", "/critical", identity_id="u1")
        r2 = limiter.check("t1", "/critical", identity_id="u1")
        # Default endpoint has no identity config → only tenant-level.
        r3 = limiter.check("t1", "/default", identity_id="u1")
        assert r1.allowed is True
        assert r2.allowed is False  # identity cap of 1 hit
        assert r3.allowed is True   # no identity config on /default
