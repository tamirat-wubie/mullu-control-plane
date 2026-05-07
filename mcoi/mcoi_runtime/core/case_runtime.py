"""Purpose: case / investigation / evidence review runtime engine.
Governance scope: opening and closing cases; assigning investigators and
    reviewers; collecting and tracking evidence from records, artifacts, events,
    and memory; recording reviews and findings; enforcing evidence status
    transitions; producing immutable snapshots and closure reports.
Dependencies: case_runtime contracts, event_spine, core invariants.
Invariants:
  - Evidence items are immutable once admitted.
  - Review disposition is fail-closed: default REQUIRES_REVIEW.
  - Case closure requires explicit decision.
  - Legal-hold evidence cannot be removed from a case.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.case_runtime import (
    CaseAssignment,
    CaseClosureDisposition,
    CaseClosureReport,
    CaseDecision,
    CaseKind,
    CaseRecord,
    CaseSeverity,
    CaseSnapshot,
    CaseStatus,
    CaseViolation,
    EvidenceCollection,
    EvidenceItem,
    EvidenceStatus,
    FindingRecord,
    FindingSeverity,
    ReviewDisposition,
    ReviewRecord,
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
        event_id=stable_identifier("evt-case", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CaseRuntimeEngine:
    """Case, investigation, and evidence review engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._cases: dict[str, CaseRecord] = {}
        self._assignments: dict[str, CaseAssignment] = {}
        self._evidence: dict[str, EvidenceItem] = {}
        self._collections: dict[str, EvidenceCollection] = {}
        self._reviews: dict[str, ReviewRecord] = {}
        self._findings: dict[str, FindingRecord] = {}
        self._decisions: dict[str, CaseDecision] = {}
        self._violations: dict[str, CaseViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def case_count(self) -> int:
        return len(self._cases)

    @property
    def open_case_count(self) -> int:
        return sum(
            1 for c in self._cases.values()
            if c.status not in (CaseStatus.CLOSED,)
        )

    @property
    def evidence_count(self) -> int:
        return len(self._evidence)

    @property
    def review_count(self) -> int:
        return len(self._reviews)

    @property
    def finding_count(self) -> int:
        return len(self._findings)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def collection_count(self) -> int:
        return len(self._collections)

    # ------------------------------------------------------------------
    # Case management
    # ------------------------------------------------------------------

    def open_case(
        self,
        case_id: str,
        tenant_id: str,
        title: str,
        *,
        kind: CaseKind = CaseKind.INCIDENT,
        severity: CaseSeverity = CaseSeverity.MEDIUM,
        description: str = "",
        opened_by: str = "system",
    ) -> CaseRecord:
        """Open a new case or investigation."""
        if case_id in self._cases:
            raise RuntimeCoreInvariantError("Duplicate case_id")
        now = _now_iso()
        case = CaseRecord(
            case_id=case_id,
            tenant_id=tenant_id,
            kind=kind,
            severity=severity,
            status=CaseStatus.OPEN,
            title=title,
            description=description,
            opened_by=opened_by,
            opened_at=now,
        )
        self._cases[case_id] = case
        _emit(self._events, "case_opened", {
            "case_id": case_id, "kind": kind.value, "severity": severity.value,
        }, case_id)
        return case

    def get_case(self, case_id: str) -> CaseRecord:
        """Get a case by ID."""
        c = self._cases.get(case_id)
        if c is None:
            raise RuntimeCoreInvariantError("Unknown case_id")
        return c

    def cases_for_tenant(self, tenant_id: str) -> tuple[CaseRecord, ...]:
        """Return all cases for a tenant."""
        return tuple(c for c in self._cases.values() if c.tenant_id == tenant_id)

    def update_case_status(self, case_id: str, status: CaseStatus) -> CaseRecord:
        """Update a case's status."""
        old = self._cases.get(case_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown case_id")
        if old.status == CaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("Cannot update a closed case")
        if not isinstance(status, CaseStatus):
            raise ValueError("status must be a CaseStatus")
        updated = CaseRecord(
            case_id=old.case_id,
            tenant_id=old.tenant_id,
            kind=old.kind,
            severity=old.severity,
            status=status,
            title=old.title,
            description=old.description,
            opened_by=old.opened_by,
            opened_at=old.opened_at,
            closed_at=old.closed_at,
            metadata=old.metadata,
        )
        self._cases[case_id] = updated
        _emit(self._events, "case_status_updated", {
            "case_id": case_id, "status": status.value,
        }, case_id)
        return updated

    def escalate_case(self, case_id: str, severity: CaseSeverity) -> CaseRecord:
        """Escalate a case's severity."""
        old = self._cases.get(case_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown case_id")
        if old.status == CaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("Cannot escalate a closed case")
        updated = CaseRecord(
            case_id=old.case_id,
            tenant_id=old.tenant_id,
            kind=old.kind,
            severity=severity,
            status=CaseStatus.ESCALATED,
            title=old.title,
            description=old.description,
            opened_by=old.opened_by,
            opened_at=old.opened_at,
            closed_at=old.closed_at,
            metadata=old.metadata,
        )
        self._cases[case_id] = updated
        _emit(self._events, "case_escalated", {
            "case_id": case_id, "severity": severity.value,
        }, case_id)
        return updated

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def assign_case(
        self,
        assignment_id: str,
        case_id: str,
        assignee_id: str,
        *,
        role: str = "investigator",
    ) -> CaseAssignment:
        """Assign an investigator or reviewer to a case."""
        if assignment_id in self._assignments:
            raise RuntimeCoreInvariantError("Duplicate assignment_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        now = _now_iso()
        assignment = CaseAssignment(
            assignment_id=assignment_id,
            case_id=case_id,
            assignee_id=assignee_id,
            role=role,
            assigned_at=now,
        )
        self._assignments[assignment_id] = assignment
        _emit(self._events, "case_assigned", {
            "assignment_id": assignment_id, "case_id": case_id,
            "assignee_id": assignee_id, "role": role,
        }, case_id)
        return assignment

    def assignments_for_case(self, case_id: str) -> tuple[CaseAssignment, ...]:
        """Return all assignments for a case."""
        return tuple(a for a in self._assignments.values() if a.case_id == case_id)

    # ------------------------------------------------------------------
    # Evidence management
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        evidence_id: str,
        case_id: str,
        source_type: str,
        source_id: str,
        *,
        title: str = "Evidence",
        description: str = "",
        submitted_by: str = "system",
        status: EvidenceStatus = EvidenceStatus.PENDING,
    ) -> EvidenceItem:
        """Add an evidence item to a case."""
        if evidence_id in self._evidence:
            raise RuntimeCoreInvariantError("Duplicate evidence_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        now = _now_iso()
        item = EvidenceItem(
            evidence_id=evidence_id,
            case_id=case_id,
            source_type=source_type,
            source_id=source_id,
            status=status,
            title=title,
            description=description,
            submitted_by=submitted_by,
            submitted_at=now,
        )
        self._evidence[evidence_id] = item
        _emit(self._events, "evidence_added", {
            "evidence_id": evidence_id, "case_id": case_id,
            "source_type": source_type, "source_id": source_id,
        }, case_id)
        return item

    def get_evidence(self, evidence_id: str) -> EvidenceItem:
        """Get an evidence item by ID."""
        e = self._evidence.get(evidence_id)
        if e is None:
            raise RuntimeCoreInvariantError("Unknown evidence_id")
        return e

    def evidence_for_case(self, case_id: str) -> tuple[EvidenceItem, ...]:
        """Return all evidence for a case."""
        return tuple(e for e in self._evidence.values() if e.case_id == case_id)

    def admit_evidence(self, evidence_id: str) -> EvidenceItem:
        """Admit an evidence item (PENDING → ADMITTED)."""
        old = self._evidence.get(evidence_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown evidence_id")
        if old.status != EvidenceStatus.PENDING:
            raise RuntimeCoreInvariantError(
                "can only admit pending evidence from current status"
            )
        updated = EvidenceItem(
            evidence_id=old.evidence_id,
            case_id=old.case_id,
            source_type=old.source_type,
            source_id=old.source_id,
            status=EvidenceStatus.ADMITTED,
            title=old.title,
            description=old.description,
            submitted_by=old.submitted_by,
            submitted_at=old.submitted_at,
            metadata=old.metadata,
        )
        self._evidence[evidence_id] = updated
        _emit(self._events, "evidence_admitted", {
            "evidence_id": evidence_id, "case_id": old.case_id,
        }, old.case_id)
        return updated

    def exclude_evidence(self, evidence_id: str, *, reason: str = "") -> EvidenceItem:
        """Exclude an evidence item from a case."""
        old = self._evidence.get(evidence_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown evidence_id")
        if old.source_type == "legal_hold":
            raise RuntimeCoreInvariantError(
                "Cannot exclude legal-hold evidence from case"
            )
        updated = EvidenceItem(
            evidence_id=old.evidence_id,
            case_id=old.case_id,
            source_type=old.source_type,
            source_id=old.source_id,
            status=EvidenceStatus.EXCLUDED,
            title=old.title,
            description=old.description,
            submitted_by=old.submitted_by,
            submitted_at=old.submitted_at,
            metadata=old.metadata,
        )
        self._evidence[evidence_id] = updated
        _emit(self._events, "evidence_excluded", {
            "evidence_id": evidence_id, "case_id": old.case_id,
            "reason": reason,
        }, old.case_id)
        return updated

    # ------------------------------------------------------------------
    # Evidence collections
    # ------------------------------------------------------------------

    def collect_evidence(
        self,
        collection_id: str,
        case_id: str,
        evidence_ids: tuple[str, ...],
        *,
        title: str = "Evidence collection",
    ) -> EvidenceCollection:
        """Group evidence items into a collection."""
        if collection_id in self._collections:
            raise RuntimeCoreInvariantError("Duplicate collection_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        for eid in evidence_ids:
            if eid not in self._evidence:
                raise RuntimeCoreInvariantError("Unknown evidence_id")
        now = _now_iso()
        collection = EvidenceCollection(
            collection_id=collection_id,
            case_id=case_id,
            title=title,
            evidence_ids=evidence_ids,
            created_at=now,
        )
        self._collections[collection_id] = collection
        _emit(self._events, "evidence_collected", {
            "collection_id": collection_id, "case_id": case_id,
            "count": len(evidence_ids),
        }, case_id)
        return collection

    def collections_for_case(self, case_id: str) -> tuple[EvidenceCollection, ...]:
        """Return all evidence collections for a case."""
        return tuple(c for c in self._collections.values() if c.case_id == case_id)

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def review_evidence(
        self,
        review_id: str,
        case_id: str,
        evidence_id: str,
        reviewer_id: str,
        *,
        disposition: ReviewDisposition = ReviewDisposition.REQUIRES_REVIEW,
        notes: str = "",
    ) -> ReviewRecord:
        """Record a review of evidence."""
        if review_id in self._reviews:
            raise RuntimeCoreInvariantError("Duplicate review_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        if evidence_id not in self._evidence:
            raise RuntimeCoreInvariantError("Unknown evidence_id")
        now = _now_iso()
        review = ReviewRecord(
            review_id=review_id,
            case_id=case_id,
            evidence_id=evidence_id,
            reviewer_id=reviewer_id,
            disposition=disposition,
            notes=notes,
            reviewed_at=now,
        )
        self._reviews[review_id] = review

        # Transition evidence status to REVIEWED if accepted
        old_ev = self._evidence[evidence_id]
        if disposition == ReviewDisposition.ACCEPTED and old_ev.status in (
            EvidenceStatus.PENDING, EvidenceStatus.ADMITTED,
        ):
            updated_ev = EvidenceItem(
                evidence_id=old_ev.evidence_id,
                case_id=old_ev.case_id,
                source_type=old_ev.source_type,
                source_id=old_ev.source_id,
                status=EvidenceStatus.REVIEWED,
                title=old_ev.title,
                description=old_ev.description,
                submitted_by=old_ev.submitted_by,
                submitted_at=old_ev.submitted_at,
                metadata=old_ev.metadata,
            )
            self._evidence[evidence_id] = updated_ev
        elif disposition == ReviewDisposition.REJECTED and old_ev.status in (
            EvidenceStatus.PENDING, EvidenceStatus.ADMITTED,
        ):
            updated_ev = EvidenceItem(
                evidence_id=old_ev.evidence_id,
                case_id=old_ev.case_id,
                source_type=old_ev.source_type,
                source_id=old_ev.source_id,
                status=EvidenceStatus.CHALLENGED,
                title=old_ev.title,
                description=old_ev.description,
                submitted_by=old_ev.submitted_by,
                submitted_at=old_ev.submitted_at,
                metadata=old_ev.metadata,
            )
            self._evidence[evidence_id] = updated_ev

        _emit(self._events, "evidence_reviewed", {
            "review_id": review_id, "case_id": case_id,
            "evidence_id": evidence_id, "disposition": disposition.value,
        }, case_id)
        return review

    def reviews_for_case(self, case_id: str) -> tuple[ReviewRecord, ...]:
        """Return all reviews for a case."""
        return tuple(r for r in self._reviews.values() if r.case_id == case_id)

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def record_finding(
        self,
        finding_id: str,
        case_id: str,
        title: str,
        *,
        severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
        description: str = "",
        evidence_ids: tuple[str, ...] = (),
        remediation: str = "",
    ) -> FindingRecord:
        """Record a finding discovered during investigation."""
        if finding_id in self._findings:
            raise RuntimeCoreInvariantError("Duplicate finding_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        now = _now_iso()
        finding = FindingRecord(
            finding_id=finding_id,
            case_id=case_id,
            severity=severity,
            title=title,
            description=description,
            evidence_ids=evidence_ids,
            remediation=remediation,
            found_at=now,
        )
        self._findings[finding_id] = finding

        # Auto-escalate case if finding severity is HIGH or CRITICAL
        case = self._cases[case_id]
        if severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL) and case.status != CaseStatus.CLOSED:
            sev_map = {
                FindingSeverity.HIGH: CaseSeverity.HIGH,
                FindingSeverity.CRITICAL: CaseSeverity.CRITICAL,
            }
            _sev_order = {
                CaseSeverity.LOW: 0,
                CaseSeverity.MEDIUM: 1,
                CaseSeverity.HIGH: 2,
                CaseSeverity.CRITICAL: 3,
            }
            target_severity = sev_map[severity]
            if _sev_order.get(target_severity, 0) > _sev_order.get(case.severity, 0):
                self.escalate_case(case_id, target_severity)

        _emit(self._events, "finding_recorded", {
            "finding_id": finding_id, "case_id": case_id,
            "severity": severity.value,
        }, case_id)
        return finding

    def findings_for_case(self, case_id: str) -> tuple[FindingRecord, ...]:
        """Return all findings for a case."""
        return tuple(f for f in self._findings.values() if f.case_id == case_id)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def make_case_decision(
        self,
        decision_id: str,
        case_id: str,
        *,
        disposition: CaseClosureDisposition = CaseClosureDisposition.UNRESOLVED,
        decided_by: str = "system",
        reason: str = "",
    ) -> CaseDecision:
        """Make a formal decision on a case."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("Duplicate decision_id")
        if case_id not in self._cases:
            raise RuntimeCoreInvariantError("Unknown case_id")
        now = _now_iso()
        decision = CaseDecision(
            decision_id=decision_id,
            case_id=case_id,
            disposition=disposition,
            decided_by=decided_by,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "case_decision_made", {
            "decision_id": decision_id, "case_id": case_id,
            "disposition": disposition.value,
        }, case_id)
        return decision

    def close_case(
        self,
        case_id: str,
        *,
        disposition: CaseClosureDisposition = CaseClosureDisposition.RESOLVED,
        decided_by: str = "system",
        reason: str = "",
    ) -> CaseClosureReport:
        """Close a case and produce a closure report."""
        case = self._cases.get(case_id)
        if case is None:
            raise RuntimeCoreInvariantError("Unknown case_id")
        if case.status == CaseStatus.CLOSED:
            raise RuntimeCoreInvariantError("Case is already closed")

        now = _now_iso()

        # Make the closing decision
        dec_id = stable_identifier("cdec", {"case": case_id, "ts": now})
        self.make_case_decision(
            dec_id, case_id,
            disposition=disposition,
            decided_by=decided_by,
            reason=reason,
        )

        # Update case to CLOSED
        closed_case = CaseRecord(
            case_id=case.case_id,
            tenant_id=case.tenant_id,
            kind=case.kind,
            severity=case.severity,
            status=CaseStatus.CLOSED,
            title=case.title,
            description=case.description,
            opened_by=case.opened_by,
            opened_at=case.opened_at,
            closed_at=now,
            metadata=case.metadata,
        )
        self._cases[case_id] = closed_case

        # Count case-specific evidence, reviews, findings, violations
        case_evidence = len([e for e in self._evidence.values() if e.case_id == case_id])
        case_reviews = len([r for r in self._reviews.values() if r.case_id == case_id])
        case_findings = len([f for f in self._findings.values() if f.case_id == case_id])
        case_violations = len([v for v in self._violations.values() if v.case_id == case_id])

        report = CaseClosureReport(
            report_id=stable_identifier("crpt", {"case": case_id, "ts": now}),
            case_id=case_id,
            tenant_id=case.tenant_id,
            disposition=disposition,
            total_evidence=case_evidence,
            total_reviews=case_reviews,
            total_findings=case_findings,
            total_violations=case_violations,
            closed_at=now,
        )

        _emit(self._events, "case_closed", {
            "case_id": case_id, "disposition": disposition.value,
            "evidence": case_evidence, "findings": case_findings,
        }, case_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_case_violations(self) -> tuple[CaseViolation, ...]:
        """Detect case governance violations."""
        now = _now_iso()
        new_violations: list[CaseViolation] = []

        for case in self._cases.values():
            # Violation: case closed without any decision
            if case.status == CaseStatus.CLOSED:
                case_decisions = [d for d in self._decisions.values() if d.case_id == case.case_id]
                if not case_decisions:
                    vid = stable_identifier("viol-case", {"case": case.case_id, "op": "closed_no_decision"})
                    if vid not in self._violations:
                        v = CaseViolation(
                            violation_id=vid,
                            case_id=case.case_id,
                            tenant_id=case.tenant_id,
                            operation="closed_without_decision",
                            reason="Case closed without a formal decision",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

            # Violation: evidence pending review on closed case
            if case.status == CaseStatus.CLOSED:
                pending = [
                    e for e in self._evidence.values()
                    if e.case_id == case.case_id and e.status == EvidenceStatus.PENDING
                ]
                if pending:
                    vid = stable_identifier("viol-case", {"case": case.case_id, "op": "unreviewed_evidence"})
                    if vid not in self._violations:
                        v = CaseViolation(
                            violation_id=vid,
                            case_id=case.case_id,
                            tenant_id=case.tenant_id,
                            operation="unreviewed_evidence_on_closure",
                            reason="pending evidence on closed case",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "case_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_case(self, case_id: str) -> tuple[CaseViolation, ...]:
        """Return all violations for a case."""
        return tuple(v for v in self._violations.values() if v.case_id == case_id)

    def violations_for_tenant(self, tenant_id: str) -> tuple[CaseViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def case_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> CaseSnapshot:
        """Capture a point-in-time case state snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snapshot = CaseSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_cases=self.case_count,
            open_cases=self.open_case_count,
            total_evidence=self.evidence_count,
            total_reviews=self.review_count,
            total_findings=self.finding_count,
            total_decisions=self.decision_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "case_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"cases={self.case_count}",
            f"open={self.open_case_count}",
            f"evidence={self.evidence_count}",
            f"reviews={self.review_count}",
            f"findings={self.finding_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
