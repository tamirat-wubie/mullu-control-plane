"""Phase 208A - Governance Guard Middleware.

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

import json
import logging
import time
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcoi_runtime.core.content_safety import ContentSafetyChain, create_content_safety_guard
from mcoi_runtime.core.governance_guard import (
    GovernanceGuardChain,
    create_api_key_guard,
    create_budget_guard,
    create_jwt_guard,
    create_rbac_guard,
    create_rate_limit_guard,
    create_tenant_guard,
)

_log = logging.getLogger(__name__)

# Paths exempt from governance guards
EXEMPT_PATHS = frozenset({"/health", "/ready", "/docs", "/openapi.json", "/redoc"})

# Max body size to parse for content safety (1MB). Larger bodies skip content extraction.
MAX_BODY_PARSE_SIZE = 1_048_576


def _extract_content_safety_fields(body: bytes) -> dict[str, str]:
    """Extract prompt/content fields for safety checks from a JSON body."""
    if not body or len(body) > MAX_BODY_PARSE_SIZE:
        return {}
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    extracted: dict[str, str] = {}
    prompt = parsed.get("prompt")
    content = parsed.get("content")
    if isinstance(prompt, str):
        extracted["prompt"] = prompt
    if isinstance(content, str):
        extracted["content"] = content
    return extracted


class GovernanceMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces governance guards."""

    def __init__(
        self,
        app: Any,
        *,
        guard_chain: GovernanceGuardChain,
        metrics_fn: Callable[[str, int], None] | None = None,
        on_reject: Callable[[dict[str, Any]], None] | None = None,
        on_allow: Callable[[dict[str, Any]], None] | None = None,
        proof_bridge: Any | None = None,
        decision_log: Any | None = None,
        request_analytics: Any | None = None,
    ) -> None:
        super().__init__(app)
        self._chain = guard_chain
        self._metrics_fn = metrics_fn
        self._on_reject = on_reject
        self._on_allow = on_allow
        self._proof_bridge = proof_bridge
        self._decision_log = decision_log
        self._request_analytics = request_analytics

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path

        # Skip non-governed paths
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # Build guard context from request
        tenant_id = request.query_params.get("tenant_id", "")
        if not tenant_id:
            tenant_id = request.headers.get("x-tenant-id", "system")

        context: dict[str, Any] = {
            "tenant_id": tenant_id,
            "endpoint": path,
            "method": request.method,
            "authorization": request.headers.get("authorization", ""),
        }

        # Extract prompt/content from request body for content safety guard.
        # Starlette caches body after first read, so downstream handlers can re-read.
        content_type = request.headers.get("content-type", "")
        if "json" in content_type and request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                context.update(_extract_content_safety_fields(body))
            except (RuntimeError, UnicodeDecodeError, json.JSONDecodeError):
                pass  # Non-JSON or malformed body - skip content extraction

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

        # Record to governance decision log
        if self._decision_log is not None:
            try:
                from mcoi_runtime.core.governance_decision_log import GuardDecisionDetail
                guards = [
                    GuardDecisionDetail(
                        guard_name=r.guard_name,
                        allowed=r.allowed,
                        reason=r.reason,
                    )
                    for r in result.results
                ]
                self._decision_log.record(
                    tenant_id=tenant_id,
                    identity_id=context.get("authenticated_subject", ""),
                    endpoint=path,
                    method=request.method,
                    allowed=result.allowed,
                    blocking_guard=result.blocking_guard,
                    blocking_reason=result.reason,
                    guards=guards,
                )
            except Exception as exc:
                if self._metrics_fn:
                    self._metrics_fn("decision_log_record_failures", 1)
                _log.warning(
                    "governance decision log record failed (%s)",
                    type(exc).__name__,
                )

        # Certify governance decision via proof bridge
        if self._proof_bridge is not None:
            try:
                guard_results = [
                    {"guard_name": r.guard_name, "allowed": r.allowed, "reason": r.reason}
                    for r in result.results
                ]
                self._proof_bridge.certify_governance_decision(
                    tenant_id=context.get("tenant_id", "system"),
                    endpoint=path,
                    guard_results=guard_results,
                    decision="allowed" if result.allowed else "denied",
                    reason=result.reason,
                )
            except Exception as exc:
                if self._metrics_fn:
                    self._metrics_fn("proof_bridge_certification_failures", 1)
                _log.warning(
                    "proof bridge certification failed (%s)",
                    type(exc).__name__,
                )

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

        # Guards passed - record allowed request for audit completeness
        if self._on_allow:
            self._on_allow({
                "path": path,
                "tenant_id": context.get("tenant_id", ""),
                "method": request.method,
                "latency_ms": round(latency_ms, 2),
            })

        # Guards passed - proceed to endpoint
        response = await call_next(request)

        # Record request analytics
        if self._request_analytics is not None:
            total_latency = (time.monotonic() - start) * 1000
            status_code = getattr(response, "status_code", 200)
            try:
                self._request_analytics.record(
                    path, latency_ms=total_latency,
                    success=200 <= status_code < 400,
                    status_code=status_code,
                )
            except Exception as exc:
                if self._metrics_fn:
                    self._metrics_fn("request_analytics_record_failures", 1)
                _log.warning(
                    "request analytics record failed (%s)",
                    type(exc).__name__,
                )

        return response


def build_guard_chain(
    *,
    rate_limiter: Any,
    budget_mgr: Any,
    api_key_mgr: Any | None = None,
    jwt_authenticator: Any | None = None,
    tenant_gating_registry: Any | None = None,
    access_runtime: Any | None = None,
    content_safety_chain: ContentSafetyChain | None = None,
) -> GovernanceGuardChain:
    """Build the standard governance guard chain.

    Guard order:
    1. API Key / JWT auth (who are you?)
    2. Tenant validation (is tenant_id valid?)
    3. Tenant gating (is tenant active?)
    4. RBAC (does this identity have permission?)
    5. Content safety (is the prompt safe?)
    6. Rate limit (within limits?)
    7. Budget (can you afford this?)
    """
    chain = GovernanceGuardChain()
    if api_key_mgr is not None:
        chain.add(create_api_key_guard(api_key_mgr))
    if jwt_authenticator is not None:
        chain.add(create_jwt_guard(jwt_authenticator))
    chain.add(create_tenant_guard())
    if tenant_gating_registry is not None:
        from mcoi_runtime.core.tenant_gating import create_tenant_gating_guard
        chain.add(create_tenant_gating_guard(tenant_gating_registry))
    if access_runtime is not None:
        chain.add(create_rbac_guard(access_runtime))
    if content_safety_chain is not None:
        chain.add(create_content_safety_guard(content_safety_chain))
    chain.add(create_rate_limit_guard(rate_limiter))
    chain.add(create_budget_guard(budget_mgr))
    return chain
