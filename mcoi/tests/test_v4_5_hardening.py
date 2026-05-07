"""v4.5.0 hardening — auto-snapshot, JWT auth, scope enforcement."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Iterator

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
    configure_musia_jwt,
)
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager
from mcoi_runtime.governance.auth.jwt import JWTAlgorithm, JWTAuthenticator, OIDCConfig
from mcoi_runtime.substrate.registry_store import (
    STORE,
    configure_persistence,
)


# ============================================================
# Auto-snapshot
# ============================================================


@pytest.fixture
def autosnapshot_client(tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    """Client with auto-snapshot enabled."""
    reset_registry()
    snapshots = tmp_path / "snapshots"
    configure_persistence(str(snapshots), auto_snapshot=True)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app), snapshots
    configure_persistence(None)
    reset_registry()


def test_auto_snapshot_writes_after_create(autosnapshot_client):
    client, snapshots = autosnapshot_client
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {"x": 1}},
    )
    assert r.status_code == 201
    assert (snapshots / "registry-acme.json").exists()


def test_auto_snapshot_writes_after_delete(autosnapshot_client):
    client, snapshots = autosnapshot_client
    s = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {"x": 1}},
    ).json()

    # Read the snapshot at this point
    path = snapshots / "registry-acme.json"
    pre_payload = json.loads(path.read_text("utf-8"))
    assert len(pre_payload["constructs"]) == 1

    # Delete; snapshot should now show 0
    client.delete(
        f"/constructs/{s['id']}",
        headers={"X-Tenant-ID": "acme"},
    )
    post_payload = json.loads(path.read_text("utf-8"))
    assert len(post_payload["constructs"]) == 0


def test_auto_snapshot_per_tenant_isolation(autosnapshot_client):
    client, snapshots = autosnapshot_client
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "foo"},
        json={"configuration": {}},
    )
    assert (snapshots / "registry-acme.json").exists()
    assert (snapshots / "registry-foo.json").exists()


def test_auto_snapshot_disabled_does_not_write(tmp_path: Path):
    reset_registry()
    snapshots = tmp_path / "snapshots"
    configure_persistence(str(snapshots), auto_snapshot=False)
    try:
        app = FastAPI()
        app.include_router(constructs_router)
        client = TestClient(app)
        client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
        assert not (snapshots / "registry-acme.json").exists()
    finally:
        configure_persistence(None)
        reset_registry()


def test_auto_snapshot_requires_backend():
    """Enabling auto-snapshot without a backend raises."""
    configure_persistence(None)
    with pytest.raises(RuntimeError, match="persistence backend"):
        STORE.set_auto_snapshot(True)


def test_auto_snapshot_silent_on_save_failure(tmp_path: Path):
    """If the save call raises, the in-memory write must not roll back."""
    reset_registry()
    snapshots = tmp_path / "snapshots"
    configure_persistence(str(snapshots), auto_snapshot=True)
    try:
        # Make the directory unwriteable by deleting it AFTER configure_persistence
        # (the directory was created on init; remove and re-create as a file
        # to force writes to fail, but tolerate platforms where this is hard).
        # Simpler: monkey-patch the backend.save to raise.
        backend = STORE.persistence

        def boom(*a, **kw):
            raise OSError("disk full")

        backend.save = boom

        app = FastAPI()
        app.include_router(constructs_router)
        client = TestClient(app)

        r = client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {"x": 1}},
        )
        # The write itself succeeded (in-memory)
        assert r.status_code == 201
        # The construct is in the registry
        r = client.get("/constructs", headers={"X-Tenant-ID": "acme"})
        assert r.json()["total"] == 1
    finally:
        configure_persistence(None)
        reset_registry()


# ============================================================
# JWT auth
# ============================================================


_JWT_SECRET = "test-secret-musia-v4.5"


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
    """Build an HS256 JWT for testing."""
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


@pytest.fixture
def jwt_authenticator() -> JWTAuthenticator:
    cfg = OIDCConfig(
        issuer="https://issuer.example.com",
        audience="musia",
        signing_key=_JWT_SECRET.encode(),
        allowed_algorithms=frozenset({"HS256"}),
    )
    return JWTAuthenticator(cfg)


@pytest.fixture
def jwt_client(jwt_authenticator) -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)  # disable api-key
    configure_musia_jwt(jwt_authenticator)
    app = FastAPI()
    app.include_router(constructs_router)
    yield TestClient(app)
    configure_musia_jwt(None)
    reset_registry()


def test_jwt_valid_token_authenticates(jwt_client):
    token = _make_jwt(
        _JWT_SECRET,
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["musia.read", "musia.write"],
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {"x": 1}},
    )
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "acme"


def test_jwt_invalid_signature_rejected(jwt_client):
    token = _make_jwt(
        "wrong-secret",
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_jwt_expired_rejected(jwt_client):
    token = _make_jwt(
        _JWT_SECRET,
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
        exp_offset_seconds=-3600,
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_jwt_wrong_issuer_rejected(jwt_client):
    token = _make_jwt(
        _JWT_SECRET,
        issuer="https://malicious.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_jwt_missing_tenant_claim_rejected(jwt_client):
    token = _make_jwt(
        _JWT_SECRET,
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="",  # blank
        scopes=["*"],
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {token}"},
        json={"configuration": {}},
    )
    assert r.status_code == 401


def test_jwt_spoof_x_tenant_id_rejected(jwt_client):
    token = _make_jwt(
        _JWT_SECRET,
        issuer="https://issuer.example.com",
        audience="musia",
        tenant_id="acme",
        scopes=["*"],
    )
    r = jwt_client.post(
        "/constructs/state",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": "foo-corp",
        },
        json={"configuration": {}},
    )
    assert r.status_code == 403


def test_both_authenticators_api_key_takes_priority(jwt_authenticator):
    """When both are configured, API-key wins for keys that match. JWT is
    fallback for unrecognized API keys (which is what JWTs look like).
    """
    reset_registry()
    api_mgr = APIKeyManager()
    raw_api, _ = api_mgr.create_key(
        tenant_id="acme-via-api",
        scopes=frozenset({"*"}),
    )
    configure_musia_auth(api_mgr)
    configure_musia_jwt(jwt_authenticator)
    try:
        app = FastAPI()
        app.include_router(constructs_router)
        client = TestClient(app)

        # API-key request → goes through api_key path
        r = client.post(
            "/constructs/state",
            headers={"Authorization": f"Bearer {raw_api}"},
            json={"configuration": {}},
        )
        assert r.status_code == 201
        assert r.json()["tenant_id"] == "acme-via-api"

        # JWT request → falls through to jwt path
        token = _make_jwt(
            _JWT_SECRET,
            issuer="https://issuer.example.com",
            audience="musia",
            tenant_id="acme-via-jwt",
            scopes=["*"],
        )
        r = client.post(
            "/constructs/state",
            headers={"Authorization": f"Bearer {token}"},
            json={"configuration": {}},
        )
        assert r.status_code == 201
        assert r.json()["tenant_id"] == "acme-via-jwt"
    finally:
        configure_musia_auth(None)
        configure_musia_jwt(None)
        reset_registry()


# ============================================================
# Scope enforcement
# ============================================================


@pytest.fixture
def scoped_client() -> Iterator[tuple[TestClient, APIKeyManager]]:
    reset_registry()
    mgr = APIKeyManager()
    configure_musia_auth(mgr)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app), mgr
    configure_musia_auth(None)
    reset_registry()


def _key(mgr: APIKeyManager, tenant: str, scopes: set[str]) -> str:
    raw, _ = mgr.create_key(tenant_id=tenant, scopes=frozenset(scopes))
    return raw


def test_read_only_key_can_get_but_not_create(scoped_client):
    client, mgr = scoped_client
    # First, create a state with a wildcard key
    admin = _key(mgr, "acme", {"*"})
    s_resp = client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {admin}"},
        json={"configuration": {"x": 1}},
    )
    state_id = s_resp.json()["id"]

    # Read-only key can list and get
    reader = _key(mgr, "acme", {"musia.read"})
    r = client.get("/constructs", headers={"Authorization": f"Bearer {reader}"})
    assert r.status_code == 200
    r = client.get(
        f"/constructs/{state_id}",
        headers={"Authorization": f"Bearer {reader}"},
    )
    assert r.status_code == 200

    # Read-only key cannot create
    r = client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {reader}"},
        json={"configuration": {}},
    )
    assert r.status_code == 403
    assert "musia.write" in r.json()["detail"]["error"]


def test_write_key_cannot_admin(scoped_client):
    client, mgr = scoped_client
    writer = _key(mgr, "acme", {"musia.read", "musia.write"})
    r = client.get("/musia/tenants", headers={"Authorization": f"Bearer {writer}"})
    assert r.status_code == 403
    assert "musia.admin" in r.json()["detail"]["error"]


def test_admin_key_can_admin(scoped_client):
    client, mgr = scoped_client
    admin = _key(mgr, "acme", {"musia.admin"})
    r = client.get("/musia/tenants", headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200


def test_wildcard_key_passes_all_scopes(scoped_client):
    client, mgr = scoped_client
    wild = _key(mgr, "acme", {"*"})
    # Create
    r = client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {wild}"},
        json={"configuration": {}},
    )
    assert r.status_code == 201
    # List
    r = client.get("/constructs", headers={"Authorization": f"Bearer {wild}"})
    assert r.status_code == 200
    # Admin
    r = client.get("/musia/tenants", headers={"Authorization": f"Bearer {wild}"})
    assert r.status_code == 200


def test_dev_mode_bypasses_scope_enforcement():
    """When no auth is configured, scopes are not enforced."""
    reset_registry()
    configure_musia_auth(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(musia_tenants_router)
    client = TestClient(app)

    # No auth, no scope, write succeeds
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 201
    # Admin endpoint also succeeds (dev mode = wildcard scopes)
    r = client.get("/musia/tenants", headers={"X-Tenant-ID": "acme"})
    assert r.status_code == 200

    reset_registry()


def test_scope_failure_includes_subject_and_granted(scoped_client):
    """The 403 detail names the subject and lists granted scopes."""
    client, mgr = scoped_client
    reader = _key(mgr, "acme", {"musia.read"})
    r = client.post(
        "/constructs/state",
        headers={"Authorization": f"Bearer {reader}"},
        json={"configuration": {}},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["subject"].startswith("mk_")
    assert "musia.read" in detail["granted_scopes"]
