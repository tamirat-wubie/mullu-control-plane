"""Purpose: cross-plane workflow runtime — validation and execution orchestration.
Governance scope: workflow validation, topological ordering, and stage-by-stage execution.
Dependencies: workflow contracts, core invariant helpers.
Invariants:
  - Workflow descriptors are validated before execution (no cycles, valid references).
  - Execution stops on first failed stage (governed early-stop).
  - Stage execution order is determined by topological sort for determinism.
  - Clock injection ensures deterministic timestamps for replay.
"""

from __future__ import annotations

from typing import Callable, Mapping, Protocol, Any

from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStatus,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


class StageExecutor(Protocol):
    """Protocol for executing a single workflow stage.

    Implementations provide the actual execution logic for different stage types.
    """

    def execute_stage(
        self,
        stage_id: str,
        stage_type: str,
        skill_id: str | None,
        inputs: Mapping[str, Any],
    ) -> StageExecutionResult: ...


class WorkflowValidator:
    """Validates a WorkflowDescriptor for structural correctness.

    Checks:
    - No cycles in the stage predecessor graph.
    - All predecessor references point to existing stages.
    - All binding source/target stage IDs reference existing stages.
    """

    def validate(self, descriptor: WorkflowDescriptor) -> list[str]:
        """Return a list of validation error strings. Empty list means valid."""
        errors: list[str] = []
        stage_ids = {stage.stage_id for stage in descriptor.stages}

        # Check predecessor references
        for stage in descriptor.stages:
            for pred in stage.predecessors:
                if pred not in stage_ids:
                    errors.append(
                        f"stage '{stage.stage_id}' references unknown predecessor '{pred}'"
                    )

        # Check binding references
        for binding in descriptor.bindings:
            if binding.source_stage_id not in stage_ids:
                errors.append(
                    f"binding '{binding.binding_id}' references unknown source stage '{binding.source_stage_id}'"
                )
            if binding.target_stage_id not in stage_ids:
                errors.append(
                    f"binding '{binding.binding_id}' references unknown target stage '{binding.target_stage_id}'"
                )

        # Check for cycles via topological sort (Kahn's algorithm)
        if not errors:
            cycle_error = self._detect_cycle(descriptor)
            if cycle_error:
                errors.append(cycle_error)

        return errors

    def _detect_cycle(self, descriptor: WorkflowDescriptor) -> str | None:
        """Return an error message if the stage graph contains a cycle, else None."""
        in_degree: dict[str, int] = {s.stage_id: 0 for s in descriptor.stages}
        dependents: dict[str, list[str]] = {s.stage_id: [] for s in descriptor.stages}

        for stage in descriptor.stages:
            for pred in stage.predecessors:
                in_degree[stage.stage_id] += 1
                dependents[pred].append(stage.stage_id)

        queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            current = queue.pop(0)
            visited_count += 1
            for dep in sorted(dependents[current]):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
                    queue.sort()

        if visited_count != len(descriptor.stages):
            return "cycle detected in stage predecessor graph"
        return None


