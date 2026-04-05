"""Purpose: executive reporting / KPI / outcome analytics engine.
Governance scope: KPI registration, metric recording, rollup computation,
    trend analysis, outcome/efficiency/cost-effectiveness/reliability
    report generation, executive dashboard snapshots.
Dependencies: executive_reporting contracts, event_spine, core invariants.
Invariants:
  - No duplicate KPI or value IDs.
  - Trends are deterministic given metric history.
  - All returns are immutable.
  - Every mutation emits an event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.executive_reporting import (
    CostEffectivenessReport,
    EfficiencyReport,
    ExecutiveDashboardSnapshot,
    KPIDefinition,
    KPIKind,
    KPIValue,
    MetricWindow,
    OutcomeReport,
    ReliabilityReport,
    ReportingDecision,
    ReportStatus,
    RollupRecord,
    RollupScope,
    TrendDirection,
    TrendSnapshot,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rpt", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExecutiveReportingEngine:
    """Engine for KPI tracking, metric rollups, trend analysis, and report generation."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._kpis: dict[str, KPIDefinition] = {}
        self._values: dict[str, KPIValue] = {}
        self._values_by_kpi: dict[str, list[str]] = {}
        self._rollups: list[RollupRecord] = []
        self._trends: list[TrendSnapshot] = []
        self._reports: list[Any] = []
        self._decisions: list[ReportingDecision] = []

    # ------------------------------------------------------------------
    # KPI registration
    # ------------------------------------------------------------------

    def register_kpi(
        self,
        kpi_id: str,
        name: str,
        kind: KPIKind,
        *,
        description: str = "",
        unit: str = "",
        window: MetricWindow = MetricWindow.DAILY,
        target_value: float = 0.0,
        warning_threshold: float = 0.0,
        critical_threshold: float = 0.0,
        higher_is_better: bool = True,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        tags: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> KPIDefinition:
        if kpi_id in self._kpis:
            raise RuntimeCoreInvariantError("KPI already exists")
        now = _now_iso()
        kpi = KPIDefinition(
            kpi_id=kpi_id,
            name=name,
            kind=kind,
            description=description,
            unit=unit,
            window=window,
            target_value=target_value,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            higher_is_better=higher_is_better,
            scope=scope,
            scope_ref_id=scope_ref_id if scope_ref_id else kpi_id,
            tags=tags,
            created_at=now,
            metadata=metadata or {},
        )
        self._kpis[kpi_id] = kpi
        _emit(self._events, "kpi_registered", {
            "kpi_id": kpi_id,
            "kind": kind.value,
        }, kpi_id)
        return kpi

    def get_kpi(self, kpi_id: str) -> KPIDefinition | None:
        return self._kpis.get(kpi_id)

    # ------------------------------------------------------------------
    # Metric recording
    # ------------------------------------------------------------------

    def record_metric(
        self,
        value_id: str,
        kpi_id: str,
        value: float,
        period_start: str,
        period_end: str,
        *,
        window: MetricWindow = MetricWindow.DAILY,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        sample_count: int = 1,
    ) -> KPIValue:
        if value_id in self._values:
            raise RuntimeCoreInvariantError("metric value already exists")
        if kpi_id not in self._kpis:
            raise RuntimeCoreInvariantError("KPI not found")
        now = _now_iso()
        kpi_value = KPIValue(
            value_id=value_id,
            kpi_id=kpi_id,
            value=value,
            window=window,
            period_start=period_start,
            period_end=period_end,
            scope=scope,
            scope_ref_id=scope_ref_id or kpi_id,
            sample_count=sample_count,
            recorded_at=now,
        )
        self._values[value_id] = kpi_value
        self._values_by_kpi.setdefault(kpi_id, []).append(value_id)
        _emit(self._events, "metric_recorded", {
            "value_id": value_id,
            "kpi_id": kpi_id,
            "value": value,
        }, kpi_id)
        return kpi_value

    def get_values(self, kpi_id: str) -> tuple[KPIValue, ...]:
        ids = self._values_by_kpi.get(kpi_id, [])
        return tuple(self._values[vid] for vid in ids if vid in self._values)

    # ------------------------------------------------------------------
    # Rollup computation
    # ------------------------------------------------------------------

    def rollup(
        self,
        kpi_id: str,
        period_start: str,
        period_end: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        window: MetricWindow = MetricWindow.DAILY,
    ) -> RollupRecord:
        if kpi_id not in self._kpis:
            raise RuntimeCoreInvariantError("KPI not found")

        values = self.get_values(kpi_id)
        # Filter by period
        filtered: list[float] = []
        for v in values:
            if scope_ref_id and v.scope_ref_id != scope_ref_id:
                continue
            filtered.append(v.value)

        now = _now_iso()
        count = len(filtered)
        total = sum(filtered) if filtered else 0.0
        average = total / count if count > 0 else 0.0
        minimum = min(filtered) if filtered else 0.0
        maximum = max(filtered) if filtered else 0.0

        rollup_rec = RollupRecord(
            rollup_id=stable_identifier("rup", {"kpi": kpi_id, "ts": now}),
            kpi_id=kpi_id,
            scope=scope,
            scope_ref_id=scope_ref_id or kpi_id,
            window=window,
            period_start=period_start,
            period_end=period_end,
            total=total,
            count=count,
            average=average,
            minimum=minimum,
            maximum=maximum,
            computed_at=now,
        )
        self._rollups.append(rollup_rec)
        _emit(self._events, "rollup_computed", {
            "kpi_id": kpi_id,
            "count": count,
            "average": average,
        }, kpi_id)
        return rollup_rec

    # ------------------------------------------------------------------
    # Trend computation
    # ------------------------------------------------------------------

    def compute_trend(
        self,
        kpi_id: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        window: MetricWindow = MetricWindow.DAILY,
    ) -> TrendSnapshot:
        if kpi_id not in self._kpis:
            raise RuntimeCoreInvariantError("KPI not found")

        kpi = self._kpis[kpi_id]
        values = self.get_values(kpi_id)
        if scope_ref_id:
            values = tuple(v for v in values if v.scope_ref_id == scope_ref_id)

        now = _now_iso()

        if len(values) < 2:
            return TrendSnapshot(
                trend_id=stable_identifier("trn", {"kpi": kpi_id, "ts": now}),
                kpi_id=kpi_id,
                direction=TrendDirection.INSUFFICIENT_DATA,
                current_value=values[0].value if values else 0.0,
                previous_value=0.0,
                change_pct=0.0,
                data_points=len(values),
                window=window,
                scope=scope,
                scope_ref_id=scope_ref_id or kpi_id,
                computed_at=now,
            )

        # Use last two values for trend
        sorted_vals = sorted(values, key=lambda v: v.period_end)
        current = sorted_vals[-1].value
        previous = sorted_vals[-2].value

        if previous != 0:
            change_pct = (current - previous) / abs(previous)
        else:
            change_pct = 1.0 if current > 0 else 0.0

        # Determine direction
        threshold = 0.05  # 5% change threshold
        if abs(change_pct) < threshold:
            direction = TrendDirection.STABLE
        elif kpi.higher_is_better:
            direction = TrendDirection.IMPROVING if change_pct > 0 else TrendDirection.DEGRADING
        else:
            direction = TrendDirection.IMPROVING if change_pct < 0 else TrendDirection.DEGRADING

        trend = TrendSnapshot(
            trend_id=stable_identifier("trn", {"kpi": kpi_id, "ts": now}),
            kpi_id=kpi_id,
            direction=direction,
            current_value=current,
            previous_value=previous,
            change_pct=change_pct,
            data_points=len(values),
            window=window,
            scope=scope,
            scope_ref_id=scope_ref_id or kpi_id,
            computed_at=now,
        )
        self._trends.append(trend)
        _emit(self._events, "trend_computed", {
            "kpi_id": kpi_id,
            "direction": direction.value,
            "change_pct": change_pct,
        }, kpi_id)
        return trend

    # ------------------------------------------------------------------
    # Report builders
    # ------------------------------------------------------------------

    def build_outcome_report(
        self,
        report_id: str,
        title: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
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
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeReport:
        now = _now_iso()
        completion_rate = completed_campaigns / total_campaigns if total_campaigns > 0 else 0.0

        report = OutcomeReport(
            report_id=report_id,
            title=title,
            scope=scope,
            scope_ref_id=scope_ref_id or report_id,
            total_campaigns=total_campaigns,
            completed_campaigns=completed_campaigns,
            failed_campaigns=failed_campaigns,
            blocked_campaigns=blocked_campaigns,
            completion_rate=min(1.0, completion_rate),
            avg_duration_seconds=avg_duration_seconds,
            escalation_count=escalation_count,
            overdue_count=overdue_count,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            metadata=metadata or {},
        )
        self._reports.append(report)
        _emit(self._events, "outcome_report_built", {
            "report_id": report_id,
            "total": total_campaigns,
            "completed": completed_campaigns,
        }, report_id)
        return report

    def build_efficiency_report(
        self,
        report_id: str,
        title: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        total_actions: int = 0,
        successful_actions: int = 0,
        failed_actions: int = 0,
        avg_latency_seconds: float = 0.0,
        waiting_on_human_seconds: float = 0.0,
        utilization: float = 0.0,
        period_start: str = "",
        period_end: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EfficiencyReport:
        now = _now_iso()
        success_rate = successful_actions / total_actions if total_actions > 0 else 0.0

        report = EfficiencyReport(
            report_id=report_id,
            title=title,
            scope=scope,
            scope_ref_id=scope_ref_id or report_id,
            total_actions=total_actions,
            successful_actions=successful_actions,
            failed_actions=failed_actions,
            success_rate=min(1.0, success_rate),
            avg_latency_seconds=avg_latency_seconds,
            waiting_on_human_seconds=waiting_on_human_seconds,
            utilization=utilization,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            metadata=metadata or {},
        )
        self._reports.append(report)
        _emit(self._events, "efficiency_report_built", {
            "report_id": report_id,
            "success_rate": success_rate,
        }, report_id)
        return report

    def build_cost_effectiveness_report(
        self,
        report_id: str,
        title: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
        scope_ref_id: str = "",
        total_spend: float = 0.0,
        budget_limit: float = 0.0,
        completed_campaigns: int = 0,
        currency: str = "USD",
        period_start: str = "",
        period_end: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CostEffectivenessReport:
        now = _now_iso()
        burn_rate = total_spend / budget_limit if budget_limit > 0 else 0.0
        cost_per_completion = total_spend / completed_campaigns if completed_campaigns > 0 else 0.0
        roi = (completed_campaigns / total_spend) if total_spend > 0 else 0.0

        report = CostEffectivenessReport(
            report_id=report_id,
            title=title,
            scope=scope,
            scope_ref_id=scope_ref_id or report_id,
            total_spend=total_spend,
            budget_limit=budget_limit,
            burn_rate=min(1.0, burn_rate),
            completed_campaigns=completed_campaigns,
            cost_per_completion=cost_per_completion,
            currency=currency,
            roi_estimate=roi,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            metadata=metadata or {},
        )
        self._reports.append(report)
        _emit(self._events, "cost_effectiveness_report_built", {
            "report_id": report_id,
            "burn_rate": burn_rate,
            "cost_per_completion": cost_per_completion,
        }, report_id)
        return report

    def build_reliability_report(
        self,
        report_id: str,
        title: str,
        *,
        scope: RollupScope = RollupScope.GLOBAL,
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
        metadata: dict[str, Any] | None = None,
    ) -> ReliabilityReport:
        now = _now_iso()
        success_rate = successful_operations / total_operations if total_operations > 0 else 0.0
        drill_rate = fault_drill_pass_count / fault_drill_count if fault_drill_count > 0 else 0.0

        report = ReliabilityReport(
            report_id=report_id,
            title=title,
            scope=scope,
            scope_ref_id=scope_ref_id or report_id,
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            success_rate=min(1.0, success_rate),
            fault_drill_count=fault_drill_count,
            fault_drill_pass_count=fault_drill_pass_count,
            fault_drill_success_rate=min(1.0, drill_rate),
            recovery_count=recovery_count,
            mean_time_to_recovery_seconds=mean_time_to_recovery_seconds,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            metadata=metadata or {},
        )
        self._reports.append(report)
        _emit(self._events, "reliability_report_built", {
            "report_id": report_id,
            "success_rate": success_rate,
            "drill_rate": drill_rate,
        }, report_id)
        return report

    def build_dashboard_snapshot(
        self,
        snapshot_id: str,
        title: str,
        *,
        kpi_statuses: dict[str, str] | None = None,
        active_campaigns: int = 0,
        blocked_campaigns: int = 0,
        active_budgets: int = 0,
        total_spend: float = 0.0,
        budget_utilization: float = 0.0,
        connector_health_pct: float = 1.0,
        overall_trend: TrendDirection = TrendDirection.STABLE,
        period_start: str = "",
        period_end: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutiveDashboardSnapshot:
        now = _now_iso()

        # Count KPI statuses
        statuses = kpi_statuses or {}
        on_target = sum(1 for s in statuses.values() if s == "on_target")
        warning = sum(1 for s in statuses.values() if s == "warning")
        critical = sum(1 for s in statuses.values() if s == "critical")
        total_kpis = len(statuses)

        snapshot = ExecutiveDashboardSnapshot(
            snapshot_id=snapshot_id,
            title=title,
            total_kpis=total_kpis,
            kpis_on_target=on_target,
            kpis_warning=warning,
            kpis_critical=critical,
            active_campaigns=active_campaigns,
            blocked_campaigns=blocked_campaigns,
            active_budgets=active_budgets,
            total_spend=total_spend,
            budget_utilization=min(1.0, budget_utilization),
            connector_health_pct=min(1.0, connector_health_pct),
            overall_trend=overall_trend,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            metadata=metadata or {},
        )
        self._reports.append(snapshot)
        _emit(self._events, "dashboard_snapshot_built", {
            "snapshot_id": snapshot_id,
            "total_kpis": total_kpis,
            "on_target": on_target,
            "warning": warning,
            "critical": critical,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # KPI status evaluation
    # ------------------------------------------------------------------

    def evaluate_kpi_status(self, kpi_id: str) -> str:
        """Evaluate current KPI status: on_target, warning, or critical."""
        kpi = self._kpis.get(kpi_id)
        if kpi is None:
            raise RuntimeCoreInvariantError("KPI not found")

        values = self.get_values(kpi_id)
        if not values:
            return "insufficient_data"

        current = sorted(values, key=lambda v: v.period_end)[-1].value

        if kpi.higher_is_better:
            if kpi.critical_threshold > 0 and current <= kpi.critical_threshold:
                return "critical"
            if kpi.warning_threshold > 0 and current <= kpi.warning_threshold:
                return "warning"
            return "on_target"
        else:
            if kpi.critical_threshold > 0 and current >= kpi.critical_threshold:
                return "critical"
            if kpi.warning_threshold > 0 and current >= kpi.warning_threshold:
                return "warning"
            return "on_target"

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_reports(self) -> tuple[Any, ...]:
        return tuple(self._reports)

    def get_rollups(self, kpi_id: str) -> tuple[RollupRecord, ...]:
        return tuple(r for r in self._rollups if r.kpi_id == kpi_id)

    def get_trends(self, kpi_id: str) -> tuple[TrendSnapshot, ...]:
        return tuple(t for t in self._trends if t.kpi_id == kpi_id)

    @property
    def kpi_count(self) -> int:
        return len(self._kpis)

    @property
    def metric_count(self) -> int:
        return len(self._values)

    @property
    def report_count(self) -> int:
        return len(self._reports)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts = [
            f"rollups={len(self._rollups)}",
            f"reports={len(self._reports)}",
        ]
        for kid in sorted(self._kpis):
            k = self._kpis[kid]
            parts.append(f"kpi:{kid}:{k.kind.value}")
        for vid in sorted(self._values):
            v = self._values[vid]
            parts.append(f"val:{vid}:{v.kpi_id}:{v.value}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest
