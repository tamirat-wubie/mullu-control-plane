"""Purpose: provide governed helper executors for skill, workflow, and goal entry paths.
Governance scope: adapter dispatch helpers only.
Dependencies: operator models, dispatcher, template validator, workflow store, and runtime autonomy.
Invariants: execution stays fail-closed, uses governed entry paths only, and never bypasses validation.
"""

from __future__ import annotations

from typing import Any, Mapping, TYPE_CHECKING

from mcoi_runtime.adapters.executor_base import ExecutionAdapterError
from mcoi_runtime.contracts.autonomy import ActionClass, AutonomyDecisionStatus
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.goal import SubGoal, SubGoalStatus
from mcoi_runtime.contracts.skill import SkillOutcomeStatus, SkillStepOutcome
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    WorkflowStatus,
)
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.errors import Recoverability, execution_error
from mcoi_runtime.app.governed_execution import governed_operator_dispatch
from mcoi_runtime.core.template_validator import TemplateValidationError
from mcoi_runtime.core.template_validator import format_template_validation_error
from mcoi_runtime.persistence.errors import PersistenceError

from .operator_models import SkillRequest

if TYPE_CHECKING:
    from .bootstrap import BootstrappedRuntime
    from .operator_loop import OperatorLoop


class _GovernedStepExecutor:
    """Step executor that dispatches through the governed runtime path."""

    def __init__(self, *, runtime: BootstrappedRuntime) -> None:
        self._runtime = runtime

    def execute_step(
        self,
        step_id: str,
        action_type: str,
        input_bindings: Mapping[str, Any],
    ) -> SkillStepOutcome:
        """Execute one skill step through the dispatcher."""
        template = {"action_type": action_type, **{k: v for k, v in input_bindings.items()}}
        bindings = {k: str(v) for k, v in input_bindings.items() if isinstance(v, str)}

        try:
            self._runtime.template_validator.validate(template, bindings)
        except TemplateValidationError as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"validation:{format_template_validation_error(exc)}",
            )

        try:
            if hasattr(self._runtime, 'governed_dispatcher') and self._runtime.governed_dispatcher is not None:
                result = governed_operator_dispatch(
                    self._runtime.governed_dispatcher,
                    DispatchRequest(goal_id=step_id, route=action_type, template=template, bindings=bindings),
                    actor_id="operator_skill",
                )
            else:
                result = self._runtime.dispatcher.dispatch(
                    DispatchRequest(
                        goal_id=step_id,
                        route=action_type,
                        template=template,
                        bindings=bindings,
                    )
                )
        except ExecutionAdapterError as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"dispatch_error:{exc.failure.code}",
            )
        except Exception as exc:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.FAILED,
                error_message=f"dispatch_error:{type(exc).__name__}",
            )

        if result.status is ExecutionOutcome.SUCCEEDED:
            return SkillStepOutcome(
                step_id=step_id,
                status=SkillOutcomeStatus.SUCCEEDED,
                execution_id=result.execution_id,
                outputs={"execution_id": result.execution_id, "status": result.status.value},
            )
        return SkillStepOutcome(
            step_id=step_id,
            status=SkillOutcomeStatus.FAILED,
            execution_id=result.execution_id,
            error_message=f"execution_{result.status.value}",
        )


