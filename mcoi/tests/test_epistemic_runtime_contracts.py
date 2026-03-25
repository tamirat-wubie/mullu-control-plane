"""Tests for epistemic runtime contracts (~200 tests).

Covers: KnowledgeClaim, EvidenceSource, TrustAssessment, SourceReliabilityRecord,
    ClaimConflict, EpistemicDecision, EpistemicAssessment, EpistemicViolation,
    EpistemicSnapshot, EpistemicClosureReport, and all enums.
"""

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.epistemic_runtime import (
    KnowledgeClaim,
    EvidenceSource,
    TrustAssessment,
    SourceReliabilityRecord,
    ClaimConflict,
    EpistemicDecision,
    EpistemicAssessment,
    EpistemicViolation,
    EpistemicSnapshot,
    EpistemicClosureReport,
    KnowledgeStatus,
    EvidenceOrigin,
    TrustLevel,
    AssertionMode,
    ConflictDisposition,
    EpistemicRiskLevel,
)

_NOW = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestKnowledgeStatusEnum:
    def test_values(self):
        assert KnowledgeStatus.OBSERVED.value == "observed"
        assert KnowledgeStatus.INFERRED.value == "inferred"
        assert KnowledgeStatus.SIMULATED.value == "simulated"
        assert KnowledgeStatus.REPORTED.value == "reported"
        assert KnowledgeStatus.PROVEN.value == "proven"
        assert KnowledgeStatus.RETRACTED.value == "retracted"

    def test_member_count(self):
        assert len(KnowledgeStatus) == 6


class TestEvidenceOriginEnum:
    def test_values(self):
        assert EvidenceOrigin.DIRECT_OBSERVATION.value == "direct_observation"
        assert EvidenceOrigin.INSTRUMENT.value == "instrument"
        assert EvidenceOrigin.HUMAN_REPORT.value == "human_report"
        assert EvidenceOrigin.SYSTEM_LOG.value == "system_log"
        assert EvidenceOrigin.INFERENCE.value == "inference"
        assert EvidenceOrigin.SIMULATION.value == "simulation"
        assert EvidenceOrigin.EXTERNAL_SOURCE.value == "external_source"

    def test_member_count(self):
        assert len(EvidenceOrigin) == 7


class TestTrustLevelEnum:
    def test_values(self):
        assert TrustLevel.VERIFIED.value == "verified"
        assert TrustLevel.HIGH.value == "high"
        assert TrustLevel.MODERATE.value == "moderate"
        assert TrustLevel.LOW.value == "low"
        assert TrustLevel.UNTRUSTED.value == "untrusted"
        assert TrustLevel.UNKNOWN.value == "unknown"

    def test_member_count(self):
        assert len(TrustLevel) == 6


class TestAssertionModeEnum:
    def test_values(self):
        assert AssertionMode.FACTUAL.value == "factual"
        assert AssertionMode.HYPOTHETICAL.value == "hypothetical"
        assert AssertionMode.CONDITIONAL.value == "conditional"
        assert AssertionMode.SPECULATIVE.value == "speculative"

    def test_member_count(self):
        assert len(AssertionMode) == 4


class TestConflictDispositionEnum:
    def test_values(self):
        assert ConflictDisposition.UNRESOLVED.value == "unresolved"
        assert ConflictDisposition.FIRST_WINS.value == "first_wins"
        assert ConflictDisposition.SECOND_WINS.value == "second_wins"
        assert ConflictDisposition.MERGED.value == "merged"
        assert ConflictDisposition.DEFERRED.value == "deferred"

    def test_member_count(self):
        assert len(ConflictDisposition) == 5


class TestEpistemicRiskLevelEnum:
    def test_values(self):
        assert EpistemicRiskLevel.LOW.value == "low"
        assert EpistemicRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(EpistemicRiskLevel) == 4


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _claim(**ov):
    d = dict(claim_id="cl1", tenant_id="t1", content="fact",
             status=KnowledgeStatus.REPORTED, assertion_mode=AssertionMode.FACTUAL,
             trust_level=TrustLevel.MODERATE, source_ref="src1",
             confidence=0.5, created_at=_NOW)
    d.update(ov)
    return KnowledgeClaim(**d)


