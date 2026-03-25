"""Purpose: executive control tower / strategic planning contracts.
Governance scope: typed descriptors for strategic objectives, directives,
    priority shifts, scenario planning, executive interventions, strategic
    decisions, portfolio bindings, and control tower snapshots.
Dependencies: _base contract utilities.
Invariants:
  - Every objective has explicit priority and KPI thresholds.
  - Directives bind objectives to actionable scope.
  - Priority shifts are traceable and reversible.
  - Scenario plans capture before/after projections.
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


class ObjectiveStatus(Enum):
    """Lifecycle status of a strategic objective."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"


class DirectiveType(Enum):
    """Type of executive directive."""
    PRIORITY_SHIFT = "priority_shift"
    BUDGET_REALLOCATION = "budget_reallocation"
    CAPACITY_SHIFT = "capacity_shift"
    PAUSE_OPERATIONS = "pause_operations"
    RESUME_OPERATIONS = "resume_operations"
    OVERRIDE_OPTIMIZER = "override_optimizer"
    HALT_AUTONOMOUS = "halt_autonomous"
    LAUNCH_SCENARIO = "launch_scenario"
    ESCALATE = "escalate"


class DirectiveStatus(Enum):
    """Lifecycle status of a directive."""
    PENDING = "pending"
    ISSUED = "issued"
    ACKNOWLEDGED = "acknowledged"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InterventionSeverity(Enum):
    """Severity of an executive intervention."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioStatus(Enum):
    """Status of a scenario plan."""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PriorityLevel(Enum):
    """Priority level for strategic objectives."""
    P0_CRITICAL = "p0_critical"
    P1_HIGH = "p1_high"
    P2_MEDIUM = "p2_medium"
    P3_LOW = "p3_low"
    P4_OPPORTUNISTIC = "p4_opportunistic"


class ControlTowerHealth(Enum):
    """Health state of the control tower."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StrategicObjective(ContractRecord):
    """A top-level strategic objective governing platform behavior."""

    objective_id: str = ""
    title: str = ""
    description: str = ""
    priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    status: ObjectiveStatus = ObjectiveStatus.DRAFT
    target_kpi: str = ""
    target_value: float = 0.0
    current_value: float = 0.0
    tolerance_pct: float = 5.0
    owner: str = ""
    scope_ref_ids: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective_id", require_non_empty_text(self.objective_id, "objective_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.priority, PriorityLevel):
            raise ValueError("priority must be a PriorityLevel")
        if not isinstance(self.status, ObjectiveStatus):
            raise ValueError("status must be an ObjectiveStatus")
        object.__setattr__(self, "tolerance_pct", require_non_negative_float(self.tolerance_pct, "tolerance_pct"))
        object.__setattr__(self, "scope_ref_ids", freeze_value(list(self.scope_ref_ids)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StrategicDirective(ContractRecord):
    """An executive directive issued to change platform behavior."""

    directive_id: str = ""
    objective_id: str = ""
    directive_type: DirectiveType = DirectiveType.PRIORITY_SHIFT
    status: DirectiveStatus = DirectiveStatus.PENDING
    title: str = ""
    reason: str = ""
    target_scope_ref_id: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    issued_by: str = ""
    issued_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.directive_type, DirectiveType):
            raise ValueError("directive_type must be a DirectiveType")
        if not isinstance(self.status, DirectiveStatus):
            raise ValueError("status must be a DirectiveStatus")
        require_datetime_text(self.issued_at, "issued_at")
        object.__setattr__(self, "parameters", freeze_value(dict(self.parameters)))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PriorityShift(ContractRecord):
    """Record of a global priority rebalance."""

    shift_id: str = ""
    directive_id: str = ""
    from_priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    to_priority: PriorityLevel = PriorityLevel.P1_HIGH
    target_scope_ref_id: str = ""
    reason: str = ""
    shifted_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "shift_id", require_non_empty_text(self.shift_id, "shift_id"))
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        if not isinstance(self.from_priority, PriorityLevel):
            raise ValueError("from_priority must be a PriorityLevel")
        if not isinstance(self.to_priority, PriorityLevel):
            raise ValueError("to_priority must be a PriorityLevel")
        require_datetime_text(self.shifted_at, "shifted_at")


