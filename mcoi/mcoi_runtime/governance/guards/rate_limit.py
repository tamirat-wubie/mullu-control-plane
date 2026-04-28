"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.rate_limiter`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.rate_limiter`` path or the new ``governance.guards.rate_limit`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.rate_limiter import (  # noqa: F401
    RateLimitConfig,
    RateLimitResult,
    RateLimitStore,
    RateLimiter,
    TokenBucket,
)

__all__ = (
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStore",
    "RateLimiter",
    "TokenBucket",
)
