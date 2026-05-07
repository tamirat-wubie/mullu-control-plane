"""Gateway capability plan executor.

Purpose: Execute validated capability plans by delegating each step to the
    governed command execution path supplied by the caller.
Governance scope: dependency ordering, step result capture, failure stop, and
    plan-level proof summary.
Dependencies: gateway capability plan contracts.
Invariants:
  - A step cannot execute before all dependencies have succeeded.
  - Resume checkpoints must match declared plan steps and dependency order.
  - Resume checkpoints require terminal certificates before skipping work.
  - Execution halts on the first failed step.
  - Plan success requires every step to produce a terminal certificate id.
  - Step outputs are recorded by step id for reconciliation and follow-on use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from gateway.command_spine import canonical_hash
from gateway.plan import CapabilityPlan, CapabilityPlanStep


@dataclass(frozen=True, slots=True)
class CapabilityPlanStepResult:
    """Observed result of one plan step."""

    step_id: str
    capability_id: str
    succeeded: bool
    command_id: str = ""
    terminal_certificate_id: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityPlanExecutionResult:
    """Plan-level execution proof summary."""

    plan_id: str
    succeeded: bool
    step_results: tuple[CapabilityPlanStepResult, ...]
    terminal_certificate_ids: tuple[str, ...]
    evidence_hash: str
    error: str = ""


GovernedStepExecutor = Callable[[CapabilityPlanStep, dict[str, CapabilityPlanStepResult]], CapabilityPlanStepResult]


class CapabilityPlanExecutor:
    """Execute a plan through a caller-supplied governed step executor."""

    def __init__(self, execute_step: GovernedStepExecutor) -> None:
        self._execute_step = execute_step

    def execute(
        self,
        plan: CapabilityPlan,
        *,
        initial_results: tuple[CapabilityPlanStepResult, ...] = (),
    ) -> CapabilityPlanExecutionResult:
        """Execute every step in dependency order."""
        checkpoint_error = _validate_initial_results(plan, initial_results)
        if checkpoint_error:
            return _plan_result(plan.plan_id, tuple(initial_results), error=checkpoint_error)
        completed: dict[str, CapabilityPlanStepResult] = {
            result.step_id: result
            for result in initial_results
        }
        step_results: list[CapabilityPlanStepResult] = list(initial_results)
        for step in plan.steps:
            if step.step_id in completed:
                continue
            missing = [dep for dep in step.depends_on if dep not in completed or not completed[dep].succeeded]
            if missing:
                result = CapabilityPlanStepResult(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    succeeded=False,
                    error=f"dependency_not_satisfied:{missing[0]}",
                )
                step_results.append(result)
                return _plan_result(plan.plan_id, tuple(step_results), error=result.error)
            result = self._execute_step(step, dict(completed))
            step_results.append(result)
            completed[step.step_id] = result
            if not result.succeeded:
                return _plan_result(plan.plan_id, tuple(step_results), error=result.error or "step_failed")

        missing_certificates = [
            result.step_id
            for result in step_results
            if not result.terminal_certificate_id
        ]
        if missing_certificates:
            return _plan_result(
                plan.plan_id,
                tuple(step_results),
                error=f"missing_terminal_certificate:{missing_certificates[0]}",
            )
        return _plan_result(plan.plan_id, tuple(step_results), error="")


def _plan_result(
    plan_id: str,
    step_results: tuple[CapabilityPlanStepResult, ...],
    *,
    error: str,
) -> CapabilityPlanExecutionResult:
    terminal_certificate_ids = tuple(
        result.terminal_certificate_id
        for result in step_results
        if result.terminal_certificate_id
    )
    evidence_hash = canonical_hash({
        "plan_id": plan_id,
        "steps": [
            {
                "step_id": result.step_id,
                "capability_id": result.capability_id,
                "succeeded": result.succeeded,
                "command_id": result.command_id,
                "terminal_certificate_id": result.terminal_certificate_id,
                "output": result.output,
                "error": result.error,
            }
            for result in step_results
        ],
    })
    return CapabilityPlanExecutionResult(
        plan_id=plan_id,
        succeeded=not error and all(result.succeeded for result in step_results),
        step_results=step_results,
        terminal_certificate_ids=terminal_certificate_ids,
        evidence_hash=evidence_hash,
        error=error,
    )


def _validate_initial_results(
    plan: CapabilityPlan,
    initial_results: tuple[CapabilityPlanStepResult, ...],
) -> str:
    if not initial_results:
        return ""
    steps_by_id = {step.step_id: step for step in plan.steps}
    completed: set[str] = set()
    seen: set[str] = set()
    for result in initial_results:
        step = steps_by_id.get(result.step_id)
        if step is None:
            return f"checkpoint_unknown_step:{result.step_id}"
        if result.step_id in seen:
            return f"checkpoint_duplicate_step:{result.step_id}"
        seen.add(result.step_id)
        if result.capability_id != step.capability_id:
            return f"checkpoint_capability_mismatch:{result.step_id}"
        if not result.succeeded:
            return f"checkpoint_not_successful:{result.step_id}"
        if not result.terminal_certificate_id:
            return f"checkpoint_missing_terminal_certificate:{result.step_id}"
        missing = [dep for dep in step.depends_on if dep not in completed]
        if missing:
            return f"checkpoint_dependency_not_satisfied:{result.step_id}:{missing[0]}"
        completed.add(result.step_id)
    return ""
