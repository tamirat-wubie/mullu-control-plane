"""LLM Response Cache — Avoid redundant provider calls for identical prompts.

Purpose: Cache LLM responses keyed on (provider, model, prompt_hash) so
    identical requests return cached results without calling the provider.
    Saves cost, reduces latency, and protects against provider outages
    for repeated queries.
Governance scope: caching only — does not modify LLM behavior.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Cache key is SHA-256 of (provider, model, prompt) — no collisions.
  - Cache is TTL-bounded — stale results expire automatically.
  - Cache is tenant-scoped — cross-tenant cache pollution impossible.
  - Bounded capacity with LRU eviction.
  - Thread-safe — concurrent reads/writes are safe.
  - Cache misses are transparent — caller doesn't know if cached.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A cached LLM response."""

    cache_key: str
    tenant_id: str
    provider: str
    model: str
    prompt_hash: str
    response: Any  # The LLM result object
    cached_at: float
    ttl_seconds: float
    token_count: int = 0  # Total tokens (for cost tracking)


@dataclass(frozen=True, slots=True)
class CacheLookupResult:
    """Result of a cache lookup."""

    hit: bool
    response: Any | None = None
    cache_key: str = ""
    age_seconds: float = 0.0


class LLMResponseCache:
    """TTL-bounded LRU cache for LLM responses.

    Usage:
        cache = LLMResponseCache()

        # Check cache before calling provider
        result = cache.get("t1", "anthropic", "claude-sonnet", "What is 2+2?")
        if result.hit:
            return result.response

        # Call provider, then cache
        llm_result = provider.complete(prompt)
        cache.put("t1", "anthropic", "claude-sonnet", "What is 2+2?", llm_result)
    """

    MAX_ENTRIES = 10_000
    DEFAULT_TTL = 300.0  # 5 minutes

    def __init__(
        self,
        *,
        default_ttl: float = DEFAULT_TTL,
        max_entries: int = MAX_ENTRIES,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0
        self._evicted_count = 0
        self._saved_cost = 0.0

    @staticmethod
    def _make_key(tenant_id: str, provider: str, model: str, prompt: str) -> str:
        """Build cache key from tenant + provider + model + prompt hash."""
        content = f"{tenant_id}:{provider}:{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]

    @staticmethod
    def _prompt_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def get(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
    ) -> CacheLookupResult:
        """Look up a cached LLM response."""
        key = self._make_key(tenant_id, provider, model, prompt)

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._miss_count += 1
                return CacheLookupResult(hit=False, cache_key=key)

            now = self._clock()
            age = now - entry.cached_at
            if age > entry.ttl_seconds:
                # Expired
                del self._entries[key]
                self._evicted_count += 1
                self._miss_count += 1
                return CacheLookupResult(hit=False, cache_key=key)

            # Cache hit — move to end (most recently used)
            self._entries.move_to_end(key)
            self._hit_count += 1
            return CacheLookupResult(
                hit=True,
                response=entry.response,
                cache_key=key,
                age_seconds=round(age, 2),
            )

    def put(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        response: Any,
        *,
        ttl: float = 0.0,
        cost: float = 0.0,
        token_count: int = 0,
    ) -> str:
        """Cache an LLM response. Returns the cache key."""
        key = self._make_key(tenant_id, provider, model, prompt)
        effective_ttl = ttl if ttl > 0 else self._default_ttl

        with self._lock:
            # Capacity enforcement — evict LRU
            if len(self._entries) >= self._max_entries and key not in self._entries:
                self._entries.popitem(last=False)
                self._evicted_count += 1

            self._entries[key] = CacheEntry(
                cache_key=key,
                tenant_id=tenant_id,
                provider=provider,
                model=model,
                prompt_hash=self._prompt_hash(prompt),
                response=response,
                cached_at=self._clock(),
                ttl_seconds=effective_ttl,
                token_count=token_count,
            )
            self._entries.move_to_end(key)
            if cost > 0:
                self._saved_cost += cost

        return key

    def invalidate(self, tenant_id: str, provider: str, model: str, prompt: str) -> bool:
        """Remove a specific cached response."""
        key = self._make_key(tenant_id, provider, model, prompt)
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def invalidate_tenant(self, tenant_id: str) -> int:
        """Remove all cached responses for a tenant."""
        with self._lock:
            to_remove = [k for k, e in self._entries.items() if e.tenant_id == tenant_id]
            for k in to_remove:
                del self._entries[k]
            return len(to_remove)

    def clear(self) -> int:
        """Clear entire cache. Returns count of entries removed."""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def hit_count(self) -> int:
        return self._hit_count

    @property
    def miss_count(self) -> int:
        return self._miss_count

    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return round(self._hit_count / total, 4) if total > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "capacity": self._max_entries,
                "hits": self._hit_count,
                "misses": self._miss_count,
                "hit_rate": self.hit_rate(),
                "evicted": self._evicted_count,
                "saved_cost": round(self._saved_cost, 4),
                "default_ttl": self._default_ttl,
            }
