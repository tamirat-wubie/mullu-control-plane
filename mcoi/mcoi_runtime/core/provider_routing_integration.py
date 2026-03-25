"""Purpose: provider routing integration bridge — connects cost routing to
provider registry, decision learning, and utility subsystems.
Governance scope: provider routing invocation for cost-aware provider selection.
Dependencies: provider cost router, provider registry, decision learning engine,
    provider routing contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Each method composes existing engine calls.
  - No graph mutation. No side effects beyond engine-internal state.
  - Routing never bypasses provider health or credential scope checks.
  - All scores are bounded and auditable.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from mcoi_runtime.contracts.provider import ProviderHealthStatus
from mcoi_runtime.contracts.provider_routing import (
    RoutingConstraints,
    RoutingDecision,
    RoutingOutcome,
    RoutingStrategy,
)
from .decision_learning import DecisionLearningEngine
from .provider_cost_routing import ProviderCostRouter
from .provider_registry import ProviderRegistry


# Health status to score mapping (shared — imported by dashboard_integration)
HEALTH_STATUS_SCORES: Mapping[ProviderHealthStatus, float] = MappingProxyType({
    ProviderHealthStatus.HEALTHY: 1.0,
    ProviderHealthStatus.DEGRADED: 0.5,
    ProviderHealthStatus.UNAVAILABLE: 0.0,
    ProviderHealthStatus.UNKNOWN: 0.3,
})


class ProviderRoutingBridge:
    """Bridges provider cost routing with the provider registry and learning engine.

    Provides convenience methods for:
    - Building provider entries from registry + learning data
    - Selecting the best provider for a context with full constraint checking
    - Recording routing outcomes and feeding them back to learning
    """

    @staticmethod
    def build_provider_entries(
        registry: ProviderRegistry,
        learning_engine: DecisionLearningEngine | None,
        provider_ids: tuple[str, ...],
        context_type: str,
        *,
        default_cost: float = 0.0,
    ) -> tuple[tuple[str, float, float, float], ...]:
        """Build scored provider entries from registry health and learned preferences.

        Returns tuples of (provider_id, estimated_cost, health_score, preference_score)
        suitable for passing to ProviderCostRouter.rank_providers().

        Providers not found in the registry are skipped.
        """
        entries: list[tuple[str, float, float, float]] = []

        for pid in provider_ids:
            descriptor = registry.get_provider(pid)
            if descriptor is None:
                continue
            if not descriptor.enabled:
                continue

            # Health score from registry
            health_record = registry.get_health(pid)
            if health_record is not None:
                health_score = HEALTH_STATUS_SCORES.get(health_record.status, 0.3)
            else:
                health_score = 0.3  # unknown health

            # Preference score from learning engine
            preference_score = 0.5  # neutral default
            if learning_engine is not None:
                pref = learning_engine.get_provider_preference(pid, context_type)
                if pref is not None:
                    preference_score = pref.score

            # Cost from credential scope (if available)
            scope = registry.get_scope(pid)
            if scope is not None and scope.cost_limit_per_invocation is not None:
                estimated_cost = scope.cost_limit_per_invocation
            else:
                estimated_cost = default_cost

            entries.append((pid, estimated_cost, health_score, preference_score))

        return tuple(entries)

    @staticmethod
    def select_best_provider(
        router: ProviderCostRouter,
        registry: ProviderRegistry,
        learning_engine: DecisionLearningEngine | None,
        provider_ids: tuple[str, ...],
        context_type: str,
        constraints: RoutingConstraints,
        *,
        default_cost: float = 0.0,
    ) -> RoutingDecision:
        """Select the best provider using registry health, learned preferences, and cost constraints.

        Combines build_provider_entries with router.select_provider for a complete
        routing decision in one call.
        """
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=learning_engine,
            provider_ids=provider_ids,
            context_type=context_type,
            default_cost=default_cost,
        )
        return router.select_provider(entries, context_type, constraints)

    @staticmethod
    def record_and_learn(
        router: ProviderCostRouter,
        learning_engine: DecisionLearningEngine,
        decision: RoutingDecision,
        actual_cost: float,
        success: bool,
        context_type: str,
    ) -> RoutingOutcome:
        """Record a routing outcome and feed it back to the learning engine.

        Updates both the router's outcome history and the learning engine's
        provider preference for the selected provider.
        """
        outcome = router.record_outcome(
            decision_id=decision.decision_id,
            provider_id=decision.selected_provider_id,
            actual_cost=actual_cost,
            success=success,
        )

        learning_engine.update_provider_preference(
            provider_id=decision.selected_provider_id,
            context_type=context_type,
            success=success,
        )

        return outcome
