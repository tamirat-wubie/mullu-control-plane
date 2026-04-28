"""v4.24.0 — per-tenant scrape redaction for governance metrics.

Closes the "per-tenant scrape redaction" gap from v4.17/v4.18 audit.
Pre-v4.24, /musia/governance/stats and /metrics were admin-scoped
and exposed every tenant's data. Multi-org SaaS deployments need
per-customer visibility without leaking cross-tenant aggregates.

v4.24 adds:
- A 3-way (surface, tenant, verdict) index on the registry, populated
  alongside the existing 2-way indices
- A ``GovernanceMetricsSnapshot.for_tenant(tenant_id)`` filter that
  returns a redacted snapshot scoped to one tenant
- ``GET /musia/governance/stats/tenant`` (JSON, musia.read scope)
- ``GET /musia/governance/metrics/tenant`` (Prometheus, musia.read scope)

Cross-tenant aggregates (``latency_by_surface``) are dropped from the
tenant view to prevent inferring other tenants' load from summed
latency counts.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_governance_bridge import (
    configure_musia_governance_chain,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY as METRICS,
    SURFACE_DOMAIN_RUN,
    SURFACE_WRITE,
    VERDICT_ALLOWED,
    VERDICT_DENIED,
    router as metrics_router,
)
from mcoi_runtime.governance.guards.chain import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    METRICS.reset()
    yield
    METRICS.reset()


# ============================================================
# 3-way index: registry-level
# ============================================================


def test_record_populates_three_way_index():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme", allowed=True,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="g",
    )
    METRICS.record(
        surface=SURFACE_DOMAIN_RUN, tenant_id="bigco", allowed=True,
    )
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_tenant_verdict == {
        (SURFACE_WRITE, "acme", VERDICT_ALLOWED): 1,
        (SURFACE_WRITE, "acme", VERDICT_DENIED): 1,
        (SURFACE_DOMAIN_RUN, "bigco", VERDICT_ALLOWED): 1,
    }


def test_three_way_index_does_not_break_existing_two_way_indices():
    """Backward compat: v4.17–v4.21 fields still populated correctly."""
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="bigco", allowed=True)
    snap = METRICS.snapshot()
    # 2-way verdict index aggregates across tenants
    assert snap.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_ALLOWED)] == 2
    # 2-way tenant index still works
    assert snap.runs_by_surface_tenant[(SURFACE_WRITE, "acme")] == 1
    assert snap.runs_by_surface_tenant[(SURFACE_WRITE, "bigco")] == 1


def test_reset_clears_three_way_index():
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.reset()
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_tenant_verdict == {}


# ============================================================
# for_tenant() — redaction logic
# ============================================================


def test_for_tenant_returns_only_named_tenants_runs():
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="bigco", allowed=True)
    METRICS.record(surface=SURFACE_DOMAIN_RUN, tenant_id="bigco", allowed=False, blocking_guard="g")

    full = METRICS.snapshot()
    acme_view = full.for_tenant("acme")

    # Acme's per-tenant counts only
    assert acme_view.runs_by_surface_tenant == {(SURFACE_WRITE, "acme"): 2}
    # No bigco entries leaked
    assert all(t == "acme" for (_, t) in acme_view.runs_by_surface_tenant)
    assert all(t == "acme" for (_, t, _) in acme_view.runs_by_surface_tenant_verdict)


def test_for_tenant_reconstructs_verdict_breakdown():
    """Per-tenant view exposes the caller's allowed/denied/exception
    counts WITHOUT leaking cross-tenant verdict aggregates."""
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=False, blocking_guard="g")
    METRICS.record(surface=SURFACE_WRITE, tenant_id="bigco", allowed=False, blocking_guard="g")
    # Big neighbor with lots of traffic
    for _ in range(50):
        METRICS.record(surface=SURFACE_WRITE, tenant_id="bigco", allowed=True)

    acme_view = METRICS.snapshot().for_tenant("acme")
    # Acme's allow/deny breakdown is correct (2 + 1)
    assert acme_view.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_ALLOWED)] == 2
    assert acme_view.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_DENIED)] == 1
    # Acme's totals don't leak bigco's 50+ writes
    assert acme_view.total_runs() == 3


def test_for_tenant_filters_recent_rejections():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="acme_guard", reason="acme reason",
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="bigco",
        allowed=False, blocking_guard="bigco_guard", reason="bigco reason",
    )
    acme_view = METRICS.snapshot().for_tenant("acme")
    assert len(acme_view.recent_rejections) == 1
    assert acme_view.recent_rejections[0].tenant_id == "acme"
    assert acme_view.recent_rejections[0].blocking_guard == "acme_guard"
    # bigco's rejection invisible
    bigco_seen = any(ev.tenant_id == "bigco" for ev in acme_view.recent_rejections)
    assert not bigco_seen


def test_for_tenant_reconstructs_denials_by_guard():
    """Per-tenant denials_by_guard is built from the tenant's filtered
    rejections, not the cross-tenant aggregate."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="rate_limit",
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="rate_limit",
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="bigco",
        allowed=False, blocking_guard="rate_limit",
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="bigco",
        allowed=False, blocking_guard="boundary_lockdown",
    )
    acme_view = METRICS.snapshot().for_tenant("acme")
    # Acme's denials_by_guard: rate_limit only, count=2 (not 3, not 4)
    assert acme_view.denials_by_guard == {"rate_limit": 2}


