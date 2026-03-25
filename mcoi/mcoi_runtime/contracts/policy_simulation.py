"""Purpose: policy simulation / governance sandbox runtime contracts.
Governance scope: typed descriptors for simulation requests, scenarios,
    results, diffs, runtime impacts, adoption recommendations, snapshots,
    violations, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every simulation references a tenant.
  - Sandbox state never mutates live runtimes.
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


class SimulationStatus(Enum):
    """Status of a policy simulation."""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationMode(Enum):
    """Mode of simulation execution."""
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    FULL = "full"
    DIFF_ONLY = "diff_only"


class PolicyImpactLevel(Enum):
    """Level of policy impact."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiffDisposition(Enum):
    """Disposition of a policy diff."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class AdoptionReadiness(Enum):
    """Readiness level for policy adoption."""
    READY = "ready"
    CAUTION = "caution"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"


class SandboxScope(Enum):
    """Scope of the simulation sandbox."""
    TENANT = "tenant"
    RUNTIME = "runtime"
    GLOBAL = "global"
    CONSTITUTIONAL = "constitutional"
    SERVICE = "service"
    FINANCIAL = "financial"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicySimulationRequest(ContractRecord):
    """A request to run a policy simulation."""

    request_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    mode: SimulationMode = SimulationMode.DRY_RUN
    scope: SandboxScope = SandboxScope.TENANT
    status: SimulationStatus = SimulationStatus.DRAFT
    candidate_rule_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.mode, SimulationMode):
            raise ValueError("mode must be a SimulationMode")
        if not isinstance(self.scope, SandboxScope):
            raise ValueError("scope must be a SandboxScope")
        if not isinstance(self.status, SimulationStatus):
            raise ValueError("status must be a SimulationStatus")
        object.__setattr__(self, "candidate_rule_count", require_non_negative_int(self.candidate_rule_count, "candidate_rule_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicySimulationScenario(ContractRecord):
    """A scenario within a simulation."""

    scenario_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    target_runtime: str = ""
    baseline_outcome: str = ""
    simulated_outcome: str = ""
    impact_level: PolicyImpactLevel = PolicyImpactLevel.NONE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "baseline_outcome", require_non_empty_text(self.baseline_outcome, "baseline_outcome"))
        object.__setattr__(self, "simulated_outcome", require_non_empty_text(self.simulated_outcome, "simulated_outcome"))
        if not isinstance(self.impact_level, PolicyImpactLevel):
            raise ValueError("impact_level must be a PolicyImpactLevel")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicySimulationResult(ContractRecord):
    """The result of a completed simulation."""

    result_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    scenario_count: int = 0
    impacted_count: int = 0
    max_impact_level: PolicyImpactLevel = PolicyImpactLevel.NONE
    adoption_readiness: AdoptionReadiness = AdoptionReadiness.READY
    readiness_score: float = 0.0
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "scenario_count", require_non_negative_int(self.scenario_count, "scenario_count"))
        object.__setattr__(self, "impacted_count", require_non_negative_int(self.impacted_count, "impacted_count"))
        if not isinstance(self.max_impact_level, PolicyImpactLevel):
            raise ValueError("max_impact_level must be a PolicyImpactLevel")
        if not isinstance(self.adoption_readiness, AdoptionReadiness):
            raise ValueError("adoption_readiness must be an AdoptionReadiness")
        object.__setattr__(self, "readiness_score", require_unit_float(self.readiness_score, "readiness_score"))
        require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PolicyDiffRecord(ContractRecord):
    """A diff between baseline and simulated policy."""

    diff_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    rule_ref: str = ""
    disposition: DiffDisposition = DiffDisposition.UNCHANGED
    before_value: str = ""
    after_value: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diff_id", require_non_empty_text(self.diff_id, "diff_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "rule_ref", require_non_empty_text(self.rule_ref, "rule_ref"))
        if not isinstance(self.disposition, DiffDisposition):
            raise ValueError("disposition must be a DiffDisposition")
        object.__setattr__(self, "before_value", require_non_empty_text(self.before_value, "before_value"))
        object.__setattr__(self, "after_value", require_non_empty_text(self.after_value, "after_value"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RuntimeImpactRecord(ContractRecord):
    """Impact of a simulation on a specific runtime."""

    impact_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    target_runtime: str = ""
    impact_level: PolicyImpactLevel = PolicyImpactLevel.NONE
    affected_actions: int = 0
    blocked_actions: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "impact_id", require_non_empty_text(self.impact_id, "impact_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.impact_level, PolicyImpactLevel):
            raise ValueError("impact_level must be a PolicyImpactLevel")
        object.__setattr__(self, "affected_actions", require_non_negative_int(self.affected_actions, "affected_actions"))
        object.__setattr__(self, "blocked_actions", require_non_negative_int(self.blocked_actions, "blocked_actions"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdoptionRecommendation(ContractRecord):
    """A recommendation for or against policy adoption."""

    recommendation_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    readiness: AdoptionReadiness = AdoptionReadiness.READY
    readiness_score: float = 0.0
    reason: str = ""
    recommended_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.readiness, AdoptionReadiness):
            raise ValueError("readiness must be an AdoptionReadiness")
        object.__setattr__(self, "readiness_score", require_unit_float(self.readiness_score, "readiness_score"))
        require_datetime_text(self.recommended_at, "recommended_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SandboxSnapshot(ContractRecord):
    """Point-in-time snapshot of sandbox state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_simulations: int = 0
    completed_simulations: int = 0
    total_scenarios: int = 0
    total_diffs: int = 0
    total_impacts: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_simulations", require_non_negative_int(self.total_simulations, "total_simulations"))
        object.__setattr__(self, "completed_simulations", require_non_negative_int(self.completed_simulations, "completed_simulations"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_diffs", require_non_negative_int(self.total_diffs, "total_diffs"))
        object.__setattr__(self, "total_impacts", require_non_negative_int(self.total_impacts, "total_impacts"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SandboxViolation(ContractRecord):
    """A sandbox violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SandboxAssessment(ContractRecord):
    """An assessment of sandbox health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_simulations: int = 0
    completion_rate: float = 0.0
    avg_readiness_score: float = 0.0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_simulations", require_non_negative_int(self.total_simulations, "total_simulations"))
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        object.__setattr__(self, "avg_readiness_score", require_unit_float(self.avg_readiness_score, "avg_readiness_score"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SandboxClosureReport(ContractRecord):
    """Closure report for sandbox."""

    report_id: str = ""
    tenant_id: str = ""
    total_simulations: int = 0
    total_scenarios: int = 0
    total_diffs: int = 0
    total_impacts: int = 0
    total_recommendations: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_simulations", require_non_negative_int(self.total_simulations, "total_simulations"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_diffs", require_non_negative_int(self.total_diffs, "total_diffs"))
        object.__setattr__(self, "total_impacts", require_non_negative_int(self.total_impacts, "total_impacts"))
        object.__setattr__(self, "total_recommendations", require_non_negative_int(self.total_recommendations, "total_recommendations"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
