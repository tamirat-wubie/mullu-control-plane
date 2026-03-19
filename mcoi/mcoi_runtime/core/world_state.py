"""Purpose: world-state core — entity graph, contradiction detection, confidence propagation.
Governance scope: world-state plane core logic only.
Dependencies: world-state contracts, invariant helpers.
Invariants:
  - Entities derive from evidence only.
  - Contradictions are explicit and tracked.
  - Confidence propagates through dependency chains.
  - Circular dependencies are detected.
"""

from __future__ import annotations

from hashlib import sha256
import json

from mcoi_runtime.contracts.world_state import (
    ConfidenceAnnotation,
    ContradictionRecord,
    ContradictionStrategy,
    EntityRelation,
    StateEntity,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class WorldStateEngine:
    """Entity graph with contradiction detection and confidence propagation.

    This engine:
    - Maintains a typed entity graph
    - Tracks relations between entities
    - Detects contradictions when evidence conflicts
    - Propagates confidence through dependency chains
    - Detects circular dependencies
    """

    def __init__(self) -> None:
        self._entities: dict[str, StateEntity] = {}
        self._relations: dict[str, EntityRelation] = {}
        self._contradictions: dict[str, ContradictionRecord] = {}

    # --- Entities ---

    def add_entity(self, entity: StateEntity) -> StateEntity:
        if entity.entity_id in self._entities:
            raise RuntimeCoreInvariantError(f"entity already exists: {entity.entity_id}")
        self._entities[entity.entity_id] = entity
        return entity

    def get_entity(self, entity_id: str) -> StateEntity | None:
        ensure_non_empty_text("entity_id", entity_id)
        return self._entities.get(entity_id)

    def list_entities(self, *, entity_type: str | None = None) -> tuple[StateEntity, ...]:
        entities = sorted(self._entities.values(), key=lambda e: e.entity_id)
        if entity_type is not None:
            ensure_non_empty_text("entity_type", entity_type)
            entities = [e for e in entities if e.entity_type == entity_type]
        return tuple(entities)

    # --- Relations ---

    def add_relation(self, relation: EntityRelation) -> EntityRelation:
        if relation.relation_id in self._relations:
            raise RuntimeCoreInvariantError(f"relation already exists: {relation.relation_id}")
        if relation.source_entity_id not in self._entities:
            raise RuntimeCoreInvariantError(f"source entity not found: {relation.source_entity_id}")
        if relation.target_entity_id not in self._entities:
            raise RuntimeCoreInvariantError(f"target entity not found: {relation.target_entity_id}")
        self._relations[relation.relation_id] = relation
        return relation

    def get_relations(self, entity_id: str) -> tuple[EntityRelation, ...]:
        """Get all relations where entity_id is the source."""
        ensure_non_empty_text("entity_id", entity_id)
        return tuple(
            r for r in sorted(self._relations.values(), key=lambda r: r.relation_id)
            if r.source_entity_id == entity_id
        )

    def detect_circular_dependency(self, entity_id: str) -> tuple[str, ...] | None:
        """Detect if entity_id is part of a dependency cycle. Returns the cycle path or None."""
        ensure_non_empty_text("entity_id", entity_id)
        visited: set[str] = set()
        path: list[str] = []

        def _dfs(current: str) -> tuple[str, ...] | None:
            if current in visited:
                cycle_start = path.index(current)
                return tuple(path[cycle_start:] + [current])
            visited.add(current)
            path.append(current)
            for rel in self._relations.values():
                if rel.source_entity_id == current and rel.relation_type == "depends_on":
                    result = _dfs(rel.target_entity_id)
                    if result is not None:
                        return result
            path.pop()
            visited.discard(current)
            return None

        return _dfs(entity_id)

    # --- Contradictions ---

    def record_contradiction(self, contradiction: ContradictionRecord) -> ContradictionRecord:
        if contradiction.contradiction_id in self._contradictions:
            raise RuntimeCoreInvariantError(
                f"contradiction already recorded: {contradiction.contradiction_id}"
            )
        self._contradictions[contradiction.contradiction_id] = contradiction
        return contradiction

    def list_unresolved_contradictions(self) -> tuple[ContradictionRecord, ...]:
        return tuple(
            c for c in sorted(self._contradictions.values(), key=lambda c: c.contradiction_id)
            if not c.resolved
        )

    # --- Confidence ---

    def effective_confidence(self, entity_id: str, _visited: set[str] | None = None) -> float:
        """Compute effective confidence considering dependency chain.

        If entity A depends_on entity B, A's effective confidence
        cannot exceed B's effective confidence. Circular dependencies
        are detected and return 0.0 confidence for the cyclic node.
        """
        ensure_non_empty_text("entity_id", entity_id)
        if _visited is None:
            _visited = set()
        if entity_id in _visited:
            return 0.0  # Cycle detected — fail safe with zero confidence
        _visited.add(entity_id)

        entity = self._entities.get(entity_id)
        if entity is None:
            return 0.0

        base = entity.confidence
        deps = [
            r.target_entity_id
            for r in self._relations.values()
            if r.source_entity_id == entity_id and r.relation_type == "depends_on"
        ]
        if not deps:
            return base

        dep_confidences = [self.effective_confidence(dep_id, _visited) for dep_id in deps]
        return min(base, *dep_confidences)

    # --- Snapshot ---

    def snapshot_hash(self) -> str:
        """Compute a deterministic hash of the current world state."""
        payload = {
            "entities": {eid: e.to_dict() for eid, e in sorted(self._entities.items())},
            "relations": {rid: r.to_dict() for rid, r in sorted(self._relations.items())},
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)
