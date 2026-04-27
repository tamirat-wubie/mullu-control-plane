"""v4.11.0 — persist_run audit trail + run_id queries."""
from __future__ import annotations

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
    TenantQuota,
    TenantState,
)


# ============================================================
# TenantState.merge_run unit tests
# ============================================================


def test_merge_run_stamps_metadata_on_each_construct():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={"x": i}) for i in range(3)]
    ok, _ = state.merge_run("run-abc", constructs)
    assert ok
    for c in constructs:
        assert c.metadata["run_id"] == "run-abc"


def test_merge_run_inserts_into_graph():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={}) for _ in range(3)]
    state.merge_run("run-1", constructs)
    assert len(state.graph.constructs) == 3
    for c in constructs:
        assert c.id in state.graph.constructs


def test_merge_run_blocked_by_lifetime_quota():
    state = TenantState(tenant_id="t", quota=TenantQuota(max_constructs=5))
    state.graph.register(State(configuration={}))
    state.graph.register(State(configuration={}))
    state.graph.register(State(configuration={}))
    # 3 already registered; merge of 3 would total 6 > max 5
    new = [State(configuration={}) for _ in range(3)]
    ok, reason = state.merge_run("run-x", new)
    assert not ok
    assert "max_constructs" in reason
    # Atomic: nothing was added
    assert len(state.graph.constructs) == 3


def test_merge_run_atomic_no_partial_inserts_on_block():
    state = TenantState(tenant_id="t", quota=TenantQuota(max_constructs=2))
    state.graph.register(State(configuration={}))
    new = [State(configuration={}) for _ in range(3)]
    ok, _ = state.merge_run("run-x", new)
    assert not ok
    # State graph still has 1 construct (the original); none of the 3 added
    assert len(state.graph.constructs) == 1


def test_merge_run_unlimited_quota_always_succeeds():
    state = TenantState(tenant_id="t")  # default quota = unlimited
    state.merge_run("run-1", [State(configuration={}) for _ in range(100)])
    assert len(state.graph.constructs) == 100


def test_merge_run_does_not_consume_rate_limit_slot():
    """Cycle constructs are derived audit artifacts; the original write that
    triggered the run already consumed (or skipped) a rate limit slot."""
    state = TenantState(
        tenant_id="t",
        quota=TenantQuota(max_writes_per_window=10, window_seconds=60),
    )
    constructs = [State(configuration={}) for _ in range(5)]
    state.merge_run("run-1", constructs)
    # Deque is still empty — merge_run does not call record_write
    assert len(state._recent_writes) == 0


# ============================================================
# HTTP /domains/<name>/process?persist_run=true
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


def test_default_persist_run_false_yields_null_run_id(client):
    r = client.post(
        "/domains/software-dev/process",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "fix x",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        },
    )
    assert r.status_code == 200
    assert r.json()["run_id"] is None


def test_persist_run_true_returns_run_id(client):
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "fix x",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] is not None
    assert body["run_id"].startswith("run-")


def test_persist_run_creates_constructs_in_registry(client):
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "fix x",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        },
    )
    run_id = r.json()["run_id"]

    # Constructs from the run are now queryable
    r = client.get(
        f"/constructs?run_id={run_id}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    # Every returned construct has run_id stamped
    # (the API doesn't expose metadata, but we can check via the underlying state)
    state = STORE.get("acme")
    assert state is not None
    for c in state.graph.constructs.values():
        assert c.metadata.get("run_id") == run_id


def test_run_id_filter_isolates_runs(client):
    """Two runs in the same tenant — each run's constructs queryable separately."""
    r1 = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "fix x",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        },
    )
    r2 = client.post(
        "/domains/business-process/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "approval",
            "summary": "approve y",
            "process_id": "p1",
            "initiator": "i",
            "approval_chain": ["a"],
            "affected_systems": ["s"],
            "acceptance_criteria": ["c"],
        },
    )
    rid1 = r1.json()["run_id"]
    rid2 = r2.json()["run_id"]
    assert rid1 != rid2

    # Run 1 query returns only run 1's constructs
    body1 = client.get(
        f"/constructs?run_id={rid1}",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    body2 = client.get(
        f"/constructs?run_id={rid2}",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    assert body1["total"] > 0
    assert body2["total"] > 0
    rid1_ids = {c["id"] for c in body1["constructs"]}
    rid2_ids = {c["id"] for c in body2["constructs"]}
    assert rid1_ids.isdisjoint(rid2_ids)


def test_persist_run_per_tenant_isolated(client):
    """Constructs persisted for tenant A must not appear in tenant B's queries."""
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "tenant-a"},
        json={
            "kind": "bug_fix",
            "summary": "fix",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["c"],
        },
    )
    rid = r.json()["run_id"]

    # tenant-b cannot see tenant-a's run
    r = client.get(
        f"/constructs?run_id={rid}",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert r.json()["total"] == 0


def test_persist_run_quota_rejection_flagged_not_failed(client):
    """When persist_run=true but quota is exhausted, the cycle still returns
    its result; the merge is rejected with a risk flag and run_id is null.
    The user-visible cycle outcome (governance_status, plan, etc.) is preserved.
    """
    # Set a tight quota — only 1 construct allowed
    client.put(
        "/musia/tenants/acme/quota",
        json={"max_constructs": 1},
    )
    # Manually fill the registry to its cap
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )

    # Now run a domain with persist_run — merge should reject (12+ > 1)
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "fix",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["c"],
        },
    )
    assert r.status_code == 200  # cycle ran
    body = r.json()
    assert body["run_id"] is None  # merge rejected
    assert any("persist_run_rejected" in f for f in body["risk_flags"])
    # Registry still has only the original 1 construct (atomic merge)
    state = STORE.get("acme")
    assert state is not None
    assert len(state.graph.constructs) == 1


