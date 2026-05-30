"""Cross-tenant access enforcement for data-plane routes.

Regression test for the path/body-tenant IDOR: an authenticated caller for one
tenant must not read or mutate another tenant's data via a path/body tenant id.
``enforce_tenant_scope`` rejects a mismatch when the request is authenticated,
and is a no-op for unauthenticated (dev / no-auth) requests.
"""

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope


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
