"""Purpose: decision learning loop contracts for outcome tracking and model adjustment.
Governance scope: outcome recording, preference signals, tradeoff outcomes,
learning aggregation, decision adjustments, and provider preferences.
Dependencies: docs/29_decision_learning.md, shared contract base helpers, utility contracts.
Invariants:
  - Outcomes are immutable records of what happened.
  - Adjustments are bounded and auditable.
  - No auto-execution from learning alone.
  - All float scores/magnitudes are finite and bounded.
  - All ID and label fields are non-empty strings.
  - Datetime fields are valid ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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


# --- Classification enums ---


class OutcomeQuality(StrEnum):
    """Classification of how well a decision outcome turned out."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class AdjustmentType(StrEnum):
    """Classification of adjustments to the decision model."""

    WEIGHT_INCREASE = "weight_increase"
    WEIGHT_DECREASE = "weight_decrease"
    CONFIDENCE_BOOST = "confidence_boost"
    CONFIDENCE_PENALTY = "confidence_penalty"
    PREFERENCE_UPDATE = "preference_update"
    CALIBRATION = "calibration"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class DecisionOutcomeRecord(ContractRecord):
    """Links a utility decision to its actual outcome."""

    outcome_id: str
    comparison_id: str
    chosen_option_id: str
    quality: OutcomeQuality
    actual_cost: float
    actual_duration_seconds: float
    success_observed: bool
    notes: str
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(
            self, "chosen_option_id", require_non_empty_text(self.chosen_option_id, "chosen_option_id"),
        )
        if not isinstance(self.quality, OutcomeQuality):
            raise ValueError("quality must be an OutcomeQuality value")
        object.__setattr__(self, "actual_cost", require_non_negative_float(self.actual_cost, "actual_cost"))
        object.__setattr__(
            self,
            "actual_duration_seconds",
            require_non_negative_float(self.actual_duration_seconds, "actual_duration_seconds"),
        )
        if not isinstance(self.success_observed, bool):
            raise ValueError("success_observed must be a bool")
        object.__setattr__(self, "notes", require_non_empty_text(self.notes, "notes"))
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))


@dataclass(frozen=True, slots=True)
class PreferenceSignal(ContractRecord):
    """A single signal about what worked or did not in a decision context."""

    signal_id: str
    context_type: str
    context_id: str
    factor_kind: str
    direction: str
    magnitude: float
    reason: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(self, "context_id", require_non_empty_text(self.context_id, "context_id"))
        object.__setattr__(self, "factor_kind", require_non_empty_text(self.factor_kind, "factor_kind"))
        if self.direction not in ("strengthen", "weaken"):
            raise ValueError("direction must be 'strengthen' or 'weaken'")
        object.__setattr__(self, "magnitude", require_unit_float(self.magnitude, "magnitude"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "observed_at", require_datetime_text(self.observed_at, "observed_at"))


@dataclass(frozen=True, slots=True)
class TradeoffOutcome(ContractRecord):
    """Captures how a tradeoff actually played out."""

    outcome_id: str
    tradeoff_id: str
    chosen_option_id: str
    quality: OutcomeQuality
    regret_score: float
    alternative_would_have_been_better: bool
    explanation: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "tradeoff_id", require_non_empty_text(self.tradeoff_id, "tradeoff_id"))
        object.__setattr__(
            self, "chosen_option_id", require_non_empty_text(self.chosen_option_id, "chosen_option_id"),
        )
        if not isinstance(self.quality, OutcomeQuality):
            raise ValueError("quality must be an OutcomeQuality value")
        object.__setattr__(self, "regret_score", require_unit_float(self.regret_score, "regret_score"))
        if not isinstance(self.alternative_would_have_been_better, bool):
            raise ValueError("alternative_would_have_been_better must be a bool")
        object.__setattr__(self, "explanation", require_non_empty_text(self.explanation, "explanation"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class DecisionAdjustment(ContractRecord):
    """A specific adjustment to make to the decision model."""

    adjustment_id: str
    adjustment_type: AdjustmentType
    target_factor_kind: str
    old_value: float
    new_value: float
    delta: float
    reason: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "adjustment_id", require_non_empty_text(self.adjustment_id, "adjustment_id"))
        if not isinstance(self.adjustment_type, AdjustmentType):
            raise ValueError("adjustment_type must be an AdjustmentType value")
        object.__setattr__(
            self, "target_factor_kind", require_non_empty_text(self.target_factor_kind, "target_factor_kind"),
        )
        object.__setattr__(self, "old_value", require_unit_float(self.old_value, "old_value"))
        object.__setattr__(self, "new_value", require_unit_float(self.new_value, "new_value"))
        object.__setattr__(self, "delta", require_finite_float(self.delta, "delta"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class UtilityLearningRecord(ContractRecord):
    """Aggregated learning from a decision cycle."""

    record_id: str
    comparison_id: str
    outcome: DecisionOutcomeRecord
    signals: tuple[PreferenceSignal, ...]
    adjustments: tuple[DecisionAdjustment, ...]
    learned_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        if not isinstance(self.outcome, DecisionOutcomeRecord):
            raise ValueError("outcome must be a DecisionOutcomeRecord")
        if not all(isinstance(s, PreferenceSignal) for s in self.signals):
            raise ValueError("all signals must be PreferenceSignal instances")
        if not all(isinstance(a, DecisionAdjustment) for a in self.adjustments):
            raise ValueError("all adjustments must be DecisionAdjustment instances")
        object.__setattr__(self, "signals", freeze_value(list(self.signals)))
        object.__setattr__(self, "adjustments", freeze_value(list(self.adjustments)))
        object.__setattr__(self, "learned_at", require_datetime_text(self.learned_at, "learned_at"))


@dataclass(frozen=True, slots=True)
class ProviderPreference(ContractRecord):
    """Learned preference for a specific provider in a context."""

    preference_id: str
    provider_id: str
    context_type: str
    score: float
    sample_count: int
    last_updated: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "preference_id", require_non_empty_text(self.preference_id, "preference_id"))
        object.__setattr__(self, "provider_id", require_non_empty_text(self.provider_id, "provider_id"))
        object.__setattr__(self, "context_type", require_non_empty_text(self.context_type, "context_type"))
        object.__setattr__(self, "score", require_unit_float(self.score, "score"))
        object.__setattr__(self, "sample_count", require_non_negative_int(self.sample_count, "sample_count"))
        object.__setattr__(self, "last_updated", require_datetime_text(self.last_updated, "last_updated"))
