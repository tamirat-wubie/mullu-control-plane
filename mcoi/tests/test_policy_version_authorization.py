"""Authorization regression for policy-version mutation endpoints.

The policy version registry exposes global governance artifacts ("operator
routes" per the module). Three mutations -- register, promote, rollback -- changed
global policy state with NO authorization, so any caller could register a new
policy version, promote a (possibly malicious) version to active, or roll policy
back to a prior version, defeating governance controls. They now require the
musia.admin scope, matching the other privileged operator endpoints. In dev mode
(no auth configured) the scope check is a no-op; in auth mode a non-admin caller
is rejected with 403 before the mutation runs.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.policy_versions import router as policy_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager


@pytest.fixture
def auth_client():
    manager = APIKeyManager()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(policy_router)
    try:
        yield TestClient(app), manager
    finally:
        configure_musia_auth(None)


def _key(manager: APIKeyManager, scopes: set[str]) -> str:
    raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset(scopes))
    return raw


def _hdr(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_register_policy_version_rejects_non_admin(auth_client):
    client, manager = auth_client
    write_key = _key(manager, {"musia.write"})
    resp = client.post(
        "/api/v1/policies/p1/versions",
        json={"policy_id": "p1", "version": "v1", "rules": []},
        headers=_hdr(write_key),
    )
    assert resp.status_code == 403
    assert "musia.admin" in resp.text


def test_promote_policy_version_rejects_non_admin(auth_client):
    client, manager = auth_client
    write_key = _key(manager, {"musia.write"})
    resp = client.post("/api/v1/policies/p1/versions/v1/promote", headers=_hdr(write_key))
    assert resp.status_code == 403


def test_rollback_policy_version_rejects_non_admin(auth_client):
    client, manager = auth_client
    write_key = _key(manager, {"musia.write"})
    resp = client.post("/api/v1/policies/p1/rollback", headers=_hdr(write_key))
    assert resp.status_code == 403


def test_register_policy_version_allows_admin(auth_client):
    client, manager = auth_client
    admin_key = _key(manager, {"musia.admin"})
    resp = client.post(
        "/api/v1/policies/p1/versions",
        json={"policy_id": "p1", "version": "v1", "rules": []},
        headers=_hdr(admin_key),
    )
    # Admin clears the authorization gate (not a 403 scope denial).
    assert resp.status_code != 403
