"""Purpose: case / investigation / evidence review runtime contracts.
Governance scope: typed descriptors for cases, assignments, evidence items,
    evidence collections, reviews, findings, decisions, snapshots, violations,
    and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every case has explicit kind, severity, and tenant scope.
  - Evidence items are immutable once admitted.
  - Review dispositions are fail-closed — default is REQUIRES_REVIEW.
  - Case closure requires explicit decision.
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


class CaseStatus(Enum):
    """Status of a case or investigation."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    PENDING_DECISION = "pending_decision"
    CLOSED = "closed"
    ESCALATED = "escalated"


class CaseSeverity(Enum):
    """Severity of a case."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseKind(Enum):
    """Kind of case or investigation."""
    INCIDENT = "incident"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    SECURITY = "security"
    OPERATIONAL = "operational"
    LEGAL = "legal"
    FAULT_ANALYSIS = "fault_analysis"


class EvidenceStatus(Enum):
    """Status of an evidence item."""
    PENDING = "pending"
    ADMITTED = "admitted"
    REVIEWED = "reviewed"
    CHALLENGED = "challenged"
    EXCLUDED = "excluded"


class ReviewDisposition(Enum):
    """Outcome of an evidence review."""
    REQUIRES_REVIEW = "requires_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    ESCALATED = "escalated"


class FindingSeverity(Enum):
    """Severity of a case finding."""
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseClosureDisposition(Enum):
    """Disposition when closing a case."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    REMEDIATED = "remediated"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CaseRecord(ContractRecord):
    """A formal case or investigation."""

    case_id: str = ""
    tenant_id: str = ""
    kind: CaseKind = CaseKind.INCIDENT
    severity: CaseSeverity = CaseSeverity.MEDIUM
    status: CaseStatus = CaseStatus.OPEN
    title: str = ""
    description: str = ""
    opened_by: str = ""
    opened_at: str = ""
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, CaseKind):
            raise ValueError("kind must be a CaseKind")
        if not isinstance(self.severity, CaseSeverity):
            raise ValueError("severity must be a CaseSeverity")
        if not isinstance(self.status, CaseStatus):
            raise ValueError("status must be a CaseStatus")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "opened_by", require_non_empty_text(self.opened_by, "opened_by"))
        require_datetime_text(self.opened_at, "opened_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseAssignment(ContractRecord):
    """Assignment of an investigator or reviewer to a case."""

    assignment_id: str = ""
    case_id: str = ""
    assignee_id: str = ""
    role: str = ""
    assigned_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "assignee_id", require_non_empty_text(self.assignee_id, "assignee_id"))
        object.__setattr__(self, "role", require_non_empty_text(self.role, "role"))
        require_datetime_text(self.assigned_at, "assigned_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceItem(ContractRecord):
    """A piece of evidence attached to a case."""

    evidence_id: str = ""
    case_id: str = ""
    source_type: str = ""
    source_id: str = ""
    status: EvidenceStatus = EvidenceStatus.PENDING
    title: str = ""
    description: str = ""
    submitted_by: str = ""
    submitted_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "source_type", require_non_empty_text(self.source_type, "source_type"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("status must be an EvidenceStatus")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "submitted_by", require_non_empty_text(self.submitted_by, "submitted_by"))
        require_datetime_text(self.submitted_at, "submitted_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EvidenceCollection(ContractRecord):
    """A grouped collection of evidence for a case."""

    collection_id: str = ""
    case_id: str = ""
    title: str = ""
    evidence_ids: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "collection_id", require_non_empty_text(self.collection_id, "collection_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.evidence_ids, tuple):
            object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReviewRecord(ContractRecord):
    """A review of evidence within a case."""

    review_id: str = ""
    case_id: str = ""
    evidence_id: str = ""
    reviewer_id: str = ""
    disposition: ReviewDisposition = ReviewDisposition.REQUIRES_REVIEW
    notes: str = ""
    reviewed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", require_non_empty_text(self.review_id, "review_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "reviewer_id", require_non_empty_text(self.reviewer_id, "reviewer_id"))
        if not isinstance(self.disposition, ReviewDisposition):
            raise ValueError("disposition must be a ReviewDisposition")
        require_datetime_text(self.reviewed_at, "reviewed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FindingRecord(ContractRecord):
    """A finding discovered during case investigation."""

    finding_id: str = ""
    case_id: str = ""
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    title: str = ""
    description: str = ""
    evidence_ids: tuple[str, ...] = ()
    remediation: str = ""
    found_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "finding_id", require_non_empty_text(self.finding_id, "finding_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        if not isinstance(self.severity, FindingSeverity):
            raise ValueError("severity must be a FindingSeverity")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.evidence_ids, tuple):
            object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        require_datetime_text(self.found_at, "found_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseDecision(ContractRecord):
    """A formal decision on a case."""

    decision_id: str = ""
    case_id: str = ""
    disposition: CaseClosureDisposition = CaseClosureDisposition.UNRESOLVED
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        if not isinstance(self.disposition, CaseClosureDisposition):
            raise ValueError("disposition must be a CaseClosureDisposition")
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseSnapshot(ContractRecord):
    """Point-in-time case state snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_cases: int = 0
    open_cases: int = 0
    total_evidence: int = 0
    total_reviews: int = 0
    total_findings: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_cases", require_non_negative_int(self.total_cases, "total_cases"))
        object.__setattr__(self, "open_cases", require_non_negative_int(self.open_cases, "open_cases"))
        object.__setattr__(self, "total_evidence", require_non_negative_int(self.total_evidence, "total_evidence"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_findings", require_non_negative_int(self.total_findings, "total_findings"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseViolation(ContractRecord):
    """A detected case governance violation."""

    violation_id: str = ""
    case_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CaseClosureReport(ContractRecord):
    """Summary report for case closure."""

    report_id: str = ""
    case_id: str = ""
    tenant_id: str = ""
    disposition: CaseClosureDisposition = CaseClosureDisposition.UNRESOLVED
    total_evidence: int = 0
    total_reviews: int = 0
    total_findings: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, CaseClosureDisposition):
            raise ValueError("disposition must be a CaseClosureDisposition")
        object.__setattr__(self, "total_evidence", require_non_negative_int(self.total_evidence, "total_evidence"))
        object.__setattr__(self, "total_reviews", require_non_negative_int(self.total_reviews, "total_reviews"))
        object.__setattr__(self, "total_findings", require_non_negative_int(self.total_findings, "total_findings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
