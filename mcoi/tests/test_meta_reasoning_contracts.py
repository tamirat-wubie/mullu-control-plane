"""Tests for mcoi_runtime.contracts.meta_reasoning — new meta-reasoning contract types.

Covers: ReplanReason, ConfidenceEnvelope, DecisionReliability,
        ReplanRecommendation, MetaReasoningSnapshot.
"""

from __future__ import annotations

import pytest

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

_TS = "2026-03-20T00:00:00Z"


# --- helpers ----------------------------------------------------------------

def _envelope(
    *,
    assessment_id: str = "env-1",
    subject: str = "model-accuracy",
    point_estimate: float = 0.8,
    lower_bound: float = 0.7,
    upper_bound: float = 0.9,
    sample_count: int = 50,
    assessed_at: str = _TS,
) -> ConfidenceEnvelope:
    return ConfidenceEnvelope(
        assessment_id=assessment_id,
        subject=subject,
        point_estimate=point_estimate,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        sample_count=sample_count,
        assessed_at=assessed_at,
    )


def _reliability(
    *,
    reliability_id: str = "rel-1",
    decision_context: str = "provider-selection",
    confidence_envelope: ConfidenceEnvelope | None = None,
    uncertainty_factors: tuple[str, ...] = ("latency-variance",),
    dominant_risk: str = "provider-downtime",
    recommendation: str = "proceed",
    assessed_at: str = _TS,
) -> DecisionReliability:
    return DecisionReliability(
        reliability_id=reliability_id,
        decision_context=decision_context,
        confidence_envelope=confidence_envelope or _envelope(),
        uncertainty_factors=uncertainty_factors,
        dominant_risk=dominant_risk,
        recommendation=recommendation,
        assessed_at=assessed_at,
    )


def _replan(
    *,
    recommendation_id: str = "rpl-1",
    reason: ReplanReason = ReplanReason.SLA_RISK,
    description: str = "SLA breach imminent",
    affected_entity_id: str = "goal-42",
    severity: EscalationSeverity = EscalationSeverity.HIGH,
    confidence_at_assessment: float = 0.4,
    created_at: str = _TS,
) -> ReplanRecommendation:
    return ReplanRecommendation(
        recommendation_id=recommendation_id,
        reason=reason,
        description=description,
        affected_entity_id=affected_entity_id,
        severity=severity,
        confidence_at_assessment=confidence_at_assessment,
        created_at=created_at,
    )


def _health_snapshot() -> SelfHealthSnapshot:
    return SelfHealthSnapshot(
        snapshot_id="health-1",
        subsystems=(
            SubsystemHealth(
                subsystem="persistence",
                status=HealthStatus.HEALTHY,
                details="All OK",
            ),
        ),
        assessed_at=_TS,
    )


def _escalation() -> EscalationRecommendation:
    return EscalationRecommendation(
        recommendation_id="esc-1",
        reason="repeated failures",
        severity=EscalationSeverity.MEDIUM,
        affected_ids=("cap-1",),
        suggested_action="notify operator",
        created_at=_TS,
    )


def _uncertainty() -> UncertaintyReport:
    return UncertaintyReport(
        report_id="unc-1",
        subject="model-accuracy",
        source=UncertaintySource.LOW_CONFIDENCE,
        description="Confidence below threshold",
        affected_ids=("cap-1",),
        created_at=_TS,
    )


def _degraded() -> DegradedModeRecord:
    return DegradedModeRecord(
        record_id="deg-1",
        capability_id="cap-1",
        reason="low success rate",
        confidence_at_entry=0.3,
        threshold=0.5,
        entered_at=_TS,
    )


# ---------------------------------------------------------------------------
# ReplanReason
# ---------------------------------------------------------------------------


class TestReplanReason:
    def test_all_members_exist(self) -> None:
        expected = {
            "CONFIDENCE_TOO_LOW",
            "AMBIGUITY_TOO_HIGH",
            "PROVIDER_VOLATILITY",
            "SLA_RISK",
            "LEARNING_UNRELIABLE",
            "SUBSYSTEM_DEGRADED",
            "MULTIPLE_FAILURES",
        }
        assert {m.name for m in ReplanReason} == expected

    def test_values_are_strings(self) -> None:
        for member in ReplanReason:
            assert isinstance(member.value, str)


