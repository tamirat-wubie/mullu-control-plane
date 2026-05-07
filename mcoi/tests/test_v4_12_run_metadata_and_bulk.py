"""v4.12.0 — run metadata enrichment + bulk delete + runs listing."""
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
    TenantState,
)


# ============================================================
# merge_run metadata enrichment
# ============================================================


def test_merge_run_stamps_default_timestamp_when_omitted():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={})]
    state.merge_run("run-1", constructs)
    ts = constructs[0].metadata.get("run_timestamp")
    assert ts is not None
    # ISO 8601 — basic shape check
    assert "T" in ts


def test_merge_run_uses_provided_timestamp():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={})]
    state.merge_run(
        "run-1", constructs,
        timestamp_iso="2026-04-26T10:00:00+00:00",
    )
    assert constructs[0].metadata["run_timestamp"] == "2026-04-26T10:00:00+00:00"


def test_merge_run_stamps_domain_and_summary():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={}), State(configuration={})]
    state.merge_run(
        "run-1", constructs,
        domain="software_dev",
        summary="fix budget enforcement leak",
    )
    for c in constructs:
        assert c.metadata["run_domain"] == "software_dev"
        assert c.metadata["run_summary"] == "fix budget enforcement leak"


def test_merge_run_omits_optional_fields_when_not_provided():
    """When domain/summary are None, they should not be set on metadata."""
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={})]
    state.merge_run("run-1", constructs)
    assert "run_domain" not in constructs[0].metadata
    assert "run_summary" not in constructs[0].metadata
    # but run_id and run_timestamp are always stamped
    assert constructs[0].metadata["run_id"] == "run-1"
    assert "run_timestamp" in constructs[0].metadata


# ============================================================
# list_runs unit
# ============================================================


def test_list_runs_groups_by_run_id():
    state = TenantState(tenant_id="t")
    a = [State(configuration={}) for _ in range(3)]
    b = [State(configuration={}) for _ in range(2)]
    state.merge_run("run-A", a, domain="software_dev", summary="A")
    state.merge_run("run-B", b, domain="business_process", summary="B")
    runs = state.list_runs()
    assert len(runs) == 2
    by_id = {r["run_id"]: r for r in runs}
    assert by_id["run-A"]["construct_count"] == 3
    assert by_id["run-A"]["domain"] == "software_dev"
    assert by_id["run-A"]["summary"] == "A"
    assert by_id["run-B"]["construct_count"] == 2
    assert by_id["run-B"]["domain"] == "business_process"


def test_list_runs_skips_constructs_without_run_id():
    state = TenantState(tenant_id="t")
    state.graph.register(State(configuration={}))  # no run_id
    state.merge_run("run-X", [State(configuration={})])
    runs = state.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-X"


def test_list_runs_orders_newest_first():
    state = TenantState(tenant_id="t")
    state.merge_run(
        "run-old", [State(configuration={})],
        timestamp_iso="2026-01-01T00:00:00+00:00",
    )
    state.merge_run(
        "run-new", [State(configuration={})],
        timestamp_iso="2026-04-01T00:00:00+00:00",
    )
    state.merge_run(
        "run-mid", [State(configuration={})],
        timestamp_iso="2026-02-15T00:00:00+00:00",
    )
    runs = state.list_runs()
    ids = [r["run_id"] for r in runs]
    assert ids == ["run-new", "run-mid", "run-old"]


def test_list_runs_empty_when_no_runs():
    state = TenantState(tenant_id="t")
    state.graph.register(State(configuration={}))
    assert state.list_runs() == []


# ============================================================
# delete_run unit
# ============================================================


def test_delete_run_removes_all_matching():
    state = TenantState(tenant_id="t")
    constructs = [State(configuration={}) for _ in range(5)]
    state.merge_run("run-X", constructs)
    assert len(state.graph.constructs) == 5

    result = state.delete_run("run-X")
    assert result["deleted"] == 5
    assert result["skipped"] == 0
    assert state.graph.constructs == {}