def test_persist_run_works_for_all_six_domains(client):
    """Every domain endpoint accepts ?persist_run=true and produces a run_id."""
    cases = [
        ("software-dev", {
            "kind": "feature", "summary": "x", "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["test_passes"],
        }),
        ("business-process", {
            "kind": "approval", "summary": "x", "process_id": "p",
            "initiator": "i", "approval_chain": ["b"],
            "affected_systems": ["s"], "acceptance_criteria": ["c"],
        }),
        ("scientific-research", {
            "kind": "analysis", "summary": "x", "study_id": "s",
            "principal_investigator": "p", "peer_reviewers": ["r"],
            "affected_corpus": ["d"], "acceptance_criteria": ["c"],
        }),
        ("manufacturing", {
            "kind": "quality_inspection", "summary": "x", "line_id": "l",
            "operator_id": "o", "quality_engineer": "qe",
            "iso_certifications": ["9001"], "affected_part_numbers": ["pn"],
            "acceptance_criteria": ["c"],
        }),
        ("healthcare", {
            "kind": "assessment", "summary": "x", "encounter_id": "e",
            "primary_clinician": "c", "patient_consented": True,
            "consent_kind": "written", "affected_records": ["r"],
            "acceptance_criteria": ["c"],
        }),
        ("education", {
            "kind": "grading", "summary": "x", "course_id": "c",
            "instructor": "i", "affected_learners": ["s"],
            "learning_objectives": ["L"], "acceptance_criteria": ["c"],
            "accessibility_requirements": ["a"],
        }),
    ]
    seen_run_ids: set[str] = set()
    for path, payload in cases:
        # Use a distinct tenant per domain to avoid quota collision
        tenant = f"tenant-for-{path}"
        r = client.post(
            f"/domains/{path}/process?persist_run=true",
            headers={"X-Tenant-ID": tenant},
            json=payload,
        )
        assert r.status_code == 200, f"{path}: {r.text}"
        rid = r.json()["run_id"]
        assert rid is not None, f"{path}: persist_run yielded no run_id"
        assert rid not in seen_run_ids
        seen_run_ids.add(rid)


def test_run_id_filter_returns_zero_when_unknown(client):
    r = client.get(
        "/constructs?run_id=run-never-existed",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_run_id_filter_combines_with_tier_filter(client):
    r = client.post(
        "/domains/software-dev/process?persist_run=true",
        headers={"X-Tenant-ID": "acme"},
        json={
            "kind": "bug_fix",
            "summary": "x",
            "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["c"],
        },
    )
    rid = r.json()["run_id"]
    # Tier 1 filter on run_id query: only Tier 1 constructs from this run
    r = client.get(
        f"/constructs?run_id={rid}&tier=1",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    for c in body["constructs"]:
        assert c["tier"] == 1


def test_capture_parameter_default_no_capture(client):
    """capture defaults to None; cycle runs with no overhead."""
    from mcoi_runtime.domain_adapters import (
        SoftwareRequest,
        SoftwareWorkKind,
        software_run_with_ucja,
    )

    req = SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="x",
        repository="y",
        affected_files=("a.py",),
        acceptance_criteria=("c",),
    )
    out = software_run_with_ucja(req)  # no capture
    assert out.governance_status == "approved"


def test_capture_parameter_collects_constructs():
    """Direct adapter call with capture=[] returns the cycle's constructs."""
    from mcoi_runtime.domain_adapters import (
        SoftwareRequest,
        SoftwareWorkKind,
        software_run_with_ucja,
    )

    req = SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="x",
        repository="y",
        affected_files=("a.py",),
        acceptance_criteria=("c",),
    )
    captured: list = []
    out = software_run_with_ucja(req, capture=captured)
    assert out.governance_status == "approved"
    # Cycle produces ~12 constructs across all 5 tiers
    assert len(captured) >= 10
    # Mix of tiers
    tiers = {c.tier.value for c in captured}
    assert 1 in tiers  # State, Boundary, etc.
    assert 5 in tiers  # Observation, Inference, Decision, Execution
