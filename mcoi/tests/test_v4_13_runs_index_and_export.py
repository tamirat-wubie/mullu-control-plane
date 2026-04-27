"""v4.13.0 — runs index + run export endpoint."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.domains import router as domains_router
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.substrate.constructs import State
from mcoi_runtime.substrate.registry_store import (
    STORE,
    TenantState,
    configure_persistence,
)


# ============================================================
# _runs_index correctness
# ============================================================


def test_runs_index_populated_on_merge():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={}) for _ in range(3)]
    state.merge_run("run-A", constructs)
    assert "run-A" in state._runs_index
    assert len(state._runs_index["run-A"]) == 3
    for c in constructs:
        assert c.id in state._runs_index["run-A"]


def test_runs_index_disjoint_across_runs():
    state = TenantState(tenant_id="t")
    a = [State(configuration={}) for _ in range(2)]
    b = [State(configuration={}) for _ in range(3)]
    state.merge_run("run-A", a)
    state.merge_run("run-B", b)
    assert state._runs_index["run-A"].isdisjoint(state._runs_index["run-B"])


def test_runs_index_empty_when_no_runs_persisted():
    state = TenantState(tenant_id="t")
    state.graph.register(State(configuration={}))  # direct write
    assert state._runs_index == {}


def test_runs_index_scrubbed_on_delete_run():
    state = TenantState(tenant_id="t")
    state.merge_run("run-X", [State(configuration={}) for _ in range(4)])
    state.delete_run("run-X")
    # Run entry removed entirely once empty
    assert "run-X" not in state._runs_index


def test_runs_index_partial_after_skip():
    """If delete_run skips constructs (live dependents), the index keeps them."""
    state = TenantState(tenant_id="t")
    target = State(configuration={})
    state.merge_run("run-X", [target])
    # Make target undeletable by registering a dependent
    state.graph.register(State(configuration={}), depends_on=(target.id,))
    state.delete_run("run-X")
    # Skip kept the construct → index entry should still hold target.id
    assert "run-X" in state._runs_index
    assert target.id in state._runs_index["run-X"]


def test_constructs_in_run_returns_members():
    state = TenantState(tenant_id="t")
    a = [State(configuration={"i": i}) for i in range(3)]
    state.merge_run("run-A", a)
    members = state.constructs_in_run("run-A")
    assert len(members) == 3
    member_ids = {c.id for c in members}
    assert member_ids == {c.id for c in a}


def test_constructs_in_run_returns_empty_for_unknown():
    state = TenantState(tenant_id="t")
    assert state.constructs_in_run("run-never") == []


# ============================================================
# list_runs uses the index
# ============================================================


def test_list_runs_uses_index_metadata_from_any_member():
    """All members of a run share the same metadata; sampling any one works."""
    state = TenantState(tenant_id="t")
    state.merge_run(
        "run-X", [State(configuration={}) for _ in range(5)],
        domain="software_dev", summary="X",
    )
    runs = state.list_runs()
    assert len(runs) == 1
    r = runs[0]
    assert r["run_id"] == "run-X"
    assert r["domain"] == "software_dev"
    assert r["summary"] == "X"
    assert r["construct_count"] == 5


def test_list_runs_after_delete_run_omits_deleted():
    state = TenantState(tenant_id="t")
    state.merge_run("run-A", [State(configuration={})])
    state.merge_run("run-B", [State(configuration={})])
    state.delete_run("run-A")
    runs = state.list_runs()
    assert {r["run_id"] for r in runs} == {"run-B"}


# ============================================================
# Index rebuild on persistence load
# ============================================================


def test_runs_index_rebuilt_on_load(tmp_path: Path):
    configure_persistence(str(tmp_path))
    try:
        STORE.reset_all()
        state = STORE.get_or_create("acme")
        state.merge_run(
            "run-A", [State(configuration={}) for _ in range(3)],
            domain="software_dev", summary="x",
        )
        state.merge_run(
            "run-B", [State(configuration={}) for _ in range(2)],
            domain="business_process", summary="y",
        )
        STORE.snapshot_tenant("acme")

        # Wipe in-memory and reload
        STORE.reset_all()
        STORE.load_tenant("acme")
        reloaded = STORE.get("acme")
        assert reloaded is not None
        # Index reconstructed
        assert "run-A" in reloaded._runs_index
        assert "run-B" in reloaded._runs_index
        assert len(reloaded._runs_index["run-A"]) == 3
        assert len(reloaded._runs_index["run-B"]) == 2
        # And list_runs / delete_run / constructs_in_run all work
        runs = reloaded.list_runs()
        assert len(runs) == 2
        members_a = reloaded.constructs_in_run("run-A")
        assert len(members_a) == 3
    finally:
        configure_persistence(None)
        STORE.reset_all()


def test_rebuild_runs_index_idempotent():
    """Calling _rebuild_runs_index multiple times produces the same result."""
    state = TenantState(tenant_id="t")
    state.merge_run("run-X", [State(configuration={}) for _ in range(3)])
    snapshot = {k: set(v) for k, v in state._runs_index.items()}
    state._rebuild_runs_index()
    assert {k: set(v) for k, v in state._runs_index.items()} == snapshot


def test_rebuild_runs_index_handles_no_runs():
    state = TenantState(tenant_id="t")
    state.graph.register(State(configuration={}))
    state._rebuild_runs_index()
    assert state._runs_index == {}


# ============================================================
# HTTP /constructs/by-run/{run_id} GET (export)
# ============================================================


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(domains_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app)
    reset_registry()


def _persist_a_run(client: TestClient, tenant: str = "acme",
                   summary: str = "fix x") -> str:
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": tenant},
        json={
            "kind": "bug_fix",
            "summary": summary,
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["c"],
        },
    )
    return r.json()["run_id"]


def test_export_endpoint_returns_full_run(client):
    rid = _persist_a_run(client, summary="fix budget leak")
    r = client.get(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme"
    assert body["run_id"] == rid
    assert body["domain"] == "software_dev"
    assert body["summary"] == "fix budget leak"
    assert body["timestamp"] is not None
    assert body["construct_count"] > 0
    assert len(body["constructs"]) == body["construct_count"]
    # Each construct has the standard payload shape
    sample = body["constructs"][0]
    assert "id" in sample
    assert "type" in sample
    assert "tier" in sample


def test_export_endpoint_unknown_run_returns_empty(client):
    """Unknown run returns 200 with empty constructs (race-tolerant for callers iterating runs)."""
    r = client.get(
        "/constructs/by-run/run-never-existed",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run-never-existed"
    assert body["construct_count"] == 0
    assert body["constructs"] == []
    assert body["domain"] is None


def test_export_endpoint_per_tenant_isolated(client):
    rid = _persist_a_run(client, tenant="tenant-a")
    # tenant-b can't see tenant-a's run
    r = client.get(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert r.status_code == 200
    assert r.json()["construct_count"] == 0


def test_export_endpoint_after_delete_returns_empty(client):
    rid = _persist_a_run(client, tenant="acme")
    client.delete(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    r = client.get(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    assert r.json()["construct_count"] == 0


def test_export_constructs_share_run_metadata(client):
    """Sanity check: every exported construct has the same run metadata."""
    rid = _persist_a_run(client, summary="audit me")
    r = client.get(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    # Pull metadata from each via the registry directly
    state = STORE.get("acme")
    members = state.constructs_in_run(rid)
    for c in members:
        assert c.metadata["run_id"] == rid
        assert c.metadata["run_domain"] == "software_dev"
        assert c.metadata["run_summary"] == "audit me"


# ============================================================
# Existing filter still works (regression check)
# ============================================================


def test_existing_run_id_filter_still_works(client):
    rid = _persist_a_run(client, tenant="acme")
    r = client.get(
        f"/constructs?run_id={rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    # All returned constructs have the same run_id (verified by registry side)
    state = STORE.get("acme")
    for c_payload in body["constructs"]:
        from uuid import UUID
        cid = UUID(c_payload["id"])
        assert state.graph.constructs[cid].metadata["run_id"] == rid


def test_run_id_filter_combined_with_tier(client):
    rid = _persist_a_run(client, tenant="acme")
    r = client.get(
        f"/constructs?run_id={rid}&tier=1",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["total"] > 0
    for c in body["constructs"]:
        assert c["tier"] == 1


# ============================================================
# Performance smoke (asserts O(M), not O(N))
# ============================================================


def test_index_lookup_independent_of_total_construct_count():
    """Even with thousands of unrelated constructs, by-run lookup is fast.

    Regression-style assertion: build a registry with 5000 unrelated direct
    writes plus one small run; querying that run should not scan all 5000.
    We can't easily measure "didn't scan" but we can verify the result is
    correct and the index has the expected size.
    """
    state = TenantState(tenant_id="t")
    # 5000 direct writes — these don't go in the index
    for i in range(5000):
        state.graph.register(State(configuration={"i": i}))
    # One small run
    run_constructs = [State(configuration={"r": i}) for i in range(5)]
    state.merge_run("run-1", run_constructs)
    # Index has exactly the run members, not all 5005
    assert len(state._runs_index["run-1"]) == 5
    # Lookup returns those 5
    assert len(state.constructs_in_run("run-1")) == 5
    # list_runs has 1 entry, not 5005
    runs = state.list_runs()
    assert len(runs) == 1
    assert runs[0]["construct_count"] == 5
