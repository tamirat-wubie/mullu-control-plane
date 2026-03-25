"""Purpose: temporal reasoning runtime engine.
Governance scope: registering temporal events, intervals, constraints,
    persistence records, sequences, evaluating temporal relations,
    detecting violations, producing immutable snapshots.
Dependencies: temporal_runtime contracts, event_spine, core invariants.
Invariants:
  - Intervals auto-derive disposition from start/end presence.
  - Constraints relate temporal events.
  - Persistence tracks fact validity windows.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable

from ..contracts.temporal_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-temp", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class TemporalRuntimeEngine:
    """Temporal reasoning engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Callable[[], str] | None = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _now_iso
        self._temporal_events: dict[str, TemporalEvent] = {}
        self._intervals: dict[str, TemporalInterval] = {}
        self._constraints: dict[str, TemporalConstraint] = {}
        self._persistence: dict[str, PersistenceRecord] = {}
        self._sequences: dict[str, TemporalSequence] = {}
        self._decisions: dict[str, TemporalDecision] = {}
        self._violations: dict[str, Any] = {}
        self._snapshot_ids: set[str] = set()
        # Track which events belong to which sequence
        self._sequence_events: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def event_count(self) -> int:
        return len(self._temporal_events)

    @property
    def interval_count(self) -> int:
        return len(self._intervals)

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    @property
    def persistence_count(self) -> int:
        return len(self._persistence)

    @property
    def sequence_count(self) -> int:
        return len(self._sequences)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Temporal events
    # ------------------------------------------------------------------

    def register_temporal_event(
        self,
        event_id: str,
        tenant_id: str,
        label: str,
        occurred_at: str,
        *,
        duration_ms: float = 0.0,
    ) -> TemporalEvent:
        """Register a temporal event."""
        if event_id in self._temporal_events:
            raise RuntimeCoreInvariantError(f"Duplicate event_id: {event_id}")
        now = self._clock()
        te = TemporalEvent(
            event_id=event_id, tenant_id=tenant_id,
            label=label, occurred_at=occurred_at,
            duration_ms=duration_ms, created_at=now,
        )
        self._temporal_events[event_id] = te
        _emit(self._events, "temporal_event_registered", {
            "event_id": event_id, "label": label,
        }, event_id)
        return te

    def get_temporal_event(self, event_id: str) -> TemporalEvent:
        """Get a temporal event by ID."""
        te = self._temporal_events.get(event_id)
        if te is None:
            raise RuntimeCoreInvariantError(f"Unknown event_id: {event_id}")
        return te

    # ------------------------------------------------------------------
    # Intervals
    # ------------------------------------------------------------------

    def register_interval(
        self,
        interval_id: str,
        tenant_id: str,
        label: str,
        start_at: str,
        *,
        end_at: str = "",
    ) -> TemporalInterval:
        """Register a temporal interval. Auto OPEN if end_at empty, CLOSED if both present."""
        if interval_id in self._intervals:
            raise RuntimeCoreInvariantError(f"Duplicate interval_id: {interval_id}")
        disposition = IntervalDisposition.OPEN if not end_at else IntervalDisposition.CLOSED
        now = self._clock()
        ti = TemporalInterval(
            interval_id=interval_id, tenant_id=tenant_id,
            label=label, start_at=start_at, end_at=end_at,
            disposition=disposition, created_at=now,
        )
        self._intervals[interval_id] = ti
        _emit(self._events, "interval_registered", {
            "interval_id": interval_id, "disposition": disposition.value,
        }, interval_id)
        return ti

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def register_temporal_constraint(
        self,
        constraint_id: str,
        tenant_id: str,
        event_a_ref: str,
        event_b_ref: str,
        *,
        relation: TemporalRelation = TemporalRelation.BEFORE,
        max_gap_ms: float = 0.0,
    ) -> TemporalConstraint:
        """Register a temporal constraint between two events."""
        if constraint_id in self._constraints:
            raise RuntimeCoreInvariantError(f"Duplicate constraint_id: {constraint_id}")
        if event_a_ref not in self._temporal_events:
            raise RuntimeCoreInvariantError(f"Unknown event_a_ref: {event_a_ref}")
        if event_b_ref not in self._temporal_events:
            raise RuntimeCoreInvariantError(f"Unknown event_b_ref: {event_b_ref}")
        now = self._clock()
        tc = TemporalConstraint(
            constraint_id=constraint_id, tenant_id=tenant_id,
            event_a_ref=event_a_ref, event_b_ref=event_b_ref,
            relation=relation, max_gap_ms=max_gap_ms,
            created_at=now,
        )
        self._constraints[constraint_id] = tc
        _emit(self._events, "temporal_constraint_registered", {
            "constraint_id": constraint_id,
            "event_a_ref": event_a_ref, "event_b_ref": event_b_ref,
            "relation": relation.value,
        }, constraint_id)
        return tc

    # ------------------------------------------------------------------
    # Evaluate temporal relation
    # ------------------------------------------------------------------

    def evaluate_temporal_relation(
        self,
        event_a_ref: str,
        event_b_ref: str,
    ) -> TemporalRelation:
        """Compare two events: BEFORE if a < b, AFTER if a > b, EQUALS if same."""
        a = self.get_temporal_event(event_a_ref)
        b = self.get_temporal_event(event_b_ref)
        if a.occurred_at < b.occurred_at:
            return TemporalRelation.BEFORE
        if a.occurred_at > b.occurred_at:
            return TemporalRelation.AFTER
        return TemporalRelation.EQUALS

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def record_persistence(
        self,
        persistence_id: str,
        tenant_id: str,
        fact_ref: str,
        valid_from: str,
        *,
        valid_until: str = "",
    ) -> PersistenceRecord:
        """Record a persisting fact (PERSISTING status)."""
        if persistence_id in self._persistence:
            raise RuntimeCoreInvariantError(f"Duplicate persistence_id: {persistence_id}")
        now = self._clock()
        pr = PersistenceRecord(
            persistence_id=persistence_id, tenant_id=tenant_id,
            fact_ref=fact_ref, status=PersistenceStatus.PERSISTING,
            valid_from=valid_from, valid_until=valid_until,
            created_at=now,
        )
        self._persistence[persistence_id] = pr
        _emit(self._events, "persistence_recorded", {
            "persistence_id": persistence_id, "fact_ref": fact_ref,
        }, persistence_id)
        return pr

    def cease_persistence(self, persistence_id: str) -> PersistenceRecord:
        """Mark a persistence record as CEASED."""
        old = self._persistence.get(persistence_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown persistence_id: {persistence_id}")
        now = self._clock()
        updated = PersistenceRecord(
            persistence_id=old.persistence_id, tenant_id=old.tenant_id,
            fact_ref=old.fact_ref, status=PersistenceStatus.CEASED,
            valid_from=old.valid_from, valid_until=now,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._persistence[persistence_id] = updated
        _emit(self._events, "persistence_ceased", {
            "persistence_id": persistence_id,
        }, persistence_id)
        return updated

    def check_persistence(self, persistence_id: str) -> PersistenceStatus:
        """Check current persistence status."""
        pr = self._persistence.get(persistence_id)
        if pr is None:
            raise RuntimeCoreInvariantError(f"Unknown persistence_id: {persistence_id}")
        return pr.status

    # ------------------------------------------------------------------
    # Sequences
    # ------------------------------------------------------------------

    def register_sequence(
        self,
        sequence_id: str,
        tenant_id: str,
        display_name: str,
    ) -> TemporalSequence:
        """Register a temporal event sequence."""
        if sequence_id in self._sequences:
            raise RuntimeCoreInvariantError(f"Duplicate sequence_id: {sequence_id}")
        now = self._clock()
        ts = TemporalSequence(
            sequence_id=sequence_id, tenant_id=tenant_id,
            display_name=display_name, event_count=0,
            status=EventSequenceStatus.ORDERED, created_at=now,
        )
        self._sequences[sequence_id] = ts
        self._sequence_events[sequence_id] = []
        _emit(self._events, "sequence_registered", {
            "sequence_id": sequence_id, "display_name": display_name,
        }, sequence_id)
        return ts

    def add_event_to_sequence(
        self,
        sequence_id: str,
        event_id: str,
    ) -> TemporalSequence:
        """Add an event to a sequence, incrementing event_count."""
        old = self._sequences.get(sequence_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown sequence_id: {sequence_id}")
        if event_id not in self._temporal_events:
            raise RuntimeCoreInvariantError(f"Unknown event_id: {event_id}")
        self._sequence_events[sequence_id].append(event_id)
        new_count = old.event_count + 1
        updated = TemporalSequence(
            sequence_id=old.sequence_id, tenant_id=old.tenant_id,
            display_name=old.display_name, event_count=new_count,
            status=old.status, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._sequences[sequence_id] = updated
        _emit(self._events, "event_added_to_sequence", {
            "sequence_id": sequence_id, "event_id": event_id,
            "new_count": new_count,
        }, sequence_id)
        return updated

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def temporal_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> TemporalAssessment:
        """Produce a temporal assessment. compliance_rate = satisfied/total constraints."""
        total_constraints = self.constraint_count
        satisfied = sum(
            1 for d in self._decisions.values() if d.satisfied
        )
        compliance_rate = 1.0
        if total_constraints > 0:
            compliance_rate = round(satisfied / total_constraints, 6)
        now = self._clock()
        assessment = TemporalAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_events=self.event_count,
            total_intervals=self.interval_count,
            total_constraints=total_constraints,
            compliance_rate=compliance_rate,
            assessed_at=now,
        )
        _emit(self._events, "temporal_assessment", {
            "assessment_id": assessment_id,
            "compliance_rate": compliance_rate,
        }, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def temporal_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> TemporalSnapshot:
        """Capture a point-in-time temporal snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = self._clock()
        snap = TemporalSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_events=self.event_count,
            total_intervals=self.interval_count,
            total_constraints=self.constraint_count,
            total_sequences=self.sequence_count,
            total_persistence=self.persistence_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "temporal_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def temporal_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> TemporalClosureReport:
        """Produce a closure report for the temporal runtime."""
        now = self._clock()
        report = TemporalClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_events=self.event_count,
            total_intervals=self.interval_count,
            total_constraints=self.constraint_count,
            total_violations=self.violation_count,
            created_at=now,
        )
        _emit(self._events, "temporal_closure_report", {
            "report_id": report_id,
        }, report_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_temporal_violations(self) -> tuple:
        """Detect temporal violations (idempotent)."""
        now = self._clock()
        new_violations: list = []

        # Constraint violated: evaluated relation doesn't match required
        for c in self._constraints.values():
            actual = self.evaluate_temporal_relation(c.event_a_ref, c.event_b_ref)
            if actual != c.relation:
                vid = stable_identifier("viol-temp", {
                    "constraint": c.constraint_id, "op": "constraint_violated",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "constraint_id": c.constraint_id,
                        "tenant_id": c.tenant_id,
                        "operation": "constraint_violated",
                        "reason": (
                            f"Constraint {c.constraint_id} requires {c.relation.value} "
                            f"but actual relation is {actual.value}"
                        ),
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)
                    # Also create a decision record
                    did = stable_identifier("dec-temp", {"constraint": c.constraint_id})
                    if did not in self._decisions:
                        decision = TemporalDecision(
                            decision_id=did, tenant_id=c.tenant_id,
                            constraint_ref=c.constraint_id,
                            satisfied=False,
                            reason=f"Actual relation {actual.value} != required {c.relation.value}",
                            decided_at=now,
                        )
                        self._decisions[did] = decision
            else:
                # Record satisfied decision
                did = stable_identifier("dec-temp", {"constraint": c.constraint_id})
                if did not in self._decisions:
                    decision = TemporalDecision(
                        decision_id=did, tenant_id=c.tenant_id,
                        constraint_ref=c.constraint_id,
                        satisfied=True,
                        reason=f"Constraint satisfied: {c.relation.value}",
                        decided_at=now,
                    )
                    self._decisions[did] = decision

        # Sequence disordered: events out of order
        for seq_id, event_ids in self._sequence_events.items():
            if len(event_ids) >= 2:
                seq = self._sequences[seq_id]
                for i in range(len(event_ids) - 1):
                    ea = self._temporal_events.get(event_ids[i])
                    eb = self._temporal_events.get(event_ids[i + 1])
                    if ea and eb and ea.occurred_at > eb.occurred_at:
                        vid = stable_identifier("viol-temp", {
                            "sequence": seq_id, "op": "sequence_disordered",
                            "idx": str(i),
                        })
                        if vid not in self._violations:
                            v = {
                                "violation_id": vid,
                                "sequence_id": seq_id,
                                "tenant_id": seq.tenant_id,
                                "operation": "sequence_disordered",
                                "reason": (
                                    f"Sequence {seq_id} event {event_ids[i]} at {ea.occurred_at} "
                                    f"is after event {event_ids[i+1]} at {eb.occurred_at}"
                                ),
                                "detected_at": now,
                            }
                            self._violations[vid] = v
                            new_violations.append(v)

        # Persistence gap: fact ceased then re-persisted (two records for same fact_ref)
        fact_records: dict[str, list[PersistenceRecord]] = {}
        for pr in self._persistence.values():
            fact_records.setdefault(pr.fact_ref, []).append(pr)
        for fact_ref, records in fact_records.items():
            if len(records) >= 2:
                has_ceased = any(r.status == PersistenceStatus.CEASED for r in records)
                has_persisting = any(r.status == PersistenceStatus.PERSISTING for r in records)
                if has_ceased and has_persisting:
                    vid = stable_identifier("viol-temp", {
                        "fact": fact_ref, "op": "persistence_gap",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "fact_ref": fact_ref,
                            "tenant_id": records[0].tenant_id,
                            "operation": "persistence_gap",
                            "reason": f"Fact {fact_ref} has both CEASED and PERSISTING records without explanation",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "temporal_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, dict]:
        return {
            "temporal_events": self._temporal_events,
            "intervals": self._intervals,
            "constraints": self._constraints,
            "persistence": self._persistence,
            "sequences": self._sequences,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, int]:
        return {
            "events": self.event_count,
            "intervals": self.interval_count,
            "constraints": self.constraint_count,
            "persistence": self.persistence_count,
            "sequences": self.sequence_count,
            "decisions": self.decision_count,
            "violations": self.violation_count,
        }

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"events={self.event_count}",
            f"intervals={self.interval_count}",
            f"constraints={self.constraint_count}",
            f"persistence={self.persistence_count}",
            f"sequences={self.sequence_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
