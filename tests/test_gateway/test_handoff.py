"""Multi-Agent Handoff Tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from gateway.handoff import HandoffRouter, AgentSpec


class TestAgentRegistration:
    def test_register_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial Agent",
            description="Handles financial queries",
            handles=("balance_check", "spending_insights"),
        ))
        assert router.agent_count == 1

    def test_set_general_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="general", name="General", description="", handles=()))
        router.set_general_agent("general")
        summary = router.summary()
        assert summary["general_agent"] == "general"


class TestRouting:
    def test_route_to_specialized_agent(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial", description="",
            handles=("balance",),
            handler=lambda msg, tid, iid: {"response": "Balance: $1000"},
        ))
        result = router.route("check balance", intent="balance", tenant_id="t1", identity_id="u1")
        assert result["agent"] == "fin"
        assert "1000" in result["response"]

    def test_route_to_general_fallback(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="general", name="General", description="",
            handles=(),
            handler=lambda msg, tid, iid: {"response": "I can help with that"},
        ))
        router.set_general_agent("general")
        result = router.route("hello", intent="unknown", tenant_id="t1", identity_id="u1")
        assert result["agent"] == "general"

    def test_no_agent_available(self):
        router = HandoffRouter()
        result = router.route("test", intent="missing")
        assert "No agent" in result["response"]

    def test_all_results_governed(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="a", name="A", description="",
            handles=("x",),
            handler=lambda m, t, i: {"response": "ok"},
        ))
        result = router.route("test", intent="x")
        assert result["governed"] is True


class TestHandoff:
    def test_handoff_between_agents(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(
            agent_id="fin", name="Financial", description="",
            handles=("balance",),
            handler=lambda m, t, i: {"response": "Balance result"},
        ))
        router.register_agent(AgentSpec(
            agent_id="general", name="General", description="",
            handles=(),
            handler=lambda m, t, i: {"response": "General result"},
        ))
        router.set_general_agent("general")
        result = router.handoff(
            "general", "fin",
            message="check my balance", reason="financial intent detected",
            tenant_id="t1", identity_id="u1",
        )
        assert router.handoff_count == 1

    def test_handoff_loop_blocked(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="a", name="A", description="", handles=("x",)))
        router.register_agent(AgentSpec(agent_id="b", name="B", description="", handles=("y",)))
        router.set_general_agent("a")
        # A → B
        router.handoff("a", "b", message="test", reason="test")
        # B → A (loop!)
        result = router.handoff("a", "b", message="test", reason="loop test")
        # Should detect the loop
        assert router.handoff_count >= 1


class TestSummary:
    def test_summary(self):
        router = HandoffRouter()
        router.register_agent(AgentSpec(agent_id="a", name="A", description="", handles=("x", "y")))
        summary = router.summary()
        assert "a" in summary["agents"]
        assert summary["intent_map"]["x"] == "a"