@dataclass(frozen=True, slots=True)
class ScenarioPlan(ContractRecord):
    """A scenario plan for simulating impact before major changes."""

    scenario_id: str = ""
    objective_id: str = ""
    title: str = ""
    status: ScenarioStatus = ScenarioStatus.DRAFT
    baseline_snapshot: Mapping[str, Any] = field(default_factory=dict)
    projected_snapshot: Mapping[str, Any] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    risk_score: float = 0.0
    confidence: float = 0.0
    created_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, ScenarioStatus):
            raise ValueError("status must be a ScenarioStatus")
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "baseline_snapshot", freeze_value(dict(self.baseline_snapshot)))
        object.__setattr__(self, "projected_snapshot", freeze_value(dict(self.projected_snapshot)))
        object.__setattr__(self, "assumptions", freeze_value(list(self.assumptions)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ScenarioOutcome(ContractRecord):
    """Assessment of a completed scenario plan."""

    outcome_id: str = ""
    scenario_id: str = ""
    verdict: str = ""
    projected_improvement_pct: float = 0.0
    projected_risk_delta: float = 0.0
    projected_cost_delta: float = 0.0
    recommendation: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "verdict", require_non_empty_text(self.verdict, "verdict"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutiveIntervention(ContractRecord):
    """Record of an executive override or intervention."""

    intervention_id: str = ""
    directive_id: str = ""
    severity: InterventionSeverity = InterventionSeverity.MEDIUM
    target_engine: str = ""
    target_ref_id: str = ""
    action: str = ""
    reason: str = ""
    intervened_at: str = ""
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "intervention_id", require_non_empty_text(self.intervention_id, "intervention_id"))
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        if not isinstance(self.severity, InterventionSeverity):
            raise ValueError("severity must be an InterventionSeverity")
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        require_datetime_text(self.intervened_at, "intervened_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StrategicDecision(ContractRecord):
    """Record of a strategic decision made by the control tower."""

    decision_id: str = ""
    objective_id: str = ""
    directive_ids: tuple[str, ...] = ()
    title: str = ""
    rationale: str = ""
    confidence: float = 0.0
    risk_score: float = 0.0
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        object.__setattr__(self, "directive_ids", freeze_value(list(self.directive_ids)))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PortfolioDirectiveBinding(ContractRecord):
    """Binds a directive to a specific portfolio/campaign/domain."""

    binding_id: str = ""
    directive_id: str = ""
    portfolio_ref_id: str = ""
    campaign_ref_id: str = ""
    domain_ref_id: str = ""
    effect: str = ""
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class ControlTowerSnapshot(ContractRecord):
    """Point-in-time snapshot of the executive control tower state."""

    snapshot_id: str = ""
    health: ControlTowerHealth = ControlTowerHealth.HEALTHY
    active_objectives: int = 0
    active_directives: int = 0
    pending_scenarios: int = 0
    interventions_in_progress: int = 0
    total_priority_shifts: int = 0
    total_decisions: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        if not isinstance(self.health, ControlTowerHealth):
            raise ValueError("health must be a ControlTowerHealth")
        object.__setattr__(self, "active_objectives", require_non_negative_int(self.active_objectives, "active_objectives"))
        object.__setattr__(self, "active_directives", require_non_negative_int(self.active_directives, "active_directives"))
        object.__setattr__(self, "pending_scenarios", require_non_negative_int(self.pending_scenarios, "pending_scenarios"))
        object.__setattr__(self, "interventions_in_progress", require_non_negative_int(self.interventions_in_progress, "interventions_in_progress"))
        object.__setattr__(self, "total_priority_shifts", require_non_negative_int(self.total_priority_shifts, "total_priority_shifts"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
