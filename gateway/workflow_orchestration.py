"""Gateway workflow orchestration contract.

Purpose: model durable workflow runs and task runs for governed operations.
Governance scope: approval waits, side-effect verification, retry bounds,
    compensation, terminal closure evidence, and deterministic run hashing.
Dependencies: standard-library dataclasses, enum, JSON serialization, hashlib.
Invariants:
  - Workflow task graphs must be acyclic and reference existing dependencies.
  - Approval tasks cannot complete without an approval reference.
  - Verification-bound tasks cannot commit without evidence references.
  - Terminal workflow closure requires every task to be closed or compensated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable


class WorkflowTaskType(StrEnum):
    """Supported gateway-level orchestration task classes."""

    TASK = "task"
    APPROVAL_TASK = "approval_task"
    HUMAN_REVIEW_TASK = "human_review_task"
    WAIT_UNTIL = "wait_until"
    RETRY = "retry"
    COMPENSATE = "compensate"
    VERIFY_EFFECT = "verify_effect"
    CLOSE_CERTIFICATE = "close_certificate"


class TaskRunStatus(StrEnum):
    """Lifecycle state for one workflow task run."""

    CREATED = "created"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    WAITING_FOR_VERIFICATION = "waiting_for_verification"
    COMMITTED = "committed"
    COMPENSATED = "compensated"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


class WorkflowRunStatus(StrEnum):
    """Lifecycle state for one workflow run."""

    CREATED = "created"
    PLANNED = "planned"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    WAITING_FOR_VERIFICATION = "waiting_for_verification"
    COMMITTED = "committed"
    COMPENSATED = "compensated"
    ACCEPTED_RISK = "accepted_risk"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


_CLOSED_TASK_STATUSES = frozenset({TaskRunStatus.COMMITTED, TaskRunStatus.COMPENSATED})
_REVIEW_TASK_STATUSES = frozenset({TaskRunStatus.REQUIRES_REVIEW, TaskRunStatus.FAILED})


@dataclass(frozen=True, slots=True)
class WorkflowTaskSpec:
    """Static task contract inside one workflow template."""

    task_id: str
    task_type: WorkflowTaskType
    action: str
    depends_on: tuple[str, ...] = ()
    approval_required: bool = False
    verification_required: bool = False
    retry_limit: int = 1
    compensation_task_id: str = ""
    evidence_required: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id_required")
        if not isinstance(self.task_type, WorkflowTaskType):
            raise ValueError("task_type_invalid")
        if not self.action:
            raise ValueError("action_required")
        if self.retry_limit < 0:
            raise ValueError("retry_limit_non_negative")
        object.__setattr__(self, "depends_on", tuple(self.depends_on))
        object.__setattr__(self, "evidence_required", tuple(self.evidence_required))
        if self.task_type == WorkflowTaskType.APPROVAL_TASK and not self.approval_required:
            object.__setattr__(self, "approval_required", True)
        if self.task_type == WorkflowTaskType.VERIFY_EFFECT and not self.verification_required:
            object.__setattr__(self, "verification_required", True)


@dataclass(frozen=True, slots=True)
class TaskRun:
    """Runtime state for one task inside a workflow run."""

    task_run_id: str
    workflow_run_id: str
    task_id: str
    status: TaskRunStatus
    attempts: int = 0
    max_attempts: int = 1
    approval_ref: str = ""
    evidence_refs: tuple[str, ...] = ()
    terminal_certificate_id: str = ""
    failure_reason: str = ""
    task_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_run_id:
            raise ValueError("task_run_id_required")
        if not self.workflow_run_id:
            raise ValueError("workflow_run_id_required")
        if not self.task_id:
            raise ValueError("task_id_required")
        if not isinstance(self.status, TaskRunStatus):
            raise ValueError("task_status_invalid")
        if self.attempts < 0:
            raise ValueError("attempts_non_negative")
        if self.max_attempts < 0:
            raise ValueError("max_attempts_non_negative")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    """Durable gateway-level workflow run witness."""

    workflow_run_id: str
    workflow_id: str
    tenant_id: str
    actor_id: str
    goal: str
    status: WorkflowRunStatus
    tasks: tuple[WorkflowTaskSpec, ...]
    task_runs: tuple[TaskRun, ...]
    evidence_refs: tuple[str, ...] = ()
    terminal_certificate_id: str = ""
    run_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workflow_run_id:
            raise ValueError("workflow_run_id_required")
        if not self.workflow_id:
            raise ValueError("workflow_id_required")
        if not self.tenant_id:
            raise ValueError("tenant_id_required")
        if not self.actor_id:
            raise ValueError("actor_id_required")
        if not self.goal:
            raise ValueError("goal_required")
        if not isinstance(self.status, WorkflowRunStatus):
            raise ValueError("workflow_status_invalid")
        if not self.tasks:
            raise ValueError("workflow_tasks_required")
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "task_runs", tuple(self.task_runs))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        _validate_task_graph(self.tasks)
        task_ids = {task.task_id for task in self.tasks}
        run_task_ids = {task_run.task_id for task_run in self.task_runs}
        if run_task_ids != task_ids:
            raise ValueError("task_run_set_must_match_task_set")


class WorkflowOrchestrator:
    """Pure state-transition helper for governed workflow runs."""

    def start_run(
        self,
        *,
        workflow_id: str,
        tenant_id: str,
        actor_id: str,
        goal: str,
        tasks: Iterable[WorkflowTaskSpec],
        workflow_run_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Create a planned workflow run and initial task-run witnesses."""
        task_tuple = tuple(tasks)
        _validate_task_graph(task_tuple)
        run_id = workflow_run_id or f"workflow-run-{_hash_payload({'workflow_id': workflow_id, 'tenant_id': tenant_id, 'goal': goal})[:16]}"
        task_runs = tuple(_initial_task_run(run_id, task) for task in task_tuple)
        return _stamp_run(WorkflowRun(
            workflow_run_id=run_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            goal=goal,
            status=_derive_workflow_status(task_runs),
            tasks=task_tuple,
            task_runs=task_runs,
            metadata=metadata or {},
        ))

    def approve_task(self, run: WorkflowRun, *, task_id: str, approval_ref: str) -> WorkflowRun:
        """Attach approval evidence and move one task to approved state."""
        if not approval_ref:
            raise ValueError("approval_ref_required")
        task = _task_spec(run, task_id)
        if not task.approval_required:
            raise ValueError("task_does_not_require_approval")
        return _replace_task_run(
            run,
            task_id,
            lambda current: replace(current, status=TaskRunStatus.APPROVED, approval_ref=approval_ref),
        )

    def mark_executing(self, run: WorkflowRun, *, task_id: str) -> WorkflowRun:
        """Move a ready task into executing state."""
        task = _task_spec(run, task_id)
        _require_dependencies_closed(run, task)
        current = _task_run(run, task_id)
        if current.status not in {TaskRunStatus.CREATED, TaskRunStatus.APPROVED, TaskRunStatus.WAITING_FOR_VERIFICATION}:
            raise ValueError("task_not_ready_to_execute")
        if current.attempts >= current.max_attempts:
            raise ValueError("retry_limit_exhausted")
        return _replace_task_run(
            run,
            task_id,
            lambda current_run: replace(
                current_run,
                status=TaskRunStatus.EXECUTING,
                attempts=current_run.attempts + 1,
            ),
        )

    def commit_task(
        self,
        run: WorkflowRun,
        *,
        task_id: str,
        evidence_refs: Iterable[str] = (),
        terminal_certificate_id: str = "",
    ) -> WorkflowRun:
        """Commit a task after approval and verification constraints pass."""
        task = _task_spec(run, task_id)
        current = _task_run(run, task_id)
        refs = tuple(evidence_refs)
        if task.approval_required and not current.approval_ref:
            raise ValueError("approval_ref_required_before_commit")
        if task.verification_required and not refs:
            raise ValueError("verification_evidence_required_before_commit")
        if task.task_type == WorkflowTaskType.CLOSE_CERTIFICATE and not terminal_certificate_id:
            raise ValueError("terminal_certificate_required_before_closure")
        missing_evidence = tuple(ref for ref in task.evidence_required if ref not in refs)
        if missing_evidence:
            raise ValueError(f"required_evidence_missing:{','.join(missing_evidence)}")
        next_run = _replace_task_run(
            run,
            task_id,
            lambda current_run: replace(
                current_run,
                status=TaskRunStatus.COMMITTED,
                evidence_refs=tuple(dict.fromkeys((*current_run.evidence_refs, *refs))),
                terminal_certificate_id=terminal_certificate_id or current_run.terminal_certificate_id,
            ),
        )
        if task.task_type == WorkflowTaskType.CLOSE_CERTIFICATE and terminal_certificate_id:
            next_run = replace(next_run, terminal_certificate_id=terminal_certificate_id)
        return _stamp_run(replace(next_run, status=_derive_workflow_status(next_run.task_runs)))

    def fail_task(self, run: WorkflowRun, *, task_id: str, reason: str) -> WorkflowRun:
        """Record task failure and choose failed or review-required workflow state."""
        if not reason:
            raise ValueError("failure_reason_required")
        task = _task_spec(run, task_id)
        next_status = TaskRunStatus.REQUIRES_REVIEW if task.compensation_task_id else TaskRunStatus.FAILED
        return _replace_task_run(
            run,
            task_id,
            lambda current: replace(current, status=next_status, failure_reason=reason),
        )

    def compensate_task(self, run: WorkflowRun, *, task_id: str, evidence_refs: Iterable[str]) -> WorkflowRun:
        """Close a failed task by attaching compensation evidence."""
        refs = tuple(evidence_refs)
        if not refs:
            raise ValueError("compensation_evidence_required")
        current = _task_run(run, task_id)
        if current.status not in _REVIEW_TASK_STATUSES:
            raise ValueError("task_not_compensatable")
        return _replace_task_run(
            run,
            task_id,
            lambda current_run: replace(
                current_run,
                status=TaskRunStatus.COMPENSATED,
                evidence_refs=tuple(dict.fromkeys((*current_run.evidence_refs, *refs))),
            ),
        )


