"""Action candidate compiler for note-memory projections.

Purpose: turn projected state into candidate actions while preserving the Mullu
control-plane execution gate.
Governance scope: candidate-only output, source-note lineage, blocker-aware
status, and no direct execution from memory or InceptaDive outputs.
Dependencies: dataclasses, note-memory projection, repair queue, and runtime
invariant helpers.
Invariants: compiled actions never execute and always require a later
governance verdict before side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_repair_queue import MemoryRepairItem
from mcoi_runtime.core.note_memory_projection import CandidateActionStatus, NoteMemoryProjection


class CompiledActionType(StrEnum):
    """Allowed compiled action classes."""

    DEPLOY = "deploy"
    TEST = "test"
    REVIEW = "review"
    REPAIR = "repair"
    REQUEST_EVIDENCE = "request_evidence"
    UPDATE_DOCUMENTATION = "update_documentation"
    SUMMARIZE = "summarize"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class CompiledMemoryAction:
    """Governance-bound action candidate."""

    compiled_action_id: str
    action_type: str
    source_note_ids: tuple[str, ...]
    repair_ids: tuple[str, ...]
    status: CandidateActionStatus
    governance_status: str
    reason: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("compiled memory action cannot execute directly")
        if not self.source_note_ids and not self.repair_ids:
            raise RuntimeCoreInvariantError("compiled memory action requires lineage")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible compiled action."""

        return {
            "compiled_action_id": self.compiled_action_id,
            "action_type": self.action_type,
            "source_note_ids": list(self.source_note_ids),
            "repair_ids": list(self.repair_ids),
            "status": self.status.value,
            "governance_status": self.governance_status,
            "reason": self.reason,
            "execution_allowed": self.execution_allowed,
        }


def compile_memory_actions(
    projection: NoteMemoryProjection,
    *,
    repair_items: Sequence[MemoryRepairItem] = (),
) -> tuple[CompiledMemoryAction, ...]:
    """Compile candidate actions from projection and repair queue."""

    actions: list[CompiledMemoryAction] = []
    for candidate in projection.candidate_actions:
        actions.append(
            _compiled_action(
                action_type=candidate.action_type,
                source_note_ids=candidate.source_note_ids,
                repair_ids=(),
                status=candidate.status,
                reason=candidate.reason,
            )
        )
    for repair in repair_items:
        actions.append(
            _compiled_action(
                action_type=CompiledActionType.REPAIR.value,
                source_note_ids=(),
                repair_ids=(repair.repair_id,),
                status=CandidateActionStatus.REPAIR_REQUIRED,
                reason=repair.reason,
            )
        )
    return tuple(actions)


def _compiled_action(
    *,
    action_type: str,
    source_note_ids: tuple[str, ...],
    repair_ids: tuple[str, ...],
    status: CandidateActionStatus,
    reason: str,
) -> CompiledMemoryAction:
    compiled_action_id = stable_identifier(
        "compiled-memory-action",
        {
            "action_type": action_type,
            "source_note_ids": source_note_ids,
            "repair_ids": repair_ids,
            "status": status.value,
        },
    )
    return CompiledMemoryAction(
        compiled_action_id=compiled_action_id,
        action_type=action_type,
        source_note_ids=source_note_ids,
        repair_ids=repair_ids,
        status=status,
        governance_status="requires_mullu_control_plane_verdict",
        reason=reason,
    )
