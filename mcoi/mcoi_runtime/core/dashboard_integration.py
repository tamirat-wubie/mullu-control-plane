"""Purpose: dashboard integration bridge — connects the dashboard engine
to the decision learning, provider routing, and provider registry subsystems.
Governance scope: dashboard snapshot generation from live engine state.
Dependencies: dashboard engine, decision learning engine, provider cost router,
    provider registry, dashboard contracts.
Invariants:
  - Bridge methods are stateless helpers.
  - Snapshot generation reads but never mutates engine state.
  - All data flows through validated contracts.
  - No network, no IO.
"""

from __future__ import annotations

from mcoi_runtime.contracts.dashboard import DashboardSnapshot, WorldStateSummary
from mcoi_runtime.contracts.meta_reasoning import MetaReasoningSnapshot
from .dashboard import DashboardEngine
from .decision_learning import DecisionLearningEngine
from .provider_cost_routing import ProviderCostRouter
from .provider_registry import ProviderRegistry
from .provider_routing_integration import HEALTH_STATUS_SCORES


class DashboardBridge:
    """Bridges the dashboard engine with live subsystem state.

    Provides a single-call method to produce a complete dashboard snapshot
    from the current state of the decision learning engine, provider cost
    router, and provider registry.
    """

    @staticmethod
    def full_snapshot(
        dashboard: DashboardEngine,
        decision_engine: DecisionLearningEngine,
        router: ProviderCostRouter,
        registry: ProviderRegistry,
        provider_ids: tuple[str, ...],
        context_type: str,
        *,
        meta_snapshot: MetaReasoningSnapshot | None = None,
        world_state_summary: WorldStateSummary | None = None,
    ) -> DashboardSnapshot:
        """Generate a complete dashboard snapshot from live engine state.

        Reads outcomes, adjustments, routing outcomes, preferences, and
        health data, then delegates to the dashboard engine for assembly.
        """
        # Gather decision learning data
        outcomes = decision_engine.outcomes
        adjustments = decision_engine.adjustments
        learned_adjustments = decision_engine.get_learned_factor_adjustments()

        # Gather routing data
        routing_outcomes = router.routing_outcomes

        # Gather preferences for each provider
        preferences: dict[str, float] = {}
        for pid in provider_ids:
            pref = decision_engine.get_provider_preference(pid, context_type)
            if pref is not None:
                preferences[pid] = pref.score

        # Gather health scores from registry
        health_scores: dict[str, float] = {}
        for pid in provider_ids:
            health_record = registry.get_health(pid)
            if health_record is not None:
                health_scores[pid] = HEALTH_STATUS_SCORES.get(health_record.status, 0.3)
            else:
                health_scores[pid] = 0.3

        return dashboard.snapshot(
            outcomes=outcomes,
            adjustments=adjustments,
            routing_outcomes=routing_outcomes,
            preferences=preferences,
            provider_ids=provider_ids,
            health_scores=health_scores,
            learned_adjustments=learned_adjustments,
            total_decisions=decision_engine.outcome_count,
            total_routing_decisions=router.routing_count,
            context_type=context_type,
            meta_snapshot=meta_snapshot,
            world_state_summary=world_state_summary,
        )
