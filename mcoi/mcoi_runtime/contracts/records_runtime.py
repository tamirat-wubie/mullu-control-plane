"""Purpose: records / retention / legal hold runtime contracts.
Governance scope: typed descriptors for official records, retention schedules,
    legal holds, disposal decisions, preservation decisions, record links,
    violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record has explicit kind, tenant scope, and authority.
  - Legal holds override normal disposal.
  - Disposal is fail-closed — default is DENY.
  - Evidence records are immutable once preserved.
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


class RecordKind(Enum):
    """Kind of official record."""
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    EVIDENCE = "evidence"
    COMMUNICATION = "communication"
    FINANCIAL = "financial"
    LEGAL = "legal"


class RetentionStatus(Enum):
    """Status of a record's retention."""
    ACTIVE = "active"
    EXPIRED = "expired"
    DISPOSED = "disposed"
    HELD = "held"
    PENDING_REVIEW = "pending_review"


class HoldStatus(Enum):
    """Status of a legal hold."""
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"


class DisposalDisposition(Enum):
    """What to do when disposing a record."""
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    TRANSFER = "transfer"
    DENY = "deny"


class RecordAuthority(Enum):
    """Authority level for record operations."""
    SYSTEM = "system"
    OPERATOR = "operator"
    LEGAL = "legal"
    COMPLIANCE = "compliance"
    EXECUTIVE = "executive"
    AUTOMATED = "automated"


class EvidenceGrade(Enum):
    """Grade of evidence integrity."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DERIVED = "derived"
    COPY = "copy"
    RECONSTRUCTED = "reconstructed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordDescriptor(ContractRecord):
    """An official record in the platform."""

    record_id: str = ""
    tenant_id: str = ""
    kind: RecordKind = RecordKind.OPERATIONAL
    title: str = ""
    source_type: str = ""
    source_id: str = ""
    authority: RecordAuthority = RecordAuthority.SYSTEM
    evidence_grade: EvidenceGrade = EvidenceGrade.PRIMARY
    classification: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, RecordKind):
            raise ValueError("kind must be a RecordKind")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.authority, RecordAuthority):
            raise ValueError("authority must be a RecordAuthority")
        if not isinstance(self.evidence_grade, EvidenceGrade):
            raise ValueError("evidence_grade must be an EvidenceGrade")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RetentionSchedule(ContractRecord):
    """A retention schedule bound to a record."""

    schedule_id: str = ""
    record_id: str = ""
    tenant_id: str = ""
    retention_days: int = 0
    status: RetentionStatus = RetentionStatus.ACTIVE
    disposal_disposition: DisposalDisposition = DisposalDisposition.DELETE
    scope_ref_id: str = ""
    created_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "schedule_id", require_non_empty_text(self.schedule_id, "schedule_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "retention_days", require_non_negative_int(self.retention_days, "retention_days"))
        if not isinstance(self.status, RetentionStatus):
            raise ValueError("status must be a RetentionStatus")
        if not isinstance(self.disposal_disposition, DisposalDisposition):
            raise ValueError("disposal_disposition must be a DisposalDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LegalHoldRecord(ContractRecord):
    """A legal hold on a record."""

    hold_id: str = ""
    record_id: str = ""
    tenant_id: str = ""
    reason: str = ""
    authority: RecordAuthority = RecordAuthority.LEGAL
    status: HoldStatus = HoldStatus.ACTIVE
    placed_at: str = ""
    released_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hold_id", require_non_empty_text(self.hold_id, "hold_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.authority, RecordAuthority):
            raise ValueError("authority must be a RecordAuthority")
        if not isinstance(self.status, HoldStatus):
            raise ValueError("status must be a HoldStatus")
        require_datetime_text(self.placed_at, "placed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DispositionReview(ContractRecord):
    """A review of a record's disposition."""

    review_id: str = ""
    record_id: str = ""
    reviewer_id: str = ""
    decision: DisposalDisposition = DisposalDisposition.DENY
    reason: str = ""
    reviewed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", require_non_empty_text(self.review_id, "review_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "reviewer_id", require_non_empty_text(self.reviewer_id, "reviewer_id"))
        if not isinstance(self.decision, DisposalDisposition):
            raise ValueError("decision must be a DisposalDisposition")
        require_datetime_text(self.reviewed_at, "reviewed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecordLink(ContractRecord):
    """An immutable link between a record and its source evidence."""

    link_id: str = ""
    record_id: str = ""
    target_type: str = ""
    target_id: str = ""
    relationship: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "link_id", require_non_empty_text(self.link_id, "link_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "relationship", require_non_empty_text(self.relationship, "relationship"))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RecordSnapshot(ContractRecord):
    """Point-in-time records state snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_records: int = 0
    total_schedules: int = 0
    total_holds: int = 0
    active_holds: int = 0
    total_links: int = 0
    total_disposals: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_schedules", require_non_negative_int(self.total_schedules, "total_schedules"))
        object.__setattr__(self, "total_holds", require_non_negative_int(self.total_holds, "total_holds"))
        object.__setattr__(self, "active_holds", require_non_negative_int(self.active_holds, "active_holds"))
        object.__setattr__(self, "total_links", require_non_negative_int(self.total_links, "total_links"))
        object.__setattr__(self, "total_disposals", require_non_negative_int(self.total_disposals, "total_disposals"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecordViolation(ContractRecord):
    """A detected records governance violation."""

    violation_id: str = ""
    record_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PreservationDecision(ContractRecord):
    """A decision about whether to preserve a record."""

    decision_id: str = ""
    record_id: str = ""
    preserve: bool = True
    reason: str = ""
    authority: RecordAuthority = RecordAuthority.SYSTEM
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        if not isinstance(self.preserve, bool):
            raise ValueError("preserve must be a boolean")
        if not isinstance(self.authority, RecordAuthority):
            raise ValueError("authority must be a RecordAuthority")
        require_datetime_text(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class DisposalDecision(ContractRecord):
    """A decision about disposing a record."""

    decision_id: str = ""
    record_id: str = ""
    tenant_id: str = ""
    disposition: DisposalDisposition = DisposalDisposition.DENY
    reason: str = ""
    authority: RecordAuthority = RecordAuthority.SYSTEM
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, DisposalDisposition):
            raise ValueError("disposition must be a DisposalDisposition")
        if not isinstance(self.authority, RecordAuthority):
            raise ValueError("authority must be a RecordAuthority")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecordsClosureReport(ContractRecord):
    """Summary report for records governance closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_records: int = 0
    total_preserved: int = 0
    total_disposed: int = 0
    total_held: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_preserved", require_non_negative_int(self.total_preserved, "total_preserved"))
        object.__setattr__(self, "total_disposed", require_non_negative_int(self.total_disposed, "total_disposed"))
        object.__setattr__(self, "total_held", require_non_negative_int(self.total_held, "total_held"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