def test_for_tenant_drops_latency_histograms():
    """Latency aggregates summed-across-tenants would let one tenant
    infer another's load. Drop the field for the per-tenant view."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    full = METRICS.snapshot()
    assert full.latency_by_surface  # populated in admin view
    acme_view = full.for_tenant("acme")
    # Per-tenant view: latency dropped entirely
    assert acme_view.latency_by_surface == {}


def test_for_tenant_with_unknown_tenant_returns_empty_view():
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    nobody_view = METRICS.snapshot().for_tenant("does-not-exist")
    assert nobody_view.total_runs() == 0
    assert nobody_view.runs_by_surface_tenant == {}
    assert nobody_view.recent_rejections == ()


def test_for_tenant_with_empty_tenant_id_returns_empty_view():
    """Defense: empty tenant_id mustn't degrade to 'all tenants'."""
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    empty_view = METRICS.snapshot().for_tenant("")
    assert empty_view.total_runs() == 0
    assert empty_view.runs_by_surface_tenant == {}


# ============================================================
# HTTP endpoints — JSON + Prometheus tenant-scoped
# ============================================================


@pytest.fixture
def http_app() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    configure_musia_governance_chain(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(metrics_router)
    yield TestClient(app)
    configure_musia_governance_chain(None)
    reset_registry()


def _seed_chain_traffic(http_app: TestClient) -> None:
    """Seed the registry with chain activity from two distinct tenants."""
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)
    # Acme: 3 writes
    for _ in range(3):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
    # Bigco: 5 writes
    for _ in range(5):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "bigco"},
            json={"configuration": {}},
        )


def test_stats_tenant_returns_only_callers_data(http_app):
    _seed_chain_traffic(http_app)
    r = http_app.get(
        "/musia/governance/stats/tenant",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    body = r.json()
    # Acme's totals only — 3 writes, 0 from bigco's 5
    assert body["total_runs"] == 3
    # No bigco strings appear anywhere in the response
    assert "bigco" not in r.text


def test_stats_tenant_separates_views(http_app):
    """Two tenants scrape independently — neither sees the other."""
    _seed_chain_traffic(http_app)
    acme = http_app.get(
        "/musia/governance/stats/tenant",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    bigco = http_app.get(
        "/musia/governance/stats/tenant",
        headers={"X-Tenant-ID": "bigco"},
    ).json()
    assert acme["total_runs"] == 3
    assert bigco["total_runs"] == 5
    # Sums match the admin global view
    admin = http_app.get(
        "/musia/governance/stats",
        headers={"X-Tenant-ID": "acme"},
    ).json()
    assert admin["total_runs"] == 8


def test_metrics_tenant_returns_prometheus_format(http_app):
    _seed_chain_traffic(http_app)
    r = http_app.get(
        "/musia/governance/metrics/tenant",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain; version=0.0.4")
    body = r.text
    # Standard Prometheus headers present
    assert "# TYPE mullu_governance_chain_runs_total counter" in body
    # Acme-scoped — bigco label string nowhere in body
    assert "bigco" not in body
    # Acme's count surfaces in total_runs gauge
    assert "mullu_governance_chain_total_runs 3" in body


def test_metrics_tenant_reflects_per_tenant_verdict_breakdown(http_app):
    """Per-tenant view exposes the caller's allow/deny breakdown."""
    deny_chain = GovernanceGuardChain()
    deny_chain.add(GovernanceGuard(
        "deny", lambda c: GuardResult(
            allowed=False, guard_name="deny", reason="x"
        ),
    ))
    configure_musia_governance_chain(deny_chain)
    # Acme: 2 denied writes
    for _ in range(2):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
    # Bigco: 3 denied writes
    for _ in range(3):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "bigco"},
            json={"configuration": {}},
        )

    acme_body = http_app.get(
        "/musia/governance/metrics/tenant",
        headers={"X-Tenant-ID": "acme"},
    ).text
    # Acme's denial count = 2, NOT 5
    assert "mullu_governance_chain_total_denials 2" in acme_body
    assert 'verdict="denied"' in acme_body


def test_metrics_tenant_omits_latency_histogram(http_app):
    """Latency dropped in tenant view (cross-tenant aggregate would leak load)."""
    _seed_chain_traffic(http_app)
    body = http_app.get(
        "/musia/governance/metrics/tenant",
        headers={"X-Tenant-ID": "acme"},
    ).text
    # Latency family still has HELP/TYPE (registered for scraper) but
    # NO sample lines — the empty histogram emits no _bucket/_sum/_count
    assert "# TYPE mullu_governance_chain_duration_seconds histogram" in body
    # Specifically NO surface="write" sample lines for duration
    assert 'mullu_governance_chain_duration_seconds_count{surface="write"}' not in body


def test_admin_metrics_endpoint_unchanged_by_tenant_view(http_app):
    """Adding /tenant variants must not affect /metrics admin endpoint."""
    _seed_chain_traffic(http_app)
    body = http_app.get(
        "/musia/governance/metrics",
        headers={"X-Tenant-ID": "acme"},
    ).text
    # Admin view sees BOTH tenants
    assert "mullu_governance_chain_total_runs 8" in body
    assert 'tenant="acme"' in body
    assert 'tenant="bigco"' in body
    # Admin latency histogram populated
    assert 'mullu_governance_chain_duration_seconds_count{surface="write"} 8' in body


def test_unknown_tenant_returns_empty_but_well_formed(http_app):
    """A tenant that's never had chain activity gets an empty-state view."""
    _seed_chain_traffic(http_app)
    body = http_app.get(
        "/musia/governance/metrics/tenant",
        headers={"X-Tenant-ID": "third-tenant"},
    ).text
    # Valid format with empty aggregates
    assert "# TYPE mullu_governance_chain_runs_total counter" in body
    assert "mullu_governance_chain_total_runs 0" in body
    assert "mullu_governance_chain_total_denials 0" in body
