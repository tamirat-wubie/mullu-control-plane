"""Request-scoped tenant guard -- persistence-layer defense-in-depth.

Purpose: carry the AUTHENTICATED tenant of the in-flight request down to the
    persistence layer so a store that returns a tenant-owned record can refuse
    to hand it to a different tenant -- a second line of defense BELOW the
    router's ``enforce_tenant_scope``. If a future by-id handler forgets to
    scope, the store still will not leak another tenant's record to a
    non-operator request.
Governance scope: read-path tenant isolation (defense-in-depth only).
Dependencies: none (stdlib contextvars + dataclasses).
Invariants:
  - No-op unless the middleware bound a concrete, non-operator authenticated
    tenant for the current request. Operators (wildcard scope),
    unauthenticated / dev requests, and non-request contexts (background jobs,
    tests) leave the binding empty, so ``assert_owns`` is a pass-through.
  - Binding is request-scoped via a ContextVar: it propagates into the sync
    threadpool handler and does not leak between requests.
  - The router's ``enforce_tenant_scope`` (403 cross_tenant_denied) and the
    fail-closed keystone remain the primary authority; this layer only fires
    when those were skipped.

Why a ContextVar (not a parameter): threading the authenticated tenant through
every store call would touch hundreds of signatures. The middleware already
resolves identity once; a ContextVar bridges that to the persistence layer with
zero signature churn and clean request isolation (verified: a sync handler in
the threadpool sees the bound value, and a later request does not).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass

# Scope token that means "operator / cross-tenant authority" -- mirrors
# _tenant_scope.py, where a wildcard scope makes tenant enforcement a no-op.
_OPERATOR_SCOPE = "*"


class CrossTenantRecordError(PermissionError):
    """A store was asked to return a record owned by a different tenant.

    Raised by ``assert_owns`` only when an authenticated, non-operator tenant is
    bound for the current request and a record from another tenant would be
    returned. The HTTP layer maps it to a bounded 403 (cross_tenant_denied).
    """


@dataclass(frozen=True, slots=True)
class _RequestTenant:
    tenant_id: str
    is_operator: bool


_request_tenant: contextvars.ContextVar[_RequestTenant | None] = contextvars.ContextVar(
    "mcoi_request_tenant", default=None
)


def bind_request_tenant(tenant_id: str | None, scopes: object = None) -> object:
    """Bind the authenticated tenant for the current request; return a token.

    Called by the governance middleware once the guard chain has resolved
    identity. Binds only when there is a concrete authenticated tenant. An
    operator (wildcard scope) binds with ``is_operator=True`` so ``assert_owns``
    stays a no-op while still recording who is acting. An empty / unauthenticated
    tenant binds ``None`` (full no-op). Always pair with ``reset_request_tenant``
    in a ``finally``.
    """
    tid = str(tenant_id or "").strip()
    if not tid:
        return _request_tenant.set(None)
    scope_set = scopes if scopes is not None else frozenset()
    try:
        is_operator = _OPERATOR_SCOPE in scope_set  # type: ignore[operator]
    except TypeError:
        is_operator = False
    return _request_tenant.set(_RequestTenant(tenant_id=tid, is_operator=is_operator))


def reset_request_tenant(token: object) -> None:
    """Reset a binding produced by ``bind_request_tenant`` (call in finally)."""
    try:
        _request_tenant.reset(token)  # type: ignore[arg-type]
    except (ValueError, LookupError):
        # Token from a different context (should not happen in normal
        # middleware use); fail safe by clearing the binding outright.
        _request_tenant.set(None)


def current_request_tenant() -> _RequestTenant | None:
    """Return the bound request tenant, or None when unbound / no-op."""
    return _request_tenant.get()


def assert_owns(record_tenant_id: str | None, *, resource: str = "record") -> None:
    """Refuse to return another tenant's record (defense-in-depth).

    No-op unless an authenticated, non-operator tenant is bound for the current
    request. When bound, a record whose tenant differs raises
    ``CrossTenantRecordError``. A record with no tenant attribution is treated as
    not tenant-owned and passes through.
    """
    bound = _request_tenant.get()
    if bound is None or bound.is_operator:
        return
    rid = str(record_tenant_id or "").strip()
    if not rid:
        return
    if rid != bound.tenant_id:
        raise CrossTenantRecordError(f"{resource} belongs to another tenant")
