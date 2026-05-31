"""Decision-use receipts for governed memory influence.

Purpose: prove how retrieved memory, Concept Boxes, projections, repairs, and
candidate actions affected a governance decision.
Governance scope: deterministic receipts, source-note lineage, blocking/support
separation, proof-state recording, and no silent memory influence.
Dependencies: dataclasses, note-memory projection, repair queue, compiled
actions, and runtime invariant helpers.
Invariants: any memory-influenced decision records supporting notes, blocking
notes, conflicts, repairs, candidate action, verdict, proof state, and hash.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from typing import Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_action_compiler import CompiledMemoryAction
from mcoi_runtime.core.memory_repair_queue import MemoryRepairItem
from mcoi_runtime.core.note_memory_mesh import ProofState
from mcoi_runtime.core.note_memory_projection import NoteMemoryProjection


@dataclass(frozen=True)
class DecisionUseReceipt:
    """Receipt proving how memory affected a decision."""

    decision_id: str
    retrieval_receipt_id: str
    projection_id: str
    box_ids: tuple[str, ...]
    axis_finding_ids_used: tuple[str, ...]
    supporting_note_ids: tuple[str, ...]
    blocking_note_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    repair_ids: tuple[str, ...]
    candidate_action_id: str
    governance_verdict: str
    proof_state: ProofState
    confidence_score: float
    assessed_at: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise RuntimeCoreInvariantError("decision_id must be non-empty")
        if not 0.0 <= self.confidence_score <= 1.0:
            raise RuntimeCoreInvariantError("confidence_score must be in [0,1]")
        if self.governance_verdict == "approve" and self.blocking_note_ids:
            raise RuntimeCoreInvariantError("approve verdict cannot carry blocking_note_ids")
        if self.snapshot_hash and self.snapshot_hash != self.expected_snapshot_hash():
            raise RuntimeCoreInvariantError("decision-use receipt snapshot_hash mismatch")

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        """Return a JSON-compatible decision-use receipt."""

        value: dict[str, object] = {
            "decision_id": self.decision_id,
            "retrieval_receipt_id": self.retrieval_receipt_id,
            "projection_id": self.projection_id,
            "box_ids": list(self.box_ids),
            "axis_finding_ids_used": list(self.axis_finding_ids_used),
            "supporting_note_ids": list(self.supporting_note_ids),
            "blocking_note_ids": list(self.blocking_note_ids),
            "conflict_ids": list(self.conflict_ids),
            "repair_ids": list(self.repair_ids),
            "candidate_action_id": self.candidate_action_id,
            "governance_verdict": self.governance_verdict,
            "proof_state": self.proof_state.value,
            "confidence_score": self.confidence_score,
            "assessed_at": self.assessed_at,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        """Return the expected deterministic receipt hash."""

        return _hash_mapping(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "DecisionUseReceipt":
        """Return the receipt with deterministic snapshot hash populated."""

        unsigned = replace(self, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


def build_decision_use_receipt(
    *,
    decision_id: str,
    retrieval_receipt_id: str,
    projection: NoteMemoryProjection,
    compiled_action: CompiledMemoryAction,
    repair_items: Sequence[MemoryRepairItem],
    governance_verdict: str,
    proof_state: ProofState,
    confidence_score: float,
    assessed_at: str,
) -> DecisionUseReceipt:
    """Build a deterministic receipt for one memory-influenced decision."""

    blocking_note_ids = tuple(sorted({source_id for blocker in projection.blockers for source_id in blocker.source_ids}))
    supporting_note_ids = tuple(sorted({note_id for action in projection.candidate_actions for note_id in action.source_note_ids}))
    receipt = DecisionUseReceipt(
        decision_id=decision_id,
        retrieval_receipt_id=retrieval_receipt_id,
        projection_id=projection.projection_id,
        box_ids=projection.receipt.box_ids,
        axis_finding_ids_used=projection.receipt.finding_ids,
        supporting_note_ids=supporting_note_ids,
        blocking_note_ids=blocking_note_ids,
        conflict_ids=tuple(conflict.conflict_id for conflict in projection.conflict_clusters),
        repair_ids=tuple(repair.repair_id for repair in repair_items),
        candidate_action_id=compiled_action.compiled_action_id,
        governance_verdict=governance_verdict,
        proof_state=proof_state,
        confidence_score=confidence_score,
        assessed_at=assessed_at,
    )
    return receipt.with_integrity()


def _hash_mapping(value: Mapping[str, object]) -> str:
    material = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(material.encode("utf-8")).hexdigest()
