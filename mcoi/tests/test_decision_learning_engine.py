"""Tests for mcoi_runtime.core.decision_learning — decision learning engine."""

from __future__ import annotations

import pytest

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
from mcoi_runtime.contracts.simulation import RiskLevel, SimulationOption
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    OptionUtility,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
)
from mcoi_runtime.core.decision_learning import DecisionLearningEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICK = 0


def _clock() -> str:
    global _TICK
    _TICK += 1
    return f"2026-01-01T00:00:{_TICK:02d}Z"


def _reset_clock() -> None:
    global _TICK
    _TICK = 0


def _make_engine() -> DecisionLearningEngine:
    _reset_clock()
    return DecisionLearningEngine(clock=_clock)


def _make_option(
    option_id: str = "opt-a",
    *,
    cost: float = 1000.0,
    duration: float = 3600.0,
    success: float = 0.8,
    risk: RiskLevel = RiskLevel.LOW,
) -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label=f"Option {option_id}",
        risk_level=risk,
        estimated_cost=cost,
        estimated_duration_seconds=duration,
        success_probability=success,
    )


def _make_option_utility(option_id: str, score: float, rank: int) -> OptionUtility:
    return OptionUtility(
        option_id=option_id,
        raw_score=score,
        weighted_score=score,
        factor_contributions={},
        rank=rank,
    )


def _make_comparison(best_id: str = "opt-a") -> DecisionComparison:
    return DecisionComparison(
        comparison_id="cmp-test",
        profile_id="profile-test",
        option_utilities=(
            _make_option_utility(best_id, 0.8, 1),
        ),
        best_option_id=best_id,
        spread=0.0,
        decided_at="2026-01-01T00:00:00Z",
    )


def _make_profile(
    tradeoff: TradeoffDirection = TradeoffDirection.BALANCED,
) -> UtilityProfile:
    return UtilityProfile(
        profile_id="profile-test",
        context_type="goal",
        context_id="goal-1",
        factors=(
            DecisionFactor(factor_id="f-risk", kind=DecisionFactorKind.RISK, weight=0.3, value=1.0, label="Risk"),
            DecisionFactor(factor_id="f-conf", kind=DecisionFactorKind.CONFIDENCE, weight=0.3, value=1.0, label="Confidence"),
            DecisionFactor(factor_id="f-cost", kind=DecisionFactorKind.COST, weight=0.2, value=1.0, label="Cost"),
            DecisionFactor(factor_id="f-time", kind=DecisionFactorKind.TIME, weight=0.2, value=1.0, label="Time"),
        ),
        tradeoff_direction=tradeoff,
        created_at="2026-01-01T00:00:00Z",
    )


