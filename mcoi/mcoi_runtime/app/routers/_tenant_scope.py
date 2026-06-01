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


# Fail-closed strict mode. Default False preserves the historical dev/test no-op
# (unit suites and local_dev build apps without auth). The server bootstrap calls
# configure_tenant_scope_strict(True) for non-dev environments, so a request that
# reaches a tenant-scoped handler WITHOUT an authenticated tenant is rejected with
# 401 instead of being treated as a trusted dev request -- closing the gap where
# the opt-in (require_auth=False) middleware guard chain lets an unauthenticated
# caller through and these helpers would otherwise no-op.
_STRICT_TENANT_SCOPE: bool = False


def configure_tenant_scope_strict(enabled: bool) -> None:
    """Enable/disable fail-closed tenant scoping (pilot/production = enabled)."""
    global _STRICT_TENANT_SCOPE
    _STRICT_TENANT_SCOPE = bool(enabled)


def tenant_scope_strict() -> bool:
    """Inspect the strict flag. Test/diagnostics only."""
    return _STRICT_TENANT_SCOPE


def _require_authenticated_tenant() -> None:
    """Reject an unauthenticated tenant-scoped request when strict mode is on."""
    if _STRICT_TENANT_SCOPE:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "authentication required for tenant-scoped resource",
                "code": "authentication_required",
                "governed": True,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def enforce_tenant_scope(request: Request, claimed_tenant: str) -> None:
    """Reject a path/body tenant that differs from the authenticated tenant.

    No-op when the request is not authenticated (no ``authenticated_tenant_id``)
    or when the caller holds the wildcard ``*`` scope.
    """
    context: dict[str, Any] = getattr(request.state, "governance_context", None) or {}
    authenticated_tenant = str(context.get("authenticated_tenant_id") or "").strip()
    if not authenticated_tenant:
        _require_authenticated_tenant()
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


def scoped_listing_tenant(request: Request, claimed_tenant: str | None) -> str | None:
    """Resolve the tenant filter for a listing/query endpoint.

    Authenticated, non-operator requests are forced to their own tenant: a
    ``None`` or different ``claimed_tenant`` cannot widen the result to other
    tenants (the ``tenant_id=None`` "return everything" default is the IDOR).
    Operators (``*`` scope) and unauthenticated (dev) requests keep the claimed
    filter unchanged, so existing suites are not affected.
    """
    context: dict[str, Any] = getattr(request.state, "governance_context", None) or {}
    authenticated_tenant = str(context.get("authenticated_tenant_id") or "").strip()
    if not authenticated_tenant:
        _require_authenticated_tenant()
        return claimed_tenant
    scopes = context.get("jwt_scopes") or frozenset()
    if "*" in scopes:
        return claimed_tenant
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
    return authenticated_tenant
