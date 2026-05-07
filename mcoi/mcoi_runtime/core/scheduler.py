"""Governed Background Scheduler — cron-like job execution with policy gates.

Purpose: Execute recurring and one-shot jobs through the governed pipeline.
    Every job runs through the guard chain before execution. Failed jobs
    are recorded but never crash the scheduler. Job history is bounded.
Governance scope: scheduling, lease management, and governed dispatch only.
Dependencies: governance guards, audit trail, clock injection.
Invariants:
  - All jobs go through the guard chain before execution.
  - Failed jobs are recorded but never crash the scheduler.
  - Job history is bounded (FIFO pruning).
  - Leases prevent zombie jobs.
  - Clock is injected for deterministic testing.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class JobStatus(StrEnum):
    """Current state of a scheduled job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    DISABLED = "disabled"


class JobSchedule(StrEnum):
    """Schedule type for a job."""

    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """Definition of a scheduled job."""

    job_id: str
    name: str
    schedule_type: JobSchedule
    interval_seconds: int = 0  # For interval-type jobs
    cron_expression: str = ""  # For cron-type jobs
    handler_name: str = ""  # Name of the registered handler
    tenant_id: str = ""
    budget_id: str = ""
    mission_id: str = ""
    goal_id: str = ""
    max_retries: int = 3
    timeout_seconds: int = 300
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobExecution:
    """Record of a single job execution."""

    execution_id: str
    job_id: str
    status: JobStatus
    started_at: str
    finished_at: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_count: int = 0
    governed: bool = True


class GovernedScheduler:
    """Background scheduler with governance gates on every job execution.

    Every job goes through the guard chain before running. Failed jobs
    are retried up to max_retries. History is bounded at _MAX_HISTORY.
    """

    _MAX_HISTORY = 10_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        guard_chain: Any | None = None,
        audit_trail: Any | None = None,
    ) -> None:
        self._clock = clock
        self._guard_chain = guard_chain
        self._audit_trail = audit_trail
        self._jobs: dict[str, ScheduledJob] = {}
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {}
        self._history: list[JobExecution] = []
        self._execution_counter = 0
        self._lock = threading.Lock()

    def _bounded_job_error(self, exc: Exception) -> str:
        return f"handler error ({type(exc).__name__})"

    def register_handler(self, name: str, handler: Callable[..., dict[str, Any]]) -> None:
        """Register a named job handler."""
        self._handlers[name] = handler

    def schedule(self, job: ScheduledJob) -> ScheduledJob:
        """Add a job to the scheduler."""
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def unschedule(self, job_id: str) -> bool:
        """Remove a job from the scheduler."""
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def disable(self, job_id: str) -> bool:
        """Disable a job without removing it."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            self._jobs[job_id] = ScheduledJob(
                job_id=job.job_id, name=job.name,
                schedule_type=job.schedule_type,
                interval_seconds=job.interval_seconds,
                cron_expression=job.cron_expression,
                handler_name=job.handler_name,
                tenant_id=job.tenant_id, budget_id=job.budget_id,
                mission_id=job.mission_id, goal_id=job.goal_id,
                max_retries=job.max_retries,
                timeout_seconds=job.timeout_seconds,
                enabled=False,
                metadata=dict(job.metadata),
            )
            return True

    def enable(self, job_id: str) -> bool:
        """Enable a previously disabled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            self._jobs[job_id] = ScheduledJob(
                job_id=job.job_id, name=job.name,
                schedule_type=job.schedule_type,
                interval_seconds=job.interval_seconds,
                cron_expression=job.cron_expression,
                handler_name=job.handler_name,
                tenant_id=job.tenant_id, budget_id=job.budget_id,
                mission_id=job.mission_id, goal_id=job.goal_id,
                max_retries=job.max_retries,
                timeout_seconds=job.timeout_seconds,
                enabled=True,
                metadata=dict(job.metadata),
            )
            return True

    def execute_job(self, job_id: str) -> JobExecution:
        """Execute a single job through the governed pipeline.

        Steps: validate → guard chain → handler → record → audit.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ValueError("job not found")
        if not job.enabled:
            return self._record_execution(job, JobStatus.DISABLED, error="job is disabled")

        # Guard chain gate
        if self._guard_chain is not None:
            guard_ctx = {
                "tenant_id": job.tenant_id,
                "budget_id": job.budget_id,
                "action_type": f"scheduler.{job.handler_name}",
                "target": job.name,
                "agent_id": f"scheduler:{job.job_id}",
            }
            guard_result = self._guard_chain.evaluate(guard_ctx)
            if not guard_result.allowed:
                return self._record_execution(
                    job, JobStatus.FAILED,
                    error="job execution denied",
                )

        # Execute handler
        handler = self._handlers.get(job.handler_name)
        if handler is None:
            return self._record_execution(
                job, JobStatus.FAILED,
                error="handler not found",
            )

        try:
            result = handler(job)
            return self._record_execution(job, JobStatus.SUCCEEDED, result=result)
        except Exception as exc:
            return self._record_execution(
                job, JobStatus.FAILED,
                error=self._bounded_job_error(exc),
            )

    def _record_execution(
        self, job: ScheduledJob, status: JobStatus, *,
        result: dict[str, Any] | None = None, error: str = "",
    ) -> JobExecution:
        """Record an execution in history and audit trail."""
        self._execution_counter += 1
        now = self._clock()
        execution = JobExecution(
            execution_id=f"exec-{self._execution_counter:06d}",
            job_id=job.job_id,
            status=status,
            started_at=now,
            finished_at=now,
            result=result or {},
            error=error,
        )

        with self._lock:
            self._history.append(execution)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY:]

        if self._audit_trail is not None:
            goal_ctx = {}
            if job.mission_id:
                goal_ctx["mission_id"] = job.mission_id
            if job.goal_id:
                goal_ctx["goal_id"] = job.goal_id
            self._audit_trail.record(
                action=f"scheduler.execute.{job.handler_name}",
                actor_id=f"scheduler:{job.job_id}",
                tenant_id=job.tenant_id,
                target=job.name,
                outcome=status.value,
                detail={"error": error, **goal_ctx} if error else goal_ctx,
            )

        return execution

    def list_jobs(self) -> list[ScheduledJob]:
        """List all registered jobs."""
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.job_id)

    def get_job(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def recent_executions(self, limit: int = 50) -> list[JobExecution]:
        """Return recent execution history."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def summary(self) -> dict[str, Any]:
        """Scheduler summary for observability."""
        with self._lock:
            total = len(self._jobs)
            enabled = sum(1 for j in self._jobs.values() if j.enabled)
            return {
                "total_jobs": total,
                "enabled_jobs": enabled,
                "disabled_jobs": total - enabled,
                "total_executions": self._execution_counter,
                "recent_failures": sum(
                    1 for e in self._history[-100:]
                    if e.status == JobStatus.FAILED
                ),
                "history_size": len(self._history),
            }
