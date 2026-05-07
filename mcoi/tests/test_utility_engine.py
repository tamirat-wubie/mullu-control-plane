"""Tests for mcoi_runtime.core.utility — utility scoring engine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationOption,
    SimulationVerdict,
    VerdictType,
)
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
from mcoi_runtime.core.utility import UtilityEngine


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


def _make_engine() -> UtilityEngine:
    _reset_clock()
    return UtilityEngine(clock=_clock)


def _make_option(
    option_id: str,
    *,
    risk: RiskLevel = RiskLevel.LOW,
    cost: float = 1000.0,
    duration: float = 3600.0,
    success: float = 0.8,
) -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label=f"Option {option_id}",
        risk_level=risk,
        estimated_cost=cost,
        estimated_duration_seconds=duration,
        success_probability=success,
    )


def _make_profile(
    *,
    tradeoff: TradeoffDirection = TradeoffDirection.BALANCED,
    factors: tuple[DecisionFactor, ...] | None = None,
) -> UtilityProfile:
    if factors is None:
        factors = (
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
                weight=0.3,
                value=1.0,
                label="Confidence",
            ),
            DecisionFactor(
                factor_id="f-cost",
                kind=DecisionFactorKind.COST,
                weight=0.2,
                value=1.0,
                label="Cost",
            ),
            DecisionFactor(
                factor_id="f-time",
                kind=DecisionFactorKind.TIME,
                weight=0.2,
                value=1.0,
                label="Time",
            ),
        )
    return UtilityProfile(
        profile_id="profile-test",
        context_type="goal",
        context_id="goal-1",
        factors=factors,
        tradeoff_direction=tradeoff,
        created_at="2026-01-01T00:00:00Z",
    )


def _make_policy(
    *,
    min_confidence: float = 0.5,
    max_risk_tolerance: float = 0.7,
    max_cost: float = 5000.0,
    require_human_above_risk: float = 0.8,
) -> DecisionPolicy:
    return DecisionPolicy(
        policy_id="pol-test",
        name="Test policy",
        min_confidence=min_confidence,
        max_risk_tolerance=max_risk_tolerance,
        max_cost=max_cost,
        deadline_weight=0.5,
        require_human_above_risk=require_human_above_risk,
    )


# ---------------------------------------------------------------------------
# score_options
# ---------------------------------------------------------------------------


class TestScoreOptions:
    def test_single_option(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        option = _make_option("opt-a", risk=RiskLevel.LOW, success=0.8, cost=1000.0, duration=3600.0)
        result = engine.score_options(profile, (option,))
        assert len(result) == 1
        assert result[0].option_id == "opt-a"
        assert result[0].rank == 1
        assert 0.0 <= result[0].weighted_score <= 1.0

    def test_empty_options_returns_empty(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        result = engine.score_options(profile, ())
        assert result == ()

    def test_higher_success_ranks_higher(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opt_good = _make_option("opt-good", success=0.95, risk=RiskLevel.LOW, cost=500.0)
        opt_bad = _make_option("opt-bad", success=0.3, risk=RiskLevel.LOW, cost=500.0)
        result = engine.score_options(profile, (opt_bad, opt_good))
        assert result[0].option_id == "opt-good"
        assert result[0].rank == 1
        assert result[1].option_id == "opt-bad"
        assert result[1].rank == 2
        assert result[0].weighted_score > result[1].weighted_score

    def test_lower_risk_ranks_higher(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opt_safe = _make_option("opt-safe", risk=RiskLevel.MINIMAL, success=0.8)
        opt_risky = _make_option("opt-risky", risk=RiskLevel.HIGH, success=0.8)
        result = engine.score_options(profile, (opt_risky, opt_safe))
        assert result[0].option_id == "opt-safe"
        assert result[0].weighted_score > result[1].weighted_score

    def test_cheaper_ranks_higher_all_else_equal(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opt_cheap = _make_option("opt-cheap", cost=100.0, risk=RiskLevel.LOW, success=0.8)
        opt_expensive = _make_option("opt-expensive", cost=9000.0, risk=RiskLevel.LOW, success=0.8)
        result = engine.score_options(profile, (opt_expensive, opt_cheap))
        assert result[0].option_id == "opt-cheap"

    def test_faster_ranks_higher_all_else_equal(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opt_fast = _make_option("opt-fast", duration=100.0, risk=RiskLevel.LOW, success=0.8, cost=1000.0)
        opt_slow = _make_option("opt-slow", duration=80000.0, risk=RiskLevel.LOW, success=0.8, cost=1000.0)
        result = engine.score_options(profile, (opt_slow, opt_fast))
        assert result[0].option_id == "opt-fast"

    def test_tiebreak_on_option_id(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opt_a = _make_option("aaa", risk=RiskLevel.LOW, success=0.8, cost=1000.0, duration=3600.0)
        opt_b = _make_option("bbb", risk=RiskLevel.LOW, success=0.8, cost=1000.0, duration=3600.0)
        result = engine.score_options(profile, (opt_b, opt_a))
        assert result[0].option_id == "aaa"
        assert result[1].option_id == "bbb"

    def test_factor_contributions_populated(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        option = _make_option("opt-x")
        result = engine.score_options(profile, (option,))
        assert len(result[0].factor_contributions) == 4

    def test_scores_clamped_to_unit(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        # Even extreme values should clamp
        opt = _make_option("opt-extreme", risk=RiskLevel.CRITICAL, success=0.0, cost=50000.0, duration=500000.0)
        result = engine.score_options(profile, (opt,))
        assert result[0].raw_score >= 0.0
        assert result[0].weighted_score >= 0.0


# ---------------------------------------------------------------------------
# Tradeoff direction bonuses
# ---------------------------------------------------------------------------


class TestTradeoffBonuses:
    def test_favor_safety_boosts_low_risk(self) -> None:
        engine = _make_engine()
        profile = _make_profile(tradeoff=TradeoffDirection.FAVOR_SAFETY)
        opt_safe = _make_option("safe", risk=RiskLevel.MINIMAL, success=0.7, cost=2000.0)
        opt_risky = _make_option("risky", risk=RiskLevel.HIGH, success=0.7, cost=2000.0)

        # Score with BALANCED for comparison
        profile_balanced = _make_profile(tradeoff=TradeoffDirection.BALANCED)
        score_balanced = engine.score_options(profile_balanced, (opt_safe,))[0].weighted_score

        score_safety = engine.score_options(profile, (opt_safe,))[0].weighted_score
        # Safety-favored profile should boost the safe option
        assert score_safety >= score_balanced

    def test_balanced_no_bonus(self) -> None:
        engine = _make_engine()
        profile = _make_profile(tradeoff=TradeoffDirection.BALANCED)
        opt = _make_option("opt-1", risk=RiskLevel.LOW, success=0.8)
        result = engine.score_options(profile, (opt,))
        # No bonus applied — just pure weighted scoring
        assert 0.0 <= result[0].weighted_score <= 1.0


# ---------------------------------------------------------------------------
# compare_options
# ---------------------------------------------------------------------------


class TestCompareOptions:
    def test_basic_comparison(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (
            _make_option("opt-a", success=0.9, risk=RiskLevel.LOW),
            _make_option("opt-b", success=0.5, risk=RiskLevel.HIGH),
        )
        comparison = engine.compare_options(profile, opts)
        assert isinstance(comparison, DecisionComparison)
        assert comparison.best_option_id == "opt-a"
        assert comparison.spread >= 0.0
        assert len(comparison.option_utilities) == 2

    def test_single_option_zero_spread(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        comparison = engine.compare_options(profile, (_make_option("only"),))
        assert comparison.spread == 0.0
        assert comparison.best_option_id == "only"

    def test_empty_options_raises(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        with pytest.raises(ValueError, match="at least one option"):
            engine.compare_options(profile, ())

    def test_comparison_id_stable_prefix(self) -> None:
        """Comparison IDs use the utility prefix."""
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a"),)
        c1 = engine.compare_options(profile, opts)
        assert c1.comparison_id.startswith("util-cmp-")


# ---------------------------------------------------------------------------
# check_resource_feasibility
# ---------------------------------------------------------------------------


class TestResourceFeasibility:
    def test_feasible(self) -> None:
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="main-budget",
                resource_type=ResourceType.BUDGET,
                total=10000.0,
                consumed=2000.0,
                reserved=1000.0,
            ),
        )
        feasible, reasons = engine.check_resource_feasibility(budgets, 5000.0)
        assert feasible is True
        assert reasons == ()

    def test_infeasible(self) -> None:
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="tight-budget",
                resource_type=ResourceType.BUDGET,
                total=1000.0,
                consumed=800.0,
                reserved=100.0,
            ),
        )
        feasible, reasons = engine.check_resource_feasibility(budgets, 200.0)
        assert feasible is False
        assert len(reasons) == 1
        assert "tight-budget" in reasons[0]

    def test_non_budget_types_ignored(self) -> None:
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="compute-1",
                resource_type=ResourceType.COMPUTE,
                total=100.0,
                consumed=99.0,
                reserved=0.0,
            ),
        )
        feasible, reasons = engine.check_resource_feasibility(budgets, 9999.0)
        assert feasible is True  # Only BUDGET type checked

    def test_multiple_budgets(self) -> None:
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="budget-ok",
                resource_type=ResourceType.BUDGET,
                total=10000.0,
                consumed=0.0,
                reserved=0.0,
            ),
            ResourceBudget(
                resource_id="budget-tight",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=90.0,
                reserved=5.0,
            ),
        )
        feasible, reasons = engine.check_resource_feasibility(budgets, 50.0)
        assert feasible is False
        assert len(reasons) == 1
        assert "budget-tight" in reasons[0]

    def test_exact_remaining(self) -> None:
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="exact",
                resource_type=ResourceType.BUDGET,
                total=1000.0,
                consumed=500.0,
                reserved=200.0,
            ),
        )
        # remaining = 300.0, cost = 300.0 — exactly feasible
        feasible, reasons = engine.check_resource_feasibility(budgets, 300.0)
        assert feasible is True


# ---------------------------------------------------------------------------
# apply_policy
# ---------------------------------------------------------------------------


class TestApplyPolicy:
    def test_approved_when_all_pass(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", success=0.9, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy(min_confidence=0.5)
        verdict = engine.apply_policy(comparison, policy)
        assert isinstance(verdict, UtilityVerdict)
        assert verdict.approved is True
        assert verdict.recommended_option_id == "opt-a"

    def test_rejected_low_confidence(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        # Very bad option — low score
        opts = (_make_option("opt-bad", success=0.1, risk=RiskLevel.HIGH, cost=9000.0, duration=80000.0),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy(min_confidence=0.9)
        verdict = engine.apply_policy(comparison, policy)
        assert verdict.approved is False
        assert any("min_confidence" in r for r in verdict.reasons)

    def test_rejected_high_risk_with_simulation_verdict(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", success=0.8, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy(max_risk_tolerance=0.1)
        sim_verdict = SimulationVerdict(
            verdict_id="sv-1",
            comparison_id="sim-cmp-1",
            verdict_type=VerdictType.ESCALATE,
            recommended_option_id="opt-a",
            confidence=0.2,  # low confidence => high risk proxy (0.8)
            reasons=("high risk",),
        )
        verdict = engine.apply_policy(comparison, policy, sim_verdict)
        assert verdict.approved is False
        assert any("risk" in r.lower() for r in verdict.reasons)

    def test_no_simulation_verdict_ok(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", success=0.9, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy()
        verdict = engine.apply_policy(comparison, policy, None)
        assert verdict.approved is True


# ---------------------------------------------------------------------------
# full_utility_analysis
# ---------------------------------------------------------------------------


class TestFullUtilityAnalysis:
    def test_full_analysis_basic(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (
            _make_option("opt-a", success=0.9, risk=RiskLevel.LOW, cost=500.0),
            _make_option("opt-b", success=0.5, risk=RiskLevel.HIGH, cost=3000.0),
        )
        policy = _make_policy()
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
        )
        assert isinstance(comparison, DecisionComparison)
        assert isinstance(verdict, UtilityVerdict)
        assert isinstance(tradeoff, TradeoffRecord)
        assert comparison.best_option_id == tradeoff.chosen_option_id
        assert "opt-b" in tradeoff.rejected_option_ids

    def test_full_analysis_with_budgets_feasible(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", cost=500.0, success=0.9, risk=RiskLevel.LOW),)
        policy = _make_policy()
        budgets = (
            ResourceBudget(
                resource_id="b-1",
                resource_type=ResourceType.BUDGET,
                total=10000.0,
                consumed=0.0,
                reserved=0.0,
            ),
        )
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
            budgets=budgets,
        )
        assert verdict.approved is True
        assert tradeoff.rationale == "tradeoff recorded with approved verdict"

    def test_full_analysis_budget_overrun(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", cost=5000.0, success=0.9, risk=RiskLevel.LOW),)
        policy = _make_policy()
        budgets = (
            ResourceBudget(
                resource_id="tight",
                resource_type=ResourceType.BUDGET,
                total=1000.0,
                consumed=500.0,
                reserved=400.0,
            ),
        )
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
            budgets=budgets,
        )
        assert verdict.approved is False
        assert any("budget" in r.lower() for r in verdict.reasons)
        assert tradeoff.rationale == (
            "tradeoff recorded with budget constraints and rejected verdict"
        )
        assert "opt-a" not in tradeoff.rationale
        assert "5000" not in tradeoff.rationale

    def test_full_analysis_empty_options_raises(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        policy = _make_policy()
        with pytest.raises(ValueError, match="at least one option"):
            engine.full_utility_analysis(profile=profile, options=(), policy=policy)

    def test_full_analysis_with_simulation_verdict(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", success=0.9, risk=RiskLevel.LOW),)
        policy = _make_policy()
        sim_verdict = SimulationVerdict(
            verdict_id="sv-1",
            comparison_id="sim-cmp-1",
            verdict_type=VerdictType.PROCEED,
            recommended_option_id="opt-a",
            confidence=0.9,
            reasons=("good",),
        )
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
            simulation_verdict=sim_verdict,
        )
        assert verdict.approved is True

    def test_tradeoff_direction_reflected(self) -> None:
        engine = _make_engine()
        profile = _make_profile(tradeoff=TradeoffDirection.FAVOR_COST)
        opts = (
            _make_option("opt-cheap", cost=100.0, success=0.7, risk=RiskLevel.LOW),
            _make_option("opt-costly", cost=8000.0, success=0.7, risk=RiskLevel.LOW),
        )
        policy = _make_policy()
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
        )
        assert tradeoff.tradeoff_direction == TradeoffDirection.FAVOR_COST

    def test_single_option_no_rejected(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("only-one", success=0.9, risk=RiskLevel.LOW),)
        policy = _make_policy()
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
        )
        assert tradeoff.rejected_option_ids == ()
        assert tradeoff.chosen_option_id == "only-one"


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    """End-to-end scenarios testing real decision-making patterns."""

    def test_three_workflow_options_for_goal(self) -> None:
        """A goal with three workflow options: fast+risky, balanced, slow+safe."""
        engine = _make_engine()
        profile = _make_profile(tradeoff=TradeoffDirection.BALANCED)

        opts = (
            _make_option("fast-risky", risk=RiskLevel.HIGH, success=0.7, cost=2000.0, duration=600.0),
            _make_option("balanced", risk=RiskLevel.MODERATE, success=0.8, cost=3000.0, duration=3600.0),
            _make_option("slow-safe", risk=RiskLevel.MINIMAL, success=0.9, cost=5000.0, duration=43200.0),
        )
        policy = _make_policy()
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
        )
        # With balanced profile, the "balanced" or "slow-safe" option should win
        assert comparison.best_option_id in ("balanced", "slow-safe")
        assert verdict.approved is True
        assert len(tradeoff.rejected_option_ids) == 2

    def test_budget_constrained_choice(self) -> None:
        """When budget is tight, the cheaper option should be chosen even if slightly worse."""
        engine = _make_engine()
        profile = _make_profile(tradeoff=TradeoffDirection.FAVOR_COST)

        opts = (
            _make_option("premium", risk=RiskLevel.MINIMAL, success=0.95, cost=8000.0),
            _make_option("basic", risk=RiskLevel.LOW, success=0.8, cost=500.0),
        )
        budgets = (
            ResourceBudget(
                resource_id="monthly",
                resource_type=ResourceType.BUDGET,
                total=5000.0,
                consumed=3000.0,
                reserved=500.0,
            ),
        )
        policy = _make_policy()
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
            budgets=budgets,
        )
        # Premium exceeds budget, basic should be feasible
        # The utility engine picks the best option first; if it's infeasible, verdict is denied
        # But basic ranks higher due to cost efficiency + FAVOR_COST bonus
        assert comparison.best_option_id == "basic"

    def test_high_risk_requires_human(self) -> None:
        """Simulation reports high risk — utility should deny auto-approval."""
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("risky-action", risk=RiskLevel.CRITICAL, success=0.3),)
        policy = _make_policy(min_confidence=0.5, max_risk_tolerance=0.3)
        sim_verdict = SimulationVerdict(
            verdict_id="sv-risky",
            comparison_id="sim-cmp-risky",
            verdict_type=VerdictType.ESCALATE,
            recommended_option_id="risky-action",
            confidence=0.1,
            reasons=("critical risk",),
        )
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
            simulation_verdict=sim_verdict,
        )
        assert verdict.approved is False


# ---------------------------------------------------------------------------
# Audit hardening tests
# ---------------------------------------------------------------------------


class TestAuditHardening:
    """Tests added from audit pass — edge cases and invariant guards."""

    def test_max_cost_enforcement(self) -> None:
        """apply_policy enforces max_cost when best_option_cost is provided."""
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("expensive", cost=8000.0, success=0.9, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy(max_cost=5000.0)
        verdict = engine.apply_policy(comparison, policy, best_option_cost=8000.0)
        assert verdict.approved is False
        assert any("max_cost" in r for r in verdict.reasons)

    def test_max_cost_within_limit_approved(self) -> None:
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("cheap", cost=500.0, success=0.9, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy(max_cost=5000.0)
        verdict = engine.apply_policy(comparison, policy, best_option_cost=500.0)
        assert verdict.approved is True

    def test_no_simulation_verdict_reason_text(self) -> None:
        """Without simulation verdict, reason should note constraints were not fully evaluated."""
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("opt-a", success=0.9, risk=RiskLevel.LOW),)
        comparison = engine.compare_options(profile, opts)
        policy = _make_policy()
        verdict = engine.apply_policy(comparison, policy, None)
        assert verdict.approved is True
        assert any("no simulation verdict" in r for r in verdict.reasons)

    def test_full_analysis_enforces_max_cost(self) -> None:
        """full_utility_analysis passes cost to apply_policy for max_cost check."""
        engine = _make_engine()
        profile = _make_profile()
        opts = (_make_option("costly", cost=9000.0, success=0.9, risk=RiskLevel.LOW),)
        policy = _make_policy(max_cost=1000.0)
        comparison, verdict, tradeoff = engine.full_utility_analysis(
            profile=profile,
            options=opts,
            policy=policy,
        )
        assert verdict.approved is False
        assert any("max_cost" in r for r in verdict.reasons)

    def test_zero_cost_feasibility(self) -> None:
        """Zero estimated cost should always be feasible."""
        engine = _make_engine()
        budgets = (
            ResourceBudget(
                resource_id="b-1",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=100.0,
                reserved=0.0,
            ),
        )
        feasible, reasons = engine.check_resource_feasibility(budgets, 0.0)
        assert feasible is True

    def test_custom_factor_uses_value_directly(self) -> None:
        """CUSTOM, OBLIGATION, PROVIDER_HEALTH, DEADLINE_PRESSURE factors use factor.value."""
        engine = _make_engine()
        factors = (
            DecisionFactor(
                factor_id="f-custom",
                kind=DecisionFactorKind.CUSTOM,
                weight=1.0,
                value=0.7,
                label="Custom factor",
            ),
        )
        profile = _make_profile(factors=factors)
        opt = _make_option("opt-x", risk=RiskLevel.LOW, success=0.8, cost=1000.0)
        result = engine.score_options(profile, (opt,))
        assert result[0].factor_contributions["f-custom"] == 0.7
