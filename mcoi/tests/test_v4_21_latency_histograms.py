"""v4.21.0 — chain latency histograms in governance metrics.

Closes the "histograms missing" gap from v4.20 release notes. v4.17
added counters; v4.20 exposed them as Prometheus text format. v4.21
adds latency histograms to both the snapshot and the Prometheus output:

- ``LatencyHistogram`` dataclass with cumulative (le=) bucket counts
- ``record(... duration_seconds=...)`` parameter on the registry
- Bridge call sites time the chain.evaluate() call and pass duration
  through (allowed, denied, exception verdicts all observed)
- ``mullu_governance_chain_duration_seconds`` Prometheus histogram
  family with ``_bucket{le=...,surface=...}``, ``_sum``, ``_count``

Bucket boundaries: 1μs, 5μs, 10μs, 25μs, 50μs, 100μs, 250μs, 500μs,
1ms, 2.5ms, 5ms (informed by v4.17 measurements: 5–16μs typical, p99 ≤
41μs). Pathological cases up to 5ms are captured before falling into
+Inf.
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
    chain_to_validator,
    configure_musia_governance_chain,
    gate_domain_run,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    DEFAULT_LATENCY_BUCKETS_SECONDS,
    GovernanceMetricsRegistry,
    LatencyHistogram,
    REGISTRY as METRICS,
    SURFACE_DOMAIN_RUN,
    SURFACE_WRITE,
    router as metrics_router,
)
from mcoi_runtime.core.governance_guard import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    ProposedDelta,
)
from uuid import uuid4


@pytest.fixture(autouse=True)
def _reset_metrics():
    METRICS.reset()
    yield
    METRICS.reset()


# ============================================================
# LatencyHistogram dataclass
# ============================================================


def test_default_bucket_boundaries_cover_v4_17_measurements():
    """The default boundaries must encompass the measured chain
    latency profile from v4.17 benchmarks (5-16μs typical, p99 ≤ 41μs)."""
    buckets = DEFAULT_LATENCY_BUCKETS_SECONDS
    # 5μs and 10μs (typical) covered
    assert 5e-6 in buckets
    assert 1e-5 in buckets
    # 50μs (p99 ceiling with headroom) covered
    assert 5e-5 in buckets
    # 5ms (pathological — blocking I/O in guard) covered
    assert 5e-3 in buckets
    # Buckets are sorted ascending (Prometheus convention)
    assert list(buckets) == sorted(buckets)


def test_p_estimate_returns_none_when_empty():
    h = LatencyHistogram(
        upper_bounds=(0.001, 0.01),
        bucket_counts=(0, 0),
        sum_seconds=0.0,
        count=0,
    )
    assert h.p_estimate(0.99) is None


def test_p_estimate_returns_smallest_bound_meeting_target():
    """p99 of 100 observations split 80/15/5 across (1ms, 10ms, +Inf)
    should report 10ms — the smallest bound covering at least 99 obs."""
    h = LatencyHistogram(
        upper_bounds=(0.001, 0.01),
        bucket_counts=(80, 95),  # cumulative; +Inf = count = 100
        sum_seconds=0.5,
        count=100,
    )
    # p50 is in the first bucket (≤1ms covers 80 of 100)
    assert h.p_estimate(0.5) == 0.001
    # p90 needs more than 80, so falls into the 10ms bucket
    assert h.p_estimate(0.9) == 0.01
    # p99 needs 99 of 100; 95 cumulative in 10ms bucket, so falls into +Inf
    assert h.p_estimate(0.99) == float("inf")


# ============================================================
# Registry — duration_seconds recording
# ============================================================


def test_record_without_duration_is_backward_compatible():
    """Pre-v4.21 callers (no duration_seconds) still work — the
    histogram simply stays empty for that surface."""
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    snap = METRICS.snapshot()
    assert snap.latency_by_surface == {}
    # Counters still incremented
    assert snap.total_runs() == 1


def test_record_with_duration_populates_histogram():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_007,  # 7μs — in 10μs bucket
    )
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 1
    assert hist.sum_seconds == pytest.approx(0.000_007)
    # 7μs falls into bucket le=10μs and all higher buckets (cumulative)
    # Bucket index 0 = 1μs (excludes), 1 = 5μs (excludes), 2 = 10μs (includes)
    bucket_for_10us = hist.bucket_counts[2]
    assert bucket_for_10us == 1


def test_record_negative_duration_treated_as_zero():
    """Defense against clock skew. Should not corrupt the histogram."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=-0.001,
    )
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 1
    assert hist.sum_seconds == 0.0
    # Falls into smallest bucket (1μs) since 0.0 ≤ 1e-6
    assert hist.bucket_counts[0] == 1


