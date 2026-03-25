"""Tests for mcoi_runtime.contracts.provider_routing — provider cost routing contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.provider_routing import (
    ProviderCandidate,
    RoutingConstraints,
    RoutingDecision,
    RoutingOutcome,
    RoutingStrategy,
)


# ---------------------------------------------------------------------------
# RoutingStrategy
# ---------------------------------------------------------------------------


class TestRoutingStrategy:
    def test_all_values(self) -> None:
        assert len(RoutingStrategy) == 4
        assert RoutingStrategy.CHEAPEST == "cheapest"
        assert RoutingStrategy.MOST_RELIABLE == "most_reliable"
        assert RoutingStrategy.BALANCED == "balanced"
        assert RoutingStrategy.LEARNED == "learned"


# ---------------------------------------------------------------------------
# RoutingConstraints
# ---------------------------------------------------------------------------


class TestRoutingConstraints:
    def test_valid_constraints(self) -> None:
        c = RoutingConstraints(
            constraints_id="rc-1",
            max_cost_per_invocation=100.0,
            min_provider_health_score=0.5,
            min_preference_score=0.0,
            min_sample_count=3,
            strategy=RoutingStrategy.BALANCED,
        )
        assert c.max_cost_per_invocation == 100.0
        assert c.strategy == RoutingStrategy.BALANCED

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="constraints_id"):
            RoutingConstraints(
                constraints_id="",
                max_cost_per_invocation=10.0,
                min_provider_health_score=0.5,
                min_preference_score=0.0,
                min_sample_count=0,
                strategy=RoutingStrategy.CHEAPEST,
            )

    def test_negative_max_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="max_cost_per_invocation"):
            RoutingConstraints(
                constraints_id="rc-bad",
                max_cost_per_invocation=-1.0,
                min_provider_health_score=0.5,
                min_preference_score=0.0,
                min_sample_count=0,
                strategy=RoutingStrategy.CHEAPEST,
            )

    def test_health_score_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="min_provider_health_score"):
            RoutingConstraints(
                constraints_id="rc-bad2",
                max_cost_per_invocation=10.0,
                min_provider_health_score=1.5,
                min_preference_score=0.0,
                min_sample_count=0,
                strategy=RoutingStrategy.CHEAPEST,
            )

    def test_negative_sample_count_raises(self) -> None:
        with pytest.raises(ValueError, match="min_sample_count"):
            RoutingConstraints(
                constraints_id="rc-bad3",
                max_cost_per_invocation=10.0,
                min_provider_health_score=0.5,
                min_preference_score=0.0,
                min_sample_count=-1,
                strategy=RoutingStrategy.CHEAPEST,
            )

    def test_string_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy"):
            RoutingConstraints(
                constraints_id="rc-bad4",
                max_cost_per_invocation=10.0,
                min_provider_health_score=0.5,
                min_preference_score=0.0,
                min_sample_count=0,
                strategy="balanced",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# ProviderCandidate
# ---------------------------------------------------------------------------


class TestProviderCandidate:
    def test_valid_candidate(self) -> None:
        c = ProviderCandidate(
            candidate_id="cand-1",
            provider_id="prov-a",
            context_type="model",
            estimated_cost=50.0,
            health_score=0.9,
            preference_score=0.7,
            composite_score=0.8,
            rank=1,
            scored_at="2026-03-20T00:00:00Z",
        )
        assert c.composite_score == 0.8
        assert c.rank == 1

    def test_empty_provider_id_raises(self) -> None:
        with pytest.raises(ValueError, match="provider_id"):
            ProviderCandidate(
                candidate_id="cand-bad",
                provider_id="",
                context_type="model",
                estimated_cost=0.0,
                health_score=0.5,
                preference_score=0.5,
                composite_score=0.5,
                rank=1,
                scored_at="2026-03-20T00:00:00Z",
            )

    def test_negative_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="estimated_cost"):
            ProviderCandidate(
                candidate_id="cand-bad2",
                provider_id="prov-a",
                context_type="model",
                estimated_cost=-1.0,
                health_score=0.5,
                preference_score=0.5,
                composite_score=0.5,
                rank=1,
                scored_at="2026-03-20T00:00:00Z",
            )

    def test_composite_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="composite_score"):
            ProviderCandidate(
                candidate_id="cand-bad3",
                provider_id="prov-a",
                context_type="model",
                estimated_cost=0.0,
                health_score=0.5,
                preference_score=0.5,
                composite_score=1.5,
                rank=1,
                scored_at="2026-03-20T00:00:00Z",
            )

    def test_rank_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="rank"):
            ProviderCandidate(
                candidate_id="cand-bad4",
                provider_id="prov-a",
                context_type="model",
                estimated_cost=0.0,
                health_score=0.5,
                preference_score=0.5,
                composite_score=0.5,
                rank=0,
                scored_at="2026-03-20T00:00:00Z",
            )

    def test_nan_health_raises(self) -> None:
        with pytest.raises(ValueError, match="health_score"):
            ProviderCandidate(
                candidate_id="cand-nan",
                provider_id="prov-a",
                context_type="model",
                estimated_cost=0.0,
                health_score=float("nan"),
                preference_score=0.5,
                composite_score=0.5,
                rank=1,
                scored_at="2026-03-20T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# RoutingDecision
# ---------------------------------------------------------------------------


def _make_candidate(provider_id: str = "prov-a", rank: int = 1, cost: float = 50.0) -> ProviderCandidate:
    return ProviderCandidate(
        candidate_id=f"cand-{provider_id}",
        provider_id=provider_id,
        context_type="model",
        estimated_cost=cost,
        health_score=0.9,
        preference_score=0.7,
        composite_score=0.8,
        rank=rank,
        scored_at="2026-03-20T00:00:00Z",
    )


class TestRoutingDecision:
    def test_valid_decision(self) -> None:
        cand = _make_candidate()
        d = RoutingDecision(
            decision_id="rd-1",
            constraints_id="rc-1",
            candidates=(cand,),
            selected_provider_id="prov-a",
            selected_cost=50.0,
            rationale="best score",
            decided_at="2026-03-20T00:00:00Z",
        )
        assert d.selected_provider_id == "prov-a"

    def test_selected_not_in_candidates_raises(self) -> None:
        cand = _make_candidate(provider_id="prov-a")
        with pytest.raises(ValueError, match="selected_provider_id"):
            RoutingDecision(
                decision_id="rd-bad",
                constraints_id="rc-1",
                candidates=(cand,),
                selected_provider_id="prov-z",
                selected_cost=50.0,
                rationale="bad selection",
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_empty_candidates_raises(self) -> None:
        with pytest.raises(ValueError, match="candidates"):
            RoutingDecision(
                decision_id="rd-empty",
                constraints_id="rc-1",
                candidates=(),
                selected_provider_id="prov-a",
                selected_cost=0.0,
                rationale="empty",
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_bad_candidate_type_raises(self) -> None:
        with pytest.raises(ValueError, match="candidates"):
            RoutingDecision(
                decision_id="rd-type",
                constraints_id="rc-1",
                candidates=("not-a-candidate",),  # type: ignore[arg-type]
                selected_provider_id="prov-a",
                selected_cost=0.0,
                rationale="bad type",
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_multiple_candidates(self) -> None:
        c1 = _make_candidate("prov-a", rank=1)
        c2 = _make_candidate("prov-b", rank=2)
        d = RoutingDecision(
            decision_id="rd-multi",
            constraints_id="rc-1",
            candidates=(c1, c2),
            selected_provider_id="prov-a",
            selected_cost=50.0,
            rationale="prov-a highest score",
            decided_at="2026-03-20T00:00:00Z",
        )
        assert len(d.candidates) == 2


# ---------------------------------------------------------------------------
# RoutingOutcome
# ---------------------------------------------------------------------------


class TestRoutingOutcome:
    def test_valid_outcome(self) -> None:
        o = RoutingOutcome(
            outcome_id="ro-1",
            decision_id="rd-1",
            provider_id="prov-a",
            actual_cost=45.0,
            success=True,
            recorded_at="2026-03-20T00:00:00Z",
        )
        assert o.success is True
        assert o.actual_cost == 45.0

    def test_negative_actual_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="actual_cost"):
            RoutingOutcome(
                outcome_id="ro-bad",
                decision_id="rd-1",
                provider_id="prov-a",
                actual_cost=-10.0,
                success=True,
                recorded_at="2026-03-20T00:00:00Z",
            )

    def test_non_bool_success_raises(self) -> None:
        with pytest.raises(ValueError, match="success"):
            RoutingOutcome(
                outcome_id="ro-bad2",
                decision_id="rd-1",
                provider_id="prov-a",
                actual_cost=0.0,
                success=1,  # type: ignore[arg-type]
                recorded_at="2026-03-20T00:00:00Z",
            )

    def test_empty_provider_id_raises(self) -> None:
        with pytest.raises(ValueError, match="provider_id"):
            RoutingOutcome(
                outcome_id="ro-bad3",
                decision_id="rd-1",
                provider_id="",
                actual_cost=0.0,
                success=True,
                recorded_at="2026-03-20T00:00:00Z",
            )

    def test_bad_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="recorded_at"):
            RoutingOutcome(
                outcome_id="ro-bad4",
                decision_id="rd-1",
                provider_id="prov-a",
                actual_cost=0.0,
                success=True,
                recorded_at="not-a-date",
            )


# ---------------------------------------------------------------------------
# Audit hardening (Phase 29B)
# ---------------------------------------------------------------------------


class TestAuditHardening:
    """Audit-driven hardening tests for Phase 29B contract gaps."""

    def test_min_preference_score_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="min_preference_score"):
            RoutingConstraints(
                constraints_id="rc-h1",
                max_cost_per_invocation=100.0,
                min_provider_health_score=0.0,
                min_preference_score=-0.1,
                min_sample_count=0,
                strategy=RoutingStrategy.BALANCED,
            )

    def test_min_preference_score_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="min_preference_score"):
            RoutingConstraints(
                constraints_id="rc-h2",
                max_cost_per_invocation=100.0,
                min_provider_health_score=0.0,
                min_preference_score=1.5,
                min_sample_count=0,
                strategy=RoutingStrategy.BALANCED,
            )

    def test_candidate_inf_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="estimated_cost"):
            ProviderCandidate(
                candidate_id="cand-inf",
                provider_id="prov-a",
                context_type="model",
                estimated_cost=float("inf"),
                health_score=0.5,
                preference_score=0.5,
                composite_score=0.5,
                rank=1,
                scored_at="2026-03-20T00:00:00Z",
            )

    def test_constraints_boolean_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_cost_per_invocation"):
            RoutingConstraints(
                constraints_id="rc-bool",
                max_cost_per_invocation=True,  # type: ignore[arg-type]
                min_provider_health_score=0.0,
                min_preference_score=0.0,
                min_sample_count=0,
                strategy=RoutingStrategy.BALANCED,
            )

    def test_decision_immutable(self) -> None:
        cand = _make_candidate()
        d = RoutingDecision(
            decision_id="rd-imm",
            constraints_id="rc-1",
            candidates=(cand,),
            selected_provider_id="prov-a",
            selected_cost=50.0,
            rationale="test",
            decided_at="2026-03-20T00:00:00Z",
        )
        with pytest.raises(AttributeError):
            d.selected_provider_id = "prov-b"  # type: ignore[misc]
