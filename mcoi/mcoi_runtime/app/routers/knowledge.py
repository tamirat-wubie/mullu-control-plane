"""Knowledge graph endpoints — entities, evidence, contradictions."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


def _knowledge_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


class AddEntityRequest(BaseModel):
    entity_id: str
    entity_type: str = "concept"
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    trust_score: float = 1.0
    source: str = ""


class AddLinkRequest(BaseModel):
    from_entity: str
    to_entity: str
    relationship: str
    strength: str = "moderate"
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str = ""


class ContradictionRequest(BaseModel):
    entity_id: str
    claim_a: str
    claim_b: str
    source_a: str = ""
    source_b: str = ""


@router.post("/api/v1/knowledge/entities")
def add_entity(req: AddEntityRequest):
    from mcoi_runtime.core.knowledge_graph import EntityType
    deps.metrics.inc("requests_governed")
    try:
        etype = EntityType(req.entity_type)
    except ValueError:
        etype = EntityType.CUSTOM
    entity = deps.knowledge_graph.add_entity(
        req.entity_id, etype, req.name,
        properties=req.properties,
        trust_score=req.trust_score,
        source=req.source,
    )
    return {
        "entity_id": entity.entity_id,
        "name": entity.name,
        "type": entity.entity_type.value,
        "trust_score": entity.trust_score,
        "governed": True,
    }


@router.get("/api/v1/knowledge/entities")
def query_entities(entity_type: str = "", min_trust: float = 0.0, limit: int = 50):
    from mcoi_runtime.core.knowledge_graph import EntityType
    deps.metrics.inc("requests_governed")
    etype = None
    if entity_type:
        try:
            etype = EntityType(entity_type)
        except ValueError:
            raise HTTPException(
                400,
                detail=_knowledge_error_detail("invalid entity type", "invalid_entity_type"),
            )
    entities = deps.knowledge_graph.query(entity_type=etype, min_trust=min_trust, limit=limit)
    return {
        "entities": [
            {
                "entity_id": e.entity_id,
                "name": e.name,
                "type": e.entity_type.value,
                "trust_score": e.trust_score,
                "source": e.source,
            }
            for e in entities
        ],
        "count": len(entities),
        "governed": True,
    }


@router.post("/api/v1/knowledge/links")
def add_link(req: AddLinkRequest):
    from mcoi_runtime.core.knowledge_graph import EvidenceStrength
    deps.metrics.inc("requests_governed")
    try:
        strength = EvidenceStrength(req.strength)
    except ValueError:
        strength = EvidenceStrength.MODERATE
    link = deps.knowledge_graph.add_link(
        req.from_entity, req.to_entity, req.relationship,
        strength=strength,
        evidence=req.evidence,
        source=req.source,
    )
    return {
        "link_id": link.link_id,
        "relationship": link.relationship,
        "strength": link.strength.value,
        "governed": True,
    }


@router.get("/api/v1/knowledge/entities/{entity_id}/links")
def entity_links(entity_id: str):
    deps.metrics.inc("requests_governed")
    links = deps.knowledge_graph.links_for_entity(entity_id)
    return {
        "entity_id": entity_id,
        "links": [
            {
                "link_id": link.link_id,
                "from": link.from_entity,
                "to": link.to_entity,
                "relationship": link.relationship,
                "strength": link.strength.value,
            }
            for link in links
        ],
        "count": len(links),
        "governed": True,
    }


@router.post("/api/v1/knowledge/contradictions")
def report_contradiction(req: ContradictionRequest):
    deps.metrics.inc("requests_governed")
    c = deps.knowledge_graph.detect_contradiction(
        req.entity_id, req.claim_a, req.claim_b,
        source_a=req.source_a, source_b=req.source_b,
    )
    return {
        "contradiction_id": c.contradiction_id,
        "entity_id": c.entity_id,
        "governed": True,
    }


@router.get("/api/v1/knowledge/contradictions/unresolved")
def unresolved_contradictions():
    deps.metrics.inc("requests_governed")
    contradictions = deps.knowledge_graph.unresolved_contradictions()
    return {
        "contradictions": [
            {
                "contradiction_id": c.contradiction_id,
                "entity_id": c.entity_id,
                "claim_a": c.claim_a,
                "claim_b": c.claim_b,
            }
            for c in contradictions
        ],
        "count": len(contradictions),
        "governed": True,
    }


@router.get("/api/v1/knowledge/summary")
def knowledge_summary():
    deps.metrics.inc("requests_governed")
    return {**deps.knowledge_graph.summary(), "governed": True}
