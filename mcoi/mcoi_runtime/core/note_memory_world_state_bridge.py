"""World-state bridge for note-memory projections.

Purpose: convert projected memory claims, blockers, and conflicts into
entity-state facts for downstream governance reasoning.
Governance scope: projection-only facts, contradiction preservation, expected
state violations, and source lineage.
Dependencies: dataclasses, note-memory projection, and runtime invariant
helpers.
Invariants: world-state facts are derived from projection receipts and never
replace append-only note-memory events.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.note_memory_projection import NoteMemoryProjection


@dataclass(frozen=True)
class WorldStateFact:
    """Projection-derived world-state fact."""

    fact_id: str
    entity_id: str
    attribute: str
    value: str
    source_ids: tuple[str, ...]
    confidence: float
    expected_state_violation: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible world-state fact."""

        return {
            "fact_id": self.fact_id,
            "entity_id": self.entity_id,
            "attribute": self.attribute,
            "value": self.value,
            "source_ids": list(self.source_ids),
            "confidence": self.confidence,
            "expected_state_violation": self.expected_state_violation,
        }


def bridge_projection_to_world_state(projection: NoteMemoryProjection) -> tuple[WorldStateFact, ...]:
    """Map a note-memory projection into world-state facts."""

    facts: list[WorldStateFact] = []
    for claim in projection.active_claims:
        facts.append(
            _fact(
                entity_id=f"scope:{claim.scope}",
                attribute="claim",
                value=claim.claim_text,
                source_ids=(claim.note_id,),
                confidence=claim.confidence,
                expected_state_violation=False,
            )
        )
    for blocker in projection.blockers:
        facts.append(
            _fact(
                entity_id=f"scope:{blocker.scope}",
                attribute="blocker",
                value=blocker.reason,
                source_ids=blocker.source_ids,
                confidence=0.8,
                expected_state_violation=True,
            )
        )
    for conflict in projection.conflict_clusters:
        facts.append(
            _fact(
                entity_id="memory-conflict",
                attribute="contradiction",
                value=conflict.reason,
                source_ids=conflict.source_note_ids,
                confidence=0.9,
                expected_state_violation=True,
            )
        )
    return tuple(facts)


def _fact(
    *,
    entity_id: str,
    attribute: str,
    value: str,
    source_ids: tuple[str, ...],
    confidence: float,
    expected_state_violation: bool,
) -> WorldStateFact:
    fact_id = stable_identifier(
        "world-state-fact",
        {
            "entity_id": entity_id,
            "attribute": attribute,
            "value": value,
            "source_ids": source_ids,
        },
    )
    return WorldStateFact(
        fact_id=fact_id,
        entity_id=entity_id,
        attribute=attribute,
        value=value,
        source_ids=source_ids,
        confidence=confidence,
        expected_state_violation=expected_state_violation,
    )
