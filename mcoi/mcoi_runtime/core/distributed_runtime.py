"""Purpose: distributed execution fabric engine.
Governance scope: governed worker/queue/lease/shard/checkpoint runtime
    with backpressure computation, retry schedules, concurrency locks,
    violation detection, and replayable state hashing.
Dependencies: event_spine, invariants, contracts.
Invariants:
  - Duplicate IDs are rejected fail-closed.
  - Terminal states block further mutations.
  - Lease transitions are terminal-guarded (RELEASED/EXPIRED/REVOKED).
  - Shard transitions are terminal-guarded (DECOMMISSIONED).
  - Checkpoint transitions are terminal-guarded (COMMITTED/FAILED/ROLLED_BACK).
  - All outputs are frozen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.distributed_runtime import (
    BackpressureLevel,
    CheckpointDisposition,
    ConcurrencyLock,
    DistributedAssessment,
    DistributedCheckpoint,
    DistributedClosureReport,
    DistributedSnapshot,
    DistributedViolation,
    LeaseRecord,
    LeaseStatus,
    QueueRecord,
    QueueStatus,
    RetrySchedule,
    ShardRecord,
    ShardStatus,
    WorkerRecord,
    WorkerStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEASE_TERMINAL = frozenset({LeaseStatus.RELEASED, LeaseStatus.EXPIRED, LeaseStatus.REVOKED})
_SHARD_TERMINAL = frozenset({ShardStatus.DECOMMISSIONED})
_CHECKPOINT_TERMINAL = frozenset({
    CheckpointDisposition.COMMITTED,
    CheckpointDisposition.FAILED,
    CheckpointDisposition.ROLLED_BACK,
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dist", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class DistributedRuntimeEngine:
    """Governed distributed execution fabric engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._workers: dict[str, WorkerRecord] = {}
        self._queues: dict[str, QueueRecord] = {}
        self._leases: dict[str, LeaseRecord] = {}
        self._shards: dict[str, ShardRecord] = {}
        self._checkpoints: dict[str, DistributedCheckpoint] = {}
        self._retries: dict[str, RetrySchedule] = {}
        self._locks: dict[str, ConcurrencyLock] = {}
        self._violations: dict[str, DistributedViolation] = {}

    # -- Properties --
    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def queue_count(self) -> int:
        return len(self._queues)

    @property
    def lease_count(self) -> int:
        return len(self._leases)

    @property
    def shard_count(self) -> int:
        return len(self._shards)

    @property
    def checkpoint_count(self) -> int:
        return len(self._checkpoints)

    @property
    def lock_count(self) -> int:
        return len(self._locks)

    @property
    def retry_count(self) -> int:
        return len(self._retries)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -----------------------------------------------------------------------
    # Workers
    # -----------------------------------------------------------------------

    def register_worker(
        self,
        worker_id: str,
        tenant_id: str,
        display_name: str,
        queue_ref: str = "default",
        capacity: int = 10,
    ) -> WorkerRecord:
        if worker_id in self._workers:
            raise RuntimeCoreInvariantError("duplicate worker_id")
        now = _now_iso()
        worker = WorkerRecord(
            worker_id=worker_id, tenant_id=tenant_id, display_name=display_name,
            status=WorkerStatus.IDLE, queue_ref=queue_ref, capacity=capacity,
            active_leases=0, registered_at=now,
        )
        self._workers[worker_id] = worker
        _emit(self._events, "register_worker", {"worker_id": worker_id}, worker_id)
        return worker

    def get_worker(self, worker_id: str) -> WorkerRecord:
        if worker_id not in self._workers:
            raise RuntimeCoreInvariantError("unknown worker_id")
        return self._workers[worker_id]

    def drain_worker(self, worker_id: str) -> WorkerRecord:
        worker = self.get_worker(worker_id)
        if worker.status == WorkerStatus.TERMINATED:
            raise RuntimeCoreInvariantError("worker is TERMINATED")
        now = _now_iso()
        updated = WorkerRecord(
            worker_id=worker.worker_id, tenant_id=worker.tenant_id,
            display_name=worker.display_name, status=WorkerStatus.DRAINING,
            queue_ref=worker.queue_ref, capacity=worker.capacity,
            active_leases=worker.active_leases, registered_at=now,
        )
        self._workers[worker_id] = updated
        _emit(self._events, "drain_worker", {"worker_id": worker_id}, worker_id)
        return updated

    def terminate_worker(self, worker_id: str) -> WorkerRecord:
        worker = self.get_worker(worker_id)
        if worker.status == WorkerStatus.TERMINATED:
            raise RuntimeCoreInvariantError("worker is already TERMINATED")
        now = _now_iso()
        updated = WorkerRecord(
            worker_id=worker.worker_id, tenant_id=worker.tenant_id,
            display_name=worker.display_name, status=WorkerStatus.TERMINATED,
            queue_ref=worker.queue_ref, capacity=worker.capacity,
            active_leases=worker.active_leases, registered_at=now,
        )
        self._workers[worker_id] = updated
        _emit(self._events, "terminate_worker", {"worker_id": worker_id}, worker_id)
        return updated

    def workers_for_tenant(self, tenant_id: str) -> tuple[WorkerRecord, ...]:
        return tuple(w for w in self._workers.values() if w.tenant_id == tenant_id)

    # -----------------------------------------------------------------------
    # Queues
    # -----------------------------------------------------------------------

    def create_queue(
        self,
        queue_id: str,
        tenant_id: str,
        display_name: str,
        max_depth: int = 1000,
    ) -> QueueRecord:
        if queue_id in self._queues:
            raise RuntimeCoreInvariantError("duplicate queue_id")
        now = _now_iso()
        queue = QueueRecord(
            queue_id=queue_id, tenant_id=tenant_id, display_name=display_name,
            status=QueueStatus.ACTIVE, depth=0, max_depth=max_depth,
            backpressure=BackpressureLevel.NONE, created_at=now,
        )
        self._queues[queue_id] = queue
        _emit(self._events, "create_queue", {"queue_id": queue_id}, queue_id)
        return queue

    def get_queue(self, queue_id: str) -> QueueRecord:
        if queue_id not in self._queues:
            raise RuntimeCoreInvariantError("unknown queue_id")
        return self._queues[queue_id]

    def pause_queue(self, queue_id: str) -> QueueRecord:
        queue = self.get_queue(queue_id)
        if queue.status == QueueStatus.CLOSED:
            raise RuntimeCoreInvariantError("queue is CLOSED")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=queue.queue_id, tenant_id=queue.tenant_id,
            display_name=queue.display_name, status=QueueStatus.PAUSED,
            depth=queue.depth, max_depth=queue.max_depth,
            backpressure=queue.backpressure, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "pause_queue", {"queue_id": queue_id}, queue_id)
        return updated

    def resume_queue(self, queue_id: str) -> QueueRecord:
        queue = self.get_queue(queue_id)
        if queue.status == QueueStatus.CLOSED:
            raise RuntimeCoreInvariantError("queue is CLOSED")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=queue.queue_id, tenant_id=queue.tenant_id,
            display_name=queue.display_name, status=QueueStatus.ACTIVE,
            depth=queue.depth, max_depth=queue.max_depth,
            backpressure=queue.backpressure, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "resume_queue", {"queue_id": queue_id}, queue_id)
        return updated

    def close_queue(self, queue_id: str) -> QueueRecord:
        queue = self.get_queue(queue_id)
        if queue.status == QueueStatus.CLOSED:
            raise RuntimeCoreInvariantError("queue is already CLOSED")
        now = _now_iso()
        updated = QueueRecord(
            queue_id=queue.queue_id, tenant_id=queue.tenant_id,
            display_name=queue.display_name, status=QueueStatus.CLOSED,
            depth=queue.depth, max_depth=queue.max_depth,
            backpressure=queue.backpressure, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "close_queue", {"queue_id": queue_id}, queue_id)
        return updated

    def queues_for_tenant(self, tenant_id: str) -> tuple[QueueRecord, ...]:
        return tuple(q for q in self._queues.values() if q.tenant_id == tenant_id)

    # -----------------------------------------------------------------------
    # Leases
    # -----------------------------------------------------------------------

    def acquire_lease(
        self,
        lease_id: str,
        tenant_id: str,
        worker_id: str,
        task_ref: str,
        ttl_ms: int = 30000,
    ) -> LeaseRecord:
        if lease_id in self._leases:
            raise RuntimeCoreInvariantError("duplicate lease_id")
        now = _now_iso()
        lease = LeaseRecord(
            lease_id=lease_id, tenant_id=tenant_id, worker_id=worker_id,
            task_ref=task_ref, status=LeaseStatus.HELD, ttl_ms=ttl_ms,
            acquired_at=now,
        )
        self._leases[lease_id] = lease
        _emit(self._events, "acquire_lease", {"lease_id": lease_id}, lease_id)
        return lease

    def _transition_lease(self, lease_id: str, target: LeaseStatus) -> LeaseRecord:
        if lease_id not in self._leases:
            raise RuntimeCoreInvariantError("unknown lease_id")
        lease = self._leases[lease_id]
        if lease.status in _LEASE_TERMINAL:
            raise RuntimeCoreInvariantError("lease is in terminal state")
        now = _now_iso()
        updated = LeaseRecord(
            lease_id=lease.lease_id, tenant_id=lease.tenant_id,
            worker_id=lease.worker_id, task_ref=lease.task_ref,
            status=target, ttl_ms=lease.ttl_ms, acquired_at=now,
        )
        self._leases[lease_id] = updated
        _emit(self._events, f"lease_{target.value}", {"lease_id": lease_id}, lease_id)
        return updated

    def release_lease(self, lease_id: str) -> LeaseRecord:
        return self._transition_lease(lease_id, LeaseStatus.RELEASED)

    def expire_lease(self, lease_id: str) -> LeaseRecord:
        return self._transition_lease(lease_id, LeaseStatus.EXPIRED)

    def revoke_lease(self, lease_id: str) -> LeaseRecord:
        return self._transition_lease(lease_id, LeaseStatus.REVOKED)

    # -----------------------------------------------------------------------
    # Shards
    # -----------------------------------------------------------------------

    def register_shard(
        self,
        shard_id: str,
        tenant_id: str,
        partition_key: str,
        assigned_worker: str,
        record_count: int = 0,
    ) -> ShardRecord:
        if shard_id in self._shards:
            raise RuntimeCoreInvariantError("duplicate shard_id")
        now = _now_iso()
        shard = ShardRecord(
            shard_id=shard_id, tenant_id=tenant_id, partition_key=partition_key,
            status=ShardStatus.ASSIGNED, record_count=record_count,
            assigned_worker=assigned_worker, created_at=now,
        )
        self._shards[shard_id] = shard
        _emit(self._events, "register_shard", {"shard_id": shard_id}, shard_id)
        return shard

    def _transition_shard(self, shard_id: str, target: ShardStatus) -> ShardRecord:
        if shard_id not in self._shards:
            raise RuntimeCoreInvariantError("unknown shard_id")
        shard = self._shards[shard_id]
        if shard.status in _SHARD_TERMINAL:
            raise RuntimeCoreInvariantError("shard is in terminal state")
        now = _now_iso()
        updated = ShardRecord(
            shard_id=shard.shard_id, tenant_id=shard.tenant_id,
            partition_key=shard.partition_key, status=target,
            record_count=shard.record_count, assigned_worker=shard.assigned_worker,
            created_at=now,
        )
        self._shards[shard_id] = updated
        _emit(self._events, f"shard_{target.value}", {"shard_id": shard_id}, shard_id)
        return updated

    def migrate_shard(self, shard_id: str) -> ShardRecord:
        return self._transition_shard(shard_id, ShardStatus.MIGRATING)

    def complete_migration(self, shard_id: str) -> ShardRecord:
        return self._transition_shard(shard_id, ShardStatus.ASSIGNED)

    def decommission_shard(self, shard_id: str) -> ShardRecord:
        return self._transition_shard(shard_id, ShardStatus.DECOMMISSIONED)

    # -----------------------------------------------------------------------
    # Checkpoints
    # -----------------------------------------------------------------------

    def create_checkpoint(
        self,
        checkpoint_id: str,
        tenant_id: str,
        shard_count: int = 0,
        worker_count: int = 0,
    ) -> DistributedCheckpoint:
        if checkpoint_id in self._checkpoints:
            raise RuntimeCoreInvariantError("duplicate checkpoint_id")
        now = _now_iso()
        cp = DistributedCheckpoint(
            checkpoint_id=checkpoint_id, tenant_id=tenant_id,
            disposition=CheckpointDisposition.PENDING,
            shard_count=shard_count, worker_count=worker_count,
            created_at=now,
        )
        self._checkpoints[checkpoint_id] = cp
        _emit(self._events, "create_checkpoint", {"checkpoint_id": checkpoint_id}, checkpoint_id)
        return cp

    def _transition_checkpoint(self, checkpoint_id: str, target: CheckpointDisposition) -> DistributedCheckpoint:
        if checkpoint_id not in self._checkpoints:
            raise RuntimeCoreInvariantError("unknown checkpoint_id")
        cp = self._checkpoints[checkpoint_id]
        if cp.disposition in _CHECKPOINT_TERMINAL:
            raise RuntimeCoreInvariantError("checkpoint is in terminal state")
        now = _now_iso()
        updated = DistributedCheckpoint(
            checkpoint_id=cp.checkpoint_id, tenant_id=cp.tenant_id,
            disposition=target, shard_count=cp.shard_count,
            worker_count=cp.worker_count, created_at=now,
        )
        self._checkpoints[checkpoint_id] = updated
        _emit(self._events, f"checkpoint_{target.value}", {"checkpoint_id": checkpoint_id}, checkpoint_id)
        return updated

    def commit_checkpoint(self, checkpoint_id: str) -> DistributedCheckpoint:
        return self._transition_checkpoint(checkpoint_id, CheckpointDisposition.COMMITTED)

    def fail_checkpoint(self, checkpoint_id: str) -> DistributedCheckpoint:
        return self._transition_checkpoint(checkpoint_id, CheckpointDisposition.FAILED)

    def rollback_checkpoint(self, checkpoint_id: str) -> DistributedCheckpoint:
        return self._transition_checkpoint(checkpoint_id, CheckpointDisposition.ROLLED_BACK)

    # -----------------------------------------------------------------------
    # Retry schedules
    # -----------------------------------------------------------------------

    def create_retry_schedule(
        self,
        schedule_id: str,
        tenant_id: str,
        task_ref: str,
        max_retries: int = 3,
        backoff_ms: int = 1000,
    ) -> RetrySchedule:
        if schedule_id in self._retries:
            raise RuntimeCoreInvariantError("duplicate schedule_id")
        now = _now_iso()
        rs = RetrySchedule(
            schedule_id=schedule_id, tenant_id=tenant_id, task_ref=task_ref,
            max_retries=max_retries, retry_count=0, backoff_ms=backoff_ms,
            created_at=now,
        )
        self._retries[schedule_id] = rs
        _emit(self._events, "create_retry_schedule", {"schedule_id": schedule_id}, schedule_id)
        return rs

    def increment_retry(self, schedule_id: str) -> RetrySchedule:
        if schedule_id not in self._retries:
            raise RuntimeCoreInvariantError("unknown schedule_id")
        rs = self._retries[schedule_id]
        new_count = rs.retry_count + 1
        if new_count >= rs.max_retries:
            raise RuntimeCoreInvariantError("retry schedule exceeded max_retries")
        now = _now_iso()
        updated = RetrySchedule(
            schedule_id=rs.schedule_id, tenant_id=rs.tenant_id,
            task_ref=rs.task_ref, max_retries=rs.max_retries,
            retry_count=new_count, backoff_ms=rs.backoff_ms,
            created_at=now,
        )
        self._retries[schedule_id] = updated
        _emit(self._events, "increment_retry", {"schedule_id": schedule_id, "count": new_count}, schedule_id)
        return updated

    # -----------------------------------------------------------------------
    # Concurrency locks
    # -----------------------------------------------------------------------

    def acquire_lock(
        self,
        lock_id: str,
        tenant_id: str,
        resource_ref: str,
        holder_ref: str,
    ) -> ConcurrencyLock:
        if lock_id in self._locks:
            raise RuntimeCoreInvariantError("duplicate lock_id")
        # Check for duplicate resource_ref
        for existing in self._locks.values():
            if existing.resource_ref == resource_ref:
                raise RuntimeCoreInvariantError("resource already locked")
        now = _now_iso()
        lock = ConcurrencyLock(
            lock_id=lock_id, tenant_id=tenant_id, resource_ref=resource_ref,
            holder_ref=holder_ref, acquired_at=now,
        )
        self._locks[lock_id] = lock
        _emit(self._events, "acquire_lock", {"lock_id": lock_id, "resource_ref": resource_ref}, lock_id)
        return lock

    def release_lock(self, lock_id: str) -> ConcurrencyLock:
        if lock_id not in self._locks:
            raise RuntimeCoreInvariantError("unknown lock_id")
        lock = self._locks.pop(lock_id)
        _emit(self._events, "release_lock", {"lock_id": lock_id}, lock_id)
        return lock

    # -----------------------------------------------------------------------
    # Backpressure
    # -----------------------------------------------------------------------

    def compute_backpressure(self, queue_id: str) -> QueueRecord:
        queue = self.get_queue(queue_id)
        if queue.max_depth == 0:
            level = BackpressureLevel.NONE
        else:
            ratio = queue.depth / queue.max_depth
            if ratio >= 0.9:
                level = BackpressureLevel.CRITICAL
            elif ratio >= 0.7:
                level = BackpressureLevel.HIGH
            elif ratio >= 0.5:
                level = BackpressureLevel.MEDIUM
            elif ratio >= 0.3:
                level = BackpressureLevel.LOW
            else:
                level = BackpressureLevel.NONE
        now = _now_iso()
        updated = QueueRecord(
            queue_id=queue.queue_id, tenant_id=queue.tenant_id,
            display_name=queue.display_name, status=queue.status,
            depth=queue.depth, max_depth=queue.max_depth,
            backpressure=level, created_at=now,
        )
        self._queues[queue_id] = updated
        _emit(self._events, "compute_backpressure", {
            "queue_id": queue_id, "level": level.value,
        }, queue_id)
        return updated

    # -----------------------------------------------------------------------
    # Snapshot
    # -----------------------------------------------------------------------

    def distributed_snapshot(self, snapshot_id: str, tenant_id: str) -> DistributedSnapshot:
        now = _now_iso()
        snap = DistributedSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_workers=len([w for w in self._workers.values() if w.tenant_id == tenant_id]),
            total_queues=len([q for q in self._queues.values() if q.tenant_id == tenant_id]),
            total_leases=len([l for l in self._leases.values() if l.tenant_id == tenant_id]),
            total_shards=len([s for s in self._shards.values() if s.tenant_id == tenant_id]),
            total_checkpoints=len([c for c in self._checkpoints.values() if c.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "distributed_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -----------------------------------------------------------------------
    # Violations
    # -----------------------------------------------------------------------

    def detect_distributed_violations(self, tenant_id: str) -> tuple[DistributedViolation, ...]:
        new_violations: list[DistributedViolation] = []
        now = _now_iso()

        # 1. Orphaned shards
        for shard in self._shards.values():
            if shard.tenant_id != tenant_id:
                continue
            if shard.status == ShardStatus.ORPHANED:
                vid = stable_identifier("viol-dist", {
                    "shard_id": shard.shard_id, "reason": "orphaned_shard",
                })
                if vid not in self._violations:
                    v = DistributedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="orphaned_shard",
                        reason="orphaned shard",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. Expired leases still HELD
        for lease in self._leases.values():
            if lease.tenant_id != tenant_id:
                continue
            if lease.status == LeaseStatus.HELD:
                vid = stable_identifier("viol-dist", {
                    "lease_id": lease.lease_id, "reason": "expired_lease_held",
                })
                if vid not in self._violations:
                    v = DistributedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="expired_lease_held",
                        reason="held lease may be expired",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Queue critical backpressure
        for queue in self._queues.values():
            if queue.tenant_id != tenant_id:
                continue
            if queue.backpressure == BackpressureLevel.CRITICAL:
                vid = stable_identifier("viol-dist", {
                    "queue_id": queue.queue_id, "reason": "queue_critical_backpressure",
                })
                if vid not in self._violations:
                    v = DistributedViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="queue_critical_backpressure",
                        reason="queue has critical backpressure",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_distributed_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id)
        return tuple(new_violations)

    # -----------------------------------------------------------------------
    # Assessment
    # -----------------------------------------------------------------------

    def distributed_assessment(self, assessment_id: str, tenant_id: str) -> DistributedAssessment:
        now = _now_iso()
        t_workers = len([w for w in self._workers.values() if w.tenant_id == tenant_id])
        t_queues = len([q for q in self._queues.values() if q.tenant_id == tenant_id])
        t_leases = len([l for l in self._leases.values() if l.tenant_id == tenant_id])
        t_checkpoints = len([c for c in self._checkpoints.values() if c.tenant_id == tenant_id])
        t_violations = len([v for v in self._violations.values() if v.tenant_id == tenant_id])
        active_workers = len([w for w in self._workers.values() if w.tenant_id == tenant_id and w.status == WorkerStatus.ACTIVE])
        rate = active_workers / t_workers if t_workers else 0.0
        assessment = DistributedAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_workers=t_workers, total_queues=t_queues,
            total_leases=t_leases, total_checkpoints=t_checkpoints,
            total_violations=t_violations,
            health_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "distributed_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -----------------------------------------------------------------------
    # Closure report
    # -----------------------------------------------------------------------

    def distributed_closure_report(self, report_id: str, tenant_id: str) -> DistributedClosureReport:
        now = _now_iso()
        report = DistributedClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_workers=len([w for w in self._workers.values() if w.tenant_id == tenant_id]),
            total_queues=len([q for q in self._queues.values() if q.tenant_id == tenant_id]),
            total_leases=len([l for l in self._leases.values() if l.tenant_id == tenant_id]),
            total_checkpoints=len([c for c in self._checkpoints.values() if c.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "distributed_closure_report", {"report_id": report_id}, report_id)
        return report

    # -----------------------------------------------------------------------
    # State hash
    # -----------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._workers):
            parts.append(f"worker:{k}:{self._workers[k].status.value}")
        for k in sorted(self._queues):
            parts.append(f"queue:{k}:{self._queues[k].status.value}")
        for k in sorted(self._leases):
            parts.append(f"lease:{k}:{self._leases[k].status.value}")
        for k in sorted(self._shards):
            parts.append(f"shard:{k}:{self._shards[k].status.value}")
        for k in sorted(self._checkpoints):
            parts.append(f"checkpoint:{k}:{self._checkpoints[k].disposition.value}")
        for k in sorted(self._retries):
            parts.append(f"retry:{k}:{self._retries[k].retry_count}")
        for k in sorted(self._locks):
            parts.append(f"lock:{k}:{self._locks[k].resource_ref}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
