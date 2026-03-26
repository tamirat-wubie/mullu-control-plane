"""Phase 207C — Capability engine tests."""

import pytest
from mcoi_runtime.core.capability_engine import CapabilityDescriptor, CapabilityEngine


class TestCapabilityEngine:
    def test_register(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="LLM calls"))
        assert eng.count == 1

    def test_duplicate_register(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        with pytest.raises(ValueError):
            eng.register(CapabilityDescriptor(capability_id="llm", name="LLM2", description="y"))

    def test_assign_and_find(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        eng.assign_to_agent("a1", "llm")
        assert eng.agent_has("a1", "llm") is True
        assert eng.find_agents("llm") == ["a1"]

    def test_find_no_agents(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        assert eng.find_agents("llm") == []

    def test_match_success(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        eng.assign_to_agent("a1", "llm")
        match = eng.match("llm")
        assert match.matched is True
        assert "a1" in match.agent_ids

    def test_match_unknown(self):
        eng = CapabilityEngine()
        match = eng.match("nonexistent")
        assert match.matched is False

    def test_match_missing_deps(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(
            capability_id="analysis", name="Analysis", description="x",
            requires=("llm",),
        ))
        eng.assign_to_agent("a1", "analysis")
        match = eng.match("analysis")
        assert match.matched is False
        assert "llm" in match.missing_deps

    def test_match_with_deps(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        eng.register(CapabilityDescriptor(
            capability_id="analysis", name="Analysis", description="x",
            requires=("llm",),
        ))
        eng.assign_to_agent("a1", "analysis")
        match = eng.match("analysis")
        assert match.matched is True

    def test_list_by_category(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x", category="llm"))
        eng.register(CapabilityDescriptor(capability_id="code", name="Code", description="x", category="tool"))
        assert len(eng.list_capabilities(category="llm")) == 1
        assert len(eng.list_capabilities()) == 2

    def test_agent_capabilities(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="a", name="A", description="x"))
        eng.register(CapabilityDescriptor(capability_id="b", name="B", description="x"))
        eng.assign_to_agent("agent1", "a")
        eng.assign_to_agent("agent1", "b")
        caps = eng.agent_capabilities("agent1")
        assert len(caps) == 2

    def test_disable(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="llm", name="LLM", description="x"))
        eng.assign_to_agent("a1", "llm")
        eng.disable("llm")
        assert eng.find_agents("llm") == []

    def test_summary(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="a", name="A", description="x", category="llm"))
        eng.assign_to_agent("a1", "a")
        summary = eng.summary()
        assert summary["total"] == 1
        assert summary["by_category"]["llm"] == 1
