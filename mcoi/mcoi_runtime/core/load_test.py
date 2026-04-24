"""Load Testing Framework — Sustained throughput benchmarks.

Purpose: Measure governance pipeline throughput, detect bottlenecks,
    and verify the platform handles sustained load without degradation.
    Runs as in-process benchmarks (no external tools required).
Governance scope: testing only — no side effects.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Benchmarks are deterministic (same config → reproducible results).
  - Results include percentile latencies (p50, p95, p99).
  - Throughput is measured in operations/second.
  - No external dependencies (runs without network/database).
  - Thread-safe — concurrent benchmarks are safe.
"""

from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    operations: int
    duration_seconds: float
    throughput_ops: float  # operations per second
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    error_count: int = 0
    error_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "operations": self.operations,
            "duration_seconds": round(self.duration_seconds, 3),
            "throughput_ops": round(self.throughput_ops, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "p50_latency_ms": round(self.p50_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "p99_latency_ms": round(self.p99_latency_ms, 3),
            "min_latency_ms": round(self.min_latency_ms, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
        }


@dataclass(frozen=True, slots=True)
class LoadTestSuite:
    """Collection of benchmark results."""

    results: tuple[BenchmarkResult, ...]
    total_operations: int
    total_duration_seconds: float
    overall_throughput_ops: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmarks": [r.to_dict() for r in self.results],
            "total_operations": self.total_operations,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "overall_throughput_ops": round(self.overall_throughput_ops, 1),
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    rank = max(0, int((pct / 100.0) * len(sorted_v) + 0.5) - 1)
    return sorted_v[min(rank, len(sorted_v) - 1)]


def run_benchmark(
    name: str,
    fn: Callable[[], Any],
    *,
    iterations: int = 1000,
    warmup: int = 10,
) -> BenchmarkResult:
    """Run a single benchmark: execute fn() `iterations` times and measure.

    Args:
        name: Benchmark name.
        fn: Function to benchmark (called with no args).
        iterations: Number of measured iterations.
        warmup: Number of warmup iterations (not measured).
    """
    # Warmup
    for _ in range(warmup):
        try:
            fn()
        except Exception:
            pass

    # Measured run
    latencies: list[float] = []
    errors = 0
    start = time.monotonic()

    for _ in range(iterations):
        t0 = time.monotonic()
        try:
            fn()
        except Exception:
            errors += 1
        t1 = time.monotonic()
        latencies.append((t1 - t0) * 1000)  # ms

    end = time.monotonic()
    duration = end - start

    if not latencies:
        return BenchmarkResult(
            name=name, operations=0, duration_seconds=0,
            throughput_ops=0, avg_latency_ms=0, p50_latency_ms=0,
            p95_latency_ms=0, p99_latency_ms=0, min_latency_ms=0,
            max_latency_ms=0,
        )

    return BenchmarkResult(
        name=name,
        operations=iterations,
        duration_seconds=duration,
        throughput_ops=iterations / duration if duration > 0 else 0,
        avg_latency_ms=statistics.mean(latencies),
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        p99_latency_ms=_percentile(latencies, 99),
        min_latency_ms=min(latencies),
        max_latency_ms=max(latencies),
        error_count=errors,
        error_rate=errors / iterations if iterations > 0 else 0,
    )


def run_concurrent_benchmark(
    name: str,
    fn: Callable[[], Any],
    *,
    iterations: int = 1000,
    concurrency: int = 4,
    warmup: int = 10,
    join_timeout_seconds: float = 60.0,
) -> BenchmarkResult:
    """Run a benchmark with concurrent threads.

    Total operations = iterations * concurrency.
    """
    # Warmup (single-threaded)
    for _ in range(warmup):
        try:
            fn()
        except Exception:
            pass

    all_latencies: list[float] = []
    total_errors = [0]
    lock = threading.Lock()

    def worker():
        local_latencies: list[float] = []
        local_errors = 0
        for _ in range(iterations):
            t0 = time.monotonic()
            try:
                fn()
            except Exception:
                local_errors += 1
            t1 = time.monotonic()
            local_latencies.append((t1 - t0) * 1000)
        with lock:
            all_latencies.extend(local_latencies)
            total_errors[0] += local_errors

    start = time.monotonic()
    threads = [
        threading.Thread(target=worker, daemon=True)
        for _ in range(concurrency)
    ]
    for t in threads:
        t.start()
    join_deadline = start + join_timeout_seconds
    for t in threads:
        remaining_seconds = max(0.0, join_deadline - time.monotonic())
        t.join(timeout=remaining_seconds)
    end = time.monotonic()

    duration = end - start
    total_ops = iterations * concurrency
    completed_ops = len(all_latencies)
    unfinished_ops = max(0, total_ops - completed_ops)
    errors = total_errors[0] + unfinished_ops

    if not all_latencies:
        return BenchmarkResult(
            name=name, operations=total_ops, duration_seconds=duration,
            throughput_ops=0, avg_latency_ms=0, p50_latency_ms=0,
            p95_latency_ms=0, p99_latency_ms=0, min_latency_ms=0,
            max_latency_ms=0, error_count=errors,
            error_rate=errors / total_ops if total_ops > 0 else 0,
        )

    return BenchmarkResult(
        name=name,
        operations=total_ops,
        duration_seconds=duration,
        throughput_ops=completed_ops / duration if duration > 0 else 0,
        avg_latency_ms=statistics.mean(all_latencies),
        p50_latency_ms=_percentile(all_latencies, 50),
        p95_latency_ms=_percentile(all_latencies, 95),
        p99_latency_ms=_percentile(all_latencies, 99),
        min_latency_ms=min(all_latencies),
        max_latency_ms=max(all_latencies),
        error_count=errors,
        error_rate=errors / total_ops if total_ops > 0 else 0,
    )


def run_platform_benchmarks() -> LoadTestSuite:
    """Run the standard platform benchmark suite.

    Benchmarks governance pipeline components without external dependencies.
    """
    results: list[BenchmarkResult] = []
    suite_start = time.monotonic()

    # 1. Guard chain evaluation
    from mcoi_runtime.core.governance_guard import (
        GovernanceGuardChain, create_tenant_guard,
        create_rate_limit_guard, create_budget_guard,
    )
    from mcoi_runtime.core.rate_limiter import RateLimiter, RateLimitConfig
    from mcoi_runtime.core.tenant_budget import TenantBudgetManager

    rl = RateLimiter(default_config=RateLimitConfig(max_tokens=100_000, refill_rate=100_000))
    bm = TenantBudgetManager(clock=lambda: "2026-01-01T00:00:00Z")
    bm.ensure_budget("bench-tenant")
    chain = GovernanceGuardChain()
    chain.add(create_tenant_guard())
    chain.add(create_rate_limit_guard(rl))
    chain.add(create_budget_guard(bm))
    ctx = {"tenant_id": "bench-tenant", "endpoint": "/api/v1/test", "method": "GET"}

    results.append(run_benchmark(
        "guard_chain_evaluation",
        lambda: chain.evaluate(dict(ctx)),
        iterations=5000, warmup=100,
    ))

    # 2. Guard chain concurrent
    results.append(run_concurrent_benchmark(
        "guard_chain_concurrent",
        lambda: chain.evaluate(dict(ctx)),
        iterations=1000, concurrency=4, warmup=50,
    ))

    # 3. Rate limiter check
    results.append(run_benchmark(
        "rate_limiter_check",
        lambda: rl.check("bench-tenant", "/api/v1/test"),
        iterations=10000, warmup=100,
    ))

    # 4. Audit trail recording
    from mcoi_runtime.core.audit_trail import AuditTrail
    trail = AuditTrail(clock=lambda: "2026-01-01T00:00:00Z", max_entries=100_000)
    results.append(run_benchmark(
        "audit_trail_record",
        lambda: trail.record(
            action="bench.test", actor_id="bench-user",
            tenant_id="bench-tenant", target="bench-resource",
            outcome="success",
        ),
        iterations=5000, warmup=100,
    ))

    # 5. Content safety evaluation
    from mcoi_runtime.core.content_safety import build_default_safety_chain
    safety = build_default_safety_chain()
    results.append(run_benchmark(
        "content_safety_evaluation",
        lambda: safety.evaluate("What is the weather in London today?"),
        iterations=5000, warmup=100,
    ))

    # 6. PII scanning
    from mcoi_runtime.core.pii_scanner import PIIScanner
    scanner = PIIScanner()
    results.append(run_benchmark(
        "pii_scan",
        lambda: scanner.scan("Contact John at john@example.com or 555-123-4567"),
        iterations=5000, warmup=100,
    ))

    # 7. Coordination lock acquire/release
    from mcoi_runtime.core.coordination_lock import CoordinationLockManager
    lock_mgr = CoordinationLockManager()
    lock_counter = [0]

    def lock_cycle():
        lock_counter[0] += 1
        r = f"bench-resource-{lock_counter[0]}"
        lock_mgr.acquire("bench-tenant", r, holder_id="bench-session")
        lock_mgr.release("bench-tenant", r, holder_id="bench-session")

    results.append(run_benchmark(
        "coordination_lock_cycle",
        lock_cycle,
        iterations=5000, warmup=100,
    ))

    # 8. Message dedup check
    from gateway.dedup import MessageDeduplicator
    dedup = MessageDeduplicator()
    dedup_counter = [0]

    def dedup_check():
        dedup_counter[0] += 1
        dedup.check("whatsapp", "+1234", f"msg-{dedup_counter[0]}")

    results.append(run_benchmark(
        "message_dedup_check",
        dedup_check,
        iterations=10000, warmup=100,
    ))

    suite_end = time.monotonic()
    total_ops = sum(r.operations for r in results)
    total_duration = suite_end - suite_start

    return LoadTestSuite(
        results=tuple(results),
        total_operations=total_ops,
        total_duration_seconds=total_duration,
        overall_throughput_ops=total_ops / total_duration if total_duration > 0 else 0,
    )
