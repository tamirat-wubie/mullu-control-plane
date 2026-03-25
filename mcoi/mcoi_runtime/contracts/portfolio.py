"""Purpose: portfolio / scheduling / resource coordination contracts.
Governance scope: typed descriptors, statuses, scheduling modes, reservations,
    preemption records, capacity snapshots, and portfolio health/closure for
    multi-campaign coordination above the campaign execution layer.
Dependencies: _base contract utilities.
Invariants:
  - Every portfolio has explicit status and priority.
  - Scheduling decisions are immutable and deterministic.
  - Reservations are typed and scoped.
  - Capacity snapshots are point-in-time immutable.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PortfolioStatus(Enum):
    """Lifecycle status of a portfolio."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    REBALANCING = "rebalancing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PortfolioPriority(Enum):
    """Priority classification for portfolio-level ordering."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class SchedulingMode(Enum):
    """How campaigns are scheduled within a portfolio."""
    FIFO = "fifo"
    PRIORITY = "priority"
    DEADLINE = "deadline"
    SLA = "sla"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"


class ReservationType(Enum):
    """Type of resource reservation."""
    WORKER = "worker"
    TEAM = "team"
    FUNCTION = "function"
    CONNECTOR = "connector"
    CHANNEL = "channel"
    QUOTA = "quota"
    TIME_WINDOW = "time_window"


class ResourceClass(Enum):
    """Classification of schedulable resources."""
    HUMAN = "human"
    SYSTEM = "system"
    CONNECTOR = "connector"
    CHANNEL = "channel"
    COMPUTE = "compute"
    BUDGET = "budget"


class PreemptionPolicy(Enum):
    """Policy for campaign preemption."""
    NEVER = "never"
    PRIORITY_ONLY = "priority_only"
    DEADLINE_CRITICAL = "deadline_critical"
    ALWAYS = "always"
    SUPERVISOR_APPROVAL = "supervisor_approval"


class SchedulingVerdict(Enum):
    """Outcome of a scheduling decision."""
    SCHEDULED = "scheduled"
    DEFERRED = "deferred"
    PREEMPTED = "preempted"
    UNSCHEDULABLE = "unschedulable"
    ESCALATED = "escalated"
    WAITING = "waiting"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PortfolioDescriptor(ContractRecord):
    """Full descriptor for a registered portfolio."""

    portfolio_id: str = ""
    name: str = ""
    description: str = ""
    status: PortfolioStatus = PortfolioStatus.DRAFT
    priority: PortfolioPriority = PortfolioPriority.NORMAL
    scheduling_mode: SchedulingMode = SchedulingMode.PRIORITY
    preemption_policy: PreemptionPolicy = PreemptionPolicy.PRIORITY_ONLY
    owner_id: str = ""
    campaign_ids: tuple[str, ...] = ()
    max_concurrent: int = 10
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.status, PortfolioStatus):
            raise ValueError("status must be a PortfolioStatus")
        if not isinstance(self.priority, PortfolioPriority):
            raise ValueError("priority must be a PortfolioPriority")
        if not isinstance(self.scheduling_mode, SchedulingMode):
            raise ValueError("scheduling_mode must be a SchedulingMode")
        if not isinstance(self.preemption_policy, PreemptionPolicy):
            raise ValueError("preemption_policy must be a PreemptionPolicy")
        object.__setattr__(
            self, "max_concurrent",
            require_non_negative_int(self.max_concurrent, "max_concurrent"),
        )
        object.__setattr__(
            self, "campaign_ids",
            freeze_value(list(self.campaign_ids)),
        )
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class CampaignReservation(ContractRecord):
    """A campaign's slot in a portfolio with scheduling metadata."""

    reservation_id: str = ""
    portfolio_id: str = ""
    campaign_id: str = ""
    priority_score: float = 0.0
    deadline: str = ""
    sla_seconds: int = 0
    preemptible: bool = True
    waiting_on_human: bool = False
    domain_pack_id: str = ""
    scheduled: bool = False
    deferred: bool = False
    deferred_reason: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reservation_id",
            require_non_empty_text(self.reservation_id, "reservation_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        if not isinstance(self.preemptible, bool):
            raise ValueError("preemptible must be a boolean")
        if not isinstance(self.waiting_on_human, bool):
            raise ValueError("waiting_on_human must be a boolean")
        if not isinstance(self.scheduled, bool):
            raise ValueError("scheduled must be a boolean")
        if not isinstance(self.deferred, bool):
            raise ValueError("deferred must be a boolean")
        object.__setattr__(
            self, "sla_seconds",
            require_non_negative_int(self.sla_seconds, "sla_seconds"),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ScheduleWindow(ContractRecord):
    """A time window during which work may be scheduled."""

    window_id: str = ""
    resource_ref: str = ""
    resource_class: ResourceClass = ResourceClass.HUMAN
    starts_at: str = ""
    ends_at: str = ""
    capacity_units: int = 1
    reserved_units: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_id",
            require_non_empty_text(self.window_id, "window_id"),
        )
        object.__setattr__(
            self, "resource_ref",
            require_non_empty_text(self.resource_ref, "resource_ref"),
        )
        if not isinstance(self.resource_class, ResourceClass):
            raise ValueError("resource_class must be a ResourceClass")
        require_datetime_text(self.starts_at, "starts_at")
        require_datetime_text(self.ends_at, "ends_at")
        object.__setattr__(
            self, "capacity_units",
            require_non_negative_int(self.capacity_units, "capacity_units"),
        )
        object.__setattr__(
            self, "reserved_units",
            require_non_negative_int(self.reserved_units, "reserved_units"),
        )


@dataclass(frozen=True, slots=True)
class ResourceReservation(ContractRecord):
    """A reservation of a specific resource for a campaign."""

    reservation_id: str = ""
    portfolio_id: str = ""
    campaign_id: str = ""
    resource_ref: str = ""
    resource_class: ResourceClass = ResourceClass.HUMAN
    reservation_type: ReservationType = ReservationType.WORKER
    units_reserved: int = 1
    active: bool = True
    created_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reservation_id",
            require_non_empty_text(self.reservation_id, "reservation_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "resource_ref",
            require_non_empty_text(self.resource_ref, "resource_ref"),
        )
        if not isinstance(self.resource_class, ResourceClass):
            raise ValueError("resource_class must be a ResourceClass")
        if not isinstance(self.reservation_type, ReservationType):
            raise ValueError("reservation_type must be a ReservationType")
        object.__setattr__(
            self, "units_reserved",
            require_non_negative_int(self.units_reserved, "units_reserved"),
        )
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class QuotaReservation(ContractRecord):
    """A reservation of connector/channel quota for a campaign."""

    reservation_id: str = ""
    portfolio_id: str = ""
    campaign_id: str = ""
    connector_id: str = ""
    quota_units: int = 0
    quota_remaining: int = 0
    active: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reservation_id",
            require_non_empty_text(self.reservation_id, "reservation_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(
            self, "connector_id",
            require_non_empty_text(self.connector_id, "connector_id"),
        )
        object.__setattr__(
            self, "quota_units",
            require_non_negative_int(self.quota_units, "quota_units"),
        )
        object.__setattr__(
            self, "quota_remaining",
            require_non_negative_int(self.quota_remaining, "quota_remaining"),
        )
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class SchedulingDecision(ContractRecord):
    """Immutable record of a scheduling decision."""

    decision_id: str = ""
    portfolio_id: str = ""
    campaign_id: str = ""
    verdict: SchedulingVerdict = SchedulingVerdict.SCHEDULED
    priority_score: float = 0.0
    reason: str = ""
    preempted_campaign_id: str = ""
    resource_reservations: tuple[str, ...] = ()
    quota_reservations: tuple[str, ...] = ()
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id",
            require_non_empty_text(self.decision_id, "decision_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "campaign_id",
            require_non_empty_text(self.campaign_id, "campaign_id"),
        )
        if not isinstance(self.verdict, SchedulingVerdict):
            raise ValueError("verdict must be a SchedulingVerdict")
        object.__setattr__(
            self, "resource_reservations",
            freeze_value(list(self.resource_reservations)),
        )
        object.__setattr__(
            self, "quota_reservations",
            freeze_value(list(self.quota_reservations)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class PreemptionRecord(ContractRecord):
    """Record of one campaign preempting another."""

    preemption_id: str = ""
    portfolio_id: str = ""
    preempting_campaign_id: str = ""
    preempted_campaign_id: str = ""
    reason: str = ""
    priority_delta: float = 0.0
    preempted_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "preemption_id",
            require_non_empty_text(self.preemption_id, "preemption_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        object.__setattr__(
            self, "preempting_campaign_id",
            require_non_empty_text(self.preempting_campaign_id, "preempting_campaign_id"),
        )
        object.__setattr__(
            self, "preempted_campaign_id",
            require_non_empty_text(self.preempted_campaign_id, "preempted_campaign_id"),
        )
        require_datetime_text(self.preempted_at, "preempted_at")


@dataclass(frozen=True, slots=True)
class CapacitySnapshot(ContractRecord):
    """Point-in-time snapshot of resource capacity."""

    snapshot_id: str = ""
    portfolio_id: str = ""
    total_workers: int = 0
    available_workers: int = 0
    total_teams: int = 0
    available_teams: int = 0
    total_connectors: int = 0
    healthy_connectors: int = 0
    total_quota_units: int = 0
    available_quota_units: int = 0
    active_campaigns: int = 0
    deferred_campaigns: int = 0
    blocked_campaigns: int = 0
    captured_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot_id",
            require_non_empty_text(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        for fld in (
            "total_workers", "available_workers", "total_teams",
            "available_teams", "total_connectors", "healthy_connectors",
            "total_quota_units", "available_quota_units",
            "active_campaigns", "deferred_campaigns", "blocked_campaigns",
        ):
            object.__setattr__(
                self, fld,
                require_non_negative_int(getattr(self, fld), fld),
            )
        require_datetime_text(self.captured_at, "captured_at")


@dataclass(frozen=True, slots=True)
class PortfolioHealth(ContractRecord):
    """Health summary for a portfolio."""

    portfolio_id: str = ""
    status: PortfolioStatus = PortfolioStatus.ACTIVE
    total_campaigns: int = 0
    active_campaigns: int = 0
    deferred_campaigns: int = 0
    blocked_campaigns: int = 0
    overdue_campaigns: int = 0
    preempted_campaigns: int = 0
    completed_campaigns: int = 0
    utilization: float = 0.0
    computed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        if not isinstance(self.status, PortfolioStatus):
            raise ValueError("status must be a PortfolioStatus")
        for fld in (
            "total_campaigns", "active_campaigns", "deferred_campaigns",
            "blocked_campaigns", "overdue_campaigns", "preempted_campaigns",
            "completed_campaigns",
        ):
            object.__setattr__(
                self, fld,
                require_non_negative_int(getattr(self, fld), fld),
            )
        object.__setattr__(
            self, "utilization",
            require_unit_float(self.utilization, "utilization"),
        )
        require_datetime_text(self.computed_at, "computed_at")


@dataclass(frozen=True, slots=True)
class PortfolioClosureReport(ContractRecord):
    """Immutable closure report for a portfolio."""

    report_id: str = ""
    portfolio_id: str = ""
    total_campaigns: int = 0
    completed_campaigns: int = 0
    failed_campaigns: int = 0
    deferred_campaigns: int = 0
    preempted_campaigns: int = 0
    total_scheduling_decisions: int = 0
    total_preemptions: int = 0
    total_resource_reservations: int = 0
    total_quota_reservations: int = 0
    summary: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "report_id",
            require_non_empty_text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self, "portfolio_id",
            require_non_empty_text(self.portfolio_id, "portfolio_id"),
        )
        for fld in (
            "total_campaigns", "completed_campaigns", "failed_campaigns",
            "deferred_campaigns", "preempted_campaigns",
            "total_scheduling_decisions", "total_preemptions",
            "total_resource_reservations", "total_quota_reservations",
        ):
            object.__setattr__(
                self, fld,
                require_non_negative_int(getattr(self, fld), fld),
            )
        require_datetime_text(self.created_at, "created_at")
