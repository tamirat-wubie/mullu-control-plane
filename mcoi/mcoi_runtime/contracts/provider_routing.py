"""Purpose: canonical provider cost routing contracts.
Governance scope: routing constraints, candidate scoring, routing decisions,
and outcome tracking for provider selection.
Dependencies: shared contract base helpers.
Invariants:
  - Routing decisions are immutable and auditable.
  - Selected provider must appear in the candidate list.
  - All float scores are finite and bounded within [0.0, 1.0]. Cost fields are finite and non-negative.
  - All ID fields are non-empty strings.
  - Datetime fields are valid ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ._base import (
    ContractRecord,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_float,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# --- Classification enums ---


class RoutingStrategy(StrEnum):
    """Strategy used to rank provider candidates."""

    CHEAPEST = "cheapest"
    MOST_RELIABLE = "most_reliable"
    BALANCED = "balanced"
    LEARNED = "learned"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class RoutingConstraints(ContractRecord):
    """Constraints that govern how providers are selected."""

    constraints_id: str
    max_cost_per_invocation: float
    min_provider_health_score: float
    min_preference_score: float
    min_sample_count: int
    strategy: RoutingStrategy

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints_id", require_non_empty_text(self.constraints_id, "constraints_id"))
        object.__setattr__(
            self,
            "max_cost_per_invocation",
            require_non_negative_float(self.max_cost_per_invocation, "max_cost_per_invocation"),
        )
        object.__setattr__(
            self,
            "min_provider_health_score",
            require_unit_float(self.min_provider_health_score, "min_provider_health_score"),
        )
        object.__setattr__(
            self,
            "min_preference_score",
            require_unit_float(self.min_preference_score, "min_preference_score"),
        )
        object.__setattr__(
            self, "min_sample_count", require_non_negative_int(self.min_sample_count, "min_sample_count"),
        )
        if not isinstance(self.strategy, RoutingStrategy):
            raise ValueError("strategy must be a RoutingStrategy value")


@dataclass(frozen=True, slots=True)
class ProviderCandidate(ContractRecord):
    """A scored provider candidate for routing."""

    candidate_id: str
    provider_id: str
    context_type: str
    estimated_cost: float
    health_score: float
    preference_score: float
    composite_score: float
    rank: int
    scored_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", require_non_empty_text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(
            self, "estimated_cost", require_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "health_score", require_unit_float(self.health_score, "health_score"))
        object.__setattr__(
            self, "preference_score", require_unit_float(self.preference_score, "preference_score"),
        )
        object.__setattr__(
            self, "composite_score", require_unit_float(self.composite_score, "composite_score"),
        )
        object.__setattr__(self, "rank", require_positive_int(self.rank, "rank"))
        object.__setattr__(self, "scored_at", require_datetime_text(self.scored_at, "scored_at"))


@dataclass(frozen=True, slots=True)
class RoutingDecision(ContractRecord):
    """Immutable record of a provider routing decision."""

    decision_id: str
    constraints_id: str
    candidates: tuple[ProviderCandidate, ...]
    selected_provider_id: str
    selected_cost: float
    rationale: str
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "constraints_id", require_non_empty_text(self.constraints_id, "constraints_id"))
        object.__setattr__(self, "candidates", require_non_empty_tuple(self.candidates, "candidates"))
        if not all(isinstance(c, ProviderCandidate) for c in self.candidates):
            raise ValueError("all candidates must be ProviderCandidate instances")
        object.__setattr__(
            self, "selected_provider_id", require_non_empty_text(self.selected_provider_id, "selected_provider_id"),
        )
        # Cross-validation: selected provider must appear in candidates
        candidate_provider_ids = {c.provider_id for c in self.candidates}
        if self.selected_provider_id not in candidate_provider_ids:
            raise ValueError("selected_provider_id must match a provider_id in candidates")
        object.__setattr__(
            self, "selected_cost", require_non_negative_float(self.selected_cost, "selected_cost"),
        )
        object.__setattr__(self, "rationale", require_non_empty_text(self.rationale, "rationale"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class RoutingOutcome(ContractRecord):
    """Immutable record of the actual outcome of a routed provider invocation."""

    outcome_id: str
    decision_id: str
    provider_id: str
    actual_cost: float
    success: bool
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        object.__setattr__(self, "actual_cost", require_non_negative_float(self.actual_cost, "actual_cost"))
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))
