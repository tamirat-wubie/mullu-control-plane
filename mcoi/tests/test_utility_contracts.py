"""Tests for mcoi_runtime.contracts.utility — utility/resource reasoning contracts."""

from __future__ import annotations

import math
import pytest

from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    DecisionPolicy,
    OptionUtility,
    ResourceBudget,
    ResourceType,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
    UtilityVerdict,
)


# ---------------------------------------------------------------------------
# ResourceBudget
# ---------------------------------------------------------------------------


class TestResourceBudget:
    def test_valid_budget(self) -> None:
        b = ResourceBudget(
            resource_id="budget-1",
            resource_type=ResourceType.BUDGET,
            total=1000.0,
            consumed=400.0,
            reserved=200.0,
        )
        assert b.total == 1000.0
        assert b.consumed == 400.0
        assert b.reserved == 200.0

    def test_exact_limit(self) -> None:
        b = ResourceBudget(
            resource_id="b-2",
            resource_type=ResourceType.COMPUTE,
            total=100.0,
            consumed=60.0,
            reserved=40.0,
        )
        assert b.consumed + b.reserved == b.total

    def test_over_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="consumed.*reserved.*exceed.*total"):
            ResourceBudget(
                resource_id="b-3",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=80.0,
                reserved=30.0,
            )

    def test_negative_total_raises(self) -> None:
        with pytest.raises(ValueError, match="total"):
            ResourceBudget(
                resource_id="b-4",
                resource_type=ResourceType.BUDGET,
                total=-1.0,
                consumed=0.0,
                reserved=0.0,
            )

    def test_nan_consumed_raises(self) -> None:
        with pytest.raises(ValueError, match="consumed"):
            ResourceBudget(
                resource_id="b-5",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=float("nan"),
                reserved=0.0,
            )

    def test_inf_reserved_raises(self) -> None:
        with pytest.raises(ValueError, match="reserved"):
            ResourceBudget(
                resource_id="b-6",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=0.0,
                reserved=float("inf"),
            )

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="resource_id"):
            ResourceBudget(
                resource_id="",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=0.0,
                reserved=0.0,
            )

    def test_all_resource_types(self) -> None:
        for rt in ResourceType:
            b = ResourceBudget(
                resource_id=f"b-{rt.value}",
                resource_type=rt,
                total=100.0,
                consumed=0.0,
                reserved=0.0,
            )
            assert b.resource_type == rt

    def test_serialization(self) -> None:
        b = ResourceBudget(
            resource_id="b-ser",
            resource_type=ResourceType.API_CALLS,
            total=500.0,
            consumed=100.0,
            reserved=50.0,
        )
        d = b.to_dict()
        assert d["resource_id"] == "b-ser"
        assert d["total"] == 500.0


# ---------------------------------------------------------------------------
# DecisionFactor
# ---------------------------------------------------------------------------


class TestDecisionFactor:
    def test_valid_factor(self) -> None:
        f = DecisionFactor(
            factor_id="f-1",
            kind=DecisionFactorKind.RISK,
            weight=0.5,
            value=0.8,
            label="Risk factor",
        )
        assert f.weight == 0.5
        assert f.value == 0.8

    def test_weight_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            DecisionFactor(
                factor_id="f-2",
                kind=DecisionFactorKind.COST,
                weight=1.5,
                value=0.5,
                label="Too heavy",
            )

    def test_value_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="value"):
            DecisionFactor(
                factor_id="f-3",
                kind=DecisionFactorKind.CONFIDENCE,
                weight=0.5,
                value=-0.1,
                label="Negative",
            )

    def test_nan_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            DecisionFactor(
                factor_id="f-4",
                kind=DecisionFactorKind.TIME,
                weight=float("nan"),
                value=0.5,
                label="NaN weight",
            )

    def test_all_factor_kinds(self) -> None:
        for kind in DecisionFactorKind:
            f = DecisionFactor(
                factor_id=f"f-{kind.value}",
                kind=kind,
                weight=0.5,
                value=0.5,
                label=f"Factor {kind.value}",
            )
            assert f.kind == kind

    def test_empty_label_raises(self) -> None:
        with pytest.raises(ValueError, match="label"):
            DecisionFactor(
                factor_id="f-5",
                kind=DecisionFactorKind.CUSTOM,
                weight=0.5,
                value=0.5,
                label="",
            )


