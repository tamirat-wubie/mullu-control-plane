"""Purpose: verify meta-reasoning engine — confidence tracking, degraded mode,
uncertainty, health, decision reliability, and replan recommendations.
Governance scope: meta-reasoning plane tests only.
Dependencies: meta-reasoning contracts, meta-reasoning engine, signal contracts.
Invariants: confidence from history; uncertainty explicit; health deterministic.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.decision_learning import (
    AdjustmentType,
    DecisionAdjustment,
)
from mcoi_runtime.contracts.meta_reasoning import (
    CapabilityConfidence,
    EscalationRecommendation,
    EscalationSeverity,
    HealthStatus,
    ReplanReason,
    SubsystemHealth,
    UncertaintyReport,
    UncertaintySource,
)
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from mcoi_runtime.contracts.simulation import SimulationVerdict, VerdictType
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    OptionUtility,
    TradeoffDirection,
    UtilityProfile,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine


_CLOCK = "2026-03-19T00:00:00+00:00"


def _confidence(
    capability_id: str = "cap-1",
    success: float = 0.9,
    verify: float = 0.95,
    timeout: float = 0.05,
    error: float = 0.02,
    samples: int = 100,
) -> CapabilityConfidence:
    return CapabilityConfidence(
        capability_id=capability_id,
        success_rate=success,
        verification_pass_rate=verify,
        timeout_rate=timeout,
        error_rate=error,
        sample_count=samples,
        assessed_at=_CLOCK,
    )


# --- Confidence tests ---

def test_overall_confidence_computed() -> None:
    c = _confidence(success=0.9, verify=1.0, error=0.0)
    assert c.overall_confidence == 0.9


def test_overall_confidence_zero_samples() -> None:
    c = _confidence(samples=0)
    assert c.overall_confidence == 0.0


def test_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="success_rate"):
        _confidence(success=1.5)


def test_update_and_get_confidence() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    engine.update_confidence(_confidence("cap-1"))
    assert engine.get_confidence("cap-1") is not None


# --- Degraded mode tests ---

def test_degraded_mode_triggers_on_low_confidence() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.8)
    engine.update_confidence(_confidence("cap-1", success=0.3, verify=0.3, error=0.5))
    assert engine.is_degraded("cap-1") is True
    assert len(engine.list_degraded()) == 1
    degraded = engine.list_degraded()[0]
    assert degraded.reason == "confidence below threshold"
    assert "0." not in degraded.reason


def test_degraded_mode_exits_on_recovery() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.5)
    engine.update_confidence(_confidence("cap-1", success=0.2, verify=0.2, error=0.8))
    assert engine.is_degraded("cap-1") is True

    engine.update_confidence(_confidence("cap-1", success=0.95, verify=0.95, error=0.01))
    assert engine.is_degraded("cap-1") is False


def test_custom_threshold() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK, default_threshold=0.1)
    engine.set_threshold("cap-1", 0.95)
    engine.update_confidence(_confidence("cap-1", success=0.9, verify=0.9, error=0.0))
    # 0.9 * 0.9 * 1.0 = 0.81, below 0.95 threshold
    assert engine.is_degraded("cap-1") is True


# --- Uncertainty tests ---

def test_report_uncertainty() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    report = UncertaintyReport(
        report_id="u-1",
        subject="filesystem state",
        source=UncertaintySource.INCOMPLETE_OBSERVATION,
        description="only partial directory listing available",
        affected_ids=("e-1",),
        created_at=_CLOCK,
    )
    engine.report_uncertainty(report)
    assert len(engine.list_uncertainty()) == 1


def test_duplicate_uncertainty_rejected() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    report = UncertaintyReport(
        report_id="u-1", subject="s", source=UncertaintySource.LOW_CONFIDENCE,
        description="d", affected_ids=(), created_at=_CLOCK,
    )
    engine.report_uncertainty(report)
    with pytest.raises(RuntimeCoreInvariantError, match="uncertainty report already exists") as exc_info:
        engine.report_uncertainty(report)
    assert "u-1" not in str(exc_info.value)


# --- Escalation tests ---

def test_recommend_escalation() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    rec = EscalationRecommendation(
        recommendation_id="esc-1",
        reason="capability degraded",
        severity=EscalationSeverity.HIGH,
        affected_ids=("cap-1",),
        suggested_action="notify operator",
        created_at=_CLOCK,
    )
    engine.recommend_escalation(rec)
    assert len(engine.list_escalation_recommendations()) == 1


# --- Health assessment tests ---

def test_health_snapshot_healthy() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
        SubsystemHealth(subsystem="persistence", status=HealthStatus.HEALTHY, details="ok"),
    ))
    assert snapshot.overall_status is HealthStatus.HEALTHY


def test_health_snapshot_degraded() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
        SubsystemHealth(subsystem="integration", status=HealthStatus.DEGRADED, details="slow"),
    ))
    assert snapshot.overall_status is HealthStatus.DEGRADED


def test_health_snapshot_unavailable_trumps_degraded() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    snapshot = engine.assess_health((
        SubsystemHealth(subsystem="execution", status=HealthStatus.DEGRADED, details="slow"),
        SubsystemHealth(subsystem="persistence", status=HealthStatus.UNAVAILABLE, details="disk full"),
    ))
    assert snapshot.overall_status is HealthStatus.UNAVAILABLE


def test_health_snapshot_deterministic_id() -> None:
    engine = MetaReasoningEngine(clock=lambda: _CLOCK)
    checks = (
        SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
    )
    s1 = engine.assess_health(checks)
    s2 = engine.assess_health(checks)
    assert s1.snapshot_id == s2.snapshot_id


# ---------------------------------------------------------------------------
# Simulation confidence assessment
# ---------------------------------------------------------------------------

_TICK = 0


def _make_engine() -> MetaReasoningEngine:
    global _TICK
    _TICK = 0

    def clock() -> str:
        global _TICK
        _TICK += 1
        return f"2026-03-20T00:{_TICK // 60:02d}:{_TICK % 60:02d}Z"

    return MetaReasoningEngine(clock=clock)


def _make_verdict(
    confidence: float = 0.8,
    verdict_type: VerdictType = VerdictType.PROCEED,
) -> SimulationVerdict:
    return SimulationVerdict(
        verdict_id="sv-1",
        comparison_id="cmp-1",
        verdict_type=verdict_type,
        recommended_option_id="opt-a",
        confidence=confidence,
        reasons=("test reason",),
    )


def _make_comparison(spread: float = 0.2, option_count: int = 2) -> DecisionComparison:
    utilities = tuple(
        OptionUtility(
            option_id=f"opt-{i}",
            raw_score=round(0.8 - i * spread, 4) if 0.8 - i * spread >= 0.0 else 0.0,
            weighted_score=round(0.8 - i * spread, 4) if 0.8 - i * spread >= 0.0 else 0.0,
            factor_contributions={"risk": 0.3},
            rank=i + 1,
        )
        for i in range(option_count)
    )
    return DecisionComparison(
        comparison_id="cmp-1",
        profile_id="prof-1",
        option_utilities=utilities,
        best_option_id="opt-0",
        spread=spread,
        decided_at="2026-03-20T00:00:00Z",
    )


def _make_routing_outcome(
    provider_id: str = "prov-a",
    success: bool = True,
) -> RoutingOutcome:
    return RoutingOutcome(
        outcome_id=f"ro-{provider_id}-{success}",
        decision_id="rd-1",
        provider_id=provider_id,
        actual_cost=50.0,
        success=success,
        recorded_at="2026-03-20T00:00:01Z",
    )


def _make_adjustment(
    factor_kind: str = "risk",
    delta: float = 0.005,
) -> DecisionAdjustment:
    return DecisionAdjustment(
        adjustment_id=f"adj-{factor_kind}-{delta}",
        adjustment_type=AdjustmentType.WEIGHT_INCREASE if delta > 0 else AdjustmentType.WEIGHT_DECREASE,
        target_factor_kind=factor_kind,
        old_value=0.5,
        new_value=min(1.0, max(0.0, 0.5 + delta)),
        delta=delta,
        reason=f"test adjustment for {factor_kind}",
        created_at="2026-03-20T00:00:01Z",
    )


class TestSimulationConfidence:
    def test_high_confidence_proceeds(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.9))
        assert rel.recommendation == "proceed"
        assert rel.confidence_envelope.point_estimate >= 0.7

    def test_low_confidence_defers(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.3))
        assert rel.recommendation in ("defer_to_review", "replan")

    def test_escalate_verdict_penalizes(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.8, verdict_type=VerdictType.ESCALATE),
        )
        # 0.8 * 0.5 = 0.4, should trigger caution or defer
        assert rel.recommendation in ("proceed_with_caution", "defer_to_review")

    def test_abort_verdict_penalizes_heavily(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.6, verdict_type=VerdictType.ABORT),
        )
        # 0.6 * 0.5 = 0.3, should recommend replan or defer
        assert rel.recommendation in ("defer_to_review", "replan")

    def test_uncertainty_factors_populated(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.3),
            min_confidence=0.6,
        )
        assert rel.uncertainty_factors == ("low simulation confidence",)


# ---------------------------------------------------------------------------
# Utility ambiguity assessment
# ---------------------------------------------------------------------------


class TestUtilityAmbiguity:
    def test_high_spread_proceeds(self):
        engine = _make_engine()
        rel = engine.assess_utility_ambiguity(_make_comparison(spread=0.3))
        assert rel.recommendation == "proceed"

    def test_low_spread_caution(self):
        engine = _make_engine()
        rel = engine.assess_utility_ambiguity(_make_comparison(spread=0.01))
        assert rel.recommendation in ("proceed_with_caution", "defer_to_review")

    def test_zero_spread_ambiguous(self):
        engine = _make_engine()
        rel = engine.assess_utility_ambiguity(_make_comparison(spread=0.0))
        assert rel.decision_context == "utility"
        assert rel.uncertainty_factors == ("utility ambiguity detected",)


# ---------------------------------------------------------------------------
# Provider volatility assessment
# ---------------------------------------------------------------------------


class TestProviderVolatility:
    def test_all_successful_proceeds(self):
        engine = _make_engine()
        outcomes = (
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-a", True),
        )
        rel = engine.assess_provider_volatility(outcomes, ("prov-a",))
        assert rel.recommendation == "proceed"
        assert rel.confidence_envelope.point_estimate >= 0.7

    def test_high_failure_rate(self):
        engine = _make_engine()
        outcomes = (
            _make_routing_outcome("prov-a", False),
            _make_routing_outcome("prov-a", False),
            _make_routing_outcome("prov-a", True),
        )
        rel = engine.assess_provider_volatility(outcomes, ("prov-a",))
        assert rel.confidence_envelope.point_estimate < 0.7
        assert rel.uncertainty_factors == ("provider volatility detected",)

    def test_no_outcomes_neutral(self):
        engine = _make_engine()
        rel = engine.assess_provider_volatility((), ("prov-a",))
        assert rel.confidence_envelope.point_estimate == 0.5
        assert "no routing outcomes" in rel.uncertainty_factors[0]

    def test_mixed_providers(self):
        engine = _make_engine()
        outcomes = (
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-b", False),
        )
        rel = engine.assess_provider_volatility(outcomes, ("prov-a", "prov-b"))
        assert rel.uncertainty_factors == ("provider volatility detected",)


# ---------------------------------------------------------------------------
# Learning reliability assessment
# ---------------------------------------------------------------------------


class TestLearningReliability:
    def test_stable_small_adjustments(self):
        engine = _make_engine()
        adjs = tuple(_make_adjustment("risk", 0.003) for _ in range(10))
        rel = engine.assess_learning_reliability(adjs)
        assert rel.recommendation == "proceed"

    def test_large_swings_unreliable(self):
        engine = _make_engine()
        adjs = tuple(_make_adjustment("risk", 0.5) for _ in range(10))
        rel = engine.assess_learning_reliability(adjs, max_magnitude=0.1)
        assert rel.recommendation != "proceed"
        assert "learning adjustment exceeds limit" in rel.uncertainty_factors
        assert "learning adjustment instability detected" in rel.uncertainty_factors

    def test_few_samples_uncertain(self):
        engine = _make_engine()
        adjs = (_make_adjustment("risk", 0.01),)
        rel = engine.assess_learning_reliability(adjs, min_sample_count=5)
        assert "insufficient learning history" in rel.uncertainty_factors

    def test_no_adjustments_neutral(self):
        engine = _make_engine()
        rel = engine.assess_learning_reliability(())
        assert rel.confidence_envelope.point_estimate == 0.5
        assert "no adjustments" in rel.uncertainty_factors[0]


# ---------------------------------------------------------------------------
# Replan recommendations
# ---------------------------------------------------------------------------


class TestReplanRecommendations:
    def test_no_replan_when_confident(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.9))
        recs = engine.check_replan_needed((rel,), "goal-1")
        assert len(recs) == 0

    def test_replan_when_low_confidence(self):
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.1))
        recs = engine.check_replan_needed((rel,), "goal-1", replan_threshold=0.3)
        assert len(recs) >= 1
        assert recs[0].reason == ReplanReason.CONFIDENCE_TOO_LOW
        assert recs[0].affected_entity_id == "goal-1"
        assert recs[0].description == "replan threshold breached"

    def test_replan_maps_context_to_reason(self):
        engine = _make_engine()
        rel = engine.assess_utility_ambiguity(_make_comparison(spread=0.0))
        recs = engine.check_replan_needed((rel,), "goal-1", replan_threshold=0.5)
        if recs:
            assert recs[0].reason == ReplanReason.AMBIGUITY_TOO_HIGH

    def test_multiple_replans_from_multiple_signals(self):
        engine = _make_engine()
        r1 = engine.assess_simulation_confidence(_make_verdict(confidence=0.1))
        r2 = engine.assess_learning_reliability(())
        # r2 has point_estimate=0.5 which is above default threshold 0.3
        # but r1 should trigger replan
        recs = engine.check_replan_needed((r1, r2), "goal-1", replan_threshold=0.3)
        assert len(recs) >= 1


# ---------------------------------------------------------------------------
# Full meta-reasoning snapshot
# ---------------------------------------------------------------------------


class TestMetaSnapshot:
    def test_empty_snapshot(self):
        engine = _make_engine()
        checks = (SubsystemHealth(subsystem="exec", status=HealthStatus.HEALTHY, details="ok"),)
        snap = engine.meta_snapshot(checks)
        assert snap.overall_confidence == 0.5
        assert len(snap.degraded_capabilities) == 0
        assert len(snap.decision_reliabilities) == 0

    def test_snapshot_with_reliabilities(self):
        engine = _make_engine()
        checks = (SubsystemHealth(subsystem="exec", status=HealthStatus.HEALTHY, details="ok"),)
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.9))
        snap = engine.meta_snapshot(checks, reliabilities=(rel,))
        assert snap.overall_confidence >= 0.5
        assert len(snap.decision_reliabilities) == 1

    def test_snapshot_penalized_by_degradation(self):
        engine = _make_engine()
        engine.update_confidence(_confidence("cap-1", success=0.1, verify=0.1, error=0.9))
        checks = (SubsystemHealth(subsystem="exec", status=HealthStatus.DEGRADED, details="slow"),)
        snap = engine.meta_snapshot(checks)
        assert snap.overall_confidence < 0.5
        assert len(snap.degraded_capabilities) >= 1

    def test_snapshot_penalized_by_uncertainty(self):
        engine = _make_engine()
        engine.report_uncertainty(UncertaintyReport(
            report_id="u-1", subject="state", source=UncertaintySource.MISSING_EVIDENCE,
            description="missing data", affected_ids=(), created_at=_CLOCK,
        ))
        checks = (SubsystemHealth(subsystem="exec", status=HealthStatus.HEALTHY, details="ok"),)
        snap = engine.meta_snapshot(checks)
        assert snap.overall_confidence < 0.5
        assert len(snap.active_uncertainties) == 1

    def test_snapshot_includes_escalations(self):
        engine = _make_engine()
        engine.recommend_escalation(EscalationRecommendation(
            recommendation_id="esc-1", reason="test", severity=EscalationSeverity.HIGH,
            affected_ids=("cap-1",), suggested_action="notify", created_at=_CLOCK,
        ))
        checks = (SubsystemHealth(subsystem="exec", status=HealthStatus.HEALTHY, details="ok"),)
        snap = engine.meta_snapshot(checks)
        assert len(snap.escalation_recommendations) == 1


# ---------------------------------------------------------------------------
# Golden scenario
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    def test_full_meta_reasoning_lifecycle(self):
        """End-to-end: assess multiple signals, check replans, produce snapshot."""
        engine = _make_engine()

        # 1. Simulation with moderate confidence
        sim_rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.6, verdict_type=VerdictType.PROCEED_WITH_CAUTION),
        )

        # 2. Utility with reasonable spread
        util_rel = engine.assess_utility_ambiguity(_make_comparison(spread=0.15))

        # 3. Provider with some failures
        outcomes = (
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-a", True),
            _make_routing_outcome("prov-b", False),
        )
        prov_rel = engine.assess_provider_volatility(outcomes, ("prov-a", "prov-b"))

        # 4. Learning with small stable adjustments
        adjs = tuple(_make_adjustment("risk", 0.002) for _ in range(8))
        learn_rel = engine.assess_learning_reliability(adjs)

        # 5. Check if replan needed
        all_rels = (sim_rel, util_rel, prov_rel, learn_rel)
        replans = engine.check_replan_needed(all_rels, "goal-42")

        # 6. Record an uncertainty
        engine.report_uncertainty(UncertaintyReport(
            report_id="u-golden", subject="provider-b health",
            source=UncertaintySource.INCOMPLETE_OBSERVATION,
            description="prov-b has limited history",
            affected_ids=("prov-b",), created_at=_CLOCK,
        ))

        # 7. Full snapshot
        checks = (
            SubsystemHealth(subsystem="execution", status=HealthStatus.HEALTHY, details="ok"),
            SubsystemHealth(subsystem="routing", status=HealthStatus.HEALTHY, details="ok"),
        )
        snap = engine.meta_snapshot(
            checks,
            reliabilities=all_rels,
            replan_recommendations=replans,
        )

        # Verify comprehensive snapshot
        assert snap.health.overall_status == HealthStatus.HEALTHY
        assert len(snap.decision_reliabilities) == 4
        assert len(snap.active_uncertainties) == 1
        assert snap.overall_confidence > 0.0
        assert snap.overall_confidence <= 1.0
        # Each reliability has a valid recommendation
        for rel in snap.decision_reliabilities:
            assert rel.recommendation in ("proceed", "proceed_with_caution", "defer_to_review", "replan")
