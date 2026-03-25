"""Tests for the decision learning integration bridge.

Covers:
- feedback_after_decision delegation
- apply_learned_weights with and without adjustments
- propagate_to_knowledge_learning
- get_preferred_providers filtering and ordering
"""

from __future__ import annotations

from mcoi_runtime.contracts.decision_learning import (
    DecisionOutcomeRecord,
    OutcomeQuality,
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
from mcoi_runtime.core.decision_learning_integration import DecisionLearningBridge
from mcoi_runtime.core.learning import LearningEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTER = 0


def _make_clock():
    global _COUNTER
    _COUNTER = 0

    def clock() -> str:
        global _COUNTER
        _COUNTER += 1
        minutes = _COUNTER // 60
        seconds = _COUNTER % 60
        return f"2026-03-20T00:{minutes:02d}:{seconds:02d}Z"

    return clock


def _make_profile(
    *,
    profile_id: str = "prof-1",
    factors: tuple[DecisionFactor, ...] | None = None,
) -> UtilityProfile:
    if factors is None:
        factors = (
            DecisionFactor(factor_id="f-risk", kind=DecisionFactorKind.RISK, weight=0.4, value=0.3, label="risk"),
            DecisionFactor(factor_id="f-cost", kind=DecisionFactorKind.COST, weight=0.3, value=0.5, label="cost"),
            DecisionFactor(factor_id="f-conf", kind=DecisionFactorKind.CONFIDENCE, weight=0.3, value=0.8, label="confidence"),
        )
    return UtilityProfile(
        profile_id=profile_id,
        context_type="test",
        context_id="ctx-1",
        factors=factors,
        tradeoff_direction=TradeoffDirection.BALANCED,
        created_at="2026-03-20T00:00:00Z",
    )


def _make_comparison(profile_id: str = "prof-1") -> DecisionComparison:
    ou1 = OptionUtility(option_id="opt-a", raw_score=0.7, weighted_score=0.65, factor_contributions={"risk": 0.3}, rank=1)
    ou2 = OptionUtility(option_id="opt-b", raw_score=0.5, weighted_score=0.45, factor_contributions={"risk": 0.5}, rank=2)
    return DecisionComparison(
        comparison_id="cmp-1",
        profile_id=profile_id,
        option_utilities=(ou1, ou2),
        best_option_id="opt-a",
        spread=0.2,
        decided_at="2026-03-20T00:00:00Z",
    )


def _make_option(option_id: str = "opt-a") -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label="Option A",
        risk_level=RiskLevel.LOW,
        estimated_cost=100.0,
        estimated_duration_seconds=3600.0,
        success_probability=0.9,
    )


