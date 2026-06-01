"""Authorization for cross-tenant financial/operator listing endpoints.

Two endpoints exposed platform-wide, cross-tenant financial data with no
authorization:
- tenant.list_tenants ("List all tenants with budgets and ledger activity") --
  every tenant's budget reports and total spend.
- llm/costs.top_spenders ("Top spending tenants") -- per-tenant spend rankings.

Both are inherently operator views (they cannot be scoped to a single tenant
without defeating their purpose), so they now require the musia.admin scope. The
per-tenant cost endpoints (/api/v1/costs/{tenant_id}) were already scoped with
enforce_tenant_scope and are unchanged. In dev mode the check is a no-op (77
cost/tenant tests green); in auth mode a non-admin is rejected with 403.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.llm.costs import router as costs_router
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.tenant import router as tenant_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager


@pytest.fixture
def auth_client():
    manager = APIKeyManager()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(tenant_router)
    app.include_router(costs_router)
    try:
        yield TestClient(app), manager
    finally:
        configure_musia_auth(None)


def _key(manager: APIKeyManager, scopes: set[str]) -> str:
    raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset(scopes))
    return raw


def _hdr(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_list_tenants_rejects_non_admin(auth_client):
    client, manager = auth_client
    resp = client.get("/api/v1/tenants", headers=_hdr(_key(manager, {"musia.read"})))
    assert resp.status_code == 403
    assert "musia.admin" in resp.text


def test_list_tenants_allows_admin(auth_client):
    client, manager = auth_client
    resp = client.get("/api/v1/tenants", headers=_hdr(_key(manager, {"musia.admin"})))
    assert resp.status_code != 403


def test_top_spenders_rejects_non_admin(auth_client):
    client, manager = auth_client
    resp = client.get("/api/v1/costs/top-spenders", headers=_hdr(_key(manager, {"musia.read"})))
    assert resp.status_code == 403


def test_top_spenders_allows_admin(auth_client):
    client, manager = auth_client
    resp = client.get("/api/v1/costs/top-spenders", headers=_hdr(_key(manager, {"musia.admin"})))
    assert resp.status_code != 403
