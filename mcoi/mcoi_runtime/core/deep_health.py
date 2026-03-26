"""Phase 203C — Deep Health Check.

Purpose: System-wide diagnostic that checks all subsystem health.
    Goes beyond simple /health to probe every governed component.
Governance scope: health check execution only.
Dependencies: all subsystem interfaces.
Invariants:
  - Each check is independent — one failure doesn't skip others.
  - Check results include timing information.
  - Overall health degrades to worst component health.
  - Checks are read-only — never modify state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """Health of a single component."""

    name: str
    status: HealthStatus
    latency_ms: float
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SystemHealth:
    """Full system health report."""

    overall: HealthStatus
    components: tuple[ComponentHealth, ...]
    total_latency_ms: float
    checked_at: str


class DeepHealthChecker:
    """Runs all registered health checks and produces a system report."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._checks: dict[str, Callable[[], dict[str, Any]]] = {}

    def register(self, name: str, check_fn: Callable[[], dict[str, Any]]) -> None:
        """Register a health check function.

        The function should return a dict with at least "status" key
        (healthy/degraded/unhealthy) and optional detail fields.
        """
        self._checks[name] = check_fn

    def run(self) -> SystemHealth:
        """Run all health checks and produce a system report."""
        components: list[ComponentHealth] = []
        total_start = time.monotonic()

        for name, check_fn in sorted(self._checks.items()):
            start = time.monotonic()
            try:
                result = check_fn()
                latency = (time.monotonic() - start) * 1000
                status = HealthStatus(result.get("status", "healthy"))
                components.append(ComponentHealth(
                    name=name,
                    status=status,
                    latency_ms=round(latency, 2),
                    detail=result,
                ))
            except Exception as exc:
                latency = (time.monotonic() - start) * 1000
                components.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=round(latency, 2),
                    detail={"error": str(exc)},
                ))

        total_latency = (time.monotonic() - total_start) * 1000

        # Overall = worst component status
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return SystemHealth(
            overall=overall,
            components=tuple(components),
            total_latency_ms=round(total_latency, 2),
            checked_at=self._clock(),
        )

    @property
    def check_count(self) -> int:
        return len(self._checks)
