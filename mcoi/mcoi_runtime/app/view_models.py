"""Purpose: typed read-only view models for the operator console.
Governance scope: operator-facing display logic only.
Dependencies: runtime contracts, core artifacts.
Invariants:
  - View models are read-only projections of existing artifacts.
  - No runtime mutation. No new semantics.
  - IDs, states, and structured errors are surfaced directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TYPE_CHECKING

from mcoi_runtime.app.operator_loop import GoalRunReport, OperatorRunReport, SkillRunReport, WorkflowRunReport
from mcoi_runtime.contracts.job import JobDescriptor, JobState, JobStatus, JobPriority, SlaStatus
from mcoi_runtime.contracts.roles import TeamQueueState, WorkloadSnapshot
from mcoi_runtime.core.coordination import CoordinationEngine
from mcoi_runtime.contracts.temporal import TemporalTask, StateTransition, ResumeCheckpoint
from mcoi_runtime.core.errors import StructuredError
from mcoi_runtime.core.memory import MemoryTier, PromotionResult
from mcoi_runtime.core.persisted_replay import PersistedReplayResult
from mcoi_runtime.core.replay_engine import ReplayVerdict
from mcoi_runtime.core.runbook import RunbookAdmissionResult, RunbookEntry

from mcoi_runtime.contracts.simulation import SimulationComparison, SimulationVerdict

if TYPE_CHECKING:
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
    autonomy_mode: str | None = None
    autonomy_decision: str | None = None

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
            autonomy_mode=report.autonomy_mode,
            autonomy_decision=report.autonomy_decision,
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
