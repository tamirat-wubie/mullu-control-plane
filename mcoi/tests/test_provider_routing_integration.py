"""Tests for mcoi_runtime.core.provider_routing_integration — routing bridge tests."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
)
from mcoi_runtime.contracts.provider_routing import (
    RoutingConstraints,
    RoutingStrategy,
)
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
    _reset()
    registry = ProviderRegistry(clock=_clock)
    # Register two providers
    scope_a = CredentialScope(scope_id="scope-a", provider_id="prov-a", cost_limit_per_invocation=100.0)
    desc_a = ProviderDescriptor(
        provider_id="prov-a", name="Provider A", provider_class=ProviderClass.MODEL,
        credential_scope_id="scope-a", enabled=True,
    )
    registry.register(desc_a, scope_a)
    registry.record_success("prov-a")

    scope_b = CredentialScope(scope_id="scope-b", provider_id="prov-b", cost_limit_per_invocation=500.0)
    desc_b = ProviderDescriptor(
        provider_id="prov-b", name="Provider B", provider_class=ProviderClass.MODEL,
        credential_scope_id="scope-b", enabled=True,
    )
    registry.register(desc_b, scope_b)
    registry.record_success("prov-b")

    return registry


def _make_router() -> ProviderCostRouter:
    return ProviderCostRouter(clock=_clock)


def _make_learning() -> DecisionLearningEngine:
    return DecisionLearningEngine(clock=_clock)


def _default_constraints(strategy: RoutingStrategy = RoutingStrategy.BALANCED) -> RoutingConstraints:
    return RoutingConstraints(
        constraints_id="rc-test",
        max_cost_per_invocation=10_000.0,
        min_provider_health_score=0.0,
        min_preference_score=0.0,
        min_sample_count=0,
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# Tests: build_provider_entries
# ---------------------------------------------------------------------------


class TestBuildProviderEntries:
    def test_builds_entries_from_registry(self):
        registry = _make_registry()
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
        )
        assert len(entries) == 2
        # Each entry is (provider_id, estimated_cost, health_score, preference_score)
        ids = {e[0] for e in entries}
        assert ids == {"prov-a", "prov-b"}

    def test_uses_cost_from_scope(self):
        registry = _make_registry()
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a",),
            context_type="model",
        )
        # prov-a scope has cost_limit_per_invocation=100.0
        assert entries[0][1] == 100.0

    def test_uses_default_cost_when_no_scope(self):
        _reset()
        registry = ProviderRegistry(clock=_clock)
        scope = CredentialScope(scope_id="scope-c", provider_id="prov-c")
        desc = ProviderDescriptor(
            provider_id="prov-c", name="Provider C", provider_class=ProviderClass.INTEGRATION,
            credential_scope_id="scope-c", enabled=True,
        )
        registry.register(desc, scope)

        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-c",),
            context_type="model",
            default_cost=42.0,
        )
        assert entries[0][1] == 42.0

    def test_skips_unknown_providers(self):
        registry = _make_registry()
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a", "prov-nonexistent"),
            context_type="model",
        )
        assert len(entries) == 1

    def test_skips_disabled_providers(self):
        _reset()
        registry = ProviderRegistry(clock=_clock)
        scope = CredentialScope(scope_id="scope-d", provider_id="prov-d")
        desc = ProviderDescriptor(
            provider_id="prov-d", name="Provider D", provider_class=ProviderClass.MODEL,
            credential_scope_id="scope-d", enabled=False,
        )
        registry.register(desc, scope)

        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-d",),
            context_type="model",
        )
        assert len(entries) == 0

    def test_uses_learned_preferences(self):
        registry = _make_registry()
        learning = _make_learning()
        # Build up preference for prov-a
        for _ in range(5):
            learning.update_provider_preference("prov-a", "model", True)
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=learning,
            provider_ids=("prov-a",),
            context_type="model",
        )
        # preference_score should be > 0.5 (default)
        assert entries[0][3] > 0.5

    def test_healthy_provider_gets_high_health_score(self):
        registry = _make_registry()
        entries = ProviderRoutingBridge.build_provider_entries(
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a",),
            context_type="model",
        )
        # prov-a had record_success so health_score should be 1.0
        assert entries[0][2] == 1.0


# ---------------------------------------------------------------------------
# Tests: select_best_provider
# ---------------------------------------------------------------------------


class TestSelectBestProvider:
    def test_selects_from_registry(self):
        registry = _make_registry()
        router = _make_router()
        decision = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
            constraints=_default_constraints(),
        )
        assert decision.selected_provider_id in ("prov-a", "prov-b")

    def test_cheapest_selects_cheapest_provider(self):
        registry = _make_registry()
        router = _make_router()
        decision = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=None,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
            constraints=_default_constraints(strategy=RoutingStrategy.CHEAPEST),
        )
        # prov-a has cost_limit 100, prov-b has 500
        assert decision.selected_provider_id == "prov-a"


# ---------------------------------------------------------------------------
# Tests: record_and_learn
# ---------------------------------------------------------------------------


class TestRecordAndLearn:
    def test_records_and_updates_preference(self):
        registry = _make_registry()
        router = _make_router()
        learning = _make_learning()

        decision = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=learning,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
            constraints=_default_constraints(),
        )

        outcome = ProviderRoutingBridge.record_and_learn(
            router=router,
            learning_engine=learning,
            decision=decision,
            actual_cost=80.0,
            success=True,
            context_type="model",
        )

        assert outcome.success is True
        assert router.outcome_count == 1

        # Learning engine should now have a preference for the selected provider
        pref = learning.get_provider_preference(decision.selected_provider_id, "model")
        assert pref is not None
        assert pref.sample_count >= 1

    def test_failure_decreases_preference(self):
        registry = _make_registry()
        router = _make_router()
        learning = _make_learning()

        decision = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=learning,
            provider_ids=("prov-a",),
            context_type="model",
            constraints=_default_constraints(),
        )

        # Record several failures
        for _ in range(5):
            ProviderRoutingBridge.record_and_learn(
                router=router,
                learning_engine=learning,
                decision=decision,
                actual_cost=100.0,
                success=False,
                context_type="model",
            )

        pref = learning.get_provider_preference(decision.selected_provider_id, "model")
        assert pref is not None
        assert pref.score < 0.5  # should be below neutral


# ---------------------------------------------------------------------------
# Golden scenario: full routing + learning loop
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    def test_learning_improves_routing(self):
        """Repeated successes for one provider should make it the preferred choice."""
        _reset()
        registry = _make_registry()
        router = ProviderCostRouter(clock=_clock)
        learning = DecisionLearningEngine(clock=_clock)

        # Initial routing — both providers similar, prov-a cheaper
        decision1 = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=learning,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
            constraints=_default_constraints(strategy=RoutingStrategy.LEARNED),
        )

        # Record successes for prov-b many times to build preference
        for _ in range(10):
            learning.update_provider_preference("prov-b", "model", True)

        # Record failures for prov-a to lower preference
        for _ in range(10):
            learning.update_provider_preference("prov-a", "model", False)

        # Now route again with LEARNED strategy — should prefer prov-b despite cost
        decision2 = ProviderRoutingBridge.select_best_provider(
            router=router,
            registry=registry,
            learning_engine=learning,
            provider_ids=("prov-a", "prov-b"),
            context_type="model",
            constraints=_default_constraints(strategy=RoutingStrategy.LEARNED),
        )

        assert decision2.selected_provider_id == "prov-b"
