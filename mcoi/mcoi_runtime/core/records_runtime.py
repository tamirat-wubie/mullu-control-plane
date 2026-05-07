"""Purpose: records / retention / legal hold runtime engine.
Governance scope: registering official records; binding retention schedules;
    applying and releasing legal holds; preventing disposal under hold;
    resolving privacy-vs-retention conflicts; tracking immutable evidence
    lineage; producing snapshots, violations, and closure reports.
Dependencies: records_runtime contracts, event_spine, core invariants.
Invariants:
  - Disposal is fail-closed: default is DENY.
  - Legal holds override normal disposal.
  - Evidence records are immutable once preserved.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.records_runtime import (
    DisposalDecision,
    DisposalDisposition,
    DispositionReview,
    EvidenceGrade,
    HoldStatus,
    LegalHoldRecord,
    PreservationDecision,
    RecordAuthority,
    RecordDescriptor,
    RecordKind,
    RecordLink,
    RecordSnapshot,
    RecordViolation,
    RecordsClosureReport,
    RetentionSchedule,
    RetentionStatus,
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
        event_id=stable_identifier("evt-rrec", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class RecordsRuntimeEngine:
    """Records, retention, and legal hold engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._records: dict[str, RecordDescriptor] = {}
        self._schedules: dict[str, RetentionSchedule] = {}
        self._holds: dict[str, LegalHoldRecord] = {}
        self._reviews: dict[str, DispositionReview] = {}
        self._links: dict[str, RecordLink] = {}
        self._violations: dict[str, RecordViolation] = {}
        self._preservation_decisions: dict[str, PreservationDecision] = {}
        self._disposal_decisions: dict[str, DisposalDecision] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def schedule_count(self) -> int:
        return len(self._schedules)

    @property
    def hold_count(self) -> int:
        return len(self._holds)

    @property
    def active_hold_count(self) -> int:
        return sum(1 for h in self._holds.values() if h.status == HoldStatus.ACTIVE)

    @property
    def link_count(self) -> int:
        return len(self._links)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def disposal_count(self) -> int:
        return sum(
            1 for d in self._disposal_decisions.values()
            if d.disposition != DisposalDisposition.DENY
        )

    @property
    def review_count(self) -> int:
        return len(self._reviews)

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------

    def register_record(
        self,
        record_id: str,
        tenant_id: str,
        title: str,
        *,
        kind: RecordKind = RecordKind.OPERATIONAL,
        source_type: str = "",
        source_id: str = "",
        authority: RecordAuthority = RecordAuthority.SYSTEM,
        evidence_grade: EvidenceGrade = EvidenceGrade.PRIMARY,
        classification: str = "",
    ) -> RecordDescriptor:
        """Register an official record."""
        if record_id in self._records:
            raise RuntimeCoreInvariantError("Duplicate record_id")
        now = _now_iso()
        record = RecordDescriptor(
            record_id=record_id,
            tenant_id=tenant_id,
            kind=kind,
            title=title,
            source_type=source_type,
            source_id=source_id,
            authority=authority,
            evidence_grade=evidence_grade,
            classification=classification,
            created_at=now,
        )
        self._records[record_id] = record
        _emit(self._events, "record_registered", {
            "record_id": record_id, "kind": kind.value,
        }, record_id)
        return record

    def get_record(self, record_id: str) -> RecordDescriptor:
        """Get a record by ID."""
        r = self._records.get(record_id)
        if r is None:
            raise RuntimeCoreInvariantError("Unknown record_id")
        return r

    def records_for_tenant(self, tenant_id: str) -> tuple[RecordDescriptor, ...]:
        """Return all records for a tenant."""
        return tuple(r for r in self._records.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Record links (immutable evidence lineage)
    # ------------------------------------------------------------------

    def add_link(
        self,
        link_id: str,
        record_id: str,
        target_type: str,
        target_id: str,
        relationship: str = "source",
    ) -> RecordLink:
        """Add an immutable link between a record and its source."""
        if link_id in self._links:
            raise RuntimeCoreInvariantError("Duplicate link_id")
        if record_id not in self._records:
            raise RuntimeCoreInvariantError("Unknown record_id")
        now = _now_iso()
        link = RecordLink(
            link_id=link_id,
            record_id=record_id,
            target_type=target_type,
            target_id=target_id,
            relationship=relationship,
            created_at=now,
        )
        self._links[link_id] = link
        _emit(self._events, "record_link_added", {
            "link_id": link_id, "record_id": record_id,
            "target_type": target_type, "target_id": target_id,
        }, record_id)
        return link

    def links_for_record(self, record_id: str) -> tuple[RecordLink, ...]:
        """Return all links for a record."""
        return tuple(l for l in self._links.values() if l.record_id == record_id)

    # ------------------------------------------------------------------
    # Retention schedules
    # ------------------------------------------------------------------

    def bind_retention_schedule(
        self,
        schedule_id: str,
        record_id: str,
        tenant_id: str,
        *,
        retention_days: int = 365,
        disposal_disposition: DisposalDisposition = DisposalDisposition.DELETE,
        scope_ref_id: str = "",
        expires_at: str = "",
    ) -> RetentionSchedule:
        """Bind a retention schedule to a record."""
        if schedule_id in self._schedules:
            raise RuntimeCoreInvariantError("Duplicate schedule_id")
        if record_id not in self._records:
            raise RuntimeCoreInvariantError("Unknown record_id")
        now = _now_iso()
        schedule = RetentionSchedule(
            schedule_id=schedule_id,
            record_id=record_id,
            tenant_id=tenant_id,
            retention_days=retention_days,
            status=RetentionStatus.ACTIVE,
            disposal_disposition=disposal_disposition,
            scope_ref_id=scope_ref_id,
            created_at=now,
            expires_at=expires_at,
        )
        self._schedules[schedule_id] = schedule
        _emit(self._events, "retention_schedule_bound", {
            "schedule_id": schedule_id, "record_id": record_id,
            "days": retention_days,
        }, record_id)
        return schedule

    def schedules_for_record(self, record_id: str) -> tuple[RetentionSchedule, ...]:
        """Return all retention schedules for a record."""
        return tuple(s for s in self._schedules.values() if s.record_id == record_id)

    # ------------------------------------------------------------------
    # Legal holds
    # ------------------------------------------------------------------

    def place_hold(
        self,
        hold_id: str,
        record_id: str,
        tenant_id: str,
        *,
        reason: str = "",
        authority: RecordAuthority = RecordAuthority.LEGAL,
    ) -> LegalHoldRecord:
        """Place a legal hold on a record."""
        if hold_id in self._holds:
            raise RuntimeCoreInvariantError("Duplicate hold_id")
        if record_id not in self._records:
            raise RuntimeCoreInvariantError("Unknown record_id")
        now = _now_iso()
        hold = LegalHoldRecord(
            hold_id=hold_id,
            record_id=record_id,
            tenant_id=tenant_id,
            reason=reason,
            authority=authority,
            status=HoldStatus.ACTIVE,
            placed_at=now,
        )
        self._holds[hold_id] = hold

        # Update any active retention schedules to HELD
        for sid, sched in list(self._schedules.items()):
            if sched.record_id == record_id and sched.status == RetentionStatus.ACTIVE:
                updated = RetentionSchedule(
                    schedule_id=sched.schedule_id,
                    record_id=sched.record_id,
                    tenant_id=sched.tenant_id,
                    retention_days=sched.retention_days,
                    status=RetentionStatus.HELD,
                    disposal_disposition=sched.disposal_disposition,
                    scope_ref_id=sched.scope_ref_id,
                    created_at=sched.created_at,
                    expires_at=sched.expires_at,
                    metadata=sched.metadata,
                )
                self._schedules[sid] = updated

        _emit(self._events, "legal_hold_placed", {
            "hold_id": hold_id, "record_id": record_id,
        }, record_id)
        return hold

    def release_hold(self, hold_id: str) -> LegalHoldRecord:
        """Release a legal hold."""
        old = self._holds.get(hold_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown hold_id")
        if old.status != HoldStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Cannot release hold in current status")
        now = _now_iso()
        updated = LegalHoldRecord(
            hold_id=old.hold_id,
            record_id=old.record_id,
            tenant_id=old.tenant_id,
            reason=old.reason,
            authority=old.authority,
            status=HoldStatus.RELEASED,
            placed_at=old.placed_at,
            released_at=now,
            metadata=old.metadata,
        )
        self._holds[hold_id] = updated

        # If no more active holds on this record, restore schedules to ACTIVE
        record_id = old.record_id
        still_held = any(
            h.record_id == record_id and h.status == HoldStatus.ACTIVE
            for h in self._holds.values()
        )
        if not still_held:
            for sid, sched in list(self._schedules.items()):
                if sched.record_id == record_id and sched.status == RetentionStatus.HELD:
                    restored = RetentionSchedule(
                        schedule_id=sched.schedule_id,
                        record_id=sched.record_id,
                        tenant_id=sched.tenant_id,
                        retention_days=sched.retention_days,
                        status=RetentionStatus.ACTIVE,
                        disposal_disposition=sched.disposal_disposition,
                        scope_ref_id=sched.scope_ref_id,
                        created_at=sched.created_at,
                        expires_at=sched.expires_at,
                        metadata=sched.metadata,
                    )
                    self._schedules[sid] = restored

        _emit(self._events, "legal_hold_released", {
            "hold_id": hold_id, "record_id": record_id,
        }, record_id)
        return updated

    def holds_for_record(self, record_id: str) -> tuple[LegalHoldRecord, ...]:
        """Return all holds for a record."""
        return tuple(h for h in self._holds.values() if h.record_id == record_id)

    def active_holds_for_record(self, record_id: str) -> tuple[LegalHoldRecord, ...]:
        """Return active holds for a record."""
        return tuple(
            h for h in self._holds.values()
            if h.record_id == record_id and h.status == HoldStatus.ACTIVE
        )

    def is_under_hold(self, record_id: str) -> bool:
        """Check if a record is under any active legal hold."""
        return any(
            h.record_id == record_id and h.status == HoldStatus.ACTIVE
            for h in self._holds.values()
        )

    # ------------------------------------------------------------------
    # Disposal evaluation
    # ------------------------------------------------------------------

    def evaluate_disposal(
        self,
        record_id: str,
        *,
        authority: RecordAuthority = RecordAuthority.SYSTEM,
        reason: str = "",
    ) -> DisposalDecision:
        """Evaluate whether a record may be disposed. Fail-closed: default DENY."""
        record = self._records.get(record_id)
        if record is None:
            raise RuntimeCoreInvariantError("Unknown record_id")

        now = _now_iso()

        # Legal hold blocks disposal
        if self.is_under_hold(record_id):
            dec = self._make_disposal_decision(
                record_id, record.tenant_id,
                DisposalDisposition.DENY, "record under legal hold",
                authority, now,
            )
            _emit(self._events, "disposal_denied_hold", {
                "record_id": record_id,
            }, record_id)
            return dec

        # Check retention schedules
        schedules = self.schedules_for_record(record_id)
        active_schedules = [s for s in schedules if s.status == RetentionStatus.ACTIVE]

        if active_schedules:
            # Still under active retention — deny
            dec = self._make_disposal_decision(
                record_id, record.tenant_id,
                DisposalDisposition.DENY, "active retention schedule",
                authority, now,
            )
            _emit(self._events, "disposal_denied_retention", {
                "record_id": record_id,
            }, record_id)
            return dec

        # Evidence records require higher authority
        if record.kind == RecordKind.EVIDENCE and authority not in (
            RecordAuthority.LEGAL, RecordAuthority.EXECUTIVE,
        ):
            dec = self._make_disposal_decision(
                record_id, record.tenant_id,
                DisposalDisposition.DENY,
                "evidence records require legal/executive authority",
                authority, now,
            )
            _emit(self._events, "disposal_denied_evidence", {
                "record_id": record_id,
            }, record_id)
            return dec

        # Determine disposal disposition from schedule or default
        expired_schedules = [s for s in schedules if s.status == RetentionStatus.EXPIRED]
        if expired_schedules:
            disposition = expired_schedules[0].disposal_disposition
        else:
            disposition = DisposalDisposition.DELETE

        dec = self._make_disposal_decision(
            record_id, record.tenant_id,
            disposition, "disposal allowed",
            authority, now,
        )
        _emit(self._events, "disposal_allowed", {
            "record_id": record_id, "disposition": disposition.value,
        }, record_id)
        return dec

    def _make_disposal_decision(
        self,
        record_id: str,
        tenant_id: str,
        disposition: DisposalDisposition,
        reason: str,
        authority: RecordAuthority,
        now: str,
    ) -> DisposalDecision:
        did = stable_identifier("disp", {
            "rec": record_id, "ts": now,
        })
        dec = DisposalDecision(
            decision_id=did,
            record_id=record_id,
            tenant_id=tenant_id,
            disposition=disposition,
            reason=reason,
            authority=authority,
            decided_at=now,
        )
        self._disposal_decisions[did] = dec
        return dec

    def dispose_record(
        self,
        record_id: str,
        *,
        authority: RecordAuthority = RecordAuthority.SYSTEM,
        reason: str = "",
    ) -> DisposalDecision:
        """Attempt to dispose a record. Evaluates first, then disposes if allowed."""
        dec = self.evaluate_disposal(record_id, authority=authority, reason=reason)
        if dec.disposition == DisposalDisposition.DENY:
            return dec

        # Mark retention schedules as disposed
        for sid, sched in list(self._schedules.items()):
            if sched.record_id == record_id and sched.status in (
                RetentionStatus.ACTIVE, RetentionStatus.EXPIRED,
            ):
                updated = RetentionSchedule(
                    schedule_id=sched.schedule_id,
                    record_id=sched.record_id,
                    tenant_id=sched.tenant_id,
                    retention_days=sched.retention_days,
                    status=RetentionStatus.DISPOSED,
                    disposal_disposition=sched.disposal_disposition,
                    scope_ref_id=sched.scope_ref_id,
                    created_at=sched.created_at,
                    expires_at=sched.expires_at,
                    metadata=sched.metadata,
                )
                self._schedules[sid] = updated

        _emit(self._events, "record_disposed", {
            "record_id": record_id, "disposition": dec.disposition.value,
        }, record_id)
        return dec

    # ------------------------------------------------------------------
    # Preservation decision
    # ------------------------------------------------------------------

    def preservation_decision(
        self,
        record_id: str,
        *,
        preserve: bool = True,
        reason: str = "",
        authority: RecordAuthority = RecordAuthority.SYSTEM,
    ) -> PreservationDecision:
        """Record a preservation decision."""
        if record_id not in self._records:
            raise RuntimeCoreInvariantError("Unknown record_id")
        now = _now_iso()
        did = stable_identifier("pres", {"rec": record_id, "ts": now})
        dec = PreservationDecision(
            decision_id=did,
            record_id=record_id,
            preserve=preserve,
            reason=reason,
            authority=authority,
            decided_at=now,
        )
        self._preservation_decisions[did] = dec
        _emit(self._events, "preservation_decided", {
            "record_id": record_id, "preserve": preserve,
        }, record_id)
        return dec

    # ------------------------------------------------------------------
    # Disposition review
    # ------------------------------------------------------------------

    def submit_review(
        self,
        review_id: str,
        record_id: str,
        reviewer_id: str,
        *,
        decision: DisposalDisposition = DisposalDisposition.DENY,
        reason: str = "",
    ) -> DispositionReview:
        """Submit a disposition review."""
        if review_id in self._reviews:
            raise RuntimeCoreInvariantError("Duplicate review_id")
        if record_id not in self._records:
            raise RuntimeCoreInvariantError("Unknown record_id")
        now = _now_iso()
        review = DispositionReview(
            review_id=review_id,
            record_id=record_id,
            reviewer_id=reviewer_id,
            decision=decision,
            reason=reason,
            reviewed_at=now,
        )
        self._reviews[review_id] = review
        _emit(self._events, "disposition_reviewed", {
            "review_id": review_id, "record_id": record_id,
            "decision": decision.value,
        }, record_id)
        return review

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_record_violations(self) -> tuple[RecordViolation, ...]:
        """Detect records governance violations."""
        now = _now_iso()
        new_violations: list[RecordViolation] = []

        for dec in self._disposal_decisions.values():
            if dec.disposition == DisposalDisposition.DENY:
                vid = stable_identifier("viol-rec", {"dec": dec.decision_id})
                if vid in self._violations:
                    continue
                record = self._records.get(dec.record_id)
                tenant_id = record.tenant_id if record else dec.tenant_id
                violation = RecordViolation(
                    violation_id=vid,
                    record_id=dec.record_id,
                    tenant_id=tenant_id,
                    operation="disposal_denied",
                    reason=dec.reason,
                    detected_at=now,
                )
                self._violations[vid] = violation
                new_violations.append(violation)

        if new_violations:
            _emit(self._events, "record_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[RecordViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def records_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> RecordSnapshot:
        """Capture a point-in-time records snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snapshot = RecordSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_records=self.record_count,
            total_schedules=self.schedule_count,
            total_holds=self.hold_count,
            active_holds=self.active_hold_count,
            total_links=self.link_count,
            total_disposals=self.disposal_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "records_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"records={self.record_count}",
            f"schedules={self.schedule_count}",
            f"holds={self.hold_count}",
            f"active_holds={self.active_hold_count}",
            f"links={self.link_count}",
            f"disposals={self.disposal_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
