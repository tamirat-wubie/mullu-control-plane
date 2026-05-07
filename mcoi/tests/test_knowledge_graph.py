"""Purpose: verify knowledge graph engine and HTTP endpoints.
Governance scope: knowledge graph tests only.
Dependencies: knowledge_graph module, FastAPI test client.
Invariants: entities unique; contradictions detected; trust degrades.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.knowledge_graph import (
    EntityType,
    EvidenceStrength,
    KnowledgeGraph,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_graph() -> KnowledgeGraph:
    return KnowledgeGraph(clock=lambda: _CLOCK)


# --- Core Tests ---


def test_add_and_get_entity() -> None:
    g = _make_graph()
    e = g.add_entity("e1", EntityType.AGENT, "Agent Alpha")
    assert e.entity_id == "e1"
    assert g.get_entity("e1") is not None


def test_update_entity_trust() -> None:
    g = _make_graph()
    g.add_entity("e1", EntityType.CONCEPT, "Test", trust_score=1.0)
    g.update_entity("e1", trust_score=0.5)
    assert g.get_entity("e1").trust_score == 0.5


def test_add_link() -> None:
    g = _make_graph()
    g.add_entity("a", EntityType.AGENT, "A")
    g.add_entity("b", EntityType.GOAL, "B")
    link = g.add_link("a", "b", "works_on", strength=EvidenceStrength.STRONG)
    assert link.relationship == "works_on"
    assert len(g.links_for_entity("a")) == 1


def test_detect_contradiction_degrades_trust() -> None:
    g = _make_graph()
    g.add_entity("e1", EntityType.CONCEPT, "Fact", trust_score=1.0)
    g.detect_contradiction("e1", "X is true", "X is false")
    assert g.get_entity("e1").trust_score < 1.0


def test_unresolved_contradictions() -> None:
    g = _make_graph()
    g.add_entity("e1", EntityType.CONCEPT, "Fact")
    g.detect_contradiction("e1", "A", "B")
    assert len(g.unresolved_contradictions()) == 1


def test_resolve_contradiction() -> None:
    g = _make_graph()
    g.add_entity("e1", EntityType.CONCEPT, "Fact")
    c = g.detect_contradiction("e1", "A", "B")
    g.resolve_contradiction(c.contradiction_id)
    assert len(g.unresolved_contradictions()) == 0


def test_query_by_type() -> None:
    g = _make_graph()
    g.add_entity("a1", EntityType.AGENT, "Agent")
    g.add_entity("g1", EntityType.GOAL, "Goal")
    results = g.query(entity_type=EntityType.AGENT)
    assert len(results) == 1
    assert results[0].entity_id == "a1"


def test_query_by_min_trust() -> None:
    g = _make_graph()
    g.add_entity("h", EntityType.CONCEPT, "High", trust_score=0.9)
    g.add_entity("l", EntityType.CONCEPT, "Low", trust_score=0.1)
    results = g.query(min_trust=0.5)
    assert len(results) == 1


def test_summary() -> None:
    g = _make_graph()
    g.add_entity("e1", EntityType.AGENT, "A")
    g.add_link("e1", "e1", "self")
    s = g.summary()
    assert s["entities"] == 1
    assert s["links"] == 1


# --- HTTP Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_add_entity_endpoint(client) -> None:
    resp = client.post("/api/v1/knowledge/entities", json={
        "entity_id": "http-e1",
        "entity_type": "agent",
        "name": "HTTP Agent",
    })
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_query_entities_endpoint(client) -> None:
    resp = client.get("/api/v1/knowledge/entities")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_query_entities_invalid_type_fails_closed_without_leakage(client) -> None:
    resp = client.get(
        "/api/v1/knowledge/entities",
        params={"entity_type": "secret-entity-type"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "invalid_entity_type"
    assert resp.json()["detail"]["governed"] is True
    assert "secret-entity-type" not in str(resp.json())


def test_add_link_endpoint(client) -> None:
    client.post("/api/v1/knowledge/entities", json={
        "entity_id": "link-a", "name": "A", "entity_type": "agent",
    })
    client.post("/api/v1/knowledge/entities", json={
        "entity_id": "link-b", "name": "B", "entity_type": "goal",
    })
    resp = client.post("/api/v1/knowledge/links", json={
        "from_entity": "link-a",
        "to_entity": "link-b",
        "relationship": "pursues",
    })
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_knowledge_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/knowledge/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "entities" in data
    assert "contradictions" in data
    assert data["governed"] is True
