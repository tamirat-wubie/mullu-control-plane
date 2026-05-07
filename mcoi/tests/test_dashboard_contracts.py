"""Tests for mcoi_runtime.contracts.dashboard — operator dashboard contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.dashboard import (
    DashboardSnapshot,
    DecisionSummary,
    LearningInsight,
    MetaReasoningSummary,
    ProviderRoutingSummary,
    ReliabilityPillarSummary,
)


# ---------------------------------------------------------------------------
# DecisionSummary
# ---------------------------------------------------------------------------


class TestDecisionSummary:
    def test_valid_summary(self) -> None:
        s = DecisionSummary(
            decision_id="ds-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality="success",
            actual_cost=90.0,
            estimated_cost=100.0,
            weight_changes=("risk: +0.005", "cost: -0.003"),
            decided_at="2026-03-20T00:00:00Z",
        )
        assert s.quality == "success"
        assert len(s.weight_changes) == 2

    def test_empty_decision_id_raises(self) -> None:
        with pytest.raises(ValueError, match="decision_id"):
            DecisionSummary(
                decision_id="",
                comparison_id="cmp-1",
                chosen_option_id="opt-a",
                quality="success",
                actual_cost=0.0,
                estimated_cost=0.0,
                weight_changes=(),
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_negative_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="actual_cost"):
            DecisionSummary(
                decision_id="ds-bad",
                comparison_id="cmp-1",
                chosen_option_id="opt-a",
                quality="success",
                actual_cost=-1.0,
                estimated_cost=0.0,
                weight_changes=(),
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_empty_weight_changes_ok(self) -> None:
        s = DecisionSummary(
            decision_id="ds-empty",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality="unknown",
            actual_cost=0.0,
            estimated_cost=0.0,
            weight_changes=(),
            decided_at="2026-03-20T00:00:00Z",
        )
        assert len(s.weight_changes) == 0


# ---------------------------------------------------------------------------
# ProviderRoutingSummary
# ---------------------------------------------------------------------------


class TestProviderRoutingSummary:
    def test_valid_summary(self) -> None:
        s = ProviderRoutingSummary(
            provider_id="prov-a",
            context_type="model",
            preference_score=0.8,
            health_score=0.9,
            routing_count=10,
            success_count=8,
            failure_count=2,
        )
        assert s.success_rate == 0.8

    def test_zero_routing_count_rate(self) -> None:
        s = ProviderRoutingSummary(
            provider_id="prov-b",
            context_type="model",
            preference_score=0.5,
            health_score=0.5,
            routing_count=0,
            success_count=0,
            failure_count=0,
        )
        assert s.success_rate == 0.0

    def test_preference_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="preference_score"):
            ProviderRoutingSummary(
                provider_id="prov-bad",
                context_type="model",
                preference_score=1.5,
                health_score=0.5,
                routing_count=0,
                success_count=0,
                failure_count=0,
            )

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="failure_count"):
            ProviderRoutingSummary(
                provider_id="prov-bad2",
                context_type="model",
                preference_score=0.5,
                health_score=0.5,
                routing_count=0,
                success_count=0,
                failure_count=-1,
            )


# ---------------------------------------------------------------------------
# LearningInsight
# ---------------------------------------------------------------------------


class TestLearningInsight:
    def test_valid_insight(self) -> None:
        i = LearningInsight(
            insight_id="li-1",
            factor_kind="risk",
            cumulative_delta=0.015,
            direction="improving",
            sample_count=5,
            explanation="risk factor weight increasing",
        )
        assert i.direction == "improving"

    def test_negative_delta_allowed(self) -> None:
        i = LearningInsight(
            insight_id="li-2",
            factor_kind="cost",
            cumulative_delta=-0.01,
            direction="declining",
            sample_count=3,
            explanation="cost factor weight decreasing",
        )
        assert i.cumulative_delta < 0

    def test_invalid_direction_raises(self) -> None:
        with pytest.raises(ValueError) as exc:
            LearningInsight(
                insight_id="li-bad",
                factor_kind="risk",
                cumulative_delta=0.0,
                direction="unknown",
                sample_count=0,
                explanation="bad direction",
            )
        assert str(exc.value) == "direction has unsupported value"
        assert "unknown" not in str(exc.value)
        assert "stable" not in str(exc.value)

    def test_nan_delta_raises(self) -> None:
        with pytest.raises(ValueError, match="cumulative_delta"):
            LearningInsight(
                insight_id="li-nan",
                factor_kind="risk",
                cumulative_delta=float("nan"),
                direction="stable",
                sample_count=0,
                explanation="nan delta",
            )

    def test_stable_direction(self) -> None:
        i = LearningInsight(
            insight_id="li-stable",
            factor_kind="confidence",
            cumulative_delta=0.0,
            direction="stable",
            sample_count=10,
            explanation="no change",
        )
        assert i.direction == "stable"


# ---------------------------------------------------------------------------
# DashboardSnapshot
# ---------------------------------------------------------------------------


class TestDashboardSnapshot:
    def test_valid_empty_snapshot(self) -> None:
        snap = DashboardSnapshot(
            snapshot_id="snap-1",
            captured_at="2026-03-20T00:00:00Z",
            total_decisions=0,
            total_routing_decisions=0,
            recent_decisions=(),
            provider_summaries=(),
            learning_insights=(),
        )
        assert snap.total_decisions == 0

    def test_snapshot_with_content(self) -> None:
        ds = DecisionSummary(
            decision_id="ds-1",
            comparison_id="cmp-1",
            chosen_option_id="opt-a",
            quality="success",
            actual_cost=90.0,
            estimated_cost=100.0,
            weight_changes=(),
            decided_at="2026-03-20T00:00:00Z",
        )
        ps = ProviderRoutingSummary(
            provider_id="prov-a",
            context_type="model",
            preference_score=0.8,
            health_score=0.9,
            routing_count=5,
            success_count=4,
            failure_count=1,
        )
        li = LearningInsight(
            insight_id="li-1",
            factor_kind="risk",
            cumulative_delta=0.01,
            direction="improving",
            sample_count=5,
            explanation="risk improving",
        )
        snap = DashboardSnapshot(
            snapshot_id="snap-2",
            captured_at="2026-03-20T00:00:00Z",
            total_decisions=1,
            total_routing_decisions=5,
            recent_decisions=(ds,),
            provider_summaries=(ps,),
            learning_insights=(li,),
        )
        assert len(snap.recent_decisions) == 1
        assert len(snap.provider_summaries) == 1
        assert len(snap.learning_insights) == 1

    def test_bad_decision_type_raises(self) -> None:
        with pytest.raises(ValueError, match="recent_decisions"):
            DashboardSnapshot(
                snapshot_id="snap-bad",
                captured_at="2026-03-20T00:00:00Z",
                total_decisions=0,
                total_routing_decisions=0,
                recent_decisions=("not-a-summary",),  # type: ignore[arg-type]
                provider_summaries=(),
                learning_insights=(),
            )

    def test_bad_provider_type_raises(self) -> None:
        with pytest.raises(ValueError, match="provider_summaries"):
            DashboardSnapshot(
                snapshot_id="snap-bad2",
                captured_at="2026-03-20T00:00:00Z",
                total_decisions=0,
                total_routing_decisions=0,
                recent_decisions=(),
                provider_summaries=("not-a-summary",),  # type: ignore[arg-type]
                learning_insights=(),
            )

    def test_bad_insight_type_raises(self) -> None:
        with pytest.raises(ValueError, match="learning_insights"):
            DashboardSnapshot(
                snapshot_id="snap-bad3",
                captured_at="2026-03-20T00:00:00Z",
                total_decisions=0,
                total_routing_decisions=0,
                recent_decisions=(),
                provider_summaries=(),
                learning_insights=("not-an-insight",),  # type: ignore[arg-type]
            )

    def test_negative_total_decisions_raises(self) -> None:
        with pytest.raises(ValueError, match="total_decisions"):
            DashboardSnapshot(
                snapshot_id="snap-neg",
                captured_at="2026-03-20T00:00:00Z",
                total_decisions=-1,
                total_routing_decisions=0,
                recent_decisions=(),
                provider_summaries=(),
                learning_insights=(),
            )


# ---------------------------------------------------------------------------
# Audit hardening (Phase 29C)
# ---------------------------------------------------------------------------


class TestAuditHardeningProviderRoutingSummary:
    """H3: Cross-field validation — success_count + failure_count <= routing_count."""

    def test_success_plus_failure_exceeds_routing_raises(self) -> None:
        with pytest.raises(ValueError, match="success_count.*failure_count.*must not exceed"):
            ProviderRoutingSummary(
                provider_id="prov-bad",
                context_type="model",
                preference_score=0.5,
                health_score=0.5,
                routing_count=5,
                success_count=3,
                failure_count=3,
            )

    def test_success_plus_failure_equals_routing_ok(self) -> None:
        s = ProviderRoutingSummary(
            provider_id="prov-exact",
            context_type="model",
            preference_score=0.5,
            health_score=0.5,
            routing_count=10,
            success_count=7,
            failure_count=3,
        )
        assert s.success_count + s.failure_count == s.routing_count

    def test_success_plus_failure_less_than_routing_ok(self) -> None:
        """Some routings may not yet have an outcome recorded."""
        s = ProviderRoutingSummary(
            provider_id="prov-partial",
            context_type="model",
            preference_score=0.5,
            health_score=0.5,
            routing_count=10,
            success_count=4,
            failure_count=2,
        )
        assert s.success_count + s.failure_count < s.routing_count

    def test_inf_health_score_raises(self) -> None:
        with pytest.raises(ValueError, match="health_score"):
            ProviderRoutingSummary(
                provider_id="prov-inf",
                context_type="model",
                preference_score=0.5,
                health_score=float("inf"),
                routing_count=0,
                success_count=0,
                failure_count=0,
            )

    def test_bool_routing_count_raises(self) -> None:
        with pytest.raises(ValueError, match="routing_count"):
            ProviderRoutingSummary(
                provider_id="prov-bool",
                context_type="model",
                preference_score=0.5,
                health_score=0.5,
                routing_count=True,  # type: ignore[arg-type]
                success_count=0,
                failure_count=0,
            )


class TestAuditHardeningDecisionSummary:
    """Additional edge-case validation for DecisionSummary."""

    def test_inf_estimated_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="estimated_cost"):
            DecisionSummary(
                decision_id="ds-inf",
                comparison_id="cmp-1",
                chosen_option_id="opt-a",
                quality="success",
                actual_cost=0.0,
                estimated_cost=float("inf"),
                weight_changes=(),
                decided_at="2026-03-20T00:00:00Z",
            )

    def test_invalid_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="decided_at"):
            DecisionSummary(
                decision_id="ds-bad-dt",
                comparison_id="cmp-1",
                chosen_option_id="opt-a",
                quality="success",
                actual_cost=0.0,
                estimated_cost=0.0,
                weight_changes=(),
                decided_at="not-a-date",
            )


class TestAuditHardeningLearningInsight:
    """Additional edge-case validation for LearningInsight."""

    def test_empty_factor_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="factor_kind"):
            LearningInsight(
                insight_id="li-empty-fk",
                factor_kind="",
                cumulative_delta=0.0,
                direction="stable",
                sample_count=0,
                explanation="empty factor",
            )

    def test_negative_sample_count_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_count"):
            LearningInsight(
                insight_id="li-neg-sc",
                factor_kind="risk",
                cumulative_delta=0.0,
                direction="stable",
                sample_count=-1,
                explanation="negative samples",
            )


# ---------------------------------------------------------------------------
# ReliabilityPillarSummary (Phase 30)
# ---------------------------------------------------------------------------

_TS = "2026-03-20T00:00:00Z"


class TestReliabilityPillarSummary:
    def test_valid_pillar(self) -> None:
        p = ReliabilityPillarSummary(
            pillar="simulation",
            confidence=0.8,
            recommendation="proceed",
            dominant_risk="simulation may not reflect reality",
        )
        assert p.pillar == "simulation"
        assert p.confidence == 0.8

    def test_empty_pillar_raises(self) -> None:
        with pytest.raises(ValueError, match="pillar"):
            ReliabilityPillarSummary(
                pillar="",
                confidence=0.5,
                recommendation="proceed",
                dominant_risk="risk",
            )

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ReliabilityPillarSummary(
                pillar="utility",
                confidence=1.5,
                recommendation="proceed",
                dominant_risk="risk",
            )

    def test_empty_recommendation_raises(self) -> None:
        with pytest.raises(ValueError, match="recommendation"):
            ReliabilityPillarSummary(
                pillar="learning",
                confidence=0.5,
                recommendation="",
                dominant_risk="risk",
            )


# ---------------------------------------------------------------------------
# MetaReasoningSummary (Phase 30)
# ---------------------------------------------------------------------------


def _meta_summary(
    *,
    summary_id: str = "ms-1",
    overall_confidence: float = 0.72,
    confidence_display: str = "0.72 [0.55 \u2013 0.89]",
    dominant_uncertainty: str = "simulation may not reflect reality",
    degraded_count: int = 0,
    replan_count: int = 0,
    escalation_count: int = 0,
    recommendation: str = "proceed",
    pillars: tuple[ReliabilityPillarSummary, ...] = (),
    assessed_at: str = _TS,
) -> MetaReasoningSummary:
    return MetaReasoningSummary(
        summary_id=summary_id,
        overall_confidence=overall_confidence,
        confidence_display=confidence_display,
        dominant_uncertainty=dominant_uncertainty,
        degraded_count=degraded_count,
        replan_count=replan_count,
        escalation_count=escalation_count,
        recommendation=recommendation,
        pillars=pillars,
        assessed_at=assessed_at,
    )


class TestMetaReasoningSummary:
    def test_valid_construction(self) -> None:
        s = _meta_summary()
        assert s.summary_id == "ms-1"
        assert s.overall_confidence == 0.72
        assert s.recommendation == "proceed"

    def test_with_pillars(self) -> None:
        p = ReliabilityPillarSummary(
            pillar="simulation",
            confidence=0.8,
            recommendation="proceed",
            dominant_risk="simulation may not reflect reality",
        )
        s = _meta_summary(pillars=(p,))
        assert len(s.pillars) == 1
        assert s.pillars[0].pillar == "simulation"

    def test_empty_summary_id_raises(self) -> None:
        with pytest.raises(ValueError, match="summary_id"):
            _meta_summary(summary_id="")

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="overall_confidence"):
            _meta_summary(overall_confidence=1.5)

    def test_negative_degraded_count_raises(self) -> None:
        with pytest.raises(ValueError, match="degraded_count"):
            _meta_summary(degraded_count=-1)

    def test_invalid_pillar_type_raises(self) -> None:
        with pytest.raises(ValueError, match="pillar"):
            _meta_summary(pillars=("not-a-pillar",))  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        s = _meta_summary()
        with pytest.raises(AttributeError):
            s.recommendation = "replan"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DashboardSnapshot with meta_reasoning (Phase 30)
# ---------------------------------------------------------------------------


class TestDashboardSnapshotMetaReasoning:
    def test_default_none(self) -> None:
        snap = DashboardSnapshot(
            snapshot_id="snap-no-meta",
            captured_at=_TS,
            total_decisions=0,
            total_routing_decisions=0,
            recent_decisions=(),
            provider_summaries=(),
            learning_insights=(),
        )
        assert snap.meta_reasoning is None

    def test_with_meta_reasoning(self) -> None:
        snap = DashboardSnapshot(
            snapshot_id="snap-meta",
            captured_at=_TS,
            total_decisions=0,
            total_routing_decisions=0,
            recent_decisions=(),
            provider_summaries=(),
            learning_insights=(),
            meta_reasoning=_meta_summary(),
        )
        assert snap.meta_reasoning is not None
        assert snap.meta_reasoning.overall_confidence == 0.72

    def test_invalid_meta_reasoning_type_raises(self) -> None:
        with pytest.raises(ValueError, match="meta_reasoning"):
            DashboardSnapshot(
                snapshot_id="snap-bad-meta",
                captured_at=_TS,
                total_decisions=0,
                total_routing_decisions=0,
                recent_decisions=(),
                provider_summaries=(),
                learning_insights=(),
                meta_reasoning="not-a-summary",  # type: ignore[arg-type]
            )
