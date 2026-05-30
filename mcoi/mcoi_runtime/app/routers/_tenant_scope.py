"""Cross-tenant access enforcement for data-plane routes.

The ``GovernanceMiddleware`` resolves the request tenant from the
``tenant_id`` query param / ``X-Tenant-ID`` header only, and the auth guards
validate that value against the authenticated token (``authenticated_tenant_id``
in ``request.state.governance_context``). Routes that instead take a tenant from
the URL **path** or request **body** bypass that binding — an authenticated
caller for tenant A could read or mutate tenant B's data.

``enforce_tenant_scope`` closes that gap: when the request is authenticated, the
path/body tenant must equal the authenticated tenant. It is intentionally a
no-op for unauthenticated requests (dev / no-auth profiles) — there is no
authenticated tenant identity to violate, and the existing suites build apps
without auth. A JWT carrying the wildcard ``*`` scope (operator/admin) may act
across tenants.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request


def enforce_tenant_scope(request: Request, claimed_tenant: str) -> None:
    """Reject a path/body tenant that differs from the authenticated tenant.

    No-op when the request is not authenticated (no ``authenticated_tenant_id``)
    or when the caller holds the wildcard ``*`` scope.
    """
    context: dict[str, Any] = getattr(request.state, "governance_context", None) or {}
    authenticated_tenant = str(context.get("authenticated_tenant_id") or "").strip()
    if not authenticated_tenant:
        return  # unauthenticated request — nothing authenticated to violate
    scopes = context.get("jwt_scopes") or frozenset()
    if "*" in scopes:
        return  # operator/admin wildcard may act across tenants
    claimed = str(claimed_tenant or "").strip()
    if claimed and claimed != authenticated_tenant:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "requested tenant does not match the authenticated tenant",
                "code": "cross_tenant_denied",
                "governed": True,
            },
        )
