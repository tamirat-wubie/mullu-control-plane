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
    EventSequenceStatus,
    IntervalDisposition,
    PersistenceRecord,
    PersistenceStatus,
    TemporalAssessment,
    TemporalClosureReport,
    TemporalConstraint,
    TemporalEvent,
    TemporalInterval,
    TemporalRelation,
    TemporalSequence,
    TemporalSnapshot,
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
