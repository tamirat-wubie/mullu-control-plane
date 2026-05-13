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
        with pytest.raises(ValueError) as exc_info:
            eng.register(CapabilityDescriptor(capability_id="llm", name="LLM2", description="y"))
        assert "llm" not in str(exc_info.value)

    def test_assign_unknown_capability_raises(self):
        eng = CapabilityEngine()
        with pytest.raises(ValueError) as exc_info:
            eng.assign_to_agent("a1", "missing")
        assert "missing" not in str(exc_info.value)

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

    def test_assess_readiness_ready_with_dependency_closure(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="shell", name="Shell", description="x"))
        eng.register(CapabilityDescriptor(
            capability_id="repo.inspect", name="Repo Inspect", description="x",
            requires=("shell",),
        ))
        eng.assign_to_agent("agent1", "repo.inspect")

        readiness = eng.assess_readiness("repo.inspect")

        assert readiness.status == "ready"
        assert readiness.score == 1.0
        assert readiness.agent_ids == ("agent1",)
        assert readiness.dependency_closure == ("repo.inspect", "shell")
        assert readiness.reasons == ("capability is enabled, assigned, and dependency-complete",)

    def test_assess_readiness_blocks_missing_dependency(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(
            capability_id="repo.inspect", name="Repo Inspect", description="x",
            requires=("shell",),
        ))
        eng.assign_to_agent("agent1", "repo.inspect")

        readiness = eng.assess_readiness("repo.inspect")

        assert readiness.status == "blocked"
        assert readiness.score == 0.75
        assert readiness.agent_ids == ("agent1",)
        assert readiness.missing_deps == ("shell",)
        assert readiness.reasons == ("dependency is not registered",)

    def test_assess_readiness_blocks_disabled_dependency(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="shell", name="Shell", description="x"))
        eng.register(CapabilityDescriptor(
            capability_id="repo.inspect", name="Repo Inspect", description="x",
            requires=("shell",),
        ))
        eng.assign_to_agent("agent1", "repo.inspect")
        assert eng.disable("shell") is True

        readiness = eng.assess_readiness("repo.inspect")

        assert readiness.status == "blocked"
        assert readiness.score == 0.75
        assert readiness.disabled_deps == ("shell",)
        assert readiness.missing_deps == ()
        assert readiness.dependency_closure == ("repo.inspect", "shell")

    def test_rank_agents_for_orders_by_dependency_coverage(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="shell", name="Shell", description="x"))
        eng.register(CapabilityDescriptor(
            capability_id="repo.inspect", name="Repo Inspect", description="x",
            requires=("shell",),
        ))
        eng.assign_to_agent("agent-a", "repo.inspect")
        eng.assign_to_agent("agent-b", "repo.inspect")
        eng.assign_to_agent("agent-b", "shell")

        scores = eng.rank_agents_for("repo.inspect")

        assert tuple(score.agent_id for score in scores) == ("agent-b", "agent-a")
        assert scores[0].score == 1.0
        assert scores[0].covered_capabilities == ("repo.inspect", "shell")
        assert scores[1].score == 0.5
        assert scores[1].missing_capabilities == ("shell",)

    def test_readiness_report_counts_statuses_deterministically(self):
        eng = CapabilityEngine()
        eng.register(CapabilityDescriptor(capability_id="ready", name="Ready", description="x"))
        eng.register(CapabilityDescriptor(capability_id="disabled", name="Disabled", description="x"))
        eng.register(CapabilityDescriptor(capability_id="waiting", name="Waiting", description="x"))
        eng.register(CapabilityDescriptor(
            capability_id="blocked", name="Blocked", description="x",
            requires=("missing",),
        ))
        eng.assign_to_agent("agent1", "ready")
        eng.assign_to_agent("agent1", "blocked")
        assert eng.disable("disabled") is True

        report = eng.readiness_report()

        assert report["total"] == 4
        assert report["ready"] == 1
        assert report["blocked"] == 1
        assert report["unassigned"] == 1
        assert report["disabled"] == 1
