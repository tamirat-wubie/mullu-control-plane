"""Purpose: contract tests for uncertainty_runtime contracts.
Governance scope: runtime-contract tests only.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcoi_runtime.contracts.uncertainty_runtime import (
    BeliefDecision,
    BeliefRecord,
    BeliefRiskLevel,
    BeliefStatus,
    BeliefUpdate,
    CompetingHypothesisSet,
    ConfidenceDisposition,
    ConfidenceInterval,
    EvidenceWeight,
    EvidenceWeightRecord,
    HypothesisDisposition,
    UncertaintyAssessment,
    UncertaintyClosureReport,
    UncertaintyHypothesis,
    UncertaintySnapshot,
    UncertaintyType,
)


NOW = datetime.now(timezone.utc).isoformat()


class TestEnums:
    def test_belief_status_values(self) -> None:
        assert len(BeliefStatus) == 5

    def test_evidence_weight_values(self) -> None:
        assert len(EvidenceWeight) == 5

    def test_confidence_disposition_values(self) -> None:
        assert len(ConfidenceDisposition) == 5

    def test_uncertainty_type_values(self) -> None:
        assert len(UncertaintyType) == 4

    def test_hypothesis_disposition_values(self) -> None:
        assert len(HypothesisDisposition) == 4

    def test_belief_risk_level_values(self) -> None:
        assert len(BeliefRiskLevel) == 4


class TestBeliefRecord:
    def test_valid_belief(self) -> None:
        b = BeliefRecord(
            belief_id="b-1", tenant_id="t-1", content="test belief",
            status=BeliefStatus.PROVISIONAL, confidence=0.5, created_at=NOW,
        )
        assert b.belief_id == "b-1"
        assert b.confidence == 0.5
        assert b.status == BeliefStatus.PROVISIONAL

    def test_empty_belief_id_raises(self) -> None:
        with pytest.raises(ValueError):
            BeliefRecord(belief_id="", tenant_id="t", content="c", created_at=NOW)

    def test_frozen(self) -> None:
        b = BeliefRecord(belief_id="b-1", tenant_id="t-1", content="c", created_at=NOW)
        with pytest.raises(AttributeError):
            b.confidence = 0.9  # type: ignore[misc]


class TestUncertaintyHypothesis:
    def test_valid_hypothesis(self) -> None:
        h = UncertaintyHypothesis(
            hypothesis_id="h-1", tenant_id="t-1", belief_ref="b-1",
            disposition=HypothesisDisposition.COMPETING,
            prior_confidence=0.3, posterior_confidence=0.6, created_at=NOW,
        )
        assert h.hypothesis_id == "h-1"
        assert h.prior_confidence == 0.3


class TestEvidenceWeightRecord:
    def test_valid_weight(self) -> None:
        w = EvidenceWeightRecord(
            weight_id="w-1", tenant_id="t-1", belief_ref="b-1",
            evidence_ref="e-1", weight=EvidenceWeight.STRONG,
            impact=0.2, created_at=NOW,
        )
        assert w.weight == EvidenceWeight.STRONG
        assert w.impact == 0.2


class TestConfidenceInterval:
    def test_valid_interval(self) -> None:
        ci = ConfidenceInterval(
            interval_id="ci-1", tenant_id="t-1", belief_ref="b-1",
            lower=0.2, upper=0.8, confidence_level=0.95, created_at=NOW,
        )
        assert ci.lower == 0.2
        assert ci.upper == 0.8


class TestBeliefUpdate:
    def test_valid_update(self) -> None:
        bu = BeliefUpdate(
            update_id="u-1", tenant_id="t-1", belief_ref="b-1",
            prior_confidence=0.5, posterior_confidence=0.7,
            evidence_ref="e-1", updated_at=NOW,
        )
        assert bu.posterior_confidence == 0.7


class TestCompetingHypothesisSet:
    def test_valid_set(self) -> None:
        cs = CompetingHypothesisSet(
            set_id="s-1", tenant_id="t-1", hypothesis_count=3,
            leading_hypothesis_ref="h-1", created_at=NOW,
        )
        assert cs.hypothesis_count == 3


class TestBeliefDecision:
    def test_valid_decision(self) -> None:
        bd = BeliefDecision(
            decision_id="d-1", tenant_id="t-1", belief_ref="b-1",
            disposition="established", reason="sufficient evidence",
            decided_at=NOW,
        )
        assert bd.disposition == "established"


class TestUncertaintyAssessment:
    def test_valid_assessment(self) -> None:
        ua = UncertaintyAssessment(
            assessment_id="a-1", tenant_id="t-1",
            total_beliefs=5, total_hypotheses=3, total_updates=10,
            avg_confidence=0.6, assessed_at=NOW,
        )
        assert ua.total_beliefs == 5


class TestUncertaintySnapshot:
    def test_valid_snapshot(self) -> None:
        snap = UncertaintySnapshot(
            snapshot_id="snap-1", tenant_id="t-1",
            total_beliefs=5, total_hypotheses=3, total_weights=8,
            total_intervals=2, total_updates=10, total_violations=1,
            captured_at=NOW,
        )
        assert snap.total_weights == 8


class TestUncertaintyClosureReport:
    def test_valid_report(self) -> None:
        r = UncertaintyClosureReport(
            report_id="r-1", tenant_id="t-1",
            total_beliefs=5, total_hypotheses=3,
            total_updates=10, total_violations=1,
            created_at=NOW,
        )
        assert r.total_violations == 1
