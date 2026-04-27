"""v4.14.0 — opt-in pagination across list endpoints."""
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


def _seed_constructs(client: TestClient, n: int, tenant: str = "acme") -> None:
    for i in range(n):
        client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": tenant},
            json={"configuration": {"i": i}},
        )


def _persist_runs(client: TestClient, n: int, tenant: str = "acme") -> list[str]:
    rids = []
    for i in range(n):
        r = client.post(
            "/domains/software-dev/process?persist_run=true",
            headers={"X-Tenant-ID": tenant},
            json={
                "kind": "bug_fix",
                "summary": f"run {i}",
                "repository": "y",
                "affected_files": ["a.py"],
                "acceptance_criteria": ["c"],
            },
        )
        rids.append(r.json()["run_id"])
    return rids


# ============================================================
# GET /constructs pagination
# ============================================================


def test_constructs_default_no_pagination_returns_all(client):
    _seed_constructs(client, 25)
    r = client.get("/constructs", headers={"X-Tenant-ID": "acme"})
    body = r.json()
    assert body["total"] == 25
    assert len(body["constructs"]) == 25
    # Pagination fields all None
    assert body["page"] is None
    assert body["page_size"] is None
    assert body["total_pages"] is None
    assert body["has_more"] is None


def test_constructs_paginated_returns_slice(client):
    _seed_constructs(client, 25)
    r = client.get(
        "/constructs?page=1&page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["total"] == 25  # full count
    assert len(body["constructs"]) == 10
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total_pages"] == 3
    assert body["has_more"] is True


def test_constructs_paginated_last_page_partial(client):
    _seed_constructs(client, 25)
    r = client.get(
        "/constructs?page=3&page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert len(body["constructs"]) == 5  # remainder
    assert body["page"] == 3
    assert body["has_more"] is False


def test_constructs_paginated_default_page_is_1(client):
    _seed_constructs(client, 25)
    # Only page_size provided; page defaults to 1
    r = client.get(
        "/constructs?page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["page"] == 1
    assert len(body["constructs"]) == 10


def test_constructs_paginated_beyond_total_returns_empty(client):
    _seed_constructs(client, 5)
    r = client.get(
        "/constructs?page=10&page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["total"] == 5
    assert body["constructs"] == []
    assert body["has_more"] is False


def test_constructs_pagination_combines_with_filters(client):
    _seed_constructs(client, 30)
    r = client.get(
        "/constructs?tier=1&page=1&page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    # All 30 are tier-1 States, so total=30 after filter
    assert body["total"] == 30
    assert len(body["constructs"]) == 10
    for c in body["constructs"]:
        assert c["tier"] == 1


def test_constructs_pagination_invalid_page_size_too_large(client):
    r = client.get(
        "/constructs?page_size=10001",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 400


def test_constructs_pagination_invalid_page_size_zero(client):
    r = client.get(
        "/constructs?page_size=0",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 400


def test_constructs_pagination_invalid_page_negative(client):
    r = client.get(
        "/constructs?page=-1&page_size=10",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 400


def test_constructs_pagination_by_type_count_is_full_match(client):
    """by_type counts reflect the full match set, not just the page."""
    _seed_constructs(client, 25)
    r = client.get(
        "/constructs?page=1&page_size=5",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    # Full match has 25 states; by_type should report 25 even though page has 5
    assert body["by_type"]["state"] == 25
    assert len(body["constructs"]) == 5


# ============================================================
# GET /constructs/by-run/{run_id} pagination
# ============================================================


def test_export_default_no_pagination(client):
    rid = _persist_runs(client, 1)[0]
    r = client.get(
        f"/constructs/by-run/{rid}",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["construct_count"] > 0
    assert len(body["constructs"]) == body["construct_count"]
    assert body["page"] is None
    assert body["page_size"] is None


def test_export_paginated(client):
    rid = _persist_runs(client, 1)[0]
    # Each run has ~12 constructs; paginate at 5 per page
    r = client.get(
        f"/constructs/by-run/{rid}?page=1&page_size=5",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["construct_count"] >= 10
    assert len(body["constructs"]) == 5
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total_pages"] >= 2
    assert body["has_more"] is True


def test_export_paginated_unknown_run_returns_zeroes(client):
    r = client.get(
        "/constructs/by-run/run-never?page=1&page_size=5",
        headers={"X-Tenant-ID": "acme"},
    )
    body = r.json()
    assert body["construct_count"] == 0
    assert body["constructs"] == []
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total_pages"] == 0
    assert body["has_more"] is False


def test_export_paginated_invalid_page_size(client):
    rid = _persist_runs(client, 1)[0]
    r = client.get(
        f"/constructs/by-run/{rid}?page_size=999999",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 400


# ============================================================
# GET /musia/tenants/{id}/runs pagination
# ============================================================


def test_runs_list_default_no_pagination(client):
    _persist_runs(client, 5)
    r = client.get("/musia/tenants/acme/runs")
    body = r.json()
    assert body["total_runs"] == 5
    assert len(body["runs"]) == 5
    assert body["page"] is None
    assert body["page_size"] is None


def test_runs_list_paginated(client):
    _persist_runs(client, 12)
    r = client.get("/musia/tenants/acme/runs?page=1&page_size=5")
    body = r.json()
    assert body["total_runs"] == 12
    assert len(body["runs"]) == 5
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total_pages"] == 3
    assert body["has_more"] is True


def test_runs_list_paginated_last_page(client):
    _persist_runs(client, 12)
    r = client.get("/musia/tenants/acme/runs?page=3&page_size=5")
    body = r.json()
    assert len(body["runs"]) == 2
    assert body["has_more"] is False


def test_runs_list_paginated_preserves_newest_first(client):
    """Pagination shouldn't change the sort order."""
    rids = _persist_runs(client, 6)
    # Newest first, so latest call is first in the unpaginated response
    full = client.get("/musia/tenants/acme/runs").json()["runs"]
    full_ids = [r["run_id"] for r in full]
    # rids was persisted in chronological order; full should be reverse of rids
    assert full_ids == list(reversed(rids))

    paginated_p1 = client.get(
        "/musia/tenants/acme/runs?page=1&page_size=2"
    ).json()["runs"]
    paginated_p2 = client.get(
        "/musia/tenants/acme/runs?page=2&page_size=2"
    ).json()["runs"]
    paginated_p3 = client.get(
        "/musia/tenants/acme/runs?page=3&page_size=2"
    ).json()["runs"]
    combined = (
        [r["run_id"] for r in paginated_p1]
        + [r["run_id"] for r in paginated_p2]
        + [r["run_id"] for r in paginated_p3]
    )
    assert combined == full_ids


def test_runs_list_paginated_invalid_params(client):
    r = client.get("/musia/tenants/acme/runs?page_size=-1")
    assert r.status_code == 400 or r.status_code == 404
    # ^ 404 if tenant doesn't exist yet; 400 if validation fires.
    # Either is fine; what matters is no crash.

    # Create a tenant first to get a 400 specifically
    _persist_runs(client, 1)
    r = client.get("/musia/tenants/acme/runs?page=0&page_size=5")
    assert r.status_code == 400


def test_runs_list_paginated_404_for_unknown_tenant(client):
    r = client.get(
        "/musia/tenants/never-existed/runs?page=1&page_size=5",
    )
    assert r.status_code == 404


# ============================================================
# Cross-cutting
# ============================================================


def test_pagination_total_independent_of_page_size(client):
    """The `total` field is the unpaginated count regardless of page_size."""
    _seed_constructs(client, 50)
    r5 = client.get(
        "/constructs?page_size=5",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    r25 = client.get(
        "/constructs?page_size=25",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    assert r5["total"] == 50
    assert r25["total"] == 50
    assert len(r5["constructs"]) == 5
    assert len(r25["constructs"]) == 25


def test_no_pagination_response_envelope_unchanged_from_v4_13(client):
    """v4.14.0 must not break v4.13 callers that don't use pagination."""
    _seed_constructs(client, 3)
    r = client.get("/constructs", headers={"X-Tenant-ID": "acme"})
    body = r.json()
    # v4.13 fields all present
    assert "total" in body
    assert "by_type" in body
    assert "constructs" in body
    assert "tenant_id" in body
    # v4.14 fields present but null
    assert body["page"] is None
    assert body["page_size"] is None
