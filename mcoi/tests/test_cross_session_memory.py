"""Cross-Session Memory Tests."""

import pytest
from mcoi_runtime.core.cross_session_memory import (
    AgentMemory,
    CrossSessionMemory,
    MemoryQuery,
    MemoryType,
)


def _mem():
    return CrossSessionMemory(clock=lambda: "2026-04-07T12:00:00Z")


class TestAddAndRecall:
    def test_add_memory(self):
        m = _mem()
        result = m.add(tenant_id="t1", content="User likes brief answers", importance=0.8)
        assert result.memory_id.startswith("mem-")
        assert result.importance == 0.8

    def test_recall_by_tenant(self):
        m = _mem()
        m.add(tenant_id="t1", content="Fact A")
        m.add(tenant_id="t2", content="Fact B")
        results = m.recall(MemoryQuery(tenant_id="t1"))
        assert len(results) == 1
        assert results[0].content == "Fact A"

    def test_recall_by_identity(self):
        m = _mem()
        m.add(tenant_id="t1", identity_id="u1", content="Pref A")
        m.add(tenant_id="t1", identity_id="u2", content="Pref B")
        results = m.recall(MemoryQuery(tenant_id="t1", identity_id="u1"))
        assert len(results) == 1

    def test_recall_by_type(self):
        m = _mem()
        m.add(tenant_id="t1", memory_type=MemoryType.PREFERENCE, content="Likes brief")
        m.add(tenant_id="t1", memory_type=MemoryType.FACT, content="Account is premium")
        results = m.recall(MemoryQuery(tenant_id="t1", memory_type=MemoryType.PREFERENCE))
        assert len(results) == 1

    def test_recall_by_importance(self):
        m = _mem()
        m.add(tenant_id="t1", content="Low", importance=0.2)
        m.add(tenant_id="t1", content="High", importance=0.9)
        results = m.recall(MemoryQuery(tenant_id="t1", min_importance=0.5))
        assert len(results) == 1
        assert results[0].content == "High"

    def test_recall_ranked_by_importance(self):
        m = _mem()
        m.add(tenant_id="t1", content="Med", importance=0.5)
        m.add(tenant_id="t1", content="High", importance=0.9)
        m.add(tenant_id="t1", content="Low", importance=0.3)
        results = m.recall(MemoryQuery(tenant_id="t1", limit=10))
        assert results[0].content == "High"
        assert results[-1].content == "Low"

    def test_recall_limit(self):
        m = _mem()
        for i in range(10):
            m.add(tenant_id="t1", content=f"Fact {i}")
        results = m.recall(MemoryQuery(tenant_id="t1", limit=3))
        assert len(results) == 3

    def test_recall_by_tags(self):
        m = _mem()
        m.add(tenant_id="t1", content="Tagged", tags=["finance"])
        m.add(tenant_id="t1", content="Untagged")
        results = m.recall(MemoryQuery(tenant_id="t1", tags=frozenset({"finance"})))
        assert len(results) == 1
        assert results[0].content == "Tagged"

    def test_access_count_increments(self):
        m = _mem()
        m.add(tenant_id="t1", content="Test")
        m.recall(MemoryQuery(tenant_id="t1"))
        m.recall(MemoryQuery(tenant_id="t1"))
        results = m.recall(MemoryQuery(tenant_id="t1"))
        assert results[0].access_count == 3


class TestDeduplication:
    def test_same_content_deduped(self):
        m = _mem()
        m.add(tenant_id="t1", identity_id="u1", content="Same fact", importance=0.5)
        m.add(tenant_id="t1", identity_id="u1", content="Same fact", importance=0.9)
        assert m.memory_count("t1") == 1
        results = m.recall(MemoryQuery(tenant_id="t1"))
        assert results[0].importance == 0.9  # Boosted

    def test_different_identity_not_deduped(self):
        m = _mem()
        m.add(tenant_id="t1", identity_id="u1", content="Same fact")
        m.add(tenant_id="t1", identity_id="u2", content="Same fact")
        assert m.memory_count("t1") == 2


class TestCapacity:
    def test_eviction_at_capacity(self):
        m = _mem()
        m.MAX_PER_TENANT = 5
        for i in range(10):
            m.add(tenant_id="t1", content=f"Fact {i}", importance=i * 0.1)
        assert m.memory_count("t1") <= 5

    def test_lowest_importance_evicted(self):
        m = _mem()
        m.MAX_PER_TENANT = 3
        m.add(tenant_id="t1", content="Low", importance=0.1)
        m.add(tenant_id="t1", content="Med", importance=0.5)
        m.add(tenant_id="t1", content="High", importance=0.9)
        m.add(tenant_id="t1", content="New", importance=0.6)
        # Low (0.1) should have been evicted
        results = m.recall(MemoryQuery(tenant_id="t1", limit=10))
        contents = {r.content for r in results}
        assert "Low" not in contents
        assert "High" in contents


class TestContextPrompt:
    def test_build_context(self):
        m = _mem()
        m.add(tenant_id="t1", memory_type=MemoryType.PREFERENCE, content="Likes brief answers")
        m.add(tenant_id="t1", memory_type=MemoryType.FACT, content="Premium account")
        prompt = m.build_context_prompt(MemoryQuery(tenant_id="t1"))
        assert "previous interactions" in prompt.lower()
        assert "brief answers" in prompt
        assert "Premium account" in prompt

    def test_empty_context(self):
        m = _mem()
        assert m.build_context_prompt(MemoryQuery(tenant_id="t1")) == ""


class TestForget:
    def test_forget_specific(self):
        m = _mem()
        mem = m.add(tenant_id="t1", content="Secret")
        assert m.forget("t1", mem.memory_id) is True
        assert m.memory_count("t1") == 0

    def test_forget_nonexistent(self):
        m = _mem()
        assert m.forget("t1", "nonexistent") is False

    def test_forget_tenant(self):
        m = _mem()
        m.add(tenant_id="t1", content="A")
        m.add(tenant_id="t1", content="B")
        m.add(tenant_id="t2", content="C")
        count = m.forget_tenant("t1")
        assert count == 2
        assert m.memory_count("t1") == 0
        assert m.memory_count("t2") == 1


class TestSummary:
    def test_summary(self):
        m = _mem()
        m.add(tenant_id="t1", content="A")
        m.add(tenant_id="t2", content="B")
        s = m.summary()
        assert s["tenants"] == 2
        assert s["total_memories"] == 2
        assert s["total_added"] == 2
