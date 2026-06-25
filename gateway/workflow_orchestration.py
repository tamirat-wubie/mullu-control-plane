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
_MUTATION_RECEIPTS_METADATA_KEY = "mutation_receipts"
_LIFE_MEANING_JUDGMENT_REQUIRED_METADATA_KEY = "life_meaning_judgment_required"
_LIFE_MEANING_JUDGMENT_REF_METADATA_KEY = "life_meaning_judgment_ref"


@dataclass(frozen=True, slots=True)
class WorkflowMutationReceipt:
    """Observed workflow lifecycle mutation receipt."""

    receipt_id: str
    mutation_type: str
    effect_name: str
    workflow_run_id: str
    evidence_ref: str
    previous_workflow_status: str | None
    new_workflow_status: str
    task_id: str | None = None
    previous_task_status: str | None = None
    new_task_status: str | None = None
    recorded_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mutation_type": self.mutation_type,
            "effect_name": self.effect_name,
            "workflow_run_id": self.workflow_run_id,
            "evidence_ref": self.evidence_ref,
            "previous_workflow_status": self.previous_workflow_status,
            "new_workflow_status": self.new_workflow_status,
            "task_id": self.task_id,
            "previous_task_status": self.previous_task_status,
            "new_task_status": self.new_task_status,
            "recorded_at": self.recorded_at,
            "metadata": dict(self.metadata),
        }

    def to_effect_record(self) -> Any:
        from mcoi_runtime.contracts.execution import EffectRecord

        return EffectRecord(
            name=self.effect_name,
            details={
                "effect_id": self.effect_name,
                "receipt_id": self.receipt_id,
                "mutation_type": self.mutation_type,
                "workflow_run_id": self.workflow_run_id,
                "evidence_ref": self.evidence_ref,
                "previous_workflow_status": self.previous_workflow_status,
                "new_workflow_status": self.new_workflow_status,
                "task_id": self.task_id,
                "previous_task_status": self.previous_task_status,
                "new_task_status": self.new_task_status,
                "observed_at": self.recorded_at,
                "metadata": dict(self.metadata),
                "source": "workflow_orchestrator",
            },
        )


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
        metadata_payload = dict(metadata or {})
        if _MUTATION_RECEIPTS_METADATA_KEY in metadata_payload:
            raise ValueError("workflow_metadata_reserved_mutation_receipts")
        run_id = workflow_run_id or f"workflow-run-{_hash_payload({'workflow_id': workflow_id, 'tenant_id': tenant_id, 'goal': goal})[:16]}"
        metadata_payload = _workflow_life_meaning_metadata(metadata_payload, run_id)
        task_runs = tuple(_initial_task_run(run_id, task) for task in task_tuple)
        run = _stamp_run(WorkflowRun(
            workflow_run_id=run_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            goal=goal,
            status=_derive_workflow_status(task_runs),
            tasks=task_tuple,
            task_runs=task_runs,
            metadata=metadata_payload,
        ))
        return _append_mutation_receipt(
            run,
            mutation_type="start_run",
            effect_name="workflow_run_started",
            previous_workflow_status=None,
            new_workflow_status=run.status,
            metadata={
                "workflow_id_hash": _hash_text(workflow_id),
                "tenant_id_hash": _hash_text(tenant_id),
                "actor_id_hash": _hash_text(actor_id),
                "goal_hash": _hash_text(goal),
                "task_count": len(task_tuple),
            },
        )

    def approve_task(self, run: WorkflowRun, *, task_id: str, approval_ref: str) -> WorkflowRun:
        """Attach approval evidence and move one task to approved state."""
        if not approval_ref:
            raise ValueError("approval_ref_required")
        task = _task_spec(run, task_id)
        if not task.approval_required:
            raise ValueError("task_does_not_require_approval")
        current = _task_run(run, task_id)
        next_run = _replace_task_run(
            run,
            task_id,
            lambda current: replace(current, status=TaskRunStatus.APPROVED, approval_ref=approval_ref),
        )
        updated = _task_run(next_run, task_id)
        return _append_mutation_receipt(
            next_run,
            mutation_type="approve_task",
            effect_name="workflow_task_approved",
            previous_workflow_status=run.status,
            new_workflow_status=next_run.status,
            task_id=task_id,
            previous_task_status=current.status,
            new_task_status=updated.status,
            metadata={"approval_ref_hash": _hash_text(approval_ref)},
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
        next_run = _replace_task_run(
            run,
            task_id,
            lambda current_run: replace(
                current_run,
                status=TaskRunStatus.EXECUTING,
                attempts=current_run.attempts + 1,
            ),
        )
        updated = _task_run(next_run, task_id)
        return _append_mutation_receipt(
            next_run,
            mutation_type="mark_executing",
            effect_name="workflow_task_executing",
            previous_workflow_status=run.status,
            new_workflow_status=next_run.status,
            task_id=task_id,
            previous_task_status=current.status,
            new_task_status=updated.status,
            metadata={"attempts": updated.attempts, "max_attempts": updated.max_attempts},
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
        next_run = _stamp_run(replace(next_run, status=_derive_workflow_status(next_run.task_runs)))
        updated = _task_run(next_run, task_id)
        return _append_mutation_receipt(
            next_run,
            mutation_type="commit_task",
            effect_name="workflow_task_committed",
            previous_workflow_status=run.status,
            new_workflow_status=next_run.status,
            task_id=task_id,
            previous_task_status=current.status,
            new_task_status=updated.status,
            metadata={
                "evidence_ref_hashes": tuple(_hash_text(ref) for ref in refs),
                "terminal_certificate_id_hash": _hash_optional_text(terminal_certificate_id),
            },
        )

    def fail_task(self, run: WorkflowRun, *, task_id: str, reason: str) -> WorkflowRun:
        """Record task failure and choose failed or review-required workflow state."""
        if not reason:
            raise ValueError("failure_reason_required")
        task = _task_spec(run, task_id)
        current = _task_run(run, task_id)
        next_status = TaskRunStatus.REQUIRES_REVIEW if task.compensation_task_id else TaskRunStatus.FAILED
        next_run = _replace_task_run(
            run,
            task_id,
            lambda current: replace(current, status=next_status, failure_reason=reason),
        )
        updated = _task_run(next_run, task_id)
        return _append_mutation_receipt(
            next_run,
            mutation_type="fail_task",
            effect_name="workflow_task_failed",
            previous_workflow_status=run.status,
            new_workflow_status=next_run.status,
            task_id=task_id,
            previous_task_status=current.status,
            new_task_status=updated.status,
            metadata={"failure_reason_hash": _hash_text(reason)},
        )

    def compensate_task(self, run: WorkflowRun, *, task_id: str, evidence_refs: Iterable[str]) -> WorkflowRun:
        """Close a failed task by attaching compensation evidence."""
        refs = tuple(evidence_refs)
        if not refs:
            raise ValueError("compensation_evidence_required")
        current = _task_run(run, task_id)
        if current.status not in _REVIEW_TASK_STATUSES:
            raise ValueError("task_not_compensatable")
        next_run = _replace_task_run(
            run,
            task_id,
            lambda current_run: replace(
                current_run,
                status=TaskRunStatus.COMPENSATED,
                evidence_refs=tuple(dict.fromkeys((*current_run.evidence_refs, *refs))),
            ),
        )
        updated = _task_run(next_run, task_id)
        return _append_mutation_receipt(
            next_run,
            mutation_type="compensate_task",
            effect_name="workflow_task_compensated",
            previous_workflow_status=run.status,
            new_workflow_status=next_run.status,
            task_id=task_id,
            previous_task_status=current.status,
            new_task_status=updated.status,
            metadata={"evidence_ref_hashes": tuple(_hash_text(ref) for ref in refs)},
        )


def workflow_run_to_json_dict(run: WorkflowRun) -> dict[str, Any]:
    """Return the JSON-contract representation of one workflow run."""
    return _json_ready(asdict(run))


def workflow_mutation_receipts(run: WorkflowRun, limit: int = 50) -> tuple[WorkflowMutationReceipt, ...]:
    """Return recent workflow lifecycle mutation receipts in append order."""
    receipt_payloads = run.metadata.get(_MUTATION_RECEIPTS_METADATA_KEY, ())
    if not isinstance(receipt_payloads, (tuple, list)):
        return ()
    return tuple(_workflow_receipt_from_dict(payload) for payload in receipt_payloads[-limit:])


def workflow_effect_records(run: WorkflowRun, limit: int = 50) -> tuple[Any, ...]:
    """Return recent workflow mutation receipts as execution actual-effect records."""
    return tuple(receipt.to_effect_record() for receipt in workflow_mutation_receipts(run, limit=limit))


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


def _append_mutation_receipt(
    run: WorkflowRun,
    *,
    mutation_type: str,
    effect_name: str,
    previous_workflow_status: WorkflowRunStatus | None,
    new_workflow_status: WorkflowRunStatus,
    task_id: str | None = None,
    previous_task_status: TaskRunStatus | None = None,
    new_task_status: TaskRunStatus | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowRun:
    existing = tuple(
        receipt.to_dict()
        for receipt in workflow_mutation_receipts(run, limit=10_000)
    )
    ordinal = len(existing)
    receipt_id = _workflow_receipt_id(
        workflow_run_id=run.workflow_run_id,
        mutation_type=mutation_type,
        task_id=task_id,
        ordinal=ordinal,
    )
    receipt = WorkflowMutationReceipt(
        receipt_id=receipt_id,
        mutation_type=mutation_type,
        effect_name=effect_name,
        workflow_run_id=run.workflow_run_id,
        evidence_ref=f"workflow-receipt:{receipt_id}",
        previous_workflow_status=previous_workflow_status.value if previous_workflow_status is not None else None,
        new_workflow_status=new_workflow_status.value,
        task_id=task_id,
        previous_task_status=previous_task_status.value if previous_task_status is not None else None,
        new_task_status=new_task_status.value if new_task_status is not None else None,
        recorded_at=f"workflow-mutation:{ordinal}",
        metadata={
            **(metadata or {}),
            _LIFE_MEANING_JUDGMENT_REQUIRED_METADATA_KEY: True,
            _LIFE_MEANING_JUDGMENT_REF_METADATA_KEY: _workflow_life_meaning_judgment_ref(run),
        },
    )
    next_metadata = dict(run.metadata)
    next_metadata[_MUTATION_RECEIPTS_METADATA_KEY] = (*existing, receipt.to_dict())
    return _stamp_run(replace(run, metadata=next_metadata))


def _workflow_receipt_from_dict(payload: Any) -> WorkflowMutationReceipt:
    if not isinstance(payload, dict):
        raise ValueError("workflow_mutation_receipt_invalid")
    return WorkflowMutationReceipt(
        receipt_id=str(payload["receipt_id"]),
        mutation_type=str(payload["mutation_type"]),
        effect_name=str(payload["effect_name"]),
        workflow_run_id=str(payload["workflow_run_id"]),
        evidence_ref=str(payload["evidence_ref"]),
        previous_workflow_status=(
            str(payload["previous_workflow_status"])
            if payload.get("previous_workflow_status") is not None
            else None
        ),
        new_workflow_status=str(payload["new_workflow_status"]),
        task_id=str(payload["task_id"]) if payload.get("task_id") is not None else None,
        previous_task_status=(
            str(payload["previous_task_status"])
            if payload.get("previous_task_status") is not None
            else None
        ),
        new_task_status=str(payload["new_task_status"]) if payload.get("new_task_status") is not None else None,
        recorded_at=str(payload.get("recorded_at") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


def _workflow_life_meaning_metadata(metadata: dict[str, Any], workflow_run_id: str) -> dict[str, Any]:
    next_metadata = dict(metadata)
    ref = next_metadata.get(_LIFE_MEANING_JUDGMENT_REF_METADATA_KEY)
    if not isinstance(ref, str) or not ref.strip():
        next_metadata[_LIFE_MEANING_JUDGMENT_REF_METADATA_KEY] = f"life-meaning:workflow-run:{workflow_run_id}"
    else:
        next_metadata[_LIFE_MEANING_JUDGMENT_REF_METADATA_KEY] = ref.strip()
    next_metadata[_LIFE_MEANING_JUDGMENT_REQUIRED_METADATA_KEY] = True
    return next_metadata


def _workflow_life_meaning_judgment_ref(run: WorkflowRun) -> str:
    ref = run.metadata.get(_LIFE_MEANING_JUDGMENT_REF_METADATA_KEY)
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    return f"life-meaning:workflow-run:{run.workflow_run_id}"


def _workflow_receipt_id(
    *,
    workflow_run_id: str,
    mutation_type: str,
    task_id: str | None,
    ordinal: int,
) -> str:
    digest = _hash_payload(
        {
            "workflow_run_id": workflow_run_id,
            "mutation_type": mutation_type,
            "task_id": task_id,
            "ordinal": ordinal,
        }
    )[:16]
    return f"workflow-{mutation_type}-{digest}"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_optional_text(value: str | None) -> str | None:
    return None if not value else _hash_text(value)


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
