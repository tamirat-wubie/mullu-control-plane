"""Phase 202C — Rate Limiting and Throttle Contracts.

Purpose: Per-tenant and per-endpoint rate limiting with token bucket algorithm.
    Prevents abuse and ensures fair resource distribution across tenants.
Governance scope: request rate enforcement only.
Dependencies: none (pure algorithm).
Invariants:
  - Rate limits are per-tenant — one tenant cannot starve others.
  - Token bucket refills at constant rate — no burst accumulation beyond max.
  - Denied requests are tracked for observability.
  - Rate limit config is immutable once applied — changes require new config.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Configuration for a rate limiter."""

    max_tokens: int = 60  # Max tokens in bucket
    refill_rate: float = 1.0  # Tokens per second
    burst_limit: int = 10  # Max tokens consumed in single burst


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

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            float(self._config.max_tokens),
            self._tokens + elapsed * self._config.refill_rate,
        )
        self._last_refill = now

    def try_consume(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to consume tokens. Returns (allowed, remaining_tokens)."""
        self._refill()
        if tokens > self._config.burst_limit:
            return False, self._tokens
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True, self._tokens
        # Calculate retry-after
        deficit = tokens - self._tokens
        retry_after = deficit / self._config.refill_rate if self._config.refill_rate > 0 else 999.0
        return False, self._tokens

    @property
    def remaining(self) -> float:
        self._refill()
        return self._tokens


class RateLimiter:
    """Multi-tenant rate limiter with per-endpoint buckets.

    Each tenant+endpoint combination gets its own token bucket.
    Limits are independently enforced — cross-tenant interference
    is structurally impossible.
    """

    def __init__(
        self,
        *,
        default_config: RateLimitConfig | None = None,
    ) -> None:
        self._default_config = default_config or RateLimitConfig()
        self._configs: dict[str, RateLimitConfig] = {}  # endpoint -> config
        self._buckets: dict[str, TokenBucket] = {}  # "tenant:endpoint" -> bucket
        self._denied_count: int = 0
        self._allowed_count: int = 0

    def configure_endpoint(self, endpoint: str, config: RateLimitConfig) -> None:
        """Set rate limit config for a specific endpoint."""
        self._configs[endpoint] = config

    def _bucket_key(self, tenant_id: str, endpoint: str) -> str:
        return f"{tenant_id}:{endpoint}"

    def _get_bucket(self, tenant_id: str, endpoint: str) -> TokenBucket:
        key = self._bucket_key(tenant_id, endpoint)
        if key not in self._buckets:
            config = self._configs.get(endpoint, self._default_config)
            self._buckets[key] = TokenBucket(config)
        return self._buckets[key]

    def check(self, tenant_id: str, endpoint: str, tokens: int = 1) -> RateLimitResult:
        """Check if a request is allowed under rate limits."""
        bucket = self._get_bucket(tenant_id, endpoint)
        allowed, remaining = bucket.try_consume(tokens)

        if allowed:
            self._allowed_count += 1
        else:
            self._denied_count += 1

        retry_after = 0.0
        if not allowed:
            deficit = tokens - remaining
            config = self._configs.get(endpoint, self._default_config)
            retry_after = deficit / config.refill_rate if config.refill_rate > 0 else 999.0

        return RateLimitResult(
            allowed=allowed,
            remaining_tokens=int(remaining),
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

    def status(self) -> dict[str, Any]:
        """Rate limiter status for health endpoint."""
        return {
            "total_allowed": self._allowed_count,
            "total_denied": self._denied_count,
            "active_buckets": len(self._buckets),
            "configured_endpoints": list(self._configs.keys()),
        }
