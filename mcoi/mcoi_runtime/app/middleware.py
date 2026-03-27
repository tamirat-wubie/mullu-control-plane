"""Phase 208A — Governance Guard Middleware.

Purpose: FastAPI middleware that runs the governance guard chain
    on every governed request before endpoint logic executes.
Governance scope: request-level validation only.
Dependencies: governance_guard, metrics, audit_trail.
Invariants:
  - Middleware runs on all /api/v1/* paths.
  - Non-governed paths (/health, /ready) are exempt.
  - Rejected requests get 429/403 with structured error.
  - All guard evaluations are metricked.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcoi_runtime.core.governance_guard import (
    GovernanceGuardChain,
    GuardChainResult,
    create_api_key_guard,
    create_budget_guard,
    create_rate_limit_guard,
    create_tenant_guard,
)


# Paths exempt from governance guards
EXEMPT_PATHS = frozenset({"/health", "/ready", "/docs", "/openapi.json", "/redoc"})


class GovernanceMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces governance guards."""

    def __init__(
        self,
        app: Any,
        *,
        guard_chain: GovernanceGuardChain,
        metrics_fn: Callable[[str, int], None] | None = None,
        on_reject: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(app)
        self._chain = guard_chain
        self._metrics_fn = metrics_fn
        self._on_reject = on_reject

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path

        # Skip non-governed paths
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # Build guard context from request
        tenant_id = ""
        # Try to extract tenant_id from query params or headers
        tenant_id = request.query_params.get("tenant_id", "")
        if not tenant_id:
            tenant_id = request.headers.get("x-tenant-id", "system")

        context = {
            "tenant_id": tenant_id,
            "endpoint": path,
            "method": request.method,
            "authorization": request.headers.get("authorization", ""),
        }

        # Evaluate guard chain
        start = time.monotonic()
        result = self._chain.evaluate(context)
        latency_ms = (time.monotonic() - start) * 1000

        if self._metrics_fn:
            self._metrics_fn("requests_total", 1)
            if result.allowed:
                self._metrics_fn("requests_governed", 1)
            else:
                self._metrics_fn("requests_rejected", 1)

        if not result.allowed:
            if self._on_reject:
                self._on_reject({
                    "path": path,
                    "tenant_id": tenant_id,
                    "guard": result.blocking_guard,
                    "reason": result.reason,
                })

            if result.blocking_guard == "rate_limit":
                status_code = 429
            elif result.blocking_guard == "api_key":
                status_code = 401
            else:
                status_code = 403
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": result.reason,
                    "guard": result.blocking_guard,
                    "governed": True,
                    "latency_ms": round(latency_ms, 2),
                },
            )

        # Guards passed — proceed to endpoint
        response = await call_next(request)
        return response


def build_guard_chain(
    *,
    rate_limiter: Any,
    budget_mgr: Any,
    api_key_mgr: Any | None = None,
) -> GovernanceGuardChain:
    """Build the standard governance guard chain."""
    chain = GovernanceGuardChain()
    if api_key_mgr is not None:
        chain.add(create_api_key_guard(api_key_mgr))
    chain.add(create_tenant_guard())
    chain.add(create_rate_limit_guard(rate_limiter))
    chain.add(create_budget_guard(budget_mgr))
    return chain
