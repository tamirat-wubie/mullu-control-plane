"""Purpose: comprehensive tests for the TemporalRuntimeEngine.
Governance scope: runtime-core tests only.
Dependencies: temporal_runtime engine, event_spine, contracts, invariants.
Invariants: intervals auto-derive disposition, constraints relate events,
    violations are idempotent.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.temporal_runtime import (
    IntervalDisposition,
    PersistenceStatus,
    TemporalActionRequest,
    TemporalPolicyVerdict,
    TemporalRelation,
    TemporalRiskLevel,
)


NOW = datetime.now(timezone.utc)
T1 = NOW.isoformat()
T2 = (NOW + timedelta(hours=1)).isoformat()
T3 = (NOW + timedelta(hours=2)).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> TemporalRuntimeEngine:
    return TemporalRuntimeEngine(spine)


@pytest.fixture()
def engine_with_events(engine: TemporalRuntimeEngine) -> TemporalRuntimeEngine:
    engine.register_temporal_event("e-1", "tenant-a", "first event", T1)
    engine.register_temporal_event("e-2", "tenant-a", "second event", T2)
    return engine


# ===================================================================
# SECTION 1: Constructor validation
# ===================================================================


class TestConstructorValidation:
    def test_valid_event_spine_accepted(self, spine: EventSpineEngine) -> None:
        eng = TemporalRuntimeEngine(spine)
        assert eng.event_count == 0

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            TemporalRuntimeEngine(None)  # type: ignore[arg-type]


# ===================================================================
# SECTION 2: Temporal event registration
# ===================================================================


class TestTemporalEventRegistration:
    def test_register_event(self, engine: TemporalRuntimeEngine) -> None:
        te = engine.register_temporal_event("e-1", "t-1", "test", T1)
        assert te.event_id == "e-1"
        assert engine.event_count == 1

    def test_duplicate_event_raises(self, engine_with_events: TemporalRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_events.register_temporal_event("e-1", "t-1", "dup", T1)

    def test_get_temporal_event(self, engine_with_events: TemporalRuntimeEngine) -> None:
        te = engine_with_events.get_temporal_event("e-1")
        assert te.label == "first event"

    def test_get_unknown_event_raises(self, engine: TemporalRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_temporal_event("nonexistent")


# ===================================================================
# SECTION 3: Intervals
# ===================================================================


class TestIntervals:
    def test_register_open_interval(self, engine: TemporalRuntimeEngine) -> None:
        ti = engine.register_interval("i-1", "t-1", "open interval", T1)
        assert ti.disposition == IntervalDisposition.OPEN
        assert engine.interval_count == 1

    def test_register_closed_interval(self, engine: TemporalRuntimeEngine) -> None:
        ti = engine.register_interval("i-1", "t-1", "closed interval", T1, end_at=T2)
        assert ti.disposition == IntervalDisposition.CLOSED

    def test_duplicate_interval_raises(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_interval("i-1", "t-1", "test", T1)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_interval("i-1", "t-1", "dup", T1)


# ===================================================================
# SECTION 4: Constraints
# ===================================================================


class TestConstraints:
    def test_register_constraint(self, engine_with_events: TemporalRuntimeEngine) -> None:
        tc = engine_with_events.register_temporal_constraint(
            "c-1", "t-1", "e-1", "e-2", relation=TemporalRelation.BEFORE,
        )
        assert tc.relation == TemporalRelation.BEFORE
        assert engine_with_events.constraint_count == 1

    def test_unknown_event_a_raises(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_temporal_event("e-2", "t-1", "test", T1)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_temporal_constraint("c-1", "t-1", "nonexistent", "e-2")

    def test_unknown_event_b_raises(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_temporal_event("e-1", "t-1", "test", T1)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_temporal_constraint("c-1", "t-1", "e-1", "nonexistent")


# ===================================================================
# SECTION 5: Evaluate temporal relation
# ===================================================================


class TestEvaluateRelation:
    def test_before_relation(self, engine_with_events: TemporalRuntimeEngine) -> None:
        rel = engine_with_events.evaluate_temporal_relation("e-1", "e-2")
        assert rel == TemporalRelation.BEFORE

    def test_after_relation(self, engine_with_events: TemporalRuntimeEngine) -> None:
        rel = engine_with_events.evaluate_temporal_relation("e-2", "e-1")
        assert rel == TemporalRelation.AFTER

    def test_equals_relation(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_temporal_event("e-1", "t-1", "a", T1)
        engine.register_temporal_event("e-2", "t-1", "b", T1)
        rel = engine.evaluate_temporal_relation("e-1", "e-2")
        assert rel == TemporalRelation.EQUALS

    def test_relation_uses_absolute_instant_not_offset_text(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_temporal_event("e-1", "t-1", "utc", "2026-05-04T13:00:00+00:00")
        engine.register_temporal_event("e-2", "t-1", "local", "2026-05-04T09:00:00-04:00")
        rel = engine.evaluate_temporal_relation("e-1", "e-2")
        assert rel == TemporalRelation.EQUALS
        assert engine.get_temporal_event("e-1").occurred_at.endswith("+00:00")
        assert engine.get_temporal_event("e-2").occurred_at.endswith("-04:00")


# ===================================================================
# SECTION 5B: Temporal action policy
# ===================================================================


class TestTemporalActionPolicy:
    def test_approval_expiry_boundary_remains_valid(self, spine: EventSpineEngine) -> None:
        engine = TemporalRuntimeEngine(spine, clock=lambda: "2026-05-04T15:00:00+00:00")
        action = TemporalActionRequest(
            action_id="act-1",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="payment",
            risk=TemporalRiskLevel.HIGH,
            requested_at="2026-05-04T13:00:00+00:00",
            approval_expires_at="2026-05-04T15:00:00+00:00",
        )
        decision = engine.decide_temporal_action(action, decision_id="dec-1")
        assert decision.verdict == TemporalPolicyVerdict.ALLOW
        assert decision.reason == "temporal_policy_passed"
        assert engine.action_decision_count == 1

    def test_expired_approval_denies_high_risk_action(self, spine: EventSpineEngine) -> None:
        engine = TemporalRuntimeEngine(spine, clock=lambda: "2026-05-04T15:01:00+00:00")
        action = TemporalActionRequest(
            action_id="act-1",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="payment",
            risk=TemporalRiskLevel.HIGH,
            requested_at="2026-05-04T13:00:00+00:00",
            approval_expires_at="2026-05-04T15:00:00+00:00",
        )
        decision = engine.decide_temporal_action(action, decision_id="dec-1")
        assert decision.verdict == TemporalPolicyVerdict.DENY
        assert decision.reason == "approval_expired"
        assert decision.action_ref == "act-1"

    def test_stale_evidence_escalates_action(self, spine: EventSpineEngine) -> None:
        engine = TemporalRuntimeEngine(spine, clock=lambda: "2026-05-04T15:01:00+00:00")
        action = TemporalActionRequest(
            action_id="act-2",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="vendor_check",
            risk=TemporalRiskLevel.MEDIUM,
            requested_at="2026-05-04T13:00:00+00:00",
            evidence_fresh_until="2026-05-04T15:00:00+00:00",
        )
        decision = engine.decide_temporal_action(action, decision_id="dec-2")
        assert decision.verdict == TemporalPolicyVerdict.ESCALATE
        assert decision.reason == "evidence_stale"
        assert decision.metadata["risk"] == TemporalRiskLevel.MEDIUM.value

    def test_future_schedule_defers_execution(self, spine: EventSpineEngine) -> None:
        engine = TemporalRuntimeEngine(spine, clock=lambda: "2026-05-04T13:00:00+00:00")
        action = TemporalActionRequest(
            action_id="act-3",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="reminder",
            requested_at="2026-05-04T13:00:00+00:00",
            execute_at="2026-05-04T14:00:00+00:00",
        )
        decision = engine.decide_temporal_action(action, decision_id="dec-3")
        assert decision.verdict == TemporalPolicyVerdict.DEFER
        assert decision.reason == "scheduled_for_future"
        assert engine.snapshot()["action_decisions"] == 1

    def test_retry_attempt_limit_denies_before_dispatch(self, spine: EventSpineEngine) -> None:
        engine = TemporalRuntimeEngine(spine, clock=lambda: "2026-05-04T13:00:00+00:00")
        action = TemporalActionRequest(
            action_id="act-4",
            tenant_id="t-1",
            actor_id="user-1",
            action_type="webhook_retry",
            requested_at="2026-05-04T13:00:00+00:00",
            retry_after="2026-05-04T14:00:00+00:00",
            max_attempts=3,
            attempt_count=3,
        )
        decision = engine.decide_temporal_action(action, decision_id="dec-4")
        assert decision.verdict == TemporalPolicyVerdict.DENY
        assert decision.reason == "retry_attempts_exhausted"
        assert engine.action_decision_count == 1


# ===================================================================
# SECTION 6: Persistence
# ===================================================================


class TestPersistence:
    def test_record_persistence(self, engine: TemporalRuntimeEngine) -> None:
        pr = engine.record_persistence("p-1", "t-1", "f-1", T1)
        assert pr.status == PersistenceStatus.PERSISTING
        assert engine.persistence_count == 1

    def test_cease_persistence(self, engine: TemporalRuntimeEngine) -> None:
        engine.record_persistence("p-1", "t-1", "f-1", T1)
        pr = engine.cease_persistence("p-1")
        assert pr.status == PersistenceStatus.CEASED

    def test_check_persistence(self, engine: TemporalRuntimeEngine) -> None:
        engine.record_persistence("p-1", "t-1", "f-1", T1)
        status = engine.check_persistence("p-1")
        assert status == PersistenceStatus.PERSISTING

    def test_unknown_persistence_raises(self, engine: TemporalRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cease_persistence("nonexistent")

    def test_check_unknown_raises(self, engine: TemporalRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.check_persistence("nonexistent")


# ===================================================================
# SECTION 7: Sequences
# ===================================================================


class TestSequences:
    def test_register_sequence(self, engine: TemporalRuntimeEngine) -> None:
        ts = engine.register_sequence("s-1", "t-1", "test seq")
        assert ts.event_count == 0
        assert engine.sequence_count == 1

    def test_add_event_to_sequence(self, engine_with_events: TemporalRuntimeEngine) -> None:
        engine_with_events.register_sequence("s-1", "t-1", "test seq")
        ts = engine_with_events.add_event_to_sequence("s-1", "e-1")
        assert ts.event_count == 1
        ts = engine_with_events.add_event_to_sequence("s-1", "e-2")
        assert ts.event_count == 2

    def test_unknown_sequence_raises(self, engine: TemporalRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_event_to_sequence("nonexistent", "e-1")


# ===================================================================
# SECTION 8: Assessment / Snapshot / Closure
# ===================================================================


class TestAssessmentSnapshotClosure:
    def test_temporal_assessment_no_constraints(self, engine: TemporalRuntimeEngine) -> None:
        a = engine.temporal_assessment("a-1", "t-1")
        assert a.compliance_rate == 1.0

    def test_temporal_snapshot(self, engine_with_events: TemporalRuntimeEngine) -> None:
        snap = engine_with_events.temporal_snapshot("snap-1", "t-1")
        assert snap.total_events == 2
        assert snap.total_violations == 0

    def test_duplicate_snapshot_raises(self, engine: TemporalRuntimeEngine) -> None:
        engine.temporal_snapshot("snap-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.temporal_snapshot("snap-1", "t-1")

    def test_closure_report(self, engine_with_events: TemporalRuntimeEngine) -> None:
        r = engine_with_events.temporal_closure_report("r-1", "t-1")
        assert r.total_events == 2


# ===================================================================
# SECTION 9: Violations
# ===================================================================


class TestViolationDetection:
    def test_constraint_violated(self, engine_with_events: TemporalRuntimeEngine) -> None:
        # e-1 is BEFORE e-2, but constraint says AFTER
        engine_with_events.register_temporal_constraint(
            "c-1", "t-1", "e-1", "e-2", relation=TemporalRelation.AFTER,
        )
        violations = engine_with_events.detect_temporal_violations()
        violated = [v for v in violations if v["operation"] == "constraint_violated"]
        assert len(violated) >= 1

    def test_satisfied_constraint_no_violation(self, engine_with_events: TemporalRuntimeEngine) -> None:
        engine_with_events.register_temporal_constraint(
            "c-1", "t-1", "e-1", "e-2", relation=TemporalRelation.BEFORE,
        )
        violations = engine_with_events.detect_temporal_violations()
        violated = [v for v in violations if v["operation"] == "constraint_violated"]
        assert len(violated) == 0

    def test_idempotent_violations(self, engine_with_events: TemporalRuntimeEngine) -> None:
        engine_with_events.register_temporal_constraint(
            "c-1", "t-1", "e-1", "e-2", relation=TemporalRelation.AFTER,
        )
        v1 = engine_with_events.detect_temporal_violations()
        v2 = engine_with_events.detect_temporal_violations()
        assert len(v1) >= 1
        assert len(v2) == 0  # idempotent

    def test_sequence_disordered(self, engine: TemporalRuntimeEngine) -> None:
        engine.register_temporal_event("e-1", "t-1", "late", T2)
        engine.register_temporal_event("e-2", "t-1", "early", T1)
        engine.register_sequence("s-1", "t-1", "test seq")
        engine.add_event_to_sequence("s-1", "e-1")
        engine.add_event_to_sequence("s-1", "e-2")
        violations = engine.detect_temporal_violations()
        disordered = [v for v in violations if v["operation"] == "sequence_disordered"]
        assert len(disordered) >= 1

    def test_persistence_gap(self, engine: TemporalRuntimeEngine) -> None:
        engine.record_persistence("p-1", "t-1", "f-1", T1)
        engine.cease_persistence("p-1")
        engine.record_persistence("p-2", "t-1", "f-1", T2)
        violations = engine.detect_temporal_violations()
        gaps = [v for v in violations if v["operation"] == "persistence_gap"]
        assert len(gaps) >= 1


# ===================================================================
# SECTION 10: State hash
# ===================================================================


class TestStateHash:
    def test_state_hash_changes(self, engine: TemporalRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.register_temporal_event("e-1", "t-1", "test", T1)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_method(self, engine_with_events: TemporalRuntimeEngine) -> None:
        snap = engine_with_events.snapshot()
        assert snap["events"] == 2


class TestBoundedContracts:
    def test_duplicate_and_unknown_contracts_do_not_reflect_ids(
        self, engine_with_events: TemporalRuntimeEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError) as dup_exc:
            engine_with_events.register_temporal_event("e-1", "t-1", "dup", T1)
        dup_message = str(dup_exc.value)
        assert dup_message == "Duplicate event_id"
        assert "e-1" not in dup_message
        assert "Duplicate event_id" in dup_message

        with pytest.raises(RuntimeCoreInvariantError) as unknown_exc:
            engine_with_events.check_persistence("p-secret")
        unknown_message = str(unknown_exc.value)
        assert unknown_message == "Unknown persistence_id"
        assert "p-secret" not in unknown_message
        assert "Unknown persistence_id" in unknown_message

    def test_violation_reasons_do_not_reflect_ids_or_relation_values(
        self, engine_with_events: TemporalRuntimeEngine
    ) -> None:
        engine_with_events.register_temporal_constraint(
            "constraint-secret", "t-1", "e-1", "e-2", relation=TemporalRelation.AFTER,
        )
        reasons = {
            violation["operation"]: violation["reason"]
            for violation in engine_with_events.detect_temporal_violations()
        }
        assert reasons["constraint_violated"] == "Constraint relation mismatch"
        assert "constraint-secret" not in reasons["constraint_violated"]
        assert "after" not in reasons["constraint_violated"].lower()

    def test_sequence_and_persistence_reasons_are_bounded(
        self, engine: TemporalRuntimeEngine
    ) -> None:
        engine.register_temporal_event("e-1", "t-1", "late", T2)
        engine.register_temporal_event("e-2", "t-1", "early", T1)
        engine.register_sequence("sequence-secret", "t-1", "seq")
        engine.add_event_to_sequence("sequence-secret", "e-1")
        engine.add_event_to_sequence("sequence-secret", "e-2")
        engine.record_persistence("p-1", "t-1", "fact-secret", T1)
        engine.cease_persistence("p-1")
        engine.record_persistence("p-2", "t-1", "fact-secret", T2)

        reasons = [violation["reason"] for violation in engine.detect_temporal_violations()]
        assert "Sequence events out of order" in reasons
        assert "Fact has inconsistent persistence records" in reasons
        assert all("sequence-secret" not in reason for reason in reasons)
        assert all("fact-secret" not in reason for reason in reasons)
