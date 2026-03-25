"""Purpose: regulatory reporting / external audit submission contracts.
Governance scope: typed descriptors for reporting requirements, filing windows,
    submission records, evidence packages, reporting reviews, auditor requests
    and responses, snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every submission has explicit completeness status.
  - Filing windows enforce deadlines.
  - Evidence packages are immutable once assembled.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionStatus(Enum):
    """Status of a regulatory submission."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class FilingKind(Enum):
    """Kind of regulatory filing."""
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    AD_HOC = "ad_hoc"
    INCIDENT = "incident"
    AUDIT_RESPONSE = "audit_response"
    CERTIFICATION = "certification"


class ReportAudience(Enum):
    """Intended audience for a report."""
    REGULATOR = "regulator"
    EXTERNAL_AUDITOR = "external_auditor"
    INTERNAL_AUDIT = "internal_audit"
    BOARD = "board"
    MANAGEMENT = "management"


class EvidenceCompleteness(Enum):
    """Completeness status of an evidence package."""
    INCOMPLETE = "incomplete"
    PARTIAL = "partial"
    COMPLETE = "complete"
    VERIFIED = "verified"


class ReviewRequirement(Enum):
    """Review requirement level."""
    NONE = "none"
    PEER_REVIEW = "peer_review"
    MANAGEMENT_REVIEW = "management_review"
    LEGAL_REVIEW = "legal_review"
    EXTERNAL_REVIEW = "external_review"


