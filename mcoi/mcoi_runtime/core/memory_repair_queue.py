"""Repair queue for governed memory fractures.

Purpose: convert contradictions, blockers, and fracture findings into explicit
repair tasks.
Governance scope: no silent contradictions, source lineage on every repair,
bounded repair outcomes, and deterministic repair identifiers.
Dependencies: dataclasses, note-memory projection, axis traversal, and runtime
invariant helpers.
Invariants: every fracture entering the queue has a repair path and no repair
item executes or mutates note memory directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from mcoi_runtime.core.inceptadive_axis_traversal import AxisFinding, DeltaType
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_projection import NoteMemoryProjection


class RepairItemType(StrEnum):
    """Allowed memory repair classes."""

    CONTRADICTION = "contradiction"
    MISSING_EVIDENCE = "missing_evidence"
    STALE_CLAIM = "stale_claim"
    SCOPE_CONFLICT = "scope_conflict"
    UNSAFE_CANDIDATE = "unsafe_candidate"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"


@dataclass(frozen=True)
class MemoryRepairItem:
    """Candidate repair task for a memory fracture."""

    repair_id: str
    repair_type: RepairItemType
    source_ids: tuple[str, ...]
    reason: str
    allowed_outcomes: tuple[str, ...]
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("repair items cannot execute directly")
        if not self.source_ids:
            raise RuntimeCoreInvariantError("repair item requires source_ids")
        if not self.allowed_outcomes:
            raise RuntimeCoreInvariantError("repair item requires allowed_outcomes")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible repair item."""

        return {
            "repair_id": self.repair_id,
            "repair_type": self.repair_type.value,
            "source_ids": list(self.source_ids),
            "reason": self.reason,
            "allowed_outcomes": list(self.allowed_outcomes),
            "execution_allowed": self.execution_allowed,
        }


def build_memory_repair_queue(
    projection: NoteMemoryProjection,
    *,
    axis_findings: Sequence[AxisFinding] = (),
) -> tuple[MemoryRepairItem, ...]:
    """Build repair tasks from projected conflicts, blockers, and fractures."""

    items: list[MemoryRepairItem] = []
    for conflict in projection.conflict_clusters:
        items.append(
            _item(
                repair_type=RepairItemType.CONTRADICTION,
                source_ids=conflict.source_note_ids,
                reason=conflict.reason,
            )
        )
    for blocker in projection.blockers:
        repair_type = RepairItemType.UNSAFE_CANDIDATE if blocker.severity == "high" else RepairItemType.UNRESOLVED_DEPENDENCY
        items.append(_item(repair_type=repair_type, source_ids=blocker.source_ids, reason=blocker.reason))
    for finding in axis_findings:
        if finding.delta_type == DeltaType.FRACTURE:
            items.append(
                _item(
                    repair_type=RepairItemType.MISSING_EVIDENCE if finding.suppression.evidence_weakness else RepairItemType.UNRESOLVED_DEPENDENCY,
                    source_ids=(finding.finding_id,),
                    reason=finding.repair_requirement,
                )
            )
    return tuple(_dedupe(items))


def _item(*, repair_type: RepairItemType, source_ids: tuple[str, ...], reason: str) -> MemoryRepairItem:
    repair_id = stable_identifier("memory-repair", {"repair_type": repair_type.value, "source_ids": source_ids, "reason": reason})
    return MemoryRepairItem(
        repair_id=repair_id,
        repair_type=repair_type,
        source_ids=source_ids,
        reason=reason,
        allowed_outcomes=("supersede_old_note", "promote_new_anchor", "mark_context_specific", "escalate_to_human", "reject_claim"),
    )


def _dedupe(items: Sequence[MemoryRepairItem]) -> tuple[MemoryRepairItem, ...]:
    seen: set[str] = set()
    result: list[MemoryRepairItem] = []
    for item in items:
        if item.repair_id in seen:
            continue
        seen.add(item.repair_id)
        result.append(item)
    return tuple(result)
