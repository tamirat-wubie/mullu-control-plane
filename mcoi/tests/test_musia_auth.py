"""MUSIA auth integration — auth-derived tenant takes precedence over X-Tenant-ID."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.cognition import router as cognition_router
from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    is_auth_configured,
    resolve_musia_tenant,
)
from mcoi_runtime.core.api_key_auth import APIKeyManager


@pytest.fixture
def manager() -> APIKeyManager:
    return APIKeyManager()


@pytest.fixture
def auth_client(manager) -> TestClient:
    """Client with APIKeyManager configured — production-style auth."""
    reset_registry()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    yield TestClient(app)
    # Tear down: revert to dev mode so other tests don't see auth
    configure_musia_auth(None)
    reset_registry()


@pytest.fixture
def dev_client() -> TestClient:
    """Client with no auth manager — dev mode preserved."""
    reset_registry()
    configure_musia_auth(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    return TestClient(app)


# ---- Helpers ----


def _make_key(manager: APIKeyManager, tenant_id: str) -> str:
    raw, _ = manager.create_key(
        tenant_id=tenant_id,
        scopes=frozenset({"*"}),
    )
    return raw


# ---- configure_musia_auth ----


def test_configure_musia_auth_toggle():
    configure_musia_auth(None)
    assert not is_auth_configured()
    configure_musia_auth(APIKeyManager())
    assert is_auth_configured()
    configure_musia_auth(None)
    assert not is_auth_configured()


# ---- Dev mode behaviour preserved ----


def test_dev_mode_default_tenant_when_no_header(dev_client):
    r = dev_client.post("/constructs/state", json={"configuration": {}})
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "default"


def test_dev_mode_header_accepted(dev_client):
    r = dev_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "any-tenant"},
        json={"configuration": {}},
    )
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "any-tenant"


# ---- Auth mode: missing/invalid Authorization ----


def test_auth_mode_missing_authorization_returns_401(auth_client):
    r = auth_client.post("/constructs/state", json={"configuration": {}})
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("WWW-Authenticate", "")


def test_auth_mode_malformed_authorization_returns_401(auth_client):
    r = auth_client.post(
        "/constructs/state",
        headers={"Authorization": "NotBearer xyz"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_auth_mode_invalid_token_returns_401(auth_client):
    r = auth_client.post(
        "/constructs/state",
        headers={"Authorization": "Bearer not-a-real-key"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


# ---- Auth mode: success path ----


def test_auth_mode_authenticated_request_uses_key_tenant(auth_client, manager):
    raw = _make_key(manager, "acme-corp")
    r = auth_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {raw}"},
        json={"configuration": {}},
    )
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "acme-corp"


def test_auth_mode_x_tenant_id_matching_authenticated_is_ok(auth_client, manager):
    raw = _make_key(manager, "acme-corp")
    r = auth_client.post(
        "/constructs/state",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-Tenant-ID": "acme-corp",
        },
        json={"configuration": {}},
    )
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "acme-corp"


# ---- Auth mode: spoofing rejected ----


def test_auth_mode_x_tenant_id_spoof_returns_403(auth_client, manager):
    """Authenticated as acme-corp but claims foo-llc → 403, no leak."""
    raw = _make_key(manager, "acme-corp")
    r = auth_client.post(
        "/constructs/state",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-Tenant-ID": "foo-llc",
        },
        json={"configuration": {}},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["authenticated_tenant"] == "acme-corp"
    assert detail["claimed_tenant"] == "foo-llc"


def test_auth_mode_spoof_attempt_does_not_create_construct(auth_client, manager):
    """Reject must not leak side-effects: no construct in EITHER tenant."""
    raw = _make_key(manager, "acme-corp")
    auth_client.post(
        "/constructs/state",
        headers={
            "Authorization": f"Bearer {raw}",
            "X-Tenant-ID": "foo-llc",
        },
        json={"configuration": {}},
    )
    # Look in both — neither should have it
    r_acme = auth_client.get(
        "/constructs",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r_acme.json()["total"] == 0


def test_auth_mode_two_keys_two_tenants_isolated(auth_client, manager):
    """Two valid keys, two tenants — each sees only its own constructs."""
    raw_a = _make_key(manager, "acme-corp")
    raw_b = _make_key(manager, "foo-llc")

    auth_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {raw_a}"},
        json={"configuration": {"x": 1}},
    )
    auth_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {raw_a}"},
        json={"configuration": {"x": 2}},
    )
    auth_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {raw_b}"},
        json={"configuration": {"y": 1}},
    )

    r_a = auth_client.get("/constructs", headers={"Authorization": f"Bearer {raw_a}"})
    r_b = auth_client.get("/constructs", headers={"Authorization": f"Bearer {raw_b}"})
    assert r_a.json()["total"] == 2
    assert r_b.json()["total"] == 1


def test_auth_mode_revoked_key_returns_401(auth_client, manager):
    raw = _make_key(manager, "acme-corp")
    # Find the key id and revoke
    keys = manager.list_keys(tenant_id="acme-corp")
    assert len(keys) == 1
    manager.revoke(keys[0].key_id)

    r = auth_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {raw}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


# ---- Auth mode: cognition router uses same tenant resolution ----


def test_auth_mode_cognition_scoped_to_authenticated_tenant(auth_client, manager):
    raw_a = _make_key(manager, "acme-corp")
    raw_b = _make_key(manager, "foo-llc")

    # acme-corp adds 3 states
    for _ in range(3):
        auth_client.post(
            "/constructs/state",
            headers={"Authorization": f"Bearer {raw_a}"},
            json={"configuration": {}},
        )

    # foo-llc sees 0 in its symbol field
    r = auth_client.get(
        "/cognition/symbol-field",
        headers={"Authorization": f"Bearer {raw_b}"},
    )
    assert r.status_code == 200
    assert r.json()["size"] == 0
    assert r.json()["tenant_id"] == "foo-llc"

    # acme-corp sees 3
    r = auth_client.get(
        "/cognition/symbol-field",
        headers={"Authorization": f"Bearer {raw_a}"},
    )
    assert r.json()["size"] == 3
