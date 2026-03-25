"""Tests for mcoi_runtime.core.dashboard — dashboard engine tests."""

from __future__ import annotations

from mcoi_runtime.contracts.dashboard import MetaReasoningSummary
from mcoi_runtime.contracts.decision_learning import (
    AdjustmentType,
    DecisionAdjustment,
    DecisionOutcomeRecord,
    OutcomeQuality,
)
from mcoi_runtime.contracts.meta_reasoning import (
    ConfidenceEnvelope,
    DecisionReliability,
    DegradedModeRecord,
    EscalationRecommendation,
    EscalationSeverity,
    HealthStatus,
    MetaReasoningSnapshot,
    ReplanReason,
    ReplanRecommendation,
    SelfHealthSnapshot,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from mcoi_runtime.core.dashboard import DashboardEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICK = 0


def _make_engine() -> DashboardEngine:
    global _TICK
    _TICK = 0

    def clock() -> str:
        global _TICK
        _TICK += 1
        return f"2026-03-20T00:{_TICK // 60:02d}:{_TICK % 60:02d}Z"

    return DashboardEngine(clock=clock)


def _make_outcome(
    outcome_id: str = "out-1",
    comparison_id: str = "cmp-1",
    quality: OutcomeQuality = OutcomeQuality.SUCCESS,
    actual_cost: float = 90.0,
    recorded_at: str = "2026-03-20T00:00:01Z",
) -> DecisionOutcomeRecord:
    return DecisionOutcomeRecord(
        outcome_id=outcome_id,
        comparison_id=comparison_id,
        chosen_option_id="opt-a",
        quality=quality,
        actual_cost=actual_cost,
        actual_duration_seconds=60.0,
        success_observed=quality == OutcomeQuality.SUCCESS,
        notes="test outcome",
        recorded_at=recorded_at,
    )


def _make_adjustment(
    factor_kind: str = "risk",
    delta: float = 0.005,
    created_at: str = "2026-03-20T00:00:01Z",
) -> DecisionAdjustment:
    return DecisionAdjustment(
        adjustment_id=f"adj-{factor_kind}",
        adjustment_type=AdjustmentType.WEIGHT_INCREASE if delta > 0 else AdjustmentType.WEIGHT_DECREASE,
        target_factor_kind=factor_kind,
        old_value=0.4,
        new_value=min(1.0, max(0.0, 0.4 + delta)),
        delta=delta,
        reason=f"test adjustment for {factor_kind}",
        created_at=created_at,
    )


def _make_routing_outcome(
    provider_id: str = "prov-a",
    success: bool = True,
) -> RoutingOutcome:
    return RoutingOutcome(
        outcome_id=f"ro-{provider_id}",
        decision_id="rd-1",
        provider_id=provider_id,
        actual_cost=50.0,
        success=success,
        recorded_at="2026-03-20T00:00:01Z",
    )


# ---------------------------------------------------------------------------
# build_decision_summaries
# ---------------------------------------------------------------------------


class TestBuildDecisionSummaries:
    def test_empty_outcomes(self):
        engine = _make_engine()
        result = engine.build_decision_summaries((), ())
        assert result == ()

    def test_single_outcome(self):
        engine = _make_engine()
        outcome = _make_outcome()
        result = engine.build_decision_summaries((outcome,), ())
        assert len(result) == 1
        assert result[0].quality == "success"
        assert result[0].comparison_id == "cmp-1"

    def test_outcome_with_matching_adjustment(self):
        engine = _make_engine()
        ts = "2026-03-20T00:00:01Z"
        outcome = _make_outcome(recorded_at=ts)
        adj = _make_adjustment(created_at=ts)
        result = engine.build_decision_summaries((outcome,), (adj,))
        assert len(result) == 1
        assert len(result[0].weight_changes) >= 1
        assert "risk" in result[0].weight_changes[0]

    def test_max_recent_limit(self):
        engine = _make_engine()
        outcomes = tuple(
            _make_outcome(
                outcome_id=f"out-{i}",
                comparison_id=f"cmp-{i}",
                recorded_at=f"2026-03-20T00:{i:02d}:00Z",
            )
            for i in range(1, 16)
        )
        result = engine.build_decision_summaries(outcomes, (), max_recent=5)
        assert len(result) == 5

    def test_most_recent_first(self):
        engine = _make_engine()
        o1 = _make_outcome(outcome_id="out-old", recorded_at="2026-03-20T00:00:01Z")
        o2 = _make_outcome(outcome_id="out-new", recorded_at="2026-03-20T00:00:02Z")
        result = engine.build_decision_summaries((o1, o2), ())
        # Most recent first
        assert result[0].decided_at == "2026-03-20T00:00:02Z"


# ---------------------------------------------------------------------------
# build_provider_summaries
# ---------------------------------------------------------------------------


class TestBuildProviderSummaries:
    def test_empty_outcomes(self):
        engine = _make_engine()
        result = engine.build_provider_summaries((), {}, ("prov-a",), {})
        assert len(result) == 1
        assert result[0].routing_count == 0

    def test_counts_successes_and_failures(self):
        engine = _make_engine()
        outcomes = (
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-a", False),
        )
        result = engine.build_provider_summaries(
            outcomes, {"prov-a": 0.8}, ("prov-a",), {"prov-a": 0.9},
        )
        assert len(result) == 1
        assert result[0].routing_count == 3
        assert result[0].success_count == 2
        assert result[0].failure_count == 1
        assert result[0].preference_score == 0.8
        assert result[0].health_score == 0.9

    def test_default_scores(self):
        engine = _make_engine()
        result = engine.build_provider_summaries((), {}, ("prov-x",), {})
        assert result[0].preference_score == 0.5  # default
        assert result[0].health_score == 0.3  # default

    def test_multiple_providers(self):
        engine = _make_engine()
        outcomes = (
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-b", False),
        )
        result = engine.build_provider_summaries(
            outcomes, {}, ("prov-a", "prov-b"), {},
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# build_learning_insights
# ---------------------------------------------------------------------------


class TestBuildLearningInsights:
    def test_empty_adjustments(self):
        engine = _make_engine()
        result = engine.build_learning_insights({})
        assert result == ()

    def test_improving_direction(self):
        engine = _make_engine()
        result = engine.build_learning_insights({"risk": 0.015})
        assert len(result) == 1
        assert result[0].direction == "improving"
        assert result[0].factor_kind == "risk"

    def test_declining_direction(self):
        engine = _make_engine()
        result = engine.build_learning_insights({"cost": -0.01})
        assert len(result) == 1
        assert result[0].direction == "declining"

    def test_stable_direction(self):
        engine = _make_engine()
        result = engine.build_learning_insights({"time": 0.0005})
        assert len(result) == 1
        assert result[0].direction == "stable"

    def test_multiple_factors(self):
        engine = _make_engine()
        result = engine.build_learning_insights({
            "risk": 0.02,
            "cost": -0.01,
            "time": 0.0,
        })
        assert len(result) == 3
        # Sorted by factor kind
        kinds = [r.factor_kind for r in result]
        assert kinds == sorted(kinds)


# ---------------------------------------------------------------------------
# Full snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_empty_snapshot(self):
        engine = _make_engine()
        snap = engine.snapshot(
            outcomes=(),
            adjustments=(),
            routing_outcomes=(),
            preferences={},
            provider_ids=(),
            health_scores={},
            learned_adjustments={},
            total_decisions=0,
            total_routing_decisions=0,
        )
        assert snap.total_decisions == 0
        assert snap.total_routing_decisions == 0
        assert len(snap.recent_decisions) == 0
        assert len(snap.provider_summaries) == 0
        assert len(snap.learning_insights) == 0

    def test_full_snapshot(self):
        engine = _make_engine()
        outcome = _make_outcome()
        adj = _make_adjustment()
        ro = _make_routing_outcome()

        snap = engine.snapshot(
            outcomes=(outcome,),
            adjustments=(adj,),
            routing_outcomes=(ro,),
            preferences={"prov-a": 0.8},
            provider_ids=("prov-a",),
            health_scores={"prov-a": 0.9},
            learned_adjustments={"risk": 0.005},
            total_decisions=1,
            total_routing_decisions=1,
        )
        assert snap.total_decisions == 1
        assert len(snap.recent_decisions) == 1
        assert len(snap.provider_summaries) == 1
        assert len(snap.learning_insights) == 1
        assert snap.learning_insights[0].direction == "improving"


# ---------------------------------------------------------------------------
# Golden scenario
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Audit hardening (Phase 29C)
# ---------------------------------------------------------------------------


class TestAuditHardening:
    def test_context_type_passthrough_in_provider_summaries(self):
        engine = _make_engine()
        result = engine.build_provider_summaries(
            (), {}, ("prov-a",), {}, context_type="model",
        )
        assert result[0].context_type == "model"

    def test_context_type_passthrough_in_snapshot(self):
        engine = _make_engine()
        snap = engine.snapshot(
            outcomes=(),
            adjustments=(),
            routing_outcomes=(),
            preferences={},
            provider_ids=("prov-a",),
            health_scores={},
            learned_adjustments={},
            total_decisions=0,
            total_routing_decisions=0,
            context_type="custom-ctx",
        )
        assert snap.provider_summaries[0].context_type == "custom-ctx"

    def test_default_context_type_is_aggregate(self):
        engine = _make_engine()
        result = engine.build_provider_summaries((), {}, ("prov-a",), {})
        assert result[0].context_type == "aggregate"

    def test_snapshot_default_context_type(self):
        engine = _make_engine()
        snap = engine.snapshot(
            outcomes=(),
            adjustments=(),
            routing_outcomes=(),
            preferences={},
            provider_ids=("prov-x",),
            health_scores={},
            learned_adjustments={},
            total_decisions=0,
            total_routing_decisions=0,
        )
        assert snap.provider_summaries[0].context_type == "aggregate"


# ---------------------------------------------------------------------------
# Golden scenario
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    def test_dashboard_reflects_learning_trajectory(self):
        """Multiple outcomes produce a snapshot showing learning direction."""
        engine = _make_engine()

        outcomes = (
            _make_outcome("out-1", "cmp-1", OutcomeQuality.FAILURE, 200.0, "2026-03-20T00:00:01Z"),
            _make_outcome("out-2", "cmp-2", OutcomeQuality.FAILURE, 180.0, "2026-03-20T00:00:02Z"),
            _make_outcome("out-3", "cmp-3", OutcomeQuality.SUCCESS, 80.0, "2026-03-20T00:00:03Z"),
        )
        adjustments = (
            _make_adjustment("risk", -0.0075, "2026-03-20T00:00:01Z"),
            _make_adjustment("risk", -0.0075, "2026-03-20T00:00:02Z"),
            _make_adjustment("risk", 0.005, "2026-03-20T00:00:03Z"),
        )

        snap = engine.snapshot(
            outcomes=outcomes,
            adjustments=adjustments,
            routing_outcomes=(),
            preferences={},
            provider_ids=(),
            health_scores={},
            learned_adjustments={"risk": -0.01},
            total_decisions=3,
            total_routing_decisions=0,
        )

        assert snap.total_decisions == 3
        assert len(snap.recent_decisions) == 3
        # Risk declining overall
        risk_insight = snap.learning_insights[0]
        assert risk_insight.factor_kind == "risk"
        assert risk_insight.direction == "declining"


# ---------------------------------------------------------------------------
# Meta-reasoning dashboard surfacing (Phase 30)
# ---------------------------------------------------------------------------

_META_TS = "2026-03-20T00:00:00Z"


def _meta_health() -> SelfHealthSnapshot:
    return SelfHealthSnapshot(
        snapshot_id="health-1",
        subsystems=(
            SubsystemHealth(
                subsystem="persistence",
                status=HealthStatus.HEALTHY,
                details="All OK",
            ),
        ),
        assessed_at=_META_TS,
    )


def _meta_envelope(
    *, point: float = 0.8, lower: float = 0.65, upper: float = 0.95,
) -> ConfidenceEnvelope:
    return ConfidenceEnvelope(
        assessment_id="env-1",
        subject="simulation",
        point_estimate=point,
        lower_bound=lower,
        upper_bound=upper,
        sample_count=10,
        assessed_at=_META_TS,
    )


def _meta_reliability(
    *, context: str = "simulation", point: float = 0.8,
    recommendation: str = "proceed", dominant_risk: str = "risk-a",
) -> DecisionReliability:
    return DecisionReliability(
        reliability_id=f"rel-{context}",
        decision_context=context,
        confidence_envelope=_meta_envelope(
            point=point,
            lower=max(0.0, point - 0.15),
            upper=min(1.0, point + 0.15),
        ),
        uncertainty_factors=("factor-a",),
        dominant_risk=dominant_risk,
        recommendation=recommendation,
        assessed_at=_META_TS,
    )


def _meta_snapshot(
    *,
    reliabilities: tuple[DecisionReliability, ...] = (),
    degraded: tuple[DegradedModeRecord, ...] = (),
    uncertainties: tuple[UncertaintyReport, ...] = (),
    replans: tuple[ReplanRecommendation, ...] = (),
    escalations: tuple[EscalationRecommendation, ...] = (),
    overall_confidence: float = 0.75,
) -> MetaReasoningSnapshot:
    return MetaReasoningSnapshot(
        snapshot_id="meta-snap-1",
        captured_at=_META_TS,
        health=_meta_health(),
        degraded_capabilities=degraded,
        active_uncertainties=uncertainties,
        decision_reliabilities=reliabilities,
        replan_recommendations=replans,
        escalation_recommendations=escalations,
        overall_confidence=overall_confidence,
    )


class TestBuildMetaReasoningSummary:
    def test_minimal_snapshot_no_pillars(self) -> None:
        engine = _make_engine()
        snap = _meta_snapshot()
        summary = engine.build_meta_reasoning_summary(snap)
        assert isinstance(summary, MetaReasoningSummary)
        assert summary.overall_confidence == 0.75
        assert summary.pillars == ()
        assert summary.recommendation == "proceed"
        assert summary.dominant_uncertainty == "none identified"

    def test_with_pillars(self) -> None:
        engine = _make_engine()
        rels = (
            _meta_reliability(context="simulation", point=0.8, recommendation="proceed"),
            _meta_reliability(context="utility", point=0.6, recommendation="proceed_with_caution"),
        )
        snap = _meta_snapshot(reliabilities=rels)
        summary = engine.build_meta_reasoning_summary(snap)
        assert len(summary.pillars) == 2
        # Confidence display should contain the overall value and a range
        assert "0.75" in summary.confidence_display
        assert "\u2013" in summary.confidence_display  # en-dash

    def test_worst_pillar_determines_recommendation(self) -> None:
        engine = _make_engine()
        rels = (
            _meta_reliability(context="simulation", point=0.8, recommendation="proceed"),
            _meta_reliability(context="utility", point=0.2, recommendation="replan"),
        )
        snap = _meta_snapshot(reliabilities=rels)
        summary = engine.build_meta_reasoning_summary(snap)
        assert summary.recommendation == "replan"

    def test_replan_recommendations_override(self) -> None:
        engine = _make_engine()
        replan = ReplanRecommendation(
            recommendation_id="rpl-1",
            reason=ReplanReason.SLA_RISK,
            description="SLA breach imminent",
            affected_entity_id="goal-42",
            severity=EscalationSeverity.HIGH,
            confidence_at_assessment=0.4,
            created_at=_META_TS,
        )
        snap = _meta_snapshot(
            reliabilities=(_meta_reliability(),),
            replans=(replan,),
        )
        summary = engine.build_meta_reasoning_summary(snap)
        assert summary.recommendation == "replan"
        assert summary.replan_count == 1

    def test_escalation_recommendations_override(self) -> None:
        engine = _make_engine()
        esc = EscalationRecommendation(
            recommendation_id="esc-1",
            reason="repeated failures",
            severity=EscalationSeverity.HIGH,
            affected_ids=("cap-1",),
            suggested_action="notify operator",
            created_at=_META_TS,
        )
        snap = _meta_snapshot(escalations=(esc,))
        summary = engine.build_meta_reasoning_summary(snap)
        assert summary.recommendation == "escalate"
        assert summary.escalation_count == 1

    def test_degraded_count(self) -> None:
        engine = _make_engine()
        degraded = DegradedModeRecord(
            record_id="deg-1",
            capability_id="cap-1",
            reason="low success rate",
            confidence_at_entry=0.3,
            threshold=0.5,
            entered_at=_META_TS,
        )
        snap = _meta_snapshot(degraded=(degraded,))
        summary = engine.build_meta_reasoning_summary(snap)
        assert summary.degraded_count == 1

    def test_uncertainty_as_dominant(self) -> None:
        engine = _make_engine()
        unc = UncertaintyReport(
            report_id="unc-1",
            subject="model-accuracy",
            source=UncertaintySource.LOW_CONFIDENCE,
            description="Model accuracy below threshold",
            affected_ids=("cap-1",),
            created_at=_META_TS,
        )
        snap = _meta_snapshot(uncertainties=(unc,))
        summary = engine.build_meta_reasoning_summary(snap)
        assert summary.dominant_uncertainty == "Model accuracy below threshold"


class TestSnapshotWithMetaReasoning:
    def test_snapshot_without_meta(self) -> None:
        engine = _make_engine()
        snap = engine.snapshot(
            outcomes=(),
            adjustments=(),
            routing_outcomes=(),
            preferences={},
            provider_ids=(),
            health_scores={},
            learned_adjustments={},
            total_decisions=0,
            total_routing_decisions=0,
        )
        assert snap.meta_reasoning is None

    def test_snapshot_with_meta(self) -> None:
        engine = _make_engine()
        meta = _meta_snapshot(
            reliabilities=(_meta_reliability(),),
        )
        snap = engine.snapshot(
            outcomes=(),
            adjustments=(),
            routing_outcomes=(),
            preferences={},
            provider_ids=(),
            health_scores={},
            learned_adjustments={},
            total_decisions=0,
            total_routing_decisions=0,
            meta_snapshot=meta,
        )
        assert snap.meta_reasoning is not None
        assert isinstance(snap.meta_reasoning, MetaReasoningSummary)
        assert snap.meta_reasoning.overall_confidence == 0.75
