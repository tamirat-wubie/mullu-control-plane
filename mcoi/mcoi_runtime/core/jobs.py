"""Purpose: job core engine — work queue, assignment, SLA, and follow-up.
Governance scope: job lifecycle management, queue operations, SLA evaluation, follow-up scheduling.
Dependencies: job contracts, invariant helpers.
Invariants:
  - Jobs follow a strict state machine; invalid transitions are rejected.
  - Queue dequeue returns highest priority first, then earliest enqueued.
  - SLA evaluation is deterministic given the same clock.
  - Clock function is injected for testability.
  - Completed/failed/cancelled jobs cannot be restarted.
  - Archived jobs are terminal except through explicit archive transition.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from mcoi_runtime.contracts.job import (
    AssignmentRecord,
    DeadlineRecord,
    FollowUpRecord,
    JobDescriptor,
    JobExecutionRecord,
    JobPauseRecord,
    JobPriority,
    JobResumeRecord,
    JobState,
    JobStatus,
    PauseReason,
    SlaStatus,
    WorkQueueEntry,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


# --- Priority rank (lower = higher priority) ---

JOB_PRIORITY_RANK: dict[JobPriority, int] = {
    JobPriority.CRITICAL: 0,
    JobPriority.HIGH: 1,
    JobPriority.NORMAL: 2,
    JobPriority.LOW: 3,
    JobPriority.BACKGROUND: 4,
}

# --- Valid state transitions ---

_VALID_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.CREATED: frozenset({JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset({JobStatus.ASSIGNED, JobStatus.CANCELLED}),
    JobStatus.ASSIGNED: frozenset({JobStatus.IN_PROGRESS, JobStatus.CANCELLED}),
    JobStatus.IN_PROGRESS: frozenset({
        JobStatus.WAITING, JobStatus.PAUSED,
        JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED,
    }),
    JobStatus.WAITING: frozenset({
        JobStatus.IN_PROGRESS, JobStatus.PAUSED,
        JobStatus.FAILED, JobStatus.CANCELLED,
    }),
    JobStatus.PAUSED: frozenset({
        JobStatus.IN_PROGRESS, JobStatus.FAILED, JobStatus.CANCELLED,
    }),
    JobStatus.COMPLETED: frozenset({JobStatus.ARCHIVED}),
    JobStatus.FAILED: frozenset({JobStatus.ARCHIVED}),
    JobStatus.CANCELLED: frozenset({JobStatus.ARCHIVED}),
    JobStatus.ARCHIVED: frozenset(),
}


def _assert_transition(current: JobStatus, target: JobStatus) -> None:
    """Validate that a state transition is legal."""
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise RuntimeCoreInvariantError("invalid job state transition")


@dataclass(frozen=True, slots=True)
class JobMutationReceipt:
    """Observed job lifecycle mutation receipt."""

    receipt_id: str
    mutation_type: str
    effect_name: str
    job_id: str
    evidence_ref: str
    previous_status: str | None
    new_status: str
    recorded_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mutation_type": self.mutation_type,
            "effect_name": self.effect_name,
            "job_id": self.job_id,
            "evidence_ref": self.evidence_ref,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "recorded_at": self.recorded_at,
            "metadata": dict(self.metadata),
        }

    def to_effect_record(self) -> Any:
        from mcoi_runtime.contracts.execution import EffectRecord

        return EffectRecord(
            name=self.effect_name,
            details={
                "receipt_id": self.receipt_id,
                "mutation_type": self.mutation_type,
                "job_id": self.job_id,
                "evidence_ref": self.evidence_ref,
                "previous_status": self.previous_status,
                "new_status": self.new_status,
                "observed_at": self.recorded_at,
                "metadata": dict(self.metadata),
                "source": "job_engine",
            },
        )


class WorkQueue:
    """In-memory priority work queue for job entries.

    Rules:
    - Enqueue adds an entry; dequeue returns highest priority then earliest enqueued.
    - Assign attaches a person to a queue entry and produces an AssignmentRecord.
    - Duplicate entry IDs are rejected.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._entries: dict[str, WorkQueueEntry] = {}
        self._order: list[str] = []  # insertion order for tie-breaking

    def enqueue(self, job_descriptor: JobDescriptor) -> WorkQueueEntry:
        """Add a job to the queue, returning the queue entry."""
        entry_id = stable_identifier("wq-entry", {
            "job_id": job_descriptor.job_id,
            "enqueued_at": self._clock(),
        })
        now = self._clock()
        entry = WorkQueueEntry(
            entry_id=entry_id,
            job_id=job_descriptor.job_id,
            priority=job_descriptor.priority,
            enqueued_at=now,
        )
        if entry_id in self._entries:
            raise RuntimeCoreInvariantError("duplicate queue entry")
        self._entries[entry_id] = entry
        self._order.append(entry_id)
        return entry

    def restore_entry(self, entry: WorkQueueEntry) -> WorkQueueEntry:
        """Restore an exact persisted queue entry without generating new identifiers."""
        if not isinstance(entry, WorkQueueEntry):
            raise RuntimeCoreInvariantError("entry must be a WorkQueueEntry instance")
        if entry.entry_id in self._entries:
            raise RuntimeCoreInvariantError(f"duplicate queue entry: {entry.entry_id}")
        self._entries[entry.entry_id] = entry
        self._order.append(entry.entry_id)
        return entry

    def _sort_key(self, entry_id: str) -> tuple[int, int]:
        entry = self._entries[entry_id]
        rank = JOB_PRIORITY_RANK.get(entry.priority, 99)
        order_idx = self._order.index(entry_id)
        return (rank, order_idx)

    def dequeue_next(self) -> WorkQueueEntry | None:
        """Remove and return the highest-priority, earliest-enqueued entry."""
        if not self._entries:
            return None
        best_id = min(self._entries, key=self._sort_key)
        entry = self._entries.pop(best_id)
        self._order.remove(best_id)
        return entry

    def peek(self) -> WorkQueueEntry | None:
        """Return the next entry without removing it."""
        if not self._entries:
            return None
        best_id = min(self._entries, key=self._sort_key)
        return self._entries[best_id]

    def get(self, entry_id: str) -> WorkQueueEntry | None:
        """Return a queue entry by identifier without mutating queue state."""
        return self._entries.get(entry_id)

    def list_entries(self) -> tuple[WorkQueueEntry, ...]:
        """Return all entries sorted by priority then enqueue order."""
        sorted_ids = sorted(self._entries, key=self._sort_key)
        return tuple(self._entries[eid] for eid in sorted_ids)

    def assign(
        self,
        entry_id: str,
        person_id: str,
        assigned_by_id: str,
        reason: str,
    ) -> AssignmentRecord:
        """Assign a queue entry to a person, returning an AssignmentRecord."""
        ensure_non_empty_text("entry_id", entry_id)
        ensure_non_empty_text("person_id", person_id)
        ensure_non_empty_text("assigned_by_id", assigned_by_id)
        ensure_non_empty_text("reason", reason)
        if entry_id not in self._entries:
            raise RuntimeCoreInvariantError("queue entry not found")
        entry = self._entries[entry_id]
        now = self._clock()
        assignment_id = stable_identifier("assignment", {
            "job_id": entry.job_id,
            "person_id": person_id,
            "assigned_at": now,
        })
        record = AssignmentRecord(
            assignment_id=assignment_id,
            job_id=entry.job_id,
            assigned_to_id=person_id,
            assigned_by_id=assigned_by_id,
            assigned_at=now,
            reason=reason,
        )
        return record

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from the queue. Returns True if found and removed."""
        if entry_id not in self._entries:
            return False
        del self._entries[entry_id]
        self._order.remove(entry_id)
        return True


class JobEngine:
    """Manages job lifecycle, SLA evaluation, and follow-up scheduling.

    All timestamps are produced by the injected clock function for determinism.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._jobs: dict[str, JobDescriptor] = {}
        self._states: dict[str, JobState] = {}
        self._mutation_receipts: list[JobMutationReceipt] = []

    # --- Job creation ---

    def create_job(
        self,
        name: str,
        description: str,
        priority: JobPriority,
        *,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        deadline: str | None = None,
        sla_target_minutes: int | None = None,
    ) -> tuple[JobDescriptor, JobState]:
        """Create a new job and its initial state."""
        ensure_non_empty_text("name", name)
        ensure_non_empty_text("description", description)
        now = self._clock()
        job_id = stable_identifier("job", {
            "name": name,
            "created_at": now,
        })
        descriptor = JobDescriptor(
            job_id=job_id,
            name=name,
            description=description,
            priority=priority,
            goal_id=goal_id,
            workflow_id=workflow_id,
            deadline=deadline,
            sla_target_minutes=sla_target_minutes,
            created_at=now,
        )
        state = JobState(
            job_id=job_id,
            status=JobStatus.CREATED,
            sla_status=SlaStatus.NOT_APPLICABLE,
            updated_at=now,
        )
        self._jobs[job_id] = descriptor
        self._states[job_id] = state
        self._record_mutation_receipt(
            mutation_type="create_job",
            effect_name="job_created",
            job_id=job_id,
            previous_status=None,
            new_status=JobStatus.CREATED,
            recorded_at=now,
            metadata={
                "name_hash": _sha256_text(name),
                "description_hash": _sha256_text(description),
                "priority": priority.value,
                "goal_id_hash": _sha256_optional_text(goal_id),
                "workflow_id_hash": _sha256_optional_text(workflow_id),
                "deadline_present": deadline is not None,
                "sla_target_minutes": sla_target_minutes,
            },
        )
        return descriptor, state

    def restore_job(
        self,
        descriptor: JobDescriptor,
        state: JobState,
    ) -> tuple[JobDescriptor, JobState]:
        """Restore an exact persisted job descriptor and state without replay."""
        if not isinstance(descriptor, JobDescriptor):
            raise RuntimeCoreInvariantError("descriptor must be a JobDescriptor instance")
        if not isinstance(state, JobState):
            raise RuntimeCoreInvariantError("state must be a JobState instance")
        if descriptor.job_id != state.job_id:
            raise RuntimeCoreInvariantError("descriptor and state job_id must match")
        if descriptor.job_id in self._jobs or descriptor.job_id in self._states:
            raise RuntimeCoreInvariantError(f"job already restored: {descriptor.job_id}")
        if state.goal_id is not None and descriptor.goal_id is not None and state.goal_id != descriptor.goal_id:
            raise RuntimeCoreInvariantError("descriptor and state goal_id must match when both are present")
        if (
            state.workflow_id is not None
            and descriptor.workflow_id is not None
            and state.workflow_id != descriptor.workflow_id
        ):
            raise RuntimeCoreInvariantError(
                "descriptor and state workflow_id must match when both are present"
            )
        self._jobs[descriptor.job_id] = descriptor
        self._states[state.job_id] = state
        self._record_mutation_receipt(
            mutation_type="restore_job",
            effect_name="job_restored",
            job_id=descriptor.job_id,
            previous_status=None,
            new_status=state.status,
            recorded_at=state.updated_at or descriptor.created_at,
            metadata={
                "name_hash": _sha256_text(descriptor.name),
                "description_hash": _sha256_text(descriptor.description),
                "priority": descriptor.priority.value,
                "goal_id_hash": _sha256_optional_text(descriptor.goal_id),
                "workflow_id_hash": _sha256_optional_text(descriptor.workflow_id),
                "deadline_present": descriptor.deadline is not None,
                "sla_status": state.sla_status.value,
            },
        )
        return descriptor, state

    def get_job_descriptor(self, job_id: str) -> JobDescriptor | None:
        """Return a job descriptor by identifier without mutating engine state."""
        return self._jobs.get(job_id)

    def get_job_state(self, job_id: str) -> JobState | None:
        """Return a job state by identifier without mutating engine state."""
        return self._states.get(job_id)

    def list_job_descriptors(self) -> tuple[JobDescriptor, ...]:
        """Return all job descriptors in deterministic identifier order."""
        return tuple(self._jobs[job_id] for job_id in sorted(self._jobs))

    def list_job_states(self) -> tuple[JobState, ...]:
        """Return all job states in deterministic identifier order."""
        return tuple(self._states[job_id] for job_id in sorted(self._states))

    # --- State helpers ---

    def _get_state(self, job_id: str) -> JobState:
        ensure_non_empty_text("job_id", job_id)
        state = self._states.get(job_id)
        if state is None:
            raise RuntimeCoreInvariantError("job not found")
        return state

    def _get_descriptor(self, job_id: str) -> JobDescriptor:
        descriptor = self._jobs.get(job_id)
        if descriptor is None:
            raise RuntimeCoreInvariantError("job not found")
        return descriptor

    def _transition(
        self,
        job_id: str,
        target: JobStatus,
        *,
        mutation_type: str | None = None,
        effect_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobState:
        current = self._get_state(job_id)
        _assert_transition(current.status, target)
        now = self._clock()
        new_state = JobState(
            job_id=job_id,
            status=target,
            sla_status=current.sla_status,
            updated_at=now,
        )
        self._states[job_id] = new_state
        self._record_mutation_receipt(
            mutation_type=mutation_type or f"transition_to_{target.value}",
            effect_name=effect_name or f"job_{target.value}",
            job_id=job_id,
            previous_status=current.status,
            new_status=target,
            recorded_at=now,
            metadata=metadata or {},
        )
        return new_state

    # --- Lifecycle ---

    def start_job(self, job_id: str) -> JobState:
        """Transition a job to in_progress.

        Allows direct start from created (shortcut for non-queued jobs),
        or from assigned (via queue assignment flow).
        """
        current = self._get_state(job_id)
        if current.status == JobStatus.CREATED:
            now = self._clock()
            new_state = JobState(
                job_id=job_id,
                status=JobStatus.IN_PROGRESS,
                sla_status=current.sla_status,
                started_at=now,
                updated_at=now,
            )
            self._states[job_id] = new_state
            self._record_mutation_receipt(
                mutation_type="start_job",
                effect_name="job_started",
                job_id=job_id,
                previous_status=current.status,
                new_status=JobStatus.IN_PROGRESS,
                recorded_at=now,
                metadata={},
            )
            return new_state
        if current.status == JobStatus.ASSIGNED:
            return self._transition(
                job_id,
                JobStatus.IN_PROGRESS,
                mutation_type="start_job",
                effect_name="job_started",
            )
        # Any other state: use the normal transition validator (will raise)
        _assert_transition(current.status, JobStatus.IN_PROGRESS)
        return self._transition(job_id, JobStatus.IN_PROGRESS)

    def pause_job(self, job_id: str, reason: PauseReason) -> tuple[JobState, JobPauseRecord]:
        """Pause a running or waiting job."""
        current = self._get_state(job_id)
        _assert_transition(current.status, JobStatus.PAUSED)
        now = self._clock()
        new_state = JobState(
            job_id=job_id,
            status=JobStatus.PAUSED,
            sla_status=current.sla_status,
            pause_reason=reason,
            updated_at=now,
        )
        self._states[job_id] = new_state
        self._record_mutation_receipt(
            mutation_type="pause_job",
            effect_name="job_paused",
            job_id=job_id,
            previous_status=current.status,
            new_status=JobStatus.PAUSED,
            recorded_at=now,
            metadata={"pause_reason": reason.value},
        )
        record = JobPauseRecord(
            job_id=job_id,
            reason=reason,
            paused_at=now,
        )
        return new_state, record

    def resume_job(
        self,
        job_id: str,
        resumed_by_id: str,
        reason: str,
    ) -> tuple[JobState, JobResumeRecord]:
        """Resume a paused job back to in_progress."""
        ensure_non_empty_text("resumed_by_id", resumed_by_id)
        ensure_non_empty_text("reason", reason)
        new_state = self._transition(
            job_id,
            JobStatus.IN_PROGRESS,
            mutation_type="resume_job",
            effect_name="job_resumed",
            metadata={
                "resumed_by_id_hash": _sha256_text(resumed_by_id),
                "reason_hash": _sha256_text(reason),
            },
        )
        now = self._clock()
        record = JobResumeRecord(
            job_id=job_id,
            resumed_by_id=resumed_by_id,
            reason=reason,
            resumed_at=now,
        )
        return new_state, record

    def complete_job(
        self,
        job_id: str,
        outcome_summary: str,
    ) -> tuple[JobState, JobExecutionRecord]:
        """Mark a job as completed with a summary."""
        ensure_non_empty_text("outcome_summary", outcome_summary)
        descriptor = self._get_descriptor(job_id)
        current = self._get_state(job_id)
        new_state = self._transition(
            job_id,
            JobStatus.COMPLETED,
            mutation_type="complete_job",
            effect_name="job_completed",
            metadata={"outcome_summary_hash": _sha256_text(outcome_summary)},
        )
        now = self._clock()
        exec_id = stable_identifier("job-exec", {
            "job_id": job_id,
            "completed_at": now,
        })
        record = JobExecutionRecord(
            job_id=job_id,
            execution_id=exec_id,
            status=JobStatus.COMPLETED,
            started_at=current.started_at or descriptor.created_at,
            outcome_summary=outcome_summary,
            completed_at=now,
        )
        return new_state, record

    def fail_job(
        self,
        job_id: str,
        errors: tuple[str, ...],
    ) -> tuple[JobState, JobExecutionRecord]:
        """Mark a job as failed with error details."""
        descriptor = self._get_descriptor(job_id)
        current = self._get_state(job_id)
        new_state = self._transition(
            job_id,
            JobStatus.FAILED,
            mutation_type="fail_job",
            effect_name="job_failed",
            metadata={
                "error_count": len(errors),
                "errors_hash": _sha256_json(tuple(errors)),
            },
        )
        now = self._clock()
        exec_id = stable_identifier("job-exec", {
            "job_id": job_id,
            "failed_at": now,
        })
        record = JobExecutionRecord(
            job_id=job_id,
            execution_id=exec_id,
            status=JobStatus.FAILED,
            started_at=current.started_at or descriptor.created_at,
            outcome_summary="; ".join(errors) if errors else "failed",
            errors=errors,
            completed_at=now,
        )
        return new_state, record

    def cancel_job(self, job_id: str, reason: str) -> JobState:
        """Cancel a job. Allowed from any state except archived."""
        ensure_non_empty_text("reason", reason)
        return self._transition(
            job_id,
            JobStatus.CANCELLED,
            mutation_type="cancel_job",
            effect_name="job_cancelled",
            metadata={"reason_hash": _sha256_text(reason)},
        )

    # --- SLA evaluation ---

    def evaluate_sla(self, job_id: str, now: str) -> DeadlineRecord:
        """Evaluate SLA status for a job at a given time.

        Returns a DeadlineRecord with:
        - on_track: elapsed < 80% of sla_target
        - at_risk: elapsed 80-100%
        - breached: elapsed > 100%
        - not_applicable: no sla_target
        """
        descriptor = self._get_descriptor(job_id)
        self._get_state(job_id)  # verify job exists

        deadline_str = descriptor.deadline or descriptor.created_at

        if descriptor.sla_target_minutes is None:
            return DeadlineRecord(
                job_id=job_id,
                deadline=deadline_str,
                sla_status=SlaStatus.NOT_APPLICABLE,
                evaluated_at=now,
            )

        created_dt = datetime.fromisoformat(
            descriptor.created_at.replace("Z", "+00:00")
        )
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        elapsed = now_dt - created_dt
        target = timedelta(minutes=descriptor.sla_target_minutes)

        if target.total_seconds() == 0:
            sla_status = SlaStatus.BREACHED
        elif elapsed > target:
            sla_status = SlaStatus.BREACHED
        elif elapsed >= target * 0.8:
            sla_status = SlaStatus.AT_RISK
        else:
            sla_status = SlaStatus.ON_TRACK

        return DeadlineRecord(
            job_id=job_id,
            deadline=deadline_str,
            sla_status=sla_status,
            evaluated_at=now,
            sla_target_minutes=descriptor.sla_target_minutes,
        )

    # --- Follow-up scheduling ---

    def schedule_follow_up(
        self,
        job_id: str,
        reason: str,
        scheduled_at: str,
    ) -> FollowUpRecord:
        """Schedule a follow-up for a job."""
        ensure_non_empty_text("reason", reason)
        self._get_state(job_id)  # verify job exists
        follow_up_id = stable_identifier("follow-up", {
            "job_id": job_id,
            "scheduled_at": scheduled_at,
        })
        return FollowUpRecord(
            follow_up_id=follow_up_id,
            job_id=job_id,
            reason=reason,
            scheduled_at=scheduled_at,
        )

    def mutation_receipts(self, limit: int = 50) -> tuple[JobMutationReceipt, ...]:
        """Return recent job lifecycle mutation receipts in append order."""
        return tuple(self._mutation_receipts[-limit:])

    def effect_records(self, limit: int = 50) -> tuple[Any, ...]:
        """Return recent mutation receipts as execution actual-effect records."""
        return tuple(receipt.to_effect_record() for receipt in self.mutation_receipts(limit=limit))

    def _record_mutation_receipt(
        self,
        *,
        mutation_type: str,
        effect_name: str,
        job_id: str,
        previous_status: JobStatus | None,
        new_status: JobStatus,
        recorded_at: str,
        metadata: dict[str, Any],
    ) -> JobMutationReceipt:
        receipt_id = _receipt_id(
            mutation_type=mutation_type,
            job_id=job_id,
            recorded_at=recorded_at,
            ordinal=len(self._mutation_receipts),
        )
        receipt = JobMutationReceipt(
            receipt_id=receipt_id,
            mutation_type=mutation_type,
            effect_name=effect_name,
            job_id=job_id,
            evidence_ref=f"job-receipt:{receipt_id}",
            previous_status=previous_status.value if previous_status is not None else None,
            new_status=new_status.value,
            recorded_at=recorded_at,
            metadata=metadata,
        )
        self._mutation_receipts.append(receipt)
        return receipt

    # --- Overdue and stale detection ---

    def find_overdue_jobs(self, now: str) -> list[str]:
        """Return IDs of jobs past their deadline."""
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        overdue: list[str] = []
        for job_id, descriptor in self._jobs.items():
            if descriptor.deadline is None:
                continue
            state = self._states.get(job_id)
            if state is None:
                continue
            # Only check non-terminal jobs
            if state.status in (
                JobStatus.COMPLETED, JobStatus.FAILED,
                JobStatus.CANCELLED, JobStatus.ARCHIVED,
            ):
                continue
            deadline_dt = datetime.fromisoformat(
                descriptor.deadline.replace("Z", "+00:00")
            )
            if now_dt > deadline_dt:
                overdue.append(job_id)
        return overdue

    def find_stale_jobs(self, max_idle_minutes: int, now: str) -> list[str]:
        """Return IDs of jobs not updated within max_idle_minutes."""
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        threshold = timedelta(minutes=max_idle_minutes)
        stale: list[str] = []
        for job_id, state in self._states.items():
            # Only check active jobs
            if state.status in (
                JobStatus.COMPLETED, JobStatus.FAILED,
                JobStatus.CANCELLED, JobStatus.ARCHIVED,
            ):
                continue
            if state.updated_at is None:
                continue
            updated_dt = datetime.fromisoformat(
                state.updated_at.replace("Z", "+00:00")
            )
            if now_dt - updated_dt > threshold:
                stale.append(job_id)
        return stale


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_optional_text(value: str | None) -> str | None:
    return None if value is None else _sha256_text(value)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _receipt_id(*, mutation_type: str, job_id: str, recorded_at: str, ordinal: int) -> str:
    payload = json.dumps(
        {
            "mutation_type": mutation_type,
            "job_id": job_id,
            "recorded_at": recorded_at,
            "ordinal": ordinal,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"job-{mutation_type}-{digest}"