def test_delete_run_skips_unrelated_constructs():
    state = TenantState(tenant_id="t")
    keep = State(configuration={})
    state.graph.register(keep)
    state.merge_run("run-X", [State(configuration={}) for _ in range(3)])
    state.delete_run("run-X")
    assert len(state.graph.constructs) == 1
    assert keep.id in state.graph.constructs


def test_delete_run_skips_constructs_with_dependents():
    """A run-stamped construct that has dependents (e.g. a manual State that
    references it) must be skipped, not orphaned."""
    state = TenantState(tenant_id="t")
    # Persist a run with one State
    target = State(configuration={})
    state.merge_run("run-X", [target])
    # Manually register a dependent on that state's id
    dependent = State(configuration={})
    state.graph.register(dependent, depends_on=(target.id,))

    result = state.delete_run("run-X")
    assert result["deleted"] == 0
    assert result["skipped"] == 1
    assert str(target.id) in result["skipped_ids"]
    # target still in registry, unorphaned
    assert target.id in state.graph.constructs


def test_delete_run_unknown_run_id_returns_zero():
    state = TenantState(tenant_id="t")
    state.merge_run("run-X", [State(configuration={})])
    result = state.delete_run("run-never-existed")
    assert result["deleted"] == 0
    assert result["skipped"] == 0


# ============================================================
# HTTP integration
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


def test_persisted_run_stamps_domain_and_summary(client):
    run_id = _persist_a_run(client, summary="fix budget leak")
    state = STORE.get("acme")
    assert state is not None
    matching = [c for c in state.graph.constructs.values() if c.metadata.get("run_id") == run_id]
    assert len(matching) > 0
    for c in matching:
        assert c.metadata["run_domain"] == "software_dev"
        assert c.metadata["run_summary"] == "fix budget leak"
        assert "run_timestamp" in c.metadata


def test_persisted_run_each_domain_stamps_correct_domain(client):
    """Run on each of the six domains; verify each construct knows its domain."""
    cases = [
        ("software-dev", {
            "kind": "feature", "summary": "x", "repository": "y",
            "affected_files": ["a.py"],
            "acceptance_criteria": ["c"],
        }, "software_dev"),
        ("business-process", {
            "kind": "approval", "summary": "x", "process_id": "p",
            "initiator": "i", "approval_chain": ["b"],
            "affected_systems": ["s"], "acceptance_criteria": ["c"],
        }, "business_process"),
        ("scientific-research", {
            "kind": "analysis", "summary": "x", "study_id": "s",
            "principal_investigator": "p", "peer_reviewers": ["r"],
            "affected_corpus": ["d"], "acceptance_criteria": ["c"],
        }, "scientific_research"),
        ("manufacturing", {
            "kind": "quality_inspection", "summary": "x", "line_id": "l",
            "operator_id": "o", "quality_engineer": "qe",
            "iso_certifications": ["9001"], "affected_part_numbers": ["pn"],
            "acceptance_criteria": ["c"],
        }, "manufacturing"),
        ("healthcare", {
            "kind": "assessment", "summary": "x", "encounter_id": "e",
            "primary_clinician": "c", "patient_consented": True,
            "consent_kind": "written", "affected_records": ["r"],
            "acceptance_criteria": ["c"],
        }, "healthcare"),
        ("education", {
            "kind": "grading", "summary": "x", "course_id": "c",
            "instructor": "i", "affected_learners": ["s"],
            "learning_objectives": ["L"], "acceptance_criteria": ["c"],
            "accessibility_requirements": ["a"],
        }, "education"),
    ]
    for path, payload, expected_domain in cases:
        tenant = f"tenant-{path}"
        r = client.post(
            f"/domains/{path}/process?persist_run=true",
            headers={"X-Tenant-ID": tenant},
            json=payload,
        )
        rid = r.json()["run_id"]
        state = STORE.get(tenant)
        matching = [c for c in state.graph.constructs.values() if c.metadata.get("run_id") == rid]
        assert all(c.metadata["run_domain"] == expected_domain for c in matching)


