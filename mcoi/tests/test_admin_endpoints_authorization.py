"""Authorization regression for privileged administrative endpoints.

Tenant-lifecycle / budget / identity / org / pilot / god-mode endpoints took a
body tenant_id and performed an administrative mutation with NO authorization --
e.g. a caller could set its own tenant budget to unlimited (defeating hard budget
enforcement), zero a victim's budget (DoS), create identities, or issue god-mode
tickets. They now depend on require_admin (the musia.admin scope), matching the
pattern already used by musia_tenants. In dev mode (no auth configured) the scope
check is a no-op, so existing suites are unaffected; in auth mode a non-admin
caller is rejected with 403 before the mutation runs.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.tenant import router as tenant_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager


@pytest.fixture
def auth_tenant_client():
    manager = APIKeyManager()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(tenant_router)
    try:
        yield TestClient(app), manager
    finally:
        configure_musia_auth(None)


def _key(manager: APIKeyManager, scopes: set[str]) -> str:
    raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset(scopes))
    return raw


def test_create_tenant_budget_rejects_non_admin_scope(auth_tenant_client):
    client, manager = auth_tenant_client
    body = {"tenant_id": "tenant-b", "max_cost": 999999.0, "max_calls": 1000000}
    write_key = _key(manager, {"musia.write"})

    denied = client.post(
        "/api/v1/tenant/budget", json=body,
        headers={"Authorization": f"Bearer {write_key}"},
    )

    assert denied.status_code == 403
    assert "musia.admin" in denied.text


def test_create_tenant_budget_allows_admin_scope(auth_tenant_client):
    client, manager = auth_tenant_client
    admin_key = _key(manager, {"musia.admin"})

    allowed = client.post(
        "/api/v1/tenant/budget",
        json={"tenant_id": "tenant-a", "max_cost": 100.0, "max_calls": 100},
        headers={"Authorization": f"Bearer {admin_key}"},
    )

    # Admin passes the authorization gate (not a 403 scope denial).
    assert allowed.status_code != 403
