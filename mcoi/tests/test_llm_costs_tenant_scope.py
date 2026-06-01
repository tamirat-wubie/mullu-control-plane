"""Cross-tenant IDOR regression for the LLM cost endpoints.

GET /api/v1/costs/{tenant_id} and /api/v1/costs/{tenant_id}/projection took the
tenant from the URL path and returned that tenant's spend/usage without checking
the authenticated tenant, so a caller authenticated for tenant A could read
tenant B's financial data. The handlers now call enforce_tenant_scope; an
authenticated cross-tenant request must be rejected, while operator (wildcard
scope) and unauthenticated requests are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.llm.costs import cost_projection, tenant_costs


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def test_tenant_costs_denies_cross_tenant_path():
    req = _Req({"authenticated_tenant_id": "tenant-a"})
    with pytest.raises(HTTPException) as exc:
        tenant_costs("tenant-b", req)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_cost_projection_denies_cross_tenant_path():
    req = _Req({"authenticated_tenant_id": "tenant-a"})
    with pytest.raises(HTTPException) as exc:
        cost_projection("tenant-b", req)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_operator_wildcard_scope_bypasses_scope_check():
    # Operator/admin (wildcard scope) is allowed across tenants: the scope check
    # must not raise. (It returns None and the handler proceeds to analytics.)
    from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope

    req = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    enforce_tenant_scope(req, "tenant-b")  # no raise


def test_unauthenticated_request_is_not_scoped():
    from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope

    req = _Req({})
    enforce_tenant_scope(req, "tenant-b")  # no raise
