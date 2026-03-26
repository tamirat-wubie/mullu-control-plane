"""Phase 226C — Health Check Aggregation with Degraded States.

Purpose: Aggregate health checks from all subsystems into a composite
    health status with support for healthy/degraded/unhealthy states,
    weighted scoring, and dependency tracking.
Dependencies: None (stdlib only).
Invariants:
  - Overall status is worst-case of all checks.
  - Degraded is between healthy and unhealthy.
  - Each check runs independently (one failure doesn't block others).
  - Results include per-check details and composite score.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable


class HealthStatus(IntEnum):
    HEALTHY = 0
    DEGRADED = 1
    UNHEALTHY = 2


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositeHealth:
    """Aggregated health across all checks."""
    status: HealthStatus
    score: float  # 0-100
    checks: list[CheckResult]
    timestamp: float

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.name.lower(),
            "score": round(self.score, 1),
            "is_healthy": self.is_healthy,
            "checks": [
                {"name": c.name, "status": c.status.name.lower(),
                 "message": c.message, "latency_ms": round(c.latency_ms, 2)}
                for c in self.checks
            ],
            "timestamp": self.timestamp,
        }


@dataclass
class HealthCheckDef:
    """Definition of a registered health check."""
    name: str
    check_fn: Callable[[], dict[str, Any]]
    weight: float = 1.0
    critical: bool = False  # if True, failure makes overall UNHEALTHY
    timeout_ms: float = 5000.0


class HealthCheckAggregator:
    """Aggregates health checks with degraded state support."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._checks: dict[str, HealthCheckDef] = {}
        self._last_result: CompositeHealth | None = None
        self._total_runs = 0

    def register(self, check: HealthCheckDef) -> None:
        self._checks[check.name] = check

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)

    @property
    def check_count(self) -> int:
        return len(self._checks)

    def run(self) -> CompositeHealth:
        """Run all health checks and aggregate results."""
        results: list[CheckResult] = []
        self._total_runs += 1

        for name, check_def in self._checks.items():
            start = time.monotonic()
            try:
                output = check_def.check_fn()
                status_str = output.get("status", "healthy")
                if status_str == "healthy":
                    status = HealthStatus.HEALTHY
                elif status_str == "degraded":
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.UNHEALTHY
                message = output.get("message", "")
            except Exception as e:
                status = HealthStatus.UNHEALTHY
                message = str(e)
                output = {}

            latency = (time.monotonic() - start) * 1000
            results.append(CheckResult(
                name=name, status=status, message=message,
                latency_ms=latency, details=output,
            ))

        # Compute composite
        overall_status = self._compute_overall(results)
        score = self._compute_score(results)

        composite = CompositeHealth(
            status=overall_status,
            score=score,
            checks=results,
            timestamp=time.time(),
        )
        self._last_result = composite
        return composite

    def _compute_overall(self, results: list[CheckResult]) -> HealthStatus:
        if not results:
            return HealthStatus.HEALTHY

        # Critical checks: if any critical check is unhealthy, overall is unhealthy
        for r in results:
            check_def = self._checks.get(r.name)
            if check_def and check_def.critical and r.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Otherwise worst-case
        worst = max(r.status for r in results)
        return HealthStatus(worst)

    def _compute_score(self, results: list[CheckResult]) -> float:
        if not results:
            return 100.0
        total_weight = sum(self._checks[r.name].weight for r in results if r.name in self._checks)
        if total_weight == 0:
            return 100.0
        weighted_sum = 0.0
        for r in results:
            check_def = self._checks.get(r.name)
            if not check_def:
                continue
            if r.status == HealthStatus.HEALTHY:
                weighted_sum += check_def.weight * 100.0
            elif r.status == HealthStatus.DEGRADED:
                weighted_sum += check_def.weight * 50.0
            # UNHEALTHY = 0
        return weighted_sum / total_weight

    @property
    def last_result(self) -> CompositeHealth | None:
        return self._last_result

    def summary(self) -> dict[str, Any]:
        return {
            "registered_checks": self.check_count,
            "total_runs": self._total_runs,
            "last_status": self._last_result.status.name.lower() if self._last_result else "unknown",
            "last_score": round(self._last_result.score, 1) if self._last_result else None,
        }
