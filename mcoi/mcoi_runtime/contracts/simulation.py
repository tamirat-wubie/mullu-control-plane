"""Purpose: simulation engine runtime contracts for consequence projection.
Governance scope: simulation request, option, consequence, risk, obligation,
outcome, comparison, and verdict typing.
Dependencies: docs/32_simulation_engine.md, shared contract base helpers.
Invariants:
  - Simulations are read-only projections; no side effects permitted.
  - Confidence and incident_probability are bounded [0.0, 1.0] and finite.
  - No simulation output may be treated as verified fact.
  - No auto-execution from simulation verdict alone.
  - All integer counts are non-negative.
  - All ID and description fields are non-empty strings.
  - Datetime fields are valid ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# --- Classification enums ---


class SimulationStatus(StrEnum):
    """Lifecycle status of a simulation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    """Classification of projected risk severity."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class VerdictType(StrEnum):
    """Classification of simulation verdict recommendation."""

    PROCEED = "proceed"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    APPROVAL_REQUIRED = "approval_required"
    ESCALATE = "escalate"
    ABORT = "abort"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class SimulationOption(ContractRecord):
    """One candidate action path to evaluate within a simulation."""

    option_id: str
    label: str
    risk_level: RiskLevel
    estimated_cost: float
    estimated_duration_seconds: float
    success_probability: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level must be a RiskLevel value")
        object.__setattr__(
            self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(
            self,
            "estimated_duration_seconds",
            require_non_negative_float(self.estimated_duration_seconds, "estimated_duration_seconds"),
        )
        object.__setattr__(
            self, "success_probability", require_unit_float(self.success_probability, "success_probability"),
        )


@dataclass(frozen=True, slots=True)
class SimulationRequest(ContractRecord):
    """A request to simulate consequences of a proposed action."""

    request_id: str
    context_type: str
    context_id: str
    description: str
    options: tuple[SimulationOption, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(self, "context_id", require_non_empty_text(self.context_id, "context_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "options", require_non_empty_tuple(self.options, "options"))


@dataclass(frozen=True, slots=True)
class ConsequenceEstimate(ContractRecord):
    """Projected graph deltas for a single simulation option."""

    estimate_id: str
    option_id: str
    affected_node_ids: tuple[str, ...]
    new_edges_count: int
    new_obligations_count: int
    blocked_nodes_count: int
    unblocked_nodes_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimate_id", require_non_empty_text(self.estimate_id, "estimate_id"))
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        if not isinstance(self.affected_node_ids, tuple):
            object.__setattr__(self, "affected_node_ids", tuple(self.affected_node_ids))
        for nid in self.affected_node_ids:
            require_non_empty_text(nid, "affected_node_ids element")
        object.__setattr__(
            self, "new_edges_count", require_non_negative_int(self.new_edges_count, "new_edges_count")
        )
        object.__setattr__(
            self,
            "new_obligations_count",
            require_non_negative_int(self.new_obligations_count, "new_obligations_count"),
        )
        object.__setattr__(
            self, "blocked_nodes_count", require_non_negative_int(self.blocked_nodes_count, "blocked_nodes_count")
        )
        object.__setattr__(
            self,
            "unblocked_nodes_count",
            require_non_negative_int(self.unblocked_nodes_count, "unblocked_nodes_count"),
        )


@dataclass(frozen=True, slots=True)
class RiskEstimate(ContractRecord):
    """Risk projection for a single simulation option."""

    estimate_id: str
    option_id: str
    risk_level: RiskLevel
    incident_probability: float
    review_burden: int
    provider_exposure_count: int
    verification_difficulty: str
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "estimate_id", require_non_empty_text(self.estimate_id, "estimate_id"))
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level must be a RiskLevel value")
        object.__setattr__(
            self,
            "incident_probability",
            require_unit_float(self.incident_probability, "incident_probability"),
        )
        object.__setattr__(
            self, "review_burden", require_non_negative_int(self.review_burden, "review_burden")
        )
        object.__setattr__(
            self,
            "provider_exposure_count",
            require_non_negative_int(self.provider_exposure_count, "provider_exposure_count"),
        )
        object.__setattr__(
            self,
            "verification_difficulty",
            require_non_empty_text(self.verification_difficulty, "verification_difficulty"),
        )
        object.__setattr__(self, "rationale", require_non_empty_text(self.rationale, "rationale"))


@dataclass(frozen=True, slots=True)
class ObligationProjection(ContractRecord):
    """Projected obligation changes for a single simulation option."""

    projection_id: str
    option_id: str
    new_obligations: tuple[str, ...]
    fulfilled_obligations: tuple[str, ...]
    deadline_pressure: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", require_non_empty_text(self.projection_id, "projection_id"))
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        if not isinstance(self.new_obligations, tuple):
            object.__setattr__(self, "new_obligations", tuple(self.new_obligations))
        if not isinstance(self.fulfilled_obligations, tuple):
            object.__setattr__(self, "fulfilled_obligations", tuple(self.fulfilled_obligations))
        for oid in self.new_obligations:
            require_non_empty_text(oid, "new_obligations element")
        for oid in self.fulfilled_obligations:
            require_non_empty_text(oid, "fulfilled_obligations element")
        object.__setattr__(
            self, "deadline_pressure", require_non_negative_int(self.deadline_pressure, "deadline_pressure")
        )


@dataclass(frozen=True, slots=True)
class SimulationOutcome(ContractRecord):
    """Composite simulation result for one option."""

    outcome_id: str
    option_id: str
    consequence: ConsequenceEstimate
    risk: RiskEstimate
    obligation_projection: ObligationProjection
    simulated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        if not isinstance(self.consequence, ConsequenceEstimate):
            raise ValueError("consequence must be a ConsequenceEstimate")
        if not isinstance(self.risk, RiskEstimate):
            raise ValueError("risk must be a RiskEstimate")
        if not isinstance(self.obligation_projection, ObligationProjection):
            raise ValueError("obligation_projection must be an ObligationProjection")
        object.__setattr__(self, "simulated_at", require_datetime_text(self.simulated_at, "simulated_at"))


@dataclass(frozen=True, slots=True)
class SimulationComparison(ContractRecord):
    """Side-by-side ranking of all evaluated simulation options."""

    comparison_id: str
    request_id: str
    ranked_option_ids: tuple[str, ...]
    scores: Mapping[str, float]
    top_risk_level: RiskLevel
    review_burden: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "ranked_option_ids", require_non_empty_tuple(self.ranked_option_ids, "ranked_option_ids"))
        object.__setattr__(self, "scores", freeze_value(self.scores))
        if not isinstance(self.top_risk_level, RiskLevel):
            raise ValueError("top_risk_level must be a RiskLevel value")
        object.__setattr__(self, "review_burden", require_unit_float(self.review_burden, "review_burden"))


@dataclass(frozen=True, slots=True)
class SimulationVerdict(ContractRecord):
    """Final recommendation from the simulation engine."""

    verdict_id: str
    comparison_id: str
    verdict_type: VerdictType
    recommended_option_id: str
    confidence: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict_id", require_non_empty_text(self.verdict_id, "verdict_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        if not isinstance(self.verdict_type, VerdictType):
            raise ValueError("verdict_type must be a VerdictType value")
        object.__setattr__(
            self,
            "recommended_option_id",
            require_non_empty_text(self.recommended_option_id, "recommended_option_id"),
        )
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
