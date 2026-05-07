"""Phase 204C — Observability Dashboard Data Aggregation.

Purpose: Aggregates data from all subsystems into dashboard-ready views.
    Single source of truth for system-wide observability.
Governance scope: data aggregation and formatting only — read-only.
Dependencies: governance_metrics, tenant_budget, audit_trail, agent_protocol, certification_daemon.
Invariants:
  - All data is read-only — never modifies source systems.
  - Aggregation is on-demand — no background processing.
  - Dashboard data is always JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def _classify_observability_exception(exc: Exception) -> str:
    return f"observability source error ({type(exc).__name__})"


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Complete dashboard data snapshot."""

    system_health: dict[str, Any]
    llm_stats: dict[str, Any]
    tenant_stats: dict[str, Any]
    agent_stats: dict[str, Any]
    audit_stats: dict[str, Any]
    certification_stats: dict[str, Any]
    captured_at: str


class ObservabilityAggregator:
    """Aggregates data from all subsystems into dashboard views."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._sources: dict[str, Callable[[], dict[str, Any]]] = {}

    def register_source(self, name: str, fn: Callable[[], dict[str, Any]]) -> None:
        """Register a data source for the dashboard."""
        self._sources[name] = fn

    def collect(self, source_name: str) -> dict[str, Any]:
        """Collect data from a single named source."""
        fn = self._sources.get(source_name)
        if fn is None:
            return {"error": "observability source unavailable"}
        try:
            return fn()
        except Exception as exc:
            return {"error": _classify_observability_exception(exc)}

    def collect_all(self) -> dict[str, Any]:
        """Collect data from all registered sources."""
        result: dict[str, Any] = {}
        for name in sorted(self._sources):
            result[name] = self.collect(name)
        result["captured_at"] = self._clock()
        result["source_count"] = len(self._sources)
        return result

    def snapshot(self) -> DashboardSnapshot:
        """Create a typed dashboard snapshot."""
        data = self.collect_all()
        return DashboardSnapshot(
            system_health=data.get("health", {}),
            llm_stats=data.get("llm", {}),
            tenant_stats=data.get("tenants", {}),
            agent_stats=data.get("agents", {}),
            audit_stats=data.get("audit", {}),
            certification_stats=data.get("certification", {}),
            captured_at=self._clock(),
        )

    @property
    def source_count(self) -> int:
        return len(self._sources)

    def source_names(self) -> list[str]:
        return sorted(self._sources.keys())
