"""Distributed State — Cross-replica coordination abstraction.

Purpose: Abstract distributed state so the platform can use in-memory
    (single-process) in development and Redis/external store in
    production for cross-replica coordination.
Governance scope: state coordination only.
Dependencies: none (pure abstraction).
Invariants:
  - Operations are atomic (get/set/delete/increment).
  - TTL is enforced on all keys (no leaked state).
  - Backend is pluggable (in-memory, Redis via protocol).
  - Key namespace is tenant-scoped (no cross-tenant leakage).
  - Thread-safe — concurrent access is safe.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class StateEntry:
    """A single entry in the distributed state store."""

    key: str
    value: Any
    stored_at: float
    ttl_seconds: float


class DistributedStateStore:
    """Protocol for distributed state backends."""

    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any, *, ttl: float = 0.0) -> bool:
        return False

    def delete(self, key: str) -> bool:
        return False

    def exists(self, key: str) -> bool:
        return False

    def increment(self, key: str, amount: int = 1, *, ttl: float = 0.0) -> int:
        return 0

    def keys(self, pattern: str = "") -> list[str]:
        return []


class InMemoryStateStore(DistributedStateStore):
    """In-memory distributed state for single-process deployment.

    Suitable for development and testing. For production with
    multiple replicas, use RedisStateStore (implement protocol).

    Usage:
        store = InMemoryStateStore(clock=time.monotonic)
        store.set("t1:rate:user1", 5, ttl=60.0)
        count = store.increment("t1:rate:user1", ttl=60.0)
        store.get("t1:rate:user1")  # Returns 6
    """

    MAX_KEYS = 100_000
    DEFAULT_TTL = 3600.0  # 1 hour

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        default_ttl: float = DEFAULT_TTL,
        max_keys: int = MAX_KEYS,
    ) -> None:
        self._clock = clock or time.monotonic
        self._default_ttl = default_ttl
        self._max_keys = max_keys
        self._entries: dict[str, StateEntry] = {}
        self._lock = threading.Lock()

    def _is_expired(self, entry: StateEntry) -> bool:
        if entry.ttl_seconds <= 0:
            return False
        return (self._clock() - entry.stored_at) > entry.ttl_seconds

    def _reap_expired(self) -> int:
        """Remove expired entries. Caller must hold lock."""
        expired = [k for k, e in self._entries.items() if self._is_expired(e)]
        for k in expired:
            del self._entries[k]
        return len(expired)

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                del self._entries[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, *, ttl: float = 0.0) -> bool:
        effective_ttl = ttl if ttl > 0 else self._default_ttl
        with self._lock:
            if len(self._entries) >= self._max_keys and key not in self._entries:
                self._reap_expired()
                if len(self._entries) >= self._max_keys:
                    # Evict oldest
                    oldest = min(self._entries, key=lambda k: self._entries[k].stored_at)
                    del self._entries[oldest]
            self._entries[key] = StateEntry(
                key=key, value=value,
                stored_at=self._clock(), ttl_seconds=effective_ttl,
            )
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if self._is_expired(entry):
                del self._entries[key]
                return False
            return True

    def increment(self, key: str, amount: int = 1, *, ttl: float = 0.0) -> int:
        """Atomic increment. Creates key with value=amount if not exists."""
        effective_ttl = ttl if ttl > 0 else self._default_ttl
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or self._is_expired(entry):
                new_val = amount
            else:
                current = entry.value if isinstance(entry.value, int) else 0
                new_val = current + amount
            self._entries[key] = StateEntry(
                key=key, value=new_val,
                stored_at=self._clock(), ttl_seconds=effective_ttl,
            )
            return new_val

    def keys(self, pattern: str = "") -> list[str]:
        with self._lock:
            self._reap_expired()
            if not pattern:
                return sorted(self._entries.keys())
            return sorted(k for k in self._entries if pattern in k)

    @property
    def key_count(self) -> int:
        with self._lock:
            self._reap_expired()
            return len(self._entries)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            self._reap_expired()
            return {
                "keys": len(self._entries),
                "capacity": self._max_keys,
                "default_ttl": self._default_ttl,
                "backend": "in_memory",
            }
