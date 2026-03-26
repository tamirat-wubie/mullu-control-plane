"""Phase 202B — Governance Metrics Engine.

Purpose: Observability plane for governance — tracks policy decisions,
    budget enforcement, execution authority, and system health.
    Provides time-series counters and histogram-style breakdowns.
Governance scope: metrics collection and reporting only.
Dependencies: none (pure counters).
Invariants:
  - Metrics are append-only — no retroactive edits.
  - Counter increments are atomic within a single call.
  - Metric names are validated — typos don't create phantom counters.
  - Reset clears values but preserves metric registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    """Point-in-time snapshot of all metrics."""

    counters: dict[str, int]
    gauges: dict[str, float]
    histograms: dict[str, list[float]]
    captured_at: str


class GovernanceMetricsEngine:
    """Collects and reports governance metrics.

    Three metric types:
    - Counters: monotonically increasing integers (e.g., total_requests)
    - Gauges: current-value floats (e.g., active_sessions)
    - Histograms: value distributions (e.g., response_latency)
    """

    # Known metric names — prevents typo-based phantom metrics
    KNOWN_COUNTERS = frozenset({
        "requests_total",
        "requests_governed",
        "requests_rejected",
        "budget_checks_total",
        "budget_checks_failed",
        "policy_decisions_total",
        "policy_decisions_denied",
        "llm_calls_total",
        "llm_calls_succeeded",
        "llm_calls_failed",
        "certifications_total",
        "certifications_passed",
        "certifications_failed",
        "sessions_created",
        "sessions_deactivated",
        "ledger_entries_total",
        "errors_total",
    })

    KNOWN_GAUGES = frozenset({
        "active_sessions",
        "active_tenants",
        "budget_utilization_pct",
        "health_score",
        "pending_llm_calls",
        "uptime_seconds",
    })

    KNOWN_HISTOGRAMS = frozenset({
        "request_latency_ms",
        "llm_latency_ms",
        "llm_cost_per_call",
        "tokens_per_call",
    })

    def __init__(self, *, clock: Callable[[], str], strict: bool = True) -> None:
        self._clock = clock
        self._strict = strict
        self._counters: dict[str, int] = {name: 0 for name in self.KNOWN_COUNTERS}
        self._gauges: dict[str, float] = {name: 0.0 for name in self.KNOWN_GAUGES}
        self._histograms: dict[str, list[float]] = {name: [] for name in self.KNOWN_HISTOGRAMS}

    def _validate_counter(self, name: str) -> None:
        if self._strict and name not in self.KNOWN_COUNTERS:
            raise ValueError(f"unknown counter: {name}")

    def _validate_gauge(self, name: str) -> None:
        if self._strict and name not in self.KNOWN_GAUGES:
            raise ValueError(f"unknown gauge: {name}")

    def _validate_histogram(self, name: str) -> None:
        if self._strict and name not in self.KNOWN_HISTOGRAMS:
            raise ValueError(f"unknown histogram: {name}")

    # ═══ Counters ═══

    def inc(self, name: str, amount: int = 1) -> int:
        """Increment a counter. Returns the new value."""
        self._validate_counter(name)
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += amount
        return self._counters[name]

    def counter(self, name: str) -> int:
        """Get current counter value."""
        self._validate_counter(name)
        return self._counters.get(name, 0)

    # ═══ Gauges ═══

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge to a specific value."""
        self._validate_gauge(name)
        self._gauges[name] = value

    def gauge(self, name: str) -> float:
        """Get current gauge value."""
        self._validate_gauge(name)
        return self._gauges.get(name, 0.0)

    def inc_gauge(self, name: str, amount: float = 1.0) -> float:
        """Increment a gauge. Returns new value."""
        self._validate_gauge(name)
        if name not in self._gauges:
            self._gauges[name] = 0.0
        self._gauges[name] += amount
        return self._gauges[name]

    def dec_gauge(self, name: str, amount: float = 1.0) -> float:
        """Decrement a gauge. Returns new value."""
        self._validate_gauge(name)
        if name not in self._gauges:
            self._gauges[name] = 0.0
        self._gauges[name] -= amount
        return self._gauges[name]

    # ═══ Histograms ═══

    def observe(self, name: str, value: float) -> None:
        """Record a value in a histogram."""
        self._validate_histogram(name)
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics (count, sum, avg, min, max, p50, p95, p99)."""
        self._validate_histogram(name)
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        total = sum(sorted_vals)

        def percentile(p: float) -> float:
            idx = int(count * p / 100)
            return sorted_vals[min(idx, count - 1)]

        return {
            "count": count,
            "sum": round(total, 6),
            "avg": round(total / count, 6),
            "min": round(sorted_vals[0], 6),
            "max": round(sorted_vals[-1], 6),
            "p50": round(percentile(50), 6),
            "p95": round(percentile(95), 6),
            "p99": round(percentile(99), 6),
        }

    # ═══ Snapshots ═══

    def snapshot(self) -> MetricSnapshot:
        """Capture a point-in-time snapshot of all metrics."""
        return MetricSnapshot(
            counters=dict(self._counters),
            gauges=dict(self._gauges),
            histograms={k: list(v) for k, v in self._histograms.items()},
            captured_at=self._clock(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Export all metrics as a flat dictionary for API responses."""
        result: dict[str, Any] = {}
        result["counters"] = dict(self._counters)
        result["gauges"] = {k: round(v, 4) for k, v in self._gauges.items()}
        result["histograms"] = {
            name: self.histogram_stats(name)
            for name in self._histograms
            if self._histograms[name]
        }
        result["captured_at"] = self._clock()
        return result

    def reset(self) -> None:
        """Reset all metric values but preserve registrations."""
        for name in self._counters:
            self._counters[name] = 0
        for name in self._gauges:
            self._gauges[name] = 0.0
        for name in self._histograms:
            self._histograms[name] = []
