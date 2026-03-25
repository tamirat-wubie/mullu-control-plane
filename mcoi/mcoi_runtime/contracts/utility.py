"""Purpose: utility and resource reasoning contracts for decision evaluation.
Governance scope: resource budgets, decision factors, utility profiles,
option scoring, comparison, tradeoff recording, policies, and verdicts.
Dependencies: docs/28_utility_resource_reasoning.md, shared contract base helpers.
Invariants:
  - Resource consumption must never exceed budget (consumed + reserved <= total).
  - Decision factor weights and values are bounded [0.0, 1.0] and finite.
  - Utility scores are bounded [0.0, 1.0] and finite.
  - No auto-execution from utility verdict alone.
  - All ID and label fields are non-empty strings.
  - Datetime fields are valid ISO 8601 strings.
"""

from __future__ import annotations

import math
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
    require_positive_int,
    require_unit_float,
)


# --- Classification enums ---


class ResourceType(StrEnum):
    """Classification of resource kinds available to the runtime."""

    COMPUTE = "compute"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"
    API_CALLS = "api_calls"
    TIME = "time"
    BUDGET = "budget"


class DecisionFactorKind(StrEnum):
    """Classification of factors that influence a decision."""

    RISK = "risk"
    OBLIGATION = "obligation"
    CONFIDENCE = "confidence"
    PROVIDER_HEALTH = "provider_health"
    DEADLINE_PRESSURE = "deadline_pressure"
    COST = "cost"
    TIME = "time"
    CUSTOM = "custom"


class TradeoffDirection(StrEnum):
    """Classification of preferred tradeoff bias."""

    FAVOR_SPEED = "favor_speed"
    FAVOR_COST = "favor_cost"
    FAVOR_SAFETY = "favor_safety"
    BALANCED = "balanced"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class ResourceBudget(ContractRecord):
    """A finite resource budget with consumption tracking."""

    resource_id: str
    resource_type: ResourceType
    total: float
    consumed: float
    reserved: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", require_non_empty_text(self.resource_id, "resource_id"))
        if not isinstance(self.resource_type, ResourceType):
            raise ValueError("resource_type must be a ResourceType value")
        object.__setattr__(self, "total", require_non_negative_float(self.total, "total"))
        object.__setattr__(self, "consumed", require_non_negative_float(self.consumed, "consumed"))
        object.__setattr__(self, "reserved", require_non_negative_float(self.reserved, "reserved"))
        if self.consumed + self.reserved > self.total:
            raise ValueError("consumed + reserved must not exceed total")


@dataclass(frozen=True, slots=True)
class DecisionFactor(ContractRecord):
    """A single weighted factor contributing to a utility evaluation."""

    factor_id: str
    kind: DecisionFactorKind
    weight: float
    value: float
    label: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "factor_id", require_non_empty_text(self.factor_id, "factor_id"))
        if not isinstance(self.kind, DecisionFactorKind):
            raise ValueError("kind must be a DecisionFactorKind value")
        object.__setattr__(self, "weight", require_unit_float(self.weight, "weight"))
        object.__setattr__(self, "value", require_unit_float(self.value, "value"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))


