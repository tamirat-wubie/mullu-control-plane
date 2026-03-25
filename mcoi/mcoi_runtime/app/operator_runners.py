"""Purpose: provide governed skill, workflow, and goal entry flows for the MCOI app layer.
Governance scope: entry-path orchestration below the public operator facade.
Dependencies: bootstrapped runtime services, operator helper executors, and contract stores.
Invariants: entry flows stay deterministic, fail closed, and preserve policy and autonomy ordering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcoi_runtime.contracts.autonomy import ActionClass, AutonomyDecisionStatus
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalExecutionState, GoalStatus, SubGoal
from mcoi_runtime.contracts.policy import PolicyDecisionStatus
from mcoi_runtime.contracts.skill import (
    SkillDescriptor,
    SkillLifecycle,
    SkillOutcomeStatus,
    SkillSelectionDecision,
)
from mcoi_runtime.contracts.workflow import (
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStatus,
    StageStatus,
)
from mcoi_runtime.core.errors import (
    Recoverability,
    SourcePlane,
    StructuredError,
    execution_error,
    policy_error,
    validation_error,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.policy_engine import PolicyInput

from .bootstrap import build_policy_decision
from .operator_executors import (
    _GoalSubGoalExecutor,
    _GovernedStepExecutor,
    _WorkflowStageExecutor,
)
from .operator_models import GoalRunReport, SkillRequest, SkillRunReport, WorkflowRunReport

if TYPE_CHECKING:
    from .operator_loop import OperatorLoop


def run_skill(loop: OperatorLoop, request: SkillRequest) -> SkillRunReport:
    """Execute a skill through the governed runtime path."""
    registry = loop.runtime.skill_registry
    selector = loop.runtime.skill_selector
    executor = loop.runtime.skill_executor

    skill: SkillDescriptor | None = None
    selection: SkillSelectionDecision | None = None

    if request.skill_id:
        skill = registry.get(request.skill_id)
        if skill is None:
            return SkillRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                skill_id=request.skill_id,
                selection=None,
                execution_record=None,
                status=SkillOutcomeStatus.FAILED,
                completed=False,
                structured_errors=(
                    execution_error(
                        error_code="skill_not_found",
                        message=f"skill not found: {request.skill_id}",
                    ),
                ),
            )
        if skill.lifecycle is SkillLifecycle.BLOCKED:
            return SkillRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                skill_id=request.skill_id,
                selection=None,
                execution_record=None,
                status=SkillOutcomeStatus.POLICY_DENIED,
                completed=False,
                structured_errors=(
                    policy_error(
                        error_code="skill_blocked",
                        message=f"skill is blocked: {request.skill_id}",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
            )
    else:
        candidates = registry.list_skills(exclude_blocked=True)
        selection = selector.select(candidates)
        if selection is None:
            return SkillRunReport(
                request_id=request.request_id,
                goal_id=request.goal_id,
                skill_id=None,
                selection=None,
                execution_record=None,
                status=SkillOutcomeStatus.FAILED,
                completed=False,
                structured_errors=(
                    execution_error(
                        error_code="no_skill_available",
                        message="no suitable skill found in registry",
                    ),
                ),
            )
        skill = registry.get(selection.selected_skill_id)

    autonomy_decision = loop.runtime.autonomy.evaluate(
        ActionClass.EXECUTE_WRITE,
        action_description=f"skill_execution:{skill.skill_id}",
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return SkillRunReport(
            request_id=request.request_id,
            goal_id=request.goal_id,
            skill_id=skill.skill_id,
            selection=selection,
            execution_record=None,
            status=SkillOutcomeStatus.POLICY_DENIED,
            completed=False,
            structured_errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message=(
                        f"autonomy mode {loop.runtime.autonomy.mode.value} "
                        f"blocked skill execution: {autonomy_decision.reason}"
                    ),
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                    },
                ),
            ),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id=request.goal_id,
            issued_at=loop.runtime.clock(),
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return SkillRunReport(
            request_id=request.request_id,
            goal_id=request.goal_id,
            skill_id=skill.skill_id,
            selection=selection,
            execution_record=None,
            status=SkillOutcomeStatus.POLICY_DENIED,
            completed=False,
            structured_errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message=f"policy gate returned {policy_decision.status.value} for skill execution",
                    recoverability=(
                        Recoverability.APPROVAL_REQUIRED
                        if policy_decision.status is PolicyDecisionStatus.ESCALATE
                        else Recoverability.FATAL_FOR_RUN
                    ),
                    related_ids=(policy_decision.decision_id,),
                    context={"policy_status": policy_decision.status.value},
                ),
            ),
        )

    governed_executor = _GovernedStepExecutor(runtime=loop.runtime)
    record = executor.execute(
        skill,
        step_executor=governed_executor,
        input_context=dict(request.input_context) if request.input_context else None,
    )

    succeeded = record.outcome.status is SkillOutcomeStatus.SUCCEEDED
    existing = skill.confidence
    new_confidence = min(1.0, existing + 0.1) if succeeded else max(0.0, existing - 0.1)
    registry.update_confidence(skill.skill_id, round(new_confidence, 4))

    if succeeded and skill.lifecycle is SkillLifecycle.CANDIDATE:
        try:
            registry.transition(skill.skill_id, SkillLifecycle.PROVISIONAL)
        except RuntimeCoreInvariantError:
            pass

    return SkillRunReport(
        request_id=request.request_id,
        goal_id=request.goal_id,
        skill_id=skill.skill_id,
        selection=selection,
        execution_record=record,
        status=record.outcome.status,
        completed=succeeded,
    )


def run_workflow(
    loop: OperatorLoop,
    request: SkillRequest,
    workflow_descriptor: WorkflowDescriptor,
) -> WorkflowRunReport:
    """Execute a workflow through the governed runtime path."""
    workflow_engine = loop.runtime.workflow_engine
    started_at = loop.runtime.clock()

    validation_errors = workflow_engine.validate_workflow(workflow_descriptor)
    if validation_errors:
        return WorkflowRunReport(
            workflow_id=workflow_descriptor.workflow_id,
            execution_id="",
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                validation_error(
                    error_code="workflow_validation_failed",
                    message=f"workflow validation failed: {'; '.join(validation_errors)}",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    autonomy_decision = loop.runtime.autonomy.evaluate(
        ActionClass.EXECUTE_WRITE,
        action_description=f"workflow_execution:{workflow_descriptor.workflow_id}",
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return WorkflowRunReport(
            workflow_id=workflow_descriptor.workflow_id,
            execution_id="",
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message=(
                        f"autonomy mode {loop.runtime.autonomy.mode.value} "
                        f"blocked workflow execution: {autonomy_decision.reason}"
                    ),
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id=request.goal_id,
            issued_at=loop.runtime.clock(),
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return WorkflowRunReport(
            workflow_id=workflow_descriptor.workflow_id,
            execution_id="",
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message=(
                        f"policy gate returned {policy_decision.status.value} "
                        "for workflow execution"
                    ),
                    recoverability=(
                        Recoverability.APPROVAL_REQUIRED
                        if policy_decision.status is PolicyDecisionStatus.ESCALATE
                        else Recoverability.FATAL_FOR_RUN
                    ),
                    related_ids=(policy_decision.decision_id,),
                    context={"policy_status": policy_decision.status.value},
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    workflow_context = dict(request.input_context) if request.input_context else None
    record = workflow_engine.start_workflow(workflow_descriptor, context=workflow_context)
    stage_executor = _WorkflowStageExecutor(loop=loop, request=request)

    while record.status is WorkflowStatus.RUNNING:
        new_record = workflow_engine.execute_next_stage(
            workflow_descriptor,
            record,
            stage_executor,
            context=workflow_context,
        )
        if new_record is record:
            record = WorkflowExecutionRecord(
                workflow_id=record.workflow_id,
                execution_id=record.execution_id,
                status=WorkflowStatus.FAILED,
                stage_results=record.stage_results,
                started_at=record.started_at,
                completed_at=loop.runtime.clock(),
            )
            break
        record = new_record

    if loop.runtime.workflow_store is not None:
        loop.runtime.workflow_store.save_execution_record(record)

    errors: list[StructuredError] = []
    if record.status is WorkflowStatus.FAILED:
        stage_has_error = False
        for stage_result in record.stage_results:
            if stage_result.status is StageStatus.FAILED and stage_result.error is not None:
                errors.append(stage_result.error)
                stage_has_error = True
        if not stage_has_error:
            errors.append(
                execution_error(
                    error_code="workflow_stuck_no_progress",
                    message="workflow execution made no progress - stages are blocked",
                )
            )

    return WorkflowRunReport(
        workflow_id=workflow_descriptor.workflow_id,
        execution_id=record.execution_id,
        status=record.status,
        stage_summaries=record.stage_results,
        errors=tuple(errors),
        started_at=record.started_at,
        completed_at=record.completed_at or loop.runtime.clock(),
    )


def run_goal(
    loop: OperatorLoop,
    request: SkillRequest,
    goal_descriptor: GoalDescriptor,
) -> GoalRunReport:
    """Execute a goal through the governed runtime path."""
    goal_engine = loop.runtime.goal_reasoning_engine
    started_at = loop.runtime.clock()

    state = goal_engine.accept_goal(goal_descriptor)

    autonomy_decision = loop.runtime.autonomy.evaluate(
        ActionClass.EXECUTE_WRITE,
        action_description=f"goal_execution:{goal_descriptor.goal_id}",
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message=(
                        f"autonomy mode {loop.runtime.autonomy.mode.value} "
                        f"blocked goal execution: {autonomy_decision.reason}"
                    ),
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id=request.goal_id,
            issued_at=loop.runtime.clock(),
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message=f"policy gate returned {policy_decision.status.value} for goal execution",
                    recoverability=(
                        Recoverability.APPROVAL_REQUIRED
                        if policy_decision.status is PolicyDecisionStatus.ESCALATE
                        else Recoverability.FATAL_FOR_RUN
                    ),
                    related_ids=(policy_decision.decision_id,),
                    context={"policy_status": policy_decision.status.value},
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    raw_sub_goals = goal_descriptor.metadata.get("sub_goals")
    if raw_sub_goals is None:
        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                validation_error(
                    error_code="goal_missing_sub_goals",
                    message="goal execution requires explicit sub-goals in metadata['sub_goals']",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    sub_goals_list: list[SubGoal] = []
    for sub_goal in raw_sub_goals:
        if isinstance(sub_goal, SubGoal):
            sub_goals_list.append(sub_goal)
    raw_sub_goals = tuple(sub_goals_list)

    if not raw_sub_goals:
        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                validation_error(
                    error_code="goal_empty_sub_goals",
                    message="all sub-goals were filtered out - none are valid SubGoal instances",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    plan = goal_engine.create_plan(goal_descriptor, raw_sub_goals)
    state = GoalExecutionState(
        goal_id=state.goal_id,
        status=GoalStatus.EXECUTING,
        current_plan_id=plan.plan_id,
        updated_at=loop.runtime.clock(),
    )

    if loop.runtime.goal_store is not None:
        loop.runtime.goal_store.save_plan(plan)
        loop.runtime.goal_store.save_goal_state(state)

    sub_goal_executor = _GoalSubGoalExecutor(loop=loop, request=request)

    while state.status is GoalStatus.EXECUTING:
        new_state = goal_engine.execute_next_sub_goal(state, plan, sub_goal_executor)
        if new_state is state:
            state = GoalExecutionState(
                goal_id=state.goal_id,
                status=GoalStatus.FAILED,
                current_plan_id=state.current_plan_id,
                updated_at=loop.runtime.clock(),
                completed_sub_goals=state.completed_sub_goals,
                failed_sub_goals=state.failed_sub_goals,
            )
            break
        state = new_state
        if loop.runtime.goal_store is not None:
            loop.runtime.goal_store.save_goal_state(state)

    errors: list[StructuredError] = []
    if state.status is GoalStatus.FAILED:
        if state.failed_sub_goals:
            errors.append(
                execution_error(
                    error_code="goal_sub_goal_failed",
                    message=f"goal failed: sub-goals {', '.join(state.failed_sub_goals)} failed",
                    related_ids=state.failed_sub_goals,
                )
            )
        else:
            errors.append(
                execution_error(
                    error_code="goal_stuck_no_progress",
                    message="goal execution made no progress - sub-goals are blocked",
                )
            )

    return GoalRunReport(
        goal_id=goal_descriptor.goal_id,
        status=state.status,
        plan_id=plan.plan_id,
        completed_sub_goals=state.completed_sub_goals,
        failed_sub_goals=state.failed_sub_goals,
        errors=tuple(errors),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


__all__ = ["run_goal", "run_skill", "run_workflow"]
