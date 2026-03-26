"""Phase 223A — Rate Limit Response Headers.

Purpose: Compute and attach standard rate limit headers to HTTP responses.
    Follows IETF draft-ietf-httpapi-ratelimit-headers (RateLimit-Limit,
    RateLimit-Remaining, RateLimit-Reset).
Dependencies: rate_limiter.
Invariants:
  - Headers are always non-negative integers.
  - Reset is Unix timestamp (seconds).
  - Retry-After is seconds until next token.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RateLimitInfo:
    """Snapshot of rate limit state for a single client/tenant."""
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp
    retry_after: float | None = None  # seconds, only when exhausted

    def to_headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None and self.retry_after > 0:
            headers["Retry-After"] = str(int(self.retry_after) + 1)
        return headers

    @property
    def is_exhausted(self) -> bool:
        return self.remaining <= 0


class RateLimitHeaderProvider:
    """Computes rate limit headers from token bucket state."""

    def __init__(self, default_limit: int = 60, window_seconds: float = 60.0):
        self._default_limit = default_limit
        self._window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}

    def consume(self, client_id: str, tokens: int = 1) -> RateLimitInfo:
        """Consume tokens and return current rate limit info."""
        bucket = self._get_or_create(client_id)
        bucket.refill()
        allowed = min(tokens, bucket.tokens)
        bucket.tokens -= allowed
        remaining = int(bucket.tokens)
        reset_at = bucket.last_refill + self._window_seconds
        retry_after = None
        if remaining <= 0:
            retry_after = max(0.0, reset_at - time.time())
        return RateLimitInfo(
            limit=self._default_limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )

    def peek(self, client_id: str) -> RateLimitInfo:
        """Check rate limit state without consuming tokens."""
        bucket = self._get_or_create(client_id)
        bucket.refill()
        remaining = int(bucket.tokens)
        reset_at = bucket.last_refill + self._window_seconds
        return RateLimitInfo(
            limit=self._default_limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    def _get_or_create(self, client_id: str) -> _Bucket:
        if client_id not in self._buckets:
            self._buckets[client_id] = _Bucket(
                tokens=float(self._default_limit),
                last_refill=time.time(),
                max_tokens=float(self._default_limit),
                refill_rate=self._default_limit / self._window_seconds,
            )
        return self._buckets[client_id]

    @property
    def tracked_clients(self) -> int:
        return len(self._buckets)

    def summary(self) -> dict[str, Any]:
        return {
            "default_limit": self._default_limit,
            "window_seconds": self._window_seconds,
            "tracked_clients": self.tracked_clients,
        }


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    max_tokens: float
    refill_rate: float  # tokens per second

    def refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
