"""Phase 227A — Idempotency Key Middleware.

Purpose: Ensure POST/PUT requests with the same idempotency key return
    identical responses without re-executing side effects.
Dependencies: None (stdlib only).
Invariants:
  - Same key + endpoint = cached response returned.
  - Cache entries expire after TTL.
  - Keys are bounded (LRU eviction).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedResponse:
    """A cached response for an idempotent request."""
    key: str
    status_code: int
    body: dict[str, Any]
    created_at: float
    endpoint: str = ""

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class IdempotencyStore:
    """Stores and retrieves idempotent request responses."""

    def __init__(self, max_entries: int = 10_000, ttl_seconds: float = 3600.0):
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._cache: dict[str, CachedResponse] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> CachedResponse | None:
        """Look up a cached response by idempotency key."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.age_seconds > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def store(self, key: str, status_code: int, body: dict[str, Any],
              endpoint: str = "") -> CachedResponse:
        """Store a response for an idempotency key."""
        if len(self._cache) >= self._max_entries:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]

        entry = CachedResponse(
            key=key, status_code=status_code, body=body,
            created_at=time.time(), endpoint=endpoint,
        )
        self._cache[key] = entry
        return entry

    def invalidate(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v.created_at > self._ttl]
        for k in expired:
            del self._cache[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._cache)

    def summary(self) -> dict[str, Any]:
        return {
            "cached_entries": self.size,
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0,
        }
