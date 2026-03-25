"""Purpose: contract tests for temporal_runtime contracts.
Governance scope: runtime-contract tests only.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcoi_runtime.contracts.temporal_runtime import (
    EventSequenceStatus,
    IntervalDisposition,
    PersistenceRecord,
    PersistenceStatus,
    TemporalAssessment,
    TemporalClosureReport,
    TemporalConstraint,
    TemporalDecision,
    TemporalEvent,
    TemporalInterval,
    TemporalRelation,
    TemporalRiskLevel,
    TemporalSequence,
    TemporalSnapshot,
    TemporalStatus,
    TemporalViolation,
)


NOW = datetime.now(timezone.utc).isoformat()


class TestEnums:
    def test_temporal_status_values(self) -> None:
        assert len(TemporalStatus) == 4

    def test_interval_disposition_values(self) -> None:
        assert len(IntervalDisposition) == 4

    def test_temporal_relation_values(self) -> None:
        assert len(TemporalRelation) == 7

    def test_persistence_status_values(self) -> None:
        assert len(PersistenceStatus) == 4

    def test_event_sequence_status_values(self) -> None:
        assert len(EventSequenceStatus) == 4

    def test_temporal_risk_level_values(self) -> None:
        assert len(TemporalRiskLevel) == 4


class TestTemporalEvent:
    def test_valid_event(self) -> None:
        te = TemporalEvent(
            event_id="e-1", tenant_id="t-1", label="test event",
            occurred_at=NOW, duration_ms=100.0, created_at=NOW,
        )
        assert te.event_id == "e-1"
        assert te.duration_ms == 100.0

    def test_empty_event_id_raises(self) -> None:
        with pytest.raises(ValueError):
            TemporalEvent(event_id="", tenant_id="t", label="l", occurred_at=NOW, created_at=NOW)

    def test_frozen(self) -> None:
        te = TemporalEvent(event_id="e-1", tenant_id="t-1", label="l", occurred_at=NOW, created_at=NOW)
        with pytest.raises(AttributeError):
            te.label = "new"  # type: ignore[misc]


class TestTemporalInterval:
    def test_valid_closed_interval(self) -> None:
        ti = TemporalInterval(
            interval_id="i-1", tenant_id="t-1", label="closed",
            start_at=NOW, end_at=NOW,
            disposition=IntervalDisposition.CLOSED, created_at=NOW,
        )
        assert ti.disposition == IntervalDisposition.CLOSED

    def test_valid_open_interval(self) -> None:
        ti = TemporalInterval(
            interval_id="i-1", tenant_id="t-1", label="open",
            start_at=NOW, end_at="",
            disposition=IntervalDisposition.OPEN, created_at=NOW,
        )
        assert ti.disposition == IntervalDisposition.OPEN


class TestTemporalConstraint:
    def test_valid_constraint(self) -> None:
        tc = TemporalConstraint(
            constraint_id="c-1", tenant_id="t-1",
            event_a_ref="e-1", event_b_ref="e-2",
            relation=TemporalRelation.BEFORE, max_gap_ms=1000.0,
            created_at=NOW,
        )
        assert tc.relation == TemporalRelation.BEFORE


class TestPersistenceRecord:
    def test_valid_persistence(self) -> None:
        pr = PersistenceRecord(
            persistence_id="p-1", tenant_id="t-1", fact_ref="f-1",
            status=PersistenceStatus.PERSISTING,
            valid_from=NOW, valid_until="", created_at=NOW,
        )
        assert pr.status == PersistenceStatus.PERSISTING

    def test_valid_persistence_with_until(self) -> None:
        pr = PersistenceRecord(
            persistence_id="p-1", tenant_id="t-1", fact_ref="f-1",
            status=PersistenceStatus.CEASED,
            valid_from=NOW, valid_until=NOW, created_at=NOW,
        )
        assert pr.status == PersistenceStatus.CEASED


class TestTemporalSequence:
    def test_valid_sequence(self) -> None:
        ts = TemporalSequence(
            sequence_id="s-1", tenant_id="t-1", display_name="test seq",
            event_count=5, status=EventSequenceStatus.ORDERED, created_at=NOW,
        )
        assert ts.event_count == 5


class TestTemporalDecision:
    def test_valid_decision(self) -> None:
        td = TemporalDecision(
            decision_id="d-1", tenant_id="t-1", constraint_ref="c-1",
            satisfied=True, reason="constraint met", decided_at=NOW,
        )
        assert td.satisfied is True


class TestTemporalAssessment:
    def test_valid_assessment(self) -> None:
        ta = TemporalAssessment(
            assessment_id="a-1", tenant_id="t-1",
            total_events=10, total_intervals=5, total_constraints=3,
            compliance_rate=0.8, assessed_at=NOW,
        )
        assert ta.compliance_rate == 0.8


class TestTemporalViolation:
    def test_valid_violation(self) -> None:
        tv = TemporalViolation(
            violation_id="v-1", tenant_id="t-1",
            operation="constraint_violated", reason="mismatch",
            detected_at=NOW,
        )
        assert tv.operation == "constraint_violated"


class TestTemporalSnapshot:
    def test_valid_snapshot(self) -> None:
        snap = TemporalSnapshot(
            snapshot_id="snap-1", tenant_id="t-1",
            total_events=10, total_intervals=5, total_constraints=3,
            total_sequences=2, total_persistence=4, total_violations=1,
            captured_at=NOW,
        )
        assert snap.total_sequences == 2


class TestTemporalClosureReport:
    def test_valid_report(self) -> None:
        r = TemporalClosureReport(
            report_id="r-1", tenant_id="t-1",
            total_events=10, total_intervals=5,
            total_constraints=3, total_violations=1,
            created_at=NOW,
        )
        assert r.total_violations == 1
