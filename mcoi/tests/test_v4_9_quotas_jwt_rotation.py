"""v4.9.0 — multi-JWT rotation + tenant construct quotas."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_jwt,
    configured_jwt_authenticators,
)
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager
from mcoi_runtime.governance.auth.jwt import JWTAuthenticator, OIDCConfig
from mcoi_runtime.substrate.registry_store import (
    STORE,
    TenantQuota,
    TenantState,
)


# ============================================================
# Multi-authenticator JWT (rotation support)
# ============================================================


def _make_jwt(
    secret: str,
    *,
    issuer: str,
    audience: str,
    tenant_id: str,
    scopes: list[str] | None = None,
    subject: str = "user-123",
    exp_offset_seconds: int = 3600,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    claims: dict = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": now,
        "exp": now + exp_offset_seconds,
        "tenant_id": tenant_id,
    }
    if scopes is not None:
        claims["scope"] = " ".join(scopes)

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    h_b64 = b64url(json.dumps(header, separators=(",", ":")).encode())
    p_b64 = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{h_b64}.{p_b64}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    s_b64 = b64url(sig)
    return f"{h_b64}.{p_b64}.{s_b64}"


def _authenticator(secret: str) -> JWTAuthenticator:
    return JWTAuthenticator(
        OIDCConfig(
            issuer="https://issuer.example.com",
            audience="musia",
            signing_key=secret.encode(),
            allowed_algorithms=frozenset({"HS256"}),
        ),
    )


@pytest.fixture
def rotation_client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    yield_client_iter = None
    app = FastAPI()
    app.include_router(constructs_router)
    yield TestClient(app)
    configure_musia_jwt(None)
    reset_registry()


def test_configure_musia_jwt_accepts_single_authenticator(rotation_client):
    """Back-compat: passing a single authenticator still works."""
    auth = _authenticator("secret-A")
    configure_musia_jwt(auth)
    assert configured_jwt_authenticators() == [auth]


def test_configure_musia_jwt_accepts_list(rotation_client):
    auth_a = _authenticator("secret-A")
    auth_b = _authenticator("secret-B")
    configure_musia_jwt([auth_a, auth_b])
    configured = configured_jwt_authenticators()
    assert configured == [auth_a, auth_b]


def test_configure_musia_jwt_none_disables(rotation_client):
    configure_musia_jwt(_authenticator("secret"))
    assert len(configured_jwt_authenticators()) == 1
    configure_musia_jwt(None)
    assert configured_jwt_authenticators() == []


def test_old_token_validates_during_rotation_window(rotation_client):
    """Both old and new authenticators active → tokens from either pass."""
    auth_a = _authenticator("secret-A-old")
    auth_b = _authenticator("secret-B-new")
    configure_musia_jwt([auth_a, auth_b])

    token_old = _make_jwt(
        "secret-A-old",
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    token_new = _make_jwt(
        "secret-B-new",
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )

    # Both succeed
    r_old = rotation_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token_old}"},
        json={"configuration": {"k": "old"}},
    )
    assert r_old.status_code == 201

    r_new = rotation_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token_new}"},
        json={"configuration": {"k": "new"}},
    )
    assert r_new.status_code == 201


def test_post_rotation_old_token_rejected(rotation_client):
    """After rotation completes (old removed), old tokens fail."""
    auth_b = _authenticator("secret-B-new")
    configure_musia_jwt([auth_b])

    token_old = _make_jwt(
        "secret-A-old",
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    r = rotation_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token_old}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_first_matching_authenticator_wins(rotation_client):
    """Authenticators tried in order; first match used."""
    auth_a = _authenticator("secret-A")
    auth_b = _authenticator("secret-A")  # same secret, different instance
    configure_musia_jwt([auth_a, auth_b])

    token = _make_jwt(
        "secret-A",
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    r = rotation_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {}},
    )
    assert r.status_code == 201
    # Both would have matched, but only one was used. No way to assert that
    # from the response — just confirming no double-processing.


# ============================================================
# Tenant construct quotas
# ============================================================


@pytest.fixture
def quota_client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)  # dev mode for simpler test setup
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app)
    reset_registry()


# ---- TenantQuota dataclass ----


def test_tenant_quota_default_is_unlimited():
    state = TenantState(tenant_id="x")
    assert state.quota.max_constructs is None
    ok, _ = state.check_quota_for_write()
    assert ok


def test_tenant_quota_rejects_negative():
    with pytest.raises(ValueError, match="max_constructs"):
        TenantQuota(max_constructs=-1)


def test_tenant_quota_zero_blocks_all_writes():
    state = TenantState(tenant_id="x", quota=TenantQuota(max_constructs=0))
    ok, reason = state.check_quota_for_write()
    assert not ok
    assert "0/0" in reason


def test_tenant_quota_at_limit_blocks_next_write():
    from mcoi_runtime.substrate.constructs import State

    state = TenantState(tenant_id="x", quota=TenantQuota(max_constructs=2))
    state.graph.register(State(configuration={}))
    state.graph.register(State(configuration={}))
    ok, reason = state.check_quota_for_write()
    assert not ok
    assert "2/2" in reason


# ---- HTTP enforcement ----


def test_quota_enforcement_returns_429(quota_client):
    quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 2},
    )
    quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Third write should be rejected
    r = quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429
    detail = r.json()["detail"]
    assert "quota" in detail["reason"]
    assert detail["tenant_id"] == "acme"


def test_quota_per_tenant_isolated(quota_client):
    quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 1},
    )
    # acme hits its limit
    quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    r = quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429

    # foo-llc has no quota set → unlimited
    for _ in range(5):
        r = quota_client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "foo-llc"},
            json={"configuration": {}},
        )
        assert r.status_code == 201


def test_quota_endpoint_get(quota_client):
    quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    r = quota_client.get("/musia/tenants/acme/quota")
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme"
    assert body["max_constructs"] is None
    assert body["current_constructs"] == 1
    assert body["headroom"] is None


def test_quota_endpoint_set(quota_client):
    r = quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["max_constructs"] == 100
    assert body["headroom"] == 100


def test_quota_endpoint_set_to_unlimited(quota_client):
    quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 50},
    )
    r = quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": None},
    )
    assert r.status_code == 200
    assert r.json()["max_constructs"] is None
    assert r.json()["headroom"] is None


def test_quota_endpoint_set_negative_rejected_at_pydantic_layer(quota_client):
    """Pydantic validator on max_constructs >= 0 rejects negatives."""
    r = quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": -5},
    )
    assert r.status_code == 422  # FastAPI/Pydantic validation error


def test_quota_endpoint_lower_below_current_count_does_not_evict(quota_client):
    """Setting max below current is permitted; no eviction. Next write blocks."""
    for _ in range(3):
        quota_client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
    # Lower the cap below current count
    r = quota_client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["max_constructs"] == 1
    assert body["current_constructs"] == 3
    assert body["headroom"] == -2

    # The 3 already there are still readable
    r = quota_client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.json()["total"] == 3

    # But writes now blocked
    r = quota_client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429


def test_quota_get_unknown_tenant_404(quota_client):
    r = quota_client.get("/musia/tenants/never-existed/quota")
    assert r.status_code == 404


def test_quota_set_creates_tenant_if_absent(quota_client):
    """PUT /quota on an unknown tenant creates the tenant state."""
    r = quota_client.put(
        "/musia/tenants/brand-new/quota",
        json={"max_constructs": 10},
    )
    assert r.status_code == 200
    # Now GET works
    r = quota_client.get("/musia/tenants/brand-new/quota")
    assert r.status_code == 200
