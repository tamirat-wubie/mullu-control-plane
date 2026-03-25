"""Tests for mcoi_runtime.core.dashboard_integration — dashboard bridge tests."""

from __future__ import annotations

from mcoi_runtime.contracts.decision_learning import OutcomeQuality
from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
)
from mcoi_runtime.contracts.provider_routing import (
    RoutingConstraints,
    RoutingStrategy,
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
from mcoi_runtime.core.dashboard import DashboardEngine
from mcoi_runtime.core.dashboard_integration import DashboardBridge
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.provider_cost_routing import ProviderCostRouter
from mcoi_runtime.core.provider_registry import ProviderRegistry
from mcoi_runtime.core.provider_routing_integration import ProviderRoutingBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICK = 0


def _clock() -> str:
    global _TICK
    _TICK += 1
    return f"2026-03-20T00:{_TICK // 60:02d}:{_TICK % 60:02d}Z"


def _reset() -> None:
    global _TICK
    _TICK = 0


def _make_registry() -> ProviderRegistry:
    registry = ProviderRegistry(clock=_clock)
    for pid, cost in [("prov-a", 100.0), ("prov-b", 500.0)]:
        scope = CredentialScope(scope_id=f"scope-{pid}", provider_id=pid, cost_limit_per_invocation=cost)
        desc = ProviderDescriptor(
            provider_id=pid, name=f"Provider {pid}",
            provider_class=ProviderClass.MODEL,
            credential_scope_id=f"scope-{pid}", enabled=True,
        )
        registry.register(desc, scope)
        registry.record_success(pid)
    return registry


def _make_comparison() -> DecisionComparison:
    ou = OptionUtility(option_id="opt-a", raw_score=0.7, weighted_score=0.65, factor_contributions={"risk": 0.3}, rank=1)
    return DecisionComparison(
        comparison_id="cmp-1", profile_id="prof-1",
        option_utilities=(ou,), best_option_id="opt-a",
        spread=0.0, decided_at="2026-03-20T00:00:00Z",
    )


def _make_option() -> SimulationOption:
    return SimulationOption(
        option_id="opt-a", label="Option A",
        risk_level=RiskLevel.LOW,
        estimated_cost=100.0, estimated_duration_seconds=3600.0,
        success_probability=0.9,
    )


def _make_profile() -> UtilityProfile:
    return UtilityProfile(
        profile_id="prof-1", context_type="test", context_id="ctx-1",
        factors=(
            DecisionFactor(factor_id="f-risk", kind=DecisionFactorKind.RISK, weight=0.5, value=0.3, label="risk"),
            DecisionFactor(factor_id="f-cost", kind=DecisionFactorKind.COST, weight=0.5, value=0.5, label="cost"),
        ),
        tradeoff_direction=TradeoffDirection.BALANCED,
        created_at="2026-03-20T00:00:00Z",
    )


def _make_tradeoff() -> TradeoffRecord:
    return TradeoffRecord(
        tradeoff_id="tradeoff-1", comparison_id="cmp-1",
        chosen_option_id="opt-a", rejected_option_ids=(),
        tradeoff_direction=TradeoffDirection.BALANCED,
        rationale="best option", recorded_at="2026-03-20T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardBridgeEmpty:
    def test_empty_snapshot(self):
        _reset()
        dashboard = DashboardEngine(clock=_clock)
        decision_engine = DecisionLearningEngine(clock=_clock)
        router = ProviderCostRouter(clock=_clock)
        registry = _make_registry()

        snap = DashboardBridge.full_snapshot(
            dashboard=dashboard,
            decision_engine=decision_engine,
            router=router,
            registry=registry,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
        )

        assert snap.total_decisions == 0
        assert snap.total_routing_decisions == 0
        assert len(snap.recent_decisions) == 0
        assert len(snap.provider_summaries) == 2
        assert len(snap.learning_insights) == 0


class TestDashboardBridgeWithData:
    def test_snapshot_after_learning_cycle(self):
        _reset()
        dashboard = DashboardEngine(clock=_clock)
        decision_engine = DecisionLearningEngine(clock=_clock)
        router = ProviderCostRouter(clock=_clock)
        registry = _make_registry()

        # Run a learning cycle
        decision_engine.full_learning_cycle(
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            actual_cost=80.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="success",
        )

        snap = DashboardBridge.full_snapshot(
            dashboard=dashboard,
            decision_engine=decision_engine,
            router=router,
            registry=registry,
            provider_ids=("prov-a",),
            context_type="model",
        )

        assert snap.total_decisions == 1
        assert len(snap.recent_decisions) == 1
        assert snap.recent_decisions[0].quality == "success"
        # Learning insights should show the weight changes
        assert len(snap.learning_insights) > 0

    def test_snapshot_after_routing(self):
        _reset()
        dashboard = DashboardEngine(clock=_clock)
        decision_engine = DecisionLearningEngine(clock=_clock)
        router = ProviderCostRouter(clock=_clock)
        registry = _make_registry()

        # Do a routing decision
        constraints = RoutingConstraints(
            constraints_id="rc-test",
            max_cost_per_invocation=10_000.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry, learning_engine=decision_engine,
            provider_ids=("prov-a", "prov-b"), context_type="model",
        )
        decision = router.select_provider(entries, "model", constraints)
        router.record_outcome(decision.decision_id, decision.selected_provider_id, 80.0, True)

        snap = DashboardBridge.full_snapshot(
            dashboard=dashboard,
            decision_engine=decision_engine,
            router=router,
            registry=registry,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
        )

        assert snap.total_routing_decisions == 1
        assert len(snap.provider_summaries) == 2
        # At least one provider should have routing_count > 0
        total_routes = sum(ps.routing_count for ps in snap.provider_summaries)
        assert total_routes == 1


class TestGoldenScenario:
    def test_full_lifecycle_snapshot(self):
        """End-to-end: learning + routing + dashboard snapshot."""
        _reset()
        dashboard = DashboardEngine(clock=_clock)
        decision_engine = DecisionLearningEngine(clock=_clock)
        router = ProviderCostRouter(clock=_clock)
        registry = _make_registry()

        # 1. Run learning cycles
        for quality in (OutcomeQuality.SUCCESS, OutcomeQuality.FAILURE, OutcomeQuality.SUCCESS):
            decision_engine.full_learning_cycle(
                comparison=_make_comparison(),
                chosen_option=_make_option(),
                profile=_make_profile(),
                tradeoff=_make_tradeoff(),
                quality=quality,
                actual_cost=80.0 if quality == OutcomeQuality.SUCCESS else 200.0,
                actual_duration_seconds=3000.0,
                success_observed=quality == OutcomeQuality.SUCCESS,
                notes=f"outcome: {quality.value}",
            )

        # 2. Update provider preferences
        for _ in range(5):
            decision_engine.update_provider_preference("prov-a", "model", True)

        # 3. Route through a provider
        constraints = RoutingConstraints(
            constraints_id="rc-test", max_cost_per_invocation=10_000.0,
            min_provider_health_score=0.0, min_preference_score=0.0,
            min_sample_count=0, strategy=RoutingStrategy.LEARNED,
        )
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry, learning_engine=decision_engine,
            provider_ids=("prov-a", "prov-b"), context_type="model",
        )
        decision = router.select_provider(entries, "model", constraints)
        ProviderRoutingBridge.record_and_learn(
            router=router, learning_engine=decision_engine,
            decision=decision, actual_cost=90.0, success=True,
            context_type="model",
        )

        # 4. Take snapshot
        snap = DashboardBridge.full_snapshot(
            dashboard=dashboard,
            decision_engine=decision_engine,
            router=router,
            registry=registry,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
        )

        # Verify comprehensive snapshot
        assert snap.total_decisions == 3
        assert snap.total_routing_decisions == 1
        assert len(snap.recent_decisions) == 3
        assert len(snap.provider_summaries) == 2
        assert len(snap.learning_insights) > 0

        # prov-a should have higher preference
        prov_a_summary = next(ps for ps in snap.provider_summaries if ps.provider_id == "prov-a")
        assert prov_a_summary.preference_score > 0.5