class _WorkflowStageExecutor:
    """Stage executor that dispatches through run_skill for skill execution stages."""

    def __init__(self, *, loop: OperatorLoop, request: SkillRequest) -> None:
        self._loop = loop
        self._request = request

    def execute_stage(
        self,
        stage_id: str,
        stage_type: str,
        skill_id: str | None,
        inputs: Mapping[str, Any],
    ) -> StageExecutionResult:
        """Execute one workflow stage through the governed skill path."""
        started_at = self._loop.runtime.clock()

        if skill_id is not None:
            report = self._loop.run_skill(
                SkillRequest(
                    request_id=f"{self._request.request_id}-{stage_id}",
                    subject_id=self._request.subject_id,
                    goal_id=self._request.goal_id,
                    skill_id=skill_id,
                    input_context=inputs,
                )
            )

            if report.succeeded:
                return StageExecutionResult(
                    stage_id=stage_id,
                    status=StageStatus.COMPLETED,
                    output={"skill_id": skill_id, "status": "succeeded"},
                    started_at=started_at,
                    completed_at=self._loop.runtime.clock(),
                )
            error = report.structured_errors[0] if report.structured_errors else None
            return StageExecutionResult(
                stage_id=stage_id,
                status=StageStatus.FAILED,
                error=error,
                started_at=started_at,
                completed_at=self._loop.runtime.clock(),
            )

        return StageExecutionResult(
            stage_id=stage_id,
            status=StageStatus.FAILED,
            error=execution_error(
                error_code="workflow_stage_handler_missing",
                message="workflow stage has no governed runtime handler",
                recoverability=Recoverability.FATAL_FOR_RUN,
                context={"stage_type": stage_type},
            ),
            started_at=started_at,
            completed_at=self._loop.runtime.clock(),
        )


class _GoalSubGoalExecutor:
    """Sub-goal executor that dispatches through governed skill or workflow paths."""

    def __init__(self, *, loop: OperatorLoop, request: SkillRequest) -> None:
        self._loop = loop
        self._request = request

    def execute_sub_goal(self, sub_goal: SubGoal) -> SubGoal:
        """Execute a sub-goal by dispatching to run_skill or run_workflow."""
        autonomy_decision = self._loop.runtime.autonomy.evaluate(
            ActionClass.EXECUTE_WRITE,
            action_description="sub-goal execution",
        )
        if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
            return SubGoal(
                sub_goal_id=sub_goal.sub_goal_id,
                goal_id=sub_goal.goal_id,
                description=sub_goal.description,
                status=SubGoalStatus.FAILED,
                skill_id=sub_goal.skill_id,
                workflow_id=sub_goal.workflow_id,
                predecessors=sub_goal.predecessors,
            )

        if sub_goal.skill_id is not None:
            report = self._loop.run_skill(
                SkillRequest(
                    request_id=f"{self._request.request_id}-{sub_goal.sub_goal_id}",
                    subject_id=self._request.subject_id,
                    goal_id=self._request.goal_id,
                    skill_id=sub_goal.skill_id,
                    input_context=self._request.input_context,
                )
            )
            new_status = SubGoalStatus.COMPLETED if report.succeeded else SubGoalStatus.FAILED
        elif sub_goal.workflow_id is not None:
            workflow_store = self._loop.runtime.workflow_store
            if workflow_store is None:
                new_status = SubGoalStatus.FAILED
            else:
                try:
                    descriptor = workflow_store.load_descriptor(sub_goal.workflow_id)
                except PersistenceError:
                    new_status = SubGoalStatus.FAILED
                else:
                    report = self._loop.run_workflow(
                        SkillRequest(
                            request_id=f"{self._request.request_id}-{sub_goal.sub_goal_id}",
                            subject_id=self._request.subject_id,
                            goal_id=self._request.goal_id,
                            input_context=self._request.input_context,
                        ),
                        descriptor,
                    )
                    new_status = (
                        SubGoalStatus.COMPLETED
                        if report.status is WorkflowStatus.COMPLETED
                        else SubGoalStatus.FAILED
                    )
        else:
            new_status = SubGoalStatus.FAILED

        return SubGoal(
            sub_goal_id=sub_goal.sub_goal_id,
            goal_id=sub_goal.goal_id,
            description=sub_goal.description,
            status=new_status,
            skill_id=sub_goal.skill_id,
            workflow_id=sub_goal.workflow_id,
            predecessors=sub_goal.predecessors,
        )


__all__ = [
    "_GoalSubGoalExecutor",
    "_GovernedStepExecutor",
    "_WorkflowStageExecutor",
]