def _make_tradeoff() -> TradeoffRecord:
    return TradeoffRecord(
        tradeoff_id="tradeoff-1",
        comparison_id="cmp-1",
        chosen_option_id="opt-a",
        rejected_option_ids=("opt-b",),
        tradeoff_direction=TradeoffDirection.BALANCED,
        rationale="option A scored higher",
        recorded_at="2026-03-20T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests: feedback_after_decision
# ---------------------------------------------------------------------------


class TestFeedbackAfterDecision:
    def test_delegates_to_full_learning_cycle(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        result = DecisionLearningBridge.feedback_after_decision(
            decision_engine=engine,
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            actual_cost=90.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="went well",
        )
        assert result.comparison_id == "cmp-1"
        assert result.outcome.quality == OutcomeQuality.SUCCESS
        assert len(result.signals) > 0
        assert len(result.adjustments) > 0

    def test_failure_produces_weaken_signals(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        result = DecisionLearningBridge.feedback_after_decision(
            decision_engine=engine,
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.FAILURE,
            actual_cost=200.0,
            actual_duration_seconds=7200.0,
            success_observed=False,
            notes="it broke",
        )
        assert result.outcome.quality == OutcomeQuality.FAILURE
        for signal in result.signals:
            assert signal.direction == "weaken"


# ---------------------------------------------------------------------------
# Tests: apply_learned_weights
# ---------------------------------------------------------------------------


class TestApplyLearnedWeights:
    def test_no_adjustments_returns_original(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        profile = _make_profile()
        result = DecisionLearningBridge.apply_learned_weights(engine, profile, "2026-03-20T00:01:00Z")
        assert result is profile  # identity — no change

    def test_adjustments_change_weights(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        # Run a success cycle to produce adjustments
        DecisionLearningBridge.feedback_after_decision(
            decision_engine=engine,
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            actual_cost=50.0,
            actual_duration_seconds=1000.0,
            success_observed=True,
            notes="good",
        )
        profile = _make_profile()
        result = DecisionLearningBridge.apply_learned_weights(engine, profile, "2026-03-20T00:02:00Z")
        assert result is not profile
        assert result.profile_id != profile.profile_id
        # At least one factor weight should differ
        original_weights = {f.kind: f.weight for f in profile.factors}
        new_weights = {f.kind: f.weight for f in result.factors}
        assert any(new_weights[k] != original_weights[k] for k in original_weights)

    def test_preserves_context(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        DecisionLearningBridge.feedback_after_decision(
            decision_engine=engine,
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            actual_cost=50.0,
            actual_duration_seconds=1000.0,
            success_observed=True,
            notes="good",
        )
        profile = _make_profile()
        result = DecisionLearningBridge.apply_learned_weights(engine, profile, "2026-03-20T00:02:00Z")
        assert result.context_type == profile.context_type
        assert result.context_id == profile.context_id
        assert result.tradeoff_direction == profile.tradeoff_direction

    def test_weights_bounded_zero_to_one(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        # Run many failure cycles to push weights down
        for _ in range(20):
            DecisionLearningBridge.feedback_after_decision(
                decision_engine=engine,
                comparison=_make_comparison(),
                chosen_option=_make_option(),
                profile=_make_profile(),
                tradeoff=_make_tradeoff(),
                quality=OutcomeQuality.FAILURE,
                actual_cost=200.0,
                actual_duration_seconds=7200.0,
                success_observed=False,
                notes="bad",
            )
        profile = _make_profile()
        result = DecisionLearningBridge.apply_learned_weights(engine, profile, "2026-03-20T00:03:00Z")
        for f in result.factors:
            assert 0.0 <= f.weight <= 1.0


# ---------------------------------------------------------------------------
# Tests: propagate_to_knowledge_learning
# ---------------------------------------------------------------------------


class TestPropagateToKnowledgeLearning:
    def test_success_outcome_updates_confidence_and_records_lesson(self):
        clock = _make_clock()
        dl_engine = DecisionLearningEngine(clock=clock)
        learning_engine = LearningEngine(clock=clock)

        outcome = DecisionOutcomeRecord(
            outcome_id="out-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=90.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="worked",
            recorded_at="2026-03-20T00:00:01Z",
        )

        DecisionLearningBridge.propagate_to_knowledge_learning(
            learning_engine=learning_engine,
            outcome=outcome,
            knowledge_id="know-1",
        )

        # Verify the learning engine recorded a lesson
        lessons = learning_engine.find_relevant_lessons(("decision",))
        assert len(lessons) == 1
        assert lessons[0].source_id == "out-1"

    def test_failure_outcome_decreases_confidence(self):
        clock = _make_clock()
        dl_engine = DecisionLearningEngine(clock=clock)
        learning_engine = LearningEngine(clock=clock)

        outcome = DecisionOutcomeRecord(
            outcome_id="out-2",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.FAILURE,
            actual_cost=200.0,
            actual_duration_seconds=7200.0,
            success_observed=False,
            notes="failed",
            recorded_at="2026-03-20T00:00:01Z",
        )

        DecisionLearningBridge.propagate_to_knowledge_learning(
            learning_engine=learning_engine,
            outcome=outcome,
            knowledge_id="know-1",
        )

        lessons = learning_engine.find_relevant_lessons(("decision",))
        assert len(lessons) == 1
        assert "failure" in lessons[0].outcome


# ---------------------------------------------------------------------------
# Tests: get_preferred_providers
# ---------------------------------------------------------------------------


class TestGetPreferredProviders:
    def test_no_preferences_returns_empty(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1", "prov-2"),
        )
        assert result == ()

    def test_filters_by_min_samples(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        # Add only 2 samples for prov-1 (below default min_samples=3)
        engine.update_provider_preference("prov-1", "test", True)
        engine.update_provider_preference("prov-1", "test", True)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1",),
        )
        assert result == ()

    def test_returns_sorted_by_score(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        # Build up enough samples
        for _ in range(5):
            engine.update_provider_preference("prov-1", "test", True)
            engine.update_provider_preference("prov-2", "test", False)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1", "prov-2"),
        )
        assert len(result) == 2
        assert result[0][0] == "prov-1"  # higher score first
        assert result[0][1] > result[1][1]

    def test_custom_min_samples(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        engine.update_provider_preference("prov-1", "test", True)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1",),
            min_samples=1,
        )
        assert len(result) == 1

    def test_ignores_providers_not_requested(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        for _ in range(5):
            engine.update_provider_preference("prov-1", "test", True)
            engine.update_provider_preference("prov-2", "test", True)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1",),  # Only asking for prov-1
        )
        assert len(result) == 1
        assert result[0][0] == "prov-1"