def workflow_run_to_json_dict(run: WorkflowRun) -> dict[str, Any]:
    """Return the JSON-contract representation of one workflow run."""
    return _json_ready(asdict(run))


def _initial_task_run(workflow_run_id: str, task: WorkflowTaskSpec) -> TaskRun:
    status = TaskRunStatus.WAITING_FOR_APPROVAL if task.approval_required else TaskRunStatus.CREATED
    return _stamp_task_run(TaskRun(
        task_run_id=f"task-run-{_hash_payload({'workflow_run_id': workflow_run_id, 'task_id': task.task_id})[:16]}",
        workflow_run_id=workflow_run_id,
        task_id=task.task_id,
        status=status,
        max_attempts=task.retry_limit,
    ))


def _replace_task_run(run: WorkflowRun, task_id: str, updater: Any) -> WorkflowRun:
    task_runs = tuple(
        _stamp_task_run(updater(task_run)) if task_run.task_id == task_id else task_run
        for task_run in run.task_runs
    )
    if all(task_run.task_id != task_id for task_run in run.task_runs):
        raise KeyError(f"unknown task_id: {task_id}")
    next_run = replace(run, task_runs=task_runs, status=_derive_workflow_status(task_runs))
    return _stamp_run(next_run)


def _derive_workflow_status(task_runs: tuple[TaskRun, ...]) -> WorkflowRunStatus:
    statuses = {task_run.status for task_run in task_runs}
    if statuses <= {TaskRunStatus.COMMITTED}:
        return WorkflowRunStatus.COMMITTED
    if statuses <= _CLOSED_TASK_STATUSES and TaskRunStatus.COMPENSATED in statuses:
        return WorkflowRunStatus.COMPENSATED
    if TaskRunStatus.FAILED in statuses:
        return WorkflowRunStatus.FAILED
    if TaskRunStatus.REQUIRES_REVIEW in statuses:
        return WorkflowRunStatus.REQUIRES_REVIEW
    if TaskRunStatus.WAITING_FOR_VERIFICATION in statuses:
        return WorkflowRunStatus.WAITING_FOR_VERIFICATION
    if TaskRunStatus.EXECUTING in statuses:
        return WorkflowRunStatus.EXECUTING
    if TaskRunStatus.WAITING_FOR_APPROVAL in statuses:
        return WorkflowRunStatus.WAITING_FOR_APPROVAL
    if TaskRunStatus.APPROVED in statuses:
        return WorkflowRunStatus.APPROVED
    return WorkflowRunStatus.PLANNED


