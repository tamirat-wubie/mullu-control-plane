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
    TemporalActionDecision,
    TemporalActionRequest,
    TemporalAssessment,
    TemporalClockSample,
    TemporalClosureReport,
    TemporalConstraint,
    TemporalDecision,
    TemporalEvent,
    TemporalInterval,
    TemporalPolicyVerdict,
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

    def test_temporal_policy_verdict_values(self) -> None:
        assert len(TemporalPolicyVerdict) == 4
        assert TemporalPolicyVerdict.ALLOW.value == "allow"
        assert TemporalPolicyVerdict.ESCALATE.value == "escalate"


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


class TestTemporalKernelContracts:
    def test_clock_sample_preserves_runtime_resolution(self) -> None:
        sample = TemporalClockSample(
            sample_id="sample-1",
            tenant_id="t-1",
            utc_now="2026-05-04T13:10:00+00:00",
            user_timezone="America/New_York",
            local_user_time="2026-05-04T09:10:00-04:00",
            original_text="tomorrow morning",
            resolved_at="2026-05-04T13:10:00+00:00",
            monotonic_ns=12,
        )
        assert sample.utc_now == "2026-05-04T13:10:00+00:00"
        assert sample.user_timezone == "America/New_York"
        assert sample.monotonic_ns == 12

    def test_action_request_accepts_governed_windows(self) -> None:
        request = TemporalActionRequest(
            action_id="act-1",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="payment",
            risk=TemporalRiskLevel.HIGH,
            requested_at="2026-05-04T13:00:00+00:00",
            execute_at="2026-05-04T14:00:00+00:00",
            expires_at="2026-05-04T15:00:00+00:00",
            approval_expires_at="2026-05-04T15:00:00+00:00",
            evidence_fresh_until="2026-05-04T14:30:00+00:00",
            max_attempts=3,
            attempt_count=1,
        )
        assert request.risk == TemporalRiskLevel.HIGH
        assert request.execute_at == "2026-05-04T14:00:00+00:00"
        assert request.max_attempts == 3

    def test_action_decision_records_bounded_verdict(self) -> None:
        decision = TemporalActionDecision(
            decision_id="td-1",
            tenant_id="t-1",
            action_ref="act-1",
            verdict=TemporalPolicyVerdict.DEFER,
            reason="scheduled_for_future",
            decided_at=NOW,
        )
        assert decision.verdict == TemporalPolicyVerdict.DEFER
        assert decision.reason == "scheduled_for_future"
        assert decision.action_ref == "act-1"


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