# ---------------------------------------------------------------------------
# UtilityProfile
# ---------------------------------------------------------------------------


def _make_factors() -> tuple[DecisionFactor, ...]:
    return (
        DecisionFactor(
            factor_id="f-risk",
            kind=DecisionFactorKind.RISK,
            weight=0.3,
            value=1.0,
            label="Risk",
        ),
        DecisionFactor(
            factor_id="f-conf",
            kind=DecisionFactorKind.CONFIDENCE,
            weight=0.7,
            value=1.0,
            label="Confidence",
        ),
    )


class TestUtilityProfile:
    def test_valid_profile(self) -> None:
        p = UtilityProfile(
            profile_id="p-1",
            context_type="goal",
            context_id="goal-1",
            factors=_make_factors(),
            tradeoff_direction=TradeoffDirection.BALANCED,
            created_at="2026-01-01T00:00:00Z",
        )
        assert len(p.factors) == 2

    def test_empty_factors_raises(self) -> None:
        with pytest.raises(ValueError, match="factors"):
            UtilityProfile(
                profile_id="p-2",
                context_type="goal",
                context_id="goal-2",
                factors=(),
                tradeoff_direction=TradeoffDirection.BALANCED,
                created_at="2026-01-01T00:00:00Z",
            )

    def test_zero_weight_sum_raises(self) -> None:
        with pytest.raises(ValueError, match="weight.*greater than 0"):
            UtilityProfile(
                profile_id="p-3",
                context_type="goal",
                context_id="goal-3",
                factors=(
                    DecisionFactor(
                        factor_id="f-zero",
                        kind=DecisionFactorKind.RISK,
                        weight=0.0,
                        value=1.0,
                        label="Zero weight",
                    ),
                ),
                tradeoff_direction=TradeoffDirection.BALANCED,
                created_at="2026-01-01T00:00:00Z",
            )

    def test_invalid_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="created_at"):
            UtilityProfile(
                profile_id="p-4",
                context_type="goal",
                context_id="goal-4",
                factors=_make_factors(),
                tradeoff_direction=TradeoffDirection.FAVOR_SPEED,
                created_at="not-a-date",
            )


# ---------------------------------------------------------------------------
# OptionUtility
# ---------------------------------------------------------------------------


class TestOptionUtility:
    def test_valid_option_utility(self) -> None:
        ou = OptionUtility(
            option_id="opt-1",
            raw_score=0.7,
            weighted_score=0.8,
            factor_contributions={"risk": 0.6, "confidence": 0.9},
            rank=1,
        )
        assert ou.rank == 1
        assert ou.weighted_score == 0.8

    def test_rank_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="rank"):
            OptionUtility(
                option_id="opt-2",
                raw_score=0.5,
                weighted_score=0.5,
                factor_contributions={},
                rank=0,
            )

    def test_score_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="raw_score"):
            OptionUtility(
                option_id="opt-3",
                raw_score=1.5,
                weighted_score=0.5,
                factor_contributions={},
                rank=1,
            )

    def test_factor_contributions_frozen(self) -> None:
        ou = OptionUtility(
            option_id="opt-4",
            raw_score=0.5,
            weighted_score=0.5,
            factor_contributions={"a": 0.3},
            rank=1,
        )
        with pytest.raises(TypeError):
            ou.factor_contributions["b"] = 0.5  # type: ignore[index]


# ---------------------------------------------------------------------------
# DecisionComparison
# ---------------------------------------------------------------------------


def _make_option_utility(option_id: str, score: float, rank: int) -> OptionUtility:
    return OptionUtility(
        option_id=option_id,
        raw_score=score,
        weighted_score=score,
        factor_contributions={},
        rank=rank,
    )


