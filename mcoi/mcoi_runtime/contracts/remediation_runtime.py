"""Purpose: remediation / corrective action runtime contracts.
Governance scope: typed descriptors for remediation records, corrective actions,
    preventive actions, assignments, verification, reopen, decisions, snapshots,
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every remediation has explicit type, priority, and tenant scope.
  - Remediation cannot close without verification.
  - Failed verification reopens remediation.
  - Overdue remediation escalates.
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


class RemediationStatus(Enum):
    """Status of a remediation item."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    CLOSED = "closed"
    REOPENED = "reopened"
    ESCALATED = "escalated"


class RemediationPriority(Enum):
    """Priority of a remediation item."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationType(Enum):
    """Type of remediation action."""
    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    COMPENSATING = "compensating"


class RemediationVerificationStatus(Enum):
    """Status of a verification check."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class PreventiveActionStatus(Enum):
    """Status of a preventive action."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    REJECTED = "rejected"


class RemediationDisposition(Enum):
    """Disposition when closing remediation."""
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"
    TRANSFERRED = "transferred"
    ESCALATED = "escalated"
    INEFFECTIVE = "ineffective"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemediationRecord(ContractRecord):
    """A remediation item tracking corrective or preventive work."""

    remediation_id: str = ""
    tenant_id: str = ""
    case_id: str = ""
    finding_id: str = ""
    remediation_type: RemediationType = RemediationType.CORRECTIVE
    priority: RemediationPriority = RemediationPriority.MEDIUM
    status: RemediationStatus = RemediationStatus.OPEN
    title: str = ""
    description: str = ""
    owner_id: str = ""
    deadline: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.remediation_type, RemediationType):
            raise ValueError("remediation_type must be a RemediationType")
        if not isinstance(self.priority, RemediationPriority):
            raise ValueError("priority must be a RemediationPriority")
        if not isinstance(self.status, RemediationStatus):
            raise ValueError("status must be a RemediationStatus")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "owner_id", require_non_empty_text(self.owner_id, "owner_id"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CorrectiveAction(ContractRecord):
    """A specific corrective action within a remediation."""

    action_id: str = ""
    remediation_id: str = ""
    title: str = ""
    description: str = ""
    owner_id: str = ""
    status: RemediationStatus = RemediationStatus.OPEN
    deadline: str = ""
    completed_at: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "owner_id", require_non_empty_text(self.owner_id, "owner_id"))
        if not isinstance(self.status, RemediationStatus):
            raise ValueError("status must be a RemediationStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PreventiveAction(ContractRecord):
    """A preventive action to avoid recurrence."""

    action_id: str = ""
    remediation_id: str = ""
    title: str = ""
    description: str = ""
    target_type: str = ""
    target_id: str = ""
    status: PreventiveActionStatus = PreventiveActionStatus.PROPOSED
    owner_id: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        if not isinstance(self.status, PreventiveActionStatus):
            raise ValueError("status must be a PreventiveActionStatus")
        object.__setattr__(self, "owner_id", require_non_empty_text(self.owner_id, "owner_id"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemediationAssignment(ContractRecord):
    """Assignment of an owner to a remediation item."""

    assignment_id: str = ""
    remediation_id: str = ""
    assignee_id: str = ""
    role: str = ""
    assigned_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "assignee_id", require_non_empty_text(self.assignee_id, "assignee_id"))
        object.__setattr__(self, "role", require_non_empty_text(self.role, "role"))
        require_datetime_text(self.assigned_at, "assigned_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VerificationRecord(ContractRecord):
    """A verification check for a remediation item."""

    verification_id: str = ""
    remediation_id: str = ""
    verifier_id: str = ""
    status: RemediationVerificationStatus = RemediationVerificationStatus.PENDING
    notes: str = ""
    verified_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", require_non_empty_text(self.verification_id, "verification_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "verifier_id", require_non_empty_text(self.verifier_id, "verifier_id"))
        if not isinstance(self.status, RemediationVerificationStatus):
            raise ValueError("status must be a RemediationVerificationStatus")
        require_datetime_text(self.verified_at, "verified_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReopenRecord(ContractRecord):
    """A record of reopening a remediation item."""

    reopen_id: str = ""
    remediation_id: str = ""
    reason: str = ""
    reopened_by: str = ""
    reopened_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reopen_id", require_non_empty_text(self.reopen_id, "reopen_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "reopened_by", require_non_empty_text(self.reopened_by, "reopened_by"))
        require_datetime_text(self.reopened_at, "reopened_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemediationDecision(ContractRecord):
    """A formal decision on a remediation item."""

    decision_id: str = ""
    remediation_id: str = ""
    disposition: RemediationDisposition = RemediationDisposition.INEFFECTIVE
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        if not isinstance(self.disposition, RemediationDisposition):
            raise ValueError("disposition must be a RemediationDisposition")
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemediationSnapshot(ContractRecord):
    """Point-in-time remediation state snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_remediations: int = 0
    open_remediations: int = 0
    total_corrective: int = 0
    total_preventive: int = 0
    total_verifications: int = 0
    total_reopens: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_remediations", require_non_negative_int(self.total_remediations, "total_remediations"))
        object.__setattr__(self, "open_remediations", require_non_negative_int(self.open_remediations, "open_remediations"))
        object.__setattr__(self, "total_corrective", require_non_negative_int(self.total_corrective, "total_corrective"))
        object.__setattr__(self, "total_preventive", require_non_negative_int(self.total_preventive, "total_preventive"))
        object.__setattr__(self, "total_verifications", require_non_negative_int(self.total_verifications, "total_verifications"))
        object.__setattr__(self, "total_reopens", require_non_negative_int(self.total_reopens, "total_reopens"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemediationViolation(ContractRecord):
    """A detected remediation governance violation."""

    violation_id: str = ""
    remediation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RemediationClosureReport(ContractRecord):
    """Summary report for remediation closure."""

    report_id: str = ""
    remediation_id: str = ""
    tenant_id: str = ""
    disposition: RemediationDisposition = RemediationDisposition.INEFFECTIVE
    total_corrective: int = 0
    total_preventive: int = 0
    total_verifications: int = 0
    total_reopens: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "remediation_id", require_non_empty_text(self.remediation_id, "remediation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, RemediationDisposition):
            raise ValueError("disposition must be a RemediationDisposition")
        object.__setattr__(self, "total_corrective", require_non_negative_int(self.total_corrective, "total_corrective"))
        object.__setattr__(self, "total_preventive", require_non_negative_int(self.total_preventive, "total_preventive"))
        object.__setattr__(self, "total_verifications", require_non_negative_int(self.total_verifications, "total_verifications"))
        object.__setattr__(self, "total_reopens", require_non_negative_int(self.total_reopens, "total_reopens"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
