"""Purpose: executive reporting integration bridge.
Governance scope: composing KPI/report generation with campaigns, portfolio,
    availability, financials, connectors, faults, benchmarks, memory mesh,
    and operational graph.
Dependencies: executive_reporting engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every reporting operation emits events.
  - Report state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.executive_reporting import (
    CostEffectivenessReport,
    EfficiencyReport,
    ExecutiveDashboardSnapshot,
    KPIKind,
    MetricWindow,
    OutcomeReport,
    ReliabilityReport,
    RollupScope,
    TrendDirection,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .executive_reporting import ExecutiveReportingEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExecutiveReportingIntegration:
    """Integration bridge for executive reporting with all platform layers."""

    def __init__(
        self,
        reporting_engine: ExecutiveReportingEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(reporting_engine, ExecutiveReportingEngine):
            raise RuntimeCoreInvariantError("reporting_engine must be an ExecutiveReportingEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._reporting = reporting_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Campaign reporting
    # ------------------------------------------------------------------

    def report_from_campaigns(
        self,
        report_id: str,
        title: str,
        *,
        scope: RollupScope = RollupScope.CAMPAIGN,
        scope_ref_id: str = "",
        total_campaigns: int = 0,
        completed_campaigns: int = 0,
        failed_campaigns: int = 0,
        blocked_campaigns: int = 0,
        avg_duration_seconds: float = 0.0,
        escalation_count: int = 0,
        overdue_count: int = 0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate an outcome report from campaign data."""
        report = self._reporting.build_outcome_report(
            report_id, title,
            scope=scope,
            scope_ref_id=scope_ref_id,
            total_campaigns=total_campaigns,
            completed_campaigns=completed_campaigns,
            failed_campaigns=failed_campaigns,
            blocked_campaigns=blocked_campaigns,
            avg_duration_seconds=avg_duration_seconds,
            escalation_count=escalation_count,
            overdue_count=overdue_count,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "campaign_report_generated", {
            "report_id": report_id,
            "total": total_campaigns,
            "completion_rate": report.completion_rate,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "outcome",
            "scope": scope.value,
            "completion_rate": report.completion_rate,
            "total_campaigns": total_campaigns,
            "completed_campaigns": completed_campaigns,
            "failed_campaigns": failed_campaigns,
            "blocked_campaigns": blocked_campaigns,
            "escalation_count": escalation_count,
            "overdue_count": overdue_count,
        }

    # ------------------------------------------------------------------
    # Portfolio reporting
    # ------------------------------------------------------------------

    def report_from_portfolio(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_campaigns: int = 0,
        completed_campaigns: int = 0,
        blocked_campaigns: int = 0,
        avg_duration_seconds: float = 0.0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate an outcome report from portfolio data."""
        report = self._reporting.build_outcome_report(
            report_id, title,
            scope=RollupScope.PORTFOLIO,
            scope_ref_id=scope_ref_id,
            total_campaigns=total_campaigns,
            completed_campaigns=completed_campaigns,
            blocked_campaigns=blocked_campaigns,
            avg_duration_seconds=avg_duration_seconds,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "portfolio_report_generated", {
            "report_id": report_id,
            "blocked": blocked_campaigns,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "outcome",
            "scope": "portfolio",
            "completion_rate": report.completion_rate,
            "blocked_campaigns": blocked_campaigns,
        }

    # ------------------------------------------------------------------
    # Availability reporting
    # ------------------------------------------------------------------

    def report_from_availability(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_actions: int = 0,
        successful_actions: int = 0,
        failed_actions: int = 0,
        waiting_on_human_seconds: float = 0.0,
        avg_latency_seconds: float = 0.0,
        utilization: float = 0.0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate an efficiency report from availability data."""
        report = self._reporting.build_efficiency_report(
            report_id, title,
            scope=RollupScope.TEAM,
            scope_ref_id=scope_ref_id,
            total_actions=total_actions,
            successful_actions=successful_actions,
            failed_actions=failed_actions,
            waiting_on_human_seconds=waiting_on_human_seconds,
            avg_latency_seconds=avg_latency_seconds,
            utilization=utilization,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "availability_report_generated", {
            "report_id": report_id,
            "waiting_on_human": waiting_on_human_seconds,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "efficiency",
            "scope": "team",
            "success_rate": report.success_rate,
            "waiting_on_human_seconds": waiting_on_human_seconds,
            "utilization": utilization,
        }

    # ------------------------------------------------------------------
    # Financial reporting
    # ------------------------------------------------------------------

    def report_from_financials(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_spend: float = 0.0,
        budget_limit: float = 0.0,
        completed_campaigns: int = 0,
        currency: str = "USD",
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate a cost-effectiveness report from financial data."""
        report = self._reporting.build_cost_effectiveness_report(
            report_id, title,
            scope=RollupScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            total_spend=total_spend,
            budget_limit=budget_limit,
            completed_campaigns=completed_campaigns,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "financial_report_generated", {
            "report_id": report_id,
            "burn_rate": report.burn_rate,
            "cost_per_completion": report.cost_per_completion,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "cost_effectiveness",
            "scope": "global",
            "total_spend": total_spend,
            "budget_limit": budget_limit,
            "burn_rate": report.burn_rate,
            "cost_per_completion": report.cost_per_completion,
            "roi_estimate": report.roi_estimate,
            "currency": currency,
        }

    # ------------------------------------------------------------------
    # Connector reporting
    # ------------------------------------------------------------------

    def report_from_connectors(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_operations: int = 0,
        successful_operations: int = 0,
        failed_operations: int = 0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate a reliability report from connector data."""
        report = self._reporting.build_reliability_report(
            report_id, title,
            scope=RollupScope.CONNECTOR,
            scope_ref_id=scope_ref_id,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "connector_report_generated", {
            "report_id": report_id,
            "success_rate": report.success_rate,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "reliability",
            "scope": "connector",
            "success_rate": report.success_rate,
            "total_operations": total_operations,
            "failed_operations": failed_operations,
        }

    # ------------------------------------------------------------------
    # Fault reporting
    # ------------------------------------------------------------------

    def report_from_faults(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_operations: int = 0,
        successful_operations: int = 0,
        failed_operations: int = 0,
        fault_drill_count: int = 0,
        fault_drill_pass_count: int = 0,
        recovery_count: int = 0,
        mean_time_to_recovery_seconds: float = 0.0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate a reliability report from fault injection/drill data."""
        report = self._reporting.build_reliability_report(
            report_id, title,
            scope=RollupScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            fault_drill_count=fault_drill_count,
            fault_drill_pass_count=fault_drill_pass_count,
            recovery_count=recovery_count,
            mean_time_to_recovery_seconds=mean_time_to_recovery_seconds,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "fault_report_generated", {
            "report_id": report_id,
            "drill_rate": report.fault_drill_success_rate,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "reliability",
            "scope": "global",
            "success_rate": report.success_rate,
            "fault_drill_success_rate": report.fault_drill_success_rate,
            "recovery_count": recovery_count,
            "mean_time_to_recovery_seconds": mean_time_to_recovery_seconds,
        }

    # ------------------------------------------------------------------
    # Benchmark reporting
    # ------------------------------------------------------------------

    def report_from_benchmarks(
        self,
        report_id: str,
        title: str,
        *,
        scope_ref_id: str = "",
        total_actions: int = 0,
        successful_actions: int = 0,
        failed_actions: int = 0,
        avg_latency_seconds: float = 0.0,
        period_start: str = "",
        period_end: str = "",
    ) -> dict[str, Any]:
        """Generate an efficiency report from benchmark data."""
        report = self._reporting.build_efficiency_report(
            report_id, title,
            scope=RollupScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            total_actions=total_actions,
            successful_actions=successful_actions,
            failed_actions=failed_actions,
            avg_latency_seconds=avg_latency_seconds,
            period_start=period_start,
            period_end=period_end,
        )
        _emit(self._events, "benchmark_report_generated", {
            "report_id": report_id,
            "success_rate": report.success_rate,
        }, report_id)
        return {
            "report_id": report_id,
            "report_type": "efficiency",
            "scope": "global",
            "success_rate": report.success_rate,
            "avg_latency_seconds": avg_latency_seconds,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_reports_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist reporting state to memory mesh."""
        now = _now_iso()

        reports = self._reporting.get_reports()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_kpis": self._reporting.kpi_count,
            "total_metrics": self._reporting.metric_count,
            "total_reports": self._reporting.report_count,
            "report_types": list(set(
                type(r).__name__ for r in reports
            )),
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-rpt", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Reporting state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("reporting", "kpi", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "reports_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_reports_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return reporting state suitable for operational graph consumption."""
        reports = self._reporting.get_reports()

        # Count by type
        outcome_count = sum(1 for r in reports if isinstance(r, OutcomeReport))
        efficiency_count = sum(1 for r in reports if isinstance(r, EfficiencyReport))
        cost_count = sum(1 for r in reports if isinstance(r, CostEffectivenessReport))
        reliability_count = sum(1 for r in reports if isinstance(r, ReliabilityReport))
        dashboard_count = sum(1 for r in reports if isinstance(r, ExecutiveDashboardSnapshot))

        return {
            "scope_ref_id": scope_ref_id,
            "total_kpis": self._reporting.kpi_count,
            "total_metrics": self._reporting.metric_count,
            "total_reports": self._reporting.report_count,
            "outcome_reports": outcome_count,
            "efficiency_reports": efficiency_count,
            "cost_effectiveness_reports": cost_count,
            "reliability_reports": reliability_count,
            "dashboard_snapshots": dashboard_count,
        }
