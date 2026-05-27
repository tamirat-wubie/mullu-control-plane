"""Purpose: provide governed skill, workflow, and goal entry flows for the MCOI app layer.
Governance scope: entry-path orchestration below the public operator facade.
Dependencies: bootstrapped runtime services, operator helper executors, and contract stores.
Invariants: entry flows stay deterministic, fail closed, and preserve policy and autonomy ordering.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import TYPE_CHECKING

from mcoi_runtime.contracts.autonomy import ActionClass, AutonomyDecisionStatus
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalExecutionState, GoalStatus, SubGoal
from mcoi_runtime.contracts.job import JobStatus
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
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence.workflow_store import WorkflowRuntimeState
from mcoi_runtime.core.errors import (
    Recoverability,
    SourcePlane,
    StructuredError,
    execution_error,
    policy_error,
    validation_error,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.skill_promotion import promote_skill_with_evidence
from mcoi_runtime.governance.policy.engine import PolicyInput

from .bootstrap import build_policy_decision
from .operator_executors import (
    _GoalSubGoalExecutor,
    _GovernedStepExecutor,
    _WorkflowStageExecutor,
)
from .operator_models import (
    CoordinationRecoveryReport,
    CoordinationRecoveryRequest,
    GoalReconcileReport,
    GoalReconcileRequest,
    GoalResumeRequest,
    GoalRunReport,
    JobReconcileReport,
    JobReconcileRequest,
    SkillRequest,
    SkillRunReport,
    TeamQueueReconcileReport,
    TeamQueueReconcileRequest,
    WorkQueueReconcileReport,
    WorkQueueReconcileRequest,
    WorkforceReconcileReport,
    WorkforceReconcileRequest,
    WorkflowResumeRequest,
    WorkflowRunReport,
)

if TYPE_CHECKING:
    from .operator_loop import OperatorLoop


def _bounded_lifecycle_transition_warning(exc: RuntimeCoreInvariantError) -> str:
    """Return a stable lifecycle warning without exposing registry details."""
    return f"skill lifecycle transition failed ({type(exc).__name__})"


def _bounded_lifecycle_promotion_skip(reason: str) -> str:
    """Return a stable promotion skip warning without exposing evidence details."""
    return f"skill lifecycle promotion skipped ({reason})"


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
                        message="skill not found",
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
                        message="skill is blocked",
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
        action_description="skill execution",
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
                    message="autonomy blocked skill execution",
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
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=True,
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
                    message="policy gate blocked skill execution",
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

    lifecycle_transition_warning = ""
    if succeeded and skill.lifecycle is SkillLifecycle.CANDIDATE:
        try:
            promotion_decision = promote_skill_with_evidence(
                registry,
                skill_id=skill.skill_id,
                target_lifecycle=SkillLifecycle.PROVISIONAL,
                execution_records=(record,),
                created_at=loop.runtime.clock(),
            )
            if not promotion_decision.approved:
                lifecycle_transition_warning = _bounded_lifecycle_promotion_skip(
                    promotion_decision.reason
                )
        except RuntimeCoreInvariantError as exc:
            lifecycle_transition_warning = _bounded_lifecycle_transition_warning(exc)

    return SkillRunReport(
        request_id=request.request_id,
        goal_id=request.goal_id,
        skill_id=skill.skill_id,
        selection=selection,
        execution_record=record,
        status=record.outcome.status,
        completed=succeeded,
        lifecycle_transition_warning=lifecycle_transition_warning,
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
                    message="workflow validation failed",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    autonomy_decision = loop.runtime.autonomy.evaluate(
        ActionClass.EXECUTE_WRITE,
        action_description="workflow execution",
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
                    message="autonomy blocked workflow execution",
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
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=True,
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
                    message="policy gate blocked workflow execution",
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
    if loop.runtime.workflow_store is not None:
        loop.runtime.workflow_store.save_descriptor(workflow_descriptor)
    record = workflow_engine.start_workflow(workflow_descriptor, context=workflow_context)
    record = _advance_workflow_record(
        loop=loop,
        request=request,
        workflow_descriptor=workflow_descriptor,
        record=record,
        workflow_context=workflow_context,
    )

    errors = _workflow_errors(record)

    return WorkflowRunReport(
        workflow_id=workflow_descriptor.workflow_id,
        execution_id=record.execution_id,
        status=record.status,
        stage_summaries=record.stage_results,
        errors=tuple(errors),
        started_at=record.started_at,
        completed_at=record.completed_at or loop.runtime.clock(),
    )


def resume_workflow(
    loop: OperatorLoop,
    request: WorkflowResumeRequest,
) -> WorkflowRunReport:
    """Resume a persisted workflow execution explicitly through the operator facade."""
    started_at = loop.runtime.clock()
    store = loop.runtime.workflow_store
    if store is None:
        return WorkflowRunReport(
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                execution_error(
                    error_code="workflow_store_not_configured",
                    message="workflow resume requires a configured workflow store",
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    try:
        workflow_descriptor = store.load_descriptor(request.workflow_id)
        persisted_record = store.load_execution_record(request.execution_id)
    except PersistenceError as exc:
        return WorkflowRunReport(
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                execution_error(
                    error_code="workflow_resume_load_failed",
                    message=str(exc),
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    if persisted_record.workflow_id != request.workflow_id:
        return WorkflowRunReport(
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            status=WorkflowStatus.FAILED,
            stage_summaries=(),
            errors=(
                validation_error(
                    error_code="workflow_resume_mismatch",
                    message="workflow execution record does not match requested workflow_id",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    try:
        resumed_record = loop.runtime.workflow_engine.resume_workflow(
            workflow_descriptor,
            persisted_record,
        )
    except RuntimeCoreInvariantError as exc:
        return WorkflowRunReport(
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            status=WorkflowStatus.FAILED,
            stage_summaries=persisted_record.stage_results,
            errors=(
                validation_error(
                    error_code="workflow_resume_invalid_state",
                    message=str(exc),
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=persisted_record.started_at,
            completed_at=loop.runtime.clock(),
        )

    workflow_context = dict(request.input_context) if request.input_context else None
    record = _advance_workflow_record(
        loop=loop,
        request=request,
        workflow_descriptor=workflow_descriptor,
        record=resumed_record,
        workflow_context=workflow_context,
    )
    errors = _workflow_errors(record)

    return WorkflowRunReport(
        workflow_id=request.workflow_id,
        execution_id=record.execution_id,
        status=record.status,
        stage_summaries=record.stage_results,
        errors=tuple(errors),
        started_at=record.started_at,
        completed_at=record.completed_at or loop.runtime.clock(),
    )


def _persist_goal_runtime(
    loop: OperatorLoop,
    goal_descriptor: GoalDescriptor,
    plan: object,
    state: GoalExecutionState,
) -> None:
    """Persist goal runtime witnesses when a goal store is configured."""
    goal_store = loop.runtime.goal_store
    if goal_store is None:
        return
    goal_store.save_goal_descriptor(goal_descriptor)
    goal_store.save_plan(plan)
    goal_store.save_goal_state(state)


def _advance_goal_state(
    loop: OperatorLoop,
    request: SkillRequest | GoalResumeRequest,
    goal_descriptor: GoalDescriptor,
    plan: object,
    state: GoalExecutionState,
) -> GoalExecutionState:
    """Advance a goal from its current state through the governed sub-goal path."""
    goal_engine = loop.runtime.goal_reasoning_engine
    _persist_goal_runtime(loop, goal_descriptor, plan, state)
    sub_goal_executor = _GoalSubGoalExecutor(loop=loop, request=request)

    while state.status in (GoalStatus.ACCEPTED, GoalStatus.PLANNING, GoalStatus.EXECUTING):
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
            if loop.runtime.goal_store is not None:
                loop.runtime.goal_store.save_goal_state(state)
            break
        state = new_state
        if loop.runtime.goal_store is not None:
            loop.runtime.goal_store.save_goal_state(state)

    return state


def _goal_errors(state: GoalExecutionState) -> tuple[StructuredError, ...]:
    """Encode deterministic goal failure causes for operator reports."""
    if state.status is not GoalStatus.FAILED:
        return ()
    if state.failed_sub_goals:
        return (
            execution_error(
                error_code="goal_sub_goal_failed",
                message="goal failed due to sub-goal failure",
                related_ids=state.failed_sub_goals,
            ),
        )
    return (
        execution_error(
            error_code="goal_stuck_no_progress",
            message="goal execution made no progress - sub-goals are blocked",
        ),
    )


def resume_goal(
    loop: OperatorLoop,
    request: GoalResumeRequest,
) -> GoalRunReport:
    """Resume a persisted goal execution explicitly through the operator facade."""
    started_at = loop.runtime.clock()
    store = loop.runtime.goal_store
    if store is None:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                execution_error(
                    error_code="goal_store_not_configured",
                    message="goal resume requires a configured goal store",
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    try:
        runtime_state = store.load_state()
    except PersistenceError as exc:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                execution_error(
                    error_code="goal_resume_load_failed",
                    message=str(exc),
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    goal_descriptor = next(
        (descriptor for descriptor in runtime_state.descriptors if descriptor.goal_id == request.goal_id),
        None,
    )
    state = next(
        (goal_state for goal_state in runtime_state.states if goal_state.goal_id == request.goal_id),
        None,
    )
    if goal_descriptor is None or state is None:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                validation_error(
                    error_code="goal_runtime_missing",
                    message="persisted goal runtime witness not found",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    if state.current_plan_id is None:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                validation_error(
                    error_code="goal_resume_invalid_state",
                    message="persisted goal state has no current plan assigned",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    if state.status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ARCHIVED):
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=state.current_plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=(
                validation_error(
                    error_code="goal_resume_invalid_state",
                    message="goal is in terminal state and cannot resume",
                    source_plane=SourcePlane.EXECUTION,
                    context={"goal_status": state.status.value},
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    plan = next(
        (candidate for candidate in runtime_state.plans if candidate.plan_id == state.current_plan_id),
        None,
    )
    if plan is None or plan.goal_id != request.goal_id:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=state.current_plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=(
                validation_error(
                    error_code="goal_resume_invalid_state",
                    message="persisted goal current plan does not match the requested goal",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    existing_descriptor = loop.runtime.goal_reasoning_engine.get_goal_descriptor(request.goal_id)
    existing_state = loop.runtime.goal_reasoning_engine.get_goal_state(request.goal_id)
    existing_plan = loop.runtime.goal_reasoning_engine.get_plan(plan.plan_id)
    if existing_descriptor is None and existing_state is None and existing_plan is None:
        try:
            loop.runtime.goal_reasoning_engine.restore_goal(goal_descriptor, state)
            loop.runtime.goal_reasoning_engine.restore_plan(plan)
        except RuntimeCoreInvariantError as exc:
            return GoalRunReport(
                goal_id=request.goal_id,
                status=GoalStatus.FAILED,
                plan_id=plan.plan_id,
                completed_sub_goals=state.completed_sub_goals,
                failed_sub_goals=state.failed_sub_goals,
                errors=(
                    validation_error(
                        error_code="goal_resume_restore_failed",
                        message=str(exc),
                        source_plane=SourcePlane.EXECUTION,
                    ),
                ),
                started_at=goal_descriptor.created_at,
                completed_at=loop.runtime.clock(),
            )
    elif (
        existing_descriptor != goal_descriptor
        or existing_state != state
        or existing_plan != plan
    ):
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=plan.plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=(
                validation_error(
                    error_code="goal_resume_runtime_mismatch",
                    message="live goal runtime does not match the persisted goal witness",
                    source_plane=SourcePlane.EXECUTION,
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    autonomy_decision = loop.runtime.autonomy.evaluate(
        ActionClass.EXECUTE_WRITE,
        action_description=f"goal_resume:{request.goal_id}",
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=plan.plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked goal resume",
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id=request.goal_id,
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=True,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return GoalRunReport(
            goal_id=request.goal_id,
            status=GoalStatus.FAILED,
            plan_id=plan.plan_id,
            completed_sub_goals=state.completed_sub_goals,
            failed_sub_goals=state.failed_sub_goals,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked goal resume",
                    recoverability=(
                        Recoverability.APPROVAL_REQUIRED
                        if policy_decision.status is PolicyDecisionStatus.ESCALATE
                        else Recoverability.FATAL_FOR_RUN
                    ),
                    related_ids=(policy_decision.decision_id,),
                    context={"policy_status": policy_decision.status.value},
                ),
            ),
            started_at=goal_descriptor.created_at,
            completed_at=loop.runtime.clock(),
        )

    state = _advance_goal_state(loop, request, goal_descriptor, plan, state)
    return GoalRunReport(
        goal_id=request.goal_id,
        status=state.status,
        plan_id=plan.plan_id,
        completed_sub_goals=state.completed_sub_goals,
        failed_sub_goals=state.failed_sub_goals,
        errors=_goal_errors(state),
        started_at=goal_descriptor.created_at,
        completed_at=loop.runtime.clock(),
    )


def _advance_workflow_record(
    *,
    loop: OperatorLoop,
    request: SkillRequest | WorkflowResumeRequest,
    workflow_descriptor: WorkflowDescriptor,
    record: WorkflowExecutionRecord,
    workflow_context: dict[str, object] | None,
) -> WorkflowExecutionRecord:
    """Advance a workflow record through all remaining eligible stages."""
    if loop.runtime.workflow_store is not None:
        loop.runtime.workflow_store.save_execution_record(record)
    stage_executor = _WorkflowStageExecutor(loop=loop, request=request)

    while record.status is WorkflowStatus.RUNNING:
        new_record = loop.runtime.workflow_engine.execute_next_stage(
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
            if loop.runtime.workflow_store is not None:
                loop.runtime.workflow_store.save_execution_record(record)
            break
        record = new_record
        if loop.runtime.workflow_store is not None:
            loop.runtime.workflow_store.save_execution_record(record)
    return record


def _workflow_errors(record: WorkflowExecutionRecord) -> list[StructuredError]:
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
    return errors


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
        action_description="goal execution",
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return GoalRunReport(
            goal_id=goal_descriptor.goal_id,
            status=GoalStatus.FAILED,
            plan_id=None,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy blocked goal execution",
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
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=True,
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
                    message="policy gate blocked goal execution",
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
    state = _advance_goal_state(loop, request, goal_descriptor, plan, state)
    return GoalRunReport(
        goal_id=goal_descriptor.goal_id,
        status=state.status,
        plan_id=plan.plan_id,
        completed_sub_goals=state.completed_sub_goals,
        failed_sub_goals=state.failed_sub_goals,
        errors=_goal_errors(state),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def reconcile_workforce(
    loop: OperatorLoop,
    request: WorkforceReconcileRequest,
) -> WorkforceReconcileReport:
    """Assess or restore explicit workforce runtime state through the governed path."""
    started_at = loop.runtime.clock()
    has_write_effects = (
        request.restore_from_store or request.detect_gaps or request.detect_violations
    )
    action_class = (
        ActionClass.EXECUTE_WRITE if has_write_effects else ActionClass.ANALYZE
    )
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            f"workforce_reconcile:{request.tenant_id}"
            if has_write_effects
            else f"workforce_assess:{request.tenant_id}"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return WorkforceReconcileReport(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            restored=False,
            assessment_id=None,
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            worker_count=0,
            active_worker_count=0,
            request_count=0,
            decision_count=0,
            gap_count=0,
            violation_count=0,
            state_hash="",
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked workforce reconciliation",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id=f"workforce_reconcile:{request.tenant_id}",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=has_write_effects,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return WorkforceReconcileReport(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            restored=False,
            assessment_id=None,
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            worker_count=0,
            active_worker_count=0,
            request_count=0,
            decision_count=0,
            gap_count=0,
            violation_count=0,
            state_hash="",
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked workforce reconciliation",
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

    workforce_engine = loop.runtime.workforce_engine
    restored = False
    if request.restore_from_store:
        store = loop.runtime.workforce_store
        if store is None:
            return WorkforceReconcileReport(
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                restored=False,
                assessment_id=None,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                worker_count=0,
                active_worker_count=0,
                request_count=0,
                decision_count=0,
                gap_count=0,
                violation_count=0,
                state_hash="",
                errors=(
                    execution_error(
                        error_code="workforce_store_not_configured",
                        message="workforce restore requires a configured workforce store",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        try:
            store.restore_state(workforce_engine)
        except (PersistenceError, RuntimeCoreInvariantError) as exc:
            return WorkforceReconcileReport(
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                restored=False,
                assessment_id=None,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                worker_count=0,
                active_worker_count=0,
                request_count=0,
                decision_count=0,
                gap_count=0,
                violation_count=0,
                state_hash="",
                errors=(
                    execution_error(
                        error_code="workforce_restore_failed",
                        message=str(exc),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        restored = True

    new_gap_ids: tuple[str, ...] = ()
    if request.detect_gaps:
        new_gap_ids = tuple(
            sorted(
                gap.gap_id
                for gap in workforce_engine.detect_coverage_gaps(request.tenant_id)
            )
        )

    new_violation_ids: tuple[str, ...] = ()
    if request.detect_violations:
        new_violation_ids = tuple(
            sorted(
                violation.violation_id
                for violation in workforce_engine.detect_workforce_violations(
                    request.tenant_id
                )
            )
        )

    assessment_id = stable_identifier(
        "workforce-assessment",
        {
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
        },
    )
    assessment = workforce_engine.workforce_assessment(assessment_id, request.tenant_id)

    return WorkforceReconcileReport(
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        restored=restored,
        assessment_id=assessment.assessment_id,
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        worker_count=assessment.total_workers,
        active_worker_count=assessment.active_workers,
        request_count=assessment.total_requests,
        decision_count=assessment.total_decisions,
        gap_count=assessment.total_gaps,
        violation_count=assessment.total_violations,
        new_gap_ids=new_gap_ids,
        new_violation_ids=new_violation_ids,
        state_hash=workforce_engine.state_hash(),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def _queue_state_hash(states: tuple[object, ...]) -> str:
    payload = [
        state.to_json_dict() if hasattr(state, "to_json_dict") else state
        for state in states
    ]
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _job_runtime_hash(
    descriptors: tuple[object, ...],
    states: tuple[object, ...],
) -> str:
    payload = {
        "descriptors": [
            descriptor.to_json_dict() if hasattr(descriptor, "to_json_dict") else descriptor
            for descriptor in descriptors
        ],
        "states": [
            state.to_json_dict() if hasattr(state, "to_json_dict") else state
            for state in states
        ],
    }
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _goal_runtime_hash(
    descriptors: tuple[object, ...],
    states: tuple[object, ...],
    plans: tuple[object, ...],
    replans: tuple[object, ...],
) -> str:
    payload = {
        "descriptors": [
            descriptor.to_json_dict() if hasattr(descriptor, "to_json_dict") else descriptor
            for descriptor in descriptors
        ],
        "states": [
            state.to_json_dict() if hasattr(state, "to_json_dict") else state
            for state in states
        ],
        "plans": [
            plan.to_json_dict() if hasattr(plan, "to_json_dict") else plan
            for plan in plans
        ],
        "replans": [
            record.to_json_dict() if hasattr(record, "to_json_dict") else record
            for record in replans
        ],
    }
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _coordination_payload_hash(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _workflow_inventory_payload(
    descriptors: tuple[object, ...],
    executions: tuple[object, ...],
) -> dict[str, object]:
    return {
        "descriptors": [
            descriptor.to_json_dict() if hasattr(descriptor, "to_json_dict") else descriptor
            for descriptor in descriptors
        ],
        "executions": [
            execution.to_json_dict() if hasattr(execution, "to_json_dict") else execution
            for execution in executions
        ],
    }


def _load_workflow_inventory(loop: OperatorLoop) -> tuple[tuple[object, ...], tuple[object, ...]]:
    store = loop.runtime.workflow_store
    if store is None:
        raise PersistenceError("workflow store not configured")
    state = store.load_state()
    return state.descriptors, state.execution_records


def _coordination_consistency_errors(
    *,
    loop: OperatorLoop,
    goal_descriptors: tuple[object, ...] | None,
    job_descriptors: tuple[object, ...] | None,
    work_queue_entries: tuple[object, ...] | None,
    workflow_descriptors: tuple[object, ...] | None,
) -> tuple[StructuredError, ...]:
    errors: list[StructuredError] = []

    if work_queue_entries is not None:
        available_job_ids = (
            {descriptor.job_id for descriptor in job_descriptors}
            if job_descriptors is not None
            else {
                descriptor.job_id
                for descriptor in loop.runtime.job_engine.list_job_descriptors()
            }
        )
        missing_job_ids = tuple(
            sorted(
                {
                    entry.job_id
                    for entry in work_queue_entries
                    if entry.job_id not in available_job_ids
                }
            )
        )
        if missing_job_ids:
            errors.append(
                validation_error(
                    error_code="recovery_missing_job_for_queue_entry",
                    message="work queue entries reference missing job descriptors",
                    source_plane=SourcePlane.COORDINATION,
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=missing_job_ids,
                )
            )

    if workflow_descriptors is not None and job_descriptors is not None:
        available_workflow_ids = {descriptor.workflow_id for descriptor in workflow_descriptors}
        missing_workflow_ids = tuple(
            sorted(
                {
                    descriptor.workflow_id
                    for descriptor in job_descriptors
                    if descriptor.workflow_id is not None
                    and descriptor.workflow_id not in available_workflow_ids
                }
            )
        )
        if missing_workflow_ids:
            errors.append(
                validation_error(
                    error_code="recovery_missing_workflow_for_job",
                    message="job descriptors reference missing workflow descriptors",
                    source_plane=SourcePlane.COORDINATION,
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=missing_workflow_ids,
                )
            )

    if job_descriptors is not None:
        available_goal_ids = (
            {descriptor.goal_id for descriptor in goal_descriptors}
            if goal_descriptors is not None
            else {
                descriptor.goal_id
                for descriptor in loop.runtime.goal_reasoning_engine.list_goal_descriptors()
            }
        )
        missing_goal_ids = tuple(
            sorted(
                {
                    descriptor.goal_id
                    for descriptor in job_descriptors
                    if descriptor.goal_id is not None
                    and descriptor.goal_id not in available_goal_ids
                }
            )
        )
        if missing_goal_ids:
            errors.append(
                validation_error(
                    error_code="recovery_missing_goal_for_job",
                    message="job descriptors reference missing goal descriptors",
                    source_plane=SourcePlane.COORDINATION,
                    recoverability=Recoverability.FATAL_FOR_RUN,
                    related_ids=missing_goal_ids,
                )
            )

    return tuple(errors)


def recover_coordination_state(
    loop: OperatorLoop,
    request: CoordinationRecoveryRequest,
) -> CoordinationRecoveryReport:
    """Inspect or restore persisted coordination carriers through one governed path."""
    started_at = loop.runtime.clock()
    has_write_effects = any(
        (
            request.restore_goals,
            request.restore_workflows,
            request.restore_jobs,
            request.restore_work_queue,
            request.restore_team_queue,
            request.restore_workforce,
        )
    )
    action_class = ActionClass.EXECUTE_WRITE if has_write_effects else ActionClass.ANALYZE
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            "coordination_recovery_restore"
            if has_write_effects
            else "coordination_recovery_inspect"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return CoordinationRecoveryReport(
            request_id=request.request_id,
            restored_components=(),
            inspected_components=(),
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0,
            work_queue_entry_count=0,
            team_queue_state_count=0,
            workforce_worker_count=0,
            workforce_request_count=0,
            workforce_decision_count=0,
            workflow_descriptor_count=0,
            workflow_execution_count=0,
            cross_store_checks_passed=False,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked coordination recovery",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id="coordination_recovery",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=has_write_effects,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return CoordinationRecoveryReport(
            request_id=request.request_id,
            restored_components=(),
            inspected_components=(),
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0,
            work_queue_entry_count=0,
            team_queue_state_count=0,
            workforce_worker_count=0,
            workforce_request_count=0,
            workforce_decision_count=0,
            workflow_descriptor_count=0,
            workflow_execution_count=0,
            cross_store_checks_passed=False,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked coordination recovery",
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

    inspected_components: list[str] = []
    restored_components: list[str] = []
    goal_state = None
    workflow_state: WorkflowRuntimeState | None = None
    job_state = None
    work_queue_state = None
    team_queue_states = None
    workforce_state = None
    workflow_descriptors: tuple[object, ...] | None = None
    workflow_executions: tuple[object, ...] | None = None

    try:
        if request.restore_goals:
            if loop.runtime.goal_store is None:
                raise PersistenceError("goal store not configured")
            goal_state = loop.runtime.goal_store.load_state()
            inspected_components.append("goals")
        if request.restore_workflows:
            if loop.runtime.workflow_store is None:
                raise PersistenceError("workflow store not configured")
            workflow_state = loop.runtime.workflow_store.load_state()
            workflow_descriptors = workflow_state.descriptors
            workflow_executions = workflow_state.execution_records
            inspected_components.append("workflow_store")
        if request.restore_jobs:
            if loop.runtime.job_store is None:
                raise PersistenceError("job store not configured")
            job_state = loop.runtime.job_store.load_state()
            inspected_components.append("jobs")
        if request.restore_work_queue:
            if loop.runtime.work_queue_store is None:
                raise PersistenceError("work queue store not configured")
            work_queue_state = loop.runtime.work_queue_store.load_state()
            inspected_components.append("work_queue")
        if request.restore_team_queue:
            if loop.runtime.team_queue_store is None:
                raise PersistenceError("team queue store not configured")
            team_queue_states = loop.runtime.team_queue_store.load_queue_states()
            inspected_components.append("team_queue")
        if request.restore_workforce:
            if loop.runtime.workforce_store is None:
                raise PersistenceError("workforce store not configured")
            workforce_state = loop.runtime.workforce_store.load_state()
            inspected_components.append("workforce")
        if request.inspect_workflow_store and workflow_state is None:
            workflow_descriptors, workflow_executions = _load_workflow_inventory(loop)
            inspected_components.append("workflow_store")
    except PersistenceError as exc:
        return CoordinationRecoveryReport(
            request_id=request.request_id,
            restored_components=(),
            inspected_components=tuple(inspected_components),
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0 if job_state is None else len(job_state.descriptors),
            work_queue_entry_count=0 if work_queue_state is None else len(work_queue_state.entries),
            team_queue_state_count=0 if team_queue_states is None else len(team_queue_states),
            workforce_worker_count=0 if workforce_state is None else len(workforce_state.workers),
            workforce_request_count=0 if workforce_state is None else len(workforce_state.requests),
            workforce_decision_count=0 if workforce_state is None else len(workforce_state.decisions),
            workflow_descriptor_count=0 if workflow_descriptors is None else len(workflow_descriptors),
            workflow_execution_count=0 if workflow_executions is None else len(workflow_executions),
            cross_store_checks_passed=False,
            goal_descriptor_count=0 if goal_state is None else len(goal_state.descriptors),
            goal_state_count=0 if goal_state is None else len(goal_state.states),
            goal_plan_count=0 if goal_state is None else len(goal_state.plans),
            goal_replan_count=0 if goal_state is None else len(goal_state.replans),
            errors=(
                execution_error(
                    error_code="coordination_store_not_available",
                    message=str(exc),
                    recoverability=Recoverability.FATAL_FOR_RUN,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )
    except RuntimeCoreInvariantError as exc:
        return CoordinationRecoveryReport(
            request_id=request.request_id,
            restored_components=(),
            inspected_components=tuple(inspected_components),
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0 if job_state is None else len(job_state.descriptors),
            work_queue_entry_count=0 if work_queue_state is None else len(work_queue_state.entries),
            team_queue_state_count=0 if team_queue_states is None else len(team_queue_states),
            workforce_worker_count=0 if workforce_state is None else len(workforce_state.workers),
            workforce_request_count=0 if workforce_state is None else len(workforce_state.requests),
            workforce_decision_count=0 if workforce_state is None else len(workforce_state.decisions),
            workflow_descriptor_count=0 if workflow_descriptors is None else len(workflow_descriptors),
            workflow_execution_count=0 if workflow_executions is None else len(workflow_executions),
            cross_store_checks_passed=False,
            goal_descriptor_count=0 if goal_state is None else len(goal_state.descriptors),
            goal_state_count=0 if goal_state is None else len(goal_state.states),
            goal_plan_count=0 if goal_state is None else len(goal_state.plans),
            goal_replan_count=0 if goal_state is None else len(goal_state.replans),
            errors=(
                validation_error(
                    error_code="workflow_store_invalid",
                    message=str(exc),
                    source_plane=SourcePlane.COORDINATION,
                    recoverability=Recoverability.FATAL_FOR_RUN,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    consistency_errors = ()
    if request.require_cross_store_consistency:
        consistency_errors = _coordination_consistency_errors(
            loop=loop,
            goal_descriptors=(None if goal_state is None else goal_state.descriptors),
            job_descriptors=(None if job_state is None else job_state.descriptors),
            work_queue_entries=(None if work_queue_state is None else work_queue_state.entries),
            workflow_descriptors=workflow_descriptors,
        )
        if consistency_errors:
            return CoordinationRecoveryReport(
                request_id=request.request_id,
                restored_components=(),
                inspected_components=tuple(inspected_components),
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                job_count=0 if job_state is None else len(job_state.descriptors),
                work_queue_entry_count=0 if work_queue_state is None else len(work_queue_state.entries),
                team_queue_state_count=0 if team_queue_states is None else len(team_queue_states),
                workforce_worker_count=0 if workforce_state is None else len(workforce_state.workers),
                workforce_request_count=0 if workforce_state is None else len(workforce_state.requests),
                workforce_decision_count=0 if workforce_state is None else len(workforce_state.decisions),
                workflow_descriptor_count=0 if workflow_descriptors is None else len(workflow_descriptors),
                workflow_execution_count=0 if workflow_executions is None else len(workflow_executions),
                cross_store_checks_passed=False,
                goal_descriptor_count=0 if goal_state is None else len(goal_state.descriptors),
                goal_state_count=0 if goal_state is None else len(goal_state.states),
                goal_plan_count=0 if goal_state is None else len(goal_state.plans),
                goal_replan_count=0 if goal_state is None else len(goal_state.replans),
                errors=consistency_errors,
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    try:
        if request.restore_goals:
            if loop.runtime.goal_store is None:
                raise PersistenceError("goal store not configured")
            loop.runtime.goal_store.restore_state(loop.runtime.goal_reasoning_engine)
            restored_components.append("goals")
        if request.restore_workflows:
            if loop.runtime.workflow_store is None:
                raise PersistenceError("workflow store not configured")
            loop.runtime.workflow_store.restore_state(loop.runtime.workflow_engine)
            restored_components.append("workflows")
        if request.restore_jobs:
            if loop.runtime.job_store is None:
                raise PersistenceError("job store not configured")
            loop.runtime.job_store.restore_state(loop.runtime.job_engine)
            restored_components.append("jobs")
        if request.restore_work_queue:
            if loop.runtime.work_queue_store is None:
                raise PersistenceError("work queue store not configured")
            loop.runtime.work_queue_store.restore_state(loop.runtime.work_queue)
            restored_components.append("work_queue")
        if request.restore_team_queue:
            if loop.runtime.team_queue_store is None:
                raise PersistenceError("team queue store not configured")
            loop.runtime.team_queue_store.restore_queue_states(loop.runtime.team_engine)
            restored_components.append("team_queue")
        if request.restore_workforce:
            if loop.runtime.workforce_store is None:
                raise PersistenceError("workforce store not configured")
            loop.runtime.workforce_store.restore_state(loop.runtime.workforce_engine)
            restored_components.append("workforce")
    except (PersistenceError, RuntimeCoreInvariantError) as exc:
        return CoordinationRecoveryReport(
            request_id=request.request_id,
            restored_components=tuple(restored_components),
            inspected_components=tuple(inspected_components),
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0 if job_state is None else len(job_state.descriptors),
            work_queue_entry_count=0 if work_queue_state is None else len(work_queue_state.entries),
            team_queue_state_count=0 if team_queue_states is None else len(team_queue_states),
            workforce_worker_count=0 if workforce_state is None else len(workforce_state.workers),
            workforce_request_count=0 if workforce_state is None else len(workforce_state.requests),
            workforce_decision_count=0 if workforce_state is None else len(workforce_state.decisions),
            workflow_descriptor_count=0 if workflow_descriptors is None else len(workflow_descriptors),
            workflow_execution_count=0 if workflow_executions is None else len(workflow_executions),
            cross_store_checks_passed=request.require_cross_store_consistency,
            goal_descriptor_count=0 if goal_state is None else len(goal_state.descriptors),
            goal_state_count=0 if goal_state is None else len(goal_state.states),
            goal_plan_count=0 if goal_state is None else len(goal_state.plans),
            goal_replan_count=0 if goal_state is None else len(goal_state.replans),
            errors=(
                execution_error(
                    error_code="coordination_restore_failed",
                    message=str(exc),
                    recoverability=Recoverability.FATAL_FOR_RUN,
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    state_hash = _coordination_payload_hash(
        {
            "goals": (
                None
                if goal_state is None
                else {
                    "descriptors": [
                        descriptor.to_json_dict() for descriptor in goal_state.descriptors
                    ],
                    "states": [
                        state.to_json_dict() for state in goal_state.states
                    ],
                    "plans": [
                        plan.to_json_dict() for plan in goal_state.plans
                    ],
                    "replans": [
                        record.to_json_dict() for record in goal_state.replans
                    ],
                }
            ),
            "jobs": (
                None
                if job_state is None
                else {
                    "descriptors": [
                        descriptor.to_json_dict() for descriptor in job_state.descriptors
                    ],
                    "states": [
                        state.to_json_dict() for state in job_state.states
                    ],
                }
            ),
            "work_queue": (
                None
                if work_queue_state is None
                else [entry.to_json_dict() for entry in work_queue_state.entries]
            ),
            "team_queue": (
                None
                if team_queue_states is None
                else [state.to_json_dict() for state in team_queue_states]
            ),
            "workforce": (
                None
                if workforce_state is None
                else {
                    "workers": [worker.to_json_dict() for worker in workforce_state.workers],
                    "requests": [request_item.to_json_dict() for request_item in workforce_state.requests],
                    "decisions": [decision.to_json_dict() for decision in workforce_state.decisions],
                }
            ),
            "workflow_store": (
                None
                if workflow_descriptors is None or workflow_executions is None
                else _workflow_inventory_payload(workflow_descriptors, workflow_executions)
            ),
        }
    )

    return CoordinationRecoveryReport(
        request_id=request.request_id,
        restored_components=tuple(restored_components),
        inspected_components=tuple(inspected_components),
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        job_count=0 if job_state is None else len(job_state.descriptors),
        work_queue_entry_count=0 if work_queue_state is None else len(work_queue_state.entries),
        team_queue_state_count=0 if team_queue_states is None else len(team_queue_states),
        workforce_worker_count=0 if workforce_state is None else len(workforce_state.workers),
        workforce_request_count=0 if workforce_state is None else len(workforce_state.requests),
        workforce_decision_count=0 if workforce_state is None else len(workforce_state.decisions),
        workflow_descriptor_count=0 if workflow_descriptors is None else len(workflow_descriptors),
        workflow_execution_count=0 if workflow_executions is None else len(workflow_executions),
        cross_store_checks_passed=request.require_cross_store_consistency,
        goal_descriptor_count=0 if goal_state is None else len(goal_state.descriptors),
        goal_state_count=0 if goal_state is None else len(goal_state.states),
        goal_plan_count=0 if goal_state is None else len(goal_state.plans),
        goal_replan_count=0 if goal_state is None else len(goal_state.replans),
        state_hash=state_hash,
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def reconcile_team_queues(
    loop: OperatorLoop,
    request: TeamQueueReconcileRequest,
) -> TeamQueueReconcileReport:
    """Assess or restore persisted team queue-state witnesses through the governed path."""
    started_at = loop.runtime.clock()
    action_class = (
        ActionClass.EXECUTE_WRITE
        if request.restore_from_store
        else ActionClass.ANALYZE
    )
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            "team_queue_restore"
            if request.restore_from_store
            else "team_queue_assessment"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return TeamQueueReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            queue_state_count=0,
            team_ids=(),
            total_queued_jobs=0,
            total_assigned_jobs=0,
            total_waiting_jobs=0,
            total_overloaded_workers=0,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked team queue reconciliation",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id="team_queue_reconcile",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=request.restore_from_store,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return TeamQueueReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            queue_state_count=0,
            team_ids=(),
            total_queued_jobs=0,
            total_assigned_jobs=0,
            total_waiting_jobs=0,
            total_overloaded_workers=0,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked team queue reconciliation",
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

    if request.restore_from_store:
        store = loop.runtime.team_queue_store
        if store is None:
            return TeamQueueReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                queue_state_count=0,
                team_ids=(),
                total_queued_jobs=0,
                total_assigned_jobs=0,
                total_waiting_jobs=0,
                total_overloaded_workers=0,
                errors=(
                    execution_error(
                        error_code="team_queue_store_not_configured",
                        message="team queue restore requires a configured team queue store",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        try:
            store.restore_queue_states(loop.runtime.team_engine)
        except (PersistenceError, RuntimeCoreInvariantError) as exc:
            return TeamQueueReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                queue_state_count=0,
                team_ids=(),
                total_queued_jobs=0,
                total_assigned_jobs=0,
                total_waiting_jobs=0,
                total_overloaded_workers=0,
                errors=(
                    execution_error(
                        error_code="team_queue_restore_failed",
                        message=str(exc),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    states = loop.runtime.team_engine.list_queue_states()
    if request.team_ids:
        requested_team_ids = set(request.team_ids)
        states = tuple(state for state in states if state.team_id in requested_team_ids)
        missing_team_ids = tuple(
            team_id for team_id in request.team_ids if team_id not in {state.team_id for state in states}
        )
        if missing_team_ids:
            return TeamQueueReconcileReport(
                request_id=request.request_id,
                restored=request.restore_from_store,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                queue_state_count=0,
                team_ids=(),
                total_queued_jobs=0,
                total_assigned_jobs=0,
                total_waiting_jobs=0,
                total_overloaded_workers=0,
                errors=(
                    validation_error(
                        error_code="team_queue_state_missing",
                        message="requested team queue state not found",
                        source_plane=SourcePlane.COORDINATION,
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=missing_team_ids,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    selected_team_ids = tuple(state.team_id for state in states)
    return TeamQueueReconcileReport(
        request_id=request.request_id,
        restored=request.restore_from_store,
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        queue_state_count=len(states),
        team_ids=selected_team_ids,
        total_queued_jobs=sum(state.queued_jobs for state in states),
        total_assigned_jobs=sum(state.assigned_jobs for state in states),
        total_waiting_jobs=sum(state.waiting_jobs for state in states),
        total_overloaded_workers=sum(state.overloaded_workers for state in states),
        state_hash=_queue_state_hash(states),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def reconcile_work_queue(
    loop: OperatorLoop,
    request: WorkQueueReconcileRequest,
) -> WorkQueueReconcileReport:
    """Assess or restore persisted work-queue entry carriers through the governed path."""
    started_at = loop.runtime.clock()
    action_class = (
        ActionClass.EXECUTE_WRITE
        if request.restore_from_store
        else ActionClass.ANALYZE
    )
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            "work_queue_restore"
            if request.restore_from_store
            else "work_queue_assessment"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return WorkQueueReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            entry_count=0,
            entry_ids=(),
            next_entry_id=None,
            assigned_person_entry_count=0,
            assigned_team_entry_count=0,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked work queue reconciliation",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id="work_queue_reconcile",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=request.restore_from_store,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return WorkQueueReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            entry_count=0,
            entry_ids=(),
            next_entry_id=None,
            assigned_person_entry_count=0,
            assigned_team_entry_count=0,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked work queue reconciliation",
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

    if request.restore_from_store:
        store = loop.runtime.work_queue_store
        if store is None:
            return WorkQueueReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                entry_count=0,
                entry_ids=(),
                next_entry_id=None,
                assigned_person_entry_count=0,
                assigned_team_entry_count=0,
                errors=(
                    execution_error(
                        error_code="work_queue_store_not_configured",
                        message="work queue restore requires a configured work queue store",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        try:
            store.restore_state(loop.runtime.work_queue)
        except (PersistenceError, RuntimeCoreInvariantError) as exc:
            return WorkQueueReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                entry_count=0,
                entry_ids=(),
                next_entry_id=None,
                assigned_person_entry_count=0,
                assigned_team_entry_count=0,
                errors=(
                    execution_error(
                        error_code="work_queue_restore_failed",
                        message=str(exc),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    entries = loop.runtime.work_queue.list_entries()
    if request.entry_ids:
        requested_entry_ids = set(request.entry_ids)
        entries = tuple(entry for entry in entries if entry.entry_id in requested_entry_ids)
        available_entry_ids = {entry.entry_id for entry in entries}
        missing_entry_ids = tuple(
            entry_id for entry_id in request.entry_ids if entry_id not in available_entry_ids
        )
        if missing_entry_ids:
            return WorkQueueReconcileReport(
                request_id=request.request_id,
                restored=request.restore_from_store,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                entry_count=0,
                entry_ids=(),
                next_entry_id=None,
                assigned_person_entry_count=0,
                assigned_team_entry_count=0,
                errors=(
                    validation_error(
                        error_code="work_queue_entry_missing",
                        message="requested work queue entry not found",
                        source_plane=SourcePlane.COORDINATION,
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=missing_entry_ids,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    entry_ids = tuple(entry.entry_id for entry in entries)
    return WorkQueueReconcileReport(
        request_id=request.request_id,
        restored=request.restore_from_store,
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        entry_count=len(entries),
        entry_ids=entry_ids,
        next_entry_id=(entries[0].entry_id if entries else None),
        assigned_person_entry_count=sum(
            1 for entry in entries if entry.assigned_to_person_id is not None
        ),
        assigned_team_entry_count=sum(
            1 for entry in entries if entry.assigned_to_team_id is not None
        ),
        state_hash=_queue_state_hash(entries),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def reconcile_jobs(
    loop: OperatorLoop,
    request: JobReconcileRequest,
) -> JobReconcileReport:
    """Assess or restore persisted job runtime carriers through the governed path."""
    started_at = loop.runtime.clock()
    action_class = (
        ActionClass.EXECUTE_WRITE
        if request.restore_from_store
        else ActionClass.ANALYZE
    )
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            "job_runtime_restore"
            if request.restore_from_store
            else "job_runtime_assessment"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return JobReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0,
            job_ids=(),
            active_job_count=0,
            completed_job_count=0,
            failed_job_count=0,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked job reconciliation",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id="job_reconcile",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=request.restore_from_store,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return JobReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            job_count=0,
            job_ids=(),
            active_job_count=0,
            completed_job_count=0,
            failed_job_count=0,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked job reconciliation",
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

    if request.restore_from_store:
        store = loop.runtime.job_store
        if store is None:
            return JobReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                job_count=0,
                job_ids=(),
                active_job_count=0,
                completed_job_count=0,
                failed_job_count=0,
                errors=(
                    execution_error(
                        error_code="job_store_not_configured",
                        message="job restore requires a configured job store",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        try:
            store.restore_state(loop.runtime.job_engine)
        except (PersistenceError, RuntimeCoreInvariantError) as exc:
            return JobReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                job_count=0,
                job_ids=(),
                active_job_count=0,
                completed_job_count=0,
                failed_job_count=0,
                errors=(
                    execution_error(
                        error_code="job_restore_failed",
                        message=str(exc),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    descriptors = loop.runtime.job_engine.list_job_descriptors()
    states = loop.runtime.job_engine.list_job_states()
    if request.job_ids:
        requested_job_ids = set(request.job_ids)
        descriptors = tuple(
            descriptor for descriptor in descriptors if descriptor.job_id in requested_job_ids
        )
        states = tuple(
            state for state in states if state.job_id in requested_job_ids
        )
        available_job_ids = {descriptor.job_id for descriptor in descriptors}
        missing_job_ids = tuple(
            job_id for job_id in request.job_ids if job_id not in available_job_ids
        )
        if missing_job_ids:
            return JobReconcileReport(
                request_id=request.request_id,
                restored=request.restore_from_store,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                job_count=0,
                job_ids=(),
                active_job_count=0,
                completed_job_count=0,
                failed_job_count=0,
                errors=(
                    validation_error(
                        error_code="job_runtime_missing",
                        message="requested job runtime witness not found",
                        source_plane=SourcePlane.COORDINATION,
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=missing_job_ids,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    terminal_statuses = {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.ARCHIVED,
    }
    selected_job_ids = tuple(descriptor.job_id for descriptor in descriptors)
    return JobReconcileReport(
        request_id=request.request_id,
        restored=request.restore_from_store,
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        job_count=len(descriptors),
        job_ids=selected_job_ids,
        active_job_count=sum(1 for state in states if state.status not in terminal_statuses),
        completed_job_count=sum(1 for state in states if state.status is JobStatus.COMPLETED),
        failed_job_count=sum(1 for state in states if state.status is JobStatus.FAILED),
        state_hash=_job_runtime_hash(descriptors, states),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


def reconcile_goals(
    loop: OperatorLoop,
    request: GoalReconcileRequest,
) -> GoalReconcileReport:
    """Assess or restore persisted goal runtime witnesses through the governed path."""
    started_at = loop.runtime.clock()
    action_class = (
        ActionClass.EXECUTE_WRITE
        if request.restore_from_store
        else ActionClass.ANALYZE
    )
    autonomy_decision = loop.runtime.autonomy.evaluate(
        action_class,
        action_description=(
            "goal_runtime_restore"
            if request.restore_from_store
            else "goal_runtime_assessment"
        ),
    )
    if autonomy_decision.status is not AutonomyDecisionStatus.ALLOWED:
        return GoalReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=None,
            policy_status=None,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            goal_count=0,
            goal_ids=(),
            active_goal_count=0,
            completed_goal_count=0,
            failed_goal_count=0,
            plan_count=0,
            replan_count=0,
            errors=(
                policy_error(
                    error_code="autonomy_blocked",
                    message="autonomy policy blocked goal reconciliation",
                    recoverability=Recoverability.APPROVAL_REQUIRED,
                    related_ids=(autonomy_decision.decision_id,),
                    context={
                        "autonomy_mode": loop.runtime.autonomy.mode.value,
                        "autonomy_status": autonomy_decision.status.value,
                        "autonomy_reason": autonomy_decision.reason,
                    },
                ),
            ),
            started_at=started_at,
            completed_at=loop.runtime.clock(),
        )

    policy_decision = loop.runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id=request.subject_id,
            goal_id="goal_reconcile",
            issued_at=loop.runtime.clock(),
            policy_pack_id=loop.runtime.config.policy_pack_id,
            policy_pack_version=loop.runtime.config.policy_pack_version,
            has_write_effects=request.restore_from_store,
        ),
        build_policy_decision,
    )
    if policy_decision.status is not PolicyDecisionStatus.ALLOW:
        return GoalReconcileReport(
            request_id=request.request_id,
            restored=False,
            policy_decision_id=policy_decision.decision_id,
            policy_status=policy_decision.status.value,
            autonomy_mode=loop.runtime.autonomy.mode.value,
            autonomy_decision=autonomy_decision.status.value,
            goal_count=0,
            goal_ids=(),
            active_goal_count=0,
            completed_goal_count=0,
            failed_goal_count=0,
            plan_count=0,
            replan_count=0,
            errors=(
                policy_error(
                    error_code=f"policy_{policy_decision.status.value}",
                    message="policy gate blocked goal reconciliation",
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

    if request.restore_from_store:
        store = loop.runtime.goal_store
        if store is None:
            return GoalReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                goal_count=0,
                goal_ids=(),
                active_goal_count=0,
                completed_goal_count=0,
                failed_goal_count=0,
                plan_count=0,
                replan_count=0,
                errors=(
                    execution_error(
                        error_code="goal_store_not_configured",
                        message="goal restore requires a configured goal store",
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )
        try:
            store.restore_state(loop.runtime.goal_reasoning_engine)
        except (PersistenceError, RuntimeCoreInvariantError) as exc:
            return GoalReconcileReport(
                request_id=request.request_id,
                restored=False,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                goal_count=0,
                goal_ids=(),
                active_goal_count=0,
                completed_goal_count=0,
                failed_goal_count=0,
                plan_count=0,
                replan_count=0,
                errors=(
                    execution_error(
                        error_code="goal_restore_failed",
                        message=str(exc),
                        recoverability=Recoverability.FATAL_FOR_RUN,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    descriptors = loop.runtime.goal_reasoning_engine.list_goal_descriptors()
    states = loop.runtime.goal_reasoning_engine.list_goal_states()
    plans = loop.runtime.goal_reasoning_engine.list_plans()
    replans = loop.runtime.goal_reasoning_engine.list_replan_records()

    if request.goal_ids:
        requested_goal_ids = set(request.goal_ids)
        descriptors = tuple(
            descriptor for descriptor in descriptors if descriptor.goal_id in requested_goal_ids
        )
        states = tuple(
            state for state in states if state.goal_id in requested_goal_ids
        )
        plans = tuple(
            plan for plan in plans if plan.goal_id in requested_goal_ids
        )
        replans = tuple(
            record for record in replans if record.goal_id in requested_goal_ids
        )
        available_goal_ids = {descriptor.goal_id for descriptor in descriptors}
        missing_goal_ids = tuple(
            goal_id for goal_id in request.goal_ids if goal_id not in available_goal_ids
        )
        if missing_goal_ids:
            return GoalReconcileReport(
                request_id=request.request_id,
                restored=request.restore_from_store,
                policy_decision_id=policy_decision.decision_id,
                policy_status=policy_decision.status.value,
                autonomy_mode=loop.runtime.autonomy.mode.value,
                autonomy_decision=autonomy_decision.status.value,
                goal_count=0,
                goal_ids=(),
                active_goal_count=0,
                completed_goal_count=0,
                failed_goal_count=0,
                plan_count=0,
                replan_count=0,
                errors=(
                    validation_error(
                        error_code="goal_runtime_missing",
                        message="requested goal runtime witness not found",
                        source_plane=SourcePlane.COORDINATION,
                        recoverability=Recoverability.FATAL_FOR_RUN,
                        related_ids=missing_goal_ids,
                    ),
                ),
                started_at=started_at,
                completed_at=loop.runtime.clock(),
            )

    terminal_statuses = {
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.ARCHIVED,
    }
    selected_goal_ids = tuple(descriptor.goal_id for descriptor in descriptors)
    return GoalReconcileReport(
        request_id=request.request_id,
        restored=request.restore_from_store,
        policy_decision_id=policy_decision.decision_id,
        policy_status=policy_decision.status.value,
        autonomy_mode=loop.runtime.autonomy.mode.value,
        autonomy_decision=autonomy_decision.status.value,
        goal_count=len(descriptors),
        goal_ids=selected_goal_ids,
        active_goal_count=sum(
            1 for state in states if state.status not in terminal_statuses
        ),
        completed_goal_count=sum(
            1 for state in states if state.status is GoalStatus.COMPLETED
        ),
        failed_goal_count=sum(
            1 for state in states if state.status is GoalStatus.FAILED
        ),
        plan_count=len(plans),
        replan_count=len(replans),
        state_hash=_goal_runtime_hash(descriptors, states, plans, replans),
        started_at=started_at,
        completed_at=loop.runtime.clock(),
    )


__all__ = [
    "recover_coordination_state",
    "reconcile_goals",
    "reconcile_jobs",
    "reconcile_work_queue",
    "reconcile_team_queues",
    "reconcile_workforce",
    "resume_goal",
    "resume_workflow",
    "run_goal",
    "run_skill",
    "run_workflow",
]