def _source(**ov):
    d = dict(source_id="src1", tenant_id="t1", display_name="Sensor1",
             origin=EvidenceOrigin.INSTRUMENT, reliability_score=0.7,
             claim_count=0, created_at=_NOW)
    d.update(ov)
    return EvidenceSource(**d)


def _trust_assessment(**ov):
    d = dict(assessment_id="ta1", tenant_id="t1", claim_ref="cl1",
             source_ref="src1", trust_level=TrustLevel.HIGH,
             confidence=0.6, basis="auto", assessed_at=_NOW)
    d.update(ov)
    return TrustAssessment(**d)


def _reliability(**ov):
    d = dict(record_id="rel1", tenant_id="t1", source_ref="src1",
             previous_score=0.5, updated_score=0.8, reason="improved",
             updated_at=_NOW)
    d.update(ov)
    return SourceReliabilityRecord(**d)


def _conflict(**ov):
    d = dict(conflict_id="cf1", tenant_id="t1", claim_a_ref="cl1",
             claim_b_ref="cl2", disposition=ConflictDisposition.UNRESOLVED,
             resolution_basis="", detected_at=_NOW)
    d.update(ov)
    return ClaimConflict(**d)


def _ep_decision(**ov):
    d = dict(decision_id="ed1", tenant_id="t1", claim_ref="cl1",
             disposition="accepted", reason="ok", decided_at=_NOW)
    d.update(ov)
    return EpistemicDecision(**d)


def _ep_assessment(**ov):
    d = dict(assessment_id="ea1", tenant_id="t1", total_claims=1,
             total_sources=1, total_conflicts=0, avg_trust=0.5,
             assessed_at=_NOW)
    d.update(ov)
    return EpistemicAssessment(**d)


def _ep_violation(**ov):
    d = dict(violation_id="ev1", tenant_id="t1", operation="insufficient_basis",
             reason="no assessment", detected_at=_NOW)
    d.update(ov)
    return EpistemicViolation(**d)


def _ep_snapshot(**ov):
    d = dict(snapshot_id="es1", tenant_id="t1", total_claims=1,
             total_sources=1, total_assessments=0, total_conflicts=0,
             total_reliability_updates=0, total_violations=0, captured_at=_NOW)
    d.update(ov)
    return EpistemicSnapshot(**d)


def _ep_closure(**ov):
    d = dict(report_id="er1", tenant_id="t1", total_claims=1,
             total_sources=1, total_conflicts=0, total_violations=0,
             created_at=_NOW)
    d.update(ov)
    return EpistemicClosureReport(**d)


# ---------------------------------------------------------------------------
# KnowledgeClaim tests
# ---------------------------------------------------------------------------


