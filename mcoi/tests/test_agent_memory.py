"""Phase 216A - Agent memory tests.

Purpose: verify tenant-scoped agent memory core behavior and HTTP routes.
Governance scope: memory lifecycle tests only.
Dependencies: AgentMemoryStore and FastAPI test client.
Invariants: storage is bounded, search is relevance-scored, and summaries stay bounded.
"""

import pytest
from mcoi_runtime.core.agent_memory import AgentMemoryStore


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


class TestAgentMemory:
    def test_store(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        entry = store.store("a1", "t1", "fact", "Python is a programming language")
        assert entry.agent_id == "a1"
        assert entry.category == "fact"

    def test_search(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        store.store("a1", "t1", "fact", "Python is great", keywords=["python", "programming"])
        store.store("a1", "t1", "fact", "Rust is fast", keywords=["rust", "performance"])
        results = store.search("a1", "t1", "python programming")
        assert len(results) >= 1
        assert results[0].memory.content == "Python is great"

    def test_tenant_isolation(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        store.store("a1", "t1", "fact", "T1 secret data")
        store.store("a1", "t2", "fact", "T2 secret data")
        t1 = store.search("a1", "t1", "secret data")
        t2 = store.search("a1", "t2", "secret data")
        assert all(r.memory.tenant_id == "t1" for r in t1)
        assert all(r.memory.tenant_id == "t2" for r in t2)

    def test_by_category(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        store.store("a1", "t1", "preference", "Prefers concise answers")
        store.store("a1", "t1", "fact", "User is a developer")
        prefs = store.get_by_category("a1", "t1", "preference")
        assert len(prefs) == 1

    def test_forget(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        entry = store.store("a1", "t1", "fact", "Temp memory")
        assert store.forget("a1", "t1", entry.memory_id) is True
        assert store.count("a1", "t1") == 0

    def test_capacity_eviction(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK, max_per_agent=3)
        store.store("a1", "t1", "fact", "Low confidence", confidence=0.1)
        store.store("a1", "t1", "fact", "High confidence", confidence=0.9)
        store.store("a1", "t1", "fact", "Medium confidence", confidence=0.5)
        store.store("a1", "t1", "fact", "New entry", confidence=0.8)  # Should evict lowest
        assert store.count("a1", "t1") == 3

    @pytest.mark.parametrize("max_per_agent", [0, -1])
    def test_capacity_requires_positive_limit(self, max_per_agent):
        with pytest.raises(ValueError, match="^max_per_agent must be positive$"):
            AgentMemoryStore(clock=FIXED_CLOCK, max_per_agent=max_per_agent)

    def test_capacity_one_evicts_existing_memory_before_store(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK, max_per_agent=1)
        first = store.store("a1", "t1", "fact", "Low confidence", confidence=0.1)
        second = store.store("a1", "t1", "fact", "New entry", confidence=0.8)
        memories = store.get_by_category("a1", "t1", "fact")
        assert first.memory_id != second.memory_id
        assert store.count("a1", "t1") == 1
        assert [memory.content for memory in memories] == ["New entry"]

    def test_summary(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        store.store("a1", "t1", "fact", "x")
        store.store("a1", "t1", "preference", "y")
        s = store.summary()
        assert s["total"] == 2
        assert s["by_category"]["fact"] == 1


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_memory_store_endpoint_bounded(client) -> None:
    response = client.post(
        "/api/v1/memory/store",
        json={
            "agent_id": "memory-http-agent-store",
            "tenant_id": "tenant-memory-http",
            "category": "fact",
            "content": "Endpoint memory store proof",
            "keywords": ["endpoint", "memory"],
            "confidence": 0.8,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["memory_id"].startswith("mem-")
    assert body["agent_id"] == "memory-http-agent-store"
    assert body["category"] == "fact"


def test_memory_search_endpoint_relevance_scored(client) -> None:
    client.post(
        "/api/v1/memory/store",
        json={
            "agent_id": "memory-http-agent-search",
            "tenant_id": "tenant-memory-http",
            "category": "fact",
            "content": "Python programming preference",
            "keywords": ["python", "programming"],
            "confidence": 0.9,
        },
    )
    response = client.post(
        "/api/v1/memory/search",
        json={
            "agent_id": "memory-http-agent-search",
            "tenant_id": "tenant-memory-http",
            "query": "python programming",
            "limit": 2,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["count"] >= 1
    assert body["results"][0]["content"] == "Python programming preference"
    assert body["results"][0]["relevance"] > 0


def test_memory_summary_endpoint_bounded(client) -> None:
    client.post(
        "/api/v1/memory/store",
        json={
            "agent_id": "memory-http-agent-summary",
            "tenant_id": "tenant-memory-http",
            "category": "preference",
            "content": "Summary endpoint memory proof",
            "confidence": 1.0,
        },
    )
    response = client.get("/api/v1/memory/summary")

    body = response.json()
    assert response.status_code == 200
    assert body["total"] >= 1
    assert body["agents"] >= 1
    assert body["by_category"]["preference"] >= 1
