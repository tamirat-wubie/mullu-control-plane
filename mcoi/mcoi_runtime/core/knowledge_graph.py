"""Knowledge Graph — entity-evidence graph with freshness and contradiction detection.

Purpose: maintain a live knowledge substrate where entities, evidence,
    and relationships are tracked with trust scores and staleness detection.
    Supports domain memory, contradiction detection, and policy-aware retrieval.
Governance scope: knowledge storage and query only.
Dependencies: clock injection.
Invariants:
  - Entities are uniquely identified.
  - Evidence links carry trust scores and timestamps.
  - Contradictions are detected and surfaced, never silently resolved.
  - Graph size is bounded.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any, Callable


class EntityType(StrEnum):
    AGENT = "agent"
    GOAL = "goal"
    ACTION = "action"
    RESOURCE = "resource"
    TENANT = "tenant"
    CONCEPT = "concept"
    CUSTOM = "custom"


class EvidenceStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CONTRADICTED = "contradicted"


@dataclass
class KnowledgeEntity:
    entity_id: str
    entity_type: EntityType
    name: str
    properties: dict[str, Any]
    trust_score: float  # 0.0 - 1.0
    created_at: str
    updated_at: str
    source: str = ""


@dataclass
class EvidenceLink:
    link_id: str
    from_entity: str
    to_entity: str
    relationship: str
    strength: EvidenceStrength
    evidence: dict[str, Any]
    created_at: str
    source: str = ""


@dataclass
class Contradiction:
    contradiction_id: str
    entity_id: str
    claim_a: str
    claim_b: str
    source_a: str
    source_b: str
    detected_at: str
    resolved: bool = False


class KnowledgeGraph:
    """Entity-evidence graph with trust scoring and contradiction detection."""

    _MAX_ENTITIES = 50_000
    _MAX_LINKS = 100_000
    _MAX_CONTRADICTIONS = 10_000

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._entities: dict[str, KnowledgeEntity] = {}
        self._links: dict[str, EvidenceLink] = {}
        self._contradictions: dict[str, Contradiction] = {}
        self._lock = threading.Lock()

    def add_entity(
        self,
        entity_id: str,
        entity_type: EntityType,
        name: str,
        properties: dict[str, Any] | None = None,
        trust_score: float = 1.0,
        source: str = "",
    ) -> KnowledgeEntity:
        now = self._clock()
        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            properties=properties or {},
            trust_score=max(0.0, min(1.0, trust_score)),
            created_at=now,
            updated_at=now,
            source=source,
        )
        with self._lock:
            self._entities[entity_id] = entity
            if len(self._entities) > self._MAX_ENTITIES:
                oldest = min(self._entities.values(), key=lambda e: e.updated_at)
                del self._entities[oldest.entity_id]
        return entity

    def update_entity(
        self,
        entity_id: str,
        properties: dict[str, Any] | None = None,
        trust_score: float | None = None,
    ) -> KnowledgeEntity | None:
        with self._lock:
            entity = self._entities.get(entity_id)
            if entity is None:
                return None
            if properties:
                entity.properties.update(properties)
            if trust_score is not None:
                entity.trust_score = max(0.0, min(1.0, trust_score))
            entity.updated_at = self._clock()
        return entity

    def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return self._entities.get(entity_id)

    def add_link(
        self,
        from_entity: str,
        to_entity: str,
        relationship: str,
        strength: EvidenceStrength = EvidenceStrength.MODERATE,
        evidence: dict[str, Any] | None = None,
        source: str = "",
    ) -> EvidenceLink:
        now = self._clock()
        link_id = f"link-{sha256(f'{from_entity}:{to_entity}:{relationship}:{now}'.encode()).hexdigest()[:12]}"
        link = EvidenceLink(
            link_id=link_id,
            from_entity=from_entity,
            to_entity=to_entity,
            relationship=relationship,
            strength=strength,
            evidence=evidence or {},
            created_at=now,
            source=source,
        )
        with self._lock:
            self._links[link_id] = link
            if len(self._links) > self._MAX_LINKS:
                oldest = min(self._links.values(), key=lambda l: l.created_at)
                del self._links[oldest.link_id]
        return link

    def links_for_entity(self, entity_id: str) -> list[EvidenceLink]:
        with self._lock:
            return [
                l for l in self._links.values()
                if l.from_entity == entity_id or l.to_entity == entity_id
            ]

    def detect_contradiction(
        self,
        entity_id: str,
        claim_a: str,
        claim_b: str,
        source_a: str = "",
        source_b: str = "",
    ) -> Contradiction:
        now = self._clock()
        cid = f"contra-{sha256(f'{entity_id}:{claim_a}:{claim_b}'.encode()).hexdigest()[:12]}"
        contradiction = Contradiction(
            contradiction_id=cid,
            entity_id=entity_id,
            claim_a=claim_a,
            claim_b=claim_b,
            source_a=source_a,
            source_b=source_b,
            detected_at=now,
        )
        with self._lock:
            self._contradictions[cid] = contradiction
            # Degrade trust on contradicted entity
            entity = self._entities.get(entity_id)
            if entity:
                entity.trust_score = max(0.0, entity.trust_score - 0.2)
            if len(self._contradictions) > self._MAX_CONTRADICTIONS:
                oldest = min(self._contradictions.values(), key=lambda c: c.detected_at)
                del self._contradictions[oldest.contradiction_id]
        return contradiction

    def unresolved_contradictions(self) -> list[Contradiction]:
        with self._lock:
            return [c for c in self._contradictions.values() if not c.resolved]

    def resolve_contradiction(self, contradiction_id: str) -> bool:
        with self._lock:
            c = self._contradictions.get(contradiction_id)
            if c is None:
                return False
            c.resolved = True
            return True

    def query(
        self,
        entity_type: EntityType | None = None,
        min_trust: float = 0.0,
        limit: int = 100,
    ) -> list[KnowledgeEntity]:
        with self._lock:
            results = list(self._entities.values())
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if min_trust > 0:
            results = [e for e in results if e.trust_score >= min_trust]
        return sorted(results, key=lambda e: -e.trust_score)[:limit]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entities": len(self._entities),
                "links": len(self._links),
                "contradictions": len(self._contradictions),
                "unresolved_contradictions": sum(
                    1 for c in self._contradictions.values() if not c.resolved
                ),
            }