class TestKnowledgeClaim:
    def test_valid(self):
        c = _claim()
        assert c.claim_id == "cl1"
        assert c.status is KnowledgeStatus.REPORTED
        assert c.confidence == 0.5

    def test_all_statuses(self):
        for st in KnowledgeStatus:
            c = _claim(status=st)
            assert c.status is st

    def test_all_assertion_modes(self):
        for mode in AssertionMode:
            c = _claim(assertion_mode=mode)
            assert c.assertion_mode is mode

    def test_all_trust_levels(self):
        for tl in TrustLevel:
            c = _claim(trust_level=tl)
            assert c.trust_level is tl

    def test_confidence_zero(self):
        c = _claim(confidence=0.0)
        assert c.confidence == 0.0

    def test_confidence_one(self):
        c = _claim(confidence=1.0)
        assert c.confidence == 1.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _claim(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _claim(confidence=1.1)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _claim(confidence=float("nan"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _claim(confidence=True)

    def test_empty_claim_id_rejected(self):
        with pytest.raises(ValueError, match="claim_id"):
            _claim(claim_id="")

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError, match="content"):
            _claim(content="")

    def test_empty_source_ref_rejected(self):
        with pytest.raises(ValueError, match="source_ref"):
            _claim(source_ref="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _claim(status="invalid")

    def test_invalid_assertion_mode_rejected(self):
        with pytest.raises(ValueError, match="assertion_mode"):
            _claim(assertion_mode="invalid")

    def test_invalid_trust_level_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _claim(trust_level="invalid")

    def test_frozen(self):
        c = _claim()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "claim_id", "x")

    def test_to_dict_preserves_enum(self):
        d = _claim().to_dict()
        assert d["status"] is KnowledgeStatus.REPORTED

    def test_to_json_dict_converts_enum(self):
        d = _claim().to_json_dict()
        assert d["status"] == "reported"

    def test_metadata_frozen(self):
        c = _claim(metadata={"k": "v"})
        with pytest.raises(TypeError):
            c.metadata["new"] = "fail"


# ---------------------------------------------------------------------------
# EvidenceSource tests
# ---------------------------------------------------------------------------


class TestEvidenceSource:
    def test_valid(self):
        s = _source()
        assert s.source_id == "src1"
        assert s.origin is EvidenceOrigin.INSTRUMENT

    def test_all_origins(self):
        for o in EvidenceOrigin:
            s = _source(origin=o)
            assert s.origin is o

    def test_reliability_score_zero(self):
        s = _source(reliability_score=0.0)
        assert s.reliability_score == 0.0

    def test_reliability_score_one(self):
        s = _source(reliability_score=1.0)
        assert s.reliability_score == 1.0

    def test_reliability_score_negative_rejected(self):
        with pytest.raises(ValueError, match="reliability_score"):
            _source(reliability_score=-0.1)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError, match="reliability_score"):
            _source(reliability_score=1.1)

    def test_claim_count_negative_rejected(self):
        with pytest.raises(ValueError, match="claim_count"):
            _source(claim_count=-1)

    def test_claim_count_bool_rejected(self):
        with pytest.raises(ValueError, match="claim_count"):
            _source(claim_count=True)

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            _source(source_id="")

    def test_empty_display_name_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _source(display_name="")

    def test_invalid_origin_rejected(self):
        with pytest.raises(ValueError, match="origin"):
            _source(origin="invalid")

    def test_frozen(self):
        s = _source()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "source_id", "x")


# ---------------------------------------------------------------------------
# TrustAssessment tests
# ---------------------------------------------------------------------------


class TestTrustAssessment:
    def test_valid(self):
        a = _trust_assessment()
        assert a.assessment_id == "ta1"
        assert a.trust_level is TrustLevel.HIGH

    def test_confidence_zero(self):
        a = _trust_assessment(confidence=0.0)
        assert a.confidence == 0.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _trust_assessment(confidence=-0.1)

    def test_empty_assessment_id_rejected(self):
        with pytest.raises(ValueError, match="assessment_id"):
            _trust_assessment(assessment_id="")

    def test_empty_claim_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_ref"):
            _trust_assessment(claim_ref="")

    def test_empty_source_ref_rejected(self):
        with pytest.raises(ValueError, match="source_ref"):
            _trust_assessment(source_ref="")

    def test_empty_basis_rejected(self):
        with pytest.raises(ValueError, match="basis"):
            _trust_assessment(basis="")

    def test_invalid_trust_level_rejected(self):
        with pytest.raises(ValueError, match="trust_level"):
            _trust_assessment(trust_level="invalid")

    def test_frozen(self):
        a = _trust_assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")


# ---------------------------------------------------------------------------
# SourceReliabilityRecord tests
# ---------------------------------------------------------------------------


