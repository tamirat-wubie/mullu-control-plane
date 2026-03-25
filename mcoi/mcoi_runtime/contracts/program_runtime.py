"""Purpose: program / initiative / OKR runtime contracts.
Governance scope: typed descriptors for objectives, initiatives, programs,
    milestones, bindings, dependencies, attainment snapshots, program health,
    decisions, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every objective has explicit attainment targets.
  - Initiatives decompose objectives into actionable streams.
  - Programs group initiatives with shared lifecycle.
  - Milestones track concrete progress gates.
  - Dependencies enforce ordering constraints.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProgramStatus(Enum):
    """Lifecycle status of a program."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class InitiativeStatus(Enum):
    """Lifecycle status of an initiative."""
    DRAFT = "draft"
    ACTIVE = "active"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MilestoneStatus(Enum):
    """Status of a milestone."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"
    DEFERRED = "deferred"


class ObjectiveType(Enum):
    """Type of objective in the OKR hierarchy."""
    STRATEGIC = "strategic"
    TACTICAL = "tactical"
    OPERATIONAL = "operational"
    KEY_RESULT = "key_result"


class AttainmentLevel(Enum):
    """Attainment level for an objective."""
    EXCEEDED = "exceeded"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BEHIND = "behind"
    FAILED = "failed"
    NOT_STARTED = "not_started"


class DependencyKind(Enum):
    """Kind of dependency between initiatives."""
    BLOCKS = "blocks"
    REQUIRES = "requires"
    ENHANCES = "enhances"
    CONFLICTS = "conflicts"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObjectiveRecord(ContractRecord):
    """An objective in the OKR hierarchy."""

    objective_id: str = ""
    title: str = ""
    description: str = ""
    objective_type: ObjectiveType = ObjectiveType.STRATEGIC
    parent_objective_id: str = ""
    target_value: float = 0.0
    current_value: float = 0.0
    unit: str = ""
    attainment: AttainmentLevel = AttainmentLevel.NOT_STARTED
    weight: float = 1.0
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective_id", require_non_empty_text(self.objective_id, "objective_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.objective_type, ObjectiveType):
            raise ValueError("objective_type must be an ObjectiveType")
        if not isinstance(self.attainment, AttainmentLevel):
            raise ValueError("attainment must be an AttainmentLevel")
        object.__setattr__(self, "weight", require_non_negative_float(self.weight, "weight"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InitiativeRecord(ContractRecord):
    """An initiative that decomposes an objective into actionable work."""

    initiative_id: str = ""
    program_id: str = ""
    objective_id: str = ""
    title: str = ""
    description: str = ""
    status: InitiativeStatus = InitiativeStatus.DRAFT
    priority: int = 0
    progress_pct: float = 0.0
    campaign_ids: tuple[str, ...] = ()
    portfolio_ids: tuple[str, ...] = ()
    milestone_ids: tuple[str, ...] = ()
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "initiative_id", require_non_empty_text(self.initiative_id, "initiative_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, InitiativeStatus):
            raise ValueError("status must be an InitiativeStatus")
        object.__setattr__(self, "progress_pct", require_non_negative_float(self.progress_pct, "progress_pct"))
        object.__setattr__(self, "campaign_ids", freeze_value(list(self.campaign_ids)))
        object.__setattr__(self, "portfolio_ids", freeze_value(list(self.portfolio_ids)))
        object.__setattr__(self, "milestone_ids", freeze_value(list(self.milestone_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProgramRecord(ContractRecord):
    """A program grouping initiatives with a shared lifecycle."""

    program_id: str = ""
    title: str = ""
    description: str = ""
    status: ProgramStatus = ProgramStatus.DRAFT
    objective_ids: tuple[str, ...] = ()
    initiative_ids: tuple[str, ...] = ()
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_id", require_non_empty_text(self.program_id, "program_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, ProgramStatus):
            raise ValueError("status must be a ProgramStatus")
        object.__setattr__(self, "objective_ids", freeze_value(list(self.objective_ids)))
        object.__setattr__(self, "initiative_ids", freeze_value(list(self.initiative_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MilestoneRecord(ContractRecord):
    """A concrete progress gate within an initiative."""

    milestone_id: str = ""
    initiative_id: str = ""
    title: str = ""
    description: str = ""
    status: MilestoneStatus = MilestoneStatus.PENDING
    target_date: str = ""
    completed_date: str = ""
    progress_pct: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "milestone_id", require_non_empty_text(self.milestone_id, "milestone_id"))
        object.__setattr__(self, "initiative_id", require_non_empty_text(self.initiative_id, "initiative_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, MilestoneStatus):
            raise ValueError("status must be a MilestoneStatus")
        object.__setattr__(self, "progress_pct", require_non_negative_float(self.progress_pct, "progress_pct"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ObjectiveBinding(ContractRecord):
    """Binds a campaign or portfolio to an objective/initiative."""

    binding_id: str = ""
    objective_id: str = ""
    initiative_id: str = ""
    campaign_ref_id: str = ""
    portfolio_ref_id: str = ""
    weight: float = 1.0
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "weight", require_non_negative_float(self.weight, "weight"))
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class InitiativeDependency(ContractRecord):
    """A dependency relationship between two initiatives."""

    dependency_id: str = ""
    from_initiative_id: str = ""
    to_initiative_id: str = ""
    kind: DependencyKind = DependencyKind.REQUIRES
    description: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependency_id", require_non_empty_text(self.dependency_id, "dependency_id"))
        object.__setattr__(self, "from_initiative_id", require_non_empty_text(self.from_initiative_id, "from_initiative_id"))
        object.__setattr__(self, "to_initiative_id", require_non_empty_text(self.to_initiative_id, "to_initiative_id"))
        if not isinstance(self.kind, DependencyKind):
            raise ValueError("kind must be a DependencyKind")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class AttainmentSnapshot(ContractRecord):
    """Point-in-time attainment snapshot for an objective."""

    snapshot_id: str = ""
    objective_id: str = ""
    attainment: AttainmentLevel = AttainmentLevel.NOT_STARTED
    target_value: float = 0.0
    current_value: float = 0.0
    progress_pct: float = 0.0
    initiative_count: int = 0
    completed_initiatives: int = 0
    blocked_initiatives: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "objective_id", require_non_empty_text(self.objective_id, "objective_id"))
        if not isinstance(self.attainment, AttainmentLevel):
            raise ValueError("attainment must be an AttainmentLevel")
        object.__setattr__(self, "progress_pct", require_non_negative_float(self.progress_pct, "progress_pct"))
        object.__setattr__(self, "initiative_count", require_non_negative_int(self.initiative_count, "initiative_count"))
        object.__setattr__(self, "completed_initiatives", require_non_negative_int(self.completed_initiatives, "completed_initiatives"))
        object.__setattr__(self, "blocked_initiatives", require_non_negative_int(self.blocked_initiatives, "blocked_initiatives"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProgramHealth(ContractRecord):
    """Health assessment of a program."""

    health_id: str = ""
    program_id: str = ""
    status: ProgramStatus = ProgramStatus.ACTIVE
    total_initiatives: int = 0
    active_initiatives: int = 0
    blocked_initiatives: int = 0
    completed_initiatives: int = 0
    total_milestones: int = 0
    achieved_milestones: int = 0
    missed_milestones: int = 0
    overall_progress_pct: float = 0.0
    assessed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "health_id", require_non_empty_text(self.health_id, "health_id"))
        object.__setattr__(self, "program_id", require_non_empty_text(self.program_id, "program_id"))
        if not isinstance(self.status, ProgramStatus):
            raise ValueError("status must be a ProgramStatus")
        object.__setattr__(self, "total_initiatives", require_non_negative_int(self.total_initiatives, "total_initiatives"))
        object.__setattr__(self, "active_initiatives", require_non_negative_int(self.active_initiatives, "active_initiatives"))
        object.__setattr__(self, "blocked_initiatives", require_non_negative_int(self.blocked_initiatives, "blocked_initiatives"))
        object.__setattr__(self, "completed_initiatives", require_non_negative_int(self.completed_initiatives, "completed_initiatives"))
        object.__setattr__(self, "total_milestones", require_non_negative_int(self.total_milestones, "total_milestones"))
        object.__setattr__(self, "achieved_milestones", require_non_negative_int(self.achieved_milestones, "achieved_milestones"))
        object.__setattr__(self, "missed_milestones", require_non_negative_int(self.missed_milestones, "missed_milestones"))
        object.__setattr__(self, "overall_progress_pct", require_non_negative_float(self.overall_progress_pct, "overall_progress_pct"))
        require_datetime_text(self.assessed_at, "assessed_at")


@dataclass(frozen=True, slots=True)
class ProgramDecision(ContractRecord):
    """A decision made about a program or initiative."""

    decision_id: str = ""
    program_id: str = ""
    initiative_id: str = ""
    title: str = ""
    rationale: str = ""
    action: str = ""
    confidence: float = 0.0
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProgramClosureReport(ContractRecord):
    """Final closure report for a program."""

    report_id: str = ""
    program_id: str = ""
    final_status: ProgramStatus = ProgramStatus.COMPLETED
    total_initiatives: int = 0
    completed_initiatives: int = 0
    failed_initiatives: int = 0
    total_milestones: int = 0
    achieved_milestones: int = 0
    missed_milestones: int = 0
    overall_attainment_pct: float = 0.0
    lessons: tuple[str, ...] = ()
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "program_id", require_non_empty_text(self.program_id, "program_id"))
        if not isinstance(self.final_status, ProgramStatus):
            raise ValueError("final_status must be a ProgramStatus")
        object.__setattr__(self, "total_initiatives", require_non_negative_int(self.total_initiatives, "total_initiatives"))
        object.__setattr__(self, "completed_initiatives", require_non_negative_int(self.completed_initiatives, "completed_initiatives"))
        object.__setattr__(self, "failed_initiatives", require_non_negative_int(self.failed_initiatives, "failed_initiatives"))
        object.__setattr__(self, "total_milestones", require_non_negative_int(self.total_milestones, "total_milestones"))
        object.__setattr__(self, "achieved_milestones", require_non_negative_int(self.achieved_milestones, "achieved_milestones"))
        object.__setattr__(self, "missed_milestones", require_non_negative_int(self.missed_milestones, "missed_milestones"))
        object.__setattr__(self, "overall_attainment_pct", require_non_negative_float(self.overall_attainment_pct, "overall_attainment_pct"))
        object.__setattr__(self, "lessons", freeze_value(list(self.lessons)))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
