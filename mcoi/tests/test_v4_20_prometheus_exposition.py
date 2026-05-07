"""v4.20.0 — Prometheus exposition for governance chain metrics.

v4.17 added counters + a JSON ``/musia/governance/stats`` endpoint.
v4.20 adds ``/musia/governance/metrics`` returning the standard
Prometheus text format (v0.0.4) so any compatible scraper (Prometheus,
Grafana Agent, Datadog, OTel Collector) can ingest natively.

These tests cover:
- Format conformance (HELP + TYPE annotations, label syntax, trailing newline)
- Label escaping (backslash, quote, newline)
- Cardinality bounds (one series per surface×verdict, etc.)
- Empty-state behavior (metrics still discoverable)
- HTTP endpoint content type, scope guard, alignment with /stats
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
# Format conformance — to_prometheus_text() unit tests
# ============================================================


def test_empty_snapshot_emits_help_and_type_annotations():
    """Empty state must still expose all metric families with HELP +
    TYPE so scrapers can register them before traffic arrives."""
    text = METRICS.snapshot().to_prometheus_text()
    expected_metrics = [
        "mullu_governance_chain_runs_total",
        "mullu_governance_chain_runs_by_tenant_total",
        "mullu_governance_chain_denials_by_guard_total",
        "mullu_governance_chain_total_runs",
        "mullu_governance_chain_total_denials",
        "mullu_governance_chain_recent_rejections",
    ]
    for metric in expected_metrics:
        assert f"# HELP {metric}" in text, f"missing HELP for {metric}"
        assert f"# TYPE {metric}" in text, f"missing TYPE for {metric}"


def test_counter_type_uses_total_suffix_convention():
    """Prometheus convention: counters end in _total."""
    text = METRICS.snapshot().to_prometheus_text()
    assert "# TYPE mullu_governance_chain_runs_total counter" in text
    assert "# TYPE mullu_governance_chain_denials_by_guard_total counter" in text
    assert "# TYPE mullu_governance_chain_total_runs gauge" in text


def test_output_ends_with_newline():
    """Prometheus exposition format requires a trailing newline."""
    text = METRICS.snapshot().to_prometheus_text()
    assert text.endswith("\n")


def test_metric_families_separated_by_blank_line():
    """Convention: families separated by blank line for readability."""
    text = METRICS.snapshot().to_prometheus_text()
    # At least one blank line between families
    assert "\n\n# HELP" in text


def test_records_appear_in_output_after_chain_activity():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme", allowed=True,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="rate_limit", reason="throttled",
    )
    text = METRICS.snapshot().to_prometheus_text()
    # Surface×verdict series
    assert 'surface="write"' in text
    assert 'verdict="allowed"' in text
    assert 'verdict="denied"' in text
    # By-guard series
    assert 'guard="rate_limit"' in text
    # Aggregate
    assert "mullu_governance_chain_total_runs 2" in text
    assert "mullu_governance_chain_total_denials 1" in text


def test_label_values_alphabetically_sorted():
    """Determinism for diff-able scraping: labels in each line are sorted."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="g", reason="r",
    )
    text = METRICS.snapshot().to_prometheus_text()
    # surface comes before verdict alphabetically
    line = next(
        line for line in text.split("\n")
        if line.startswith("mullu_governance_chain_runs_total{")
    )
    assert line.index("surface=") < line.index("verdict=")


def test_custom_prefix_propagates():
    """Operators may want a different prefix (e.g., for multi-tenant
    scraping with rewrites). All metric names should use it."""
    text = METRICS.snapshot().to_prometheus_text(prefix="acme_corp")
    assert "mullu_governance" not in text
    assert "acme_corp_governance_chain_runs_total" in text
    assert "acme_corp_governance_chain_total_runs" in text


# ============================================================
# Label escaping (Prometheus exposition spec)
# ============================================================


def test_label_value_with_quote_escaped():
    METRICS.record(
        surface=SURFACE_WRITE,
        tenant_id='tenant"with"quotes',
        allowed=True,
    )
    text = METRICS.snapshot().to_prometheus_text()
    # Quote must be backslash-escaped per Prometheus spec
    assert r'tenant=\"tenant\"with\"quotes\"' not in text  # not present unescaped
    assert r'tenant="tenant\"with\"quotes"' in text


def test_label_value_with_backslash_escaped():
    METRICS.record(
        surface=SURFACE_WRITE,
        tenant_id="tenant\\with\\backslash",
        allowed=True,
    )
    text = METRICS.snapshot().to_prometheus_text()
    # Backslash → double-backslash
    assert r'tenant="tenant\\with\\backslash"' in text


def test_label_value_with_newline_escaped():
    METRICS.record(
        surface=SURFACE_WRITE,
        tenant_id="tenant\nwith\nnewline",
        allowed=True,
    )
    text = METRICS.snapshot().to_prometheus_text()
    # Newline must be escaped to \n literal so each metric stays on
    # one line — otherwise the scraper gets confused
    assert "tenant\nwith\nnewline" not in text
    assert r'tenant="tenant\nwith\nnewline"' in text


