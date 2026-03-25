"""Purpose: human workflow / approvals / collaborative review runtime contracts.
Governance scope: typed descriptors for human tasks, review packets, approval
    boards, board members, votes, collaborative decisions, handoff packets,
    workflow snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every human task references an assignee.
  - Board decisions require quorum or unanimity as configured.
  - Completed workflows cannot be re-opened.
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
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HumanTaskStatus(Enum):
    """Status of a human task."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class ReviewMode(Enum):
    """Mode for how reviews are conducted."""
    SINGLE = "single"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class ApprovalMode(Enum):
    """Mode for how approvals are decided."""
    SINGLE = "single"
    QUORUM = "quorum"
    UNANIMOUS = "unanimous"
    OVERRIDE = "override"


class BoardDecisionStatus(Enum):
    """Status of a board decision."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    OVERRIDDEN = "overridden"


class EscalationDisposition(Enum):
    """Disposition of an escalation."""
    PENDING = "pending"
    RESOLVED = "resolved"
    REASSIGNED = "reassigned"
    EXPIRED = "expired"


class CollaborationScope(Enum):
    """Scope of collaborative work."""
    CHANGE = "change"
    CASE = "case"
    PROCUREMENT = "procurement"
    SERVICE = "service"
    REGULATORY = "regulatory"
    EXECUTIVE = "executive"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanTaskRecord(ContractRecord):
    """A task assigned to a human participant."""

    task_id: str = ""
    tenant_id: str = ""
    assignee_ref: str = ""
    status: HumanTaskStatus = HumanTaskStatus.PENDING
    scope: CollaborationScope = CollaborationScope.CHANGE
    scope_ref_id: str = ""
    title: str = ""
    description: str = ""
    due_at: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_non_empty_text(self.task_id, "task_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "assignee_ref", require_non_empty_text(self.assignee_ref, "assignee_ref"))
        if not isinstance(self.status, HumanTaskStatus):
            raise ValueError("status must be a HumanTaskStatus")
        if not isinstance(self.scope, CollaborationScope):
            raise ValueError("scope must be a CollaborationScope")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReviewPacket(ContractRecord):
    """A packet of evidence or work submitted for human review."""

    packet_id: str = ""
    tenant_id: str = ""
    scope: CollaborationScope = CollaborationScope.CASE
    scope_ref_id: str = ""
    review_mode: ReviewMode = ReviewMode.SINGLE
    title: str = ""
    reviewer_count: int = 0
    reviews_completed: int = 0
    reviews_approved: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "packet_id", require_non_empty_text(self.packet_id, "packet_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, CollaborationScope):
            raise ValueError("scope must be a CollaborationScope")
        if not isinstance(self.review_mode, ReviewMode):
            raise ValueError("review_mode must be a ReviewMode")
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "reviewer_count", require_non_negative_int(self.reviewer_count, "reviewer_count"))
        object.__setattr__(self, "reviews_completed", require_non_negative_int(self.reviews_completed, "reviews_completed"))
        object.__setattr__(self, "reviews_approved", require_non_negative_int(self.reviews_approved, "reviews_approved"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ApprovalBoard(ContractRecord):
    """An approval board that decides on requests."""

    board_id: str = ""
    tenant_id: str = ""
    name: str = ""
    approval_mode: ApprovalMode = ApprovalMode.SINGLE
    quorum_required: int = 1
    scope: CollaborationScope = CollaborationScope.CHANGE
    scope_ref_id: str = ""
    member_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "board_id", require_non_empty_text(self.board_id, "board_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.approval_mode, ApprovalMode):
            raise ValueError("approval_mode must be an ApprovalMode")
        object.__setattr__(self, "quorum_required", require_positive_int(self.quorum_required, "quorum_required"))
        if not isinstance(self.scope, CollaborationScope):
            raise ValueError("scope must be a CollaborationScope")
        object.__setattr__(self, "member_count", require_non_negative_int(self.member_count, "member_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BoardMember(ContractRecord):
    """A member of an approval board."""

    member_id: str = ""
    board_id: str = ""
    identity_ref: str = ""
    role: str = ""
    added_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", require_non_empty_text(self.member_id, "member_id"))
        object.__setattr__(self, "board_id", require_non_empty_text(self.board_id, "board_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        object.__setattr__(self, "role", require_non_empty_text(self.role, "role"))
        require_datetime_text(self.added_at, "added_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BoardVote(ContractRecord):
    """A vote cast by a board member."""

    vote_id: str = ""
    board_id: str = ""
    member_id: str = ""
    scope_ref_id: str = ""
    approved: bool = False
    reason: str = ""
    voted_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vote_id", require_non_empty_text(self.vote_id, "vote_id"))
        object.__setattr__(self, "board_id", require_non_empty_text(self.board_id, "board_id"))
        object.__setattr__(self, "member_id", require_non_empty_text(self.member_id, "member_id"))
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a bool")
        require_datetime_text(self.voted_at, "voted_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CollaborativeDecision(ContractRecord):
    """A decision made through collaborative review or board vote."""

    decision_id: str = ""
    board_id: str = ""
    scope_ref_id: str = ""
    status: BoardDecisionStatus = BoardDecisionStatus.PENDING
    total_votes: int = 0
    approvals: int = 0
    rejections: int = 0
    decided_by: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "board_id", require_non_empty_text(self.board_id, "board_id"))
        if not isinstance(self.status, BoardDecisionStatus):
            raise ValueError("status must be a BoardDecisionStatus")
        object.__setattr__(self, "total_votes", require_non_negative_int(self.total_votes, "total_votes"))
        object.__setattr__(self, "approvals", require_non_negative_int(self.approvals, "approvals"))
        object.__setattr__(self, "rejections", require_non_negative_int(self.rejections, "rejections"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class HandoffPacket(ContractRecord):
    """A handoff between human and runtime work."""

    handoff_id: str = ""
    tenant_id: str = ""
    scope: CollaborationScope = CollaborationScope.SERVICE
    scope_ref_id: str = ""
    from_ref: str = ""
    to_ref: str = ""
    direction: str = ""
    reason: str = ""
    handed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "handoff_id", require_non_empty_text(self.handoff_id, "handoff_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, CollaborationScope):
            raise ValueError("scope must be a CollaborationScope")
        object.__setattr__(self, "from_ref", require_non_empty_text(self.from_ref, "from_ref"))
        object.__setattr__(self, "to_ref", require_non_empty_text(self.to_ref, "to_ref"))
        object.__setattr__(self, "direction", require_non_empty_text(self.direction, "direction"))
        require_datetime_text(self.handed_at, "handed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class HumanWorkflowSnapshot(ContractRecord):
    """Point-in-time human workflow state snapshot."""

    snapshot_id: str = ""
    total_tasks: int = 0
    total_review_packets: int = 0
    total_boards: int = 0
    total_members: int = 0
    total_votes: int = 0
    total_decisions: int = 0
    total_handoffs: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_review_packets", require_non_negative_int(self.total_review_packets, "total_review_packets"))
        object.__setattr__(self, "total_boards", require_non_negative_int(self.total_boards, "total_boards"))
        object.__setattr__(self, "total_members", require_non_negative_int(self.total_members, "total_members"))
        object.__setattr__(self, "total_votes", require_non_negative_int(self.total_votes, "total_votes"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_handoffs", require_non_negative_int(self.total_handoffs, "total_handoffs"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class HumanWorkflowViolation(ContractRecord):
    """A violation detected in human workflow processing."""

    violation_id: str = ""
    tenant_id: str = ""
    scope_ref_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class HumanWorkflowClosureReport(ContractRecord):
    """Summary report for human workflow lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_tasks: int = 0
    total_review_packets: int = 0
    total_boards: int = 0
    total_decisions_approved: int = 0
    total_decisions_rejected: int = 0
    total_handoffs: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_tasks", require_non_negative_int(self.total_tasks, "total_tasks"))
        object.__setattr__(self, "total_review_packets", require_non_negative_int(self.total_review_packets, "total_review_packets"))
        object.__setattr__(self, "total_boards", require_non_negative_int(self.total_boards, "total_boards"))
        object.__setattr__(self, "total_decisions_approved", require_non_negative_int(self.total_decisions_approved, "total_decisions_approved"))
        object.__setattr__(self, "total_decisions_rejected", require_non_negative_int(self.total_decisions_rejected, "total_decisions_rejected"))
        object.__setattr__(self, "total_handoffs", require_non_negative_int(self.total_handoffs, "total_handoffs"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