# ---- /musia/tenants/{id}/runs ----


def test_list_runs_endpoint_returns_runs(client):
    rid_a = _persist_a_run(client, tenant="acme", summary="fix A")
    rid_b = _persist_a_run(client, tenant="acme", summary="fix B")
    r = client.get("/musia/tenants/acme/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme"
    assert body["total_runs"] == 2
    ids = {run["run_id"] for run in body["runs"]}
    assert ids == {rid_a, rid_b}


def test_list_runs_endpoint_carries_metadata(client):
    rid = _persist_a_run(client, tenant="acme", summary="audit me")
    body = client.get("/musia/tenants/acme/runs").json()
    found = next(r for r in body["runs"] if r["run_id"] == rid)
    assert found["domain"] == "software_dev"
    assert found["summary"] == "audit me"
    assert found["timestamp"] is not None
    assert found["construct_count"] > 0


def test_list_runs_404_for_unknown_tenant(client):
    r = client.get("/musia/tenants/never-existed/runs")
    assert r.status_code == 404


def test_list_runs_excludes_direct_writes(client):
    """A direct POST /constructs/state isn't a run; it shouldn't appear."""
    # Direct write
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Domain run with persist
    rid = _persist_a_run(client, tenant="acme")
    body = client.get("/musia/tenants/acme/runs").json()
    assert body["total_runs"] == 1
    assert body["runs"][0]["run_id"] == rid


# ---- DELETE /constructs/by-run/{run_id} ----


def test_bulk_delete_removes_run_constructs(client):
    rid = _persist_a_run(client, tenant="acme")
    pre_total = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
    ).json()["total"]
    assert pre_total > 0

    r = client.delete(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme"
    assert body["run_id"] == rid
    assert body["deleted"] > 0
    assert body["skipped"] == 0
    # Now zero matching
    post = client.get(
        f"/constructs?run_id={rid}",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    assert post["total"] == 0


def test_bulk_delete_unknown_run_id_returns_zero_counts(client):
    r = client.delete(
        "/constructs/by-run/run-never-existed",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == 0
    assert body["skipped"] == 0


def test_bulk_delete_does_not_touch_other_runs(client):
    rid_a = _persist_a_run(client, tenant="acme", summary="A")
    rid_b = _persist_a_run(client, tenant="acme", summary="B")
    client.delete(
        f"/constructs/by-run/{rid_a}",
        headers={"X-Tenant-ID": "acme"},
    )
    # B's constructs still present
    body = client.get(
        f"/constructs?run_id={rid_b}",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    assert body["total"] > 0


def test_bulk_delete_per_tenant_isolated(client):
    rid = _persist_a_run(client, tenant="tenant-a")
    # tenant-b cannot delete tenant-a's run (run_id won't match in tenant-b's registry)
    r = client.delete(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "tenant-b"},
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == 0
    # tenant-a's constructs still intact
    body = client.get(
        f"/constructs?run_id={rid}",
        headers={"X-Tenant-ID": "tenant-a"},
    ).json()
    assert body["total"] > 0


def test_bulk_delete_does_not_remove_direct_writes(client):
    # Direct write
    s = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    ).json()
    rid = _persist_a_run(client, tenant="acme")
    client.delete(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    # Direct-write construct still there
    r = client.get(
        f"/constructs/{s['id']}",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200


def test_runs_endpoint_after_bulk_delete_omits_deleted_run(client):
    rid_a = _persist_a_run(client, tenant="acme")
    rid_b = _persist_a_run(client, tenant="acme")
    client.delete(
        f"/constructs/by-run/{rid_a}",
        headers={"X-Tenant-ID": "acme"},
    )
    body = client.get("/musia/tenants/acme/runs").json()
    ids = {r["run_id"] for r in body["runs"]}
    assert ids == {rid_b}
