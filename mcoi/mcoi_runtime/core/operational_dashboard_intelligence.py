"""Operational dashboard intelligence for note-memory projections.

Purpose: expose project state, ready actions, blocked actions, blockers,
conflicts, repairs, high-intensity concepts, recent deltas, confidence trend,
workflow health, and execution readiness as a read-only dashboard model.
Governance scope: projection-only display, constructive/fracture separation,
readiness gating, repair visibility, and no execution authority.
Dependencies: dataclasses, Concept Boxes, projection, repair queue, compiled
actions, interrogation queue, simple platform checks, simple workflow plans,
simple onboarding guide, and runtime invariant helpers.
Invariants: dashboard state is derived from receipts and candidates; it never
promotes truth, executes actions, or hides blockers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox
from mcoi_runtime.core.inceptadive_interrogation_queue import InterrogationTask
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_action_compiler import CompiledMemoryAction
from mcoi_runtime.core.memory_repair_queue import MemoryRepairItem
from mcoi_runtime.core.note_memory_projection import CandidateActionStatus, NoteMemoryProjection
from mcoi_runtime.core.simple_platform import SimpleActionCheck, SimpleOnboardingGuide, SimpleWorkflowPlan


class WorkflowHealth(StrEnum):
    """Operational workflow health classes."""

    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    REPAIR_REQUIRED = "repair_required"


@dataclass(frozen=True)
class DashboardSimpleActionSummary:
    """Read-only dashboard projection for one simple action check."""

    action_ref: str
    outcome: str
    title: str
    message: str
    next_step: str
    proof_stamp_ref: str
    boundary_witness_ref: str
    blocked_reasons: tuple[str, ...]
    review_reasons: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple action cannot allow execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple action summary."""

        return {
            "action_ref": self.action_ref,
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "proof_stamp_ref": self.proof_stamp_ref,
            "boundary_witness_ref": self.boundary_witness_ref,
            "blocked_reasons": list(self.blocked_reasons),
            "review_reasons": list(self.review_reasons),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleWorkflowSummary:
    """Read-only dashboard projection for one simple workflow plan."""

    workflow_ref: str
    workflow: str
    label: str
    outcome: str
    title: str
    message: str
    next_step: str
    ready_count: int
    review_count: int
    blocked_count: int
    action_refs: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple workflow cannot allow execution")
        if min(self.ready_count, self.review_count, self.blocked_count) < 0:
            raise RuntimeCoreInvariantError("dashboard simple workflow counts cannot be negative")
        if self.outcome not in {"ready", "needs_review", "blocked"}:
            raise RuntimeCoreInvariantError("dashboard simple workflow outcome is unsupported")
        if self.ready_count + self.review_count + self.blocked_count != len(self.action_refs):
            raise RuntimeCoreInvariantError("dashboard simple workflow counts must match action refs")
        if self.outcome == "ready" and (self.review_count or self.blocked_count):
            raise RuntimeCoreInvariantError("dashboard simple workflow ready outcome cannot carry review or blocked counts")
        if self.outcome == "needs_review" and (self.review_count < 1 or self.blocked_count):
            raise RuntimeCoreInvariantError("dashboard simple workflow review outcome must carry review counts only")
        if self.outcome == "blocked" and self.blocked_count < 1:
            raise RuntimeCoreInvariantError("dashboard simple workflow blocked outcome must carry blocked counts")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple workflow summary."""

        return {
            "workflow_ref": self.workflow_ref,
            "workflow": self.workflow,
            "label": self.label,
            "outcome": self.outcome,
            "title": self.title,
            "message": self.message,
            "next_step": self.next_step,
            "ready_count": self.ready_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "action_refs": list(self.action_refs),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleStartGuideSummary:
    """Read-only dashboard projection for the simple onboarding guide."""

    title: str
    message: str
    recommended_commands: tuple[str, ...]
    outcomes: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple start guide cannot allow execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple start guide summary."""

        return {
            "title": self.title,
            "message": self.message,
            "recommended_commands": list(self.recommended_commands),
            "outcomes": list(self.outcomes),
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class DashboardSimpleHomeSummary:
    """Compact dashboard home projection for non-technical users."""

    title: str
    message: str
    primary_command: str
    ready_workflow_count: int
    review_workflow_count: int
    blocked_workflow_count: int
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard simple home cannot allow execution")
        if min(self.ready_workflow_count, self.review_workflow_count, self.blocked_workflow_count) < 0:
            raise RuntimeCoreInvariantError("dashboard simple home counts cannot be negative")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible simple dashboard home summary."""

        return {
            "title": self.title,
            "message": self.message,
            "primary_command": self.primary_command,
            "ready_workflow_count": self.ready_workflow_count,
            "review_workflow_count": self.review_workflow_count,
            "blocked_workflow_count": self.blocked_workflow_count,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class OperationalDashboardState:
    """Read-only operational dashboard model."""

    dashboard_id: str
    projection_id: str
    active_project_count: int
    ready_action_ids: tuple[str, ...]
    blocked_action_ids: tuple[str, ...]
    open_blocker_ids: tuple[str, ...]
    open_conflict_ids: tuple[str, ...]
    repair_ids: tuple[str, ...]
    stale_high_impact_claim_ids: tuple[str, ...]
    high_intensity_box_ids: tuple[str, ...]
    constructive_delta_ids: tuple[str, ...]
    fracture_delta_ids: tuple[str, ...]
    memory_confidence_trend: float
    workflow_health: WorkflowHealth
    execution_readiness: str
    interrogation_task_ids: tuple[str, ...]
    simple_action_summaries: tuple[DashboardSimpleActionSummary, ...] = ()
    simple_workflow_summaries: tuple[DashboardSimpleWorkflowSummary, ...] = ()
    simple_start_guide: DashboardSimpleStartGuideSummary | None = None
    simple_home_summary: DashboardSimpleHomeSummary | None = None
    simple_ready_action_refs: tuple[str, ...] = ()
    simple_review_action_refs: tuple[str, ...] = ()
    simple_blocked_action_refs: tuple[str, ...] = ()
    simple_ready_workflow_refs: tuple[str, ...] = ()
    simple_review_workflow_refs: tuple[str, ...] = ()
    simple_blocked_workflow_refs: tuple[str, ...] = ()
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard state cannot allow execution")
        if not 0.0 <= self.memory_confidence_trend <= 1.0:
            raise RuntimeCoreInvariantError("memory_confidence_trend must be in [0,1]")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible dashboard state."""

        return {
            "dashboard_id": self.dashboard_id,
            "projection_id": self.projection_id,
            "active_project_count": self.active_project_count,
            "ready_action_ids": list(self.ready_action_ids),
            "blocked_action_ids": list(self.blocked_action_ids),
            "open_blocker_ids": list(self.open_blocker_ids),
            "open_conflict_ids": list(self.open_conflict_ids),
            "repair_ids": list(self.repair_ids),
            "stale_high_impact_claim_ids": list(self.stale_high_impact_claim_ids),
            "high_intensity_box_ids": list(self.high_intensity_box_ids),
            "constructive_delta_ids": list(self.constructive_delta_ids),
            "fracture_delta_ids": list(self.fracture_delta_ids),
            "memory_confidence_trend": self.memory_confidence_trend,
            "workflow_health": self.workflow_health.value,
            "execution_readiness": self.execution_readiness,
            "interrogation_task_ids": list(self.interrogation_task_ids),
            "simple_action_summaries": [summary.to_dict() for summary in self.simple_action_summaries],
            "simple_workflow_summaries": [summary.to_dict() for summary in self.simple_workflow_summaries],
            "simple_start_guide": self.simple_start_guide.to_dict() if self.simple_start_guide else None,
            "simple_home_summary": self.simple_home_summary.to_dict() if self.simple_home_summary else None,
            "simple_ready_action_refs": list(self.simple_ready_action_refs),
            "simple_review_action_refs": list(self.simple_review_action_refs),
            "simple_blocked_action_refs": list(self.simple_blocked_action_refs),
            "simple_ready_workflow_refs": list(self.simple_ready_workflow_refs),
            "simple_review_workflow_refs": list(self.simple_review_workflow_refs),
            "simple_blocked_workflow_refs": list(self.simple_blocked_workflow_refs),
            "execution_allowed": self.execution_allowed,
        }


def build_operational_dashboard_state(
    *,
    projection: NoteMemoryProjection,
    boxes: Sequence[ConceptBox] = (),
    repair_items: Sequence[MemoryRepairItem] = (),
    compiled_actions: Sequence[CompiledMemoryAction] = (),
    interrogation_tasks: Sequence[InterrogationTask] = (),
    simple_action_checks: Sequence[SimpleActionCheck] = (),
    simple_workflow_plans: Sequence[SimpleWorkflowPlan] = (),
    simple_start_guide: SimpleOnboardingGuide | None = None,
) -> OperationalDashboardState:
    """Build a read-only dashboard state from projection and candidates."""

    ready_action_ids = tuple(
        action.compiled_action_id
        for action in compiled_actions
        if action.status == CandidateActionStatus.READY_FOR_GOVERNANCE
    )
    blocked_action_ids = tuple(
        action.compiled_action_id
        for action in compiled_actions
        if action.status in {CandidateActionStatus.BLOCKED, CandidateActionStatus.REPAIR_REQUIRED}
    )
    high_intensity_box_ids = tuple(box.box_id for box in boxes if box.risk_facets)
    active_project_count = len(
        {
            box.box_id
            for box in boxes
            if box.box_type.value == "project" and any(note_id in _active_note_ids(projection) for note_id in box.source_note_ids)
        }
    )
    confidence_values = tuple(claim.confidence for claim in projection.active_claims)
    confidence_trend = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    simple_action_summaries = tuple(_simple_action_summary(check) for check in simple_action_checks)
    simple_workflow_summaries = tuple(_simple_workflow_summary(plan) for plan in simple_workflow_plans)
    simple_start_guide_summary = _simple_start_guide_summary(simple_start_guide) if simple_start_guide else None
    simple_home_summary = _simple_home_summary(
        simple_workflow_summaries=simple_workflow_summaries,
        simple_start_guide=simple_start_guide_summary,
    )
    workflow_health = _workflow_health(projection, repair_items, blocked_action_ids)
    readiness = _execution_readiness(workflow_health, ready_action_ids, blocked_action_ids)
    dashboard_id = stable_identifier(
        "operational-dashboard",
        {
            "projection_id": projection.projection_id,
            "repair_ids": tuple(repair.repair_id for repair in repair_items),
            "compiled_action_ids": tuple(action.compiled_action_id for action in compiled_actions),
            "interrogation_task_ids": tuple(task.task_id for task in interrogation_tasks),
            "simple_action_refs": tuple(summary.action_ref for summary in simple_action_summaries),
            "simple_workflow_refs": tuple(summary.workflow_ref for summary in simple_workflow_summaries),
            "simple_start_guide": simple_start_guide_summary.to_dict() if simple_start_guide_summary else None,
            "simple_home_summary": simple_home_summary.to_dict() if simple_home_summary else None,
        },
    )
    return OperationalDashboardState(
        dashboard_id=dashboard_id,
        projection_id=projection.projection_id,
        active_project_count=active_project_count,
        ready_action_ids=ready_action_ids,
        blocked_action_ids=blocked_action_ids,
        open_blocker_ids=tuple(blocker.blocker_id for blocker in projection.blockers),
        open_conflict_ids=tuple(conflict.conflict_id for conflict in projection.conflict_clusters),
        repair_ids=tuple(repair.repair_id for repair in repair_items),
        stale_high_impact_claim_ids=tuple(
            claim.claim_id
            for claim in projection.inactive_claims
            if any(marker in claim.claim_text.lower() for marker in ("deploy", "security", "risk", "blocked"))
        ),
        high_intensity_box_ids=high_intensity_box_ids,
        constructive_delta_ids=projection.constructive_delta_ids,
        fracture_delta_ids=projection.fracture_delta_ids,
        memory_confidence_trend=confidence_trend,
        workflow_health=workflow_health,
        execution_readiness=readiness,
        interrogation_task_ids=tuple(task.task_id for task in interrogation_tasks),
        simple_action_summaries=simple_action_summaries,
        simple_workflow_summaries=simple_workflow_summaries,
        simple_start_guide=simple_start_guide_summary,
        simple_home_summary=simple_home_summary,
        simple_ready_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "ready"
        ),
        simple_review_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "needs_review"
        ),
        simple_blocked_action_refs=tuple(
            summary.action_ref for summary in simple_action_summaries if summary.outcome == "blocked"
        ),
        simple_ready_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "ready"
        ),
        simple_review_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "needs_review"
        ),
        simple_blocked_workflow_refs=tuple(
            summary.workflow_ref for summary in simple_workflow_summaries if summary.outcome == "blocked"
        ),
    )


