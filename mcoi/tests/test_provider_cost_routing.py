"""Tests for mcoi_runtime.core.provider_cost_routing — provider cost routing engine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider_routing import (
    RoutingConstraints,
    RoutingStrategy,
)
from mcoi_runtime.core.provider_cost_routing import ProviderCostRouter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICK = 0


def _make_router() -> ProviderCostRouter:
    global _TICK
    _TICK = 0

    def clock() -> str:
        global _TICK
        _TICK += 1
        return f"2026-03-20T00:{_TICK // 60:02d}:{_TICK % 60:02d}Z"

    return ProviderCostRouter(clock=clock)


def _default_constraints(
    strategy: RoutingStrategy = RoutingStrategy.BALANCED,
    max_cost: float = 10_000.0,
) -> RoutingConstraints:
    return RoutingConstraints(
        constraints_id="rc-test",
        max_cost_per_invocation=max_cost,
        min_provider_health_score=0.0,
        min_preference_score=0.0,
        min_sample_count=0,
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# score_provider
# ---------------------------------------------------------------------------


class TestScoreProvider:
    def test_cheapest_favors_low_cost(self):
        router = _make_router()
        # Provider with zero cost vs high cost
        cheap = router.score_provider("p1", "ctx", estimated_cost=0.0, health_score=0.5, preference_score=0.5, strategy=RoutingStrategy.CHEAPEST)
        expensive = router.score_provider("p2", "ctx", estimated_cost=9000.0, health_score=0.5, preference_score=0.5, strategy=RoutingStrategy.CHEAPEST)
        assert cheap > expensive

    def test_most_reliable_favors_health(self):
        router = _make_router()
        healthy = router.score_provider("p1", "ctx", estimated_cost=5000.0, health_score=1.0, preference_score=0.5, strategy=RoutingStrategy.MOST_RELIABLE)
        unhealthy = router.score_provider("p2", "ctx", estimated_cost=5000.0, health_score=0.1, preference_score=0.5, strategy=RoutingStrategy.MOST_RELIABLE)
        assert healthy > unhealthy

    def test_learned_favors_preference(self):
        router = _make_router()
        preferred = router.score_provider("p1", "ctx", estimated_cost=5000.0, health_score=0.5, preference_score=1.0, strategy=RoutingStrategy.LEARNED)
        unpreferred = router.score_provider("p2", "ctx", estimated_cost=5000.0, health_score=0.5, preference_score=0.0, strategy=RoutingStrategy.LEARNED)
        assert preferred > unpreferred

    def test_balanced_between_all(self):
        router = _make_router()
        score = router.score_provider("p1", "ctx", estimated_cost=0.0, health_score=1.0, preference_score=1.0, strategy=RoutingStrategy.BALANCED)
        assert 0.99 <= score <= 1.0

    def test_score_clamped_to_unit(self):
        router = _make_router()
        score = router.score_provider("p1", "ctx", estimated_cost=0.0, health_score=1.0, preference_score=1.0, strategy=RoutingStrategy.CHEAPEST)
        assert 0.0 <= score <= 1.0

    def test_high_cost_reduces_cost_score(self):
        router = _make_router()
        # Cost at normalization boundary
        s1 = router.score_provider("p1", "ctx", estimated_cost=10_000.0, health_score=0.5, preference_score=0.5, strategy=RoutingStrategy.BALANCED)
        s2 = router.score_provider("p2", "ctx", estimated_cost=0.0, health_score=0.5, preference_score=0.5, strategy=RoutingStrategy.BALANCED)
        assert s2 > s1  # zero cost scores higher


# ---------------------------------------------------------------------------
# rank_providers
# ---------------------------------------------------------------------------


class TestRankProviders:
    def test_basic_ranking(self):
        router = _make_router()
        entries = (
            ("prov-a", 100.0, 0.9, 0.7),
            ("prov-b", 200.0, 0.8, 0.8),
            ("prov-c", 50.0, 0.95, 0.6),
        )
        candidates = router.rank_providers(entries, "model", _default_constraints())
        assert len(candidates) == 3
        assert candidates[0].rank == 1
        assert candidates[1].rank == 2
        assert candidates[2].rank == 3
        # Scores should be descending
        assert candidates[0].composite_score >= candidates[1].composite_score
        assert candidates[1].composite_score >= candidates[2].composite_score

    def test_filters_by_max_cost(self):
        router = _make_router()
        entries = (
            ("prov-cheap", 50.0, 0.9, 0.7),
            ("prov-expensive", 500.0, 0.9, 0.7),
        )
        constraints = RoutingConstraints(
            constraints_id="rc-cost",
            max_cost_per_invocation=100.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        candidates = router.rank_providers(entries, "model", constraints)
        assert len(candidates) == 1
        assert candidates[0].provider_id == "prov-cheap"

    def test_filters_by_min_health(self):
        router = _make_router()
        entries = (
            ("prov-healthy", 100.0, 0.8, 0.5),
            ("prov-sick", 100.0, 0.2, 0.5),
        )
        constraints = RoutingConstraints(
            constraints_id="rc-health",
            max_cost_per_invocation=10_000.0,
            min_provider_health_score=0.5,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        candidates = router.rank_providers(entries, "model", constraints)
        assert len(candidates) == 1
        assert candidates[0].provider_id == "prov-healthy"

    def test_filters_by_min_preference(self):
        router = _make_router()
        entries = (
            ("prov-liked", 100.0, 0.8, 0.7),
            ("prov-unknown", 100.0, 0.8, 0.1),
        )
        constraints = RoutingConstraints(
            constraints_id="rc-pref",
            max_cost_per_invocation=10_000.0,
            min_provider_health_score=0.0,
            min_preference_score=0.5,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        candidates = router.rank_providers(entries, "model", constraints)
        assert len(candidates) == 1
        assert candidates[0].provider_id == "prov-liked"

    def test_empty_after_filtering(self):
        router = _make_router()
        entries = (("prov-a", 500.0, 0.9, 0.7),)
        constraints = RoutingConstraints(
            constraints_id="rc-strict",
            max_cost_per_invocation=100.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        candidates = router.rank_providers(entries, "model", constraints)
        assert len(candidates) == 0

    def test_deterministic_tiebreaker(self):
        router = _make_router()
        # Same scores, different IDs — should be sorted alphabetically
        entries = (
            ("prov-b", 100.0, 0.9, 0.7),
            ("prov-a", 100.0, 0.9, 0.7),
        )
        candidates = router.rank_providers(entries, "model", _default_constraints())
        assert candidates[0].provider_id == "prov-a"
        assert candidates[1].provider_id == "prov-b"


# ---------------------------------------------------------------------------
# select_provider
# ---------------------------------------------------------------------------


class TestSelectProvider:
    def test_selects_top_ranked(self):
        router = _make_router()
        entries = (
            ("prov-a", 100.0, 0.9, 0.7),
            ("prov-b", 200.0, 0.8, 0.8),
        )
        decision = router.select_provider(entries, "model", _default_constraints())
        assert decision.selected_provider_id in ("prov-a", "prov-b")
        assert len(decision.candidates) == 2
        assert decision.candidates[0].provider_id == decision.selected_provider_id

    def test_raises_when_no_candidates(self):
        router = _make_router()
        entries = (("prov-a", 99999.0, 0.9, 0.7),)
        constraints = RoutingConstraints(
            constraints_id="rc-strict",
            max_cost_per_invocation=10.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        with pytest.raises(ValueError, match="no provider candidates"):
            router.select_provider(entries, "model", constraints)

    def test_decision_stored_in_history(self):
        router = _make_router()
        assert router.routing_count == 0
        entries = (("prov-a", 100.0, 0.9, 0.7),)
        router.select_provider(entries, "model", _default_constraints())
        assert router.routing_count == 1

    def test_rationale_contains_strategy(self):
        router = _make_router()
        entries = (("prov-a", 100.0, 0.9, 0.7),)
        decision = router.select_provider(entries, "model", _default_constraints(strategy=RoutingStrategy.CHEAPEST))
        assert "cheapest" in decision.rationale


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


class TestRecordOutcome:
    def test_records_success(self):
        router = _make_router()
        outcome = router.record_outcome("dec-1", "prov-a", 45.0, True)
        assert outcome.success is True
        assert outcome.actual_cost == 45.0
        assert router.outcome_count == 1

    def test_records_failure(self):
        router = _make_router()
        outcome = router.record_outcome("dec-1", "prov-a", 0.0, False)
        assert outcome.success is False


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_cheapest_strategy_picks_cheapest_provider(self):
        """Given providers at different price points, CHEAPEST strategy selects the cheapest."""
        router = _make_router()
        entries = (
            ("openai", 500.0, 0.9, 0.5),
            ("anthropic", 300.0, 0.9, 0.5),
            ("google", 800.0, 0.9, 0.5),
        )
        decision = router.select_provider(entries, "model", _default_constraints(strategy=RoutingStrategy.CHEAPEST))
        assert decision.selected_provider_id == "anthropic"  # lowest cost

    def test_reliable_strategy_picks_healthiest(self):
        """Given providers at different health levels, MOST_RELIABLE selects the healthiest."""
        router = _make_router()
        entries = (
            ("openai", 500.0, 0.7, 0.5),
            ("anthropic", 500.0, 0.95, 0.5),
            ("google", 500.0, 0.5, 0.5),
        )
        decision = router.select_provider(entries, "model", _default_constraints(strategy=RoutingStrategy.MOST_RELIABLE))
        assert decision.selected_provider_id == "anthropic"  # healthiest

    def test_learned_strategy_picks_preferred(self):
        """Given providers at different preference levels, LEARNED selects the most preferred."""
        router = _make_router()
        entries = (
            ("openai", 500.0, 0.8, 0.3),
            ("anthropic", 500.0, 0.8, 0.9),
            ("google", 500.0, 0.8, 0.5),
        )
        decision = router.select_provider(entries, "model", _default_constraints(strategy=RoutingStrategy.LEARNED))
        assert decision.selected_provider_id == "anthropic"  # most preferred

    def test_cost_constraint_overrides_preference(self):
        """Even a highly preferred provider is excluded if it exceeds cost limits."""
        router = _make_router()
        entries = (
            ("cheap-ok", 50.0, 0.7, 0.3),
            ("expensive-preferred", 500.0, 0.9, 0.95),
        )
        constraints = RoutingConstraints(
            constraints_id="rc-budget",
            max_cost_per_invocation=100.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.LEARNED,
        )
        decision = router.select_provider(entries, "model", constraints)
        assert decision.selected_provider_id == "cheap-ok"

    def test_full_routing_cycle(self):
        """End-to-end: select provider, record outcome, verify audit trail."""
        router = _make_router()
        entries = (
            ("prov-a", 100.0, 0.9, 0.7),
            ("prov-b", 200.0, 0.8, 0.6),
        )
        decision = router.select_provider(entries, "model", _default_constraints())
        assert router.routing_count == 1

        outcome = router.record_outcome(
            decision_id=decision.decision_id,
            provider_id=decision.selected_provider_id,
            actual_cost=90.0,
            success=True,
        )
        assert router.outcome_count == 1
        assert outcome.provider_id == decision.selected_provider_id


# ---------------------------------------------------------------------------
# Audit hardening (Phase 29B)
# ---------------------------------------------------------------------------


class TestAuditHardening:
    def test_empty_entries_returns_empty(self):
        router = _make_router()
        candidates = router.rank_providers((), "model", _default_constraints())
        assert candidates == ()

    def test_cost_above_normalization_clamped(self):
        router = _make_router()
        score = router.score_provider(
            "p1", "ctx", estimated_cost=20_000.0, health_score=0.5,
            preference_score=0.5, strategy=RoutingStrategy.BALANCED,
        )
        assert 0.0 <= score <= 1.0

    def test_select_raises_when_all_filtered(self):
        router = _make_router()
        entries = (("prov-a", 500.0, 0.9, 0.7),)
        constraints = RoutingConstraints(
            constraints_id="rc-strict",
            max_cost_per_invocation=10.0,
            min_provider_health_score=0.0,
            min_preference_score=0.0,
            min_sample_count=0,
            strategy=RoutingStrategy.BALANCED,
        )
        with pytest.raises(ValueError, match="no provider candidates"):
            router.select_provider(entries, "model", constraints)
