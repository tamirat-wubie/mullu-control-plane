"""Phase 215B — Production Monitoring Dashboard.

Purpose: Real-time monitoring data for operational dashboards.
    Aggregates system vitals, throughput, error rates, and
    performance metrics into dashboard-ready time series.
Governance scope: monitoring data collection only.
Dependencies: governance_metrics, cost_analytics.
Invariants:
  - Monitoring data is always fresh (computed on-demand).
  - Time windows are configurable.
  - All rates are per-minute normalized.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SystemVitals:
    """Real-time system vitals."""

    uptime_seconds: float
    requests_per_minute: float
    errors_per_minute: float
    error_rate_pct: float
    active_tenants: int
    llm_calls_total: int
    total_cost: float
    health_score: float
    circuit_breaker_state: str
    event_bus_events: int
    captured_at: str


class MonitoringEngine:
    """Collects and computes monitoring metrics."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._start_time = time.monotonic()
        self._request_timestamps: list[float] = []
        self._error_timestamps: list[float] = []

    def record_request(self) -> None:
        self._request_timestamps.append(time.monotonic())

    def record_error(self) -> None:
        self._error_timestamps.append(time.monotonic())

    def _rate_per_minute(self, timestamps: list[float], window_seconds: float = 60.0) -> float:
        now = time.monotonic()
        cutoff = now - window_seconds
        recent = [t for t in timestamps if t >= cutoff]
        if window_seconds <= 0:
            return 0.0
        return len(recent) * (60.0 / window_seconds)

    def compute_vitals(
        self,
        *,
        active_tenants: int = 0,
        llm_calls: int = 0,
        total_cost: float = 0.0,
        health_score: float = 1.0,
        circuit_state: str = "closed",
        event_count: int = 0,
    ) -> SystemVitals:
        """Compute current system vitals."""
        uptime = time.monotonic() - self._start_time
        req_rate = self._rate_per_minute(self._request_timestamps)
        err_rate = self._rate_per_minute(self._error_timestamps)
        error_pct = (err_rate / req_rate * 100) if req_rate > 0 else 0.0

        return SystemVitals(
            uptime_seconds=round(uptime, 1),
            requests_per_minute=round(req_rate, 2),
            errors_per_minute=round(err_rate, 2),
            error_rate_pct=round(error_pct, 2),
            active_tenants=active_tenants,
            llm_calls_total=llm_calls,
            total_cost=round(total_cost, 6),
            health_score=round(health_score, 4),
            circuit_breaker_state=circuit_state,
            event_bus_events=event_count,
            captured_at=self._clock(),
        )

    @property
    def total_requests(self) -> int:
        return len(self._request_timestamps)

    @property
    def total_errors(self) -> int:
        return len(self._error_timestamps)

    def summary(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
        }