# ---------------------------------------------------------------------------
# ConfidenceEnvelope
# ---------------------------------------------------------------------------


class TestConfidenceEnvelope:
    def test_valid_construction(self) -> None:
        e = _envelope()
        assert e.assessment_id == "env-1"
        assert e.point_estimate == 0.8
        assert e.lower_bound == 0.7
        assert e.upper_bound == 0.9
        assert e.sample_count == 50

    def test_empty_assessment_id_raises(self) -> None:
        with pytest.raises(ValueError, match="assessment_id"):
            _envelope(assessment_id="")

    def test_empty_subject_raises(self) -> None:
        with pytest.raises(ValueError, match="subject"):
            _envelope(subject="")

    def test_point_estimate_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="point_estimate"):
            _envelope(point_estimate=1.1)

    def test_point_estimate_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="point_estimate"):
            _envelope(point_estimate=-0.1)

    def test_lower_bound_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_bound"):
            _envelope(lower_bound=1.5)

    def test_upper_bound_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="upper_bound"):
            _envelope(upper_bound=-0.01)

    def test_negative_sample_count_raises(self) -> None:
        with pytest.raises(ValueError, match="sample_count"):
            _envelope(sample_count=-1)

    def test_lower_exceeds_point_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_bound.*point_estimate"):
            _envelope(lower_bound=0.85, point_estimate=0.8, upper_bound=0.9)

    def test_point_exceeds_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="point_estimate.*upper_bound"):
            _envelope(point_estimate=0.95, lower_bound=0.7, upper_bound=0.9)

    def test_boundary_equality_allowed(self) -> None:
        e = _envelope(lower_bound=0.5, point_estimate=0.5, upper_bound=0.5)
        assert e.lower_bound == e.point_estimate == e.upper_bound

    def test_frozen(self) -> None:
        e = _envelope()
        with pytest.raises(AttributeError):
            e.point_estimate = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DecisionReliability
# ---------------------------------------------------------------------------


