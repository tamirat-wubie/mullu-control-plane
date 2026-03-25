"""Purpose: function runtime engine — registry, SLA evaluation, outcome tracking, and playbooks.
Governance scope: service function lifecycle, queue routing, SLA enforcement, metrics aggregation, playbook binding.
Dependencies: function contracts, job contracts, invariant helpers.
Invariants:
  - Function registration rejects duplicate IDs.
  - Only active functions accept new jobs.
  - Retired functions reject job submissions.
  - SLA evaluation is deterministic given the same clock.
  - Metrics aggregation is pure (no side effects).
  - Clock function is injected for testability.
  - No network logic; all operations are in-memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from mcoi_runtime.contracts.function import (
    CommunicationStyle,
    FunctionMetricsSnapshot,
    FunctionOutcomeRecord,
    FunctionPolicyBinding,
    FunctionQueueProfile,
    FunctionSlaProfile,
    FunctionStatus,
    FunctionType,
    ServiceFunctionTemplate,
)
from mcoi_runtime.contracts.job import (
    DeadlineRecord,
    JobDescriptor,
    JobPriority,
    SlaStatus,
    WorkQueueEntry,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class FunctionRegistry:
    """In-memory registry for service functions, policy bindings, SLA profiles, and queue profiles.

    Rules:
    - Duplicate IDs on registration are rejected.
    - Lookups return None for missing records.
    - activate_function transitions a function to ACTIVE status.
    - retire_function transitions a function to RETIRED status.
    - list_active_functions returns only functions with ACTIVE status.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._functions: dict[str, ServiceFunctionTemplate] = {}
        self._statuses: dict[str, FunctionStatus] = {}
        self._policy_bindings: dict[str, FunctionPolicyBinding] = {}
        self._sla_profiles: dict[str, FunctionSlaProfile] = {}
        self._queue_profiles: dict[str, FunctionQueueProfile] = {}

    # --- Function templates ---

    def register_function(self, template: ServiceFunctionTemplate) -> ServiceFunctionTemplate:
        """Register a service function template. Rejects duplicate function_id."""
        if template.function_id in self._functions:
            raise RuntimeCoreInvariantError(
                f"function already registered: {template.function_id}"
            )
        self._functions[template.function_id] = template
        self._statuses[template.function_id] = FunctionStatus.DRAFT
        return template

    def get_function(self, function_id: str) -> ServiceFunctionTemplate | None:
        """Return function template or None if not found."""
        return self._functions.get(function_id)

    def get_function_status(self, function_id: str) -> FunctionStatus | None:
        """Return current function status or None if not found."""
        return self._statuses.get(function_id)

    def list_active_functions(self) -> list[ServiceFunctionTemplate]:
        """Return all functions with ACTIVE status."""
        return [
            self._functions[fid]
            for fid, status in self._statuses.items()
            if status == FunctionStatus.ACTIVE
        ]

    def activate_function(self, function_id: str) -> FunctionStatus:
        """Transition a function to ACTIVE status."""
        ensure_non_empty_text("function_id", function_id)
        if function_id not in self._functions:
            raise RuntimeCoreInvariantError(f"function not found: {function_id}")
        current = self._statuses[function_id]
        if current == FunctionStatus.RETIRED:
            raise RuntimeCoreInvariantError(
                f"cannot activate a retired function: {function_id}"
            )
        self._statuses[function_id] = FunctionStatus.ACTIVE
        return FunctionStatus.ACTIVE

    def pause_function(self, function_id: str) -> FunctionStatus:
        """Transition an ACTIVE function to PAUSED status."""
        ensure_non_empty_text("function_id", function_id)
        if function_id not in self._functions:
            raise RuntimeCoreInvariantError(f"function not found: {function_id}")
        current = self._statuses[function_id]
        if current != FunctionStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"can only pause an active function, current: {current.value}"
            )
        self._statuses[function_id] = FunctionStatus.PAUSED
        return FunctionStatus.PAUSED

    def retire_function(self, function_id: str) -> FunctionStatus:
        """Transition a function to RETIRED status."""
        ensure_non_empty_text("function_id", function_id)
        if function_id not in self._functions:
            raise RuntimeCoreInvariantError(f"function not found: {function_id}")
        self._statuses[function_id] = FunctionStatus.RETIRED
        return FunctionStatus.RETIRED

    # --- Policy bindings ---

    def register_policy_binding(self, binding: FunctionPolicyBinding) -> FunctionPolicyBinding:
        """Register a policy binding. Rejects duplicate binding_id."""
        if binding.binding_id in self._policy_bindings:
            raise RuntimeCoreInvariantError(
                f"policy binding already registered: {binding.binding_id}"
            )
        self._policy_bindings[binding.binding_id] = binding
        return binding

    def get_policy_binding(self, binding_id: str) -> FunctionPolicyBinding | None:
        """Return policy binding or None if not found."""
        return self._policy_bindings.get(binding_id)

    def get_bindings_for_function(self, function_id: str) -> list[FunctionPolicyBinding]:
        """Return all policy bindings for a given function."""
        return [
            b for b in self._policy_bindings.values()
            if b.function_id == function_id
        ]

    # --- SLA profiles ---

    def register_sla_profile(self, profile: FunctionSlaProfile) -> FunctionSlaProfile:
        """Register an SLA profile. Keyed by function_id. Rejects duplicate function_id."""
        if profile.function_id in self._sla_profiles:
            raise RuntimeCoreInvariantError(
                f"SLA profile already registered for function: {profile.function_id}"
            )
        self._sla_profiles[profile.function_id] = profile
        return profile

    def get_sla_profile(self, function_id: str) -> FunctionSlaProfile | None:
        """Return SLA profile for a function or None if not found."""
        return self._sla_profiles.get(function_id)

    def get_sla_for_function(self, function_id: str) -> FunctionSlaProfile | None:
        """Return the SLA profile bound to a function, or None."""
        return self._sla_profiles.get(function_id)

    # --- Queue profiles ---

    def register_queue_profile(self, profile: FunctionQueueProfile) -> FunctionQueueProfile:
        """Register a queue profile. Keyed by function_id. Rejects duplicate function_id."""
        if profile.function_id in self._queue_profiles:
            raise RuntimeCoreInvariantError(
                f"queue profile already registered for function: {profile.function_id}"
            )
        self._queue_profiles[profile.function_id] = profile
        return profile

    def get_queue_profile(self, function_id: str) -> FunctionQueueProfile | None:
        """Return queue profile for a function or None if not found."""
        return self._queue_profiles.get(function_id)

    def get_queue_for_function(self, function_id: str) -> FunctionQueueProfile | None:
        """Return the queue profile bound to a function, or None."""
        return self._queue_profiles.get(function_id)


