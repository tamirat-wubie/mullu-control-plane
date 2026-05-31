"""Interrogation queue for InceptaDive Concept Boxes.

Purpose: decide which Concept Boxes should be interrogated next after new
notes, blockers, contradictions, stale high-impact claims, rejected actions, or
promotion requests.
Governance scope: bounded curiosity, source lineage, axis-plan traceability,
repair policy declaration, and no execution authority.
Dependencies: dataclasses, Concept Box ledger, note-memory projection, repair
queue, and runtime invariant helpers.
Invariants: interrogation tasks are candidates only; every task records target
Box, reason, priority, scope, axis plan, depth, expected output, and repair
policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox
from mcoi_runtime.core.inceptadive_axis_traversal import TraversalAxis
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_repair_queue import MemoryRepairItem
from mcoi_runtime.core.note_memory_projection import NoteMemoryProjection


class InterrogationReason(StrEnum):
    """Allowed interrogation triggers."""

    NEW_NOTE_CAPTURED = "new_note_captured"
    CONTRADICTION_DETECTED = "contradiction_detected"
    PROJECT_BLOCKER = "project_blocker"
    HIGH_IMPACT_STALE_NOTE = "high_impact_stale_note"
    ACTION_REJECTED = "action_rejected"
    WORKFLOW_STUCK = "workflow_stuck"
    NEW_EVIDENCE_ADDED = "new_evidence_added"
    PROMOTION_REQUESTED = "promotion_requested"


class InterrogationPriority(StrEnum):
    """Queue priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class InterrogationTask:
    """Candidate task for future InceptaDive traversal."""

    task_id: str
    target_box_id: str
    reason: InterrogationReason
    priority: InterrogationPriority
    scope: str
    axis_plan: tuple[TraversalAxis, ...]
    max_depth: int
    expected_output: str
    repair_policy: str
    source_ids: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("interrogation tasks cannot execute directly")
        if not self.target_box_id.strip():
            raise RuntimeCoreInvariantError("interrogation task requires target_box_id")
        if self.max_depth < 1:
            raise RuntimeCoreInvariantError("interrogation task max_depth must be positive")
        if not self.axis_plan:
            raise RuntimeCoreInvariantError("interrogation task requires axis_plan")
        if not self.source_ids:
            raise RuntimeCoreInvariantError("interrogation task requires source_ids")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible interrogation task."""

        return {
            "task_id": self.task_id,
            "target_box_id": self.target_box_id,
            "reason": self.reason.value,
            "priority": self.priority.value,
            "scope": self.scope,
            "axis_plan": [axis.value for axis in self.axis_plan],
            "max_depth": self.max_depth,
            "expected_output": self.expected_output,
            "repair_policy": self.repair_policy,
            "source_ids": list(self.source_ids),
            "execution_allowed": self.execution_allowed,
        }


def build_interrogation_queue(
    boxes: Sequence[ConceptBox],
    projection: NoteMemoryProjection,
    *,
    repair_items: Iterable[MemoryRepairItem] = (),
) -> tuple[InterrogationTask, ...]:
    """Build bounded InceptaDive interrogation tasks from current projection."""

    box_by_source_note: dict[str, ConceptBox] = {}
    for box in boxes:
        for source_note_id in box.source_note_ids:
            box_by_source_note[source_note_id] = box
    tasks: list[InterrogationTask] = []
    for blocker in projection.blockers:
        target = _target_box(box_by_source_note, blocker.source_ids, boxes)
        if target is not None:
            tasks.append(
                _task(
                    target_box=target,
                    reason=InterrogationReason.PROJECT_BLOCKER,
                    priority=InterrogationPriority.HIGH if blocker.severity == "high" else InterrogationPriority.MEDIUM,
                    scope=blocker.scope,
                    axis_plan=(
                        TraversalAxis.VERTICAL,
                        TraversalAxis.CIRCULAR,
                        TraversalAxis.DIAGONAL,
                        TraversalAxis.INTENSITY,
                    ),
                    expected_output="blocker cause, evidence need, and safe repair candidate",
                    repair_policy="create repair item before action promotion",
                    source_ids=blocker.source_ids,
                )
            )
    for conflict in projection.conflict_clusters:
        target = _target_box(box_by_source_note, conflict.source_note_ids, boxes)
        if target is not None:
            tasks.append(
                _task(
                    target_box=target,
                    reason=InterrogationReason.CONTRADICTION_DETECTED,
                    priority=InterrogationPriority.CRITICAL,
                    scope="conflict",
                    axis_plan=(TraversalAxis.HORIZONTAL, TraversalAxis.CIRCULAR, TraversalAxis.TEMPORAL, TraversalAxis.META),
                    expected_output="contradiction cluster with supersede, context split, or escalation path",
                    repair_policy="block promotion until contradiction is resolved",
                    source_ids=conflict.source_note_ids,
                )
            )
    for repair in repair_items:
        target = _target_box(box_by_source_note, repair.source_ids, boxes)
        if target is not None:
            tasks.append(
                _task(
                    target_box=target,
                    reason=InterrogationReason.WORKFLOW_STUCK,
                    priority=InterrogationPriority.HIGH,
                    scope="repair",
                    axis_plan=(TraversalAxis.VERTICAL, TraversalAxis.TEMPORAL, TraversalAxis.META),
                    expected_output="repair evidence requirement and allowed outcome recommendation",
                    repair_policy="keep as repair candidate until Mullu governance verdict",
                    source_ids=repair.source_ids,
                )
            )
    if not tasks:
        for box in boxes:
            tasks.append(
                _task(
                    target_box=box,
                    reason=InterrogationReason.NEW_NOTE_CAPTURED,
                    priority=InterrogationPriority.LOW,
                    scope=box.box_type.value,
                    axis_plan=(TraversalAxis.VERTICAL, TraversalAxis.TEMPORAL),
                    expected_output="baseline concept facets and temporal state",
                    repair_policy="repair only if fracture findings emerge",
                    source_ids=box.source_note_ids or (box.box_id,),
                )
            )
    return tuple(_dedupe(tasks))


def _task(
    *,
    target_box: ConceptBox,
    reason: InterrogationReason,
    priority: InterrogationPriority,
    scope: str,
    axis_plan: tuple[TraversalAxis, ...],
    expected_output: str,
    repair_policy: str,
    source_ids: tuple[str, ...],
) -> InterrogationTask:
    task_id = stable_identifier(
        "interrogation-task",
        {
            "target_box_id": target_box.box_id,
            "reason": reason.value,
            "source_ids": source_ids,
            "axis_plan": tuple(axis.value for axis in axis_plan),
        },
    )
    return InterrogationTask(
        task_id=task_id,
        target_box_id=target_box.box_id,
        reason=reason,
        priority=priority,
        scope=scope,
        axis_plan=axis_plan,
        max_depth=3,
        expected_output=expected_output,
        repair_policy=repair_policy,
        source_ids=source_ids,
    )


def _target_box(
    box_by_source_note: Mapping[str, ConceptBox],
    source_ids: Sequence[str],
    boxes: Sequence[ConceptBox],
) -> ConceptBox | None:
    for source_id in source_ids:
        if source_id in box_by_source_note:
            return box_by_source_note[source_id]
    return boxes[0] if boxes else None


def _dedupe(tasks: Sequence[InterrogationTask]) -> tuple[InterrogationTask, ...]:
    seen: set[str] = set()
    result: list[InterrogationTask] = []
    for task in tasks:
        if task.task_id in seen:
            continue
        seen.add(task.task_id)
        result.append(task)
    return tuple(result)