def test_record_distributes_across_buckets_correctly():
    """Each observation goes into ALL buckets whose upper bound ≥ duration
    (cumulative semantics). Verifies the bucket math."""
    durations = [
        0.000_002,  # 2μs   → ≤5μs and above
        0.000_007,  # 7μs   → ≤10μs and above
        0.000_030,  # 30μs  → ≤50μs and above
        0.000_500,  # 500μs → ≤500μs and above
        0.010,      # 10ms  → only +Inf (above all bounds)
    ]
    for d in durations:
        METRICS.record(
            surface=SURFACE_WRITE, tenant_id="acme",
            allowed=True, duration_seconds=d,
        )

    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 5
    assert hist.sum_seconds == pytest.approx(sum(durations))

    # Bucket index for ≤1μs: only 0 obs (none ≤ 1μs)
    assert hist.bucket_counts[0] == 0
    # Bucket index for ≤5μs: 1 (the 2μs obs)
    assert hist.bucket_counts[1] == 1
    # Bucket index for ≤10μs: 2 (the 2μs and 7μs)
    assert hist.bucket_counts[2] == 2
    # Bucket index for ≤500μs (index 7): 4 (everything except 10ms)
    assert hist.bucket_counts[7] == 4
    # Last bucket (≤5ms, index 10): still 4 (10ms is +Inf)
    assert hist.bucket_counts[10] == 4
    # +Inf bucket = total count
    assert hist.count == 5


def test_record_separates_histograms_by_surface():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    METRICS.record(
        surface=SURFACE_DOMAIN_RUN, tenant_id="acme",
        allowed=True, duration_seconds=0.001,
    )
    snap = METRICS.snapshot()
    # Two separate histograms
    assert SURFACE_WRITE in snap.latency_by_surface
    assert SURFACE_DOMAIN_RUN in snap.latency_by_surface
    assert snap.latency_by_surface[SURFACE_WRITE].count == 1
    assert snap.latency_by_surface[SURFACE_DOMAIN_RUN].count == 1
    # Different sums prove they don't share state
    assert (snap.latency_by_surface[SURFACE_WRITE].sum_seconds
            != snap.latency_by_surface[SURFACE_DOMAIN_RUN].sum_seconds)


def test_record_histogram_observed_for_all_verdicts():
    """allowed, denied, exception — all should populate the histogram.
    A crashing guard's wall-clock cost is interesting too."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="g", duration_seconds=0.000_020,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="exc", exception=True,
        duration_seconds=0.001,
    )
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 3


def test_reset_clears_histograms():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    METRICS.reset()
    snap = METRICS.snapshot()
    assert snap.latency_by_surface == {}


def test_custom_bucket_boundaries():
    """Operators may want different bucket boundaries (e.g., for chains
    that include external calls). Construct a registry with custom bounds."""
    custom = (0.01, 0.1, 1.0)
    reg = GovernanceMetricsRegistry(latency_buckets_seconds=custom)
    reg.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.05,  # 50ms
    )
    hist = reg.snapshot().latency_by_surface[SURFACE_WRITE]
    assert hist.upper_bounds == custom
    # 50ms ≤ 100ms (index 1), so cumulative counts: [0, 1, 1]
    assert hist.bucket_counts == (0, 1, 1)


# ============================================================
# Bridge wiring — chain_to_validator + gate_domain_run pass durations
# ============================================================


def _delta() -> ProposedDelta:
    return ProposedDelta(
        construct_id=uuid4(),
        operation="create",
        payload={"type": "state", "tier": 1},
    )


def _ctx() -> GovernanceContext:
    return GovernanceContext(correlation_id="cid", tenant_id="acme")


def _auth() -> Authority:
    return Authority(identifier="a", kind="agent")


def test_chain_to_validator_records_duration_for_allow():
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx(), _auth())
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 1
    # Real chain runs in microseconds — sum should be tiny but positive
    assert 0 < hist.sum_seconds < 0.1


def test_chain_to_validator_records_duration_for_deny():
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard(
        "deny", lambda c: GuardResult(
            allowed=False, guard_name="deny", reason="x",
        ),
    ))
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx(), _auth())
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 1


def test_chain_to_validator_records_duration_for_exception():
    """Exception path includes time spent before the raise."""
    class BadChain:
        guards = []  # type: ignore[var-annotated]
        def evaluate(self, ctx):
            raise RuntimeError("boom")

    validator = chain_to_validator(BadChain())  # type: ignore[arg-type]
    validator(_delta(), _ctx(), _auth())
    snap = METRICS.snapshot()
    hist = snap.latency_by_surface[SURFACE_WRITE]
    assert hist.count == 1


def test_gate_domain_run_records_duration():
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="acme", summary="x")
        snap = METRICS.snapshot()
        hist = snap.latency_by_surface[SURFACE_DOMAIN_RUN]
        assert hist.count == 1
    finally:
        configure_musia_governance_chain(None)


def test_detached_chain_records_no_duration():
    """When chain is detached, gate_domain_run is a no-op — and no
    histogram entry should appear."""
    configure_musia_governance_chain(None)
    gate_domain_run(domain="software_dev", tenant_id="acme", summary="x")
    snap = METRICS.snapshot()
    assert snap.latency_by_surface == {}


# ============================================================
# Prometheus exposition format
# ============================================================


def test_prometheus_emits_histogram_family():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    text = METRICS.snapshot().to_prometheus_text()
    assert "# TYPE mullu_governance_chain_duration_seconds histogram" in text
    # _bucket lines with le= label
    assert 'mullu_governance_chain_duration_seconds_bucket{le=' in text
    # _sum and _count lines
    assert 'mullu_governance_chain_duration_seconds_sum{surface="write"}' in text
    assert 'mullu_governance_chain_duration_seconds_count{surface="write"}' in text


def test_prometheus_emits_inf_bucket():
    """Prometheus convention requires a +Inf bucket equal to count."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    text = METRICS.snapshot().to_prometheus_text()
    assert 'le="+Inf"' in text


