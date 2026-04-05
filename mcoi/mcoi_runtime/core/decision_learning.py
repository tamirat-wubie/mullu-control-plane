"""Purpose: decision learning loop — feeds utility decision outcomes back into
the learning system so future decisions improve.
Governance scope: decision outcome recording, preference signal generation,
factor weight adjustment, and provider preference tracking only.
Dependencies: decision_learning contracts, utility contracts, simulation contracts,
core invariants.
Invariants:
  - Learning is bounded: weight changes are small per cycle (max 0.05 per adjustment).
  - Learning is auditable: every change produces a record.
  - No auto-execution: learning records are advisory.
  - No network, no IO. Clock injected for determinism.
"""

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType
from typing import Callable, Mapping

from mcoi_runtime.contracts.decision_learning import (
    AdjustmentType,
    DecisionAdjustment,
    DecisionOutcomeRecord,
    OutcomeQuality,
    PreferenceSignal,
    ProviderPreference,
    TradeoffOutcome,
    UtilityLearningRecord,
)
from mcoi_runtime.contracts.simulation import SimulationOption
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    TradeoffRecord,
    UtilityProfile,
)
from .invariants import stable_identifier


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class DecisionLearningEngine:
    """Learns from decision outcomes to improve future utility scoring.

    Maintains:
    - Factor weight adjustments based on outcome quality
    - Provider preference scores from observed performance
    - Regret tracking for tradeoff quality assessment
    - Preference signals that can tune future UtilityProfiles
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._outcomes: list[DecisionOutcomeRecord] = []
        self._adjustments: list[DecisionAdjustment] = []
        self._tradeoff_outcomes: list[TradeoffOutcome] = []
        self._provider_preferences: dict[tuple[str, str], ProviderPreference] = {}  # (provider_id, context_type) -> pref

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def outcome_count(self) -> int:
        """Number of recorded outcomes."""
        return len(self._outcomes)

    @property
    def adjustment_count(self) -> int:
        """Number of recorded adjustments."""
        return len(self._adjustments)

    @property
    def outcomes(self) -> tuple[DecisionOutcomeRecord, ...]:
        """All recorded outcomes (immutable copy)."""
        return tuple(self._outcomes)

    @property
    def adjustments(self) -> tuple[DecisionAdjustment, ...]:
        """All recorded adjustments (immutable copy)."""
        return tuple(self._adjustments)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        comparison: DecisionComparison,
        chosen_option: SimulationOption,
        quality: OutcomeQuality,
        actual_cost: float,
        actual_duration_seconds: float,
        success_observed: bool,
        notes: str,
    ) -> DecisionOutcomeRecord:
        """Record the actual outcome of a decision for later learning.

        Creates and stores a DecisionOutcomeRecord linking a comparison
        to its actual outcome.
        """
        now = self._clock()
        outcome_id = stable_identifier("dl-outcome", {
            "comparison_id": comparison.comparison_id,
            "chosen_option_id": chosen_option.option_id,
            "recorded_at": now,
        })

        record = DecisionOutcomeRecord(
            outcome_id=outcome_id,
            comparison_id=comparison.comparison_id,
            chosen_option_id=chosen_option.option_id,
            quality=quality,
            actual_cost=actual_cost,
            actual_duration_seconds=actual_duration_seconds,
            success_observed=success_observed,
            notes=notes,
            recorded_at=now,
        )

        self._outcomes.append(record)
        return record

    def assess_tradeoff(
        self,
        tradeoff: TradeoffRecord,
        quality: OutcomeQuality,
        alternative_would_have_been_better: bool,
        explanation: str,
    ) -> TradeoffOutcome:
        """Assess how a tradeoff played out after the fact.

        Computes a regret score based on outcome quality:
        - SUCCESS: 0.0
        - PARTIAL_SUCCESS: 0.3
        - FAILURE: 1.0
        - UNKNOWN: 0.5
        If the alternative would have been better, adds 0.2 (clamped to 1.0).
        """
        regret_map: dict[OutcomeQuality, float] = {
            OutcomeQuality.SUCCESS: 0.0,
            OutcomeQuality.PARTIAL_SUCCESS: 0.3,
            OutcomeQuality.FAILURE: 1.0,
            OutcomeQuality.UNKNOWN: 0.5,
        }
        regret = regret_map.get(quality, 0.5)
        if alternative_would_have_been_better:
            regret = _clamp(regret + 0.2)

        now = self._clock()
        outcome_id = stable_identifier("dl-tradeoff-outcome", {
            "tradeoff_id": tradeoff.tradeoff_id,
            "assessed_at": now,
        })

        outcome = TradeoffOutcome(
            outcome_id=outcome_id,
            tradeoff_id=tradeoff.tradeoff_id,
            chosen_option_id=tradeoff.chosen_option_id,
            quality=quality,
            regret_score=regret,
            alternative_would_have_been_better=alternative_would_have_been_better,
            explanation=explanation,
            assessed_at=now,
        )
        self._tradeoff_outcomes.append(outcome)
        return outcome

    def generate_signals(
        self,
        outcome: DecisionOutcomeRecord,
        profile: UtilityProfile,
    ) -> tuple[PreferenceSignal, ...]:
        """Generate preference signals from an outcome against a utility profile.

        For each factor in the profile, generates a preference signal based on
        outcome quality:
        - SUCCESS: strengthen with magnitude 0.1
        - FAILURE: weaken with magnitude 0.15
        - PARTIAL_SUCCESS: weaken with magnitude 0.05
        - UNKNOWN: no signal

        Note: cost/time accuracy bonus signals require access to the original
        SimulationOption and are produced only through ``full_learning_cycle``.
        """
        if outcome.quality == OutcomeQuality.UNKNOWN:
            return ()

        signals: list[PreferenceSignal] = []
        now = self._clock()

        # Determine direction and magnitude from quality
        direction_map: dict[OutcomeQuality, tuple[str, float]] = {
            OutcomeQuality.SUCCESS: ("strengthen", 0.1),
            OutcomeQuality.FAILURE: ("weaken", 0.15),
            OutcomeQuality.PARTIAL_SUCCESS: ("weaken", 0.05),
        }
        direction, magnitude = direction_map[outcome.quality]

        for factor in profile.factors:
            signal_id = stable_identifier("dl-signal", {
                "outcome_id": outcome.outcome_id,
                "factor_id": factor.factor_id,
                "direction": direction,
                "observed_at": now,
            })

            signals.append(PreferenceSignal(
                signal_id=signal_id,
                context_type=profile.context_type,
                context_id=profile.context_id,
                factor_kind=factor.kind.value,
                direction=direction,
                magnitude=magnitude,
                reason="outcome quality signal detected",
                observed_at=now,
            ))

        return tuple(signals)

    def generate_signals_with_option(
        self,
        outcome: DecisionOutcomeRecord,
        profile: UtilityProfile,
        chosen_option: SimulationOption,
    ) -> tuple[PreferenceSignal, ...]:
        """Generate preference signals with access to the original option for
        cost and time accuracy signals.
        """
        base_signals = list(self.generate_signals(outcome, profile))
        if outcome.quality == OutcomeQuality.UNKNOWN:
            return tuple(base_signals)

        now = self._clock()

        for factor in profile.factors:
            if factor.kind == DecisionFactorKind.COST:
                if outcome.actual_cost < chosen_option.estimated_cost * 0.8:
                    signal_id = stable_identifier("dl-signal-cost-accuracy", {
                        "outcome_id": outcome.outcome_id,
                        "factor_id": factor.factor_id,
                        "observed_at": now,
                    })
                    base_signals.append(PreferenceSignal(
                        signal_id=signal_id,
                        context_type=profile.context_type,
                        context_id=profile.context_id,
                        factor_kind=factor.kind.value,
                        direction="strengthen",
                        magnitude=0.1,
                        reason="actual cost significantly below estimate — cost accuracy bonus",
                        observed_at=now,
                    ))

            if factor.kind == DecisionFactorKind.TIME:
                if outcome.actual_duration_seconds < chosen_option.estimated_duration_seconds * 0.8:
                    signal_id = stable_identifier("dl-signal-time-accuracy", {
                        "outcome_id": outcome.outcome_id,
                        "factor_id": factor.factor_id,
                        "observed_at": now,
                    })
                    base_signals.append(PreferenceSignal(
                        signal_id=signal_id,
                        context_type=profile.context_type,
                        context_id=profile.context_id,
                        factor_kind=factor.kind.value,
                        direction="strengthen",
                        magnitude=0.1,
                        reason="actual duration significantly below estimate — time accuracy bonus",
                        observed_at=now,
                    ))

        return tuple(base_signals)

    def compute_adjustments(
        self,
        signals: tuple[PreferenceSignal, ...],
        profile: UtilityProfile,
    ) -> tuple[DecisionAdjustment, ...]:
        """Compute factor weight adjustments from aggregated preference signals.

        Aggregates signals by factor_kind:
        - For "strengthen" signals: increase weight by avg(magnitude) * 0.05
        - For "weaken" signals: decrease weight by avg(magnitude) * 0.05
        Clamps new weights to [0.0, 1.0].
        """
        if not signals:
            return ()

        # Group signals by factor_kind and direction
        strengthen_by_kind: dict[str, list[float]] = defaultdict(list)
        weaken_by_kind: dict[str, list[float]] = defaultdict(list)

        for signal in signals:
            if signal.direction == "strengthen":
                strengthen_by_kind[signal.factor_kind].append(signal.magnitude)
            elif signal.direction == "weaken":
                weaken_by_kind[signal.factor_kind].append(signal.magnitude)

        # Build a lookup of current weights by factor kind
        factor_weight_by_kind: dict[str, float] = {}
        for factor in profile.factors:
            factor_weight_by_kind[factor.kind.value] = factor.weight

        adjustments: list[DecisionAdjustment] = []
        now = self._clock()

        # Collect all factor kinds that have signals
        all_kinds = set(strengthen_by_kind.keys()) | set(weaken_by_kind.keys())

        for kind in sorted(all_kinds):
            old_weight = factor_weight_by_kind.get(kind, 0.5)
            delta = 0.0

            if kind in strengthen_by_kind:
                magnitudes = strengthen_by_kind[kind]
                avg_mag = sum(magnitudes) / len(magnitudes)
                delta += avg_mag * 0.05

            if kind in weaken_by_kind:
                magnitudes = weaken_by_kind[kind]
                avg_mag = sum(magnitudes) / len(magnitudes)
                delta -= avg_mag * 0.05

            if delta == 0.0:
                continue

            new_weight = _clamp(old_weight + delta)

            if delta > 0:
                adjustment_type = AdjustmentType.WEIGHT_INCREASE
            else:
                adjustment_type = AdjustmentType.WEIGHT_DECREASE

            adjustment_id = stable_identifier("dl-adj", {
                "factor_kind": kind,
                "delta": str(round(delta, 6)),
                "created_at": now,
            })

            adjustment = DecisionAdjustment(
                adjustment_id=adjustment_id,
                adjustment_type=adjustment_type,
                target_factor_kind=kind,
                old_value=old_weight,
                new_value=new_weight,
                delta=round(delta, 6),
                reason="aggregated learning signal",
                created_at=now,
            )

            adjustments.append(adjustment)
            self._adjustments.append(adjustment)

        return tuple(adjustments)

    def update_provider_preference(
        self,
        provider_id: str,
        context_type: str,
        success: bool,
    ) -> ProviderPreference:
        """Update the running preference score for a provider in a context.

        Uses exponential moving average:
        new_score = old_score * 0.9 + (1.0 if success else 0.0) * 0.1
        """
        key = (provider_id, context_type)
        now = self._clock()

        existing = self._provider_preferences.get(key)
        if existing is not None:
            old_score = existing.score
            old_count = existing.sample_count
        else:
            old_score = 0.5
            old_count = 0

        new_score = _clamp(old_score * 0.9 + (1.0 if success else 0.0) * 0.1)
        new_count = old_count + 1

        preference_id = stable_identifier("dl-prov-pref", {
            "provider_id": provider_id,
            "context_type": context_type,
        })

        pref = ProviderPreference(
            preference_id=preference_id,
            provider_id=provider_id,
            context_type=context_type,
            score=round(new_score, 6),
            sample_count=new_count,
            last_updated=now,
        )

        self._provider_preferences[key] = pref
        return pref

    def get_provider_preference(
        self,
        provider_id: str,
        context_type: str,
    ) -> ProviderPreference | None:
        """Return the current preference for a provider in a context, or None."""
        return self._provider_preferences.get((provider_id, context_type))

    def full_learning_cycle(
        self,
        comparison: DecisionComparison,
        chosen_option: SimulationOption,
        profile: UtilityProfile,
        tradeoff: TradeoffRecord,
        quality: OutcomeQuality,
        actual_cost: float,
        actual_duration_seconds: float,
        success_observed: bool,
        notes: str,
        alternative_better: bool = False,
    ) -> UtilityLearningRecord:
        """Orchestrate a complete decision learning cycle.

        Steps:
        1. Record the outcome
        2. Generate preference signals (with option access for cost/time bonuses)
        3. Compute factor weight adjustments
        4. Assess the tradeoff

        Returns a UtilityLearningRecord bundling everything.
        """
        # Step 1: record outcome
        outcome = self.record_outcome(
            comparison=comparison,
            chosen_option=chosen_option,
            quality=quality,
            actual_cost=actual_cost,
            actual_duration_seconds=actual_duration_seconds,
            success_observed=success_observed,
            notes=notes,
        )

        # Step 2: generate signals (with option for cost/time accuracy)
        signals = self.generate_signals_with_option(outcome, profile, chosen_option)

        # Step 3: compute adjustments
        adjustments = self.compute_adjustments(signals, profile)

        # Step 4: assess tradeoff (stored for auditability)
        tradeoff_outcome = self.assess_tradeoff(
            tradeoff=tradeoff,
            quality=quality,
            alternative_would_have_been_better=alternative_better,
            explanation=notes,
        )

        now = self._clock()
        record_id = stable_identifier("dl-learning", {
            "comparison_id": comparison.comparison_id,
            "outcome_id": outcome.outcome_id,
            "learned_at": now,
        })

        return UtilityLearningRecord(
            record_id=record_id,
            comparison_id=comparison.comparison_id,
            outcome=outcome,
            signals=signals,
            adjustments=adjustments,
            learned_at=now,
        )

    def get_learned_factor_adjustments(self) -> Mapping[str, float]:
        """Return cumulative delta per factor_kind from all recorded adjustments.

        Returns an immutable mapping of factor_kind -> cumulative delta.
        """
        cumulative: dict[str, float] = defaultdict(float)
        for adj in self._adjustments:
            cumulative[adj.target_factor_kind] += adj.delta
        return MappingProxyType(dict(cumulative))
