"""Phase 4B — Governance Performance Benchmarks tests.

Tests: Benchmark harness, result structure, governance subsystem latency,
    suite execution, summary reporting.
"""

import pytest
from mcoi_runtime.core.governance_bench import (
    BenchResult,
    BenchSuite,
    benchmark,
    run_governance_benchmarks,
)


# ═══ Benchmark Harness ═══


class TestBenchmarkHarness:
    def test_simple_benchmark(self):
        result = benchmark("noop", lambda: None, iterations=100, warmup=10)
        assert result.name == "noop"
        assert result.iterations == 100
        assert result.total_seconds > 0
        assert result.mean_ns > 0
        assert result.ops_per_second > 0

    def test_min_max_ordering(self):
        result = benchmark("test", lambda: sum(range(100)), iterations=50, warmup=5)
        assert result.min_ns <= result.mean_ns <= result.max_ns

    def test_percentiles(self):
        result = benchmark("test", lambda: None, iterations=100, warmup=10)
        assert result.median_ns > 0
        assert result.p95_ns >= result.median_ns
        assert result.p99_ns >= result.p95_ns

    def test_mean_us_conversion(self):
        result = benchmark("test", lambda: None, iterations=100, warmup=10)
        assert result.mean_us == result.mean_ns / 1000

    def test_summary_string(self):
        result = benchmark("test_op", lambda: None, iterations=100, warmup=10)
        summary = result.summary
        assert "test_op" in summary
        assert "μs/op" in summary
        assert "ops/s" in summary


# ═══ BenchSuite ═══


class TestBenchSuite:
    def test_empty_suite(self):
        suite = BenchSuite(name="test")
        assert suite.total_iterations == 0
        assert len(suite.results) == 0

    def test_add_result(self):
        suite = BenchSuite(name="test")
        result = benchmark("op", lambda: None, iterations=50, warmup=5)
        suite.add(result)
        assert len(suite.results) == 1
        assert suite.total_iterations == 50

    def test_summary(self):
        suite = BenchSuite(name="test")
        suite.add(benchmark("op1", lambda: None, iterations=50, warmup=5))
        suite.add(benchmark("op2", lambda: None, iterations=50, warmup=5))
        summary = suite.summary()
        assert summary["suite"] == "test"
        assert summary["benchmarks"] == 2
        assert summary["total_iterations"] == 100
        assert len(summary["results"]) == 2


# ═══ Governance Benchmarks ═══


class TestGovernanceBenchmarks:
    def test_suite_runs_to_completion(self):
        """Run the full governance benchmark suite — must complete without error."""
        suite = run_governance_benchmarks()
        assert suite.name == "governance"
        assert len(suite.results) >= 8  # 9 benchmarks defined
        assert suite.total_iterations > 0

    def test_guard_chain_benchmark_exists(self):
        suite = run_governance_benchmarks()
        names = [r.name for r in suite.results]
        assert "guard_chain_3_guards" in names

    def test_rate_limit_benchmark_exists(self):
        suite = run_governance_benchmarks()
        names = [r.name for r in suite.results]
        assert "rate_limit_check" in names

    def test_audit_benchmark_exists(self):
        suite = run_governance_benchmarks()
        names = [r.name for r in suite.results]
        assert "audit_record" in names

    def test_pii_benchmarks_exist(self):
        suite = run_governance_benchmarks()
        names = [r.name for r in suite.results]
        assert "pii_scan_clean" in names
        assert "pii_scan_with_pii" in names

    def test_content_safety_benchmarks_exist(self):
        suite = run_governance_benchmarks()
        names = [r.name for r in suite.results]
        assert "content_safety_safe" in names
        assert "content_safety_unsafe" in names

    def test_all_benchmarks_have_positive_ops(self):
        suite = run_governance_benchmarks()
        for result in suite.results:
            assert result.ops_per_second > 0, f"{result.name} has 0 ops/s"
            assert result.mean_ns > 0, f"{result.name} has 0 mean_ns"

    def test_guard_chain_latency_reasonable(self):
        """Guard chain should evaluate in <1ms (1_000_000 ns) per call."""
        suite = run_governance_benchmarks()
        guard = next(r for r in suite.results if r.name == "guard_chain_3_guards")
        assert guard.mean_ns < 1_000_000, f"Guard chain too slow: {guard.mean_us:.1f} μs"
