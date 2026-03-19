"""Purpose: verify world-state engine — entity graph, contradictions, confidence propagation.
Governance scope: world-state plane tests only.
Dependencies: world-state contracts, world-state engine.
Invariants: entities from evidence; contradictions explicit; confidence propagates.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.world_state import (
    ContradictionRecord,
    ContradictionStrategy,
    EntityRelation,
    StateEntity,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.world_state import WorldStateEngine


_CLOCK = "2026-03-19T00:00:00+00:00"


def _entity(entity_id: str = "e-1", confidence: float = 0.9) -> StateEntity:
    return StateEntity(
        entity_id=entity_id,
        entity_type="file",
        attributes={"path": "/tmp/test"},
        evidence_ids=("ev-1",),
        confidence=confidence,
        created_at=_CLOCK,
    )


# --- Entity tests ---

def test_add_and_get_entity() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity())
    assert engine.get_entity("e-1") is not None
    assert engine.entity_count == 1


def test_duplicate_entity_rejected() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity())
    with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
        engine.add_entity(_entity())


def test_list_entities_by_type() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("e-1"))
    engine.add_entity(StateEntity(
        entity_id="e-2", entity_type="process",
        attributes={"pid": 123}, evidence_ids=("ev-2",),
    ))
    assert len(engine.list_entities()) == 2
    assert len(engine.list_entities(entity_type="file")) == 1
    assert len(engine.list_entities(entity_type="process")) == 1


def test_entity_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_ids"):
        StateEntity(
            entity_id="e-1", entity_type="file",
            attributes={}, evidence_ids=(),
        )


# --- Relation tests ---

def test_add_relation() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("e-1"))
    engine.add_entity(_entity("e-2"))
    engine.add_relation(EntityRelation(
        relation_id="r-1",
        source_entity_id="e-1",
        target_entity_id="e-2",
        relation_type="depends_on",
        evidence_ids=("ev-1",),
    ))
    assert engine.relation_count == 1
    assert len(engine.get_relations("e-1")) == 1


def test_relation_rejects_dangling() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("e-1"))
    with pytest.raises(RuntimeCoreInvariantError, match="not found"):
        engine.add_relation(EntityRelation(
            relation_id="r-1",
            source_entity_id="e-1",
            target_entity_id="e-missing",
            relation_type="depends_on",
            evidence_ids=("ev-1",),
        ))


def test_self_referential_relation_rejected() -> None:
    with pytest.raises(ValueError, match="self-referential"):
        EntityRelation(
            relation_id="r-1",
            source_entity_id="e-1",
            target_entity_id="e-1",
            relation_type="depends_on",
            evidence_ids=("ev-1",),
        )


# --- Circular dependency detection ---

def test_detect_circular_dependency() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("a"))
    engine.add_entity(_entity("b"))
    engine.add_entity(_entity("c"))
    engine.add_relation(EntityRelation(
        relation_id="r-1", source_entity_id="a", target_entity_id="b",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    engine.add_relation(EntityRelation(
        relation_id="r-2", source_entity_id="b", target_entity_id="c",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    engine.add_relation(EntityRelation(
        relation_id="r-3", source_entity_id="c", target_entity_id="a",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    cycle = engine.detect_circular_dependency("a")
    assert cycle is not None
    assert "a" in cycle


def test_no_circular_dependency() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("a"))
    engine.add_entity(_entity("b"))
    engine.add_relation(EntityRelation(
        relation_id="r-1", source_entity_id="a", target_entity_id="b",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    assert engine.detect_circular_dependency("a") is None


# --- Contradiction tests ---

def test_record_contradiction() -> None:
    engine = WorldStateEngine()
    engine.record_contradiction(ContradictionRecord(
        contradiction_id="c-1",
        entity_id="e-1",
        attribute="status",
        conflicting_evidence_ids=("ev-1", "ev-2"),
        strategy=ContradictionStrategy.ESCALATE,
        resolved=False,
    ))
    assert len(engine.list_unresolved_contradictions()) == 1


# --- Confidence propagation ---

def test_confidence_propagates_through_dependencies() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("a", confidence=0.9))
    engine.add_entity(_entity("b", confidence=0.5))
    engine.add_relation(EntityRelation(
        relation_id="r-1", source_entity_id="a", target_entity_id="b",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    # A depends on B, so A's effective confidence <= B's
    assert engine.effective_confidence("a") == 0.5
    assert engine.effective_confidence("b") == 0.5


def test_confidence_handles_circular_dependency_without_crash() -> None:
    """Previously this caused infinite recursion. Now returns 0.0 for cyclic nodes."""
    engine = WorldStateEngine()
    engine.add_entity(_entity("a", confidence=0.9))
    engine.add_entity(_entity("b", confidence=0.8))
    engine.add_relation(EntityRelation(
        relation_id="r-1", source_entity_id="a", target_entity_id="b",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    engine.add_relation(EntityRelation(
        relation_id="r-2", source_entity_id="b", target_entity_id="a",
        relation_type="depends_on", evidence_ids=("ev-1",),
    ))
    # Should not crash — cycle guard returns 0.0 for the cyclic node
    confidence_a = engine.effective_confidence("a")
    confidence_b = engine.effective_confidence("b")
    assert confidence_a == 0.0  # Cycle detected, fails safe
    assert confidence_b == 0.0


def test_confidence_without_dependencies() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("a", confidence=0.8))
    assert engine.effective_confidence("a") == 0.8


# --- Snapshot hash ---

def test_snapshot_hash_deterministic() -> None:
    engine = WorldStateEngine()
    engine.add_entity(_entity("e-1"))
    hash1 = engine.snapshot_hash()
    hash2 = engine.snapshot_hash()
    assert hash1 == hash2
    assert len(hash1) == 64
