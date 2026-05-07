"""Coordination Locks — Tenant-scoped resource locking for concurrent agents.

Purpose: Prevent concurrent operations on the same resource within a tenant.
    Critical for financial operations, state mutations, and multi-agent
    coordination where two agents shouldn't modify the same entity.
Governance scope: concurrency control only — no business logic here.
Dependencies: none (pure threading primitives).
Invariants:
  - Locks are tenant-scoped — cross-tenant interference is impossible.
  - Locks have TTL — abandoned locks auto-expire (no deadlocks).
  - Lock acquisition is bounded — callers never wait indefinitely.
  - Lock holders are tracked — audit trail knows who holds what.
  - Bounded capacity — stale locks are reaped under memory pressure.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Generator
from contextlib import contextmanager


@dataclass(frozen=True, slots=True)
class LockInfo:
    """Metadata about a held lock."""

    resource_key: str
    tenant_id: str
    holder_id: str  # session_id or identity_id
    acquired_at: float  # monotonic time
    ttl_seconds: float
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LockResult:
    """Result of a lock acquisition attempt."""

    acquired: bool
    resource_key: str
    holder_id: str
    waited_seconds: float = 0.0
    error: str = ""


class CoordinationLockManager:
    """Tenant-scoped resource locking with TTL and bounded capacity.

    Usage:
        lock_mgr = CoordinationLockManager()

        # Context manager (recommended)
        with lock_mgr.lock("t1", "account:123", holder_id="session-abc"):
            # Exclusive access to account:123 within tenant t1
            do_transfer()

        # Manual acquire/release
        result = lock_mgr.acquire("t1", "order:456", holder_id="agent-1")
        if result.acquired:
            try:
                process_order()
            finally:
                lock_mgr.release("t1", "order:456", holder_id="agent-1")
    """

    MAX_LOCKS = 100_000
    DEFAULT_TTL = 30.0  # seconds
    DEFAULT_TIMEOUT = 5.0  # max wait time for acquisition

    def __init__(
        self,
        *,
        default_ttl: float = DEFAULT_TTL,
        default_timeout: float = DEFAULT_TIMEOUT,
        max_locks: int = MAX_LOCKS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        if default_timeout < 0:
            raise ValueError("default_timeout must be >= 0")
        self._default_ttl = default_ttl
        self._default_timeout = default_timeout
        self._max_locks = max_locks
        self._clock = clock or time.monotonic
        self._locks: dict[str, LockInfo] = {}  # "tenant:resource" -> LockInfo
        self._lock = threading.Lock()  # Protects _locks dict
        self._conditions: dict[str, threading.Condition] = {}
        self._acquired_count = 0
        self._denied_count = 0
        self._expired_count = 0

    def _key(self, tenant_id: str, resource_key: str) -> str:
        return f"{tenant_id}:{resource_key}"

    def _is_expired(self, info: LockInfo) -> bool:
        return (self._clock() - info.acquired_at) > info.ttl_seconds

    def _reap_expired(self) -> int:
        """Remove expired locks. Caller must hold self._lock."""
        expired_keys = [
            k for k, info in self._locks.items() if self._is_expired(info)
        ]
        for k in expired_keys:
            del self._locks[k]
            cond = self._conditions.pop(k, None)
            if cond is not None:
                cond.notify_all()
            self._expired_count += 1
        return len(expired_keys)

    def _get_condition(self, key: str) -> threading.Condition:
        """Get or create a condition variable for a lock key. Caller must hold self._lock."""
        if key not in self._conditions:
            self._conditions[key] = threading.Condition(self._lock)
        return self._conditions[key]

    def acquire(
        self,
        tenant_id: str,
        resource_key: str,
        *,
        holder_id: str,
        ttl: float = 0.0,
        timeout: float = -1.0,
        reason: str = "",
    ) -> LockResult:
        """Attempt to acquire a lock on a tenant-scoped resource.

        Args:
            tenant_id: Tenant scope (cross-tenant locks are impossible).
            resource_key: The resource to lock (e.g., "account:123").
            holder_id: Who is holding (session_id, agent_id, etc.).
            ttl: Lock TTL in seconds (0 = use default).
            timeout: Max wait time (0 = no wait, -1 = use default).
            reason: Optional description for audit trail.

        Returns:
            LockResult with acquired=True on success, False on timeout/conflict.
        """
        effective_ttl = ttl if ttl > 0 else self._default_ttl
        effective_timeout = timeout if timeout >= 0 else self._default_timeout
        key = self._key(tenant_id, resource_key)
        start = self._clock()

        with self._lock:
            self._reap_expired()

            # Fast path: already held by same holder (reentrant)
            existing = self._locks.get(key)
            if existing is not None and existing.holder_id == holder_id and not self._is_expired(existing):
                # Refresh TTL
                self._locks[key] = LockInfo(
                    resource_key=resource_key,
                    tenant_id=tenant_id,
                    holder_id=holder_id,
                    acquired_at=self._clock(),
                    ttl_seconds=effective_ttl,
                    reason=reason or existing.reason,
                )
                return LockResult(acquired=True, resource_key=resource_key, holder_id=holder_id)

            # Try to acquire with timeout
            deadline = start + effective_timeout
            cond = self._get_condition(key)

            while True:
                existing = self._locks.get(key)
                if existing is None or self._is_expired(existing):
                    # Lock is free
                    if existing is not None:
                        del self._locks[key]
                        self._expired_count += 1

                    # Capacity check
                    if len(self._locks) >= self._max_locks:
                        self._reap_expired()
                        if len(self._locks) >= self._max_locks:
                            self._denied_count += 1
                            return LockResult(
                                acquired=False, resource_key=resource_key,
                                holder_id=holder_id, error="lock capacity exceeded",
                            )

                    self._locks[key] = LockInfo(
                        resource_key=resource_key,
                        tenant_id=tenant_id,
                        holder_id=holder_id,
                        acquired_at=self._clock(),
                        ttl_seconds=effective_ttl,
                        reason=reason,
                    )
                    self._acquired_count += 1
                    waited = self._clock() - start
                    return LockResult(
                        acquired=True, resource_key=resource_key,
                        holder_id=holder_id, waited_seconds=round(waited, 4),
                    )

                # Lock held by someone else — wait or fail
                remaining = deadline - self._clock()
                if remaining <= 0:
                    self._denied_count += 1
                    waited = self._clock() - start
                    return LockResult(
                        acquired=False, resource_key=resource_key,
                        holder_id=holder_id, waited_seconds=round(waited, 4),
                        error="lock acquisition timed out",
                    )
                cond.wait(timeout=min(remaining, 1.0))

    def release(
        self,
        tenant_id: str,
        resource_key: str,
        *,
        holder_id: str,
    ) -> bool:
        """Release a held lock. Returns True if released, False if not held."""
        key = self._key(tenant_id, resource_key)
        with self._lock:
            existing = self._locks.get(key)
            if existing is None:
                return False
            if existing.holder_id != holder_id:
                return False  # Cannot release someone else's lock
            del self._locks[key]
            cond = self._conditions.pop(key, None)
            if cond is not None:
                cond.notify_all()
            return True

    @contextmanager
    def lock(
        self,
        tenant_id: str,
        resource_key: str,
        *,
        holder_id: str,
        ttl: float = 0.0,
        timeout: float = -1.0,
        reason: str = "",
    ) -> Generator[LockResult, None, None]:
        """Context manager for acquiring and releasing a lock.

        Raises RuntimeError if the lock cannot be acquired.
        """
        result = self.acquire(
            tenant_id, resource_key,
            holder_id=holder_id, ttl=ttl, timeout=timeout, reason=reason,
        )
        if not result.acquired:
            raise RuntimeError(f"failed to acquire lock on {resource_key}")
        try:
            yield result
        finally:
            self.release(tenant_id, resource_key, holder_id=holder_id)

    def is_locked(self, tenant_id: str, resource_key: str) -> bool:
        """Check if a resource is currently locked (non-expired)."""
        key = self._key(tenant_id, resource_key)
        with self._lock:
            info = self._locks.get(key)
            if info is None:
                return False
            if self._is_expired(info):
                del self._locks[key]
                self._expired_count += 1
                return False
            return True

    def lock_holder(self, tenant_id: str, resource_key: str) -> str | None:
        """Get the holder_id of a locked resource, or None."""
        key = self._key(tenant_id, resource_key)
        with self._lock:
            info = self._locks.get(key)
            if info is None or self._is_expired(info):
                return None
            return info.holder_id

    def held_locks(self, *, tenant_id: str = "", holder_id: str = "") -> list[LockInfo]:
        """List held (non-expired) locks, optionally filtered."""
        with self._lock:
            self._reap_expired()
            result = []
            for info in self._locks.values():
                if tenant_id and info.tenant_id != tenant_id:
                    continue
                if holder_id and info.holder_id != holder_id:
                    continue
                result.append(info)
            return result

    def force_release(self, tenant_id: str, resource_key: str) -> bool:
        """Admin: force-release a lock regardless of holder. Use with caution."""
        key = self._key(tenant_id, resource_key)
        with self._lock:
            if key in self._locks:
                del self._locks[key]
                cond = self._conditions.pop(key, None)
                if cond is not None:
                    cond.notify_all()
                return True
            return False

    def status(self) -> dict[str, Any]:
        """Lock manager status for health endpoint."""
        with self._lock:
            self._reap_expired()
            return {
                "active_locks": len(self._locks),
                "total_acquired": self._acquired_count,
                "total_denied": self._denied_count,
                "total_expired": self._expired_count,
                "capacity": self._max_locks,
                "default_ttl": self._default_ttl,
            }