def test_prometheus_buckets_are_cumulative_and_monotonic():
    """Add observations across multiple buckets; verify cumulative
    counts in the Prometheus output increase monotonically."""
    for _ in range(5):
        METRICS.record(
            surface=SURFACE_WRITE, tenant_id="acme",
            allowed=True, duration_seconds=0.000_001,  # smallest bucket
        )
    for _ in range(3):
        METRICS.record(
            surface=SURFACE_WRITE, tenant_id="acme",
            allowed=True, duration_seconds=0.000_100,  # larger bucket
        )

    text = METRICS.snapshot().to_prometheus_text()
    bucket_lines = [
        line for line in text.split("\n")
        if "mullu_governance_chain_duration_seconds_bucket{" in line
    ]
    # Extract the count (last whitespace-separated token)
    counts = [int(line.split()[-1]) for line in bucket_lines]
    # Cumulative: each count ≥ previous
    assert counts == sorted(counts)
    # Total = 8 (the +Inf bucket value)
    assert counts[-1] == 8


def test_prometheus_empty_state_emits_help_and_type():
    """Before any observation, the histogram family should still be
    discoverable so Prometheus registers it."""
    text = METRICS.snapshot().to_prometheus_text()
    assert "# TYPE mullu_governance_chain_duration_seconds histogram" in text


def test_prometheus_separates_histograms_by_surface():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    METRICS.record(
        surface=SURFACE_DOMAIN_RUN, tenant_id="acme",
        allowed=True, duration_seconds=0.001,
    )
    text = METRICS.snapshot().to_prometheus_text()
    assert 'surface="write"' in text
    assert 'surface="domain_run"' in text


def test_as_dict_includes_latency():
    """JSON consumers see the same data as the Prometheus output."""
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=True, duration_seconds=0.000_010,
    )
    body = METRICS.snapshot().as_dict()
    assert "latency_by_surface" in body
    assert "write" in body["latency_by_surface"]
    surface_data = body["latency_by_surface"]["write"]
    assert surface_data["count"] == 1
    assert surface_data["sum_seconds"] == pytest.approx(0.000_010)
    assert "upper_bounds" in surface_data
    assert "bucket_counts" in surface_data


# ============================================================
# HTTP endpoint end-to-end
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


def test_end_to_end_chain_writes_populate_histogram(http_app):
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)

    for _ in range(10):
        http_app.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )

    body = http_app.get("/musia/governance/metrics").text
    # Histogram family discoverable
    assert "# TYPE mullu_governance_chain_duration_seconds histogram" in body
    # Count line equals 10
    assert 'mullu_governance_chain_duration_seconds_count{surface="write"} 10' in body
    # +Inf bucket also = 10
    inf_lines = [
        line for line in body.split("\n")
        if 'le="+Inf"' in line
        and 'mullu_governance_chain_duration_seconds_bucket' in line
    ]
    assert len(inf_lines) == 1
    assert inf_lines[0].split()[-1] == "10"
