"""Purpose: canonical operator dashboard contracts for point-in-time visibility.
Governance scope: decision summaries, provider routing summaries, learning
insights, and dashboard snapshots for operator consumption.
Dependencies: shared contract base helpers.
Invariants:
  - Snapshots are read-only point-in-time aggregations.
  - No state mutation from snapshot generation.
  - All scores bounded and finite.
  - All ID fields are non-empty strings.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_finite_float,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# --- Helpers ---

_VALID_DIRECTIONS = ("improving", "declining", "stable")


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class DecisionSummary(ContractRecord):
    """Summary of a single decision outcome for dashboard display."""

    decision_id: str
    comparison_id: str
    chosen_option_id: str
    quality: str
    actual_cost: float
    estimated_cost: float
    weight_changes: tuple[str, ...]
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(
            self, "chosen_option_id", require_non_empty_text(self.chosen_option_id, "chosen_option_id"),
        )
        object.__setattr__(self, "quality", require_non_empty_text(self.quality, "quality"))
        object.__setattr__(self, "actual_cost", require_non_negative_float(self.actual_cost, "actual_cost"))
        object.__setattr__(
            self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "weight_changes", freeze_value(list(self.weight_changes)))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class ProviderRoutingSummary(ContractRecord):
    """Aggregate routing statistics for a single provider and context type."""

    provider_id: str
    context_type: str
    preference_score: float
    health_score: float
    routing_count: int
    success_count: int
    failure_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(
            self, "preference_score", require_unit_float(self.preference_score, "preference_score"),
        )
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        object.__setattr__(self, "routing_count", require_non_negative_int(self.routing_count, "routing_count"))
        object.__setattr__(self, "success_count", require_non_negative_int(self.success_count, "success_count"))
        object.__setattr__(self, "failure_count", require_non_negative_int(self.failure_count, "failure_count"))
        if self.success_count + self.failure_count > self.routing_count:
            raise ValueError("success_count + failure_count must not exceed routing_count")

    @property
    def success_rate(self) -> float:
        return self.success_count / self.routing_count if self.routing_count > 0 else 0.0


@dataclass(frozen=True, slots=True)
class LearningInsight(ContractRecord):
    """A single learning-system insight for operator review."""

    insight_id: str
    factor_kind: str
    cumulative_delta: float
    direction: str
    sample_count: int
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "insight_id", require_non_empty_text(self.insight_id, "insight_id"))
        object.__setattr__(self, "factor_kind", require_non_empty_text(self.factor_kind, "factor_kind"))
        object.__setattr__(
            self, "cumulative_delta", require_finite_float(self.cumulative_delta, "cumulative_delta"),
        )
        object.__setattr__(self, "direction", require_non_empty_text(self.direction, "direction"))
        if self.direction not in _VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {_VALID_DIRECTIONS}, got {self.direction!r}")
        object.__setattr__(self, "sample_count", require_non_negative_int(self.sample_count, "sample_count"))
        object.__setattr__(self, "explanation", require_non_empty_text(self.explanation, "explanation"))


@dataclass(frozen=True, slots=True)
class ReliabilityPillarSummary(ContractRecord):
    """Single reliability pillar summary for dashboard display."""

    pillar: str
    confidence: float
    recommendation: str
    dominant_risk: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "pillar", require_non_empty_text(self.pillar, "pillar"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "recommendation", require_non_empty_text(self.recommendation, "recommendation"))
        object.__setattr__(self, "dominant_risk", require_non_empty_text(self.dominant_risk, "dominant_risk"))


@dataclass(frozen=True, slots=True)
class MetaReasoningSummary(ContractRecord):
    """Meta-reasoning summary for operator dashboard display.

    Provides a condensed view of overall system self-assessment:
    confidence envelope, dominant uncertainty, degraded/replan/escalation counts,
    and per-pillar reliability breakdowns.
    """

    summary_id: str
    overall_confidence: float
    confidence_display: str
    dominant_uncertainty: str
    degraded_count: int
    replan_count: int
    escalation_count: int
    recommendation: str
    pillars: tuple[ReliabilityPillarSummary, ...]
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_id", require_non_empty_text(self.summary_id, "summary_id"))
        object.__setattr__(
            self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"),
        )
        object.__setattr__(
            self, "confidence_display", require_non_empty_text(self.confidence_display, "confidence_display"),
        )
        object.__setattr__(
            self, "dominant_uncertainty",
            require_non_empty_text(self.dominant_uncertainty, "dominant_uncertainty"),
        )
        object.__setattr__(self, "degraded_count", require_non_negative_int(self.degraded_count, "degraded_count"))
        object.__setattr__(self, "replan_count", require_non_negative_int(self.replan_count, "replan_count"))
        object.__setattr__(
            self, "escalation_count", require_non_negative_int(self.escalation_count, "escalation_count"),
        )
        object.__setattr__(self, "recommendation", require_non_empty_text(self.recommendation, "recommendation"))
        object.__setattr__(self, "pillars", freeze_value(list(self.pillars)))
        for item in self.pillars:
            if not isinstance(item, ReliabilityPillarSummary):
                raise ValueError("each pillar must be a ReliabilityPillarSummary instance")
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class WorldStateSummary(ContractRecord):
    """World-state summary for operator dashboard display.

    Provides a condensed view of entity graph health: entity/relation counts,
    unresolved contradictions, conflict sets, expected-state violations,
    derived fact count, and overall world-state confidence.
    """

    summary_id: str
    entity_count: int
    relation_count: int
    derived_fact_count: int
    unresolved_contradiction_count: int
    conflict_set_count: int
    expected_state_count: int
    violation_count: int
    overall_confidence: float
    confidence_display: str
    recommendation: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary_id", require_non_empty_text(self.summary_id, "summary_id"))
        object.__setattr__(self, "entity_count", require_non_negative_int(self.entity_count, "entity_count"))
        object.__setattr__(self, "relation_count", require_non_negative_int(self.relation_count, "relation_count"))
        object.__setattr__(
            self, "derived_fact_count",
            require_non_negative_int(self.derived_fact_count, "derived_fact_count"),
        )
        object.__setattr__(
            self, "unresolved_contradiction_count",
            require_non_negative_int(self.unresolved_contradiction_count, "unresolved_contradiction_count"),
        )
        object.__setattr__(
            self, "conflict_set_count",
            require_non_negative_int(self.conflict_set_count, "conflict_set_count"),
        )
        object.__setattr__(
            self, "expected_state_count",
            require_non_negative_int(self.expected_state_count, "expected_state_count"),
        )
        object.__setattr__(
            self, "violation_count",
            require_non_negative_int(self.violation_count, "violation_count"),
        )
        object.__setattr__(
            self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"),
        )
        object.__setattr__(
            self, "confidence_display", require_non_empty_text(self.confidence_display, "confidence_display"),
        )
        object.__setattr__(self, "recommendation", require_non_empty_text(self.recommendation, "recommendation"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class DashboardSnapshot(ContractRecord):
    """Full dashboard snapshot for operator visibility."""

    snapshot_id: str
    captured_at: str
    total_decisions: int
    total_routing_decisions: int
    recent_decisions: tuple[DecisionSummary, ...]
    provider_summaries: tuple[ProviderRoutingSummary, ...]
    learning_insights: tuple[LearningInsight, ...]
    meta_reasoning: MetaReasoningSummary | None = None
    world_state: WorldStateSummary | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
        object.__setattr__(
            self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"),
        )
        object.__setattr__(
            self,
            "total_routing_decisions",
            require_non_negative_int(self.total_routing_decisions, "total_routing_decisions"),
        )
        object.__setattr__(self, "recent_decisions", freeze_value(list(self.recent_decisions)))
        if not all(isinstance(d, DecisionSummary) for d in self.recent_decisions):
            raise ValueError("all recent_decisions must be DecisionSummary instances")
        object.__setattr__(self, "provider_summaries", freeze_value(list(self.provider_summaries)))
        if not all(isinstance(s, ProviderRoutingSummary) for s in self.provider_summaries):
            raise ValueError("all provider_summaries must be ProviderRoutingSummary instances")
        object.__setattr__(self, "learning_insights", freeze_value(list(self.learning_insights)))
        if not all(isinstance(i, LearningInsight) for i in self.learning_insights):
            raise ValueError("all learning_insights must be LearningInsight instances")
        if self.meta_reasoning is not None and not isinstance(self.meta_reasoning, MetaReasoningSummary):
            raise ValueError("meta_reasoning must be a MetaReasoningSummary instance or None")
        if self.world_state is not None and not isinstance(self.world_state, WorldStateSummary):
            raise ValueError("world_state must be a WorldStateSummary instance or None")
