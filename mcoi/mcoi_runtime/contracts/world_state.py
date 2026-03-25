"""Purpose: canonical world-state contracts for entities, relations, snapshots,
contradictions, derived facts, expected state, conflict sets, and resolutions.
Governance scope: world-state plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Entities derive from evidence, never fabricated.
  - Derived facts carry full derivation chain.
  - Contradictions are explicit, never silently resolved.
  - Expected states are projections, not verified fact.
  - Confidence derives from evidence quality and verification status.
  - All confidence values are bounded [0.0, 1.0].
  - Snapshots are read-only point-in-time views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


class ContradictionStrategy(StrEnum):
    PREFER_LATEST = "prefer_latest"
    PREFER_HIGHEST_CONFIDENCE = "prefer_highest_confidence"
    ESCALATE = "escalate"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ConfidenceAnnotation(ContractRecord):
    """Confidence score attached to an entity or relation."""

    target_id: str
    confidence: float
    source: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class StateEntity(ContractRecord):
    """A named, typed object in the world model."""

    entity_id: str
    entity_type: str
    attributes: Mapping[str, Any]
    evidence_ids: tuple[str, ...]
    confidence: float = 0.0
    created_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_id", require_non_empty_text(self.entity_id, "entity_id"))
        object.__setattr__(self, "entity_type", require_non_empty_text(self.entity_type, "entity_type"))
        if not isinstance(self.attributes, Mapping):
            raise ValueError("attributes must be a mapping")
        object.__setattr__(self, "attributes", freeze_value(self.attributes))
        if not self.evidence_ids:
            raise ValueError("evidence_ids must contain at least one item")
        for eid in self.evidence_ids:
            require_non_empty_text(eid, "evidence_id")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if self.created_at is not None:
            object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class EntityRelation(ContractRecord):
    """A directed dependency or association between entities."""

    relation_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    evidence_ids: tuple[str, ...]
    confidence: float = 0.0

    def __post_init__(self) -> None:
        for field_name in ("relation_id", "source_entity_id", "target_entity_id", "relation_type"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("self-referential relations are prohibited")
        if not self.evidence_ids:
            raise ValueError("evidence_ids must contain at least one item")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class ContradictionRecord(ContractRecord):
    """Explicit record of conflicting evidence about the same entity."""

    contradiction_id: str
    entity_id: str
    attribute: str
    conflicting_evidence_ids: tuple[str, ...]
    strategy: ContradictionStrategy
    resolved: bool
    resolution_value: Any = None

    def __post_init__(self) -> None:
        for field_name in ("contradiction_id", "entity_id", "attribute"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if len(self.conflicting_evidence_ids) < 2:
            raise ValueError("contradiction requires at least two conflicting evidence IDs")
        if not isinstance(self.strategy, ContradictionStrategy):
            raise ValueError("strategy must be a ContradictionStrategy value")


# ---------------------------------------------------------------------------
# New enums (Phase 31)
# ---------------------------------------------------------------------------


class DeltaKind(StrEnum):
    """Classification of world-state changes."""

    ENTITY_ADDED = "entity_added"
    ENTITY_REMOVED = "entity_removed"
    ENTITY_MODIFIED = "entity_modified"
    RELATION_ADDED = "relation_added"
    RELATION_REMOVED = "relation_removed"
    FACT_DERIVED = "fact_derived"
    EXPECTATION_MET = "expectation_met"
    EXPECTATION_VIOLATED = "expectation_violated"


# ---------------------------------------------------------------------------
# New frozen dataclasses (Phase 31)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DerivedFact(ContractRecord):
    """A fact derived from other entities or evidence, with derivation chain.

    Derived facts are always traceable to their source entities and the
    rule used to produce them.  They are never asserted directly.
    """

    fact_id: str
    entity_id: str
    attribute: str
    derived_value: Any
    source_entity_ids: tuple[str, ...]
    derivation_rule: str
    confidence: float
    derived_at: str

    def __post_init__(self) -> None:
        for f in ("fact_id", "entity_id", "attribute", "derivation_rule"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "derived_value", freeze_value(self.derived_value))
        if not self.source_entity_ids:
            raise ValueError("source_entity_ids must contain at least one item")
        for sid in self.source_entity_ids:
            require_non_empty_text(sid, "source_entity_id")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "derived_at", require_datetime_text(self.derived_at, "derived_at"))


@dataclass(frozen=True, slots=True)
class ExpectedState(ContractRecord):
    """A projection of what the state should be after some action.

    Expected states are projections, not verified fact.  They are
    compared against actual state to detect drift and violation.
    """

    expectation_id: str
    entity_id: str
    attribute: str
    expected_value: Any
    basis: str
    confidence: float
    expected_by: str
    created_at: str

    def __post_init__(self) -> None:
        for f in ("expectation_id", "entity_id", "attribute", "basis"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "expected_value", freeze_value(self.expected_value))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "expected_by", require_non_empty_text(self.expected_by, "expected_by"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ConflictSet(ContractRecord):
    """Grouped contradictions about the same entity.

    A conflict set aggregates multiple contradictions that share the
    same entity, making it easier to reason about resolution strategy.
    """

    conflict_set_id: str
    entity_id: str
    contradictions: tuple[ContradictionRecord, ...]
    overall_strategy: ContradictionStrategy
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflict_set_id", require_non_empty_text(self.conflict_set_id, "conflict_set_id"))
        object.__setattr__(self, "entity_id", require_non_empty_text(self.entity_id, "entity_id"))
        if not self.contradictions:
            raise ValueError("contradictions must contain at least one item")
        for item in self.contradictions:
            if not isinstance(item, ContradictionRecord):
                raise ValueError("each contradiction must be a ContradictionRecord instance")
        if not isinstance(self.overall_strategy, ContradictionStrategy):
            raise ValueError("overall_strategy must be a ContradictionStrategy value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ResolutionRecord(ContractRecord):
    """Records how a conflict or contradiction was resolved."""

    resolution_id: str
    contradiction_id: str
    resolved_value: Any
    strategy_used: ContradictionStrategy
    resolver_id: str
    confidence: float
    resolved_at: str

    def __post_init__(self) -> None:
        for f in ("resolution_id", "contradiction_id", "resolver_id"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "resolved_value", freeze_value(self.resolved_value))
        if not isinstance(self.strategy_used, ContradictionStrategy):
            raise ValueError("strategy_used must be a ContradictionStrategy value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "resolved_at", require_datetime_text(self.resolved_at, "resolved_at"))


@dataclass(frozen=True, slots=True)
class StateConfidenceEnvelope(ContractRecord):
    """Confidence range around a state assertion for a specific entity attribute."""

    envelope_id: str
    entity_id: str
    attribute: str
    point_estimate: float
    lower_bound: float
    upper_bound: float
    evidence_count: int
    assessed_at: str

    def __post_init__(self) -> None:
        for f in ("envelope_id", "entity_id", "attribute"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "point_estimate", require_unit_float(self.point_estimate, "point_estimate"))
        object.__setattr__(self, "lower_bound", require_unit_float(self.lower_bound, "lower_bound"))
        object.__setattr__(self, "upper_bound", require_unit_float(self.upper_bound, "upper_bound"))
        if self.lower_bound > self.point_estimate:
            raise ValueError("lower_bound must be <= point_estimate")
        if self.point_estimate > self.upper_bound:
            raise ValueError("point_estimate must be <= upper_bound")
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class WorldStateDelta(ContractRecord):
    """A single change in the world state between two points in time."""

    delta_id: str
    kind: DeltaKind
    target_id: str
    description: str
    previous_value: str | None = None
    new_value: str | None = None
    computed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "delta_id", require_non_empty_text(self.delta_id, "delta_id"))
        if not isinstance(self.kind, DeltaKind):
            raise ValueError("kind must be a DeltaKind value")
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        object.__setattr__(self, "computed_at", require_datetime_text(self.computed_at, "computed_at"))


@dataclass(frozen=True, slots=True)
class WorldStateSnapshot(ContractRecord):
    """Point-in-time snapshot of the entire world state.

    Composes entities, relations, derived facts, unresolved contradictions,
    and expected states into a single immutable view.
    """

    snapshot_id: str
    entities: tuple[StateEntity, ...]
    relations: tuple[EntityRelation, ...]
    derived_facts: tuple[DerivedFact, ...]
    unresolved_contradictions: tuple[ContradictionRecord, ...]
    expected_states: tuple[ExpectedState, ...]
    state_hash: str
    entity_count: int
    relation_count: int
    overall_confidence: float
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "entities", freeze_value(list(self.entities)))
        for item in self.entities:
            if not isinstance(item, StateEntity):
                raise ValueError("each entity must be a StateEntity instance")
        object.__setattr__(self, "relations", freeze_value(list(self.relations)))
        for item in self.relations:
            if not isinstance(item, EntityRelation):
                raise ValueError("each relation must be an EntityRelation instance")
        object.__setattr__(self, "derived_facts", freeze_value(list(self.derived_facts)))
        for item in self.derived_facts:
            if not isinstance(item, DerivedFact):
                raise ValueError("each derived_fact must be a DerivedFact instance")
        object.__setattr__(
            self, "unresolved_contradictions", freeze_value(list(self.unresolved_contradictions)),
        )
        for item in self.unresolved_contradictions:
            if not isinstance(item, ContradictionRecord):
                raise ValueError("each unresolved_contradiction must be a ContradictionRecord")
        object.__setattr__(self, "expected_states", freeze_value(list(self.expected_states)))
        for item in self.expected_states:
            if not isinstance(item, ExpectedState):
                raise ValueError("each expected_state must be an ExpectedState instance")
        object.__setattr__(self, "state_hash", require_non_empty_text(self.state_hash, "state_hash"))
        object.__setattr__(self, "entity_count", require_non_negative_int(self.entity_count, "entity_count"))
        object.__setattr__(self, "relation_count", require_non_negative_int(self.relation_count, "relation_count"))
        object.__setattr__(
            self, "overall_confidence", require_unit_float(self.overall_confidence, "overall_confidence"),
        )
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))
