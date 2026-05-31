"""Operational dashboard intelligence for note-memory projections.

Purpose: expose project state, ready actions, blocked actions, blockers,
conflicts, repairs, high-intensity concepts, recent deltas, confidence trend,
workflow health, and execution readiness as a read-only dashboard model.
Governance scope: projection-only display, constructive/fracture separation,
readiness gating, repair visibility, and no execution authority.
Dependencies: dataclasses, Concept Boxes, projection, repair queue, compiled
actions, interrogation queue, and runtime invariant helpers.
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


class WorkflowHealth(StrEnum):
    """Operational workflow health classes."""

    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    REPAIR_REQUIRED = "repair_required"


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
            "execution_allowed": self.execution_allowed,
        }


def build_operational_dashboard_state(
    *,
    projection: NoteMemoryProjection,
    boxes: Sequence[ConceptBox] = (),
    repair_items: Sequence[MemoryRepairItem] = (),
    compiled_actions: Sequence[CompiledMemoryAction] = (),
    interrogation_tasks: Sequence[InterrogationTask] = (),
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
    workflow_health = _workflow_health(projection, repair_items, blocked_action_ids)
    readiness = _execution_readiness(workflow_health, ready_action_ids, blocked_action_ids)
    dashboard_id = stable_identifier(
        "operational-dashboard",
        {
            "projection_id": projection.projection_id,
            "repair_ids": tuple(repair.repair_id for repair in repair_items),
            "compiled_action_ids": tuple(action.compiled_action_id for action in compiled_actions),
            "interrogation_task_ids": tuple(task.task_id for task in interrogation_tasks),
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