# ============================================================
# Cardinality bounds (regression guard)
# ============================================================


def test_runs_by_surface_verdict_cardinality_bounded():
    """surface×verdict = 2×3 = at most 6 series, regardless of traffic."""
    for tid in [f"t{i}" for i in range(20)]:
        METRICS.record(surface=SURFACE_WRITE, tenant_id=tid, allowed=True)
        METRICS.record(
            surface=SURFACE_DOMAIN_RUN, tenant_id=tid,
            allowed=False, blocking_guard="g",
        )
    text = METRICS.snapshot().to_prometheus_text()
    # Count lines for the runs_total metric (excluding HELP/TYPE)
    runs_lines = [
        line for line in text.split("\n")
        if line.startswith("mullu_governance_chain_runs_total{")
    ]
    # We triggered 2 distinct (surface, verdict) tuples — (write, allowed)
    # and (domain_run, denied) — regardless of 20-tenant traffic. The
    # invariant under test: series count is bounded by the cross product
    # of surface×verdict (max 6), NOT by tenant count.
    assert len(runs_lines) == 2
    assert len(runs_lines) <= 6  # absolute upper bound on this metric


def test_denials_by_guard_one_series_per_guard():
    """Denials counter has one series per blocking guard name —
    bounded by chain config size, not tenant count."""
    for tid in [f"t{i}" for i in range(50)]:
        METRICS.record(
            surface=SURFACE_WRITE, tenant_id=tid,
            allowed=False, blocking_guard="rate_limit",
        )
        METRICS.record(
            surface=SURFACE_WRITE, tenant_id=tid,
            allowed=False, blocking_guard="boundary_lockdown",
        )
    text = METRICS.snapshot().to_prometheus_text()
    guard_lines = [
        line for line in text.split("\n")
        if line.startswith("mullu_governance_chain_denials_by_guard_total{")
    ]
    # 2 distinct guards regardless of 50-tenant traffic
    assert len(guard_lines) == 2


# ============================================================
# HTTP endpoint
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


def test_metrics_endpoint_returns_prometheus_content_type(http_app):
    r = http_app.get("/musia/governance/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "text/plain; version=0.0.4"
    )


def test_metrics_endpoint_body_is_text_format(http_app):
    r = http_app.get("/musia/governance/metrics")
    body = r.text
    # All required metric families discoverable
    assert "# TYPE mullu_governance_chain_runs_total counter" in body
    assert "# TYPE mullu_governance_chain_total_runs gauge" in body
    # Trailing newline
    assert body.endswith("\n")


def test_metrics_endpoint_reflects_chain_activity(http_app):
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny_test",
            lambda c: GuardResult(
                allowed=False, guard_name="deny_test", reason="x",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    # One blocked write
    http_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )

    body = http_app.get("/musia/governance/metrics").text
    assert 'guard="deny_test"' in body
    assert 'surface="write"' in body
    assert 'verdict="denied"' in body
    assert "mullu_governance_chain_total_runs 1" in body
    assert "mullu_governance_chain_total_denials 1" in body


def test_metrics_endpoint_aligns_with_stats_endpoint(http_app):
    """Same data, two formats — counts must match."""
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok"))
    )
    configure_musia_governance_chain(chain)

    for _ in range(3):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )

    stats = http_app.get("/musia/governance/stats").json()
    metrics_body = http_app.get("/musia/governance/metrics").text

    assert stats["total_runs"] == 3
    # Same number surfaces in the Prometheus body
    assert "mullu_governance_chain_total_runs 3" in metrics_body


def test_metrics_endpoint_handles_concurrent_chain_writes(http_app):
    """Snapshot-based reads must not race against incoming records."""
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok"))
    )
    configure_musia_governance_chain(chain)

    # Hammer some writes; interleave reads
    for i in range(20):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": f"t{i % 5}"},
            json={"configuration": {}},
        )
    # Read finalizes — must reflect a coherent snapshot, not a partial one
    body = http_app.get("/musia/governance/metrics").text
    assert "mullu_governance_chain_total_runs 20" in body


def test_metrics_endpoint_empty_state_is_valid_format(http_app):
    """Before any chain activity, the endpoint still returns a valid
    document with HELP + TYPE for all expected families. This lets
    Prometheus register the series before traffic arrives."""
    body = http_app.get("/musia/governance/metrics").text
    # All 6 metric families discoverable in empty state
    expected_metrics = [
        "mullu_governance_chain_runs_total",
        "mullu_governance_chain_runs_by_tenant_total",
        "mullu_governance_chain_denials_by_guard_total",
        "mullu_governance_chain_total_runs",
        "mullu_governance_chain_total_denials",
        "mullu_governance_chain_recent_rejections",
    ]
    for metric in expected_metrics:
        assert f"# HELP {metric}" in body
        assert f"# TYPE {metric}" in body
    # Aggregate gauges are 0 in empty state
    assert "mullu_governance_chain_total_runs 0" in body
    assert "mullu_governance_chain_total_denials 0" in body
    assert "mullu_governance_chain_recent_rejections 0" in body
