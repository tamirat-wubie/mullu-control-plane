"""Tests for epistemic runtime engine (~200 tests).

Covers: EpistemicRuntimeEngine lifecycle, claims, evidence sources, trust
    assessment, source reliability, claim conflicts, epistemic assessment,
    snapshot, closure, violation detection, state_hash, golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.epistemic_runtime import (
    KnowledgeClaim,
    EvidenceSource,
    TrustAssessment,
    SourceReliabilityRecord,
    ClaimConflict,
    EpistemicAssessment,
    EpistemicViolation,
    EpistemicSnapshot,
    EpistemicClosureReport,
    KnowledgeStatus,
    EvidenceOrigin,
    TrustLevel,
    AssertionMode,
    ConflictDisposition,
)
from mcoi_runtime.core.epistemic_runtime import EpistemicRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

_T1 = "t1"
_T2 = "t2"


def _make_engine(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    eng = EpistemicRuntimeEngine(es, clock=clk)
    return eng, es


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_valid(self):
        eng, _ = _make_engine()
        assert eng.claim_count == 0
        assert eng.source_count == 0
        assert eng.assessment_count == 0
        assert eng.reliability_update_count == 0
        assert eng.conflict_count == 0
        assert eng.decision_count == 0
        assert eng.violation_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeEngine("bad")

    def test_none_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeEngine(None)

    def test_custom_clock(self):
        clk = FixedClock("2026-06-01T00:00:00+00:00")
        eng, _ = _make_engine(clock=clk)
        c = eng.register_claim("cl1", _T1, "fact")
        assert c.created_at == "2026-06-01T00:00:00+00:00"

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = EpistemicRuntimeEngine(es, clock=None)
        assert eng.claim_count == 0


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


class TestClaims:
    def test_register(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "knowledge fact")
        assert c.claim_id == "cl1"
        assert c.status is KnowledgeStatus.REPORTED
        assert c.trust_level is TrustLevel.MODERATE

    def test_register_with_status(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.PROVEN)
        assert c.status is KnowledgeStatus.PROVEN
        assert c.trust_level is TrustLevel.VERIFIED

    def test_register_observed_trust(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        assert c.trust_level is TrustLevel.VERIFIED

    def test_register_inferred_trust(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.INFERRED)
        assert c.trust_level is TrustLevel.HIGH

    def test_register_simulated_trust(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.SIMULATED)
        assert c.trust_level is TrustLevel.LOW

    def test_register_retracted_trust(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.RETRACTED)
        assert c.trust_level is TrustLevel.UNTRUSTED

    def test_register_with_confidence(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", confidence=0.9)
        assert c.confidence == 0.9

    def test_register_with_assertion_mode(self):
        eng, _ = _make_engine()
        c = eng.register_claim("cl1", _T1, "fact", assertion_mode=AssertionMode.HYPOTHETICAL)
        assert c.assertion_mode is AssertionMode.HYPOTHETICAL

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_claim("cl1", _T1, "fact")

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.claim_count == 0
        eng.register_claim("cl1", _T1, "fact")
        assert eng.claim_count == 1

    def test_get_claim(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        c = eng.get_claim("cl1")
        assert c.claim_id == "cl1"

    def test_get_claim_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_claim("missing")

    def test_claims_for_tenant(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact1")
        eng.register_claim("cl2", _T2, "fact2")
        claims = eng.claims_for_tenant(_T1)
        assert len(claims) == 1
        assert claims[0].claim_id == "cl1"

    def test_claims_by_status(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact1", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "fact2", status=KnowledgeStatus.PROVEN)
        reported = eng.claims_by_status(_T1, KnowledgeStatus.REPORTED)
        assert len(reported) == 1

    def test_retract_claim(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        retracted = eng.retract_claim("cl1")
        assert retracted.status is KnowledgeStatus.RETRACTED
        assert retracted.trust_level is TrustLevel.UNTRUSTED

    def test_retract_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.retract_claim("missing")

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        assert es.event_count >= 1


# ---------------------------------------------------------------------------
# Evidence sources
# ---------------------------------------------------------------------------


class TestEvidenceSources:
    def test_register(self):
        eng, _ = _make_engine()
        s = eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        assert s.source_id == "src1"
        assert s.origin is EvidenceOrigin.INSTRUMENT
        assert s.reliability_score == 0.7

    def test_register_with_reliability(self):
        eng, _ = _make_engine()
        s = eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.9)
        assert s.reliability_score == 0.9

    def test_all_origins(self):
        eng, _ = _make_engine()
        for i, origin in enumerate(EvidenceOrigin):
            s = eng.register_evidence_source(f"src{i}", _T1, f"S{i}", origin)
            assert s.origin is origin

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)

    def test_count_increments(self):
        eng, _ = _make_engine()
        assert eng.source_count == 0
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        assert eng.source_count == 1

    def test_get_source(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        s = eng.get_source("src1")
        assert s.source_id == "src1"

    def test_get_source_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_source("missing")

    def test_sources_for_tenant(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.INSTRUMENT)
        eng.register_evidence_source("src2", _T2, "S2", EvidenceOrigin.INSTRUMENT)
        sources = eng.sources_for_tenant(_T1)
        assert len(sources) == 1


# ---------------------------------------------------------------------------
# Source reliability
# ---------------------------------------------------------------------------


class TestSourceReliability:
    def test_update(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.5)
        r = eng.update_source_reliability("rel1", _T1, "src1", 0.8, "improved")
        assert r.previous_score == 0.5
        assert r.updated_score == 0.8

    def test_updates_source(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.5)
        eng.update_source_reliability("rel1", _T1, "src1", 0.8, "improved")
        s = eng.get_source("src1")
        assert s.reliability_score == 0.8

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        eng.update_source_reliability("rel1", _T1, "src1", 0.8, "improved")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.update_source_reliability("rel1", _T1, "src1", 0.9, "again")

    def test_unknown_source_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.update_source_reliability("rel1", _T1, "missing", 0.8, "fail")

    def test_count_increments(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        assert eng.reliability_update_count == 0
        eng.update_source_reliability("rel1", _T1, "src1", 0.8, "improved")
        assert eng.reliability_update_count == 1


# ---------------------------------------------------------------------------
# Trust assessment
# ---------------------------------------------------------------------------


class TestTrustAssessmentEngine:
    def test_assess(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", confidence=0.8)
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.9)
        a = eng.assess_trust("ta1", _T1, "cl1", "src1")
        assert a.assessment_id == "ta1"
        assert a.confidence == pytest.approx(0.72, abs=0.01)

    def test_trust_level_derived(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", confidence=0.9)
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.9)
        a = eng.assess_trust("ta1", _T1, "cl1", "src1")
        # 0.9 * 0.9 = 0.81 -> VERIFIED
        assert a.trust_level is TrustLevel.VERIFIED

    def test_low_combined_trust(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", confidence=0.3)
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.3)
        a = eng.assess_trust("ta1", _T1, "cl1", "src1")
        # 0.3 * 0.3 = 0.09 -> UNTRUSTED
        assert a.trust_level is TrustLevel.UNTRUSTED

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        eng.assess_trust("ta1", _T1, "cl1", "src1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.assess_trust("ta1", _T1, "cl1", "src1")

    def test_unknown_claim_rejected(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.assess_trust("ta1", _T1, "missing", "src1")

    def test_unknown_source_rejected(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.assess_trust("ta1", _T1, "cl1", "missing")

    def test_count_increments(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT)
        assert eng.assessment_count == 0
        eng.assess_trust("ta1", _T1, "cl1", "src1")
        assert eng.assessment_count == 1


# ---------------------------------------------------------------------------
# Claim conflict detection
# ---------------------------------------------------------------------------


class TestClaimConflicts:
    def test_no_conflicts_clean(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) == 0

    def test_conflict_same_content_different_status(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) >= 1

    def test_conflict_idempotent(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        first = eng.detect_claim_conflicts(_T1)
        assert len(first) >= 1
        second = eng.detect_claim_conflicts(_T1)
        assert len(second) == 0

    def test_conflict_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T2, "same", status=KnowledgeStatus.PROVEN)
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) == 0

    def test_retracted_claims_excluded(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.retract_claim("cl2")
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) == 0

    def test_resolve_conflict(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) >= 1
        resolved = eng.resolve_conflict(conflicts[0].conflict_id,
                                        ConflictDisposition.FIRST_WINS, "cl1 preferred")
        assert resolved.disposition is ConflictDisposition.FIRST_WINS

    def test_resolve_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.resolve_conflict("missing", ConflictDisposition.FIRST_WINS, "basis")

    def test_conflict_count_increments(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        assert eng.conflict_count == 0
        eng.detect_claim_conflicts(_T1)
        assert eng.conflict_count >= 1


# ---------------------------------------------------------------------------
# Epistemic assessment
# ---------------------------------------------------------------------------


class TestEpistemicAssessmentEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        a = eng.epistemic_assessment("ea1", _T1)
        assert a.total_claims == 0
        assert a.avg_trust == 0.0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", confidence=0.8)
        eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.INSTRUMENT, reliability_score=0.9)
        a = eng.epistemic_assessment("ea1", _T1)
        assert a.total_claims == 1
        assert a.total_sources == 1

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact1")
        eng.register_claim("cl2", _T2, "fact2")
        a = eng.epistemic_assessment("ea1", _T1)
        assert a.total_claims == 1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestEpistemicSnapshotEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        s = eng.epistemic_snapshot("es1", _T1)
        assert s.total_claims == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.INSTRUMENT)
        s = eng.epistemic_snapshot("es1", _T1)
        assert s.total_claims == 1
        assert s.total_sources == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        snap = eng.snapshot()
        assert "claims" in snap
        assert "_state_hash" in snap


# ---------------------------------------------------------------------------
# Closure report
# ---------------------------------------------------------------------------


class TestEpistemicClosureEngine:
    def test_empty(self):
        eng, _ = _make_engine()
        r = eng.epistemic_closure_report("er1", _T1)
        assert r.total_claims == 0

    def test_with_data(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact")
        r = eng.epistemic_closure_report("er1", _T1)
        assert r.total_claims == 1


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


class TestEpistemicViolations:
    def test_no_violations_clean(self):
        eng, _ = _make_engine()
        viols = eng.detect_epistemic_violations(_T1)
        assert len(viols) == 0

    def test_insufficient_basis_violation(self):
        eng, _ = _make_engine()
        # OBSERVED claim gets VERIFIED trust, but no assessment
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        viols = eng.detect_epistemic_violations(_T1)
        assert any(v.operation == "insufficient_basis" for v in viols)

    def test_unresolved_conflict_violation(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        eng.detect_claim_conflicts(_T1)
        viols = eng.detect_epistemic_violations(_T1)
        assert any(v.operation == "unresolved_conflict" for v in viols)

    def test_untrusted_source_high_claim_violation(self):
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "Bad", EvidenceOrigin.EXTERNAL_SOURCE, reliability_score=0.2)
        eng.register_claim("cl1", _T1, "fact", confidence=0.9, source_ref="src1")
        viols = eng.detect_epistemic_violations(_T1)
        assert any(v.operation == "untrusted_source_high_claim" for v in viols)

    def test_violation_idempotent(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        first = eng.detect_epistemic_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_epistemic_violations(_T1)
        assert len(second) == 0

    def test_violation_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        viols = eng.detect_epistemic_violations(_T2)
        assert len(viols) == 0

    def test_violation_count_increments(self):
        eng, _ = _make_engine()
        assert eng.violation_count == 0
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        eng.detect_epistemic_violations(_T1)
        assert eng.violation_count >= 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestEpistemicStateHash:
    def test_empty_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_on_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_claim("cl1", _T1, "fact")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_64_chars(self):
        eng, _ = _make_engine()
        assert len(eng.state_hash()) == 64

    def test_deterministic_same_ops(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        eng1.register_claim("cl1", _T1, "fact")
        eng2.register_claim("cl1", _T1, "fact")
        assert eng1.state_hash() == eng2.state_hash()

    def test_includes_sources(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.INSTRUMENT)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_violations(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        h1 = eng.state_hash()
        eng.detect_epistemic_violations(_T1)
        h2 = eng.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Golden scenarios
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        eng, es = _make_engine()
        eng.register_evidence_source("src1", _T1, "Sensor", EvidenceOrigin.INSTRUMENT, reliability_score=0.9)
        c = eng.register_claim("cl1", _T1, "measurement", confidence=0.8, source_ref="src1")
        a = eng.assess_trust("ta1", _T1, "cl1", "src1")
        assert a.trust_level is TrustLevel.HIGH  # 0.8 * 0.9 = 0.72
        ea = eng.epistemic_assessment("ea1", _T1)
        assert ea.total_claims == 1
        assert ea.total_sources == 1
        snap = eng.epistemic_snapshot("es1", _T1)
        assert snap.total_assessments == 1
        report = eng.epistemic_closure_report("er1", _T1)
        assert report.total_claims == 1
        assert es.event_count > 0

    def test_cross_tenant_isolation(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact1")
        eng.register_claim("cl2", _T2, "fact2")
        snap1 = eng.epistemic_snapshot("es1", _T1)
        snap2 = eng.epistemic_snapshot("es2", _T2)
        assert snap1.total_claims == 1
        assert snap2.total_claims == 1

    def test_claim_synced_golden(self):
        """Claim registered, source registered, trust assessed."""
        eng, _ = _make_engine()
        eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.DIRECT_OBSERVATION, reliability_score=0.95)
        eng.register_claim("cl1", _T1, "observation", confidence=0.9, source_ref="src1",
                           status=KnowledgeStatus.OBSERVED)
        a = eng.assess_trust("ta1", _T1, "cl1", "src1")
        # 0.9 * 0.95 = 0.855 -> VERIFIED
        assert a.trust_level is TrustLevel.VERIFIED

    def test_violation_detection_idempotency_golden(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "fact", status=KnowledgeStatus.OBSERVED)
        first = eng.detect_epistemic_violations(_T1)
        assert len(first) >= 1
        second = eng.detect_epistemic_violations(_T1)
        assert len(second) == 0

    def test_state_hash_determinism_golden(self):
        clk1 = FixedClock()
        clk2 = FixedClock()
        eng1, _ = _make_engine(clock=clk1)
        eng2, _ = _make_engine(clock=clk2)
        for eng in (eng1, eng2):
            eng.register_claim("cl1", _T1, "fact")
            eng.register_evidence_source("src1", _T1, "S1", EvidenceOrigin.INSTRUMENT)
        assert eng1.state_hash() == eng2.state_hash()

    def test_conflict_resolution_golden(self):
        eng, _ = _make_engine()
        eng.register_claim("cl1", _T1, "same", status=KnowledgeStatus.REPORTED)
        eng.register_claim("cl2", _T1, "same", status=KnowledgeStatus.PROVEN)
        conflicts = eng.detect_claim_conflicts(_T1)
        assert len(conflicts) >= 1
        resolved = eng.resolve_conflict(
            conflicts[0].conflict_id,
            ConflictDisposition.SECOND_WINS,
            "proven claim preferred"
        )
        assert resolved.disposition is ConflictDisposition.SECOND_WINS
