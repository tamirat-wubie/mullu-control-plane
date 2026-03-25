"""Purpose: comprehensive tests for the UncertaintyRuntimeEngine.
Governance scope: runtime-core tests only.
Dependencies: uncertainty_runtime engine, event_spine, contracts, invariants.
Invariants: beliefs start PROVISIONAL, evidence weight auto-updates confidence,
    confidence intervals validated, violations are idempotent.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.uncertainty_runtime import UncertaintyRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.uncertainty_runtime import (
    BeliefRecord,
    BeliefStatus,
    BeliefUpdate,
    CompetingHypothesisSet,
    ConfidenceInterval,
    EvidenceWeight,
    EvidenceWeightRecord,
    HypothesisDisposition,
    UncertaintyAssessment,
    UncertaintyClosureReport,
    UncertaintyHypothesis,
    UncertaintySnapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> UncertaintyRuntimeEngine:
    return UncertaintyRuntimeEngine(spine)


@pytest.fixture()
def engine_with_belief(engine: UncertaintyRuntimeEngine) -> UncertaintyRuntimeEngine:
    engine.register_belief("b-1", "tenant-a", "test belief")
    return engine


@pytest.fixture()
def engine_with_hypothesis(engine_with_belief: UncertaintyRuntimeEngine) -> UncertaintyRuntimeEngine:
    engine_with_belief.register_hypothesis("h-1", "tenant-a", "b-1")
    return engine_with_belief


# ===================================================================
# SECTION 1: Constructor validation
# ===================================================================


class TestConstructorValidation:
    def test_valid_event_spine_accepted(self, spine: EventSpineEngine) -> None:
        eng = UncertaintyRuntimeEngine(spine)
        assert eng.belief_count == 0

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            UncertaintyRuntimeEngine(None)  # type: ignore[arg-type]


# ===================================================================
# SECTION 2: Belief registration
# ===================================================================


class TestBeliefRegistration:
    def test_register_belief_default_confidence(self, engine: UncertaintyRuntimeEngine) -> None:
        b = engine.register_belief("b-1", "t-1", "test")
        assert b.status == BeliefStatus.PROVISIONAL
        assert b.confidence == 0.5
        assert engine.belief_count == 1

    def test_register_belief_custom_confidence(self, engine: UncertaintyRuntimeEngine) -> None:
        b = engine.register_belief("b-1", "t-1", "test", confidence=0.8)
        assert b.confidence == 0.8

    def test_duplicate_belief_raises(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_belief.register_belief("b-1", "t-1", "dup")

    def test_get_belief(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        b = engine_with_belief.get_belief("b-1")
        assert b.belief_id == "b-1"

    def test_get_unknown_belief_raises(self, engine: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_belief("nonexistent")


# ===================================================================
# SECTION 3: Hypothesis registration
# ===================================================================


class TestHypothesisRegistration:
    def test_register_hypothesis(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        h = engine_with_belief.register_hypothesis("h-1", "t-1", "b-1")
        assert h.disposition == HypothesisDisposition.COMPETING
        assert engine_with_belief.hypothesis_count == 1

    def test_unknown_belief_ref_raises(self, engine: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_hypothesis("h-1", "t-1", "nonexistent")

    def test_duplicate_hypothesis_raises(self, engine_with_hypothesis: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_hypothesis.register_hypothesis("h-1", "t-1", "b-1")


# ===================================================================
# SECTION 4: Evidence weight
# ===================================================================


class TestEvidenceWeight:
    def test_register_evidence_weight_auto_updates_confidence(
        self, engine_with_belief: UncertaintyRuntimeEngine
    ) -> None:
        # Default confidence is 0.5, STRONG adds 0.2 -> 0.7
        wr = engine_with_belief.register_evidence_weight(
            "w-1", "t-1", "b-1", "e-1", weight=EvidenceWeight.STRONG,
        )
        assert wr.weight == EvidenceWeight.STRONG
        assert wr.impact == 0.2
        b = engine_with_belief.get_belief("b-1")
        assert b.confidence == pytest.approx(0.7)

    def test_decisive_weight(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        engine_with_belief.register_evidence_weight(
            "w-1", "t-1", "b-1", "e-1", weight=EvidenceWeight.DECISIVE,
        )
        b = engine_with_belief.get_belief("b-1")
        assert b.confidence == pytest.approx(0.8)

    def test_negligible_weight(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        engine_with_belief.register_evidence_weight(
            "w-1", "t-1", "b-1", "e-1", weight=EvidenceWeight.NEGLIGIBLE,
        )
        b = engine_with_belief.get_belief("b-1")
        assert b.confidence == pytest.approx(0.5)

    def test_confidence_clamped_at_1(self, engine: UncertaintyRuntimeEngine) -> None:
        engine.register_belief("b-1", "t-1", "test", confidence=0.9)
        engine.register_evidence_weight("w-1", "t-1", "b-1", "e-1", weight=EvidenceWeight.DECISIVE)
        b = engine.get_belief("b-1")
        assert b.confidence == 1.0

    def test_unknown_belief_raises(self, engine: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_evidence_weight("w-1", "t-1", "nonexistent", "e-1")


# ===================================================================
# SECTION 5: Confidence intervals
# ===================================================================


class TestConfidenceIntervals:
    def test_register_confidence_interval(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        ci = engine_with_belief.register_confidence_interval(
            "ci-1", "t-1", "b-1", lower=0.3, upper=0.7,
        )
        assert ci.lower == 0.3
        assert ci.upper == 0.7
        assert engine_with_belief.interval_count == 1

    def test_lower_greater_than_upper_raises(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_belief.register_confidence_interval(
                "ci-1", "t-1", "b-1", lower=0.8, upper=0.2,
            )


# ===================================================================
# SECTION 6: Belief updates
# ===================================================================


class TestBeliefUpdates:
    def test_update_belief(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        bu = engine_with_belief.update_belief(
            "u-1", "t-1", "b-1", "e-1", new_confidence=0.8,
        )
        assert bu.prior_confidence == 0.5
        assert bu.posterior_confidence == 0.8
        b = engine_with_belief.get_belief("b-1")
        assert b.confidence == 0.8
        assert engine_with_belief.update_count == 1


# ===================================================================
# SECTION 7: Competing hypothesis sets
# ===================================================================


class TestCompetingSets:
    def test_create_competing_set(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        engine_with_belief.register_hypothesis("h-1", "t-1", "b-1", posterior_confidence=0.7)
        engine_with_belief.register_hypothesis("h-2", "t-1", "b-1", posterior_confidence=0.3)
        cs = engine_with_belief.create_competing_set("s-1", "t-1", ["h-1", "h-2"])
        assert cs.hypothesis_count == 2
        assert cs.leading_hypothesis_ref == "h-1"

    def test_empty_hypothesis_ids_raises(self, engine: UncertaintyRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_competing_set("s-1", "t-1", [])


# ===================================================================
# SECTION 8: Ranking
# ===================================================================


class TestRanking:
    def test_rank_hypotheses(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        engine_with_belief.register_hypothesis("h-1", "t-1", "b-1", posterior_confidence=0.3)
        engine_with_belief.register_hypothesis("h-2", "t-1", "b-1", posterior_confidence=0.9)
        ranked = engine_with_belief.rank_hypotheses("b-1")
        assert len(ranked) == 2
        assert ranked[0].hypothesis_id == "h-2"


# ===================================================================
# SECTION 9: Assessment / Snapshot / Closure
# ===================================================================


class TestAssessmentSnapshotClosure:
    def test_uncertainty_assessment(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        a = engine_with_belief.uncertainty_assessment("a-1", "t-1")
        assert a.total_beliefs == 1
        assert a.avg_confidence == pytest.approx(0.5)

    def test_uncertainty_snapshot(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        snap = engine_with_belief.uncertainty_snapshot("snap-1", "t-1")
        assert snap.total_beliefs == 1
        assert snap.total_violations == 0

    def test_duplicate_snapshot_raises(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        engine_with_belief.uncertainty_snapshot("snap-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_belief.uncertainty_snapshot("snap-1", "t-1")

    def test_closure_report(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        r = engine_with_belief.uncertainty_closure_report("r-1", "t-1")
        assert r.total_beliefs == 1


# ===================================================================
# SECTION 10: Violations
# ===================================================================


class TestViolationDetection:
    def test_stale_belief_violation(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        violations = engine_with_belief.detect_uncertainty_violations()
        stale = [v for v in violations if v["operation"] == "stale_belief"]
        assert len(stale) >= 1

    def test_idempotent_violations(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        v1 = engine_with_belief.detect_uncertainty_violations()
        v2 = engine_with_belief.detect_uncertainty_violations()
        assert len(v2) == 0  # idempotent

    def test_zero_evidence_high_confidence(self, engine: UncertaintyRuntimeEngine) -> None:
        engine.register_belief("b-1", "t-1", "test", confidence=0.9)
        violations = engine.detect_uncertainty_violations()
        hi_conf = [v for v in violations if v["operation"] == "zero_evidence_high_confidence"]
        assert len(hi_conf) >= 1


# ===================================================================
# SECTION 11: State hash
# ===================================================================


class TestStateHash:
    def test_state_hash_changes(self, engine: UncertaintyRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.register_belief("b-1", "t-1", "test")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_method(self, engine_with_belief: UncertaintyRuntimeEngine) -> None:
        snap = engine_with_belief.snapshot()
        assert snap["beliefs"] == 1
