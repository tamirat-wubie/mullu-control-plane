"""Tests for mcoi_runtime.contracts.decision_learning — decision learning contracts."""

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


# ---------------------------------------------------------------------------
# DecisionOutcomeRecord
# ---------------------------------------------------------------------------


class TestDecisionOutcomeRecord:
    def test_valid_outcome(self) -> None:
        r = DecisionOutcomeRecord(
            outcome_id="out-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            actual_cost=500.0,
            actual_duration_seconds=3600.0,
            success_observed=True,
            notes="Completed successfully.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        assert r.quality == OutcomeQuality.SUCCESS
        assert r.success_observed is True

    def test_empty_outcome_id_raises(self) -> None:
        with pytest.raises(ValueError, match="outcome_id"):
            DecisionOutcomeRecord(
                outcome_id="",
                comparison_id="cmp-1",
                chosen_option_id="opt-a",
                quality=OutcomeQuality.FAILURE,
                actual_cost=0.0,
                actual_duration_seconds=0.0,
                success_observed=False,
                notes="Failed.",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_negative_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="actual_cost"):
            DecisionOutcomeRecord(
                outcome_id="out-2",
                comparison_id="cmp-2",
                chosen_option_id="opt-b",
                quality=OutcomeQuality.FAILURE,
                actual_cost=-1.0,
                actual_duration_seconds=0.0,
                success_observed=False,
                notes="Bad cost.",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_nan_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="actual_duration"):
            DecisionOutcomeRecord(
                outcome_id="out-3",
                comparison_id="cmp-3",
                chosen_option_id="opt-c",
                quality=OutcomeQuality.UNKNOWN,
                actual_cost=0.0,
                actual_duration_seconds=float("nan"),
                success_observed=False,
                notes="NaN duration.",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_non_bool_success_raises(self) -> None:
        with pytest.raises(ValueError, match="success_observed"):
            DecisionOutcomeRecord(
                outcome_id="out-4",
                comparison_id="cmp-4",
                chosen_option_id="opt-d",
                quality=OutcomeQuality.SUCCESS,
                actual_cost=0.0,
                actual_duration_seconds=0.0,
                success_observed=1,  # type: ignore[arg-type]
                notes="Not bool.",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_serialization(self) -> None:
        r = DecisionOutcomeRecord(
            outcome_id="out-ser",
            comparison_id="cmp-ser",
            chosen_option_id="opt-ser",
            quality=OutcomeQuality.PARTIAL_SUCCESS,
            actual_cost=100.0,
            actual_duration_seconds=60.0,
            success_observed=False,
            notes="Partial.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        d = r.to_dict()
        assert d["outcome_id"] == "out-ser"
        assert d["quality"] == "partial_success"


# ---------------------------------------------------------------------------
# PreferenceSignal
# ---------------------------------------------------------------------------


class TestPreferenceSignal:
    def test_valid_signal(self) -> None:
        s = PreferenceSignal(
            signal_id="sig-1",
            context_type="goal",
            context_id="goal-1",
            factor_kind="risk",
            direction="strengthen",
            magnitude=0.1,
            reason="Good outcome for risk factor.",
            observed_at="2026-01-01T00:00:00Z",
        )
        assert s.direction == "strengthen"
        assert s.magnitude == 0.1

    def test_invalid_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            PreferenceSignal(
                signal_id="sig-2",
                context_type="goal",
                context_id="goal-2",
                factor_kind="cost",
                direction="neutral",
                magnitude=0.1,
                reason="Bad direction.",
                observed_at="2026-01-01T00:00:00Z",
            )

    def test_magnitude_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="magnitude"):
            PreferenceSignal(
                signal_id="sig-3",
                context_type="goal",
                context_id="goal-3",
                factor_kind="time",
                direction="weaken",
                magnitude=1.5,
                reason="Too big.",
                observed_at="2026-01-01T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# TradeoffOutcome
# ---------------------------------------------------------------------------


class TestTradeoffOutcome:
    def test_valid_tradeoff_outcome(self) -> None:
        t = TradeoffOutcome(
            outcome_id="to-out-1",
            tradeoff_id="to-1",
            chosen_option_id="opt-a",
            quality=OutcomeQuality.SUCCESS,
            regret_score=0.0,
            alternative_would_have_been_better=False,
            explanation="Good choice.",
            assessed_at="2026-01-01T00:00:00Z",
        )
        assert t.regret_score == 0.0
        assert t.alternative_would_have_been_better is False

    def test_regret_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="regret_score"):
            TradeoffOutcome(
                outcome_id="to-out-2",
                tradeoff_id="to-2",
                chosen_option_id="opt-b",
                quality=OutcomeQuality.FAILURE,
                regret_score=1.5,
                alternative_would_have_been_better=True,
                explanation="Bad.",
                assessed_at="2026-01-01T00:00:00Z",
            )

    def test_non_bool_alternative_raises(self) -> None:
        with pytest.raises(ValueError, match="alternative_would_have_been_better"):
            TradeoffOutcome(
                outcome_id="to-out-3",
                tradeoff_id="to-3",
                chosen_option_id="opt-c",
                quality=OutcomeQuality.UNKNOWN,
                regret_score=0.5,
                alternative_would_have_been_better=0,  # type: ignore[arg-type]
                explanation="Not bool.",
                assessed_at="2026-01-01T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# DecisionAdjustment
# ---------------------------------------------------------------------------


class TestDecisionAdjustment:
    def test_valid_adjustment(self) -> None:
        a = DecisionAdjustment(
            adjustment_id="adj-1",
            adjustment_type=AdjustmentType.WEIGHT_INCREASE,
            target_factor_kind="risk",
            old_value=0.3,
            new_value=0.35,
            delta=0.05,
            reason="Strengthen risk factor after success.",
            created_at="2026-01-01T00:00:00Z",
        )
        assert a.delta == 0.05
        assert a.adjustment_type == AdjustmentType.WEIGHT_INCREASE

    def test_negative_delta_allowed(self) -> None:
        """Delta can be negative for weight decreases."""
        a = DecisionAdjustment(
            adjustment_id="adj-2",
            adjustment_type=AdjustmentType.WEIGHT_DECREASE,
            target_factor_kind="cost",
            old_value=0.5,
            new_value=0.45,
            delta=-0.05,
            reason="Weaken cost factor after failure.",
            created_at="2026-01-01T00:00:00Z",
        )
        assert a.delta == -0.05

    def test_nan_delta_raises(self) -> None:
        with pytest.raises(ValueError, match="delta"):
            DecisionAdjustment(
                adjustment_id="adj-3",
                adjustment_type=AdjustmentType.CALIBRATION,
                target_factor_kind="time",
                old_value=0.5,
                new_value=0.5,
                delta=float("nan"),
                reason="NaN delta.",
                created_at="2026-01-01T00:00:00Z",
            )

    def test_all_adjustment_types(self) -> None:
        for at in AdjustmentType:
            a = DecisionAdjustment(
                adjustment_id=f"adj-{at.value}",
                adjustment_type=at,
                target_factor_kind="risk",
                old_value=0.5,
                new_value=0.5,
                delta=0.0,
                reason=f"Test {at.value}.",
                created_at="2026-01-01T00:00:00Z",
            )
            assert a.adjustment_type == at


# ---------------------------------------------------------------------------
# UtilityLearningRecord
# ---------------------------------------------------------------------------


def _make_outcome() -> DecisionOutcomeRecord:
    return DecisionOutcomeRecord(
        outcome_id="out-lr",
        comparison_id="cmp-lr",
        chosen_option_id="opt-lr",
        quality=OutcomeQuality.SUCCESS,
        actual_cost=100.0,
        actual_duration_seconds=60.0,
        success_observed=True,
        notes="OK.",
        recorded_at="2026-01-01T00:00:00Z",
    )


class TestUtilityLearningRecord:
    def test_valid_record(self) -> None:
        lr = UtilityLearningRecord(
            record_id="lr-1",
            comparison_id="cmp-1",
            outcome=_make_outcome(),
            signals=(),
            adjustments=(),
            learned_at="2026-01-01T00:00:00Z",
        )
        assert lr.record_id == "lr-1"

    def test_wrong_outcome_type_raises(self) -> None:
        with pytest.raises(ValueError, match="outcome"):
            UtilityLearningRecord(
                record_id="lr-2",
                comparison_id="cmp-2",
                outcome="not-an-outcome",  # type: ignore[arg-type]
                signals=(),
                adjustments=(),
                learned_at="2026-01-01T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# ProviderPreference
# ---------------------------------------------------------------------------


class TestProviderPreference:
    def test_valid_preference(self) -> None:
        p = ProviderPreference(
            preference_id="pref-1",
            provider_id="openai",
            context_type="goal",
            score=0.85,
            sample_count=10,
            last_updated="2026-01-01T00:00:00Z",
        )
        assert p.score == 0.85
        assert p.sample_count == 10

    def test_negative_sample_count_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_count"):
            ProviderPreference(
                preference_id="pref-2",
                provider_id="anthropic",
                context_type="skill",
                score=0.5,
                sample_count=-1,
                last_updated="2026-01-01T00:00:00Z",
            )

    def test_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="score"):
            ProviderPreference(
                preference_id="pref-3",
                provider_id="google",
                context_type="workflow",
                score=1.5,
                sample_count=0,
                last_updated="2026-01-01T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_outcome_quality(self) -> None:
        assert len(OutcomeQuality) == 4

    def test_adjustment_type(self) -> None:
        assert len(AdjustmentType) == 6


# ---------------------------------------------------------------------------
# Audit hardening (Phase 29 audit pass)
# ---------------------------------------------------------------------------


def _valid_outcome() -> DecisionOutcomeRecord:
    return DecisionOutcomeRecord(
        outcome_id="out-h",
        comparison_id="cmp-h",
        chosen_option_id="opt-h",
        quality=OutcomeQuality.SUCCESS,
        actual_cost=10.0,
        actual_duration_seconds=60.0,
        success_observed=True,
        notes="hardening",
        recorded_at="2026-01-01T00:00:00Z",
    )


def _valid_signal() -> PreferenceSignal:
    return PreferenceSignal(
        signal_id="sig-h",
        context_type="test",
        context_id="ctx-h",
        factor_kind="risk",
        direction="strengthen",
        magnitude=0.1,
        reason="hardening signal",
        observed_at="2026-01-01T00:00:00Z",
    )


def _valid_adjustment() -> DecisionAdjustment:
    return DecisionAdjustment(
        adjustment_id="adj-h",
        adjustment_type=AdjustmentType.WEIGHT_INCREASE,
        target_factor_kind="risk",
        old_value=0.4,
        new_value=0.45,
        delta=0.05,
        reason="hardening adj",
        created_at="2026-01-01T00:00:00Z",
    )


class TestAuditHardening:
    """Audit-driven hardening tests for Phase 29 contract gaps."""

    # D1: adjustment old_value / new_value out of range
    def test_adjustment_old_value_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="old_value"):
            DecisionAdjustment(
                adjustment_id="adj-bad",
                adjustment_type=AdjustmentType.WEIGHT_INCREASE,
                target_factor_kind="risk",
                old_value=-0.1,
                new_value=0.5,
                delta=0.6,
                reason="bad old",
                created_at="2026-01-01T00:00:00Z",
            )

    def test_adjustment_new_value_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="new_value"):
            DecisionAdjustment(
                adjustment_id="adj-bad2",
                adjustment_type=AdjustmentType.WEIGHT_DECREASE,
                target_factor_kind="cost",
                old_value=0.9,
                new_value=1.5,
                delta=0.6,
                reason="bad new",
                created_at="2026-01-01T00:00:00Z",
            )

    def test_adjustment_old_value_nan(self) -> None:
        with pytest.raises(ValueError, match="old_value"):
            DecisionAdjustment(
                adjustment_id="adj-nan",
                adjustment_type=AdjustmentType.WEIGHT_INCREASE,
                target_factor_kind="risk",
                old_value=float("inf"),
                new_value=0.5,
                delta=0.05,
                reason="inf old",
                created_at="2026-01-01T00:00:00Z",
            )

    # D2: UtilityLearningRecord with actual signals and adjustments
    def test_learning_record_with_signals_and_adjustments(self) -> None:
        rec = UtilityLearningRecord(
            record_id="lr-full",
            comparison_id="cmp-full",
            outcome=_valid_outcome(),
            signals=(_valid_signal(),),
            adjustments=(_valid_adjustment(),),
            learned_at="2026-01-01T00:00:00Z",
        )
        assert len(rec.signals) == 1
        assert len(rec.adjustments) == 1

    # B1: UtilityLearningRecord rejects bad signal types
    def test_learning_record_rejects_bad_signal_type(self) -> None:
        with pytest.raises(ValueError, match="signals"):
            UtilityLearningRecord(
                record_id="lr-bad",
                comparison_id="cmp-bad",
                outcome=_valid_outcome(),
                signals=("not-a-signal",),  # type: ignore[arg-type]
                adjustments=(),
                learned_at="2026-01-01T00:00:00Z",
            )

    def test_learning_record_rejects_bad_adjustment_type(self) -> None:
        with pytest.raises(ValueError, match="adjustments"):
            UtilityLearningRecord(
                record_id="lr-bad2",
                comparison_id="cmp-bad2",
                outcome=_valid_outcome(),
                signals=(),
                adjustments=("not-an-adj",),  # type: ignore[arg-type]
                learned_at="2026-01-01T00:00:00Z",
            )

    # D3: string quality instead of enum
    def test_outcome_string_quality_raises(self) -> None:
        with pytest.raises(ValueError, match="quality"):
            DecisionOutcomeRecord(
                outcome_id="out-sq",
                comparison_id="cmp-sq",
                chosen_option_id="opt-sq",
                quality="success",  # type: ignore[arg-type]
                actual_cost=0.0,
                actual_duration_seconds=0.0,
                success_observed=True,
                notes="string quality",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_tradeoff_string_quality_raises(self) -> None:
        with pytest.raises(ValueError, match="quality"):
            TradeoffOutcome(
                outcome_id="to-sq",
                tradeoff_id="t-sq",
                chosen_option_id="opt-sq",
                quality="failure",  # type: ignore[arg-type]
                regret_score=0.5,
                alternative_would_have_been_better=False,
                explanation="string quality",
                assessed_at="2026-01-01T00:00:00Z",
            )

    def test_adjustment_string_type_raises(self) -> None:
        with pytest.raises(ValueError, match="adjustment_type"):
            DecisionAdjustment(
                adjustment_id="adj-st",
                adjustment_type="weight_increase",  # type: ignore[arg-type]
                target_factor_kind="risk",
                old_value=0.4,
                new_value=0.45,
                delta=0.05,
                reason="string type",
                created_at="2026-01-01T00:00:00Z",
            )

    # D4: empty notes raises
    def test_empty_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="notes"):
            DecisionOutcomeRecord(
                outcome_id="out-en",
                comparison_id="cmp-en",
                chosen_option_id="opt-en",
                quality=OutcomeQuality.SUCCESS,
                actual_cost=0.0,
                actual_duration_seconds=0.0,
                success_observed=True,
                notes="",
                recorded_at="2026-01-01T00:00:00Z",
            )
