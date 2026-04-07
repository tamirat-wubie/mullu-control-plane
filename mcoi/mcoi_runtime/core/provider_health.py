"""Provider Health Monitor — Active health probing and latency tracking.

Purpose: Proactively detect LLM provider degradation (latency spikes,
    elevated error rates, partial outages) before they cascade into
    user-visible failures.  Complements the passive CircuitBreaker by
    providing continuous health signals independent of live traffic.
Governance scope: observability only — does not route traffic.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Health probes are lightweight (no real LLM calls in probes).
  - Latency windows are bounded (sliding window, max N samples).
  - Error rate uses rolling window — old samples age out.
  - Health score is 0.0 (dead) to 1.0 (perfect).
  - Thread-safe — multiple probe threads + readers are safe.
  - Provider health is independent per provider.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ProviderHealthStatus(Enum):
    """Health status of an LLM provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthSample:
    """A single health observation for a provider."""

    timestamp: float  # monotonic time
    latency_ms: float
    success: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class ProviderHealthReport:
    """Computed health report for a single provider."""

    provider_name: str
    status: ProviderHealthStatus
    health_score: float  # 0.0 to 1.0
    avg_latency_ms: float
    p95_latency_ms: float
    error_rate: float  # 0.0 to 1.0
    sample_count: int
    consecutive_failures: int
    last_check_at: float


