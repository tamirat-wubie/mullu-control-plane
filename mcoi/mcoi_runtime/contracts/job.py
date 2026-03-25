"""Purpose: canonical job ownership runtime contract mapping.
Governance scope: job descriptor, queue, assignment, state, follow-up, deadline, execution, pause, and resume typing.
Dependencies: docs/28_job_ownership_runtime.md, shared contract base helpers.
Invariants:
  - Every job carries explicit identity, priority, and lifecycle state.
  - No assignment without a queue entry.
  - No job mutation after archive.
  - No silent deadline skip; every SLA evaluation produces a DeadlineRecord.
  - Follow-ups are scheduled explicitly and never silently dropped.
  - Pause and resume always produce typed audit records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)


# --- Classification enums ---


class JobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class JobPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


# Numeric rank for sorting (lower number = higher priority)
JOB_PRIORITY_RANK: dict[JobPriority, int] = {
    JobPriority.CRITICAL: 0,
    JobPriority.HIGH: 1,
    JobPriority.NORMAL: 2,
    JobPriority.LOW: 3,
    JobPriority.BACKGROUND: 4,
}


class PauseReason(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_RESPONSE = "awaiting_response"
    AWAITING_REVIEW = "awaiting_review"
    BLOCKED_DEPENDENCY = "blocked_dependency"
    OPERATOR_HOLD = "operator_hold"
    SYSTEM_ERROR = "system_error"


class SlaStatus(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    NOT_APPLICABLE = "not_applicable"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class JobDescriptor(ContractRecord):
    """Identity and metadata for a single job."""

    job_id: str
    name: str
    description: str
    priority: JobPriority
    created_at: str
    goal_id: str | None = None
    workflow_id: str | None = None
    deadline: str | None = None
    sla_target_minutes: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.priority, JobPriority):
            raise ValueError("priority must be a JobPriority value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if self.workflow_id is not None:
            object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        if self.deadline is not None:
            object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))
        if self.sla_target_minutes is not None:
            if not isinstance(self.sla_target_minutes, int) or self.sla_target_minutes < 1:
                raise ValueError("sla_target_minutes must be a positive integer")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class WorkQueueEntry(ContractRecord):
    """A job's position in a priority-ordered work queue."""

    entry_id: str
    job_id: str
    priority: JobPriority
    enqueued_at: str
    assigned_to_person_id: str | None = None
    assigned_to_team_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", require_non_empty_text(self.entry_id, "entry_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        if not isinstance(self.priority, JobPriority):
            raise ValueError("priority must be a JobPriority value")
        object.__setattr__(self, "enqueued_at", require_datetime_text(self.enqueued_at, "enqueued_at"))
        if self.assigned_to_person_id is not None:
            object.__setattr__(
                self, "assigned_to_person_id",
                require_non_empty_text(self.assigned_to_person_id, "assigned_to_person_id"),
            )
        if self.assigned_to_team_id is not None:
            object.__setattr__(
                self, "assigned_to_team_id",
                require_non_empty_text(self.assigned_to_team_id, "assigned_to_team_id"),
            )


@dataclass(frozen=True, slots=True)
class AssignmentRecord(ContractRecord):
    """Audit record for a job assignment or re-assignment."""

    assignment_id: str
    job_id: str
    assigned_to_id: str
    assigned_by_id: str
    assigned_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", require_non_empty_text(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "assigned_to_id", require_non_empty_text(self.assigned_to_id, "assigned_to_id"))
        object.__setattr__(self, "assigned_by_id", require_non_empty_text(self.assigned_by_id, "assigned_by_id"))
        object.__setattr__(self, "assigned_at", require_datetime_text(self.assigned_at, "assigned_at"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class JobState(ContractRecord):
    """Current progress tracker for a job (rebuilt as frozen instances)."""

    job_id: str
    status: JobStatus
    sla_status: SlaStatus
    current_assignment_id: str | None = None
    pause_reason: PauseReason | None = None
    thread_id: str | None = None
    goal_id: str | None = None
    workflow_id: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        if not isinstance(self.status, JobStatus):
            raise ValueError("status must be a JobStatus value")
        if not isinstance(self.sla_status, SlaStatus):
            raise ValueError("sla_status must be a SlaStatus value")
        if self.current_assignment_id is not None:
            object.__setattr__(
                self, "current_assignment_id",
                require_non_empty_text(self.current_assignment_id, "current_assignment_id"),
            )
        if self.pause_reason is not None:
            if not isinstance(self.pause_reason, PauseReason):
                raise ValueError("pause_reason must be a PauseReason value")
        if self.thread_id is not None:
            object.__setattr__(self, "thread_id", require_non_empty_text(self.thread_id, "thread_id"))
        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if self.workflow_id is not None:
            object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        if self.started_at is not None:
            object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        if self.updated_at is not None:
            object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))


@dataclass(frozen=True, slots=True)
class FollowUpRecord(ContractRecord):
    """Scheduled follow-up for a stalled job."""

    follow_up_id: str
    job_id: str
    reason: str
    scheduled_at: str
    resolved: bool = False
    executed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "follow_up_id", require_non_empty_text(self.follow_up_id, "follow_up_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "scheduled_at", require_datetime_text(self.scheduled_at, "scheduled_at"))
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a boolean")
        if self.executed_at is not None:
            object.__setattr__(self, "executed_at", require_datetime_text(self.executed_at, "executed_at"))


@dataclass(frozen=True, slots=True)
class DeadlineRecord(ContractRecord):
    """SLA and deadline evaluation snapshot."""

    job_id: str
    deadline: str
    sla_status: SlaStatus
    evaluated_at: str
    sla_target_minutes: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))
        if not isinstance(self.sla_status, SlaStatus):
            raise ValueError("sla_status must be a SlaStatus value")
        object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))
        if self.sla_target_minutes is not None:
            if not isinstance(self.sla_target_minutes, int) or self.sla_target_minutes < 1:
                raise ValueError("sla_target_minutes must be a positive integer")


@dataclass(frozen=True, slots=True)
class JobExecutionRecord(ContractRecord):
    """Outcome record for a completed or failed job execution."""

    job_id: str
    execution_id: str
    status: JobStatus
    started_at: str
    outcome_summary: str
    errors: tuple[str, ...] = ()
    completed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.status, JobStatus):
            raise ValueError("status must be a JobStatus value")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "outcome_summary", require_non_empty_text(self.outcome_summary, "outcome_summary"))
        object.__setattr__(self, "errors", freeze_value(list(self.errors)))
        for idx, err in enumerate(self.errors):
            require_non_empty_text(err, f"errors[{idx}]")
        if self.completed_at is not None:
            object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))


@dataclass(frozen=True, slots=True)
class JobPauseRecord(ContractRecord):
    """Audit record when a job is paused."""

    job_id: str
    paused_at: str
    reason: PauseReason
    resumed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "paused_at", require_datetime_text(self.paused_at, "paused_at"))
        if not isinstance(self.reason, PauseReason):
            raise ValueError("reason must be a PauseReason value")
        if self.resumed_at is not None:
            object.__setattr__(self, "resumed_at", require_datetime_text(self.resumed_at, "resumed_at"))


@dataclass(frozen=True, slots=True)
class JobResumeRecord(ContractRecord):
    """Audit record when a job is resumed."""

    job_id: str
    resumed_at: str
    resumed_by_id: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "resumed_at", require_datetime_text(self.resumed_at, "resumed_at"))
        object.__setattr__(self, "resumed_by_id", require_non_empty_text(self.resumed_by_id, "resumed_by_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