class FunctionEngine:
    """Manages job submission to functions, SLA evaluation, outcome recording, and metrics.

    All timestamps are produced by the injected clock function for determinism.
    """

    def __init__(self, *, registry: FunctionRegistry, clock: Callable[[], str]) -> None:
        self._registry = registry
        self._clock = clock

    # --- Job submission ---

    def submit_job_to_function(
        self,
        function_id: str,
        job_descriptor: JobDescriptor,
    ) -> WorkQueueEntry:
        """Submit a job to a service function's queue.

        Validates:
        - Function exists and is ACTIVE.
        - Queue profile team_id is used for team assignment if present.

        Returns a WorkQueueEntry representing the enqueued job.
        Raises RuntimeCoreInvariantError if function is not active.
        """
        ensure_non_empty_text("function_id", function_id)
        template = self._registry.get_function(function_id)
        if template is None:
            raise RuntimeCoreInvariantError(f"function not found: {function_id}")

        status = self._registry.get_function_status(function_id)
        if status != FunctionStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                f"function is not active (status={status.value if status else 'unknown'}): {function_id}"
            )

        now = self._clock()
        entry_id = stable_identifier("fn-wq-entry", {
            "function_id": function_id,
            "job_id": job_descriptor.job_id,
            "enqueued_at": now,
        })

        # Check for queue profile to determine team assignment
        queue_profile = self._registry.get_queue_for_function(function_id)
        assigned_team = queue_profile.team_id if queue_profile else None

        entry = WorkQueueEntry(
            entry_id=entry_id,
            job_id=job_descriptor.job_id,
            priority=job_descriptor.priority,
            enqueued_at=now,
            assigned_to_team_id=assigned_team,
        )
        return entry

    # --- SLA evaluation ---

    def evaluate_function_sla(
        self,
        function_id: str,
        jobs: list[tuple[JobDescriptor, str]],
        now: str,
    ) -> list[DeadlineRecord]:
        """Evaluate SLA for all active jobs against a function's SLA profile.

        Args:
            function_id: The function whose SLA profile to use.
            jobs: List of (job_descriptor, job_created_at) tuples to evaluate.
            now: Current time as ISO string for deterministic evaluation.

        Returns a list of DeadlineRecord, one per job.
        """
        ensure_non_empty_text("function_id", function_id)
        sla_profile = self._registry.get_sla_for_function(function_id)

        records: list[DeadlineRecord] = []
        for job_desc, created_at in jobs:
            if sla_profile is None:
                records.append(DeadlineRecord(
                    job_id=job_desc.job_id,
                    deadline=job_desc.deadline or created_at,
                    sla_status=SlaStatus.NOT_APPLICABLE,
                    evaluated_at=now,
                ))
                continue

            target_minutes = sla_profile.target_completion_minutes
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
            elapsed = now_dt - created_dt
            target = timedelta(minutes=target_minutes)

            if target.total_seconds() == 0:
                sla_status = SlaStatus.BREACHED
            elif elapsed > target:
                sla_status = SlaStatus.BREACHED
            elif elapsed >= target * 0.8:
                sla_status = SlaStatus.AT_RISK
            else:
                sla_status = SlaStatus.ON_TRACK

            deadline_str = job_desc.deadline or created_at
            records.append(DeadlineRecord(
                job_id=job_desc.job_id,
                deadline=deadline_str,
                sla_status=sla_status,
                evaluated_at=now,
                sla_target_minutes=target_minutes,
            ))

        return records

    # --- Outcome recording ---

    def record_outcome(
        self,
        function_id: str,
        job_id: str,
        *,
        completed: bool,
        completion_minutes: int,
        escalated: bool = False,
        drift_detected: bool = False,
    ) -> FunctionOutcomeRecord:
        """Record the outcome of a job processed through a function.

        Returns a FunctionOutcomeRecord capturing the result.
        """
        ensure_non_empty_text("function_id", function_id)
        ensure_non_empty_text("job_id", job_id)
        now = self._clock()
        outcome_id = stable_identifier("fn-outcome", {
            "function_id": function_id,
            "job_id": job_id,
            "recorded_at": now,
        })
        return FunctionOutcomeRecord(
            outcome_id=outcome_id,
            function_id=function_id,
            job_id=job_id,
            completed=completed,
            completion_minutes=completion_minutes,
            escalated=escalated,
            drift_detected=drift_detected,
            recorded_at=now,
        )

    # --- Metrics computation ---

    def compute_metrics(
        self,
        function_id: str,
        outcomes: list[FunctionOutcomeRecord],
        period_start: str,
        period_end: str,
    ) -> FunctionMetricsSnapshot:
        """Aggregate outcomes into a metrics snapshot for a function over a period.

        Computes:
        - total_jobs: number of outcomes in the period.
        - completed_jobs: outcomes where completed=True.
        - failed_jobs: outcomes where completed=False.
        - avg_completion_minutes: average of completion_minutes for completed jobs (0.0 if none).
        - escalation_count: outcomes where escalated=True.
        - drift_count: outcomes where drift_detected=True.
        """
        ensure_non_empty_text("function_id", function_id)
        now = self._clock()

        # Filter outcomes within the period
        period_start_dt = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
        period_end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))

        in_period: list[FunctionOutcomeRecord] = []
        for outcome in outcomes:
            recorded_dt = datetime.fromisoformat(outcome.recorded_at.replace("Z", "+00:00"))
            if period_start_dt <= recorded_dt <= period_end_dt:
                in_period.append(outcome)

        total_jobs = len(in_period)
        completed_outcomes = [o for o in in_period if o.completed]
        completed_jobs = len(completed_outcomes)
        failed_jobs = total_jobs - completed_jobs

        if completed_outcomes:
            avg_completion_minutes = sum(
                o.completion_minutes for o in completed_outcomes
            ) / completed_jobs
        else:
            avg_completion_minutes = 0.0

        escalation_count = sum(1 for o in in_period if o.escalated)
        drift_count = sum(1 for o in in_period if o.drift_detected)

        return FunctionMetricsSnapshot(
            function_id=function_id,
            period_start=period_start,
            period_end=period_end,
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            avg_completion_minutes=avg_completion_minutes,
            escalation_count=escalation_count,
            drift_count=drift_count,
            captured_at=now,
        )


