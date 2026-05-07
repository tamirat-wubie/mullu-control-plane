"""v4.29.0 — atomic rate limit enforcement under concurrent writes (audit F11).

Pre-v4.29 the ``RateLimiter`` enforced rate limits via per-process
``TokenBucket`` instances kept in ``self._buckets``. Single-process
atomicity was correct (TokenBucket guards refill+check+decrement
under a ``threading.Lock``). But across replicas/workers, each
process held its own bucket — N replicas effectively multiplied the
configured ``max_tokens`` by N. The ``RateLimitStore`` existed only
as an observability sink (``record_decision``).

v4.29 introduces ``RateLimitStore.try_consume`` — an optional atomic
test-and-consume primitive owned by the storage layer. When a store
overrides it, ``RateLimiter.check`` delegates enforcement to the
store. Detection uses the same MRO override-sentinel as v4.27
``BudgetStore.try_record_spend``: stores signal capability by
overriding the method, nothing more.

  - InMemoryRateLimitStore: ``threading.Lock``-guarded bucket state.
  - PostgresRateLimitStore: not implemented in v4.29 (own PR; needs
    schema columns for ``tokens``/``last_refill`` and an atomic
    ``UPDATE … WHERE tokens >= $1 RETURNING …``).

These tests exercise the in-memory atomic path under thread
concurrency and verify the override-detection dispatch.
"""
from __future__ import annotations

import threading
import time

import pytest

from mcoi_runtime.governance.guards.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitStore,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryRateLimitStore,
)


# ============================================================
# RateLimitStore base class contract
# ============================================================


class TestRateLimitStoreBase:
    def test_base_try_consume_returns_none(self):
        store = RateLimitStore()
        assert store.try_consume("t:e", 1, RateLimitConfig()) is None

    def test_limiter_with_base_store_uses_in_memory_path(self):
        # Base class doesn't override try_consume → limiter falls
        # through to its own TokenBucket. record_decision still fires
        # for observability.
        store = RateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=3, refill_rate=0.001),
            store=store,
        )
        results = [limiter.check("tenant", "/x") for _ in range(5)]
        allowed = [r for r in results if r.allowed]
        denied = [r for r in results if not r.allowed]
        assert len(allowed) == 3
        assert len(denied) == 2


# ============================================================
# InMemoryRateLimitStore.try_consume semantics
# ============================================================


class TestInMemoryStoreTryConsume:
    def test_first_call_initializes_full_bucket(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.001)
        allowed, remaining = store.try_consume("k", 1, cfg)
        assert allowed is True
        assert 8.99 <= remaining <= 9.01

    def test_exhaust_then_deny(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=3, refill_rate=0.001)
        for _ in range(3):
            allowed, _ = store.try_consume("k", 1, cfg)
            assert allowed is True
        allowed, remaining = store.try_consume("k", 1, cfg)
        assert allowed is False
        assert remaining < 1.0

    def test_burst_limit_rejects(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=100, burst_limit=5)
        allowed, _ = store.try_consume("k", 10, cfg)
        assert allowed is False

    def test_independent_keys(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=2, refill_rate=0.001)
        store.try_consume("a", 1, cfg)
        store.try_consume("a", 1, cfg)
        allowed_a, _ = store.try_consume("a", 1, cfg)
        allowed_b, _ = store.try_consume("b", 1, cfg)
        assert allowed_a is False
        assert allowed_b is True

    def test_refill_over_time(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=2, refill_rate=100.0)  # fast refill
        store.try_consume("k", 2, cfg)  # drain
        allowed, _ = store.try_consume("k", 1, cfg)
        # Right after drain, no refill yet.
        assert allowed is False
        time.sleep(0.05)  # 5 tokens of refill capacity, capped at 2
        allowed, _ = store.try_consume("k", 1, cfg)
        assert allowed is True


# ============================================================
# Concurrency — the F11 fix in action
# ============================================================