class TestSourceReliabilityRecord:
    def test_valid(self):
        r = _reliability()
        assert r.record_id == "rel1"
        assert r.previous_score == 0.5
        assert r.updated_score == 0.8

    def test_scores_zero(self):
        r = _reliability(previous_score=0.0, updated_score=0.0)
        assert r.previous_score == 0.0

    def test_scores_one(self):
        r = _reliability(previous_score=1.0, updated_score=1.0)
        assert r.previous_score == 1.0

    def test_previous_score_negative_rejected(self):
        with pytest.raises(ValueError, match="previous_score"):
            _reliability(previous_score=-0.1)

    def test_updated_score_above_one_rejected(self):
        with pytest.raises(ValueError, match="updated_score"):
            _reliability(updated_score=1.1)

    def test_empty_record_id_rejected(self):
        with pytest.raises(ValueError, match="record_id"):
            _reliability(record_id="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _reliability(reason="")

    def test_frozen(self):
        r = _reliability()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "record_id", "x")


# ---------------------------------------------------------------------------
# ClaimConflict tests
# ---------------------------------------------------------------------------


class TestClaimConflict:
    def test_valid(self):
        c = _conflict()
        assert c.conflict_id == "cf1"
        assert c.disposition is ConflictDisposition.UNRESOLVED

    def test_all_dispositions(self):
        for d in ConflictDisposition:
            c = _conflict(disposition=d)
            assert c.disposition is d

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _conflict(disposition="invalid")

    def test_empty_conflict_id_rejected(self):
        with pytest.raises(ValueError, match="conflict_id"):
            _conflict(conflict_id="")

    def test_empty_claim_a_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_a_ref"):
            _conflict(claim_a_ref="")

    def test_empty_claim_b_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_b_ref"):
            _conflict(claim_b_ref="")

    def test_frozen(self):
        c = _conflict()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "conflict_id", "x")


# ---------------------------------------------------------------------------
# EpistemicDecision tests
# ---------------------------------------------------------------------------