# --- Playbook ---


@dataclass(frozen=True, slots=True)
class PlaybookDescriptor:
    """Binds a function template to a workflow/skill sequence.

    Fields:
    - playbook_id: unique identifier.
    - function_id: the service function this playbook executes.
    - name: human-readable name.
    - workflow_id: optional workflow to invoke.
    - skill_ids: tuple of skill IDs to invoke in order.
    - description: what the playbook does.
    """

    playbook_id: str
    function_id: str
    name: str
    workflow_id: str | None = None
    skill_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        ensure_non_empty_text("playbook_id", self.playbook_id)
        ensure_non_empty_text("function_id", self.function_id)
        ensure_non_empty_text("name", self.name)
        if self.workflow_id is None and not self.skill_ids:
            raise ValueError("playbook must have at least workflow_id or non-empty skill_ids")


class FunctionPlaybook:
    """Container that binds function templates to workflow/skill sequences.

    Rules:
    - Duplicate playbook IDs are rejected.
    - Lookups return None for missing playbooks.
    - execute_playbook returns the descriptor (actual execution delegates to skill/workflow runtime).
    """

    def __init__(self) -> None:
        self._playbooks: dict[str, PlaybookDescriptor] = {}

    def register_playbook(self, descriptor: PlaybookDescriptor) -> PlaybookDescriptor:
        """Register a playbook. Rejects duplicate playbook_id."""
        if descriptor.playbook_id in self._playbooks:
            raise RuntimeCoreInvariantError(
                f"playbook already registered: {descriptor.playbook_id}"
            )
        self._playbooks[descriptor.playbook_id] = descriptor
        return descriptor

    def get_playbook(self, playbook_id: str) -> PlaybookDescriptor | None:
        """Return playbook descriptor or None if not found."""
        return self._playbooks.get(playbook_id)

    def list_playbooks_for_function(self, function_id: str) -> list[PlaybookDescriptor]:
        """Return all playbooks bound to a given function."""
        return [
            p for p in self._playbooks.values()
            if p.function_id == function_id
        ]

    def execute_playbook(self, playbook_id: str, job_id: str) -> PlaybookDescriptor:
        """Execute a playbook for a job.

        Currently returns the descriptor. Actual execution delegates to
        the existing skill/workflow runtime.

        Raises RuntimeCoreInvariantError if playbook not found.
        """
        ensure_non_empty_text("playbook_id", playbook_id)
        ensure_non_empty_text("job_id", job_id)
        descriptor = self._playbooks.get(playbook_id)
        if descriptor is None:
            raise RuntimeCoreInvariantError(f"playbook not found: {playbook_id}")
        return descriptor
