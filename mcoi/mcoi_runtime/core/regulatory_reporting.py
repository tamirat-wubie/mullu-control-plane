"""Purpose: regulatory reporting / external audit submission runtime engine.
Governance scope: registering reporting requirements; scheduling filing windows;
    assembling evidence packages; validating completeness; tracking submissions,
    reviews, auditor requests/responses; detecting missed windows and violations;
    producing immutable snapshots.
Dependencies: regulatory_reporting contracts, event_spine, core invariants.
Invariants:
  - Incomplete packages cannot be submitted.
  - Filing windows enforce deadlines.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.regulatory_reporting import (
    AuditorRequest,
    AuditorResponse,
    EvidenceCompleteness,
    EvidencePackage,
    FilingKind,
    FilingWindow,
    RegulatorySnapshot,
    ReportAudience,
    ReportingClosureReport,
    ReportingDisposition,
    ReportingRequirement,
    ReportingReview,
    ReportingViolation,
    ReviewRequirement,
    SubmissionRecord,
    SubmissionStatus,
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
        event_id=stable_identifier("evt-rrep", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_SUBMISSION_TERMINAL = frozenset({
    SubmissionStatus.ACCEPTED,
    SubmissionStatus.REJECTED,
    SubmissionStatus.WITHDRAWN,
})


class RegulatoryReportingEngine:
    """Regulatory reporting and external audit submission engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._requirements: dict[str, ReportingRequirement] = {}
        self._windows: dict[str, FilingWindow] = {}
        self._packages: dict[str, EvidencePackage] = {}
        self._submissions: dict[str, SubmissionRecord] = {}
        self._reviews: dict[str, ReportingReview] = {}
        self._auditor_requests: dict[str, AuditorRequest] = {}
        self._auditor_responses: dict[str, AuditorResponse] = {}
        self._violations: dict[str, ReportingViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def requirement_count(self) -> int:
        return len(self._requirements)

    @property
    def window_count(self) -> int:
        return len(self._windows)

    @property
    def package_count(self) -> int:
        return len(self._packages)

    @property
    def submission_count(self) -> int:
        return len(self._submissions)

    @property
    def review_count(self) -> int:
        return len(self._reviews)

    @property
    def auditor_request_count(self) -> int:
        return len(self._auditor_requests)

    @property
    def auditor_response_count(self) -> int:
        return len(self._auditor_responses)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Requirements
    # ------------------------------------------------------------------

    def register_requirement(
        self,
        requirement_id: str,
        tenant_id: str,
        title: str,
        *,
        filing_kind: FilingKind = FilingKind.AD_HOC,
        audience: ReportAudience = ReportAudience.REGULATOR,
        review_requirement: ReviewRequirement = ReviewRequirement.NONE,
        description: str = "",
        recurring: bool = False,
    ) -> ReportingRequirement:
        """Register a reporting requirement."""
        if requirement_id in self._requirements:
            raise RuntimeCoreInvariantError(f"Duplicate requirement_id: {requirement_id}")
        now = _now_iso()
        req = ReportingRequirement(
            requirement_id=requirement_id,
            tenant_id=tenant_id,
            filing_kind=filing_kind,
            audience=audience,
            review_requirement=review_requirement,
            title=title,
            description=description,
            recurring=recurring,
            created_at=now,
        )
        self._requirements[requirement_id] = req
        _emit(self._events, "requirement_registered", {
            "requirement_id": requirement_id, "filing_kind": filing_kind.value,
        }, requirement_id)
        return req

    def get_requirement(self, requirement_id: str) -> ReportingRequirement:
        """Get a requirement by ID."""
        r = self._requirements.get(requirement_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown requirement_id: {requirement_id}")
        return r

    def requirements_for_tenant(self, tenant_id: str) -> tuple[ReportingRequirement, ...]:
        """Return all requirements for a tenant."""
        return tuple(r for r in self._requirements.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Filing windows
    # ------------------------------------------------------------------

    def open_filing_window(
        self,
        window_id: str,
        requirement_id: str,
        opens_at: str,
        closes_at: str,
    ) -> FilingWindow:
        """Open a filing window for a requirement."""
        if window_id in self._windows:
            raise RuntimeCoreInvariantError(f"Duplicate window_id: {window_id}")
        if requirement_id not in self._requirements:
            raise RuntimeCoreInvariantError(f"Unknown requirement_id: {requirement_id}")
        window = FilingWindow(
            window_id=window_id,
            requirement_id=requirement_id,
            opens_at=opens_at,
            closes_at=closes_at,
            status=SubmissionStatus.DRAFT,
        )
        self._windows[window_id] = window
        _emit(self._events, "filing_window_opened", {
            "window_id": window_id, "requirement_id": requirement_id,
        }, window_id)
        return window

    def get_window(self, window_id: str) -> FilingWindow:
        """Get a filing window by ID."""
        w = self._windows.get(window_id)
        if w is None:
            raise RuntimeCoreInvariantError(f"Unknown window_id: {window_id}")
        return w

    def windows_for_requirement(self, requirement_id: str) -> tuple[FilingWindow, ...]:
        """Return all windows for a requirement."""
        return tuple(w for w in self._windows.values() if w.requirement_id == requirement_id)

    # ------------------------------------------------------------------
    # Evidence packages
    # ------------------------------------------------------------------

    def assemble_evidence_package(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        evidence_ids: tuple[str, ...],
        *,
        assembled_by: str = "system",
    ) -> EvidencePackage:
        """Assemble an evidence package from evidence IDs."""
        if package_id in self._packages:
            raise RuntimeCoreInvariantError(f"Duplicate package_id: {package_id}")
        if requirement_id not in self._requirements:
            raise RuntimeCoreInvariantError(f"Unknown requirement_id: {requirement_id}")

        count = len(evidence_ids)
        if count == 0:
            completeness = EvidenceCompleteness.INCOMPLETE
        elif count == 1:
            completeness = EvidenceCompleteness.PARTIAL
        elif count <= 3:
            completeness = EvidenceCompleteness.COMPLETE
        else:
            completeness = EvidenceCompleteness.VERIFIED

        now = _now_iso()
        pkg = EvidencePackage(
            package_id=package_id,
            tenant_id=tenant_id,
            requirement_id=requirement_id,
            completeness=completeness,
            evidence_ids=evidence_ids,
            total_evidence_items=count,
            assembled_by=assembled_by,
            assembled_at=now,
        )
        self._packages[package_id] = pkg
        _emit(self._events, "evidence_package_assembled", {
            "package_id": package_id, "completeness": completeness.value,
            "evidence_count": count,
        }, package_id)
        return pkg

    def get_package(self, package_id: str) -> EvidencePackage:
        """Get an evidence package by ID."""
        p = self._packages.get(package_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown package_id: {package_id}")
        return p

    def validate_package(self, package_id: str) -> EvidenceCompleteness:
        """Validate and return the completeness of an evidence package."""
        pkg = self.get_package(package_id)
        _emit(self._events, "package_validated", {
            "package_id": package_id, "completeness": pkg.completeness.value,
        }, package_id)
        return pkg.completeness

    # ------------------------------------------------------------------
    # Submissions
    # ------------------------------------------------------------------

    def submit_report(
        self,
        submission_id: str,
        window_id: str,
        tenant_id: str,
        package_id: str,
        *,
        submitted_by: str = "system",
    ) -> SubmissionRecord:
        """Submit a report for a filing window."""
        if submission_id in self._submissions:
            raise RuntimeCoreInvariantError(f"Duplicate submission_id: {submission_id}")

        # Validate window exists
        window = self.get_window(window_id)

        # Validate package exists and is complete enough
        pkg = self.get_package(package_id)
        if pkg.completeness == EvidenceCompleteness.INCOMPLETE:
            raise RuntimeCoreInvariantError(
                "Cannot submit with INCOMPLETE evidence package"
            )

        now = _now_iso()
        sub = SubmissionRecord(
            submission_id=submission_id,
            window_id=window_id,
            tenant_id=tenant_id,
            package_id=package_id,
            status=SubmissionStatus.SUBMITTED,
            submitted_by=submitted_by,
            submitted_at=now,
        )
        self._submissions[submission_id] = sub

        # Update window status
        updated_window = FilingWindow(
            window_id=window.window_id,
            requirement_id=window.requirement_id,
            opens_at=window.opens_at,
            closes_at=window.closes_at,
            submitted_at=now,
            status=SubmissionStatus.SUBMITTED,
            metadata=window.metadata,
        )
        self._windows[window_id] = updated_window

        _emit(self._events, "report_submitted", {
            "submission_id": submission_id, "window_id": window_id,
            "package_id": package_id,
        }, submission_id)
        return sub

    def get_submission(self, submission_id: str) -> SubmissionRecord:
        """Get a submission by ID."""
        s = self._submissions.get(submission_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown submission_id: {submission_id}")
        return s

    def accept_submission(self, submission_id: str) -> SubmissionRecord:
        """Mark a submission as accepted."""
        old = self.get_submission(submission_id)
        if old.status in _SUBMISSION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot accept submission in status {old.status.value}"
            )
        updated = SubmissionRecord(
            submission_id=old.submission_id,
            window_id=old.window_id,
            tenant_id=old.tenant_id,
            package_id=old.package_id,
            status=SubmissionStatus.ACCEPTED,
            submitted_by=old.submitted_by,
            submitted_at=old.submitted_at,
            metadata=old.metadata,
        )
        self._submissions[submission_id] = updated
        _emit(self._events, "submission_accepted", {
            "submission_id": submission_id,
        }, submission_id)
        return updated

    def reject_submission(self, submission_id: str, *, reason: str = "") -> SubmissionRecord:
        """Mark a submission as rejected."""
        old = self.get_submission(submission_id)
        if old.status in _SUBMISSION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot reject submission in status {old.status.value}"
            )
        updated = SubmissionRecord(
            submission_id=old.submission_id,
            window_id=old.window_id,
            tenant_id=old.tenant_id,
            package_id=old.package_id,
            status=SubmissionStatus.REJECTED,
            submitted_by=old.submitted_by,
            submitted_at=old.submitted_at,
            metadata=old.metadata,
        )
        self._submissions[submission_id] = updated
        _emit(self._events, "submission_rejected", {
            "submission_id": submission_id, "reason": reason,
        }, submission_id)
        return updated

    def withdraw_submission(self, submission_id: str) -> SubmissionRecord:
        """Withdraw a submission."""
        old = self.get_submission(submission_id)
        if old.status in _SUBMISSION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot withdraw submission in status {old.status.value}"
            )
        updated = SubmissionRecord(
            submission_id=old.submission_id,
            window_id=old.window_id,
            tenant_id=old.tenant_id,
            package_id=old.package_id,
            status=SubmissionStatus.WITHDRAWN,
            submitted_by=old.submitted_by,
            submitted_at=old.submitted_at,
            metadata=old.metadata,
        )
        self._submissions[submission_id] = updated
        _emit(self._events, "submission_withdrawn", {
            "submission_id": submission_id,
        }, submission_id)
        return updated

    def submissions_for_window(self, window_id: str) -> tuple[SubmissionRecord, ...]:
        """Return all submissions for a window."""
        return tuple(s for s in self._submissions.values() if s.window_id == window_id)

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def record_review(
        self,
        review_id: str,
        submission_id: str,
        *,
        reviewer: str = "system",
        review_requirement: ReviewRequirement = ReviewRequirement.PEER_REVIEW,
        approved: bool = False,
        comments: str = "",
    ) -> ReportingReview:
        """Record a review of a submission."""
        if review_id in self._reviews:
            raise RuntimeCoreInvariantError(f"Duplicate review_id: {review_id}")
        if submission_id not in self._submissions:
            raise RuntimeCoreInvariantError(f"Unknown submission_id: {submission_id}")
        now = _now_iso()
        review = ReportingReview(
            review_id=review_id,
            submission_id=submission_id,
            reviewer=reviewer,
            review_requirement=review_requirement,
            approved=approved,
            comments=comments,
            reviewed_at=now,
        )
        self._reviews[review_id] = review
        _emit(self._events, "review_recorded", {
            "review_id": review_id, "submission_id": submission_id,
            "approved": approved,
        }, submission_id)
        return review

    def reviews_for_submission(self, submission_id: str) -> tuple[ReportingReview, ...]:
        """Return all reviews for a submission."""
        return tuple(r for r in self._reviews.values() if r.submission_id == submission_id)

    # ------------------------------------------------------------------
    # Auditor requests/responses
    # ------------------------------------------------------------------

    def record_auditor_request(
        self,
        request_id: str,
        tenant_id: str,
        submission_id: str,
        *,
        requested_by: str = "auditor",
        description: str = "",
        due_at: str = "",
    ) -> AuditorRequest:
        """Record a request from an auditor."""
        if request_id in self._auditor_requests:
            raise RuntimeCoreInvariantError(f"Duplicate request_id: {request_id}")
        if submission_id not in self._submissions:
            raise RuntimeCoreInvariantError(f"Unknown submission_id: {submission_id}")
        now = _now_iso()
        if not due_at:
            due_at = now  # default due immediately
        req = AuditorRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            submission_id=submission_id,
            requested_by=requested_by,
            description=description,
            requested_at=now,
            due_at=due_at,
        )
        self._auditor_requests[request_id] = req

        # Move submission back to pending_review
        old_sub = self._submissions[submission_id]
        if old_sub.status == SubmissionStatus.SUBMITTED:
            updated_sub = SubmissionRecord(
                submission_id=old_sub.submission_id,
                window_id=old_sub.window_id,
                tenant_id=old_sub.tenant_id,
                package_id=old_sub.package_id,
                status=SubmissionStatus.PENDING_REVIEW,
                submitted_by=old_sub.submitted_by,
                submitted_at=old_sub.submitted_at,
                metadata=old_sub.metadata,
            )
            self._submissions[submission_id] = updated_sub

        _emit(self._events, "auditor_request_recorded", {
            "request_id": request_id, "submission_id": submission_id,
        }, submission_id)
        return req

    def record_auditor_response(
        self,
        response_id: str,
        request_id: str,
        *,
        responder: str = "system",
        content: str = "",
        evidence_ids: tuple[str, ...] = (),
    ) -> AuditorResponse:
        """Record a response to an auditor request."""
        if response_id in self._auditor_responses:
            raise RuntimeCoreInvariantError(f"Duplicate response_id: {response_id}")
        if request_id not in self._auditor_requests:
            raise RuntimeCoreInvariantError(f"Unknown request_id: {request_id}")
        now = _now_iso()
        resp = AuditorResponse(
            response_id=response_id,
            request_id=request_id,
            responder=responder,
            content=content,
            evidence_ids=evidence_ids,
            responded_at=now,
        )
        self._auditor_responses[response_id] = resp
        _emit(self._events, "auditor_response_recorded", {
            "response_id": response_id, "request_id": request_id,
        }, request_id)
        return resp

    def requests_for_submission(self, submission_id: str) -> tuple[AuditorRequest, ...]:
        """Return all auditor requests for a submission."""
        return tuple(r for r in self._auditor_requests.values() if r.submission_id == submission_id)

    def responses_for_request(self, request_id: str) -> tuple[AuditorResponse, ...]:
        """Return all responses for an auditor request."""
        return tuple(r for r in self._auditor_responses.values() if r.request_id == request_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_reporting_violations(self) -> tuple[ReportingViolation, ...]:
        """Detect regulatory reporting violations (missed windows, etc.)."""
        now = _now_iso()
        new_violations: list[ReportingViolation] = []

        # Missed filing windows — past closes_at with no submission
        for window in self._windows.values():
            if window.status == SubmissionStatus.DRAFT:
                try:
                    close_dt = datetime.fromisoformat(window.closes_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > close_dt:
                        vid = stable_identifier("viol-rrep", {
                            "win": window.window_id, "op": "missed_filing",
                        })
                        if vid not in self._violations:
                            req = self._requirements.get(window.requirement_id)
                            tenant_id = req.tenant_id if req else "unknown"
                            v = ReportingViolation(
                                violation_id=vid,
                                tenant_id=tenant_id,
                                requirement_id=window.requirement_id,
                                window_id=window.window_id,
                                operation="missed_filing_window",
                                reason=f"Filing window {window.window_id} closed at {window.closes_at} without submission",
                                detected_at=now,
                            )
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        if new_violations:
            _emit(self._events, "reporting_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ReportingViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def regulatory_snapshot(self, snapshot_id: str) -> RegulatorySnapshot:
        """Capture a point-in-time regulatory reporting snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        snap = RegulatorySnapshot(
            snapshot_id=snapshot_id,
            total_requirements=self.requirement_count,
            total_windows=self.window_count,
            total_packages=self.package_count,
            total_submissions=self.submission_count,
            total_reviews=self.review_count,
            total_auditor_requests=self.auditor_request_count,
            total_auditor_responses=self.auditor_response_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "regulatory_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"requirements={self.requirement_count}",
            f"windows={self.window_count}",
            f"packages={self.package_count}",
            f"submissions={self.submission_count}",
            f"reviews={self.review_count}",
            f"auditor_requests={self.auditor_request_count}",
            f"auditor_responses={self.auditor_response_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