class TestDecisionReliability:
    def test_valid_construction(self) -> None:
        r = _reliability()
        assert r.reliability_id == "rel-1"
        assert r.decision_context == "provider-selection"
        assert r.recommendation == "proceed"

    def test_empty_reliability_id_raises(self) -> None:
        with pytest.raises(ValueError, match="reliability_id"):
            _reliability(reliability_id="")

    def test_empty_decision_context_raises(self) -> None:
        with pytest.raises(ValueError, match="decision_context"):
            _reliability(decision_context="")

    def test_empty_dominant_risk_raises(self) -> None:
        with pytest.raises(ValueError, match="dominant_risk"):
            _reliability(dominant_risk="")

    def test_invalid_recommendation_string_raises(self) -> None:
        with pytest.raises(ValueError, match="recommendation"):
            _reliability(recommendation="abort")

    def test_all_valid_recommendations_accepted(self) -> None:
        for rec in ("proceed", "proceed_with_caution", "defer_to_review", "replan"):
            r = _reliability(recommendation=rec)
            assert r.recommendation == rec

    def test_non_envelope_type_raises(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            DecisionReliability(
                reliability_id="rel-bad",
                decision_context="ctx",
                confidence_envelope="not-an-envelope",  # type: ignore[arg-type]
                uncertainty_factors=(),
                dominant_risk="risk",
                recommendation="proceed",
                assessed_at=_TS,
            )

    def test_frozen(self) -> None:
        r = _reliability()
        with pytest.raises(AttributeError):
            r.recommendation = "replan"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ReplanRecommendation
# ---------------------------------------------------------------------------


class TestReplanRecommendation:
    def test_valid_construction(self) -> None:
        r = _replan()
        assert r.recommendation_id == "rpl-1"
        assert r.reason == ReplanReason.SLA_RISK
        assert r.severity == EscalationSeverity.HIGH
        assert r.confidence_at_assessment == 0.4

    def test_empty_recommendation_id_raises(self) -> None:
        with pytest.raises(ValueError, match="recommendation_id"):
            _replan(recommendation_id="")

    def test_empty_description_raises(self) -> None:
        with pytest.raises(ValueError, match="description"):
            _replan(description="")

    def test_empty_affected_entity_id_raises(self) -> None:
        with pytest.raises(ValueError, match="affected_entity_id"):
            _replan(affected_entity_id="")

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence_at_assessment"):
            _replan(confidence_at_assessment=1.01)

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence_at_assessment"):
            _replan(confidence_at_assessment=-0.01)

    def test_invalid_reason_enum_raises(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            _replan(reason="not_a_reason")  # type: ignore[arg-type]

    def test_invalid_severity_enum_raises(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            _replan(severity="extreme")  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        r = _replan()
        with pytest.raises(AttributeError):
            r.severity = EscalationSeverity.LOW  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MetaReasoningSnapshot
# ---------------------------------------------------------------------------


class TestMetaReasoningSnapshot:
    def test_valid_construction(self) -> None:
        s = MetaReasoningSnapshot(
            snapshot_id="snap-1",
            captured_at=_TS,
            health=_health_snapshot(),
            degraded_capabilities=(_degraded(),),
            active_uncertainties=(_uncertainty(),),
            decision_reliabilities=(_reliability(),),
            replan_recommendations=(_replan(),),
            escalation_recommendations=(_escalation(),),
            overall_confidence=0.75,
        )
        assert s.snapshot_id == "snap-1"
        assert s.overall_confidence == 0.75
        assert len(s.decision_reliabilities) == 1
        assert len(s.replan_recommendations) == 1

    def test_empty_snapshot_id_raises(self) -> None:
        with pytest.raises(ValueError, match="snapshot_id"):
            MetaReasoningSnapshot(
                snapshot_id="",
                captured_at=_TS,
                health=_health_snapshot(),
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=(),
                replan_recommendations=(),
                escalation_recommendations=(),
                overall_confidence=0.5,
            )

    def test_overall_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="overall_confidence"):
            MetaReasoningSnapshot(
                snapshot_id="snap-bad",
                captured_at=_TS,
                health=_health_snapshot(),
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=(),
                replan_recommendations=(),
                escalation_recommendations=(),
                overall_confidence=1.5,
            )

    def test_overall_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="overall_confidence"):
            MetaReasoningSnapshot(
                snapshot_id="snap-bad2",
                captured_at=_TS,
                health=_health_snapshot(),
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=(),
                replan_recommendations=(),
                escalation_recommendations=(),
                overall_confidence=-0.1,
            )

    def test_invalid_health_type_raises(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            MetaReasoningSnapshot(
                snapshot_id="snap-bad3",
                captured_at=_TS,
                health="not-a-snapshot",  # type: ignore[arg-type]
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=(),
                replan_recommendations=(),
                escalation_recommendations=(),
                overall_confidence=0.5,
            )

    def test_invalid_element_in_decision_reliabilities_raises(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            MetaReasoningSnapshot(
                snapshot_id="snap-bad4",
                captured_at=_TS,
                health=_health_snapshot(),
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=("not-a-reliability",),  # type: ignore[arg-type]
                replan_recommendations=(),
                escalation_recommendations=(),
                overall_confidence=0.5,
            )

    def test_invalid_element_in_replan_recommendations_raises(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            MetaReasoningSnapshot(
                snapshot_id="snap-bad5",
                captured_at=_TS,
                health=_health_snapshot(),
                degraded_capabilities=(),
                active_uncertainties=(),
                decision_reliabilities=(),
                replan_recommendations=(42,),  # type: ignore[arg-type]
                escalation_recommendations=(),
                overall_confidence=0.5,
            )

    def test_empty_tuples_accepted(self) -> None:
        s = MetaReasoningSnapshot(
            snapshot_id="snap-empty",
            captured_at=_TS,
            health=_health_snapshot(),
            degraded_capabilities=(),
            active_uncertainties=(),
            decision_reliabilities=(),
            replan_recommendations=(),
            escalation_recommendations=(),
            overall_confidence=0.0,
        )
        assert s.decision_reliabilities == ()
        assert s.replan_recommendations == ()

    def test_frozen(self) -> None:
        s = MetaReasoningSnapshot(
            snapshot_id="snap-frozen",
            captured_at=_TS,
            health=_health_snapshot(),
            degraded_capabilities=(),
            active_uncertainties=(),
            decision_reliabilities=(),
            replan_recommendations=(),
            escalation_recommendations=(),
            overall_confidence=0.5,
        )
        with pytest.raises(AttributeError):
            s.overall_confidence = 0.9  # type: ignore[misc]