class TestEpistemicDecision:
    def test_valid(self):
        d = _ep_decision()
        assert d.decision_id == "ed1"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _ep_decision(decision_id="")

    def test_empty_claim_ref_rejected(self):
        with pytest.raises(ValueError, match="claim_ref"):
            _ep_decision(claim_ref="")

    def test_empty_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _ep_decision(disposition="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _ep_decision(reason="")

    def test_frozen(self):
        d = _ep_decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")


# ---------------------------------------------------------------------------
# EpistemicAssessment tests
# ---------------------------------------------------------------------------


class TestEpistemicAssessment:
    def test_valid(self):
        a = _ep_assessment()
        assert a.avg_trust == 0.5

    def test_avg_trust_zero(self):
        a = _ep_assessment(avg_trust=0.0)
        assert a.avg_trust == 0.0

    def test_avg_trust_one(self):
        a = _ep_assessment(avg_trust=1.0)
        assert a.avg_trust == 1.0

    def test_avg_trust_negative_rejected(self):
        with pytest.raises(ValueError, match="avg_trust"):
            _ep_assessment(avg_trust=-0.1)

    def test_avg_trust_above_one_rejected(self):
        with pytest.raises(ValueError, match="avg_trust"):
            _ep_assessment(avg_trust=1.1)

    def test_total_claims_negative_rejected(self):
        with pytest.raises(ValueError, match="total_claims"):
            _ep_assessment(total_claims=-1)

    def test_total_sources_negative_rejected(self):
        with pytest.raises(ValueError, match="total_sources"):
            _ep_assessment(total_sources=-1)

    def test_total_conflicts_negative_rejected(self):
        with pytest.raises(ValueError, match="total_conflicts"):
            _ep_assessment(total_conflicts=-1)

    def test_frozen(self):
        a = _ep_assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")


# ---------------------------------------------------------------------------
# EpistemicViolation tests
# ---------------------------------------------------------------------------


class TestEpistemicViolation:
    def test_valid(self):
        v = _ep_violation()
        assert v.violation_id == "ev1"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _ep_violation(violation_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _ep_violation(operation="")

    def test_frozen(self):
        v = _ep_violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")


# ---------------------------------------------------------------------------
# EpistemicSnapshot tests
# ---------------------------------------------------------------------------


class TestEpistemicSnapshot:
    def test_valid(self):
        s = _ep_snapshot()
        assert s.snapshot_id == "es1"

    def test_negative_counts_rejected(self):
        for field in ["total_claims", "total_sources", "total_assessments",
                      "total_conflicts", "total_reliability_updates", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _ep_snapshot(**{field: -1})

    def test_frozen(self):
        s = _ep_snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")


# ---------------------------------------------------------------------------
# EpistemicClosureReport tests
# ---------------------------------------------------------------------------


class TestEpistemicClosureReport:
    def test_valid(self):
        r = _ep_closure()
        assert r.report_id == "er1"

    def test_negative_counts_rejected(self):
        for field in ["total_claims", "total_sources", "total_conflicts", "total_violations"]:
            with pytest.raises(ValueError, match=field):
                _ep_closure(**{field: -1})

    def test_frozen(self):
        r = _ep_closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "x")


# ---------------------------------------------------------------------------
# Cross-cutting tests
# ---------------------------------------------------------------------------


class TestEpistemicCrossCutting:
    def test_all_contracts_have_to_dict(self):
        objs = [_claim(), _source(), _trust_assessment(), _reliability(),
                _conflict(), _ep_decision(), _ep_assessment(), _ep_violation(),
                _ep_snapshot(), _ep_closure()]
        for obj in objs:
            assert isinstance(obj.to_dict(), dict)

    def test_all_contracts_frozen(self):
        objs = [_claim(), _source(), _trust_assessment(), _reliability(),
                _conflict(), _ep_decision(), _ep_assessment(), _ep_violation(),
                _ep_snapshot(), _ep_closure()]
        for obj in objs:
            with pytest.raises((FrozenInstanceError, AttributeError)):
                setattr(obj, "tenant_id", "x")

    def test_all_invalid_datetime(self):
        with pytest.raises(ValueError):
            _claim(created_at="bad")
        with pytest.raises(ValueError):
            _source(created_at="bad")
        with pytest.raises(ValueError):
            _trust_assessment(assessed_at="bad")
        with pytest.raises(ValueError):
            _reliability(updated_at="bad")
        with pytest.raises(ValueError):
            _conflict(detected_at="bad")
        with pytest.raises(ValueError):
            _ep_decision(decided_at="bad")
        with pytest.raises(ValueError):
            _ep_assessment(assessed_at="bad")
        with pytest.raises(ValueError):
            _ep_violation(detected_at="bad")
        with pytest.raises(ValueError):
            _ep_snapshot(captured_at="bad")
        with pytest.raises(ValueError):
            _ep_closure(created_at="bad")

    def test_all_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _claim(tenant_id="")
        with pytest.raises(ValueError):
            _source(tenant_id="")
        with pytest.raises(ValueError):
            _trust_assessment(tenant_id="")
        with pytest.raises(ValueError):
            _reliability(tenant_id="")
        with pytest.raises(ValueError):
            _conflict(tenant_id="")
        with pytest.raises(ValueError):
            _ep_decision(tenant_id="")
        with pytest.raises(ValueError):
            _ep_assessment(tenant_id="")
        with pytest.raises(ValueError):
            _ep_violation(tenant_id="")
        with pytest.raises(ValueError):
            _ep_snapshot(tenant_id="")
        with pytest.raises(ValueError):
            _ep_closure(tenant_id="")

    def test_all_to_json(self):
        import json
        objs = [_claim(), _source(), _trust_assessment(), _reliability(),
                _conflict(), _ep_decision(), _ep_assessment(), _ep_violation(),
                _ep_snapshot(), _ep_closure()]
        for obj in objs:
            j = obj.to_json()
            assert isinstance(json.loads(j), dict)
