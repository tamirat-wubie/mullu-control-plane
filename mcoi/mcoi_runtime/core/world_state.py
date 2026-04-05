"""Purpose: world-state core — entity graph, contradiction detection, confidence propagation,
snapshot assembly, delta computation, conflict grouping, expected-vs-actual comparison.
Governance scope: world-state plane core logic only.
Dependencies: world-state contracts, invariant helpers.
Invariants:
  - Entities derive from evidence only.
  - Contradictions are explicit and tracked.
  - Confidence propagates through dependency chains.
  - Circular dependencies are detected.
  - Snapshots are immutable point-in-time views.
  - Deltas are computed, never fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from typing import Callable

from mcoi_runtime.contracts.world_state import (
    ConflictSet,
    ConfidenceAnnotation,
    ContradictionRecord,
    ContradictionStrategy,
    DeltaKind,
    DerivedFact,
    EntityRelation,
    ExpectedState,
    ResolutionRecord,
    StateConfidenceEnvelope,
    StateEntity,
    WorldStateDelta,
    WorldStateSnapshot,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


class WorldStateEngine:
    """Entity graph with contradiction detection, confidence propagation,
    snapshot assembly, delta computation, and expected-vs-actual comparison.

    This engine:
    - Maintains a typed entity graph
    - Tracks relations between entities
    - Detects contradictions when evidence conflicts
    - Propagates confidence through dependency chains
    - Detects circular dependencies
    - Assembles immutable snapshots
    - Computes deltas between snapshots
    - Groups contradictions into conflict sets
    - Compares expected state against actual
    - Manages derived facts and resolution records
    - Computes state confidence envelopes
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._entities: dict[str, StateEntity] = {}
        self._relations: dict[str, EntityRelation] = {}
        self._contradictions: dict[str, ContradictionRecord] = {}
        self._derived_facts: dict[str, DerivedFact] = {}
        self._resolutions: dict[str, ResolutionRecord] = {}
        self._expected_states: dict[str, ExpectedState] = {}
        self._clock = clock or self._default_clock

    @staticmethod
    def _default_clock() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _now(self) -> str:
        return self._clock()

    # --- Entities ---

    def add_entity(self, entity: StateEntity) -> StateEntity:
        if entity.entity_id in self._entities:
            raise RuntimeCoreInvariantError("entity already exists")
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
            raise RuntimeCoreInvariantError("relation already exists")
        if relation.source_entity_id not in self._entities:
            raise RuntimeCoreInvariantError("source entity not found")
        if relation.target_entity_id not in self._entities:
            raise RuntimeCoreInvariantError("target entity not found")
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
            raise RuntimeCoreInvariantError("contradiction already recorded")
        self._contradictions[contradiction.contradiction_id] = contradiction
        return contradiction

    def list_unresolved_contradictions(self) -> tuple[ContradictionRecord, ...]:
        return tuple(
            c for c in sorted(self._contradictions.values(), key=lambda c: c.contradiction_id)
            if not c.resolved
        )

    # --- Derived Facts ---

    def add_derived_fact(self, fact: DerivedFact) -> DerivedFact:
        """Register a derived fact. Source entities must exist."""
        if fact.fact_id in self._derived_facts:
            raise RuntimeCoreInvariantError("derived fact already exists")
        for src_id in fact.source_entity_ids:
            if src_id not in self._entities:
                raise RuntimeCoreInvariantError("source entity not found")
        self._derived_facts[fact.fact_id] = fact
        return fact

    def list_derived_facts(self, *, entity_id: str | None = None) -> tuple[DerivedFact, ...]:
        facts = sorted(self._derived_facts.values(), key=lambda f: f.fact_id)
        if entity_id is not None:
            ensure_non_empty_text("entity_id", entity_id)
            facts = [f for f in facts if f.entity_id == entity_id]
        return tuple(facts)

    # --- Resolutions ---

    def record_resolution(self, resolution: ResolutionRecord) -> ResolutionRecord:
        """Record a contradiction resolution. The contradiction must exist."""
        if resolution.resolution_id in self._resolutions:
            raise RuntimeCoreInvariantError("resolution already exists")
        if resolution.contradiction_id not in self._contradictions:
            raise RuntimeCoreInvariantError("contradiction not found")
        self._resolutions[resolution.resolution_id] = resolution
        return resolution

    def list_resolutions(self) -> tuple[ResolutionRecord, ...]:
        return tuple(sorted(self._resolutions.values(), key=lambda r: r.resolution_id))

    # --- Expected States ---

    def add_expected_state(self, expected: ExpectedState) -> ExpectedState:
        """Register an expected state projection."""
        if expected.expectation_id in self._expected_states:
            raise RuntimeCoreInvariantError("expected state already exists")
        self._expected_states[expected.expectation_id] = expected
        return expected

    def list_expected_states(self, *, entity_id: str | None = None) -> tuple[ExpectedState, ...]:
        states = sorted(self._expected_states.values(), key=lambda e: e.expectation_id)
        if entity_id is not None:
            ensure_non_empty_text("entity_id", entity_id)
            states = [s for s in states if s.entity_id == entity_id]
        return tuple(states)

    def compare_expected_vs_actual(
        self,
        expectation_id: str,
    ) -> tuple[ExpectedState, str, bool]:
        """Compare an expected state against the actual entity attribute.

        Returns (expected_state, actual_value_repr, matches).
        If the entity or attribute is missing, actual_value_repr is '<missing>'
        and matches is False.
        """
        ensure_non_empty_text("expectation_id", expectation_id)
        expected = self._expected_states.get(expectation_id)
        if expected is None:
            raise RuntimeCoreInvariantError("expected state not found")

        entity = self._entities.get(expected.entity_id)
        if entity is None:
            return (expected, "<missing>", False)

        actual = entity.attributes.get(expected.attribute, "<missing>")
        actual_repr = str(actual)
        matches = actual == expected.expected_value
        return (expected, actual_repr, matches)

    # --- Conflict Grouping ---

    def group_conflicts(self) -> tuple[ConflictSet, ...]:
        """Group unresolved contradictions by entity into ConflictSets."""
        unresolved = self.list_unresolved_contradictions()
        if not unresolved:
            return ()

        by_entity: dict[str, list[ContradictionRecord]] = defaultdict(list)
        for c in unresolved:
            by_entity[c.entity_id].append(c)

        now = self._now()
        sets: list[ConflictSet] = []
        for entity_id in sorted(by_entity):
            contras = tuple(by_entity[entity_id])
            strategies = [c.strategy for c in contras]
            if ContradictionStrategy.ESCALATE in strategies:
                overall = ContradictionStrategy.ESCALATE
            elif ContradictionStrategy.MANUAL in strategies:
                overall = ContradictionStrategy.MANUAL
            elif ContradictionStrategy.PREFER_HIGHEST_CONFIDENCE in strategies:
                overall = ContradictionStrategy.PREFER_HIGHEST_CONFIDENCE
            else:
                overall = ContradictionStrategy.PREFER_LATEST

            cs_id = stable_identifier("cs", {"entity_id": entity_id, "count": len(contras)})
            sets.append(ConflictSet(
                conflict_set_id=cs_id,
                entity_id=entity_id,
                contradictions=contras,
                overall_strategy=overall,
                created_at=now,
            ))
        return tuple(sets)

    # --- Confidence Envelopes ---

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

    def compute_confidence_envelope(
        self,
        entity_id: str,
        attribute: str,
    ) -> StateConfidenceEnvelope:
        """Compute a confidence envelope for a specific entity attribute.

        The point estimate is the entity's effective confidence.
        Bounds are derived from evidence count and contradiction presence.
        """
        ensure_non_empty_text("entity_id", entity_id)
        ensure_non_empty_text("attribute", attribute)

        entity = self._entities.get(entity_id)
        if entity is None:
            raise RuntimeCoreInvariantError("entity not found")

        point = self.effective_confidence(entity_id)
        evidence_count = len(entity.evidence_ids)

        # Contradictions on this entity+attribute widen the bounds
        contras = [
            c for c in self._contradictions.values()
            if c.entity_id == entity_id and c.attribute == attribute and not c.resolved
        ]
        penalty = min(0.3, 0.1 * len(contras))
        lower = max(0.0, point - penalty - (0.1 if evidence_count < 3 else 0.0))
        upper = min(1.0, point + (0.1 if evidence_count < 3 else 0.05))

        env_id = stable_identifier("sce", {
            "entity_id": entity_id, "attribute": attribute,
        })
        return StateConfidenceEnvelope(
            envelope_id=env_id,
            entity_id=entity_id,
            attribute=attribute,
            point_estimate=round(point, 4),
            lower_bound=round(lower, 4),
            upper_bound=round(upper, 4),
            evidence_count=evidence_count,
            assessed_at=self._now(),
        )

    # --- Snapshot Assembly ---

    def snapshot_hash(self) -> str:
        """Compute a deterministic hash of the current world state."""
        payload = {
            "entities": {eid: e.to_dict() for eid, e in sorted(self._entities.items())},
            "relations": {rid: r.to_dict() for rid, r in sorted(self._relations.items())},
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def assemble_snapshot(self, snapshot_id: str | None = None) -> WorldStateSnapshot:
        """Build an immutable point-in-time snapshot of the entire world state."""
        entities = self.list_entities()
        relations = tuple(sorted(self._relations.values(), key=lambda r: r.relation_id))
        derived = self.list_derived_facts()
        unresolved = self.list_unresolved_contradictions()
        expected = self.list_expected_states()
        state_hash = self.snapshot_hash()

        if not entities:
            overall_conf = 0.0
        else:
            overall_conf = sum(
                self.effective_confidence(e.entity_id) for e in entities
            ) / len(entities)

        sid = snapshot_id or stable_identifier("wss", {"hash": state_hash})
        return WorldStateSnapshot(
            snapshot_id=sid,
            entities=entities,
            relations=relations,
            derived_facts=derived,
            unresolved_contradictions=unresolved,
            expected_states=expected,
            state_hash=state_hash,
            entity_count=len(entities),
            relation_count=len(relations),
            overall_confidence=round(overall_conf, 4),
            captured_at=self._now(),
        )

    # --- Delta Computation ---

    def compute_deltas(
        self,
        previous: WorldStateSnapshot,
        current: WorldStateSnapshot,
    ) -> tuple[WorldStateDelta, ...]:
        """Compute deltas between two snapshots."""
        deltas: list[WorldStateDelta] = []
        now = self._now()
        counter = 0

        def _next_id() -> str:
            nonlocal counter
            counter += 1
            return stable_identifier("wsd", {
                "prev": previous.snapshot_id,
                "curr": current.snapshot_id,
                "n": counter,
            })

        prev_entities = {e.entity_id: e for e in previous.entities}
        curr_entities = {e.entity_id: e for e in current.entities}

        # Added entities
        for eid in sorted(set(curr_entities) - set(prev_entities)):
            deltas.append(WorldStateDelta(
                delta_id=_next_id(),
                kind=DeltaKind.ENTITY_ADDED,
                target_id=eid,
                description="entity added",
                computed_at=now,
            ))

        # Removed entities
        for eid in sorted(set(prev_entities) - set(curr_entities)):
            deltas.append(WorldStateDelta(
                delta_id=_next_id(),
                kind=DeltaKind.ENTITY_REMOVED,
                target_id=eid,
                description="entity removed",
                computed_at=now,
            ))

        # Modified entities (attributes changed)
        for eid in sorted(set(prev_entities) & set(curr_entities)):
            prev_e = prev_entities[eid]
            curr_e = curr_entities[eid]
            if prev_e.attributes != curr_e.attributes:
                deltas.append(WorldStateDelta(
                    delta_id=_next_id(),
                    kind=DeltaKind.ENTITY_MODIFIED,
                    target_id=eid,
                    description="entity modified",
                    previous_value=str(dict(prev_e.attributes)),
                    new_value=str(dict(curr_e.attributes)),
                    computed_at=now,
                ))

        # Relations
        prev_rels = {r.relation_id for r in previous.relations}
        curr_rels = {r.relation_id for r in current.relations}

        for rid in sorted(curr_rels - prev_rels):
            deltas.append(WorldStateDelta(
                delta_id=_next_id(),
                kind=DeltaKind.RELATION_ADDED,
                target_id=rid,
                description="relation added",
                computed_at=now,
            ))

        for rid in sorted(prev_rels - curr_rels):
            deltas.append(WorldStateDelta(
                delta_id=_next_id(),
                kind=DeltaKind.RELATION_REMOVED,
                target_id=rid,
                description="relation removed",
                computed_at=now,
            ))

        # Derived facts
        prev_facts = {f.fact_id for f in previous.derived_facts}
        curr_facts = {f.fact_id for f in current.derived_facts}
        for fid in sorted(curr_facts - prev_facts):
            deltas.append(WorldStateDelta(
                delta_id=_next_id(),
                kind=DeltaKind.FACT_DERIVED,
                target_id=fid,
                description="fact derived",
                computed_at=now,
            ))

        return tuple(deltas)

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    @property
    def derived_fact_count(self) -> int:
        return len(self._derived_facts)

    @property
    def resolution_count(self) -> int:
        return len(self._resolutions)

    @property
    def expected_state_count(self) -> int:
        return len(self._expected_states)
