"""Purpose: distributed execution fabric contracts.
Governance scope: typed descriptors for workers, queues, leases, shards,
    checkpoints, retry schedules, concurrency locks, snapshots, violations,
    and closure reports for distributed scale-out execution.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Backpressure levels are explicit and computable.
  - Lease and shard lifecycles are terminal-guarded.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkerStatus(Enum):
    """Status of a registered distributed worker."""
    IDLE = "idle"
    ACTIVE = "active"
    DRAINING = "draining"
    TERMINATED = "terminated"


class QueueStatus(Enum):
    """Status of a distributed task queue."""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    CLOSED = "closed"


class LeaseStatus(Enum):
    """Status of a task lease."""
    HELD = "held"
    RELEASED = "released"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ShardStatus(Enum):
    """Status of a data shard."""
    ASSIGNED = "assigned"
    MIGRATING = "migrating"
    ORPHANED = "orphaned"
    DECOMMISSIONED = "decommissioned"


class CheckpointDisposition(Enum):
    """Disposition of a distributed checkpoint."""
    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class BackpressureLevel(Enum):
    """Backpressure level for a queue."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkerRecord(ContractRecord):
    """A registered distributed worker."""

    worker_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: WorkerStatus = WorkerStatus.IDLE
    queue_ref: str = ""
    capacity: int = 0
    active_leases: int = 0
    registered_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, WorkerStatus):
            raise ValueError("status must be a WorkerStatus")
        object.__setattr__(self, "queue_ref", require_non_empty_text(self.queue_ref, "queue_ref"))
        object.__setattr__(self, "capacity", require_non_negative_int(self.capacity, "capacity"))
        object.__setattr__(self, "active_leases", require_non_negative_int(self.active_leases, "active_leases"))
        require_datetime_text(self.registered_at, "registered_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueueRecord(ContractRecord):
    """A distributed task queue."""

    queue_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: QueueStatus = QueueStatus.ACTIVE
    depth: int = 0
    max_depth: int = 0
    backpressure: BackpressureLevel = BackpressureLevel.NONE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "queue_id", require_non_empty_text(self.queue_id, "queue_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, QueueStatus):
            raise ValueError("status must be a QueueStatus")
        object.__setattr__(self, "depth", require_non_negative_int(self.depth, "depth"))
        object.__setattr__(self, "max_depth", require_non_negative_int(self.max_depth, "max_depth"))
        if not isinstance(self.backpressure, BackpressureLevel):
            raise ValueError("backpressure must be a BackpressureLevel")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LeaseRecord(ContractRecord):
    """A task lease held by a worker."""

    lease_id: str = ""
    tenant_id: str = ""
    worker_id: str = ""
    task_ref: str = ""
    status: LeaseStatus = LeaseStatus.HELD
    ttl_ms: int = 0
    acquired_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lease_id", require_non_empty_text(self.lease_id, "lease_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "worker_id", require_non_empty_text(self.worker_id, "worker_id"))
        object.__setattr__(self, "task_ref", require_non_empty_text(self.task_ref, "task_ref"))
        if not isinstance(self.status, LeaseStatus):
            raise ValueError("status must be a LeaseStatus")
        object.__setattr__(self, "ttl_ms", require_non_negative_int(self.ttl_ms, "ttl_ms"))
        require_datetime_text(self.acquired_at, "acquired_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ShardRecord(ContractRecord):
    """A data shard assigned to a worker."""

    shard_id: str = ""
    tenant_id: str = ""
    partition_key: str = ""
    status: ShardStatus = ShardStatus.ASSIGNED
    record_count: int = 0
    assigned_worker: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "shard_id", require_non_empty_text(self.shard_id, "shard_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "partition_key", require_non_empty_text(self.partition_key, "partition_key"))
        if not isinstance(self.status, ShardStatus):
            raise ValueError("status must be a ShardStatus")
        object.__setattr__(self, "record_count", require_non_negative_int(self.record_count, "record_count"))
        object.__setattr__(self, "assigned_worker", require_non_empty_text(self.assigned_worker, "assigned_worker"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DistributedCheckpoint(ContractRecord):
    """A distributed checkpoint for coordinated state capture."""

    checkpoint_id: str = ""
    tenant_id: str = ""
    disposition: CheckpointDisposition = CheckpointDisposition.PENDING
    shard_count: int = 0
    worker_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_id", require_non_empty_text(self.checkpoint_id, "checkpoint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, CheckpointDisposition):
            raise ValueError("disposition must be a CheckpointDisposition")
        object.__setattr__(self, "shard_count", require_non_negative_int(self.shard_count, "shard_count"))
        object.__setattr__(self, "worker_count", require_non_negative_int(self.worker_count, "worker_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RetrySchedule(ContractRecord):
    """A retry schedule for a failed task."""

    schedule_id: str = ""
    tenant_id: str = ""
    task_ref: str = ""
    max_retries: int = 0
    retry_count: int = 0
    backoff_ms: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "schedule_id", require_non_empty_text(self.schedule_id, "schedule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "task_ref", require_non_empty_text(self.task_ref, "task_ref"))
        object.__setattr__(self, "max_retries", require_non_negative_int(self.max_retries, "max_retries"))
        object.__setattr__(self, "retry_count", require_non_negative_int(self.retry_count, "retry_count"))
        object.__setattr__(self, "backoff_ms", require_non_negative_int(self.backoff_ms, "backoff_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConcurrencyLock(ContractRecord):
    """A distributed concurrency lock on a resource."""

    lock_id: str = ""
    tenant_id: str = ""
    resource_ref: str = ""
    holder_ref: str = ""
    acquired_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lock_id", require_non_empty_text(self.lock_id, "lock_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "resource_ref", require_non_empty_text(self.resource_ref, "resource_ref"))
        object.__setattr__(self, "holder_ref", require_non_empty_text(self.holder_ref, "holder_ref"))
        require_datetime_text(self.acquired_at, "acquired_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DistributedSnapshot(ContractRecord):
    """Point-in-time snapshot of distributed runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    total_queues: int = 0
    total_leases: int = 0
    total_shards: int = 0
    total_checkpoints: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "total_queues", require_non_negative_int(self.total_queues, "total_queues"))
        object.__setattr__(self, "total_leases", require_non_negative_int(self.total_leases, "total_leases"))
        object.__setattr__(self, "total_shards", require_non_negative_int(self.total_shards, "total_shards"))
        object.__setattr__(self, "total_checkpoints", require_non_negative_int(self.total_checkpoints, "total_checkpoints"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DistributedViolation(ContractRecord):
    """A detected violation in the distributed runtime."""

    violation_id: str = ""
    tenant_id: str = ""
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
class DistributedClosureReport(ContractRecord):
    """Closure report for distributed runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    total_queues: int = 0
    total_leases: int = 0
    total_checkpoints: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "total_queues", require_non_negative_int(self.total_queues, "total_queues"))
        object.__setattr__(self, "total_leases", require_non_negative_int(self.total_leases, "total_leases"))
        object.__setattr__(self, "total_checkpoints", require_non_negative_int(self.total_checkpoints, "total_checkpoints"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DistributedAssessment(ContractRecord):
    """Assessment of distributed runtime health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_workers: int = 0
    total_queues: int = 0
    total_leases: int = 0
    total_checkpoints: int = 0
    total_violations: int = 0
    health_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_workers", require_non_negative_int(self.total_workers, "total_workers"))
        object.__setattr__(self, "total_queues", require_non_negative_int(self.total_queues, "total_queues"))
        object.__setattr__(self, "total_leases", require_non_negative_int(self.total_leases, "total_leases"))
        object.__setattr__(self, "total_checkpoints", require_non_negative_int(self.total_checkpoints, "total_checkpoints"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "health_rate", require_unit_float(self.health_rate, "health_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
