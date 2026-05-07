"""Tests for Phase 222C — Agent Orchestration Protocol.

Governance scope: validate multi-agent coordination, consensus protocols,
    capability-based handoffs, and plan lifecycle.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcoi_runtime.core.agent_orchestration import (
    AgentOrchestrator,
    AgentProposal,
    HandoffResult,
    OrchestrationPhase,
    OrchestrationPlan,
    Vote,
)


def _clock():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def orchestrator():
    orch = AgentOrchestrator(clock=_clock)
    orch.register_agent("agent-a", ("llm", "search"))
    orch.register_agent("agent-b", ("llm", "code"))
    orch.register_agent("agent-c", ("search", "code", "deploy"))
    return orch


class TestAgentRegistration:
    def test_register_and_count(self, orchestrator):
        assert orchestrator.agent_count == 3

    def test_unregister(self, orchestrator):
        orchestrator.unregister_agent("agent-c")
        assert orchestrator.agent_count == 2

    def test_unregister_nonexistent(self, orchestrator):
        orchestrator.unregister_agent("ghost")  # no error
        assert orchestrator.agent_count == 3


class TestPlanLifecycle:
    def test_create_plan(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "Summarize document")
        assert plan.plan_id
        assert plan.phase == OrchestrationPhase.PLANNING
        assert plan.initiator_id == "agent-a"

    def test_create_plan_unknown_agent(self, orchestrator):
        with pytest.raises(ValueError, match="^initiator agent unavailable$") as exc_info:
            orchestrator.create_plan("ghost", "goal")
        assert "ghost" not in str(exc_info.value)

    def test_add_proposal(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        orchestrator.add_proposal(plan.plan_id, proposal)
        assert len(plan.proposals) == 1

    def test_add_proposal_wrong_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(proposal_id="p1", agent_id="agent-a",
                                 action="search", description="d")
        orchestrator.add_proposal(plan.plan_id, proposal)
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^plan not accepting proposals$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, proposal)
        assert OrchestrationPhase.VOTING.value not in str(exc_info.value)

    def test_add_proposal_plan_unavailable(self, orchestrator):
        proposal = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.add_proposal("missing-plan", proposal)
        assert "missing-plan" not in str(exc_info.value)

    def test_submit_empty_plan_fails(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="empty plan"):
            orchestrator.submit_for_voting(plan.plan_id)


class TestVotingAndConsensus:
    def test_voting_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        assert plan.phase == OrchestrationPhase.VOTING

    def test_cast_vote(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        assert plan.approval_count == 2

    def test_quorum_reached(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        assert orchestrator.check_consensus(plan.plan_id)

    def test_quorum_not_reached(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.REJECT)
        orchestrator.cast_vote(plan.plan_id, "agent-c", Vote.REJECT)
        assert not orchestrator.check_consensus(plan.plan_id)

    def test_vote_wrong_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="^plan not accepting votes$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        assert OrchestrationPhase.PLANNING.value not in str(exc_info.value)

    def test_vote_unknown_agent(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^voting agent unavailable$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "ghost", Vote.APPROVE)
        assert "ghost" not in str(exc_info.value)

    def test_vote_plan_unavailable(self, orchestrator):
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.cast_vote("missing-plan", "agent-a", Vote.APPROVE)
        assert "missing-plan" not in str(exc_info.value)


class TestPlanExecution:
    def test_execute_with_quorum(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="search",
            description="d", priority=10,
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        result = orchestrator.execute_plan(plan.plan_id)
        assert result.phase == OrchestrationPhase.COMPLETED
        assert len(result.results) == 1
        assert result.results[0]["success"]

    def test_execute_without_quorum_fails(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        result = orchestrator.execute_plan(plan.plan_id)
        assert result.phase == OrchestrationPhase.FAILED

    def test_execute_with_custom_executor(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        result = orchestrator.execute_plan(
            plan.plan_id,
            executor=lambda p: {"output": f"executed {p.proposal_id}"},
        )
        assert result.phase == OrchestrationPhase.COMPLETED
        assert result.results[0]["output"] == "executed p1"

    def test_execute_with_failing_executor(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        result = orchestrator.execute_plan(
            plan.plan_id,
            executor=lambda p: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert result.phase == OrchestrationPhase.FAILED
        assert result.results[0]["error"] == "proposal execution error (RuntimeError)"
        assert "boom" not in result.results[0]["error"]

    def test_execute_plan_wrong_phase_is_bounded(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="^plan not ready for execution$") as exc_info:
            orchestrator.execute_plan(plan.plan_id)
        assert OrchestrationPhase.PLANNING.value not in str(exc_info.value)

    def test_execute_plan_unavailable_is_bounded(self, orchestrator):
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.execute_plan("missing-plan")
        assert "missing-plan" not in str(exc_info.value)


class TestHandoffs:
    def test_successful_handoff(self, orchestrator):
        result = orchestrator.handoff("agent-a", "agent-c",
                                       required_capabilities=("search",),
                                       payload={"doc_id": "123"})
        assert result.success
        assert result.payload["doc_id"] == "123"

    def test_handoff_missing_capability(self, orchestrator):
        result = orchestrator.handoff("agent-a", "agent-b",
                                       required_capabilities=("deploy",))
        assert not result.success
        assert result.error == "target agent lacks required capabilities"
        assert "deploy" not in result.error

    def test_handoff_unknown_source(self, orchestrator):
        result = orchestrator.handoff("ghost", "agent-a")
        assert not result.success
        assert result.error == "source agent unavailable"
        assert "ghost" not in result.error

    def test_handoff_unknown_target(self, orchestrator):
        result = orchestrator.handoff("agent-a", "ghost")
        assert not result.success
        assert result.error == "target agent unavailable"
        assert "ghost" not in result.error

    def test_find_capable_agents(self, orchestrator):
        agents = orchestrator.find_capable_agents(("code", "deploy"))
        assert agents == ["agent-c"]

    def test_find_capable_agents_llm(self, orchestrator):
        agents = orchestrator.find_capable_agents(("llm",))
        assert set(agents) == {"agent-a", "agent-b"}


class TestSummary:
    def test_summary(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        s = orchestrator.summary()
        assert s["registered_agents"] == 3
        assert s["total_plans"] == 1
        assert s["active_plans"] == 1

    def test_plan_to_dict(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        d = plan.to_dict()
        assert d["plan_id"] == plan.plan_id
        assert d["phase"] == "planning"
        assert d["approval_count"] == 0
