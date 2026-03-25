"""Purpose: utility integration bridge — connects utility engine to simulation and graph decisions.
Governance scope: utility invocation for goals, workflows, and resource-constrained decisions.
Dependencies: utility engine, utility contracts, simulation engine, simulation contracts,
    operational graph.
Invariants:
  - Bridge methods are stateless static helpers.
  - Each method builds a UtilityProfile from context, runs utility analysis, returns results.
  - No graph mutation. No side effects beyond scoring.
  - All options must be non-empty tuples.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from mcoi_runtime.contracts.simulation import (
    SimulationComparison,
    SimulationOption,
    SimulationVerdict,
)
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    DecisionPolicy,
    ResourceBudget,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
    UtilityVerdict,
)
from .invariants import stable_identifier
from .simulation import SimulationEngine
from .utility import UtilityEngine


class UtilityBridge:
    """Static methods bridging graph decision points to utility-aware scoring.

    Combines simulation risk analysis with utility scoring to produce
    decisions that are both safe AND optimal.
    """

    @staticmethod
    def build_default_profile(
        context_type: str,
        context_id: str,
        *,
        tradeoff: TradeoffDirection = TradeoffDirection.BALANCED,
        risk_weight: float = 0.3,
        confidence_weight: float = 0.3,
        cost_weight: float = 0.2,
        time_weight: float = 0.2,
        clock_now: str,
    ) -> UtilityProfile:
        """Build a standard utility profile with sensible defaults.

        Provides balanced factor weights that can be tuned per context.
        """
        factors = (
            DecisionFactor(
                factor_id=stable_identifier("factor", {"ctx": context_id, "kind": "risk"}),
                kind=DecisionFactorKind.RISK,
                weight=risk_weight,
                value=1.0,
                label="Risk tolerance",
            ),
            DecisionFactor(
                factor_id=stable_identifier("factor", {"ctx": context_id, "kind": "confidence"}),
                kind=DecisionFactorKind.CONFIDENCE,
                weight=confidence_weight,
                value=1.0,
                label="Success confidence",
            ),
            DecisionFactor(
                factor_id=stable_identifier("factor", {"ctx": context_id, "kind": "cost"}),
                kind=DecisionFactorKind.COST,
                weight=cost_weight,
                value=1.0,
                label="Cost efficiency",
            ),
            DecisionFactor(
                factor_id=stable_identifier("factor", {"ctx": context_id, "kind": "time"}),
                kind=DecisionFactorKind.TIME,
                weight=time_weight,
                value=1.0,
                label="Time efficiency",
            ),
        )
        profile_id = stable_identifier("profile", {
            "context_type": context_type,
            "context_id": context_id,
        })
        return UtilityProfile(
            profile_id=profile_id,
            context_type=context_type,
            context_id=context_id,
            factors=factors,
            tradeoff_direction=tradeoff,
            created_at=clock_now,
        )

    @staticmethod
    def utility_enhanced_simulation(
        simulation_engine: SimulationEngine,
        utility_engine: UtilityEngine,
        options: tuple[SimulationOption, ...],
        context_type: str,
        context_id: str,
        policy: DecisionPolicy,
        *,
        tradeoff: TradeoffDirection = TradeoffDirection.BALANCED,
        budgets: tuple[ResourceBudget, ...] | None = None,
    ) -> tuple[SimulationComparison, SimulationVerdict, DecisionComparison, UtilityVerdict, TradeoffRecord]:
        """Run simulation + utility analysis in one call.

        Steps:
        1. Run simulation engine for risk/consequence analysis.
        2. Build a utility profile from context.
        3. Run full utility analysis incorporating simulation verdict.
        4. Return all artifacts for audit trail.
        """
        from mcoi_runtime.contracts.simulation import SimulationRequest

        # Step 1: Simulation
        request_id = stable_identifier("sim-req-utility", {
            "context_type": context_type,
            "context_id": context_id,
        })
        request = SimulationRequest(
            request_id=request_id,
            context_type=context_type,
            context_id=context_id,
            description=f"Utility-enhanced simulation for {context_type} {context_id}",
            options=tuple(options),
        )
        sim_comparison, sim_verdict = simulation_engine.full_simulation(request)

        # Step 2: Build utility profile
        clock_now = utility_engine.clock()
        profile = UtilityBridge.build_default_profile(
            context_type=context_type,
            context_id=context_id,
            tradeoff=tradeoff,
            clock_now=clock_now,
        )

        # Step 3: Full utility analysis
        util_comparison, util_verdict, tradeoff_record = utility_engine.full_utility_analysis(
            profile=profile,
            options=tuple(options),
            policy=policy,
            simulation_verdict=sim_verdict,
            budgets=budgets,
        )

        return sim_comparison, sim_verdict, util_comparison, util_verdict, tradeoff_record

    @staticmethod
    def evaluate_resource_feasibility(
        utility_engine: UtilityEngine,
        budgets: tuple[ResourceBudget, ...],
        options: tuple[SimulationOption, ...],
    ) -> Mapping[str, tuple[bool, tuple[str, ...]]]:
        """Check resource feasibility for each option.

        Returns an immutable mapping of option_id -> (feasible, reasons).
        """
        result: dict[str, tuple[bool, tuple[str, ...]]] = {}
        for option in options:
            feasible, reasons = utility_engine.check_resource_feasibility(
                budgets=budgets,
                estimated_cost=option.estimated_cost,
            )
            result[option.option_id] = (feasible, tuple(reasons))
        return MappingProxyType(result)