def _simple_action_summary(check: SimpleActionCheck) -> DashboardSimpleActionSummary:
    """Project one simple action check into dashboard display state."""

    return DashboardSimpleActionSummary(
        action_ref=check.decision_ref,
        outcome=check.outcome,
        title=check.title,
        message=check.message,
        next_step=check.next_step,
        proof_stamp_ref=check.proof_stamp_ref,
        boundary_witness_ref=check.boundary_witness_ref,
        blocked_reasons=check.blocked_reasons,
        review_reasons=check.review_reasons,
    )


def _simple_workflow_summary(plan: SimpleWorkflowPlan) -> DashboardSimpleWorkflowSummary:
    """Project one simple workflow plan into dashboard display state."""

    action_refs = tuple(check.decision_ref for check in plan.checks)
    workflow_ref = stable_identifier(
        "dashboard-simple-workflow",
        {
            "workflow": plan.workflow,
            "action_refs": action_refs,
            "outcome": plan.outcome,
        },
    )
    return DashboardSimpleWorkflowSummary(
        workflow_ref=workflow_ref,
        workflow=plan.workflow,
        label=plan.label,
        outcome=plan.outcome,
        title=plan.title,
        message=plan.message,
        next_step=plan.next_step,
        ready_count=plan.ready_count,
        review_count=plan.review_count,
        blocked_count=plan.blocked_count,
        action_refs=action_refs,
    )