class TestDecisionComparison:
    def test_valid_comparison(self) -> None:
        dc = DecisionComparison(
            comparison_id="cmp-1",
            profile_id="p-1",
            option_utilities=(
                _make_option_utility("a", 0.9, 1),
                _make_option_utility("b", 0.6, 2),
            ),
            best_option_id="a",
            spread=0.3,
            decided_at="2026-01-01T00:00:00Z",
        )
        assert dc.best_option_id == "a"
        assert dc.spread == 0.3

    def test_empty_options_raises(self) -> None:
        with pytest.raises(ValueError, match="option_utilities"):
            DecisionComparison(
                comparison_id="cmp-2",
                profile_id="p-2",
                option_utilities=(),
                best_option_id="a",
                spread=0.0,
                decided_at="2026-01-01T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# TradeoffRecord
# ---------------------------------------------------------------------------


class TestTradeoffRecord:
    def test_valid_tradeoff(self) -> None:
        tr = TradeoffRecord(
            tradeoff_id="to-1",
            comparison_id="cmp-1",
            chosen_option_id="a",
            rejected_option_ids=("b", "c"),
            tradeoff_direction=TradeoffDirection.FAVOR_SAFETY,
            rationale="Option A has lowest risk with acceptable cost.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        assert tr.chosen_option_id == "a"
        assert len(tr.rejected_option_ids) == 2

    def test_empty_rationale_raises(self) -> None:
        with pytest.raises(ValueError, match="rationale"):
            TradeoffRecord(
                tradeoff_id="to-2",
                comparison_id="cmp-2",
                chosen_option_id="a",
                rejected_option_ids=(),
                tradeoff_direction=TradeoffDirection.BALANCED,
                rationale="",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_empty_rejected_is_ok(self) -> None:
        """Single-option scenarios have no rejected options."""
        tr = TradeoffRecord(
            tradeoff_id="to-3",
            comparison_id="cmp-3",
            chosen_option_id="a",
            rejected_option_ids=(),
            tradeoff_direction=TradeoffDirection.BALANCED,
            rationale="Only one option available.",
            recorded_at="2026-01-01T00:00:00Z",
        )
        assert tr.rejected_option_ids == ()


# ---------------------------------------------------------------------------
# DecisionPolicy
# ---------------------------------------------------------------------------


class TestDecisionPolicy:
    def test_valid_policy(self) -> None:
        dp = DecisionPolicy(
            policy_id="pol-1",
            name="Default policy",
            min_confidence=0.6,
            max_risk_tolerance=0.7,
            max_cost=5000.0,
            deadline_weight=0.5,
            require_human_above_risk=0.8,
        )
        assert dp.min_confidence == 0.6

    def test_min_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="min_confidence"):
            DecisionPolicy(
                policy_id="pol-2",
                name="Bad policy",
                min_confidence=1.5,
                max_risk_tolerance=0.5,
                max_cost=100.0,
                deadline_weight=0.5,
                require_human_above_risk=0.8,
            )

    def test_negative_max_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="max_cost"):
            DecisionPolicy(
                policy_id="pol-3",
                name="Bad cost",
                min_confidence=0.5,
                max_risk_tolerance=0.5,
                max_cost=-1.0,
                deadline_weight=0.5,
                require_human_above_risk=0.8,
            )

    def test_nan_risk_tolerance_raises(self) -> None:
        with pytest.raises(ValueError, match="max_risk_tolerance"):
            DecisionPolicy(
                policy_id="pol-4",
                name="NaN policy",
                min_confidence=0.5,
                max_risk_tolerance=float("nan"),
                max_cost=100.0,
                deadline_weight=0.5,
                require_human_above_risk=0.8,
            )


# ---------------------------------------------------------------------------
# UtilityVerdict
# ---------------------------------------------------------------------------


class TestUtilityVerdict:
    def test_valid_verdict(self) -> None:
        v = UtilityVerdict(
            verdict_id="uv-1",
            comparison_id="cmp-1",
            policy_id="pol-1",
            approved=True,
            recommended_option_id="opt-a",
            confidence=0.85,
            reasons=("Meets all policy constraints.",),
            decided_at="2026-01-01T00:00:00Z",
        )
        assert v.approved is True
        assert v.confidence == 0.85

    def test_non_bool_approved_raises(self) -> None:
        with pytest.raises(ValueError, match="approved"):
            UtilityVerdict(
                verdict_id="uv-2",
                comparison_id="cmp-2",
                policy_id="pol-2",
                approved=1,  # type: ignore[arg-type]
                recommended_option_id="opt-b",
                confidence=0.5,
                reasons=("test",),
                decided_at="2026-01-01T00:00:00Z",
            )

    def test_empty_reasons_raises(self) -> None:
        with pytest.raises(ValueError, match="reasons"):
            UtilityVerdict(
                verdict_id="uv-3",
                comparison_id="cmp-3",
                policy_id="pol-3",
                approved=False,
                recommended_option_id="opt-c",
                confidence=0.5,
                reasons=(),
                decided_at="2026-01-01T00:00:00Z",
            )

    def test_verdict_serialization_roundtrip(self) -> None:
        v = UtilityVerdict(
            verdict_id="uv-4",
            comparison_id="cmp-4",
            policy_id="pol-4",
            approved=False,
            recommended_option_id="opt-d",
            confidence=0.3,
            reasons=("Low confidence.", "High risk."),
            decided_at="2026-01-01T12:00:00Z",
        )
        d = v.to_dict()
        assert d["verdict_id"] == "uv-4"
        assert d["approved"] is False
        assert len(d["reasons"]) == 2
        j = v.to_json()
        assert "uv-4" in j


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_resource_types(self) -> None:
        assert len(ResourceType) == 7

    def test_decision_factor_kinds(self) -> None:
        assert len(DecisionFactorKind) == 8

    def test_tradeoff_directions(self) -> None:
        assert len(TradeoffDirection) == 4


# ---------------------------------------------------------------------------
# Audit hardening tests
# ---------------------------------------------------------------------------


class TestAuditHardening:
    """Tests added from audit pass — edge cases and invariant guards."""

    def test_nan_in_factor_contributions_raises(self) -> None:
        with pytest.raises(ValueError, match="factor_contributions.*finite"):
            OptionUtility(
                option_id="opt-nan",
                raw_score=0.5,
                weighted_score=0.5,
                factor_contributions={"risk": float("nan")},
                rank=1,
            )

    def test_inf_in_factor_contributions_raises(self) -> None:
        with pytest.raises(ValueError, match="factor_contributions.*finite"):
            OptionUtility(
                option_id="opt-inf",
                raw_score=0.5,
                weighted_score=0.5,
                factor_contributions={"risk": float("inf")},
                rank=1,
            )

    def test_best_option_id_not_in_utilities_raises(self) -> None:
        with pytest.raises(ValueError, match="best_option_id"):
            DecisionComparison(
                comparison_id="cmp-bad",
                profile_id="p-1",
                option_utilities=(_make_option_utility("a", 0.9, 1),),
                best_option_id="nonexistent",
                spread=0.0,
                decided_at="2026-01-01T00:00:00Z",
            )

    def test_empty_string_in_rejected_option_ids_raises(self) -> None:
        with pytest.raises(ValueError, match="rejected_option_ids"):
            TradeoffRecord(
                tradeoff_id="to-bad",
                comparison_id="cmp-1",
                chosen_option_id="a",
                rejected_option_ids=("b", ""),
                tradeoff_direction=TradeoffDirection.BALANCED,
                rationale="Some rationale.",
                recorded_at="2026-01-01T00:00:00Z",
            )

    def test_whitespace_in_rejected_option_ids_raises(self) -> None:
        with pytest.raises(ValueError, match="rejected_option_ids"):
            TradeoffRecord(
                tradeoff_id="to-bad2",
                comparison_id="cmp-1",
                chosen_option_id="a",
                rejected_option_ids=("   ",),
                tradeoff_direction=TradeoffDirection.BALANCED,
                rationale="Some rationale.",
                recorded_at="2026-01-01T00:00:00Z",
            )
