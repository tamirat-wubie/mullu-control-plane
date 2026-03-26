"""Phase 219C — Caching Layer.

Purpose: In-memory cache with TTL for expensive operations
    (LLM responses, computed analytics, health checks).
Governance scope: caching only — never modifies source data.
Invariants:
  - Expired entries are never returned.
  - Cache keys are deterministic.
  - Cache misses are explicit (returns None, not stale data).
  - Size is bounded (LRU eviction).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""

    key: str
    value: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) >= self.ttl_seconds


class GovernedCache:
    """TTL-based in-memory cache with LRU eviction."""

    def __init__(self, *, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._entries: dict[str, CacheEntry] = {}
        self._total_hits = 0
        self._total_misses = 0

    def get(self, key: str) -> Any | None:
        """Get a cached value. Returns None if missing or expired."""
        entry = self._entries.get(key)
        if entry is None:
            self._total_misses += 1
            return None
        if entry.expired:
            del self._entries[key]
            self._total_misses += 1
            return None
        entry.hits += 1
        self._total_hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a cache value with optional TTL override."""
        if len(self._entries) >= self._max_size and key not in self._entries:
            self._evict_lru()
        self._entries[key] = CacheEntry(
            key=key, value=value,
            created_at=time.monotonic(),
            ttl_seconds=ttl if ttl is not None else self._default_ttl,
        )

    def delete(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        self._entries.clear()

    def _evict_lru(self) -> None:
        """Evict least recently used (lowest hits) entry."""
        if not self._entries:
            return
        lru_key = min(self._entries, key=lambda k: self._entries[k].hits)
        del self._entries[lru_key]

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl: float | None = None) -> Any:
        """Get cached value or compute and cache it."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute_fn()
        self.set(key, value, ttl=ttl)
        return value

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def hit_rate(self) -> float:
        total = self._total_hits + self._total_misses
        return self._total_hits / total if total > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate": round(self.hit_rate, 4),
        }