def _simple_start_guide_summary(guide: SimpleOnboardingGuide) -> DashboardSimpleStartGuideSummary:
    """Project the simple onboarding guide into dashboard display state."""

    return DashboardSimpleStartGuideSummary(
        title=guide.title,
        message=guide.message,
        recommended_commands=tuple(step.command for step in guide.recommended_path),
        outcomes=guide.outcomes,
    )


def _simple_home_summary(
    *,
    simple_workflow_summaries: Sequence[DashboardSimpleWorkflowSummary],
    simple_start_guide: DashboardSimpleStartGuideSummary | None,
) -> DashboardSimpleHomeSummary | None:
    """Build a compact dashboard home summary from simple projections."""

    if not simple_workflow_summaries and simple_start_guide is None:
        return None
    ready_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "ready")
    review_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "needs_review")
    blocked_count = sum(1 for summary in simple_workflow_summaries if summary.outcome == "blocked")
    primary_command = (
        simple_start_guide.recommended_commands[0]
        if simple_start_guide and simple_start_guide.recommended_commands
        else "mullu start"
    )
    if blocked_count:
        return DashboardSimpleHomeSummary(
            title="Blocked",
            message="Some workflows need a narrower target before users continue.",
            primary_command=primary_command,
            ready_workflow_count=ready_count,
            review_workflow_count=review_count,
            blocked_workflow_count=blocked_count,
        )
    if review_count:
        return DashboardSimpleHomeSummary(
            title="Needs review",
            message="Some workflows need approval before users continue.",
            primary_command=primary_command,
            ready_workflow_count=ready_count,
            review_workflow_count=review_count,
            blocked_workflow_count=blocked_count,
        )
    return DashboardSimpleHomeSummary(
        title="Ready",
        message="Users can start with the recommended simple workflow path.",
        primary_command=primary_command,
        ready_workflow_count=ready_count,
        review_workflow_count=review_count,
        blocked_workflow_count=blocked_count,
    )


def _workflow_health(
    projection: NoteMemoryProjection,
    repair_items: Sequence[MemoryRepairItem],
    blocked_action_ids: Sequence[str],
) -> WorkflowHealth:
    if projection.conflict_clusters or repair_items:
        return WorkflowHealth.REPAIR_REQUIRED
    if projection.blockers or blocked_action_ids:
        return WorkflowHealth.BLOCKED
    if projection.fracture_delta_ids:
        return WorkflowHealth.DEGRADED
    return WorkflowHealth.READY


def _execution_readiness(
    workflow_health: WorkflowHealth,
    ready_action_ids: Sequence[str],
    blocked_action_ids: Sequence[str],
) -> str:
    if workflow_health in {WorkflowHealth.REPAIR_REQUIRED, WorkflowHealth.BLOCKED}:
        return "not_ready_governance_review_required"
    if ready_action_ids and not blocked_action_ids:
        return "candidate_ready_for_mullu_governance_verdict"
    return "no_action_candidate_ready"


def _active_note_ids(projection: NoteMemoryProjection) -> set[str]:
    return {claim.note_id for claim in projection.active_claims}
