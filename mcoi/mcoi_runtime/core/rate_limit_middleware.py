"""Phase 217A — Rate Limit Response Headers.

Purpose: Adds standard rate limit headers to API responses.
Governance scope: header injection only.
"""

from __future__ import annotations
from typing import Any


def rate_limit_headers(remaining: int, limit: int, retry_after: float = 0.0) -> dict[str, str]:
    """Generate standard rate limit response headers."""
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
    }
    if retry_after > 0:
        headers["Retry-After"] = str(int(retry_after))
    return headers
