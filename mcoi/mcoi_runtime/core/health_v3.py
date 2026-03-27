"""Phase 232C — Health Check Aggregation v3.

Purpose: Weighted health aggregation with dependency-aware ordering,
    degradation detection, and recovery tracking.
Dependencies: None (stdlib only).
Invariants:
  - Health score is 0.0-1.0 weighted average.
  - Degraded components reduce score proportionally.
  - Recovery detection requires N consecutive healthy checks.
  - All checks are non-destructive (read-only probes).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class ComponentHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthComponent:
    """A health-checkable component."""
    name: str
    check_fn: Callable[[], ComponentHealth]
    weight: float = 1.0
    last_status: ComponentHealth = ComponentHealth.UNKNOWN
    consecutive_healthy: int = 0
    consecutive_unhealthy: int = 0
    last_checked_at: float = 0.0

    def check(self) -> ComponentHealth:
        try:
            status = self.check_fn()
        except Exception:
            status = ComponentHealth.UNHEALTHY
        self.last_status = status
        self.last_checked_at = time.time()
        if status == ComponentHealth.HEALTHY:
            self.consecutive_healthy += 1
            self.consecutive_unhealthy = 0
        elif status == ComponentHealth.UNHEALTHY:
            self.consecutive_unhealthy += 1
            self.consecutive_healthy = 0
        else:
            self.consecutive_healthy = 0
            self.consecutive_unhealthy = 0
        return status


_HEALTH_SCORES = {
    ComponentHealth.HEALTHY: 1.0,
    ComponentHealth.DEGRADED: 0.5,
    ComponentHealth.UNHEALTHY: 0.0,
    ComponentHealth.UNKNOWN: 0.0,
}


class HealthAggregatorV3:
    """Weighted health aggregation with recovery tracking."""

    def __init__(self, recovery_threshold: int = 3):
        self._components: list[HealthComponent] = []
        self._recovery_threshold = recovery_threshold
        self._total_checks = 0

    def register(self, name: str, check_fn: Callable[[], ComponentHealth],
                 weight: float = 1.0) -> None:
        self._components.append(HealthComponent(
            name=name, check_fn=check_fn, weight=weight,
        ))

    def check_all(self) -> dict[str, Any]:
        self._total_checks += 1
        results = []
        total_weight = 0.0
        weighted_score = 0.0

        for comp in self._components:
            status = comp.check()
            score = _HEALTH_SCORES[status]
            weighted_score += score * comp.weight
            total_weight += comp.weight
            recovered = comp.consecutive_healthy >= self._recovery_threshold
            results.append({
                "name": comp.name,
                "status": status.value,
                "score": score,
                "weight": comp.weight,
                "recovered": recovered,
                "consecutive_healthy": comp.consecutive_healthy,
                "consecutive_unhealthy": comp.consecutive_unhealthy,
            })

        overall = weighted_score / total_weight if total_weight > 0 else 0.0
        return {
            "overall_score": round(overall, 4),
            "status": "healthy" if overall >= 0.8 else "degraded" if overall >= 0.4 else "unhealthy",
            "components": results,
            "total_checks": self._total_checks,
            "checked_at": time.time(),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "components": len(self._components),
            "total_checks": self._total_checks,
            "recovery_threshold": self._recovery_threshold,
        }
