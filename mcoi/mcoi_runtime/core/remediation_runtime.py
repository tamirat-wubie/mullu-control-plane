"""Purpose: remediation / corrective action runtime engine.
Governance scope: creating remediation items from findings/cases; assigning
    owners and deadlines; tracking corrective and preventive actions; requiring
    verification before closure; reopening on failed verification; escalating
    overdue or ineffective remediation; producing immutable snapshots and
    closure reports.
Dependencies: remediation_runtime contracts, event_spine, core invariants.
Invariants:
  - Remediation cannot close without verification.
  - Failed verification reopens remediation.
  - Overdue remediation escalates.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.remediation_runtime import (
    CorrectiveAction,
    PreventiveAction,
    PreventiveActionStatus,
    RemediationAssignment,
    RemediationClosureReport,
    RemediationDecision,
    RemediationDisposition,
    RemediationPriority,
    RemediationRecord,
    RemediationSnapshot,
    RemediationStatus,
    RemediationType,
    RemediationViolation,
    ReopenRecord,
    VerificationRecord,
    RemediationVerificationStatus,
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
        event_id=stable_identifier("evt-rmed", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_CLOSED_STATUSES = frozenset({RemediationStatus.CLOSED, RemediationStatus.VERIFIED})


class RemediationRuntimeEngine:
    """Remediation, corrective action, and preventive action engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._remediations: dict[str, RemediationRecord] = {}
        self._corrective: dict[str, CorrectiveAction] = {}
        self._preventive: dict[str, PreventiveAction] = {}
        self._assignments: dict[str, RemediationAssignment] = {}
        self._verifications: dict[str, VerificationRecord] = {}
        self._reopens: dict[str, ReopenRecord] = {}
        self._decisions: dict[str, RemediationDecision] = {}
        self._violations: dict[str, RemediationViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def remediation_count(self) -> int:
        return len(self._remediations)

    @property
    def open_remediation_count(self) -> int:
        return sum(
            1 for r in self._remediations.values()
            if r.status not in _CLOSED_STATUSES
        )

    @property
    def corrective_count(self) -> int:
        return len(self._corrective)

    @property
    def preventive_count(self) -> int:
        return len(self._preventive)

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def verification_count(self) -> int:
        return len(self._verifications)

    @property
    def reopen_count(self) -> int:
        return len(self._reopens)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Remediation management
    # ------------------------------------------------------------------

    def create_remediation(
        self,
        remediation_id: str,
        tenant_id: str,
        title: str,
        *,
        case_id: str = "",
        finding_id: str = "",
        remediation_type: RemediationType = RemediationType.CORRECTIVE,
        priority: RemediationPriority = RemediationPriority.MEDIUM,
        description: str = "",
        owner_id: str = "system",
        deadline: str = "",
    ) -> RemediationRecord:
        """Create a new remediation item."""
        if remediation_id in self._remediations:
            raise RuntimeCoreInvariantError(f"Duplicate remediation_id: {remediation_id}")
        now = _now_iso()
        rec = RemediationRecord(
            remediation_id=remediation_id,
            tenant_id=tenant_id,
            case_id=case_id,
            finding_id=finding_id,
            remediation_type=remediation_type,
            priority=priority,
            status=RemediationStatus.OPEN,
            title=title,
            description=description,
            owner_id=owner_id,
            deadline=deadline,
            created_at=now,
        )
        self._remediations[remediation_id] = rec
        _emit(self._events, "remediation_created", {
            "remediation_id": remediation_id,
            "type": remediation_type.value,
            "priority": priority.value,
        }, remediation_id)
        return rec

    def get_remediation(self, remediation_id: str) -> RemediationRecord:
        """Get a remediation by ID."""
        r = self._remediations.get(remediation_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        return r

    def remediations_for_tenant(self, tenant_id: str) -> tuple[RemediationRecord, ...]:
        """Return all remediations for a tenant."""
        return tuple(r for r in self._remediations.values() if r.tenant_id == tenant_id)

    def _update_remediation_status(
        self, remediation_id: str, status: RemediationStatus
    ) -> RemediationRecord:
        old = self._remediations[remediation_id]
        updated = RemediationRecord(
            remediation_id=old.remediation_id,
            tenant_id=old.tenant_id,
            case_id=old.case_id,
            finding_id=old.finding_id,
            remediation_type=old.remediation_type,
            priority=old.priority,
            status=status,
            title=old.title,
            description=old.description,
            owner_id=old.owner_id,
            deadline=old.deadline,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._remediations[remediation_id] = updated
        return updated

    def start_remediation(self, remediation_id: str) -> RemediationRecord:
        """Move remediation to IN_PROGRESS."""
        r = self.get_remediation(remediation_id)
        if r.status in _CLOSED_STATUSES:
            raise RuntimeCoreInvariantError("Cannot start a closed remediation")
        updated = self._update_remediation_status(remediation_id, RemediationStatus.IN_PROGRESS)
        _emit(self._events, "remediation_started", {
            "remediation_id": remediation_id,
        }, remediation_id)
        return updated

    def submit_for_verification(self, remediation_id: str) -> RemediationRecord:
        """Move remediation to PENDING_VERIFICATION."""
        r = self.get_remediation(remediation_id)
        if r.status in _CLOSED_STATUSES:
            raise RuntimeCoreInvariantError("Cannot submit closed remediation for verification")
        updated = self._update_remediation_status(remediation_id, RemediationStatus.PENDING_VERIFICATION)
        _emit(self._events, "remediation_submitted_for_verification", {
            "remediation_id": remediation_id,
        }, remediation_id)
        return updated

    def escalate_remediation(
        self, remediation_id: str, *, priority: RemediationPriority | None = None
    ) -> RemediationRecord:
        """Escalate a remediation item."""
        old = self.get_remediation(remediation_id)
        if old.status in _CLOSED_STATUSES:
            raise RuntimeCoreInvariantError("Cannot escalate a closed remediation")
        new_priority = priority if priority is not None else old.priority
        updated = RemediationRecord(
            remediation_id=old.remediation_id,
            tenant_id=old.tenant_id,
            case_id=old.case_id,
            finding_id=old.finding_id,
            remediation_type=old.remediation_type,
            priority=new_priority,
            status=RemediationStatus.ESCALATED,
            title=old.title,
            description=old.description,
            owner_id=old.owner_id,
            deadline=old.deadline,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._remediations[remediation_id] = updated
        _emit(self._events, "remediation_escalated", {
            "remediation_id": remediation_id,
            "priority": new_priority.value,
        }, remediation_id)
        return updated

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def assign_remediation(
        self,
        assignment_id: str,
        remediation_id: str,
        assignee_id: str,
        *,
        role: str = "owner",
    ) -> RemediationAssignment:
        """Assign an owner to a remediation item."""
        if assignment_id in self._assignments:
            raise RuntimeCoreInvariantError(f"Duplicate assignment_id: {assignment_id}")
        if remediation_id not in self._remediations:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        now = _now_iso()
        assignment = RemediationAssignment(
            assignment_id=assignment_id,
            remediation_id=remediation_id,
            assignee_id=assignee_id,
            role=role,
            assigned_at=now,
        )
        self._assignments[assignment_id] = assignment
        _emit(self._events, "remediation_assigned", {
            "assignment_id": assignment_id,
            "remediation_id": remediation_id,
            "assignee_id": assignee_id,
        }, remediation_id)
        return assignment

    def assignments_for_remediation(self, remediation_id: str) -> tuple[RemediationAssignment, ...]:
        """Return all assignments for a remediation."""
        return tuple(a for a in self._assignments.values() if a.remediation_id == remediation_id)

    # ------------------------------------------------------------------
    # Corrective actions
    # ------------------------------------------------------------------

    def add_corrective_action(
        self,
        action_id: str,
        remediation_id: str,
        title: str,
        *,
        description: str = "",
        owner_id: str = "system",
        deadline: str = "",
    ) -> CorrectiveAction:
        """Add a corrective action to a remediation."""
        if action_id in self._corrective:
            raise RuntimeCoreInvariantError(f"Duplicate corrective action_id: {action_id}")
        if remediation_id not in self._remediations:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        now = _now_iso()
        action = CorrectiveAction(
            action_id=action_id,
            remediation_id=remediation_id,
            title=title,
            description=description,
            owner_id=owner_id,
            status=RemediationStatus.OPEN,
            deadline=deadline,
            created_at=now,
        )
        self._corrective[action_id] = action
        _emit(self._events, "corrective_action_added", {
            "action_id": action_id,
            "remediation_id": remediation_id,
        }, remediation_id)
        return action

    def complete_corrective_action(self, action_id: str) -> CorrectiveAction:
        """Mark a corrective action as completed (PENDING_VERIFICATION)."""
        old = self._corrective.get(action_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown corrective action_id: {action_id}")
        now = _now_iso()
        updated = CorrectiveAction(
            action_id=old.action_id,
            remediation_id=old.remediation_id,
            title=old.title,
            description=old.description,
            owner_id=old.owner_id,
            status=RemediationStatus.PENDING_VERIFICATION,
            deadline=old.deadline,
            completed_at=now,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._corrective[action_id] = updated
        _emit(self._events, "corrective_action_completed", {
            "action_id": action_id,
        }, old.remediation_id)
        return updated

    def corrective_actions_for_remediation(self, remediation_id: str) -> tuple[CorrectiveAction, ...]:
        """Return all corrective actions for a remediation."""
        return tuple(a for a in self._corrective.values() if a.remediation_id == remediation_id)

    # ------------------------------------------------------------------
    # Preventive actions
    # ------------------------------------------------------------------

    def add_preventive_action(
        self,
        action_id: str,
        remediation_id: str,
        title: str,
        target_type: str,
        target_id: str,
        *,
        description: str = "",
        owner_id: str = "system",
    ) -> PreventiveAction:
        """Add a preventive action linked to a target (program/control/campaign)."""
        if action_id in self._preventive:
            raise RuntimeCoreInvariantError(f"Duplicate preventive action_id: {action_id}")
        if remediation_id not in self._remediations:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        now = _now_iso()
        action = PreventiveAction(
            action_id=action_id,
            remediation_id=remediation_id,
            title=title,
            description=description,
            target_type=target_type,
            target_id=target_id,
            status=PreventiveActionStatus.PROPOSED,
            owner_id=owner_id,
            created_at=now,
        )
        self._preventive[action_id] = action
        _emit(self._events, "preventive_action_added", {
            "action_id": action_id,
            "remediation_id": remediation_id,
            "target_type": target_type,
            "target_id": target_id,
        }, remediation_id)
        return action

    def approve_preventive_action(self, action_id: str) -> PreventiveAction:
        """Approve a preventive action."""
        old = self._preventive.get(action_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown preventive action_id: {action_id}")
        if old.status != PreventiveActionStatus.PROPOSED:
            raise RuntimeCoreInvariantError(
                f"Can only approve PROPOSED preventive actions, got {old.status.value}"
            )
        updated = PreventiveAction(
            action_id=old.action_id,
            remediation_id=old.remediation_id,
            title=old.title,
            description=old.description,
            target_type=old.target_type,
            target_id=old.target_id,
            status=PreventiveActionStatus.APPROVED,
            owner_id=old.owner_id,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._preventive[action_id] = updated
        _emit(self._events, "preventive_action_approved", {
            "action_id": action_id,
        }, old.remediation_id)
        return updated

    def implement_preventive_action(self, action_id: str) -> PreventiveAction:
        """Mark a preventive action as implemented."""
        old = self._preventive.get(action_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown preventive action_id: {action_id}")
        if old.status != PreventiveActionStatus.APPROVED:
            raise RuntimeCoreInvariantError(
                f"Can only implement APPROVED preventive actions, got {old.status.value}"
            )
        updated = PreventiveAction(
            action_id=old.action_id,
            remediation_id=old.remediation_id,
            title=old.title,
            description=old.description,
            target_type=old.target_type,
            target_id=old.target_id,
            status=PreventiveActionStatus.IMPLEMENTED,
            owner_id=old.owner_id,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._preventive[action_id] = updated
        _emit(self._events, "preventive_action_implemented", {
            "action_id": action_id,
        }, old.remediation_id)
        return updated

    def preventive_actions_for_remediation(self, remediation_id: str) -> tuple[PreventiveAction, ...]:
        """Return all preventive actions for a remediation."""
        return tuple(a for a in self._preventive.values() if a.remediation_id == remediation_id)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_remediation(
        self,
        verification_id: str,
        remediation_id: str,
        verifier_id: str,
        *,
        status: RemediationVerificationStatus = RemediationVerificationStatus.PENDING,
        notes: str = "",
    ) -> VerificationRecord:
        """Record a verification check for a remediation."""
        if verification_id in self._verifications:
            raise RuntimeCoreInvariantError(f"Duplicate verification_id: {verification_id}")
        if remediation_id not in self._remediations:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        now = _now_iso()
        verification = VerificationRecord(
            verification_id=verification_id,
            remediation_id=remediation_id,
            verifier_id=verifier_id,
            status=status,
            notes=notes,
            verified_at=now,
        )
        self._verifications[verification_id] = verification

        # Auto-transition remediation based on verification result
        rem = self._remediations[remediation_id]
        if status == RemediationVerificationStatus.PASSED and rem.status != RemediationStatus.CLOSED:
            self._update_remediation_status(remediation_id, RemediationStatus.VERIFIED)
        elif status == RemediationVerificationStatus.FAILED and rem.status not in _CLOSED_STATUSES:
            self._update_remediation_status(remediation_id, RemediationStatus.REOPENED)
            # Auto-create reopen record
            reopen_id = stable_identifier("reopen", {"ver": verification_id, "ts": now})
            reopen = ReopenRecord(
                reopen_id=reopen_id,
                remediation_id=remediation_id,
                reason=f"Verification failed: {notes}" if notes else "Verification failed",
                reopened_by=verifier_id,
                reopened_at=now,
            )
            self._reopens[reopen_id] = reopen

        _emit(self._events, "remediation_verified", {
            "verification_id": verification_id,
            "remediation_id": remediation_id,
            "status": status.value,
        }, remediation_id)
        return verification

    def verifications_for_remediation(self, remediation_id: str) -> tuple[VerificationRecord, ...]:
        """Return all verifications for a remediation."""
        return tuple(v for v in self._verifications.values() if v.remediation_id == remediation_id)

    # ------------------------------------------------------------------
    # Reopen
    # ------------------------------------------------------------------

    def reopen_remediation(
        self,
        reopen_id: str,
        remediation_id: str,
        *,
        reason: str = "",
        reopened_by: str = "system",
    ) -> ReopenRecord:
        """Manually reopen a remediation item."""
        if reopen_id in self._reopens:
            raise RuntimeCoreInvariantError(f"Duplicate reopen_id: {reopen_id}")
        rem = self.get_remediation(remediation_id)
        if rem.status == RemediationStatus.CLOSED:
            raise RuntimeCoreInvariantError("Cannot reopen a closed remediation")
        now = _now_iso()
        reopen = ReopenRecord(
            reopen_id=reopen_id,
            remediation_id=remediation_id,
            reason=reason,
            reopened_by=reopened_by,
            reopened_at=now,
        )
        self._reopens[reopen_id] = reopen
        self._update_remediation_status(remediation_id, RemediationStatus.REOPENED)
        _emit(self._events, "remediation_reopened", {
            "reopen_id": reopen_id,
            "remediation_id": remediation_id,
        }, remediation_id)
        return reopen

    def reopens_for_remediation(self, remediation_id: str) -> tuple[ReopenRecord, ...]:
        """Return all reopen records for a remediation."""
        return tuple(r for r in self._reopens.values() if r.remediation_id == remediation_id)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def make_decision(
        self,
        decision_id: str,
        remediation_id: str,
        *,
        disposition: RemediationDisposition = RemediationDisposition.INEFFECTIVE,
        decided_by: str = "system",
        reason: str = "",
    ) -> RemediationDecision:
        """Make a formal decision on a remediation."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"Duplicate decision_id: {decision_id}")
        if remediation_id not in self._remediations:
            raise RuntimeCoreInvariantError(f"Unknown remediation_id: {remediation_id}")
        now = _now_iso()
        decision = RemediationDecision(
            decision_id=decision_id,
            remediation_id=remediation_id,
            disposition=disposition,
            decided_by=decided_by,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "remediation_decision_made", {
            "decision_id": decision_id,
            "remediation_id": remediation_id,
            "disposition": disposition.value,
        }, remediation_id)
        return decision

    # ------------------------------------------------------------------
    # Closure
    # ------------------------------------------------------------------

    def close_remediation(
        self,
        remediation_id: str,
        *,
        disposition: RemediationDisposition = RemediationDisposition.RESOLVED,
        decided_by: str = "system",
        reason: str = "",
    ) -> RemediationClosureReport:
        """Close a remediation. Requires at least one PASSED verification."""
        rem = self.get_remediation(remediation_id)
        if rem.status == RemediationStatus.CLOSED:
            raise RuntimeCoreInvariantError("Remediation is already closed")

        # Verify: must have at least one PASSED verification
        verifications = self.verifications_for_remediation(remediation_id)
        has_passed = any(v.status == RemediationVerificationStatus.PASSED for v in verifications)
        if not has_passed and disposition == RemediationDisposition.RESOLVED:
            raise RuntimeCoreInvariantError(
                "Cannot close as RESOLVED without at least one passed verification"
            )

        now = _now_iso()

        # Auto-create closing decision
        dec_id = stable_identifier("rdec", {"rem": remediation_id, "ts": now})
        self.make_decision(
            dec_id, remediation_id,
            disposition=disposition,
            decided_by=decided_by,
            reason=reason,
        )

        # Update status
        self._update_remediation_status(remediation_id, RemediationStatus.CLOSED)

        # Count items
        rem_corrective = len([a for a in self._corrective.values() if a.remediation_id == remediation_id])
        rem_preventive = len([a for a in self._preventive.values() if a.remediation_id == remediation_id])
        rem_verifications = len(verifications)
        rem_reopens = len([r for r in self._reopens.values() if r.remediation_id == remediation_id])
        rem_violations = len([v for v in self._violations.values() if v.remediation_id == remediation_id])

        report = RemediationClosureReport(
            report_id=stable_identifier("rrpt", {"rem": remediation_id, "ts": now}),
            remediation_id=remediation_id,
            tenant_id=rem.tenant_id,
            disposition=disposition,
            total_corrective=rem_corrective,
            total_preventive=rem_preventive,
            total_verifications=rem_verifications,
            total_reopens=rem_reopens,
            total_violations=rem_violations,
            closed_at=now,
        )

        _emit(self._events, "remediation_closed", {
            "remediation_id": remediation_id,
            "disposition": disposition.value,
        }, remediation_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_violations(self) -> tuple[RemediationViolation, ...]:
        """Detect remediation governance violations."""
        now = _now_iso()
        new_violations: list[RemediationViolation] = []

        for rem in self._remediations.values():
            # Overdue: has deadline, still open, deadline passed
            if rem.deadline and rem.status not in _CLOSED_STATUSES:
                try:
                    deadline_dt = datetime.fromisoformat(
                        rem.deadline.replace("Z", "+00:00")
                    )
                    now_dt = datetime.now(timezone.utc)
                    if now_dt > deadline_dt:
                        vid = stable_identifier("viol-rem", {
                            "rem": rem.remediation_id, "op": "overdue",
                        })
                        if vid not in self._violations:
                            v = RemediationViolation(
                                violation_id=vid,
                                remediation_id=rem.remediation_id,
                                tenant_id=rem.tenant_id,
                                operation="overdue",
                                reason=f"Remediation overdue: deadline {rem.deadline}",
                                detected_at=now,
                            )
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

            # Closed without verification
            if rem.status == RemediationStatus.CLOSED:
                verifications = self.verifications_for_remediation(rem.remediation_id)
                has_passed = any(v.status == RemediationVerificationStatus.PASSED for v in verifications)
                if not has_passed:
                    vid = stable_identifier("viol-rem", {
                        "rem": rem.remediation_id, "op": "closed_no_verification",
                    })
                    if vid not in self._violations:
                        v = RemediationViolation(
                            violation_id=vid,
                            remediation_id=rem.remediation_id,
                            tenant_id=rem.tenant_id,
                            operation="closed_without_verification",
                            reason="Remediation closed without passed verification",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "remediation_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_remediation(self, remediation_id: str) -> tuple[RemediationViolation, ...]:
        """Return all violations for a remediation."""
        return tuple(v for v in self._violations.values() if v.remediation_id == remediation_id)

    def violations_for_tenant(self, tenant_id: str) -> tuple[RemediationViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def remediation_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> RemediationSnapshot:
        """Capture a point-in-time remediation state snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        snapshot = RemediationSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_remediations=self.remediation_count,
            open_remediations=self.open_remediation_count,
            total_corrective=self.corrective_count,
            total_preventive=self.preventive_count,
            total_verifications=self.verification_count,
            total_reopens=self.reopen_count,
            total_decisions=self.decision_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "remediation_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"remediations={self.remediation_count}",
            f"open={self.open_remediation_count}",
            f"corrective={self.corrective_count}",
            f"preventive={self.preventive_count}",
            f"verifications={self.verification_count}",
            f"reopens={self.reopen_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