@dataclass(frozen=True, slots=True)
class UtilityProfile(ContractRecord):
    """A collection of decision factors scoped to a context."""

    profile_id: str
    context_type: str
    context_id: str
    factors: tuple[DecisionFactor, ...]
    tradeoff_direction: TradeoffDirection
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(self, "context_id", require_non_empty_text(self.context_id, "context_id"))
        object.__setattr__(self, "factors", require_non_empty_tuple(self.factors, "factors"))
        if not isinstance(self.tradeoff_direction, TradeoffDirection):
            raise ValueError("tradeoff_direction must be a TradeoffDirection value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        total_weight = sum(f.weight for f in self.factors)
        if total_weight <= 0.0:
            raise ValueError("sum of factor weights must be greater than 0")


@dataclass(frozen=True, slots=True)
class OptionUtility(ContractRecord):
    """Scored utility for a single decision option."""

    option_id: str
    raw_score: float
    weighted_score: float
    factor_contributions: Mapping[str, float]
    rank: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        object.__setattr__(self, "raw_score", require_unit_float(self.raw_score, "raw_score"))
        object.__setattr__(self, "weighted_score", require_unit_float(self.weighted_score, "weighted_score"))
        frozen_contribs = freeze_value(self.factor_contributions)
        # Validate factor contribution values are finite
        for key, val in frozen_contribs.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                if not math.isfinite(float(val)):
                    raise ValueError(f"factor_contributions[{key!r}] must be finite")
        object.__setattr__(self, "factor_contributions", frozen_contribs)
        object.__setattr__(self, "rank", require_positive_int(self.rank, "rank"))


@dataclass(frozen=True, slots=True)
class DecisionComparison(ContractRecord):
    """Side-by-side ranking of scored option utilities."""

    comparison_id: str
    profile_id: str
    option_utilities: tuple[OptionUtility, ...]
    best_option_id: str
    spread: float
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        object.__setattr__(
            self, "option_utilities", require_non_empty_tuple(self.option_utilities, "option_utilities"),
        )
        object.__setattr__(self, "best_option_id", require_non_empty_text(self.best_option_id, "best_option_id"))
        option_ids = {u.option_id for u in self.option_utilities}
        if self.best_option_id not in option_ids:
            raise ValueError("best_option_id must reference an option in option_utilities")
        object.__setattr__(self, "spread", require_non_negative_float(self.spread, "spread"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class TradeoffRecord(ContractRecord):
    """Auditable record of a tradeoff decision with rationale."""

    tradeoff_id: str
    comparison_id: str
    chosen_option_id: str
    rejected_option_ids: tuple[str, ...]
    tradeoff_direction: TradeoffDirection
    rationale: str
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tradeoff_id", require_non_empty_text(self.tradeoff_id, "tradeoff_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(
            self, "chosen_option_id", require_non_empty_text(self.chosen_option_id, "chosen_option_id"),
        )
        if not isinstance(self.rejected_option_ids, tuple):
            object.__setattr__(self, "rejected_option_ids", tuple(self.rejected_option_ids))
        for rid in self.rejected_option_ids:
            require_non_empty_text(rid, "rejected_option_ids entry")
        if not isinstance(self.tradeoff_direction, TradeoffDirection):
            raise ValueError("tradeoff_direction must be a TradeoffDirection value")
        object.__setattr__(self, "rationale", require_non_empty_text(self.rationale, "rationale"))
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))


@dataclass(frozen=True, slots=True)
class DecisionPolicy(ContractRecord):
    """Policy constraints governing automated decision approval."""

    policy_id: str
    name: str
    min_confidence: float
    max_risk_tolerance: float
    max_cost: float
    deadline_weight: float
    require_human_above_risk: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "min_confidence", require_unit_float(self.min_confidence, "min_confidence"))
        object.__setattr__(
            self, "max_risk_tolerance", require_unit_float(self.max_risk_tolerance, "max_risk_tolerance"),
        )
        object.__setattr__(self, "max_cost", require_non_negative_float(self.max_cost, "max_cost"))
        object.__setattr__(self, "deadline_weight", require_unit_float(self.deadline_weight, "deadline_weight"))
        object.__setattr__(
            self,
            "require_human_above_risk",
            require_unit_float(self.require_human_above_risk, "require_human_above_risk"),
        )


@dataclass(frozen=True, slots=True)
class UtilityVerdict(ContractRecord):
    """Final verdict from utility evaluation against a decision policy."""

    verdict_id: str
    comparison_id: str
    policy_id: str
    approved: bool
    recommended_option_id: str
    confidence: float
    reasons: tuple[str, ...]
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict_id", require_non_empty_text(self.verdict_id, "verdict_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a bool")
        object.__setattr__(
            self,
            "recommended_option_id",
            require_non_empty_text(self.recommended_option_id, "recommended_option_id"),
        )
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
