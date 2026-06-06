"""Phase 219C — Cache tests."""

import time
import pytest
from mcoi_runtime.core.cache import GovernedCache


class TestGovernedCache:
    def test_set_and_get(self):
        cache = GovernedCache()
        cache.set("k1", "value1")
        assert cache.get("k1") == "value1"

    def test_miss(self):
        cache = GovernedCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = GovernedCache(default_ttl=0.01)
        cache.set("k1", "v1")
        time.sleep(0.02)
        assert cache.get("k1") is None

    def test_delete(self):
        cache = GovernedCache()
        cache.set("k1", "v1")
        assert cache.delete("k1") is True
        assert cache.get("k1") is None

    def test_clear(self):
        cache = GovernedCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_max_size_eviction(self):
        cache = GovernedCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict LRU
        assert cache.size == 3

    @pytest.mark.parametrize("max_size", [0, -1])
    def test_max_size_requires_positive_limit(self, max_size):
        with pytest.raises(ValueError, match="^max_size must be positive$"):
            GovernedCache(max_size=max_size)

    @pytest.mark.parametrize("default_ttl", [0.0, -1.0])
    def test_default_ttl_requires_positive_limit(self, default_ttl):
        with pytest.raises(ValueError, match="^default_ttl must be positive$"):
            GovernedCache(default_ttl=default_ttl)

    def test_max_size_one_preserves_bounded_capacity(self):
        cache = GovernedCache(max_size=1)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size == 1
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_get_or_compute(self):
        cache = GovernedCache()
        calls = {"n": 0}
        def compute():
            calls["n"] += 1
            return 42
        assert cache.get_or_compute("k1", compute) == 42
        assert cache.get_or_compute("k1", compute) == 42  # Cached
        assert calls["n"] == 1  # Only computed once

    def test_hit_rate(self):
        cache = GovernedCache()
        cache.set("k1", "v1")
        cache.get("k1")  # hit
        cache.get("k1")  # hit
        cache.get("miss")  # miss
        assert cache.hit_rate == pytest.approx(2/3, abs=0.01)

    def test_custom_ttl(self):
        cache = GovernedCache(default_ttl=999)
        cache.set("k1", "v1", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("k1") is None

    def test_summary(self):
        cache = GovernedCache(max_size=100)
        cache.set("a", 1)
        s = cache.summary()
        assert s["size"] == 1
        assert s["max_size"] == 100
