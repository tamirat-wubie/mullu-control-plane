"""Phase 216A — Agent memory tests."""

import pytest
from mcoi_runtime.core.agent_memory import AgentMemoryStore

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


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

    def test_summary(self):
        store = AgentMemoryStore(clock=FIXED_CLOCK)
        store.store("a1", "t1", "fact", "x")
        store.store("a1", "t1", "preference", "y")
        s = store.summary()
        assert s["total"] == 2
        assert s["by_category"]["fact"] == 1
