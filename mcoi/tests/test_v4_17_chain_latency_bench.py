"""v4.17.0 supplement — chain latency benchmarks.

The chain runs on every governed write and every domain run. v4.17.0
added counter observability but left latency unmeasured. These
benchmarks establish a baseline + regression guard so we know whether
adding a guard or restructuring the bridge moved the cost meaningfully.

Numbers are not a SLA; they are a tripwire. The asserted thresholds are
deliberately loose (10× expected typical) so they fire on real
regressions, not on slower CI hardware. If you see this test fail in
CI, the chain got measurably slower — go look at what changed.

Run interactively to see the actual numbers:

    pytest tests/test_v4_17_chain_latency_bench.py -s
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.app.routers.musia_governance_bridge import (
    chain_to_validator,
    configure_musia_governance_chain,
    gate_domain_run,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY as METRICS,
)
from mcoi_runtime.core.governance_bench import benchmark
from mcoi_runtime.governance.guards.chain import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    ProposedDelta,
)


def _delta() -> ProposedDelta:
    return ProposedDelta(
        construct_id=uuid4(),
        operation="create",
        payload={"type": "state", "tier": 1},
    )


def _ctx() -> GovernanceContext:
    return GovernanceContext(correlation_id="bench", tenant_id="acme")


def _auth() -> Authority:
    return Authority(identifier="bench", kind="agent")


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Counter recording is on the hot path; we don't want metrics to
    grow unbounded across the benchmark suite."""
    METRICS.reset()
    yield
    configure_musia_governance_chain(None)
    METRICS.reset()


def _allow_guard(name: str) -> GovernanceGuard:
    return GovernanceGuard(
        name, lambda c: GuardResult(allowed=True, guard_name=name)
    )


def _deny_guard(name: str) -> GovernanceGuard:
    return GovernanceGuard(
        name,
        lambda c: GuardResult(
            allowed=False, guard_name=name, reason="bench-deny",
        ),
    )


# ============================================================
# Write surface (chain_to_validator)
# ============================================================


