"""Purpose: verify RBAC HTTP endpoints.
Governance scope: RBAC endpoint tests only.
Dependencies: FastAPI test client, server app, access_runtime.
Invariants: identities/roles/bindings are governed; operations are audited.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def test_create_identity(client: TestClient) -> None:
    resp = client.post("/api/v1/rbac/identities", json={
        "identity_id": "rbac-user-001",
        "display_name": "Test User",
        "tenant_id": "t1",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["identity_id"] == "rbac-user-001"
    assert data["governed"] is True
    assert data["enabled"] is True


def test_list_identities(client: TestClient) -> None:
    client.post("/api/v1/rbac/identities", json={
        "identity_id": "rbac-list-user",
        "display_name": "List User",
        "tenant_id": "t1",
    })
    resp = client.get("/api/v1/rbac/identities")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
    assert resp.json()["count"] >= 1


def test_create_role(client: TestClient) -> None:
    resp = client.post("/api/v1/rbac/roles", json={
        "role_id": "rbac-admin",
        "name": "Administrator",
        "permissions": ["read", "write", "execute"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role_id"] == "rbac-admin"
    assert "read" in data["permissions"]
    assert data["governed"] is True


def test_list_roles(client: TestClient) -> None:
    client.post("/api/v1/rbac/roles", json={
        "role_id": "rbac-list-role",
        "name": "List Role",
        "permissions": ["read"],
    })
    resp = client.get("/api/v1/rbac/roles")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_bind_role(client: TestClient) -> None:
    client.post("/api/v1/rbac/identities", json={
        "identity_id": "rbac-bind-user",
        "display_name": "Bind User",
        "tenant_id": "t1",
    })
    client.post("/api/v1/rbac/roles", json={
        "role_id": "rbac-bind-role",
        "name": "Bind Role",
        "permissions": ["read"],
    })
    resp = client.post("/api/v1/rbac/bindings", json={
        "identity_id": "rbac-bind-user",
        "role_id": "rbac-bind-role",
    })
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_rbac_summary(client: TestClient) -> None:
    resp = client.get("/api/v1/rbac/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "identity_count" in data
    assert "role_count" in data
    assert data["governed"] is True


def test_identity_creation_audited(client: TestClient) -> None:
    client.post("/api/v1/rbac/identities", json={
        "identity_id": "rbac-audit-user",
        "display_name": "Audit User",
        "tenant_id": "t1",
    })
    resp = client.get("/api/v1/audit?action=rbac.identity.create&limit=5")
    assert resp.status_code == 200
    assert resp.json().get("count", 0) >= 1