def _make_tradeoff() -> TradeoffRecord:
    return TradeoffRecord(
        tradeoff_id="to-test",
        comparison_id="cmp-test",
        chosen_option_id="opt-a",
        rejected_option_ids=("opt-b",),
        tradeoff_direction=TradeoffDirection.BALANCED,
        rationale="Chose best option.",
        recorded_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


class TestRecordOutcome:
    def test_records_success(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        outcome = engine.record_outcome(
            comparison=comparison,
            chosen_option=option,
            quality=OutcomeQuality.SUCCESS,
            actual_cost=800.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="Completed well.",
        )
        assert isinstance(outcome, DecisionOutcomeRecord)
        assert outcome.quality == OutcomeQuality.SUCCESS
        assert outcome.actual_cost == 800.0
        assert outcome.success_observed is True

    def test_records_failure(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        outcome = engine.record_outcome(
            comparison=comparison,
            chosen_option=option,
            quality=OutcomeQuality.FAILURE,
            actual_cost=2000.0,
            actual_duration_seconds=7200.0,
            success_observed=False,
            notes="Failed completely.",
        )
        assert outcome.quality == OutcomeQuality.FAILURE
        assert outcome.success_observed is False

    def test_outcome_stored(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        engine.record_outcome(
            comparison=comparison,
            chosen_option=option,
            quality=OutcomeQuality.SUCCESS,
            actual_cost=100.0,
            actual_duration_seconds=60.0,
            success_observed=True,
            notes="OK.",
        )
        assert engine.outcome_count == 1


# ---------------------------------------------------------------------------
# assess_tradeoff
# ---------------------------------------------------------------------------


class TestAssessTradeoff:
    def test_success_zero_regret(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.SUCCESS,
            alternative_would_have_been_better=False,
            explanation="Good choice.",
        )
        assert isinstance(result, TradeoffOutcome)
        assert result.regret_score == 0.0

    def test_failure_max_regret(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.FAILURE,
            alternative_would_have_been_better=False,
            explanation="Bad choice.",
        )
        assert result.regret_score == 1.0

    def test_partial_success_moderate_regret(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.PARTIAL_SUCCESS,
            alternative_would_have_been_better=False,
            explanation="Partial.",
        )
        assert result.regret_score == 0.3

    def test_alternative_better_adds_regret(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.PARTIAL_SUCCESS,
            alternative_would_have_been_better=True,
            explanation="Should have picked the other one.",
        )
        assert result.regret_score == 0.5  # 0.3 + 0.2

    def test_regret_clamped_at_one(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.FAILURE,
            alternative_would_have_been_better=True,
            explanation="Total regret.",
        )
        assert result.regret_score == 1.0  # 1.0 + 0.2 clamped to 1.0

    def test_unknown_regret(self) -> None:
        engine = _make_engine()
        tradeoff = _make_tradeoff()
        result = engine.assess_tradeoff(
            tradeoff=tradeoff,
            quality=OutcomeQuality.UNKNOWN,
            alternative_would_have_been_better=False,
            explanation="Unknown.",
        )
        assert result.regret_score == 0.5


# ---------------------------------------------------------------------------
# generate_signals
# ---------------------------------------------------------------------------


class TestGenerateSignals:
    def test_success_generates_strengthen(self) -> None:
        engine = _make_engine()
        outcome = DecisionOutcomeRecord(
            outcome_id="out-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=500.0,
            actual_duration_seconds=1800.0,
            success_observed=True,
            notes="Good.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals(outcome, profile)
        assert len(signals) == 4  # One per factor
        assert all(s.direction == "strengthen" for s in signals)
        assert all(s.magnitude == 0.1 for s in signals)
        assert signals[0].reason == "outcome quality signal detected"
        assert outcome.quality.value not in signals[0].reason
        assert signals[0].factor_kind not in signals[0].reason

    def test_failure_generates_weaken(self) -> None:
        engine = _make_engine()
        outcome = DecisionOutcomeRecord(
            outcome_id="out-2",
            comparison_id="cmp-2",
            chosen_option_id="opt-b",
            quality=OutcomeQuality.FAILURE,
            actual_cost=5000.0,
            actual_duration_seconds=7200.0,
            success_observed=False,
            notes="Bad.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals(outcome, profile)
        assert len(signals) == 4
        assert all(s.direction == "weaken" for s in signals)
        assert all(s.magnitude == 0.15 for s in signals)

    def test_unknown_generates_no_signals(self) -> None:
        engine = _make_engine()
        outcome = DecisionOutcomeRecord(
            outcome_id="out-3",
            comparison_id="cmp-3",
            chosen_option_id="opt-c",
            quality=OutcomeQuality.UNKNOWN,
            actual_cost=0.0,
            actual_duration_seconds=0.0,
            success_observed=False,
            notes="Unknown outcome.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals(outcome, profile)
        assert signals == ()

    def test_partial_success_generates_weaken_low_magnitude(self) -> None:
        engine = _make_engine()
        outcome = DecisionOutcomeRecord(
            outcome_id="out-4",
            comparison_id="cmp-4",
            chosen_option_id="opt-d",
            quality=OutcomeQuality.PARTIAL_SUCCESS,
            actual_cost=1000.0,
            actual_duration_seconds=3600.0,
            success_observed=False,
            notes="Partial.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals(outcome, profile)
        assert all(s.direction == "weaken" for s in signals)
        assert all(s.magnitude == 0.05 for s in signals)


# ---------------------------------------------------------------------------
# generate_signals_with_option (cost/time accuracy bonuses)
# ---------------------------------------------------------------------------


class TestGenerateSignalsWithOption:
    def test_cost_accuracy_bonus(self) -> None:
        engine = _make_engine()
        option = _make_option(cost=1000.0, duration=3600.0)
        outcome = DecisionOutcomeRecord(
            outcome_id="out-acc",
            comparison_id="cmp-acc",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=500.0,  # < 1000 * 0.8 = 800
            actual_duration_seconds=3600.0,
            success_observed=True,
            notes="Cheap.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals_with_option(outcome, profile, option)
        # 4 base signals + 1 cost accuracy bonus
        assert len(signals) == 5
        cost_bonus = [s for s in signals if "cost accuracy" in s.reason]
        assert len(cost_bonus) == 1
        assert cost_bonus[0].direction == "strengthen"

    def test_time_accuracy_bonus(self) -> None:
        engine = _make_engine()
        option = _make_option(cost=1000.0, duration=3600.0)
        outcome = DecisionOutcomeRecord(
            outcome_id="out-time",
            comparison_id="cmp-time",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=1000.0,
            actual_duration_seconds=2000.0,  # < 3600 * 0.8 = 2880
            success_observed=True,
            notes="Fast.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals_with_option(outcome, profile, option)
        # 4 base + 1 time accuracy bonus
        assert len(signals) == 5
        time_bonus = [s for s in signals if "time accuracy" in s.reason]
        assert len(time_bonus) == 1

    def test_no_bonus_when_costs_match(self) -> None:
        engine = _make_engine()
        option = _make_option(cost=1000.0, duration=3600.0)
        outcome = DecisionOutcomeRecord(
            outcome_id="out-match",
            comparison_id="cmp-match",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=900.0,  # > 1000 * 0.8 = 800, no bonus
            actual_duration_seconds=3500.0,  # > 3600 * 0.8 = 2880, no bonus
            success_observed=True,
            notes="Expected.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        profile = _make_profile()
        signals = engine.generate_signals_with_option(outcome, profile, option)
        assert len(signals) == 4  # No bonuses


# ---------------------------------------------------------------------------
# compute_adjustments
# ---------------------------------------------------------------------------


class TestComputeAdjustments:
    def test_strengthen_signals_increase_weight(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        signals = (
            PreferenceSignal(
                signal_id="s-1",
                context_type="goal",
                context_id="goal-1",
                factor_kind="risk",
                direction="strengthen",
                magnitude=0.1,
                reason="Good risk outcome.",
                observed_at="2026-01-01T00:00:00Z",
            ),
        )
        adjustments = engine.compute_adjustments(signals, profile)
        assert len(adjustments) == 1
        assert adjustments[0].adjustment_type == AdjustmentType.WEIGHT_INCREASE
        assert adjustments[0].target_factor_kind == "risk"
        assert adjustments[0].delta > 0
        assert adjustments[0].reason == "aggregated learning signal"
        assert adjustments[0].target_factor_kind not in adjustments[0].reason
        assert f"{adjustments[0].delta:+.6f}" not in adjustments[0].reason

    def test_weaken_signals_decrease_weight(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        signals = (
            PreferenceSignal(
                signal_id="s-2",
                context_type="goal",
                context_id="goal-1",
                factor_kind="cost",
                direction="weaken",
                magnitude=0.15,
                reason="Bad cost outcome.",
                observed_at="2026-01-01T00:00:00Z",
            ),
        )
        adjustments = engine.compute_adjustments(signals, profile)
        assert len(adjustments) == 1
        assert adjustments[0].adjustment_type == AdjustmentType.WEIGHT_DECREASE
        assert adjustments[0].delta < 0

    def test_empty_signals_returns_empty(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        adjustments = engine.compute_adjustments((), profile)
        assert adjustments == ()

    def test_adjustments_stored(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        signals = (
            PreferenceSignal(
                signal_id="s-3",
                context_type="goal",
                context_id="goal-1",
                factor_kind="risk",
                direction="strengthen",
                magnitude=0.1,
                reason="Good.",
                observed_at="2026-01-01T00:00:00Z",
            ),
        )
        engine.compute_adjustments(signals, profile)
        assert engine.adjustment_count == 1

    def test_adjustment_bounded(self) -> None:
        """Weight change per adjustment is bounded by max 0.05 * magnitude."""
        engine = _make_engine()
        profile = _make_profile()
        signals = (
            PreferenceSignal(
                signal_id="s-4",
                context_type="goal",
                context_id="goal-1",
                factor_kind="risk",
                direction="strengthen",
                magnitude=1.0,
                reason="Max magnitude.",
                observed_at="2026-01-01T00:00:00Z",
            ),
        )
        adjustments = engine.compute_adjustments(signals, profile)
        assert adjustments[0].delta <= 0.05


# ---------------------------------------------------------------------------
# provider preferences
# ---------------------------------------------------------------------------


class TestProviderPreferences:
    def test_initial_preference(self) -> None:
        engine = _make_engine()
        pref = engine.update_provider_preference("openai", "goal", True)
        assert isinstance(pref, ProviderPreference)
        assert pref.provider_id == "openai"
        assert pref.context_type == "goal"
        assert pref.sample_count == 1
        # Initial was 0.5, success: 0.5 * 0.9 + 1.0 * 0.1 = 0.55
        assert pref.score == 0.55

    def test_successive_updates(self) -> None:
        engine = _make_engine()
        engine.update_provider_preference("openai", "goal", True)
        pref = engine.update_provider_preference("openai", "goal", True)
        assert pref.sample_count == 2
        assert pref.score > 0.55  # Score should increase

    def test_failure_decreases_score(self) -> None:
        engine = _make_engine()
        engine.update_provider_preference("openai", "goal", True)
        pref = engine.update_provider_preference("openai", "goal", False)
        assert pref.score < 0.55  # Decreased from initial success

    def test_get_nonexistent_returns_none(self) -> None:
        engine = _make_engine()
        assert engine.get_provider_preference("nonexistent", "goal") is None

    def test_get_existing(self) -> None:
        engine = _make_engine()
        engine.update_provider_preference("anthropic", "skill", True)
        pref = engine.get_provider_preference("anthropic", "skill")
        assert pref is not None
        assert pref.provider_id == "anthropic"

    def test_different_contexts_independent(self) -> None:
        engine = _make_engine()
        engine.update_provider_preference("openai", "goal", True)
        engine.update_provider_preference("openai", "workflow", False)
        goal_pref = engine.get_provider_preference("openai", "goal")
        wf_pref = engine.get_provider_preference("openai", "workflow")
        assert goal_pref is not None
        assert wf_pref is not None
        assert goal_pref.score > wf_pref.score


# ---------------------------------------------------------------------------
# full_learning_cycle
# ---------------------------------------------------------------------------


class TestFullLearningCycle:
    def test_success_cycle(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        record = engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=option,
            profile=profile,
            tradeoff=tradeoff,
            quality=OutcomeQuality.SUCCESS,
            actual_cost=800.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="Went well.",
        )

        assert isinstance(record, UtilityLearningRecord)
        assert record.outcome.quality == OutcomeQuality.SUCCESS
        assert len(record.signals) >= 4  # At least one per factor
        assert len(record.adjustments) >= 1  # At least one adjustment

    def test_failure_cycle(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        record = engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=option,
            profile=profile,
            tradeoff=tradeoff,
            quality=OutcomeQuality.FAILURE,
            actual_cost=5000.0,
            actual_duration_seconds=7200.0,
            success_observed=False,
            notes="Failed badly.",
            alternative_better=True,
        )

        assert record.outcome.quality == OutcomeQuality.FAILURE
        # Failure should produce weaken signals
        weaken_signals = [s for s in record.signals if s.direction == "weaken"]
        assert len(weaken_signals) >= 4

    def test_unknown_cycle_no_signals(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        record = engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=option,
            profile=profile,
            tradeoff=tradeoff,
            quality=OutcomeQuality.UNKNOWN,
            actual_cost=0.0,
            actual_duration_seconds=0.0,
            success_observed=False,
            notes="Unknown.",
        )

        assert record.signals == ()
        assert record.adjustments == ()


# ---------------------------------------------------------------------------
# get_learned_factor_adjustments
# ---------------------------------------------------------------------------


class TestGetLearnedFactorAdjustments:
    def test_empty_initially(self) -> None:
        engine = _make_engine()
        assert engine.get_learned_factor_adjustments() == {}

    def test_cumulative_after_cycles(self) -> None:
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        # Run two success cycles
        engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=option,
            profile=profile,
            tradeoff=tradeoff,
            quality=OutcomeQuality.SUCCESS,
            actual_cost=500.0,
            actual_duration_seconds=1800.0,
            success_observed=True,
            notes="First success.",
        )
        engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=option,
            profile=profile,
            tradeoff=tradeoff,
            quality=OutcomeQuality.SUCCESS,
            actual_cost=500.0,
            actual_duration_seconds=1800.0,
            success_observed=True,
            notes="Second success.",
        )

        adjustments = engine.get_learned_factor_adjustments()
        assert len(adjustments) > 0
        # All deltas should be positive (strengthen)
        for kind, delta in adjustments.items():
            assert delta > 0


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_learning_improves_over_time(self) -> None:
        """After multiple successes, learned deltas should be positive and growing."""
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option(cost=1000.0, duration=3600.0)
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        for i in range(5):
            engine.full_learning_cycle(
                comparison=comparison,
                chosen_option=option,
                profile=profile,
                tradeoff=tradeoff,
                quality=OutcomeQuality.SUCCESS,
                actual_cost=800.0,
                actual_duration_seconds=3000.0,
                success_observed=True,
                notes=f"Cycle {i+1}.",
            )

        adjustments = engine.get_learned_factor_adjustments()
        # After 5 success cycles, risk factor should have positive delta
        assert "risk" in adjustments
        assert adjustments["risk"] > 0

    def test_provider_preference_converges(self) -> None:
        """After many successes, provider score should approach 1.0."""
        engine = _make_engine()
        for _ in range(20):
            engine.update_provider_preference("reliable", "goal", True)
        pref = engine.get_provider_preference("reliable", "goal")
        assert pref is not None
        assert pref.score > 0.8
        assert pref.sample_count == 20

    def test_mixed_outcomes_moderate_adjustment(self) -> None:
        """Mixed success/failure should produce smaller net adjustments."""
        engine = _make_engine()
        comparison = _make_comparison()
        option = _make_option()
        profile = _make_profile()
        tradeoff = _make_tradeoff()

        engine.full_learning_cycle(
            comparison=comparison, chosen_option=option, profile=profile,
            tradeoff=tradeoff, quality=OutcomeQuality.SUCCESS,
            actual_cost=800.0, actual_duration_seconds=3000.0,
            success_observed=True, notes="Success.",
        )
        engine.full_learning_cycle(
            comparison=comparison, chosen_option=option, profile=profile,
            tradeoff=tradeoff, quality=OutcomeQuality.FAILURE,
            actual_cost=5000.0, actual_duration_seconds=7200.0,
            success_observed=False, notes="Failure.",
        )

        adjustments = engine.get_learned_factor_adjustments()
        # Net delta should be small (success + failure nearly cancel)
        for kind, delta in adjustments.items():
            assert abs(delta) < 0.02  # Small net effect