def _validate_task_graph(tasks: tuple[WorkflowTaskSpec, ...]) -> None:
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate_task_id")
    known = set(task_ids)
    for task in tasks:
        missing = tuple(dep for dep in task.depends_on if dep not in known)
        if missing:
            raise ValueError(f"missing_task_dependency:{','.join(missing)}")
        if task.compensation_task_id and task.compensation_task_id not in known:
            raise ValueError(f"missing_compensation_task:{task.compensation_task_id}")
    visiting: set[str] = set()
    visited: set[str] = set()
    adjacency = {task.task_id: task.depends_on for task in tasks}
    for task_id in task_ids:
        _visit_task_graph(task_id, adjacency, visiting, visited)


def _visit_task_graph(
    task_id: str,
    adjacency: dict[str, tuple[str, ...]],
    visiting: set[str],
    visited: set[str],
) -> None:
    if task_id in visited:
        return
    if task_id in visiting:
        raise ValueError("workflow_dependency_cycle")
    visiting.add(task_id)
    for dependency_id in adjacency[task_id]:
        _visit_task_graph(dependency_id, adjacency, visiting, visited)
    visiting.remove(task_id)
    visited.add(task_id)


def _require_dependencies_closed(run: WorkflowRun, task: WorkflowTaskSpec) -> None:
    by_task_id = {task_run.task_id: task_run for task_run in run.task_runs}
    open_dependencies = tuple(
        dependency_id
        for dependency_id in task.depends_on
        if by_task_id[dependency_id].status not in _CLOSED_TASK_STATUSES
    )
    if open_dependencies:
        raise ValueError(f"task_dependencies_open:{','.join(open_dependencies)}")


def _task_spec(run: WorkflowRun, task_id: str) -> WorkflowTaskSpec:
    for task in run.tasks:
        if task.task_id == task_id:
            return task
    raise KeyError(f"unknown task_id: {task_id}")


def _task_run(run: WorkflowRun, task_id: str) -> TaskRun:
    for task_run in run.task_runs:
        if task_run.task_id == task_id:
            return task_run
    raise KeyError(f"unknown task_id: {task_id}")


def _stamp_task_run(task_run: TaskRun) -> TaskRun:
    return replace(task_run, task_hash=_hash_payload(_json_ready(asdict(replace(task_run, task_hash="")))))


def _stamp_run(run: WorkflowRun) -> WorkflowRun:
    return replace(run, run_hash=_hash_payload(_json_ready(asdict(replace(run, run_hash="")))))


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value