class ReportingDisposition(Enum):
    """Final disposition of a reporting cycle."""
    FILED = "filed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OVERDUE = "overdue"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReportingRequirement(ContractRecord):
    """A regulatory reporting requirement."""

    requirement_id: str = ""
    tenant_id: str = ""
    filing_kind: FilingKind = FilingKind.AD_HOC
    audience: ReportAudience = ReportAudience.REGULATOR
    review_requirement: ReviewRequirement = ReviewRequirement.NONE
    title: str = ""
    description: str = ""
    recurring: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.filing_kind, FilingKind):
            raise ValueError("filing_kind must be a FilingKind")
        if not isinstance(self.audience, ReportAudience):
            raise ValueError("audience must be a ReportAudience")
        if not isinstance(self.review_requirement, ReviewRequirement):
            raise ValueError("review_requirement must be a ReviewRequirement")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FilingWindow(ContractRecord):
    """A scheduled filing window for a reporting requirement."""

    window_id: str = ""
    requirement_id: str = ""
    opens_at: str = ""
    closes_at: str = ""
    submitted_at: str = ""
    status: SubmissionStatus = SubmissionStatus.DRAFT
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        require_datetime_text(self.opens_at, "opens_at")
        require_datetime_text(self.closes_at, "closes_at")
        if not isinstance(self.status, SubmissionStatus):
            raise ValueError("status must be a SubmissionStatus")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SubmissionRecord(ContractRecord):
    """A record of a regulatory submission."""

    submission_id: str = ""
    window_id: str = ""
    tenant_id: str = ""
    package_id: str = ""
    status: SubmissionStatus = SubmissionStatus.DRAFT
    submitted_by: str = ""
    submitted_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "submission_id", require_non_empty_text(self.submission_id, "submission_id"))
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "package_id", require_non_empty_text(self.package_id, "package_id"))
        if not isinstance(self.status, SubmissionStatus):
            raise ValueError("status must be a SubmissionStatus")
        object.__setattr__(self, "submitted_by", require_non_empty_text(self.submitted_by, "submitted_by"))
        require_datetime_text(self.submitted_at, "submitted_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidencePackage(ContractRecord):
    """An assembled evidence package for regulatory submission."""

    package_id: str = ""
    tenant_id: str = ""
    requirement_id: str = ""
    completeness: EvidenceCompleteness = EvidenceCompleteness.INCOMPLETE
    evidence_ids: tuple[str, ...] = ()
    total_evidence_items: int = 0
    assembled_by: str = ""
    assembled_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", require_non_empty_text(self.package_id, "package_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        if not isinstance(self.completeness, EvidenceCompleteness):
            raise ValueError("completeness must be an EvidenceCompleteness")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "total_evidence_items", require_non_negative_int(self.total_evidence_items, "total_evidence_items"))
        object.__setattr__(self, "assembled_by", require_non_empty_text(self.assembled_by, "assembled_by"))
        require_datetime_text(self.assembled_at, "assembled_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReportingReview(ContractRecord):
    """A review of a regulatory submission."""

    review_id: str = ""
    submission_id: str = ""
    reviewer: str = ""
    review_requirement: ReviewRequirement = ReviewRequirement.NONE
    approved: bool = False
    comments: str = ""
    reviewed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", require_non_empty_text(self.review_id, "review_id"))
        object.__setattr__(self, "submission_id", require_non_empty_text(self.submission_id, "submission_id"))
        object.__setattr__(self, "reviewer", require_non_empty_text(self.reviewer, "reviewer"))
        if not isinstance(self.review_requirement, ReviewRequirement):
            raise ValueError("review_requirement must be a ReviewRequirement")
        require_datetime_text(self.reviewed_at, "reviewed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AuditorRequest(ContractRecord):
    """A request from an auditor or regulator."""

    request_id: str = ""
    tenant_id: str = ""
    submission_id: str = ""
    requested_by: str = ""
    description: str = ""
    requested_at: str = ""
    due_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "submission_id", require_non_empty_text(self.submission_id, "submission_id"))
        object.__setattr__(self, "requested_by", require_non_empty_text(self.requested_by, "requested_by"))
        require_datetime_text(self.requested_at, "requested_at")
        require_datetime_text(self.due_at, "due_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AuditorResponse(ContractRecord):
    """A response to an auditor request."""

    response_id: str = ""
    request_id: str = ""
    responder: str = ""
    content: str = ""
    evidence_ids: tuple[str, ...] = ()
    responded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_id", require_non_empty_text(self.response_id, "response_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "responder", require_non_empty_text(self.responder, "responder"))
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        require_datetime_text(self.responded_at, "responded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RegulatorySnapshot(ContractRecord):
    """Point-in-time regulatory reporting state snapshot."""

    snapshot_id: str = ""
    total_requirements: int = 0
    total_windows: int = 0
    total_packages: int = 0
    total_submissions: int = 0
    total_reviews: int = 0
    total_auditor_requests: int = 0
    total_auditor_responses: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_requirements", require_non_negative_int(self.total_requirements, "total_requirements"))
        object.__setattr__(self, "total_windows", require_non_negative_int(self.total_windows, "total_windows"))
        object.__setattr__(self, "total_packages", require_non_negative_int(self.total_packages, "total_packages"))
        object.__setattr__(self, "total_submissions", require_non_negative_int(self.total_submissions, "total_submissions"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_auditor_requests", require_non_negative_int(self.total_auditor_requests, "total_auditor_requests"))
        object.__setattr__(self, "total_auditor_responses", require_non_negative_int(self.total_auditor_responses, "total_auditor_responses"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReportingViolation(ContractRecord):
    """A detected regulatory reporting violation."""

    violation_id: str = ""
    tenant_id: str = ""
    requirement_id: str = ""
    window_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReportingClosureReport(ContractRecord):
    """Summary report for a regulatory reporting cycle closure."""

    report_id: str = ""
    requirement_id: str = ""
    tenant_id: str = ""
    disposition: ReportingDisposition = ReportingDisposition.OVERDUE
    total_submissions: int = 0
    total_reviews: int = 0
    total_auditor_requests: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, ReportingDisposition):
            raise ValueError("disposition must be a ReportingDisposition")
        object.__setattr__(self, "total_submissions", require_non_negative_int(self.total_submissions, "total_submissions"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_auditor_requests", require_non_negative_int(self.total_auditor_requests, "total_auditor_requests"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
