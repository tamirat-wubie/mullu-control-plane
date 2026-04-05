"""Tests for MetaReasoningBridge — meta-reasoning integration bridge.

Covers: assess_decision_pillars, assess_and_replan, full_meta_snapshot,
        assess_before_routing, assess_before_recovery,
        escalate_from_reliability, report_uncertainty_from_reliability.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.decision_learning import (
    AdjustmentType,
    DecisionAdjustment,
)
from mcoi_runtime.contracts.meta_reasoning import (
    DecisionReliability,
    EscalationRecommendation,
    HealthStatus,
    MetaReasoningSnapshot,
    ReplanRecommendation,
    SubsystemHealth,
    UncertaintyReport,
)
from mcoi_runtime.contracts.provider_routing import RoutingOutcome
from mcoi_runtime.contracts.simulation import SimulationVerdict, VerdictType
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    OptionUtility,
)
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.meta_reasoning_integration import MetaReasoningBridge

_TS = "2026-03-20T00:00:00Z"


# --- helpers ----------------------------------------------------------------


def _make_engine() -> MetaReasoningEngine:
    return MetaReasoningEngine(clock=lambda: _TS, default_threshold=0.5)


def _make_verdict(
    *,
    confidence: float = 0.8,
    verdict_type: VerdictType = VerdictType.PROCEED,
) -> SimulationVerdict:
    return SimulationVerdict(
        verdict_id="v-1",
        comparison_id="cmp-1",
        verdict_type=verdict_type,
        recommended_option_id="opt-1",
        confidence=confidence,
        reasons=("reason-1",),
    )


def _make_comparison(*, spread: float = 0.25) -> DecisionComparison:
    util_a = OptionUtility(
        option_id="opt-1",
        raw_score=0.9,
        weighted_score=0.9,
        factor_contributions={"risk": 0.9},
        rank=1,
    )
    util_b = OptionUtility(
        option_id="opt-2",
        raw_score=max(0.0, 0.9 - spread),
        weighted_score=max(0.0, 0.9 - spread),
        factor_contributions={"risk": max(0.0, 0.9 - spread)},
        rank=2,
    )
    return DecisionComparison(
        comparison_id="dc-1",
        profile_id="prof-1",
        option_utilities=(util_a, util_b),
        best_option_id="opt-1",
        spread=spread,
        decided_at=_TS,
    )


def _make_routing_outcome(
    *, provider_id: str = "prov-1", success: bool = True,
) -> RoutingOutcome:
    return RoutingOutcome(
        outcome_id=f"ro-{provider_id}-{success}",
        decision_id="rd-1",
        provider_id=provider_id,
        actual_cost=1.0,
        success=success,
        recorded_at=_TS,
    )


def _make_adjustment(*, delta: float = 0.02) -> DecisionAdjustment:
    return DecisionAdjustment(
        adjustment_id=f"adj-{delta}",
        adjustment_type=AdjustmentType.WEIGHT_INCREASE,
        target_factor_kind="risk",
        old_value=0.5,
        new_value=0.5 + delta,
        delta=delta,
        reason="test adjustment",
        created_at=_TS,
    )


def _subsystem_checks() -> tuple[SubsystemHealth, ...]:
    return (
        SubsystemHealth(
            subsystem="persistence",
            status=HealthStatus.HEALTHY,
            details="All OK",
        ),
    )


# ---------------------------------------------------------------------------
# assess_decision_pillars
# ---------------------------------------------------------------------------


class TestAssessDecisionPillars:
    def test_no_inputs_returns_empty(self) -> None:
        engine = _make_engine()
        result = MetaReasoningBridge.assess_decision_pillars(engine)
        assert result == ()

    def test_simulation_only(self) -> None:
        engine = _make_engine()
        result = MetaReasoningBridge.assess_decision_pillars(
            engine, sim_verdict=_make_verdict(),
        )
        assert len(result) == 1
        assert result[0].decision_context == "simulation"

    def test_utility_only(self) -> None:
        engine = _make_engine()
        result = MetaReasoningBridge.assess_decision_pillars(
            engine, util_comparison=_make_comparison(),
        )
        assert len(result) == 1
        assert result[0].decision_context == "utility"

    def test_all_four_pillars(self) -> None:
        engine = _make_engine()
        result = MetaReasoningBridge.assess_decision_pillars(
            engine,
            sim_verdict=_make_verdict(),
            util_comparison=_make_comparison(),
            routing_outcomes=(
                _make_routing_outcome(success=True),
                _make_routing_outcome(success=False),
            ),
            provider_ids=("prov-1",),
            learning_adjustments=(
                _make_adjustment(delta=0.01),
                _make_adjustment(delta=0.02),
            ),
        )
        assert len(result) == 4
        contexts = {r.decision_context for r in result}
        assert contexts == {"simulation", "utility", "provider_routing", "learning"}

    def test_routing_without_outcomes_skipped(self) -> None:
        engine = _make_engine()
        result = MetaReasoningBridge.assess_decision_pillars(
            engine,
            routing_outcomes=(),
            provider_ids=("prov-1",),
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# assess_and_replan
# ---------------------------------------------------------------------------


class TestAssessAndReplan:
    def test_high_confidence_no_replan(self) -> None:
        engine = _make_engine()
        reliabilities, replans = MetaReasoningBridge.assess_and_replan(
            engine,
            "goal-42",
            sim_verdict=_make_verdict(confidence=0.9),
        )
        assert len(reliabilities) == 1
        assert replans == ()

    def test_low_confidence_triggers_replan(self) -> None:
        engine = _make_engine()
        reliabilities, replans = MetaReasoningBridge.assess_and_replan(
            engine,
            "goal-42",
            sim_verdict=_make_verdict(
                confidence=0.2,
                verdict_type=VerdictType.ABORT,
            ),
        )
        assert len(reliabilities) == 1
        assert len(replans) >= 1
        assert replans[0].affected_entity_id == "goal-42"

    def test_multiple_low_pillars(self) -> None:
        engine = _make_engine()
        reliabilities, replans = MetaReasoningBridge.assess_and_replan(
            engine,
            "goal-99",
            sim_verdict=_make_verdict(
                confidence=0.1, verdict_type=VerdictType.ABORT,
            ),
            util_comparison=_make_comparison(spread=0.001),
        )
        assert len(reliabilities) == 2
        # At least one replan because sim confidence is very low
        assert len(replans) >= 1


# ---------------------------------------------------------------------------
# full_meta_snapshot
# ---------------------------------------------------------------------------


class TestFullMetaSnapshot:
    def test_minimal_snapshot(self) -> None:
        engine = _make_engine()
        snap = MetaReasoningBridge.full_meta_snapshot(
            engine,
            _subsystem_checks(),
        )
        assert isinstance(snap, MetaReasoningSnapshot)
        assert snap.decision_reliabilities == ()
        assert snap.replan_recommendations == ()
        assert snap.overall_confidence == 0.5  # neutral

    def test_snapshot_with_all_pillars(self) -> None:
        engine = _make_engine()
        snap = MetaReasoningBridge.full_meta_snapshot(
            engine,
            _subsystem_checks(),
            sim_verdict=_make_verdict(confidence=0.9),
            util_comparison=_make_comparison(spread=0.3),
            routing_outcomes=(
                _make_routing_outcome(success=True),
                _make_routing_outcome(success=True),
            ),
            provider_ids=("prov-1",),
            learning_adjustments=(
                _make_adjustment(delta=0.01),
                _make_adjustment(delta=0.02),
            ),
            affected_entity_id="goal-77",
        )
        assert isinstance(snap, MetaReasoningSnapshot)
        assert len(snap.decision_reliabilities) == 4
        assert snap.overall_confidence > 0.0

    def test_snapshot_with_degraded_capability(self) -> None:
        engine = _make_engine()
        # Force a degraded capability by recording low confidence
        from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence

        engine.update_confidence(CapabilityConfidence(
            capability_id="cap-1",
            success_rate=0.3,
            verification_pass_rate=0.5,
            timeout_rate=0.0,
            error_rate=0.3,
            sample_count=10,
            assessed_at=_TS,
        ))
        snap = MetaReasoningBridge.full_meta_snapshot(
            engine,
            _subsystem_checks(),
        )
        assert len(snap.degraded_capabilities) == 1
        # Overall confidence penalized
        assert snap.overall_confidence < 0.5


# ---------------------------------------------------------------------------
# assess_before_routing
# ---------------------------------------------------------------------------


class TestAssessBeforeRouting:
    def test_stable_providers(self) -> None:
        engine = _make_engine()
        outcomes = tuple(
            _make_routing_outcome(success=True) for _ in range(5)
        )
        rel = MetaReasoningBridge.assess_before_routing(
            engine, outcomes, ("prov-1",),
        )
        assert rel.decision_context == "provider_routing"
        assert rel.confidence_envelope.point_estimate >= 0.7

    def test_volatile_providers(self) -> None:
        engine = _make_engine()
        outcomes = tuple(
            _make_routing_outcome(success=False) for _ in range(5)
        )
        rel = MetaReasoningBridge.assess_before_routing(
            engine, outcomes, ("prov-1",),
        )
        assert rel.confidence_envelope.point_estimate <= 0.3


# ---------------------------------------------------------------------------
# assess_before_recovery
# ---------------------------------------------------------------------------


class TestAssessBeforeRecovery:
    def test_confident_recovery(self) -> None:
        engine = _make_engine()
        rel = MetaReasoningBridge.assess_before_recovery(
            engine, _make_verdict(confidence=0.9),
        )
        assert rel.recommendation == "proceed"

    def test_uncertain_recovery(self) -> None:
        engine = _make_engine()
        rel = MetaReasoningBridge.assess_before_recovery(
            engine,
            _make_verdict(confidence=0.2, verdict_type=VerdictType.ESCALATE),
        )
        assert rel.recommendation in ("defer_to_review", "replan")


# ---------------------------------------------------------------------------
# escalate_from_reliability
# ---------------------------------------------------------------------------


class TestEscalateFromReliability:
    def test_no_escalation_for_high_confidence(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.9))
        result = MetaReasoningBridge.escalate_from_reliability(
            engine, (rel,), ("cap-1",),
        )
        assert result == ()
        assert engine.list_escalation_recommendations() == ()

    def test_escalation_for_low_confidence(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.1, verdict_type=VerdictType.ABORT),
        )
        result = MetaReasoningBridge.escalate_from_reliability(
            engine, (rel,), ("cap-1",),
        )
        assert len(result) == 1
        assert isinstance(result[0], EscalationRecommendation)
        assert result[0].reason == "confidence below escalation threshold"
        assert "simulation" not in result[0].reason
        # Verify recorded in engine
        assert len(engine.list_escalation_recommendations()) == 1

    def test_custom_threshold(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.5))
        # With threshold=0.9, even moderate confidence triggers escalation
        result = MetaReasoningBridge.escalate_from_reliability(
            engine, (rel,), ("cap-1",), escalation_threshold=0.9,
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# report_uncertainty_from_reliability
# ---------------------------------------------------------------------------


class TestReportUncertaintyFromReliability:
    def test_no_uncertainty_for_high_confidence(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.9))
        result = MetaReasoningBridge.report_uncertainty_from_reliability(
            engine, (rel,), ("cap-1",),
        )
        assert result == ()
        assert engine.list_uncertainty() == ()

    def test_uncertainty_for_low_confidence(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.1, verdict_type=VerdictType.ABORT),
        )
        result = MetaReasoningBridge.report_uncertainty_from_reliability(
            engine, (rel,), ("cap-1",),
        )
        assert len(result) == 1
        assert isinstance(result[0], UncertaintyReport)
        # Verify recorded in engine
        assert len(engine.list_uncertainty()) == 1

    def test_custom_threshold(self) -> None:
        engine = _make_engine()
        rel = engine.assess_simulation_confidence(_make_verdict(confidence=0.6))
        # With threshold=0.9, moderate confidence triggers uncertainty
        result = MetaReasoningBridge.report_uncertainty_from_reliability(
            engine, (rel,), ("cap-1",), uncertainty_threshold=0.9,
        )
        assert len(result) == 1

    def test_multiple_reliabilities(self) -> None:
        engine = _make_engine()
        rel_sim = engine.assess_simulation_confidence(
            _make_verdict(confidence=0.1, verdict_type=VerdictType.ABORT),
        )
        rel_util = engine.assess_utility_ambiguity(
            _make_comparison(spread=0.001),
        )
        result = MetaReasoningBridge.report_uncertainty_from_reliability(
            engine, (rel_sim, rel_util), ("cap-1",),
        )
        # At least the simulation one should trigger
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Golden scenario: full pipeline
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    def test_full_pipeline_assess_escalate_snapshot(self) -> None:
        """End-to-end: assess pillars → escalate → report uncertainty → snapshot."""
        engine = _make_engine()

        # Step 1: Assess all pillars with mixed confidence
        reliabilities = MetaReasoningBridge.assess_decision_pillars(
            engine,
            sim_verdict=_make_verdict(confidence=0.9),
            util_comparison=_make_comparison(spread=0.001),  # ambiguous
        )
        assert len(reliabilities) == 2

        # Step 2: Escalate any low-reliability pillars
        escalations = MetaReasoningBridge.escalate_from_reliability(
            engine, reliabilities, ("goal-42",), escalation_threshold=0.5,
        )

        # Step 3: Report uncertainty
        uncertainties = MetaReasoningBridge.report_uncertainty_from_reliability(
            engine, reliabilities, ("goal-42",), uncertainty_threshold=0.5,
        )

        # Step 4: Full snapshot
        snap = MetaReasoningBridge.full_meta_snapshot(
            engine,
            _subsystem_checks(),
            sim_verdict=_make_verdict(confidence=0.9),
            affected_entity_id="goal-42",
        )
        assert isinstance(snap, MetaReasoningSnapshot)
        # Snapshot should reflect the escalations and uncertainties we recorded
        assert len(snap.escalation_recommendations) == len(escalations)
        assert len(snap.active_uncertainties) == len(uncertainties)
