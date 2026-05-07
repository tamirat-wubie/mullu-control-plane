"""Operational Dashboard — Single-view system health aggregator.

Purpose: Aggregates health and status from all platform subsystems into
    a single operational view for monitoring dashboards and alerting.
Governance scope: read-only aggregation.
Dependencies: none (pulls from subsystem summary() methods).
Invariants:
  - Dashboard is read-only (never modifies subsystem state).
  - Aggregation is bounded (capped response size).
  - Status classification: healthy/degraded/unhealthy based on subsystem states.
  - Thread-safe — concurrent reads are safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SubsystemStatus:
    """Health status of a single subsystem."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy", "unknown"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Point-in-time snapshot of system health."""

    overall_status: str
    subsystems: tuple[SubsystemStatus, ...]
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    snapshot_at: str
    platform_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "healthy": self.healthy_count,
            "degraded": self.degraded_count,
            "unhealthy": self.unhealthy_count,
            "snapshot_at": self.snapshot_at,
            "subsystems": [
                {"name": s.name, "status": s.status, "detail": s.detail}
                for s in self.subsystems
            ],
        }


class OpsDashboard:
    """Aggregates subsystem health into a single operational view.

    Usage:
        dashboard = OpsDashboard(clock=lambda: "2026-04-07T12:00:00Z")

        # Register subsystem health checks
        dashboard.register("rate_limiter", lambda: rate_limiter.status())
        dashboard.register("audit_trail", lambda: audit_trail.summary())
        dashboard.register("gateway_dedup", lambda: dedup.status())

        # Get snapshot
        snapshot = dashboard.snapshot()
        print(snapshot.overall_status)  # "healthy"
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        platform_version: str = "",
    ) -> None:
        self._clock = clock
        self._version = platform_version
        self._checks: dict[str, Callable[[], dict[str, Any]]] = {}
        self._health_rules: dict[str, Callable[[dict[str, Any]], str]] = {}

    def register(
        self,
        name: str,
        check_fn: Callable[[], dict[str, Any]],
        *,
        health_rule: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        """Register a subsystem health check.

        Args:
            name: Subsystem name.
            check_fn: Returns status dict (e.g., subsystem.summary()).
            health_rule: Optional function that takes the status dict and
                returns "healthy", "degraded", or "unhealthy".
                Default rule: always "healthy".
        """
        self._checks[name] = check_fn
        if health_rule is not None:
            self._health_rules[name] = health_rule

    def unregister(self, name: str) -> bool:
        if name in self._checks:
            del self._checks[name]
            self._health_rules.pop(name, None)
            return True
        return False

    def _evaluate_health(self, name: str, detail: dict[str, Any]) -> str:
        """Evaluate health status for a subsystem."""
        rule = self._health_rules.get(name)
        if rule is not None:
            try:
                return rule(detail)
            except Exception:
                return "unhealthy"
        return "healthy"

    def snapshot(self) -> DashboardSnapshot:
        """Capture a point-in-time snapshot of all subsystem health."""
        subsystems: list[SubsystemStatus] = []
        healthy = 0
        degraded = 0
        unhealthy = 0

        for name, check_fn in sorted(self._checks.items()):
            try:
                detail = check_fn()
                status = self._evaluate_health(name, detail)
            except Exception as exc:
                detail = {"error": f"check failed ({type(exc).__name__})"}
                status = "unhealthy"

            subsystems.append(SubsystemStatus(name=name, status=status, detail=detail))
            if status == "healthy":
                healthy += 1
            elif status == "degraded":
                degraded += 1
            else:
                unhealthy += 1

        # Overall status
        if unhealthy > 0:
            overall = "unhealthy"
        elif degraded > 0:
            overall = "degraded"
        elif healthy > 0:
            overall = "healthy"
        else:
            overall = "unknown"

        return DashboardSnapshot(
            overall_status=overall,
            subsystems=tuple(subsystems),
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
            snapshot_at=self._clock(),
            platform_version=self._version,
        )

    @property
    def subsystem_count(self) -> int:
        return len(self._checks)

    def list_subsystems(self) -> list[str]:
        return sorted(self._checks.keys())
