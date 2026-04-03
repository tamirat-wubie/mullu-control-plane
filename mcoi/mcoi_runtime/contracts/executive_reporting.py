"""Purpose: executive reporting / KPI / outcome analytics contracts.
Governance scope: typed descriptors for KPI definitions, metric values,
    trend snapshots, rollup records, outcome/efficiency/cost-effectiveness/
    reliability reports, executive dashboard snapshots, and reporting decisions.
Dependencies: _base contract utilities.
Invariants:
  - Every KPI has explicit kind and window.
  - Metric values are immutable and timestamped.
  - Trends are deterministic given metric history.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


def _parse_datetime_text(value: str, field_name: str) -> datetime:
    """Parse a validated datetime text deterministically."""
    require_datetime_text(value, field_name)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _require_period_start_before_end(period_start: str, period_end: str) -> None:
    """Validate that a reporting period has a strict forward ordering."""
    start_dt = _parse_datetime_text(period_start, "period_start")
    end_dt = _parse_datetime_text(period_end, "period_end")
    if start_dt >= end_dt:
        raise ValueError(
            f"period_start ({period_start}) must be before period_end ({period_end})"
        )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KPIKind(Enum):
    """Kind of KPI being tracked."""
    CAMPAIGN_COMPLETION_RATE = "campaign_completion_rate"
    WAITING_ON_HUMAN_DELAY = "waiting_on_human_delay"
    ESCALATION_FREQUENCY = "escalation_frequency"
    CONNECTOR_SUCCESS_RATE = "connector_success_rate"
    BUDGET_BURN_VS_COMPLETION = "budget_burn_vs_completion"
    OVERDUE_OBLIGATION_RATE = "overdue_obligation_rate"
    COST_PER_CLOSURE = "cost_per_closure"
    PORTFOLIO_BLOCKED_COUNT = "portfolio_blocked_count"
    FAULT_DRILL_SUCCESS_RATE = "fault_drill_success_rate"
    CUSTOM = "custom"


class MetricWindow(Enum):
    """Time window for metric aggregation."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class TrendDirection(Enum):
    """Direction of a trend."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    INSUFFICIENT_DATA = "insufficient_data"


class RollupScope(Enum):
    """Scope at which metrics are rolled up."""
    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    CAMPAIGN = "campaign"
    TEAM = "team"
    FUNCTION = "function"
    CONNECTOR = "connector"
    DOMAIN_PACK = "domain_pack"
    CHANNEL = "channel"


class ReportStatus(Enum):
    """Status of a generated report."""
    DRAFT = "draft"
    FINAL = "final"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KPIDefinition(ContractRecord):
    """Definition of a KPI to track."""

    kpi_id: str = ""
    name: str = ""
    kind: KPIKind = KPIKind.CUSTOM
    description: str = ""
    unit: str = ""
    window: MetricWindow = MetricWindow.DAILY
    target_value: float = 0.0
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    higher_is_better: bool = True
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kpi_id", require_non_empty_text(self.kpi_id, "kpi_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.kind, KPIKind):
            raise ValueError("kind must be a KPIKind")
        if not isinstance(self.window, MetricWindow):
            raise ValueError("window must be a MetricWindow")
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.higher_is_better, bool):
            raise ValueError("higher_is_better must be a boolean")
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class KPIValue(ContractRecord):
    """A single recorded metric value."""

    value_id: str = ""
    kpi_id: str = ""
    value: float = 0.0
    window: MetricWindow = MetricWindow.DAILY
    period_start: str = ""
    period_end: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    sample_count: int = 0
    recorded_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "value_id", require_non_empty_text(self.value_id, "value_id"))
        object.__setattr__(self, "kpi_id", require_non_empty_text(self.kpi_id, "kpi_id"))
        if not isinstance(self.window, MetricWindow):
            raise ValueError("window must be a MetricWindow")
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        object.__setattr__(self, "sample_count", require_non_negative_int(self.sample_count, "sample_count"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class TrendSnapshot(ContractRecord):
    """Trend analysis over a series of metric values."""

    trend_id: str = ""
    kpi_id: str = ""
    direction: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    current_value: float = 0.0
    previous_value: float = 0.0
    change_pct: float = 0.0
    data_points: int = 0
    window: MetricWindow = MetricWindow.DAILY
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    computed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "trend_id", require_non_empty_text(self.trend_id, "trend_id"))
        object.__setattr__(self, "kpi_id", require_non_empty_text(self.kpi_id, "kpi_id"))
        if not isinstance(self.direction, TrendDirection):
            raise ValueError("direction must be a TrendDirection")
        if not isinstance(self.window, MetricWindow):
            raise ValueError("window must be a MetricWindow")
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        object.__setattr__(self, "data_points", require_non_negative_int(self.data_points, "data_points"))
        require_datetime_text(self.computed_at, "computed_at")


@dataclass(frozen=True, slots=True)
class RollupRecord(ContractRecord):
    """Aggregated metric rollup across a scope."""

    rollup_id: str = ""
    kpi_id: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    window: MetricWindow = MetricWindow.DAILY
    period_start: str = ""
    period_end: str = ""
    total: float = 0.0
    count: int = 0
    average: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0
    computed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rollup_id", require_non_empty_text(self.rollup_id, "rollup_id"))
        object.__setattr__(self, "kpi_id", require_non_empty_text(self.kpi_id, "kpi_id"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.window, MetricWindow):
            raise ValueError("window must be a MetricWindow")
        object.__setattr__(self, "count", require_non_negative_int(self.count, "count"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.computed_at, "computed_at")


@dataclass(frozen=True, slots=True)
class OutcomeReport(ContractRecord):
    """Report on campaign/portfolio outcomes."""

    report_id: str = ""
    title: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    status: ReportStatus = ReportStatus.FINAL
    total_campaigns: int = 0
    completed_campaigns: int = 0
    failed_campaigns: int = 0
    blocked_campaigns: int = 0
    completion_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    escalation_count: int = 0
    overdue_count: int = 0
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.status, ReportStatus):
            raise ValueError("status must be a ReportStatus")
        object.__setattr__(self, "total_campaigns", require_non_negative_int(self.total_campaigns, "total_campaigns"))
        object.__setattr__(self, "completed_campaigns", require_non_negative_int(self.completed_campaigns, "completed_campaigns"))
        object.__setattr__(self, "failed_campaigns", require_non_negative_int(self.failed_campaigns, "failed_campaigns"))
        object.__setattr__(self, "blocked_campaigns", require_non_negative_int(self.blocked_campaigns, "blocked_campaigns"))
        if self.completed_campaigns + self.failed_campaigns + self.blocked_campaigns > self.total_campaigns:
            raise ValueError("sum of completed + failed + blocked cannot exceed total_campaigns")
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        object.__setattr__(self, "avg_duration_seconds", require_non_negative_float(self.avg_duration_seconds, "avg_duration_seconds"))
        object.__setattr__(self, "escalation_count", require_non_negative_int(self.escalation_count, "escalation_count"))
        object.__setattr__(self, "overdue_count", require_non_negative_int(self.overdue_count, "overdue_count"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EfficiencyReport(ContractRecord):
    """Report on team/function/connector efficiency."""

    report_id: str = ""
    title: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    status: ReportStatus = ReportStatus.FINAL
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    success_rate: float = 0.0
    avg_latency_seconds: float = 0.0
    waiting_on_human_seconds: float = 0.0
    utilization: float = 0.0
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.status, ReportStatus):
            raise ValueError("status must be a ReportStatus")
        object.__setattr__(self, "total_actions", require_non_negative_int(self.total_actions, "total_actions"))
        object.__setattr__(self, "successful_actions", require_non_negative_int(self.successful_actions, "successful_actions"))
        object.__setattr__(self, "failed_actions", require_non_negative_int(self.failed_actions, "failed_actions"))
        if self.successful_actions + self.failed_actions > self.total_actions:
            raise ValueError("successful + failed cannot exceed total_actions")
        object.__setattr__(self, "success_rate", require_unit_float(self.success_rate, "success_rate"))
        object.__setattr__(self, "avg_latency_seconds", require_non_negative_float(self.avg_latency_seconds, "avg_latency_seconds"))
        object.__setattr__(self, "waiting_on_human_seconds", require_non_negative_float(self.waiting_on_human_seconds, "waiting_on_human_seconds"))
        object.__setattr__(self, "utilization", require_unit_float(self.utilization, "utilization"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CostEffectivenessReport(ContractRecord):
    """Report combining budget burn with campaign outcomes."""

    report_id: str = ""
    title: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    status: ReportStatus = ReportStatus.FINAL
    total_spend: float = 0.0
    budget_limit: float = 0.0
    burn_rate: float = 0.0
    completed_campaigns: int = 0
    cost_per_completion: float = 0.0
    currency: str = "USD"
    roi_estimate: float = 0.0
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.status, ReportStatus):
            raise ValueError("status must be a ReportStatus")
        object.__setattr__(self, "total_spend", require_non_negative_float(self.total_spend, "total_spend"))
        object.__setattr__(self, "budget_limit", require_non_negative_float(self.budget_limit, "budget_limit"))
        object.__setattr__(self, "burn_rate", require_unit_float(self.burn_rate, "burn_rate"))
        object.__setattr__(self, "completed_campaigns", require_non_negative_int(self.completed_campaigns, "completed_campaigns"))
        object.__setattr__(self, "cost_per_completion", require_non_negative_float(self.cost_per_completion, "cost_per_completion"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReliabilityReport(ContractRecord):
    """Report on system/connector reliability."""

    report_id: str = ""
    title: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    status: ReportStatus = ReportStatus.FINAL
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    success_rate: float = 0.0
    fault_drill_count: int = 0
    fault_drill_pass_count: int = 0
    fault_drill_success_rate: float = 0.0
    recovery_count: int = 0
    mean_time_to_recovery_seconds: float = 0.0
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.status, ReportStatus):
            raise ValueError("status must be a ReportStatus")
        object.__setattr__(self, "total_operations", require_non_negative_int(self.total_operations, "total_operations"))
        object.__setattr__(self, "successful_operations", require_non_negative_int(self.successful_operations, "successful_operations"))
        object.__setattr__(self, "failed_operations", require_non_negative_int(self.failed_operations, "failed_operations"))
        if self.successful_operations + self.failed_operations > self.total_operations:
            raise ValueError("successful + failed cannot exceed total_operations")
        object.__setattr__(self, "success_rate", require_unit_float(self.success_rate, "success_rate"))
        object.__setattr__(self, "fault_drill_count", require_non_negative_int(self.fault_drill_count, "fault_drill_count"))
        object.__setattr__(self, "fault_drill_pass_count", require_non_negative_int(self.fault_drill_pass_count, "fault_drill_pass_count"))
        if self.fault_drill_pass_count > self.fault_drill_count:
            raise ValueError("fault_drill_pass_count cannot exceed fault_drill_count")
        object.__setattr__(self, "fault_drill_success_rate", require_unit_float(self.fault_drill_success_rate, "fault_drill_success_rate"))
        object.__setattr__(self, "recovery_count", require_non_negative_int(self.recovery_count, "recovery_count"))
        object.__setattr__(self, "mean_time_to_recovery_seconds", require_non_negative_float(self.mean_time_to_recovery_seconds, "mean_time_to_recovery_seconds"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutiveDashboardSnapshot(ContractRecord):
    """Point-in-time executive dashboard with cross-cutting KPIs."""

    snapshot_id: str = ""
    title: str = ""
    status: ReportStatus = ReportStatus.FINAL
    total_kpis: int = 0
    kpis_on_target: int = 0
    kpis_warning: int = 0
    kpis_critical: int = 0
    active_campaigns: int = 0
    blocked_campaigns: int = 0
    active_budgets: int = 0
    total_spend: float = 0.0
    budget_utilization: float = 0.0
    connector_health_pct: float = 0.0
    overall_trend: TrendDirection = TrendDirection.STABLE
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, ReportStatus):
            raise ValueError("status must be a ReportStatus")
        if not isinstance(self.overall_trend, TrendDirection):
            raise ValueError("overall_trend must be a TrendDirection")
        object.__setattr__(self, "total_kpis", require_non_negative_int(self.total_kpis, "total_kpis"))
        object.__setattr__(self, "kpis_on_target", require_non_negative_int(self.kpis_on_target, "kpis_on_target"))
        object.__setattr__(self, "kpis_warning", require_non_negative_int(self.kpis_warning, "kpis_warning"))
        object.__setattr__(self, "kpis_critical", require_non_negative_int(self.kpis_critical, "kpis_critical"))
        if self.kpis_on_target + self.kpis_warning + self.kpis_critical > self.total_kpis:
            raise ValueError("kpi status counts cannot exceed total_kpis")
        object.__setattr__(self, "active_campaigns", require_non_negative_int(self.active_campaigns, "active_campaigns"))
        object.__setattr__(self, "blocked_campaigns", require_non_negative_int(self.blocked_campaigns, "blocked_campaigns"))
        object.__setattr__(self, "active_budgets", require_non_negative_int(self.active_budgets, "active_budgets"))
        object.__setattr__(self, "total_spend", require_non_negative_float(self.total_spend, "total_spend"))
        object.__setattr__(self, "budget_utilization", require_unit_float(self.budget_utilization, "budget_utilization"))
        object.__setattr__(self, "connector_health_pct", require_unit_float(self.connector_health_pct, "connector_health_pct"))
        _require_period_start_before_end(self.period_start, self.period_end)
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReportingDecision(ContractRecord):
    """Decision about what to report and how."""

    decision_id: str = ""
    report_type: str = ""
    scope: RollupScope = RollupScope.GLOBAL
    scope_ref_id: str = ""
    window: MetricWindow = MetricWindow.DAILY
    include_trends: bool = True
    include_breakdowns: bool = True
    reason: str = ""
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "report_type", require_non_empty_text(self.report_type, "report_type"))
        if not isinstance(self.scope, RollupScope):
            raise ValueError("scope must be a RollupScope")
        if not isinstance(self.window, MetricWindow):
            raise ValueError("window must be a MetricWindow")
        if not isinstance(self.include_trends, bool):
            raise ValueError("include_trends must be a boolean")
        if not isinstance(self.include_breakdowns, bool):
            raise ValueError("include_breakdowns must be a boolean")
        require_datetime_text(self.decided_at, "decided_at")
