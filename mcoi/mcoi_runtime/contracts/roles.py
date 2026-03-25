"""Purpose: canonical team runtime role and worker contracts.
Governance scope: role descriptors, worker profiles, capacity, assignment, handoff, and queue state typing.
Dependencies: docs/29_team_runtime.md, shared contract base helpers.
Invariants:
  - Every role has a non-empty ID, name, and at least one required skill.
  - Worker capacity never reports negative available slots.
  - No handoff without source and destination worker IDs.
  - Assignment decisions always reference a job, worker, and role.
  - WorkloadSnapshot contains at least one WorkerCapacity entry.
  - TeamQueueState counts are non-negative.
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
    require_non_empty_tuple,
)


# --- Classification enums ---


class WorkerStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    OFFLINE = "offline"
    ON_HOLD = "on_hold"


class AssignmentStrategy(StrEnum):
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"
    EXPLICIT = "explicit"
    ESCALATE = "escalate"


class HandoffReason(StrEnum):
    CAPACITY_EXCEEDED = "capacity_exceeded"
    ROLE_CHANGE = "role_change"
    ESCALATION = "escalation"
    OPERATOR_OVERRIDE = "operator_override"
    SHIFT_CHANGE = "shift_change"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class RoleDescriptor(ContractRecord):
    """Defines a named role with skill requirements and concurrency constraints."""

    role_id: str
    name: str
    description: str
    required_skills: tuple[str, ...]
    approval_required: bool = False
    max_concurrent_per_worker: int = 5
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(
            self, "required_skills",
            require_non_empty_tuple(self.required_skills, "required_skills"),
        )
        for idx, skill in enumerate(self.required_skills):
            require_non_empty_text(skill, f"required_skills[{idx}]")
        if not isinstance(self.approval_required, bool):
            raise ValueError("approval_required must be a boolean")
        if not isinstance(self.max_concurrent_per_worker, int) or self.max_concurrent_per_worker < 1:
            raise ValueError("max_concurrent_per_worker must be a positive integer")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class WorkerProfile(ContractRecord):
    """Identity and capability profile for a worker."""

    worker_id: str
    name: str
    roles: tuple[str, ...]
    max_concurrent_jobs: int = 5
    status: WorkerStatus = WorkerStatus.AVAILABLE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(
            self, "roles",
            require_non_empty_tuple(self.roles, "roles"),
        )
        for idx, role_id in enumerate(self.roles):
            require_non_empty_text(role_id, f"roles[{idx}]")
        if not isinstance(self.max_concurrent_jobs, int) or self.max_concurrent_jobs < 1:
            raise ValueError("max_concurrent_jobs must be a positive integer")
        if not isinstance(self.status, WorkerStatus):
            raise ValueError("status must be a WorkerStatus value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class WorkerCapacity(ContractRecord):
    """Point-in-time load snapshot for a single worker."""

    worker_id: str
    max_concurrent: int
    current_load: int
    available_slots: int
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        if not isinstance(self.max_concurrent, int) or self.max_concurrent < 1:
            raise ValueError("max_concurrent must be a positive integer")
        if not isinstance(self.current_load, int) or self.current_load < 0:
            raise ValueError("current_load must be a non-negative integer")
        if self.current_load > self.max_concurrent:
            raise ValueError("current_load cannot exceed max_concurrent")
        if not isinstance(self.available_slots, int) or self.available_slots < 0:
            raise ValueError("available_slots must be a non-negative integer")
        if self.available_slots != self.max_concurrent - self.current_load:
            raise ValueError(
                "available_slots must equal max_concurrent - current_load"
            )
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))


@dataclass(frozen=True, slots=True)
class AssignmentPolicy(ContractRecord):
    """Strategy binding for routing jobs through a role to workers."""

    policy_id: str
    role_id: str
    strategy: AssignmentStrategy
    fallback_team_id: str | None = None
    escalation_chain_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        if not isinstance(self.strategy, AssignmentStrategy):
            raise ValueError("strategy must be an AssignmentStrategy value")
        if self.fallback_team_id is not None:
            object.__setattr__(
                self, "fallback_team_id",
                require_non_empty_text(self.fallback_team_id, "fallback_team_id"),
            )
        if self.escalation_chain_id is not None:
            object.__setattr__(
                self, "escalation_chain_id",
                require_non_empty_text(self.escalation_chain_id, "escalation_chain_id"),
            )


@dataclass(frozen=True, slots=True)
class AssignmentDecision(ContractRecord):
    """Audit record for a single job-to-worker assignment decision."""

    decision_id: str
    job_id: str
    worker_id: str
    role_id: str
    reason: str
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        object.__setattr__(self, "role_id", require_non_empty_text(self.role_id, "role_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class HandoffRecord(ContractRecord):
    """Typed audit record for an explicit job transfer between workers."""

    handoff_id: str
    job_id: str
    from_worker_id: str
    to_worker_id: str
    reason: HandoffReason
    thread_id: str | None = None
    handoff_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "handoff_id", require_non_empty_text(self.handoff_id, "handoff_id"))
        object.__setattr__(self, "job_id", require_non_empty_text(self.job_id, "job_id"))
        object.__setattr__(self, "from_worker_id", require_non_empty_text(self.from_worker_id, "from_worker_id"))
        object.__setattr__(self, "to_worker_id", require_non_empty_text(self.to_worker_id, "to_worker_id"))
        if not isinstance(self.reason, HandoffReason):
            raise ValueError("reason must be a HandoffReason value")
        if self.thread_id is not None:
            object.__setattr__(self, "thread_id", require_non_empty_text(self.thread_id, "thread_id"))
        object.__setattr__(self, "handoff_at", require_datetime_text(self.handoff_at, "handoff_at"))


@dataclass(frozen=True, slots=True)
class WorkloadSnapshot(ContractRecord):
    """Team-wide capacity snapshot at a point in time."""

    snapshot_id: str
    team_id: str
    worker_capacities: tuple[WorkerCapacity, ...]
    captured_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "team_id", require_non_empty_text(self.team_id, "team_id"))
        object.__setattr__(
            self, "worker_capacities",
            require_non_empty_tuple(self.worker_capacities, "worker_capacities"),
        )
        for entry in self.worker_capacities:
            if not isinstance(entry, WorkerCapacity):
                raise ValueError("each entry in worker_capacities must be a WorkerCapacity instance")
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))


@dataclass(frozen=True, slots=True)
class TeamQueueState(ContractRecord):
    """Aggregate queue health for a team."""

    team_id: str
    queued_jobs: int
    assigned_jobs: int
    waiting_jobs: int
    overloaded_workers: int
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "team_id", require_non_empty_text(self.team_id, "team_id"))
        if not isinstance(self.queued_jobs, int) or self.queued_jobs < 0:
            raise ValueError("queued_jobs must be a non-negative integer")
        if not isinstance(self.assigned_jobs, int) or self.assigned_jobs < 0:
            raise ValueError("assigned_jobs must be a non-negative integer")
        if not isinstance(self.waiting_jobs, int) or self.waiting_jobs < 0:
            raise ValueError("waiting_jobs must be a non-negative integer")
        if not isinstance(self.overloaded_workers, int) or self.overloaded_workers < 0:
            raise ValueError("overloaded_workers must be a non-negative integer")
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
