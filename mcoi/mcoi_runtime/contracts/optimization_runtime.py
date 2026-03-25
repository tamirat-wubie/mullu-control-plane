"""Purpose: optimization / recommendation runtime contracts.
Governance scope: typed descriptors for optimization requests, constraints,
    candidates, recommendations, plans, results, impact estimates, and
    recommendation decisions.
Dependencies: _base contract utilities.
Invariants:
  - Every optimization has explicit target and strategy.
  - Recommendations are immutable and scored.
  - Constraints are respected in all candidate generation.
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


class OptimizationTarget(Enum):
    """What is being optimized."""
    CAMPAIGN_COST = "campaign_cost"
    CAMPAIGN_DURATION = "campaign_duration"
    CONNECTOR_SELECTION = "connector_selection"
    PORTFOLIO_BALANCE = "portfolio_balance"
    BUDGET_ALLOCATION = "budget_allocation"
    SCHEDULE_EFFICIENCY = "schedule_efficiency"
    ESCALATION_POLICY = "escalation_policy"
    DOMAIN_PACK_SELECTION = "domain_pack_selection"
    CHANNEL_ROUTING = "channel_routing"
    FAULT_AVOIDANCE = "fault_avoidance"


class OptimizationStrategy(Enum):
    """Strategy used to generate recommendations."""
    COST_MINIMIZATION = "cost_minimization"
    THROUGHPUT_MAXIMIZATION = "throughput_maximization"
    LATENCY_MINIMIZATION = "latency_minimization"
    RELIABILITY_MAXIMIZATION = "reliability_maximization"
    BALANCED = "balanced"
    CONSTRAINT_SATISFACTION = "constraint_satisfaction"


class RecommendationSeverity(Enum):
    """Urgency of a recommendation."""
    INFORMATIONAL = "informational"
    ADVISORY = "advisory"
    RECOMMENDED = "recommended"
    URGENT = "urgent"
    CRITICAL = "critical"


class RecommendationDisposition(Enum):
    """Outcome of a recommendation decision."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    PARTIALLY_ACCEPTED = "partially_accepted"
    SUPERSEDED = "superseded"


class OptimizationScope(Enum):
    """Scope at which optimization applies."""
    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    CAMPAIGN = "campaign"
    CONNECTOR = "connector"
    TEAM = "team"
    FUNCTION = "function"
    CHANNEL = "channel"
    DOMAIN_PACK = "domain_pack"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OptimizationRequest(ContractRecord):
    """A request to optimize a target."""

    request_id: str = ""
    target: OptimizationTarget = OptimizationTarget.CAMPAIGN_COST
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    scope: OptimizationScope = OptimizationScope.GLOBAL
    scope_ref_id: str = ""
    priority: str = "normal"
    max_candidates: int = 10
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        if not isinstance(self.target, OptimizationTarget):
            raise ValueError("target must be an OptimizationTarget")
        if not isinstance(self.strategy, OptimizationStrategy):
            raise ValueError("strategy must be an OptimizationStrategy")
        if not isinstance(self.scope, OptimizationScope):
            raise ValueError("scope must be an OptimizationScope")
        object.__setattr__(self, "max_candidates", require_non_negative_int(self.max_candidates, "max_candidates"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationConstraint(ContractRecord):
    """A constraint that must be respected during optimization."""

    constraint_id: str = ""
    request_id: str = ""
    constraint_type: str = ""
    field_name: str = ""
    operator: str = ""
    value: str = ""
    hard: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "constraint_type", require_non_empty_text(self.constraint_type, "constraint_type"))
        if not isinstance(self.hard, bool):
            raise ValueError("hard must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class OptimizationCandidate(ContractRecord):
    """A candidate change generated during optimization."""

    candidate_id: str = ""
    request_id: str = ""
    description: str = ""
    target: OptimizationTarget = OptimizationTarget.CAMPAIGN_COST
    action: str = ""
    scope_ref_id: str = ""
    score: float = 0.0
    feasible: bool = True
    estimated_improvement: float = 0.0
    estimated_cost_delta: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.target, OptimizationTarget):
            raise ValueError("target must be an OptimizationTarget")
        object.__setattr__(self, "score", require_unit_float(self.score, "score"))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationRecommendation(ContractRecord):
    """A scored recommendation from optimization."""

    recommendation_id: str = ""
    request_id: str = ""
    candidate_id: str = ""
    title: str = ""
    description: str = ""
    target: OptimizationTarget = OptimizationTarget.CAMPAIGN_COST
    severity: RecommendationSeverity = RecommendationSeverity.ADVISORY
    score: float = 0.0
    confidence: float = 1.0
    action: str = ""
    scope: OptimizationScope = OptimizationScope.GLOBAL
    scope_ref_id: str = ""
    estimated_improvement_pct: float = 0.0
    estimated_cost_delta: float = 0.0
    rationale: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.target, OptimizationTarget):
            raise ValueError("target must be an OptimizationTarget")
        if not isinstance(self.severity, RecommendationSeverity):
            raise ValueError("severity must be a RecommendationSeverity")
        if not isinstance(self.scope, OptimizationScope):
            raise ValueError("scope must be an OptimizationScope")
        object.__setattr__(self, "score", require_unit_float(self.score, "score"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationPlan(ContractRecord):
    """An ordered set of recommendations forming an action plan."""

    plan_id: str = ""
    request_id: str = ""
    title: str = ""
    recommendation_ids: tuple[str, ...] = ()
    total_estimated_improvement_pct: float = 0.0
    total_estimated_cost_delta: float = 0.0
    feasible: bool = True
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "recommendation_ids", freeze_value(list(self.recommendation_ids)))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationResult(ContractRecord):
    """Final result of an optimization run."""

    result_id: str = ""
    request_id: str = ""
    plan_id: str = ""
    candidates_generated: int = 0
    recommendations_produced: int = 0
    constraints_satisfied: int = 0
    constraints_violated: int = 0
    best_score: float = 0.0
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "candidates_generated", require_non_negative_int(self.candidates_generated, "candidates_generated"))
        object.__setattr__(self, "recommendations_produced", require_non_negative_int(self.recommendations_produced, "recommendations_produced"))
        object.__setattr__(self, "constraints_satisfied", require_non_negative_int(self.constraints_satisfied, "constraints_satisfied"))
        object.__setattr__(self, "constraints_violated", require_non_negative_int(self.constraints_violated, "constraints_violated"))
        object.__setattr__(self, "best_score", require_unit_float(self.best_score, "best_score"))
        require_datetime_text(self.completed_at, "completed_at")


@dataclass(frozen=True, slots=True)
class OptimizationImpactEstimate(ContractRecord):
    """Estimated impact of applying a recommendation."""

    estimate_id: str = ""
    recommendation_id: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    projected_value: float = 0.0
    improvement_pct: float = 0.0
    confidence: float = 1.0
    risk_level: str = "low"
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimate_id", require_non_empty_text(self.estimate_id, "estimate_id"))
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RecommendationDecision(ContractRecord):
    """Decision about whether to act on a recommendation."""

    decision_id: str = ""
    recommendation_id: str = ""
    disposition: RecommendationDisposition = RecommendationDisposition.PENDING
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        if not isinstance(self.disposition, RecommendationDisposition):
            raise ValueError("disposition must be a RecommendationDisposition")
        require_datetime_text(self.decided_at, "decided_at")