class ProviderHealthTracker:
    """Tracks health samples for a single provider with sliding window.

    Computes:
    - Average and P95 latency from recent samples
    - Error rate (failures / total) in the window
    - Health score (composite of latency + error rate)
    - Status classification (HEALTHY/DEGRADED/UNHEALTHY)
    """

    WINDOW_SIZE = 100  # Max samples in sliding window
    LATENCY_DEGRADED_MS = 5000.0  # P95 above this → degraded
    LATENCY_UNHEALTHY_MS = 15000.0  # P95 above this → unhealthy
    ERROR_RATE_DEGRADED = 0.1  # >10% errors → degraded
    ERROR_RATE_UNHEALTHY = 0.5  # >50% errors → unhealthy

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self._samples: deque[HealthSample] = deque(maxlen=self.WINDOW_SIZE)
        self._consecutive_failures = 0
        self._lock = threading.Lock()

    def record(self, sample: HealthSample) -> None:
        """Record a health observation."""
        with self._lock:
            self._samples.append(sample)
            if sample.success:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

    def record_success(self, latency_ms: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        """Convenience: record a successful observation."""
        self.record(HealthSample(timestamp=clock(), latency_ms=latency_ms, success=True))

    def record_failure(self, latency_ms: float, error: str = "", *, clock: Callable[[], float] = time.monotonic) -> None:
        """Convenience: record a failed observation."""
        self.record(HealthSample(timestamp=clock(), latency_ms=latency_ms, success=False, error=error))

    def report(self) -> ProviderHealthReport:
        """Compute current health report from sliding window."""
        with self._lock:
            samples = list(self._samples)
            consec_fail = self._consecutive_failures

        if not samples:
            return ProviderHealthReport(
                provider_name=self.provider_name,
                status=ProviderHealthStatus.UNKNOWN,
                health_score=0.5,
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                error_rate=0.0,
                sample_count=0,
                consecutive_failures=consec_fail,
                last_check_at=0.0,
            )

        latencies = [s.latency_ms for s in samples if s.success]
        failures = sum(1 for s in samples if not s.success)
        error_rate = failures / len(samples) if samples else 0.0

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p95_latency = _percentile(latencies, 95) if latencies else 0.0

        # Compute health score (0.0 to 1.0)
        latency_score = _latency_score(p95_latency) if latencies else 0.0
        error_score = max(0.0, 1.0 - error_rate * 2)  # 50% errors → 0.0
        health_score = round(latency_score * 0.4 + error_score * 0.6, 3)

        # Classify status (check most severe conditions first)
        if error_rate >= self.ERROR_RATE_UNHEALTHY or consec_fail >= 5:
            status = ProviderHealthStatus.UNHEALTHY
        elif p95_latency >= self.LATENCY_UNHEALTHY_MS:
            status = ProviderHealthStatus.UNHEALTHY
        elif error_rate >= self.ERROR_RATE_DEGRADED or p95_latency >= self.LATENCY_DEGRADED_MS:
            status = ProviderHealthStatus.DEGRADED
        else:
            status = ProviderHealthStatus.HEALTHY

        return ProviderHealthReport(
            provider_name=self.provider_name,
            status=status,
            health_score=health_score,
            avg_latency_ms=round(avg_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            error_rate=round(error_rate, 4),
            sample_count=len(samples),
            consecutive_failures=consec_fail,
            last_check_at=samples[-1].timestamp,
        )

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def sample_count(self) -> int:
        return len(self._samples)


class ProviderHealthMonitor:
    """Aggregates health across multiple providers.

    Maintains a ProviderHealthTracker per provider and provides
    a unified view of provider fleet health.

    Usage:
        monitor = ProviderHealthMonitor()
        monitor.record_invocation("anthropic", latency_ms=230, success=True)
        monitor.record_invocation("openai", latency_ms=450, success=True)
        monitor.record_invocation("openai", latency_ms=0, success=False, error="timeout")

        report = monitor.provider_report("openai")
        fleet = monitor.fleet_health()
    """

    MAX_PROVIDERS = 100

    def __init__(self) -> None:
        self._trackers: dict[str, ProviderHealthTracker] = {}
        self._lock = threading.Lock()

    def _get_tracker(self, provider_name: str) -> ProviderHealthTracker:
        if provider_name not in self._trackers:
            if len(self._trackers) >= self.MAX_PROVIDERS:
                # Evict provider with fewest samples
                min_key = min(self._trackers, key=lambda k: self._trackers[k].sample_count)
                del self._trackers[min_key]
            self._trackers[provider_name] = ProviderHealthTracker(provider_name)
        return self._trackers[provider_name]

    def record_invocation(
        self,
        provider_name: str,
        *,
        latency_ms: float,
        success: bool,
        error: str = "",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Record a provider invocation result."""
        with self._lock:
            tracker = self._get_tracker(provider_name)
        sample = HealthSample(
            timestamp=clock(), latency_ms=latency_ms,
            success=success, error=error,
        )
        tracker.record(sample)

    def provider_report(self, provider_name: str) -> ProviderHealthReport | None:
        """Get health report for a single provider."""
        with self._lock:
            tracker = self._trackers.get(provider_name)
        if tracker is None:
            return None
        return tracker.report()

    def fleet_health(self) -> dict[str, Any]:
        """Aggregate health across all tracked providers."""
        with self._lock:
            names = list(self._trackers.keys())
            trackers = list(self._trackers.values())

        reports = [t.report() for t in trackers]
        if not reports:
            return {
                "providers": [],
                "overall_status": "unknown",
                "overall_score": 0.5,
                "healthy_count": 0,
                "degraded_count": 0,
                "unhealthy_count": 0,
            }

        healthy = sum(1 for r in reports if r.status == ProviderHealthStatus.HEALTHY)
        degraded = sum(1 for r in reports if r.status == ProviderHealthStatus.DEGRADED)
        unhealthy = sum(1 for r in reports if r.status == ProviderHealthStatus.UNHEALTHY)
        scores = [r.health_score for r in reports]
        overall_score = round(sum(scores) / len(scores), 3) if scores else 0.5

        if unhealthy > len(reports) / 2:
            overall_status = "unhealthy"
        elif degraded + unhealthy > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "providers": [
                {
                    "name": r.provider_name,
                    "status": r.status.value,
                    "score": r.health_score,
                    "avg_latency_ms": r.avg_latency_ms,
                    "p95_latency_ms": r.p95_latency_ms,
                    "error_rate": r.error_rate,
                    "samples": r.sample_count,
                    "consecutive_failures": r.consecutive_failures,
                }
                for r in reports
            ],
            "overall_status": overall_status,
            "overall_score": overall_score,
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unhealthy_count": unhealthy,
        }

    def best_provider(self) -> str | None:
        """Return the healthiest provider name, or None."""
        with self._lock:
            trackers = list(self._trackers.values())
        if not trackers:
            return None
        reports = [(t.provider_name, t.report()) for t in trackers]
        # Sort by health_score descending, then by p95 latency ascending
        reports.sort(key=lambda x: (-x[1].health_score, x[1].p95_latency_ms))
        return reports[0][0] if reports else None

    def unhealthy_providers(self) -> list[str]:
        """List provider names that are currently unhealthy."""
        with self._lock:
            trackers = list(self._trackers.values())
        return [
            t.provider_name for t in trackers
            if t.report().status == ProviderHealthStatus.UNHEALTHY
        ]

    @property
    def provider_count(self) -> int:
        return len(self._trackers)


# ── Utility functions ──────────────────────────────────────────

def _percentile(values: list[float], pct: int) -> float:
    """Compute the pct-th percentile of a sorted list."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def _latency_score(p95_ms: float) -> float:
    """Convert P95 latency to a 0.0–1.0 score.

    < 1000ms → 1.0 (excellent)
    1000–5000ms → 0.5–1.0 (acceptable)
    5000–15000ms → 0.0–0.5 (degraded)
    > 15000ms → 0.0 (unhealthy)
    """
    if p95_ms <= 1000:
        return 1.0
    if p95_ms <= 5000:
        return round(1.0 - (p95_ms - 1000) / 8000, 3)
    if p95_ms <= 15000:
        return round(0.5 - (p95_ms - 5000) / 20000, 3)
    return 0.0
