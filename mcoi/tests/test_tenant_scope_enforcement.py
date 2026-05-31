"""Cross-tenant access enforcement for data-plane routes.

Regression test for the path/body-tenant IDOR: an authenticated caller for one
tenant must not read or mutate another tenant's data via a path/body tenant id.
``enforce_tenant_scope`` rejects a mismatch when the request is authenticated,
and is a no-op for unauthenticated (dev / no-auth) requests.
"""

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers._tenant_scope import (
    enforce_tenant_scope,
    scoped_listing_tenant,
)


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def test_authenticated_cross_tenant_is_denied():
    req = _Req({"authenticated_tenant_id": "tenant-a"})
    with pytest.raises(HTTPException) as exc_info:
        enforce_tenant_scope(req, "tenant-b")
    assert exc_info.value.status_code == 403


def test_authenticated_same_tenant_is_allowed():
    enforce_tenant_scope(_Req({"authenticated_tenant_id": "tenant-a"}), "tenant-a")


def test_unauthenticated_request_is_not_enforced():
    # No authenticated tenant (dev / no-auth) -> no-op, existing suites unaffected.
    enforce_tenant_scope(_Req({}), "tenant-b")
    enforce_tenant_scope(_Req({"authenticated_tenant_id": ""}), "tenant-b")


def test_wildcard_scope_may_act_cross_tenant():
    req = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    enforce_tenant_scope(req, "tenant-b")


def test_missing_governance_context_attr_is_safe():
    class _BareState:
        pass

    class _BareReq:
        def __init__(self):
            self.state = _BareState()

    enforce_tenant_scope(_BareReq(), "tenant-b")


def test_scoped_listing_forces_authenticated_tenant_when_none():
    # The tenant_id=None "return all tenants" IDOR: authenticated requests are
    # forced to their own tenant.
    assert scoped_listing_tenant(_Req({"authenticated_tenant_id": "tenant-a"}), None) == "tenant-a"


def test_scoped_listing_denies_other_tenant():
    with pytest.raises(HTTPException) as exc_info:
        scoped_listing_tenant(_Req({"authenticated_tenant_id": "tenant-a"}), "tenant-b")
    assert exc_info.value.status_code == 403


def test_scoped_listing_passthrough_when_unauthenticated():
    # Dev / no-auth: claimed filter is unchanged (incl. None -> all), suite unaffected.
    assert scoped_listing_tenant(_Req({}), None) is None
    assert scoped_listing_tenant(_Req({}), "tenant-b") == "tenant-b"


def test_scoped_listing_operator_keeps_claimed_filter():
    req = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    assert scoped_listing_tenant(req, None) is None
    assert scoped_listing_tenant(req, "tenant-b") == "tenant-b"