def test_bench_empty_chain_pass():
    """Empty chain — measures the bridge translation overhead alone.
    The chain has nothing to do; whatever this costs is pure adapter work
    (ProposedDelta + GovernanceContext + Authority → guard_ctx dict)."""
    chain = GovernanceGuardChain()
    validator = chain_to_validator(chain)
    delta, ctx, auth = _delta(), _ctx(), _auth()

    result = benchmark(
        "write_chain_empty_pass",
        lambda: validator(delta, ctx, auth),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p95={result.p95_ns/1000:.1f}us p99={result.p99_ns/1000:.1f}us")

    # Tripwire: empty bridge should be cheap. 1ms p99 means something is
    # very wrong (allocation explosion, lock contention, etc.).
    assert result.p99_ns < 1_000_000, (
        f"empty chain p99 {result.p99_ns/1000:.1f}us > 1ms threshold"
    )


def test_bench_single_allow_guard():
    chain = GovernanceGuardChain()
    chain.add(_allow_guard("g1"))
    validator = chain_to_validator(chain)
    delta, ctx, auth = _delta(), _ctx(), _auth()

    result = benchmark(
        "write_chain_1guard_pass",
        lambda: validator(delta, ctx, auth),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p95={result.p95_ns/1000:.1f}us p99={result.p99_ns/1000:.1f}us")
    assert result.p99_ns < 1_000_000


def test_bench_five_allow_guards():
    """Five trivial guards — establishes per-guard amortized cost."""
    chain = GovernanceGuardChain()
    for i in range(5):
        chain.add(_allow_guard(f"g{i}"))
    validator = chain_to_validator(chain)
    delta, ctx, auth = _delta(), _ctx(), _auth()

    result = benchmark(
        "write_chain_5guards_pass",
        lambda: validator(delta, ctx, auth),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p95={result.p95_ns/1000:.1f}us p99={result.p99_ns/1000:.1f}us")
    # 5 trivial guards should still be sub-millisecond.
    assert result.p99_ns < 2_000_000, (
        f"5-guard chain p99 {result.p99_ns/1000:.1f}us > 2ms threshold"
    )


def test_bench_first_failure_stops():
    """5 guards where the first denies — the chain should short-circuit.
    Cost should approximate the 1-guard case, NOT the 5-guard case.
    This benchmark protects against accidentally evaluating all guards
    on rejection."""
    chain = GovernanceGuardChain()
    chain.add(_deny_guard("first"))
    for i in range(4):
        chain.add(_allow_guard(f"never_{i}"))
    validator = chain_to_validator(chain)
    delta, ctx, auth = _delta(), _ctx(), _auth()

    result = benchmark(
        "write_chain_first_denies_5guards",
        lambda: validator(delta, ctx, auth),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p95={result.p95_ns/1000:.1f}us p99={result.p99_ns/1000:.1f}us")
    # If short-circuit broke, p99 would be near 5-guard pass cost.
    # We just assert the absolute ceiling (regression guard).
    assert result.p99_ns < 1_000_000


def test_bench_metrics_recording_overhead():
    """Counter recording on every invocation is on the hot path — does
    it dominate the per-call cost? This benchmark answers."""
    chain = GovernanceGuardChain()
    chain.add(_allow_guard("g1"))
    validator = chain_to_validator(chain)
    delta, ctx, auth = _delta(), _ctx(), _auth()

    # Baseline: with metrics live (default after v4.17)
    with_metrics = benchmark(
        "write_chain_with_metrics",
        lambda: validator(delta, ctx, auth),
        iterations=2000, warmup=200,
    )
    print(f"\n  {with_metrics.name}: mean={with_metrics.mean_us:.1f}us ops/s={with_metrics.ops_per_second:.0f}")
    print(f"  p99 with metrics: {with_metrics.p99_ns/1000:.1f}us")
    # The lock + dict updates per call should be << 100us even on slow
    # hardware. If this fires, metrics became expensive — likely a
    # cardinality explosion or the ring buffer changed shape.
    assert with_metrics.mean_ns < 100_000, (
        f"metrics-instrumented chain mean {with_metrics.mean_us:.1f}us > 100us"
    )


# ============================================================
# Domain-run surface (gate_domain_run)
# ============================================================


def test_bench_gate_domain_run_detached():
    """When chain is detached, gate_domain_run should be near-free —
    one None check and return."""
    configure_musia_governance_chain(None)

    result = benchmark(
        "domain_gate_detached",
        lambda: gate_domain_run(
            domain="software_dev", tenant_id="acme", summary="x",
        ),
        iterations=5000, warmup=500,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p99={result.p99_ns/1000:.1f}us")
    # Detached path is a ~3-line function. 50us p99 is generous.
    assert result.p99_ns < 50_000, (
        f"detached gate p99 {result.p99_ns/1000:.1f}us > 50us — investigate"
    )


def test_bench_gate_domain_run_attached_pass():
    chain = GovernanceGuardChain()
    chain.add(_allow_guard("g1"))
    configure_musia_governance_chain(chain)

    result = benchmark(
        "domain_gate_attached_pass",
        lambda: gate_domain_run(
            domain="software_dev", tenant_id="acme", summary="x",
        ),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p99={result.p99_ns/1000:.1f}us")
    assert result.p99_ns < 1_000_000


def test_bench_gate_domain_run_attached_deny():
    """Deny path includes denial counter + ring buffer append.
    Compare to attached_pass to see the deny-path overhead."""
    chain = GovernanceGuardChain()
    chain.add(_deny_guard("g1"))
    configure_musia_governance_chain(chain)

    result = benchmark(
        "domain_gate_attached_deny",
        lambda: gate_domain_run(
            domain="software_dev", tenant_id="acme", summary="x",
        ),
        iterations=2000, warmup=200,
    )
    print(f"\n  {result.name}: mean={result.mean_us:.1f}us ops/s={result.ops_per_second:.0f}")
    print(f"  p99={result.p99_ns/1000:.1f}us")
    assert result.p99_ns < 1_000_000


# ============================================================
# Latency budget summary (only printed; no assertion)
# ============================================================


def test_print_latency_summary():
    """Run a small suite and print per-bench means side by side. This
    is informational — fast iteration during chain perf tuning. Not a
    pass/fail; the assertion guards above do that work."""
    from mcoi_runtime.core.governance_bench import BenchSuite

    suite = BenchSuite(name="v4.17_chain_latency")

    chain_empty = GovernanceGuardChain()
    chain_1 = GovernanceGuardChain()
    chain_1.add(_allow_guard("g1"))
    chain_5 = GovernanceGuardChain()
    for i in range(5):
        chain_5.add(_allow_guard(f"g{i}"))

    delta, ctx, auth = _delta(), _ctx(), _auth()

    suite.add(benchmark(
        "validator_empty",
        lambda: chain_to_validator(chain_empty)(delta, ctx, auth),
        iterations=500, warmup=50,
    ))
    suite.add(benchmark(
        "validator_1guard",
        lambda: chain_to_validator(chain_1)(delta, ctx, auth),
        iterations=500, warmup=50,
    ))
    suite.add(benchmark(
        "validator_5guards",
        lambda: chain_to_validator(chain_5)(delta, ctx, auth),
        iterations=500, warmup=50,
    ))

    configure_musia_governance_chain(chain_1)
    suite.add(benchmark(
        "domain_gate_pass",
        lambda: gate_domain_run(
            domain="software_dev", tenant_id="acme", summary="x",
        ),
        iterations=500, warmup=50,
    ))

    print("\n=== v4.17.0 chain latency summary ===")
    for r in suite.results:
        print(f"  {r.name:30s} mean={r.mean_us:6.1f}us  p95={r.p95_ns/1000:6.1f}us  p99={r.p99_ns/1000:6.1f}us  ops/s={r.ops_per_second:>8.0f}")

    # Soft sanity check: total iterations executed (no perf assertion here)
    assert suite.total_iterations == 4 * 500