class WorkflowEngine:
    """Orchestrates workflow execution: validate, start, execute stages, suspend.

    Uses topological sort to determine stage execution order.
    Stops on first failed stage (governed early-stop).
    Takes a clock function for deterministic timestamps.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._validator = WorkflowValidator()

    def validate_workflow(self, descriptor: WorkflowDescriptor) -> list[str]:
        """Validate a workflow descriptor. Returns list of error strings."""
        return self._validator.validate(descriptor)

    def start_workflow(
        self,
        descriptor: WorkflowDescriptor,
        context: Mapping[str, Any] | None = None,
    ) -> WorkflowExecutionRecord:
        """Validate and start a workflow. Returns initial execution record.

        Raises RuntimeCoreInvariantError if the descriptor is invalid.
        """
        errors = self.validate_workflow(descriptor)
        if errors:
            raise RuntimeCoreInvariantError(
                f"workflow validation failed: {'; '.join(errors)}"
            )

        execution_id = stable_identifier("wf-exec", {
            "workflow_id": descriptor.workflow_id,
            "started_at": self._clock(),
        })

        return WorkflowExecutionRecord(
            workflow_id=descriptor.workflow_id,
            execution_id=execution_id,
            status=WorkflowStatus.RUNNING,
            stage_results=(),
            started_at=self._clock(),
        )

    def execute_next_stage(
        self,
        descriptor: WorkflowDescriptor,
        record: WorkflowExecutionRecord,
        stage_executor: StageExecutor,
        context: Mapping[str, Any] | None = None,
    ) -> WorkflowExecutionRecord:
        """Execute the next eligible stage and return an updated record.

        Determines execution order via topological sort, skips already-completed
        stages, and stops on first failure.
        """
        if record.status is not WorkflowStatus.RUNNING:
            return record

        execution_order = self._topological_sort(descriptor)
        completed_ids = {r.stage_id for r in record.stage_results}
        failed_ids = {
            r.stage_id for r in record.stage_results
            if r.status is StageStatus.FAILED
        }

        # If any stage has failed, the workflow is already failed
        if failed_ids:
            return WorkflowExecutionRecord(
                workflow_id=record.workflow_id,
                execution_id=record.execution_id,
                status=WorkflowStatus.FAILED,
                stage_results=record.stage_results,
                started_at=record.started_at,
                completed_at=self._clock(),
            )

        # Find next eligible stage
        for stage in execution_order:
            if stage.stage_id in completed_ids:
                continue
            # Check all predecessors are completed
            preds_met = all(p in completed_ids for p in stage.predecessors)
            if not preds_met:
                continue

            # Execute this stage
            inputs = dict(context) if context else {}
            # Collect outputs from predecessor stages
            for result in record.stage_results:
                for key, value in result.output.items():
                    inputs[f"{result.stage_id}.{key}"] = value

            result = stage_executor.execute_stage(
                stage_id=stage.stage_id,
                stage_type=stage.stage_type.value,
                skill_id=stage.skill_id,
                inputs=inputs,
            )

            new_results = record.stage_results + (result,)

            if result.status is StageStatus.FAILED:
                return WorkflowExecutionRecord(
                    workflow_id=record.workflow_id,
                    execution_id=record.execution_id,
                    status=WorkflowStatus.FAILED,
                    stage_results=new_results,
                    started_at=record.started_at,
                    completed_at=self._clock(),
                )

            # Check if all stages are now completed
            new_completed = {r.stage_id for r in new_results}
            all_stage_ids = {s.stage_id for s in descriptor.stages}
            if new_completed == all_stage_ids:
                return WorkflowExecutionRecord(
                    workflow_id=record.workflow_id,
                    execution_id=record.execution_id,
                    status=WorkflowStatus.COMPLETED,
                    stage_results=new_results,
                    started_at=record.started_at,
                    completed_at=self._clock(),
                )

            return WorkflowExecutionRecord(
                workflow_id=record.workflow_id,
                execution_id=record.execution_id,
                status=WorkflowStatus.RUNNING,
                stage_results=new_results,
                started_at=record.started_at,
            )

        # No eligible stage found — all done or stuck
        all_stage_ids = {s.stage_id for s in descriptor.stages}
        if completed_ids == all_stage_ids:
            return WorkflowExecutionRecord(
                workflow_id=record.workflow_id,
                execution_id=record.execution_id,
                status=WorkflowStatus.COMPLETED,
                stage_results=record.stage_results,
                started_at=record.started_at,
                completed_at=self._clock(),
            )

        return record

    def suspend_workflow(
        self,
        record: WorkflowExecutionRecord,
        reason: str,
    ) -> WorkflowExecutionRecord:
        """Suspend a running workflow. Preserves partial results."""
        if record.status is not WorkflowStatus.RUNNING:
            raise RuntimeCoreInvariantError(
                f"cannot suspend workflow in status {record.status.value}"
            )

        return WorkflowExecutionRecord(
            workflow_id=record.workflow_id,
            execution_id=record.execution_id,
            status=WorkflowStatus.SUSPENDED,
            stage_results=record.stage_results,
            started_at=record.started_at,
            completed_at=self._clock(),
        )

    def _topological_sort(self, descriptor: WorkflowDescriptor) -> list:
        """Sort stages by predecessor order (Kahn's algorithm). Deterministic via sorted queues."""
        stage_map = {s.stage_id: s for s in descriptor.stages}
        in_degree: dict[str, int] = {s.stage_id: 0 for s in descriptor.stages}
        dependents: dict[str, list[str]] = {s.stage_id: [] for s in descriptor.stages}

        for stage in descriptor.stages:
            for pred in stage.predecessors:
                in_degree[stage.stage_id] += 1
                dependents[pred].append(stage.stage_id)

        queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])
        result: list = []

        while queue:
            current = queue.pop(0)
            result.append(stage_map[current])
            for dep in sorted(dependents[current]):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
                    queue.sort()

        return result
