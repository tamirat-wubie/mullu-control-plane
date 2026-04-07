"""LLM Response Cache Tests."""

import pytest
from mcoi_runtime.core.llm_cache import LLMResponseCache, CacheLookupResult


class TestBasicCaching:
    def test_miss_then_hit(self):
        cache = LLMResponseCache()
        r1 = cache.get("t1", "anthropic", "sonnet", "What is 2+2?")
        assert r1.hit is False
        cache.put("t1", "anthropic", "sonnet", "What is 2+2?", "4")
        r2 = cache.get("t1", "anthropic", "sonnet", "What is 2+2?")
        assert r2.hit is True
        assert r2.response == "4"

    def test_different_prompt_is_miss(self):
        cache = LLMResponseCache()
        cache.put("t1", "anthropic", "sonnet", "What is 2+2?", "4")
        r = cache.get("t1", "anthropic", "sonnet", "What is 3+3?")
        assert r.hit is False

    def test_different_model_is_miss(self):
        cache = LLMResponseCache()
        cache.put("t1", "anthropic", "sonnet", "test", "resp")
        r = cache.get("t1", "anthropic", "opus", "test")
        assert r.hit is False

    def test_different_provider_is_miss(self):
        cache = LLMResponseCache()
        cache.put("t1", "anthropic", "sonnet", "test", "resp")
        r = cache.get("t1", "openai", "sonnet", "test")
        assert r.hit is False


class TestTenantIsolation:
    def test_different_tenant_is_miss(self):
        cache = LLMResponseCache()
        cache.put("t1", "anthropic", "sonnet", "test", "t1-response")
        r = cache.get("t2", "anthropic", "sonnet", "test")
        assert r.hit is False

    def test_invalidate_tenant(self):
        cache = LLMResponseCache()
        cache.put("t1", "a", "m", "p1", "r1")
        cache.put("t1", "a", "m", "p2", "r2")
        cache.put("t2", "a", "m", "p1", "r3")
        removed = cache.invalidate_tenant("t1")
        assert removed == 2
        assert cache.entry_count == 1


class TestTTL:
    def test_expired_entry_is_miss(self):
        now = [0.0]
        cache = LLMResponseCache(default_ttl=5.0, clock=lambda: now[0])
        cache.put("t1", "a", "m", "prompt", "resp")
        now[0] = 10.0
        r = cache.get("t1", "a", "m", "prompt")
        assert r.hit is False

    def test_within_ttl_is_hit(self):
        now = [0.0]
        cache = LLMResponseCache(default_ttl=10.0, clock=lambda: now[0])
        cache.put("t1", "a", "m", "prompt", "resp")
        now[0] = 5.0
        r = cache.get("t1", "a", "m", "prompt")
        assert r.hit is True

    def test_custom_ttl(self):
        now = [0.0]
        cache = LLMResponseCache(default_ttl=60.0, clock=lambda: now[0])
        cache.put("t1", "a", "m", "prompt", "resp", ttl=2.0)
        now[0] = 3.0
        r = cache.get("t1", "a", "m", "prompt")
        assert r.hit is False

    def test_age_reported(self):
        now = [0.0]
        cache = LLMResponseCache(clock=lambda: now[0])
        cache.put("t1", "a", "m", "prompt", "resp")
        now[0] = 2.5
        r = cache.get("t1", "a", "m", "prompt")
        assert r.age_seconds == 2.5


class TestCapacity:
    def test_lru_eviction(self):
        cache = LLMResponseCache(max_entries=3)
        cache.put("t1", "a", "m", "p1", "r1")
        cache.put("t1", "a", "m", "p2", "r2")
        cache.put("t1", "a", "m", "p3", "r3")
        cache.put("t1", "a", "m", "p4", "r4")  # Evicts p1
        assert cache.get("t1", "a", "m", "p1").hit is False
        assert cache.get("t1", "a", "m", "p4").hit is True

    def test_bounded(self):
        cache = LLMResponseCache(max_entries=5)
        for i in range(20):
            cache.put("t1", "a", "m", f"p{i}", f"r{i}")
        assert cache.entry_count <= 5


class TestInvalidation:
    def test_invalidate_specific(self):
        cache = LLMResponseCache()
        cache.put("t1", "a", "m", "prompt", "resp")
        assert cache.invalidate("t1", "a", "m", "prompt") is True
        assert cache.get("t1", "a", "m", "prompt").hit is False

    def test_invalidate_nonexistent(self):
        cache = LLMResponseCache()
        assert cache.invalidate("t1", "a", "m", "nope") is False

    def test_clear(self):
        cache = LLMResponseCache()
        cache.put("t1", "a", "m", "p1", "r1")
        cache.put("t1", "a", "m", "p2", "r2")
        removed = cache.clear()
        assert removed == 2
        assert cache.entry_count == 0


class TestHitTracking:
    def test_hit_miss_counts(self):
        cache = LLMResponseCache()
        cache.get("t1", "a", "m", "miss")
        cache.put("t1", "a", "m", "hit", "resp")
        cache.get("t1", "a", "m", "hit")
        assert cache.hit_count == 1
        assert cache.miss_count == 1

    def test_hit_rate(self):
        cache = LLMResponseCache()
        cache.put("t1", "a", "m", "p", "r")
        cache.get("t1", "a", "m", "p")  # hit
        cache.get("t1", "a", "m", "miss")  # miss
        assert cache.hit_rate() == 0.5

    def test_empty_hit_rate(self):
        assert LLMResponseCache().hit_rate() == 0.0

    def test_saved_cost(self):
        cache = LLMResponseCache()
        cache.put("t1", "a", "m", "p", "r", cost=0.05)
        s = cache.summary()
        assert s["saved_cost"] == 0.05


class TestSummary:
    def test_summary_fields(self):
        cache = LLMResponseCache(default_ttl=120.0)
        cache.put("t1", "a", "m", "p", "r")
        s = cache.summary()
        assert s["entries"] == 1
        assert s["default_ttl"] == 120.0
        assert "hits" in s
        assert "misses" in s
        assert "hit_rate" in s


class TestValidation:
    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError):
            LLMResponseCache(default_ttl=-1.0)
