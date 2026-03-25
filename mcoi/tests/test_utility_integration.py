"""Tests for mcoi_runtime.core.utility_integration — utility bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.graph import NodeType
from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationOption,
)
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionPolicy,
    ResourceBudget,
    ResourceType,
    TradeoffDirection,
    TradeoffRecord,
    UtilityVerdict,
)
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.utility import UtilityEngine
from mcoi_runtime.core.utility_integration import UtilityBridge


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


def _make_graph() -> OperationalGraph:
    _reset_clock()
    g = OperationalGraph(clock=_clock)
    g.ensure_node("goal-1", NodeType.GOAL, "Test goal")
    return g


def _make_option(
    option_id: str,
    *,
    risk: RiskLevel = RiskLevel.LOW,
    cost: float = 1000.0,
    success: float = 0.8,
) -> SimulationOption:
    return SimulationOption(
        option_id=option_id,
        label=f"Option {option_id}",
        risk_level=risk,
        estimated_cost=cost,
        estimated_duration_seconds=3600.0,
        success_probability=success,
    )


def _make_policy() -> DecisionPolicy:
    return DecisionPolicy(
        policy_id="pol-int",
        name="Integration policy",
        min_confidence=0.5,
        max_risk_tolerance=0.7,
        max_cost=5000.0,
        deadline_weight=0.5,
        require_human_above_risk=0.8,
    )


# ---------------------------------------------------------------------------
# build_default_profile
# ---------------------------------------------------------------------------


class TestBuildDefaultProfile:
    def test_builds_valid_profile(self) -> None:
        profile = UtilityBridge.build_default_profile(
            "goal", "goal-1",
            clock_now="2026-01-01T00:00:00Z",
        )
        assert profile.context_type == "goal"
        assert profile.context_id == "goal-1"
        assert len(profile.factors) == 4
        assert profile.tradeoff_direction == TradeoffDirection.BALANCED

    def test_custom_tradeoff(self) -> None:
        profile = UtilityBridge.build_default_profile(
            "incident", "inc-1",
            tradeoff=TradeoffDirection.FAVOR_SAFETY,
            clock_now="2026-01-01T00:00:00Z",
        )
        assert profile.tradeoff_direction == TradeoffDirection.FAVOR_SAFETY

    def test_custom_weights(self) -> None:
        profile = UtilityBridge.build_default_profile(
            "goal", "goal-2",
            risk_weight=0.5,
            confidence_weight=0.5,
            cost_weight=0.0,
            time_weight=0.0,
            clock_now="2026-01-01T00:00:00Z",
        )
        weights = [f.weight for f in profile.factors]
        assert weights == [0.5, 0.5, 0.0, 0.0]


# ---------------------------------------------------------------------------
# utility_enhanced_simulation
# ---------------------------------------------------------------------------


class TestUtilityEnhancedSimulation:
    def test_full_pipeline(self) -> None:
        _reset_clock()
        graph = _make_graph()
        sim_engine = SimulationEngine(graph=graph, clock=_clock)
        util_engine = UtilityEngine(clock=_clock)
        policy = _make_policy()

        options = (
            _make_option("opt-a", success=0.9, risk=RiskLevel.LOW, cost=500.0),
            _make_option("opt-b", success=0.5, risk=RiskLevel.HIGH, cost=3000.0),
        )

        sim_cmp, sim_verdict, util_cmp, util_verdict, tradeoff = (
            UtilityBridge.utility_enhanced_simulation(
                simulation_engine=sim_engine,
                utility_engine=util_engine,
                options=options,
                context_type="goal",
                context_id="goal-1",
                policy=policy,
            )
        )

        assert sim_cmp is not None
        assert sim_verdict is not None
        assert isinstance(util_cmp, DecisionComparison)
        assert isinstance(util_verdict, UtilityVerdict)
        assert isinstance(tradeoff, TradeoffRecord)

    def test_with_budgets(self) -> None:
        _reset_clock()
        graph = _make_graph()
        sim_engine = SimulationEngine(graph=graph, clock=_clock)
        util_engine = UtilityEngine(clock=_clock)
        policy = _make_policy()
        budgets = (
            ResourceBudget(
                resource_id="main",
                resource_type=ResourceType.BUDGET,
                total=2000.0,
                consumed=0.0,
                reserved=0.0,
            ),
        )

        options = (
            _make_option("opt-a", cost=500.0, success=0.8, risk=RiskLevel.LOW),
        )

        _, _, _, verdict, _ = UtilityBridge.utility_enhanced_simulation(
            simulation_engine=sim_engine,
            utility_engine=util_engine,
            options=options,
            context_type="goal",
            context_id="goal-1",
            policy=policy,
            budgets=budgets,
        )
        assert verdict.approved is True

    def test_budget_overrun_denies(self) -> None:
        _reset_clock()
        graph = _make_graph()
        sim_engine = SimulationEngine(graph=graph, clock=_clock)
        util_engine = UtilityEngine(clock=_clock)
        policy = _make_policy()
        budgets = (
            ResourceBudget(
                resource_id="tiny",
                resource_type=ResourceType.BUDGET,
                total=100.0,
                consumed=90.0,
                reserved=5.0,
            ),
        )

        options = (
            _make_option("opt-expensive", cost=5000.0, success=0.9, risk=RiskLevel.LOW),
        )

        _, _, _, verdict, _ = UtilityBridge.utility_enhanced_simulation(
            simulation_engine=sim_engine,
            utility_engine=util_engine,
            options=options,
            context_type="goal",
            context_id="goal-1",
            policy=policy,
            budgets=budgets,
        )
        assert verdict.approved is False


# ---------------------------------------------------------------------------
# evaluate_resource_feasibility
# ---------------------------------------------------------------------------


class TestEvaluateResourceFeasibility:
    def test_all_feasible(self) -> None:
        _reset_clock()
        util_engine = UtilityEngine(clock=_clock)
        budgets = (
            ResourceBudget(
                resource_id="b-1",
                resource_type=ResourceType.BUDGET,
                total=10000.0,
                consumed=0.0,
                reserved=0.0,
            ),
        )
        options = (
            _make_option("opt-a", cost=500.0),
            _make_option("opt-b", cost=1000.0),
        )
        result = UtilityBridge.evaluate_resource_feasibility(util_engine, budgets, options)
        assert result["opt-a"][0] is True
        assert result["opt-b"][0] is True

    def test_one_infeasible(self) -> None:
        _reset_clock()
        util_engine = UtilityEngine(clock=_clock)
        budgets = (
            ResourceBudget(
                resource_id="b-1",
                resource_type=ResourceType.BUDGET,
                total=1000.0,
                consumed=500.0,
                reserved=200.0,
            ),
        )
        options = (
            _make_option("opt-cheap", cost=200.0),
            _make_option("opt-expensive", cost=5000.0),
        )
        result = UtilityBridge.evaluate_resource_feasibility(util_engine, budgets, options)
        assert result["opt-cheap"][0] is True
        assert result["opt-expensive"][0] is False
