"""Purpose: canonical world-state contracts for entities, relations, snapshots, and contradictions.
Governance scope: world-state plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Entities derive from evidence, never fabricated.
  - Contradictions are explicit, never silently resolved.
  - Confidence derives from evidence quality and verification status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


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
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
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
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
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
        if not isinstance(self.confidence, (int, float)) or self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")


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
