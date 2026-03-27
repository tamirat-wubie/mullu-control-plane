"""Tests for Phase 227A — Idempotency Key Middleware."""
from __future__ import annotations
import time
import pytest
from mcoi_runtime.core.idempotency import IdempotencyStore


class TestIdempotencyStore:
    def test_store_and_retrieve(self):
        store = IdempotencyStore()
        store.store("key1", 200, {"result": "ok"})
        entry = store.get("key1")
        assert entry is not None
        assert entry.status_code == 200
        assert entry.body["result"] == "ok"

    def test_miss_returns_none(self):
        store = IdempotencyStore()
        assert store.get("nonexistent") is None

    def test_hit_miss_counters(self):
        store = IdempotencyStore()
        store.store("k1", 200, {})
        store.get("k1")  # hit
        store.get("k2")  # miss
        s = store.summary()
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["hit_rate"] == 0.5

    def test_ttl_expiry(self):
        store = IdempotencyStore(ttl_seconds=0.01)
        store.store("k1", 200, {})
        time.sleep(0.02)
        assert store.get("k1") is None

    def test_eviction_when_full(self):
        store = IdempotencyStore(max_entries=2)
        store.store("k1", 200, {})
        time.sleep(0.01)
        store.store("k2", 200, {})
        store.store("k3", 200, {})
        assert store.size == 2
        # k1 was oldest, should be evicted
        assert store.get("k1") is None

    def test_invalidate(self):
        store = IdempotencyStore()
        store.store("k1", 200, {})
        assert store.invalidate("k1")
        assert store.get("k1") is None
        assert not store.invalidate("nonexistent")

    def test_cleanup_expired(self):
        store = IdempotencyStore(ttl_seconds=0.01)
        store.store("k1", 200, {})
        store.store("k2", 200, {})
        time.sleep(0.02)
        removed = store.cleanup_expired()
        assert removed == 2
        assert store.size == 0

    def test_summary(self):
        store = IdempotencyStore(max_entries=500, ttl_seconds=120.0)
        s = store.summary()
        assert s["max_entries"] == 500
        assert s["ttl_seconds"] == 120.0
        assert s["cached_entries"] == 0
