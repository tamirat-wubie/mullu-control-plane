"""Multi-tenant registry isolation tests.

Asserts that constructs registered under one tenant are invisible to other
tenants, and that Φ_agent filters installed on one tenant do not leak.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.cognition import router as cognition_router
from mcoi_runtime.app.routers.constructs import (
    install_phi_agent_filter,
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.substrate.phi_gov import PhiAgentFilter


@pytest.fixture
def client() -> TestClient:
    reset_registry()
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    app.include_router(musia_tenants_router)
    return TestClient(app)


# ---- Basic isolation ----


def test_construct_in_tenant_a_invisible_to_tenant_b(client):
    a = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {"x": 1}},
    )
    assert a.status_code == 201
    state_id = a.json()["id"]
    assert a.json()["tenant_id"] == "tenant-a"

    # tenant-b cannot see this construct
    r = client.get(
        f"/constructs/{state_id}",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert r.status_code == 404


def test_list_constructs_scoped_to_tenant(client):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {}},
    )

    r_a = client.get("/constructs", headers={"X-Tenant-ID": "tenant-a"})
    r_b = client.get("/constructs", headers={"X-Tenant-ID": "tenant-b"})
    assert r_a.json()["total"] == 2
    assert r_b.json()["total"] == 1


def test_default_tenant_when_header_absent(client):
    r = client.post("/constructs/state", json={"configuration": {}})
    assert r.status_code == 201
    assert r.json()["tenant_id"] == "default"


def test_construct_create_change_with_cross_tenant_ref_rejected(client):
    """A Change in tenant-b cannot reference a State in tenant-a."""
    s_a = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {}},
    ).json()
    s_b1 = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {}},
    ).json()

    r = client.post(
        "/constructs/change",
        headers={"X-Tenant-ID": "tenant-b"},
        json={
            "state_before_id": s_a["id"],  # cross-tenant ref!
            "state_after_id": s_b1["id"],
            "delta_vector": {},
        },
    )
    assert r.status_code == 400
    assert "tenant-b" in r.json()["detail"]


# ---- Φ_agent isolation ----


def test_phi_agent_filter_isolated_per_tenant(client):
    """A filter installed on tenant-a must not block tenant-b's writes."""
    install_phi_agent_filter(
        PhiAgentFilter(l3=lambda d, c, a: False),
        tenant_id="tenant-a",
    )

    # tenant-a: rejected
    r_a = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {"x": 1}},
    )
    assert r_a.status_code == 403
    assert r_a.json()["detail"]["tenant_id"] == "tenant-a"

    # tenant-b: succeeds (default-permissive)
    r_b = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {"x": 1}},
    )
    assert r_b.status_code == 201
    assert r_b.json()["tenant_id"] == "tenant-b"


# ---- Cognition scope ----


def test_cognition_tension_per_tenant(client):
    # tenant-a: 3 states
    for _ in range(3):
        client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "tenant-a"},
            json={"configuration": {}},
        )
    # tenant-b: 0 states
    r_a = client.get("/cognition/symbol-field", headers={"X-Tenant-ID": "tenant-a"})
    r_b = client.get("/cognition/symbol-field", headers={"X-Tenant-ID": "tenant-b"})
    assert r_a.json()["size"] == 3
    assert r_b.json()["size"] == 0


def test_cognition_run_only_sees_tenant_constructs(client):
    """Cycle in tenant-a must not see tenant-b's constructs."""
    from mcoi_runtime.substrate.constructs import Pattern, Validation
    from mcoi_runtime.substrate.registry_store import STORE

    # Manually register a pending Validation in tenant-a (would create
    # ongoing tension if it leaked into tenant-b)
    state_a = STORE.get_or_create("tenant-a")
    from mcoi_runtime.substrate.constructs import State
    s = State(configuration={})
    state_a.graph.register(s)
    p = Pattern(template_state_id=s.id)
    state_a.graph.register(p)
    v = Validation(target_pattern_id=p.id, criteria=("c",), decision="unknown")
    state_a.graph.register(v)

    # tenant-b runs the cycle: should see no constructs and converge immediately
    r_b = client.post(
        "/cognition/run",
        headers={"X-Tenant-ID": "tenant-b"},
        json={},
    )
    assert r_b.status_code == 200
    assert r_b.json()["proof_state"] == "Pass"
    assert r_b.json()["final_tension"]["total"] == 0.0


# ---- /musia/tenants endpoints ----


def test_list_tenants_summary(client):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {}},
    )

    r = client.get("/musia/tenants")
    body = r.json()
    assert body["tenant_count"] == 2
    by_id = {t["tenant_id"]: t["construct_count"] for t in body["tenants"]}
    assert by_id["tenant-a"] == 1
    assert by_id["tenant-b"] == 2


def test_get_tenant_404_when_unknown(client):
    r = client.get("/musia/tenants/never-existed")
    assert r.status_code == 404


def test_reset_tenant_isolated(client):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"configuration": {}},
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "tenant-b"},
        json={"configuration": {}},
    )

    r = client.delete("/musia/tenants/tenant-a")
    assert r.status_code == 204

    # tenant-a is gone
    assert client.get("/musia/tenants/tenant-a").status_code == 404
    # tenant-b unaffected
    r_b = client.get("/musia/tenants/tenant-b")
    assert r_b.status_code == 200
    assert r_b.json()["construct_count"] == 1


def test_reset_tenant_404_when_unknown(client):
    r = client.delete("/musia/tenants/never-existed")
    assert r.status_code == 404


# ---- TenantedRegistryStore unit tests ----


def test_store_get_or_create_creates_fresh_state():
    from mcoi_runtime.substrate.registry_store import TenantedRegistryStore
    s = TenantedRegistryStore()
    state = s.get_or_create("foo")
    assert state.tenant_id == "foo"
    assert len(state.graph.constructs) == 0


def test_store_get_or_create_returns_same_state_twice():
    from mcoi_runtime.substrate.registry_store import TenantedRegistryStore
    s = TenantedRegistryStore()
    a = s.get_or_create("foo")
    b = s.get_or_create("foo")
    assert a is b


def test_store_rejects_empty_tenant_id():
    from mcoi_runtime.substrate.registry_store import TenantedRegistryStore
    s = TenantedRegistryStore()
    with pytest.raises(ValueError):
        s.get_or_create("")


def test_store_reset_tenant_does_not_affect_others():
    from mcoi_runtime.substrate.registry_store import TenantedRegistryStore
    from mcoi_runtime.substrate.constructs import State
    s = TenantedRegistryStore()
    a = s.get_or_create("a")
    b = s.get_or_create("b")
    a.graph.register(State(configuration={}))
    b.graph.register(State(configuration={}))

    s.reset_tenant("a")
    assert s.get("a") is None
    assert s.get("b") is not None
    assert len(s.get("b").graph.constructs) == 1
