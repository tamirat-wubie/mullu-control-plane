"""Cross-tenant IDOR regression for agent memory endpoints.

store_memory / search_memory took tenant_id from the request body and wrote/read
agent memory under that tenant with no check against the authenticated tenant: a
caller authenticated for tenant A could read tenant B's agent memory (search) or
inject memories into tenant B's agent memory (store / cross-tenant memory
poisoning). The handlers now call enforce_tenant_scope; an authenticated
cross-tenant request must be rejected, while operator and unauthenticated/dev
requests are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers.agent import (
    MemorySearchRequest,
    MemoryStoreRequest,
    search_memory,
    store_memory,
)


class _State:
    def __init__(self, ctx):
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx):
        self.state = _State(ctx)


def _authed_a() -> _Req:
    return _Req({"authenticated_tenant_id": "tenant-a"})


def test_store_memory_denies_cross_tenant():
    body = MemoryStoreRequest(agent_id="agent-1", tenant_id="tenant-b", content="x")
    with pytest.raises(HTTPException) as exc:
        store_memory(body, _authed_a())
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_search_memory_denies_cross_tenant():
    body = MemorySearchRequest(agent_id="agent-1", tenant_id="tenant-b", query="x")
    with pytest.raises(HTTPException) as exc:
        search_memory(body, _authed_a())
    assert exc.value.status_code == 403


def test_operator_wildcard_may_access_any_tenant_memory():
    from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope

    operator = _Req({"authenticated_tenant_id": "tenant-a", "jwt_scopes": frozenset({"*"})})
    enforce_tenant_scope(operator, "tenant-b")  # no raise