class TestConcurrentEnforcement:
    def test_100_threads_against_10_token_budget(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=10, refill_rate=0.0001)
        results: list[bool] = []
        results_lock = threading.Lock()

        def worker():
            allowed, _ = store.try_consume("k", 1, cfg)
            with results_lock:
                results.append(allowed)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for r in results if r)
        denied_count = sum(1 for r in results if not r)
        # The bucket starts at max_tokens=10. With refill_rate=0.0001
        # tokens/sec, the test window adds < 0.001 tokens — negligible.
        # Exactly 10 succeed.
        assert allowed_count == 10
        assert denied_count == 90

    def test_two_keys_independent_under_contention(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=5, refill_rate=0.0001)
        results: dict[str, list[bool]] = {"a": [], "b": []}
        lock = threading.Lock()

        def worker(key: str):
            allowed, _ = store.try_consume(key, 1, cfg)
            with lock:
                results[key].append(allowed)

        threads = (
            [threading.Thread(target=worker, args=("a",)) for _ in range(20)]
            + [threading.Thread(target=worker, args=("b",)) for _ in range(20)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results["a"]) == 5
        assert sum(results["b"]) == 5

    def test_pre_exhausted_all_concurrent_attempts_fail(self):
        store = InMemoryRateLimitStore()
        cfg = RateLimitConfig(max_tokens=3, refill_rate=0.0001)
        for _ in range(3):
            store.try_consume("k", 1, cfg)
        # Bucket drained.
        results: list[bool] = []
        lock = threading.Lock()

        def worker():
            allowed, _ = store.try_consume("k", 1, cfg)
            with lock:
                results.append(allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not any(results)

    def test_limiter_concurrent_through_check(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=10, refill_rate=0.0001),
            store=store,
        )
        results: list[bool] = []
        lock = threading.Lock()

        def worker():
            r = limiter.check("tenant-1", "/api/v1/x")
            with lock:
                results.append(r.allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly 10 succeed when the store owns the bucket.
        assert sum(results) == 10


# ============================================================
# RateLimiter dispatch — atomic store path vs in-memory fallback
# ============================================================


class TestRateLimiterDispatch:
    def test_uses_store_when_overridden(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        # First two allowed, third denied — enforced by the store.
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is False
        # Limiter's own _buckets should be empty: enforcement is store-owned.
        assert "t:/x" not in limiter._buckets

    def test_falls_through_when_store_does_not_override(self):
        # A custom store that only implements record_decision.
        class CounterOnlyStore(RateLimitStore):
            def __init__(self):
                self.allowed = 0
                self.denied = 0

            def record_decision(self, key, allowed):
                if allowed:
                    self.allowed += 1
                else:
                    self.denied += 1

        store = CounterOnlyStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
            store=store,
        )
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is False
        # Limiter falls through to in-memory bucket.
        assert "t:/x" in limiter._buckets
        assert store.allowed == 2
        assert store.denied == 1

    def test_no_store_uses_in_memory_path(self):
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=2, refill_rate=0.0001),
        )
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is True
        assert limiter.check("t", "/x").allowed is False


# ============================================================
# Backward compatibility
# ============================================================


class TestBackwardCompat:
    def test_existing_inmemory_record_decision_still_works(self):
        store = InMemoryRateLimitStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=5, refill_rate=0.0001),
            store=store,
        )
        for _ in range(7):
            limiter.check("t", "/x")
        counters = store.get_counters()
        assert counters["allowed"] == 5
        assert counters["denied"] == 2

    def test_legacy_subclass_without_try_consume_falls_through(self):
        class LegacyStore(RateLimitStore):
            # Deliberately does not override try_consume.
            pass

        store = LegacyStore()
        limiter = RateLimiter(
            default_config=RateLimitConfig(max_tokens=3, refill_rate=0.0001),
            store=store,
        )
        results = [limiter.check("t", "/x").allowed for _ in range(5)]
        assert results == [True, True, True, False, False]
