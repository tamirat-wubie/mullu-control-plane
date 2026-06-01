"""Fail-closed (strict) tenant scoping.

enforce_tenant_scope / scoped_listing_tenant no-op when a request carries no
authenticated tenant -- correct for local_dev/test, but the HTTP guard chain is
opt-in (require_auth=False), so an unauthenticated caller can reach a tenant-scoped
handler in any environment. The server bootstrap enables strict mode for non-dev
environments (configure_tenant_scope_strict), which turns that no-op into a 401.

Strict mode is OFF by default so unit suites and local_dev are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers._tenant_scope import (
    configure_tenant_scope_strict,
    enforce_tenant_scope,
    scoped_listing_tenant,
    tenant_scope_strict,
)


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _unauth() -> _Req:
    return _Req({})


def _authed(tenant_id: str) -> _Req:
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": frozenset({"musia.read"})})


@pytest.fixture
def strict():
    configure_tenant_scope_strict(True)
    try:
        yield
    finally:
        configure_tenant_scope_strict(False)


def test_default_is_not_strict():
    assert tenant_scope_strict() is False


def test_strict_rejects_unauthenticated_enforce(strict):
    with pytest.raises(HTTPException) as exc:
        enforce_tenant_scope(_unauth(), "tenant-a")
    assert exc.value.status_code == 401


def test_strict_rejects_unauthenticated_listing(strict):
    with pytest.raises(HTTPException) as exc:
        scoped_listing_tenant(_unauth(), None)
    assert exc.value.status_code == 401


def test_strict_still_allows_authenticated(strict):
    enforce_tenant_scope(_authed("tenant-a"), "tenant-a")  # own tenant -> no raise
    assert scoped_listing_tenant(_authed("tenant-a"), "") == "tenant-a"


def test_strict_authenticated_cross_tenant_still_403(strict):
    with pytest.raises(HTTPException) as exc:
        enforce_tenant_scope(_authed("tenant-a"), "tenant-b")
    assert exc.value.status_code == 403


def test_non_strict_unauthenticated_is_noop():
    # No fixture -> default off: unauthenticated passes through unchanged.
    enforce_tenant_scope(_unauth(), "tenant-a")  # no raise
    assert scoped_listing_tenant(_unauth(), "tenant-b") == "tenant-b"
