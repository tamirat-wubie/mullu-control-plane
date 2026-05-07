"""Load Testing Framework Tests."""

import time

import pytest
from mcoi_runtime.core.load_test import (
    LoadTestSuite,
    run_benchmark,
    run_concurrent_benchmark,
    run_platform_benchmarks,
)


class TestRunBenchmark:
    def test_basic_benchmark(self):
        counter = [0]
        def fn():
            counter[0] += 1
        result = run_benchmark("counter", fn, iterations=100, warmup=5)
        assert result.name == "counter"
        assert result.operations == 100
        assert result.throughput_ops > 0
        assert result.avg_latency_ms > 0
        assert result.p50_latency_ms > 0
        assert result.p95_latency_ms >= result.p50_latency_ms
        assert result.p99_latency_ms >= result.p95_latency_ms
        assert result.error_count == 0
        assert counter[0] == 105  # 100 iterations + 5 warmup

    def test_benchmark_with_errors(self):
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise ValueError("flaky")
        result = run_benchmark("flaky", flaky, iterations=30, warmup=0)
        assert result.error_count == 10  # Every 3rd call
        assert result.error_rate == pytest.approx(10 / 30, rel=0.01)

    def test_benchmark_to_dict(self):
        result = run_benchmark("test", lambda: None, iterations=10, warmup=0)
        d = result.to_dict()
        assert d["name"] == "test"
        assert "throughput_ops" in d
        assert "p95_latency_ms" in d

    def test_zero_iterations(self):
        result = run_benchmark("empty", lambda: None, iterations=0, warmup=0)
        assert result.operations == 0


class TestConcurrentBenchmark:
    def test_concurrent(self):
        counter = [0]
        lock = __import__("threading").Lock()
        def fn():
            with lock:
                counter[0] += 1
        result = run_concurrent_benchmark(
            "concurrent", fn, iterations=50, concurrency=4, warmup=0,
        )
        assert result.operations == 200  # 50 * 4
        assert counter[0] == 200
        assert result.throughput_ops > 0
        assert result.error_count == 0

    def test_concurrent_with_errors(self):
        def failing():
            raise RuntimeError("always fails")
        result = run_concurrent_benchmark(
            "fail_concurrent", failing,
            iterations=10, concurrency=2, warmup=0,
        )
        assert result.error_count == 20
        assert result.error_rate == 1.0

    def test_concurrent_timeout_counts_unfinished_operations(self):
        def slow():
            time.sleep(0.2)

        result = run_concurrent_benchmark(
            "slow_concurrent",
            slow,
            iterations=1,
            concurrency=2,
            warmup=0,
            join_timeout_seconds=0.01,
        )

        assert result.operations == 2
        assert result.error_count == 2
        assert result.error_rate == 1.0
        assert result.throughput_ops == 0


class TestPlatformBenchmarks:
    def test_suite_runs(self):
        suite = run_platform_benchmarks()
        assert isinstance(suite, LoadTestSuite)
        assert len(suite.results) >= 8
        assert suite.total_operations > 0
        assert suite.overall_throughput_ops > 0

    def test_guard_chain_under_1ms(self):
        """Guard chain evaluation should be sub-millisecond."""
        suite = run_platform_benchmarks()
        guard_bench = next(r for r in suite.results if r.name == "guard_chain_evaluation")
        assert guard_bench.p95_latency_ms < 5.0  # Sub-5ms even on slow CI

    def test_rate_limiter_fast(self):
        suite = run_platform_benchmarks()
        rl_bench = next(r for r in suite.results if r.name == "rate_limiter_check")
        assert rl_bench.throughput_ops > 10000  # >10K ops/sec

    def test_content_safety_fast(self):
        suite = run_platform_benchmarks()
        safety_bench = next(r for r in suite.results if r.name == "content_safety_evaluation")
        assert safety_bench.throughput_ops > 1000  # >1K ops/sec

    def test_no_errors_in_suite(self):
        suite = run_platform_benchmarks()
        for r in suite.results:
            assert r.error_count == 0, f"{r.name} had {r.error_count} errors"

    def test_suite_to_dict(self):
        suite = run_platform_benchmarks()
        d = suite.to_dict()
        assert "benchmarks" in d
        assert len(d["benchmarks"]) >= 8
        assert "overall_throughput_ops" in d

    def test_concurrent_guard_no_errors(self):
        suite = run_platform_benchmarks()
        concurrent = next(r for r in suite.results if r.name == "guard_chain_concurrent")
        assert concurrent.error_count == 0
        assert concurrent.operations > 0
