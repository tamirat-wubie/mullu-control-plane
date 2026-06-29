"""Purpose: typed read-only view models for the operator console.
Governance scope: operator-facing display logic only.
Dependencies: runtime contracts, core artifacts.
Invariants:
  - View models are read-only projections of existing artifacts.
  - No runtime mutation. No new semantics.
  - IDs, states, and structured errors are surfaced directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TYPE_CHECKING

from mcoi_runtime.app.operator_loop import GoalRunReport, OperatorRunReport, SkillRunReport, WorkflowRunReport
from mcoi_runtime.app.skill_promotion_read_models import (
    SkillPromotionReceiptReadReport,
    SkillPromotionReceiptSummary,
)
from mcoi_runtime.contracts.conversation import ConversationThread
from mcoi_runtime.contracts.job import JobDescriptor, JobState
from mcoi_runtime.contracts.roles import TeamQueueState, WorkloadSnapshot
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.core.job_integration import JobConversationBridge, WHQRJobClarificationReplay
from mcoi_runtime.contracts.temporal import TemporalTask
from mcoi_runtime.core.errors import StructuredError
from mcoi_runtime.core.persisted_replay import PersistedReplayResult
from mcoi_runtime.core.runbook import RunbookAdmissionResult
from mcoi_runtime.whqr.clarification import build_binding_map_from_clarification_responses

from mcoi_runtime.contracts.simulation import SimulationComparison, SimulationVerdict
from mcoi_runtime.contracts.provider_attribution import ProviderAttribution

if TYPE_CHECKING:
    from mcoi_runtime.app.autonomous_request import AutonomousRequestEpisodeReceipt
    from mcoi_runtime.core.operational_graph import OperationalGraph


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RunSummaryView:
    """Top-level summary of one operator run."""

    request_id: str
    goal_id: str
    policy_decision_id: str
    execution_id: str | None
    verification_id: str | None
    completed: bool
    dispatched: bool
    verification_closed: bool
    validation_passed: bool
    validation_error: str | None
    verification_error: str | None
    structured_errors: tuple[ErrorView, ...]
    world_state_hash: str | None = None
    world_state_entity_count: int = 0
    world_state_contradiction_count: int = 0
    degraded_capabilities: tuple[str, ...] = ()
    escalation_recommendations: tuple[str, ...] = ()
    provider_count: int = 0
    unhealthy_providers: tuple[str, ...] = ()
    execution_route: str | None = None
    integration_provider_id: str | None = None
    communication_provider_id: str | None = None
    model_provider_id: str | None = None
    provider_attributions: tuple[ProviderAttribution, ...] = ()
    provider_attribution_count: int = 0
    receipt_attributed_provider_operation_count: int = 0
    routing_attributed_provider_operation_count: int = 0
    plane_attributed_provider_operation_count: int = 0
    autonomy_mode: str | None = None
    autonomy_decision: str | None = None
    mil_program_id: str | None = None
    mil_instruction_count: int = 0
    mil_verification_passed: bool | None = None
    mil_verification_issues: tuple[str, ...] = ()
    mil_instruction_trace: tuple[str, ...] = ()
    mil_audit_record_id: str | None = None
    mil_trace_ids: tuple[str, ...] = ()

    @staticmethod
    def from_report(report: OperatorRunReport) -> RunSummaryView:
        return RunSummaryView(
            request_id=report.request_id,
            goal_id=report.goal_id,
            policy_decision_id=report.policy_decision_id,
            execution_id=report.execution_id,
            verification_id=report.verification_id,
            completed=report.completed,
            dispatched=report.dispatched,
            verification_closed=report.verification_closed,
            validation_passed=report.validation_passed,
            validation_error=report.validation_error,
            verification_error=report.verification_error,
            structured_errors=tuple(ErrorView.from_error(e) for e in report.structured_errors),
            world_state_hash=report.world_state_hash,
            world_state_entity_count=report.world_state_entity_count,
            world_state_contradiction_count=report.world_state_contradiction_count,
            degraded_capabilities=report.degraded_capabilities,
            escalation_recommendations=report.escalation_recommendations,
            provider_count=report.provider_count,
            unhealthy_providers=report.unhealthy_providers,
            execution_route=report.execution_route,
            integration_provider_id=report.integration_provider_id,
            communication_provider_id=report.communication_provider_id,
            model_provider_id=report.model_provider_id,
            provider_attributions=report.provider_attributions,
            provider_attribution_count=report.provider_attribution_count,
            receipt_attributed_provider_operation_count=report.receipt_attributed_provider_operation_count,
            routing_attributed_provider_operation_count=report.routing_attributed_provider_operation_count,
            plane_attributed_provider_operation_count=report.plane_attributed_provider_operation_count,
            autonomy_mode=report.autonomy_mode,
            autonomy_decision=report.autonomy_decision,
            mil_program_id=report.mil_program_id,
            mil_instruction_count=report.mil_instruction_count,
            mil_verification_passed=report.mil_verification_passed,
            mil_verification_issues=report.mil_verification_issues,
            mil_instruction_trace=report.mil_instruction_trace,
            mil_audit_record_id=report.mil_audit_record_id,
            mil_trace_ids=report.mil_trace_ids,
        )


@dataclass(frozen=True, slots=True)
class ErrorView:
    """Structured error for operator display."""

    error_code: str
    family: str
    message: str
    source_plane: str
    recoverability: str
    related_ids: tuple[str, ...]

    @staticmethod
    def from_error(error: StructuredError) -> ErrorView:
        return ErrorView(
            error_code=error.error_code,
            family=error.family.value,
            message=error.message,
            source_plane=error.source_plane.value,
            recoverability=error.recoverability.value,
            related_ids=error.related_ids,
        )


# ---------------------------------------------------------------------------
# Execution summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExecutionSummaryView:
    """Execution outcome for operator display."""

    dispatched: bool
    execution_id: str | None
    status: str | None
    goal_id: str
    effect_count: int
    verification_closed: bool
    verification_status: str | None

    @staticmethod
    def from_report(report: OperatorRunReport) -> ExecutionSummaryView:
        if report.execution_result is None:
            return ExecutionSummaryView(
                dispatched=False,
                execution_id=None,
                status=None,
                goal_id=report.goal_id,
                effect_count=0,
                verification_closed=report.verification_closed,
                verification_status=None,
            )
        return ExecutionSummaryView(
            dispatched=True,
            execution_id=report.execution_result.execution_id,
            status=report.execution_result.status.value,
            goal_id=report.execution_result.goal_id,
            effect_count=len(report.execution_result.actual_effects),
            verification_closed=report.verification_closed,
            verification_status=None,
        )


# ---------------------------------------------------------------------------
# Replay summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ReplaySummaryView:
    """Persisted replay status for operator display."""

    replay_id: str
    trace_id: str
    verdict: str
    ready: bool
    trace_found: bool
    trace_hash_matches: bool | None
    trace_lookup_reason: str
    reasons: tuple[str, ...]

    @staticmethod
    def from_result(result: PersistedReplayResult) -> ReplaySummaryView:
        return ReplaySummaryView(
            replay_id=result.replay_id,
            trace_id=result.trace_id,
            verdict=result.validation.verdict.value,
            ready=result.validation.ready,
            trace_found=result.trace_found,
            trace_hash_matches=result.trace_hash_matches,
            trace_lookup_reason=result.trace_lookup_reason,
            reasons=result.validation.reasons,
        )


# ---------------------------------------------------------------------------
# Temporal summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TemporalTaskView:
    """Temporal task for operator display."""

    task_id: str
    goal_id: str
    state: str
    trigger_type: str
    deadline: str | None
    has_checkpoint: bool
    transition_count: int

    @staticmethod
    def from_task(
        task: TemporalTask,
        *,
        has_checkpoint: bool = False,
        transition_count: int = 0,
    ) -> TemporalTaskView:
        return TemporalTaskView(
            task_id=task.task_id,
            goal_id=task.goal_id,
            state=task.state.value,
            trigger_type=task.trigger.trigger_type.value,
            deadline=task.deadline,
            has_checkpoint=has_checkpoint,
            transition_count=transition_count,
        )


# ---------------------------------------------------------------------------
# Coordination summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CoordinationSummaryView:
    """Coordination artifacts for operator display."""

    delegation_count: int
    handoff_count: int
    merge_count: int
    unresolved_conflict_count: int

    @staticmethod
    def from_engine(engine: CoordinationEngine) -> CoordinationSummaryView:
        """Build from a CoordinationEngine instance using public properties."""
        return CoordinationSummaryView(
            delegation_count=engine.delegation_count,
            handoff_count=engine.handoff_count,
            merge_count=engine.merge_count,
            unresolved_conflict_count=len(engine.list_unresolved_conflicts()),
        )


# ---------------------------------------------------------------------------
# Runbook summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RunbookSummaryView:
    """Runbook admission result for operator display."""

    runbook_id: str
    status: str
    reasons: tuple[str, ...]
    provenance_execution_id: str | None
    provenance_replay_id: str | None

    @staticmethod
    def from_admission(result: RunbookAdmissionResult) -> RunbookSummaryView:
        return RunbookSummaryView(
            runbook_id=result.runbook_id,
            status=result.status.value,
            reasons=result.reasons,
            provenance_execution_id=(
                result.entry.provenance.execution_id if result.entry else None
            ),
            provenance_replay_id=(
                result.entry.provenance.replay_id if result.entry else None
            ),
        )


# ---------------------------------------------------------------------------
# Skill summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SkillSummaryView:
    """Skill execution result for operator display."""

    request_id: str
    goal_id: str
    skill_id: str | None
    status: str
    completed: bool
    selected_from: int
    step_count: int
    failed_step: str | None
    structured_errors: tuple[ErrorView, ...]
    lifecycle_transition_warning: str

    @staticmethod
    def from_report(report: SkillRunReport) -> SkillSummaryView:
        step_count = 0
        failed_step = None
        if report.execution_record and report.execution_record.outcome.step_outcomes:
            step_count = len(report.execution_record.outcome.step_outcomes)
            for so in report.execution_record.outcome.step_outcomes:
                if so.status.value != "succeeded":
                    failed_step = so.step_id
                    break

        return SkillSummaryView(
            request_id=report.request_id,
            goal_id=report.goal_id,
            skill_id=report.skill_id,
            status=report.status.value,
            completed=report.completed,
            selected_from=(
                len(report.selection.candidates_considered) if report.selection else 0
            ),
            step_count=step_count,
            failed_step=failed_step,
            structured_errors=tuple(ErrorView.from_error(e) for e in report.structured_errors),
            lifecycle_transition_warning=report.lifecycle_transition_warning,
        )


@dataclass(frozen=True, slots=True)
class SkillPromotionReceiptItemView:
    """One promotion receipt row for operator display."""

    evidence_id: str
    skill_id: str
    target_lifecycle: str
    execution_record_count: int
    evidence_ref_count: int
    verification_count: int
    created_at: str
    reason: str

    @staticmethod
    def from_summary(summary: SkillPromotionReceiptSummary) -> "SkillPromotionReceiptItemView":
        return SkillPromotionReceiptItemView(
            evidence_id=summary.evidence_id,
            skill_id=summary.skill_id,
            target_lifecycle=summary.target_lifecycle.value,
            execution_record_count=len(summary.execution_record_ids),
            evidence_ref_count=len(summary.evidence_refs),
            verification_count=len(summary.verification_ids),
            created_at=summary.created_at,
            reason=summary.reason,
        )


@dataclass(frozen=True, slots=True)
class SkillPromotionReceiptReadView:
    """Skill promotion receipt read model for operator display."""

    request_id: str
    store_configured: bool
    receipt_count: int
    skill_id_filter: str
    target_lifecycle_filter: str | None
    receipts: tuple[SkillPromotionReceiptItemView, ...]
    structured_errors: tuple[ErrorView, ...]

    @staticmethod
    def from_report(report: SkillPromotionReceiptReadReport) -> "SkillPromotionReceiptReadView":
        return SkillPromotionReceiptReadView(
            request_id=report.request_id,
            store_configured=report.store_configured,
            receipt_count=report.receipt_count,
            skill_id_filter=report.skill_id_filter,
            target_lifecycle_filter=(
                report.target_lifecycle_filter.value
                if report.target_lifecycle_filter is not None
                else None
            ),
            receipts=tuple(SkillPromotionReceiptItemView.from_summary(item) for item in report.receipts),
            structured_errors=tuple(ErrorView.from_error(error) for error in report.errors),
        )


# ---------------------------------------------------------------------------
# Workflow summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WorkflowSummaryView:
    """Workflow execution result for operator display."""

    workflow_id: str
    status: str
    stage_count: int
    completed_stages: int
    failed_stage_id: str | None

    @staticmethod
    def from_report(report: WorkflowRunReport) -> WorkflowSummaryView:
        completed = sum(
            1 for s in report.stage_summaries
            if s.status.value == "completed"
        )
        failed_stage = None
        for s in report.stage_summaries:
            if s.status.value == "failed":
                failed_stage = s.stage_id
                break

        return WorkflowSummaryView(
            workflow_id=report.workflow_id,
            status=report.status.value,
            stage_count=len(report.stage_summaries),
            completed_stages=completed,
            failed_stage_id=failed_stage,
        )


# ---------------------------------------------------------------------------
# Autonomous request summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AutonomousRequestEpisodeSummaryView:
    """Autonomous request episode continuation state for operator display."""

    episode_id: str
    goal_id: str
    automation_state: str
    solver_outcome: str
    action_count: int
    dispatched_count: int
    prompt_count: int
    workflow_descriptor_ref: str | None
    workflow_stage_count: int
    workflow_approval_stage_count: int
    workflow_external_stage_count: int
    plan_receipt_ref: str | None
    rollback_ref: str
    execution_stage_ids: tuple[str, ...] = ()
    step_receipt_refs: tuple[str, ...] = ()
    stage_receipt_bindings: tuple[Mapping[str, str], ...] = ()
    stage_execution_bindings: tuple[Mapping[str, object], ...] = ()
    stage_verification_bindings: tuple[Mapping[str, object], ...] = ()
    stage_policy_bindings: tuple[Mapping[str, object], ...] = ()
    stage_rollback_bindings: tuple[Mapping[str, object], ...] = ()
    stage_dependency_bindings: tuple[Mapping[str, object], ...] = ()
    stage_repair_bindings: tuple[Mapping[str, object], ...] = ()
    stage_error_bindings: tuple[Mapping[str, object], ...] = ()
    stage_outcome_bindings: tuple[Mapping[str, object], ...] = ()
    stage_next_action_bindings: tuple[Mapping[str, object], ...] = ()
    stage_attention_bindings: tuple[Mapping[str, object], ...] = ()

    @staticmethod
    def from_receipt(
        receipt: AutonomousRequestEpisodeReceipt,
    ) -> "AutonomousRequestEpisodeSummaryView":
        return AutonomousRequestEpisodeSummaryView(
            episode_id=receipt.episode_id,
            goal_id=receipt.goal_id,
            automation_state=receipt.automation_state,
            solver_outcome=receipt.solver_outcome,
            action_count=receipt.action_count,
            dispatched_count=receipt.dispatched_count,
            prompt_count=receipt.prompt_count,
            workflow_descriptor_ref=receipt.workflow_descriptor_ref,
            workflow_stage_count=receipt.workflow_stage_count,
            workflow_approval_stage_count=receipt.workflow_approval_stage_count,
            workflow_external_stage_count=receipt.workflow_external_stage_count,
            plan_receipt_ref=receipt.plan_receipt_ref,
            execution_stage_ids=tuple(
                step.plan_stage_id for step in receipt.step_receipts if step.plan_stage_id is not None
            ),
            step_receipt_refs=receipt.receipt_refs,
            stage_receipt_bindings=tuple(
                {"stage_id": step.plan_stage_id, "receipt_ref": step.receipt_ref}
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_execution_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "action_class": step.action_class,
                    "boundary": step.boundary,
                    "autonomy_status": step.autonomy_status,
                    "dispatched": step.dispatched,
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_verification_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "verification_keys": list(step.verification_keys),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_policy_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "autonomy_decision_id": step.autonomy_decision_id,
                    "autonomy_status": step.autonomy_status,
                    "autonomy_reason": step.autonomy_reason,
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_rollback_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "rollback_ref": receipt.rollback_ref,
                    "rollback_scope": _autonomous_request_rollback_scope(step.action_class),
                    "compensation_required": False,
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_dependency_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "predecessor_stage_ids": list(step.plan_predecessors),
                    "dependency_status": _autonomous_request_dependency_status(step.structured_error_codes),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_repair_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "attempt_count": step.attempt_count,
                    "retry_count": step.retry_count,
                    "repair_receipt_refs": [repair.receipt_ref for repair in step.repair_receipts],
                    "repair_status": _autonomous_request_repair_status(step.retry_count, step.validation_error),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_error_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "validation_error": step.validation_error,
                    "structured_error_codes": list(step.structured_error_codes),
                    "error_status": _autonomous_request_error_status(
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_outcome_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "dispatched": step.dispatched,
                    "validation_error": step.validation_error,
                    "error_status": _autonomous_request_error_status(
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                    "repair_status": _autonomous_request_repair_status(step.retry_count, step.validation_error),
                    "outcome_status": _autonomous_request_outcome_status(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_next_action_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "outcome_status": _autonomous_request_outcome_status(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                    "next_action": _autonomous_request_next_action(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            stage_attention_bindings=tuple(
                {
                    "stage_id": step.plan_stage_id,
                    "receipt_ref": step.receipt_ref,
                    "next_action": _autonomous_request_next_action(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                    "attention_status": _autonomous_request_attention_status(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                    "attention_priority": _autonomous_request_attention_priority(
                        step.dispatched,
                        step.retry_count,
                        step.validation_error,
                        step.structured_error_codes,
                    ),
                }
                for step in receipt.step_receipts
                if step.plan_stage_id is not None
            ),
            rollback_ref=receipt.rollback_ref,
        )


def _autonomous_request_rollback_scope(action_class: str) -> str:
    """Classify local autonomous demo rollback scope from the step action class."""
    if action_class == "execute_write":
        return "local_reversible"
    return "no_effect"


def _autonomous_request_dependency_status(structured_error_codes: tuple[str, ...]) -> str:
    """Classify whether a stage dependency chain admitted or blocked execution."""
    if "dependency_blocked" in structured_error_codes:
        return "blocked"
    return "satisfied"


def _autonomous_request_repair_status(retry_count: int, validation_error: str | None) -> str:
    """Classify whether a stage needed autonomous repair before settling."""
    if retry_count == 0:
        return "not_required"
    if validation_error is None:
        return "repaired"
    return "repair_failed"


def _autonomous_request_error_status(
    validation_error: str | None,
    structured_error_codes: tuple[str, ...],
) -> str:
    """Classify whether a stage emitted validation or structured error evidence."""
    if validation_error is None and not structured_error_codes:
        return "clear"
    if "dependency_blocked" in structured_error_codes:
        return "dependency_blocked"
    return "blocked"


def _autonomous_request_outcome_status(
    dispatched: bool,
    retry_count: int,
    validation_error: str | None,
    structured_error_codes: tuple[str, ...],
) -> str:
    """Classify the settled per-stage outcome from dispatch, repair, and error evidence."""
    if not dispatched:
        return "skipped"
    if retry_count > 0 and validation_error is not None:
        return "repair_failed"
    if retry_count > 0:
        return "repaired"
    if validation_error is not None or structured_error_codes:
        return "blocked"
    return "settled"


def _autonomous_request_next_action(
    dispatched: bool,
    retry_count: int,
    validation_error: str | None,
    structured_error_codes: tuple[str, ...],
) -> str:
    """Classify the next autonomous controller action from per-stage evidence."""
    outcome_status = _autonomous_request_outcome_status(
        dispatched,
        retry_count,
        validation_error,
        structured_error_codes,
    )
    if outcome_status == "skipped":
        return "halt_review"
    if "dependency_blocked" in structured_error_codes:
        return "unblock_dependency"
    if outcome_status == "repair_failed":
        return "halt_review"
    if outcome_status == "repaired":
        return "continue"
    if outcome_status == "blocked":
        return "repair"
    return "continue"


def _autonomous_request_attention_status(
    dispatched: bool,
    retry_count: int,
    validation_error: str | None,
    structured_error_codes: tuple[str, ...],
) -> str:
    """Classify whether the stage should be observed, repaired, unblocked, or reviewed."""
    next_action = _autonomous_request_next_action(
        dispatched,
        retry_count,
        validation_error,
        structured_error_codes,
    )
    if next_action == "halt_review":
        return "review"
    if next_action == "unblock_dependency":
        return "dependency_attention"
    if next_action == "repair":
        return "repair_attention"
    return "observe"


def _autonomous_request_attention_priority(
    dispatched: bool,
    retry_count: int,
    validation_error: str | None,
    structured_error_codes: tuple[str, ...],
) -> str:
    """Classify deterministic controller attention priority for a stage."""
    next_action = _autonomous_request_next_action(
        dispatched,
        retry_count,
        validation_error,
        structured_error_codes,
    )
    if next_action == "halt_review":
        return "critical"
    if next_action in {"unblock_dependency", "repair"}:
        return "high"
    if retry_count > 0:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Goal summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GoalSummaryView:
    """Goal execution result for operator display."""

    goal_id: str
    status: str
    priority: str
    sub_goal_count: int
    completed: int
    failed: int

    @staticmethod
    def from_report(report: GoalRunReport, priority: str = "normal") -> GoalSummaryView:
        return GoalSummaryView(
            goal_id=report.goal_id,
            status=report.status.value,
            priority=priority,
            sub_goal_count=len(report.completed_sub_goals) + len(report.failed_sub_goals),
            completed=len(report.completed_sub_goals),
            failed=len(report.failed_sub_goals),
        )


# ---------------------------------------------------------------------------
# Job summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JobSummaryView:
    """Job execution summary for operator display."""

    job_id: str
    name: str
    status: str
    priority: str
    sla_status: str
    assigned_to: str | None
    thread_id: str | None
    deadline: str | None

    @staticmethod
    def from_state(state: JobState, descriptor: JobDescriptor) -> JobSummaryView:
        return JobSummaryView(
            job_id=state.job_id,
            name=descriptor.name,
            status=state.status.value,
            priority=descriptor.priority.value,
            sla_status=state.sla_status.value if hasattr(state, "sla_status") and state.sla_status is not None else "unknown",
            assigned_to=state.assigned_to if hasattr(state, "assigned_to") else None,
            thread_id=state.thread_id if hasattr(state, "thread_id") else None,
            deadline=descriptor.deadline if hasattr(descriptor, "deadline") else None,
        )


@dataclass(frozen=True, slots=True)
class WHQRBindingClarificationStatusView:
    """WHQR binding clarification replay status for operator display."""

    thread_id: str
    request_count: int
    response_count: int
    pending_request_ids: tuple[str, ...]
    responded_request_ids: tuple[str, ...]
    accepted_count: int
    rejected_count: int
    rejected_reasons: tuple[str, ...]
    has_replay_pairs: bool
    binding_map_passed: bool
    next_step: str

    @staticmethod
    def from_thread(thread: ConversationThread) -> WHQRBindingClarificationStatusView:
        replay = JobConversationBridge.replay_whqr_binding_clarifications(thread)
        return WHQRBindingClarificationStatusView.from_replay(thread.thread_id, replay)

    @staticmethod
    def from_replay(
        thread_id: str,
        replay: WHQRJobClarificationReplay,
    ) -> WHQRBindingClarificationStatusView:
        request_ids = tuple(request.request_id for request in replay.requests)
        responded_ids = tuple(response.request_id for response in replay.responses)
        responded_id_set = set(responded_ids)
        pending_ids = tuple(request_id for request_id in request_ids if request_id not in responded_id_set)
        binding_map = (
            build_binding_map_from_clarification_responses(replay.requests, replay.responses)
            if replay.responses
            else None
        )
        accepted_count = binding_map.accepted_count if binding_map is not None else 0
        rejected_count = binding_map.rejected_count if binding_map is not None else 0
        rejected_reasons = (
            tuple(result.reason for result in binding_map.results if not result.accepted)
            if binding_map is not None
            else ()
        )
        return WHQRBindingClarificationStatusView(
            thread_id=thread_id,
            request_count=len(replay.requests),
            response_count=len(replay.responses),
            pending_request_ids=pending_ids,
            responded_request_ids=responded_ids,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            rejected_reasons=rejected_reasons,
            has_replay_pairs=replay.ready_for_binding_map,
            binding_map_passed=binding_map.passed if binding_map is not None else False,
            next_step=_whqr_binding_clarification_next_step(
                request_count=len(replay.requests),
                accepted_count=accepted_count,
                rejected_count=rejected_count,
                pending_count=len(pending_ids),
            ),
        )


def _whqr_binding_clarification_next_step(
    *,
    request_count: int,
    accepted_count: int,
    rejected_count: int,
    pending_count: int,
) -> str:
    if request_count == 0:
        return "no_whqr_binding_clarification"
    if rejected_count:
        return "resolve_whqr_clarification_response"
    if pending_count:
        return "await_whqr_binding_response"
    if accepted_count:
        return "ready_for_orchestration"
    return "await_whqr_binding_response"


# ---------------------------------------------------------------------------
# Team summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TeamSummaryView:
    """Team workload summary for operator display."""

    team_id: str
    total_workers: int
    available_workers: int
    overloaded_workers: int
    queued_jobs: int
    assigned_jobs: int

    @staticmethod
    def from_snapshot(
        workload: WorkloadSnapshot,
        queue_state: TeamQueueState,
    ) -> TeamSummaryView:
        """Build a team summary from a workload snapshot and queue state."""
        return TeamSummaryView(
            team_id=workload.team_id,
            total_workers=workload.total_workers,
            available_workers=workload.available_workers,
            overloaded_workers=workload.overloaded_workers,
            queued_jobs=queue_state.queued_jobs,
            assigned_jobs=queue_state.assigned_jobs,
        )


# ---------------------------------------------------------------------------
# Graph summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GraphSummaryView:
    """Operational graph summary for operator display."""

    total_nodes: int
    total_edges: int
    node_types: Mapping[str, int]
    unfulfilled_obligations: int

    @staticmethod
    def from_graph(graph: OperationalGraph) -> GraphSummaryView:
        """Build a summary view from an OperationalGraph instance."""
        nodes = graph.all_nodes()
        edges = graph.all_edges()
        obligations = graph.all_obligations()

        type_counts: dict[str, int] = {}
        for node in nodes:
            key = node.node_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        unfulfilled = sum(1 for o in obligations if not o.fulfilled)

        return GraphSummaryView(
            total_nodes=len(nodes),
            total_edges=len(edges),
            node_types=type_counts,
            unfulfilled_obligations=unfulfilled,
        )


# ---------------------------------------------------------------------------
# Simulation summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SimulationSummaryView:
    """Simulation result summary for operator display."""

    request_id: str
    option_count: int
    recommended_option_id: str
    verdict_type: str
    confidence: float
    top_risk_level: str

    @staticmethod
    def from_result(
        comparison: SimulationComparison,
        verdict: SimulationVerdict,
    ) -> SimulationSummaryView:
        """Build a summary view from simulation comparison and verdict."""
        return SimulationSummaryView(
            request_id=comparison.request_id,
            option_count=len(comparison.ranked_option_ids),
            recommended_option_id=verdict.recommended_option_id,
            verdict_type=verdict.verdict_type.value,
            confidence=verdict.confidence,
            top_risk_level=comparison.top_risk_level.value,
        )
