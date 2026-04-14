"""Phase 202C — Rate Limiting and Throttle Contracts.

Purpose: Per-tenant, per-endpoint, and per-identity rate limiting with token
    bucket algorithm.  Prevents abuse and ensures fair resource distribution
    across tenants AND within a tenant across identities.
Governance scope: request rate enforcement only.
Dependencies: none (pure algorithm).
Invariants:
  - Rate limits are per-tenant — one tenant cannot starve others.
  - Per-identity limits prevent a single user from exhausting shared quota.
  - Token bucket refills at constant rate — no burst accumulation beyond max.
  - Denied requests are tracked for observability.
  - Rate limit config is immutable once applied — changes require new config.
  - Both tenant-level AND identity-level checks must pass (dual gate).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Configuration for a rate limiter."""

    max_tokens: int = 60  # Max tokens in bucket
    refill_rate: float = 1.0  # Tokens per second
    burst_limit: int = 10  # Max tokens consumed in single burst

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.refill_rate <= 0.0:
            raise ValueError("refill_rate must be > 0.0")
        if self.burst_limit < 1:
            raise ValueError("burst_limit must be >= 1")


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining_tokens: int
    retry_after_seconds: float  # 0.0 if allowed
    tenant_id: str
    endpoint: str


class TokenBucket:
    """Token bucket rate limiter for a single key (tenant+endpoint)."""

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._tokens: float = float(config.max_tokens)
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Add tokens based on elapsed time. Caller must hold _lock."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._config.max_tokens),
            self._tokens + elapsed * self._config.refill_rate,
        )
        self._last_refill = now

    def try_consume(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to consume tokens. Returns (allowed, remaining_tokens)."""
        with self._lock:
            self._refill()
            if tokens > self._config.burst_limit:
                return False, self._tokens
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True, self._tokens
            return False, self._tokens

    @property
    def remaining(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


class RateLimitStore:
    """Optional persistent backend for rate limit counters.

    When provided to RateLimiter, denied/allowed counts and bucket
    configurations are persisted for cross-replica observability.
    Token bucket state remains in-memory (time-based, not shareable),
    but counter aggregation becomes consistent across replicas.
    """

    def record_decision(self, bucket_key: str, allowed: bool) -> None:
        pass

    def get_counters(self) -> dict[str, int]:
        return {"allowed": 0, "denied": 0}


class RateLimiter:
    """Multi-tenant rate limiter with per-endpoint and per-identity buckets.

    Each tenant+endpoint combination gets its own token bucket.
    Optionally, each identity within a tenant gets a separate, tighter
    bucket — preventing a single user from exhausting the shared quota.

    Dual-gate enforcement: both the tenant-level AND identity-level
    checks must pass.  If either denies, the request is denied.

    When a RateLimitStore is provided, decisions are written through
    for cross-replica observability.
    """

    def __init__(
        self,
        *,
        default_config: RateLimitConfig | None = None,
        identity_config: RateLimitConfig | None = None,
        max_buckets: int = 100_000,
        store: RateLimitStore | None = None,
    ) -> None:
        self._default_config = default_config or RateLimitConfig()
        self._identity_config = identity_config  # None = no per-identity limiting
        self._configs: dict[str, RateLimitConfig] = {}  # endpoint -> config
        self._identity_configs: dict[str, RateLimitConfig] = {}  # endpoint -> identity config
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()  # LRU: "tenant:endpoint" -> bucket
        self._max_buckets = max_buckets
        self._denied_count: int = 0
        self._allowed_count: int = 0
        self._identity_denied_count: int = 0
        self._store = store
        self._lock = threading.Lock()

    def configure_endpoint(
        self,
        endpoint: str,
        config: RateLimitConfig,
        *,
        identity_config: RateLimitConfig | None = None,
    ) -> None:
        """Set rate limit config for a specific endpoint.

        Args:
            endpoint: The endpoint path.
            config: Tenant-level rate limit config.
            identity_config: Optional per-identity config for this endpoint.
                Defaults to the limiter-wide identity_config if not specified.
        """
        self._configs[endpoint] = config
        if identity_config is not None:
            self._identity_configs[endpoint] = identity_config

    def _bucket_key(self, tenant_id: str, endpoint: str) -> str:
        return f"{tenant_id}:{endpoint}"

    @staticmethod
    def _identity_bucket_key(tenant_id: str, identity_id: str, endpoint: str) -> str:
        return f"{tenant_id}:{identity_id}:{endpoint}"

    def _get_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        if key in self._buckets:
            self._buckets.move_to_end(key)  # Mark as recently used
            return self._buckets[key]
        # Evict least recently used if at capacity
        if len(self._buckets) >= self._max_buckets:
            self._buckets.popitem(last=False)  # Remove LRU (oldest)
        self._buckets[key] = TokenBucket(config)
        return self._buckets[key]

    def _resolve_config(self, endpoint: str) -> RateLimitConfig:
        return self._configs.get(endpoint, self._default_config)

    def _resolve_identity_config(self, endpoint: str) -> RateLimitConfig | None:
        return self._identity_configs.get(endpoint, self._identity_config)

    def check(
        self,
        tenant_id: str,
        endpoint: str,
        tokens: int = 1,
        *,
        identity_id: str = "",
    ) -> RateLimitResult:
        """Check if a request is allowed under rate limits.

        Performs dual-gate check when identity_id is provided and
        per-identity config exists:
          1. Tenant-level bucket must allow.
          2. Identity-level bucket must allow.
        Both must pass — if either denies, the request is denied.
        """
        if tokens < 1:
            raise ValueError(f"tokens must be >= 1, got {tokens}")
        with self._lock:
            tenant_config = self._resolve_config(endpoint)
            tenant_key = self._bucket_key(tenant_id, endpoint)
            tenant_bucket = self._get_bucket(tenant_key, tenant_config)

        # Tenant-level check (TokenBucket has its own lock)
        allowed, remaining = tenant_bucket.try_consume(tokens)
        denied_by = ""
        if not allowed:
            denied_by = "tenant"

        # Identity-level check (only if tenant allowed and identity provided)
        identity_remaining: float | None = None
        if allowed and identity_id:
            id_config = self._resolve_identity_config(endpoint)
            if id_config is not None:
                with self._lock:
                    id_key = self._identity_bucket_key(tenant_id, identity_id, endpoint)
                    id_bucket = self._get_bucket(id_key, id_config)
                id_allowed, identity_remaining = id_bucket.try_consume(tokens)
                if not id_allowed:
                    allowed = False
                    denied_by = "identity"

        with self._lock:
            if allowed:
                self._allowed_count += 1
            else:
                self._denied_count += 1
            if denied_by == "identity":
                self._identity_denied_count += 1
        if self._store is not None:
            self._store.record_decision(tenant_key, allowed)

        retry_after = 0.0
        if not allowed:
            if denied_by == "identity" and identity_remaining is not None:
                deficit = tokens - identity_remaining
                id_config = self._resolve_identity_config(endpoint)
                refill = id_config.refill_rate if id_config and id_config.refill_rate > 0 else 999.0
                retry_after = deficit / refill
            else:
                deficit = tokens - remaining
                retry_after = deficit / tenant_config.refill_rate if tenant_config.refill_rate > 0 else 999.0

        return RateLimitResult(
            allowed=allowed,
            remaining_tokens=int(identity_remaining if identity_remaining is not None and identity_id else remaining),
            retry_after_seconds=round(retry_after, 2),
            tenant_id=tenant_id,
            endpoint=endpoint,
        )

    @property
    def denied_count(self) -> int:
        return self._denied_count

    @property
    def allowed_count(self) -> int:
        return self._allowed_count

    @property
    def identity_denied_count(self) -> int:
        return self._identity_denied_count

    def status(self) -> dict[str, Any]:
        """Rate limiter status for health endpoint."""
        return {
            "total_allowed": self._allowed_count,
            "total_denied": self._denied_count,
            "identity_denied": self._identity_denied_count,
            "active_buckets": len(self._buckets),
            "configured_endpoints": list(self._configs.keys()),
            "identity_limiting_enabled": self._identity_config is not None,
        }
