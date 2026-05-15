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
    OrchestrationPhase,
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
        assert len(plan.proposal_proofs) == 1
        assert plan.proposal_proofs[0].decision == "accepted"
        assert plan.proposal_proofs[0].reason == "proposal admitted"

    def test_add_proposal_wrong_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(proposal_id="p1", agent_id="agent-a",
                                 action="search", description="d")
        orchestrator.add_proposal(plan.plan_id, proposal)
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^plan not accepting proposals$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, proposal)
        assert OrchestrationPhase.VOTING.value not in str(exc_info.value)
        assert plan.proposal_proofs[-1].decision == "rejected"
        assert plan.proposal_proofs[-1].reason == "plan not accepting proposals"

    def test_add_proposal_rejects_duplicate_proposal_id(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        first = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        duplicate = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search-again", description="Search docs again",
        )

        orchestrator.add_proposal(plan.plan_id, first)
        with pytest.raises(ValueError, match="^proposal already recorded$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, duplicate)

        assert "p1" not in str(exc_info.value)
        assert len(plan.proposals) == 1
        assert plan.proposal_proofs[-1].decision == "rejected"
        assert plan.proposal_proofs[-1].reason == "proposal already recorded"

    def test_add_proposal_plan_unavailable(self, orchestrator):
        proposal = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.add_proposal("missing-plan", proposal)
        assert "missing-plan" not in str(exc_info.value)

    def test_add_proposal_rejects_unknown_proposer_before_voting(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(
            proposal_id="p1",
            agent_id="ghost",
            action="search",
            description="Search docs",
            required_capabilities=("search",),
        )

        with pytest.raises(ValueError, match="^proposal agent unavailable$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, proposal)

        assert "ghost" not in str(exc_info.value)
        assert plan.proposals == []
        assert plan.proposal_proofs[0].decision == "rejected"
        assert plan.proposal_proofs[0].agent_registered is False

    def test_add_proposal_rejects_missing_agent_capability_before_voting(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(
            proposal_id="p1",
            agent_id="agent-b",
            action="deploy",
            description="Deploy change",
            required_capabilities=("deploy",),
        )

        with pytest.raises(ValueError, match="^proposal agent lacks required capabilities$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, proposal)

        assert "deploy" not in str(exc_info.value)
        assert plan.proposals == []
        assert plan.proposal_proofs[0].decision == "rejected"
        assert plan.proposal_proofs[0].agent_capable is False

    def test_add_proposal_rejects_unmanifested_capability_before_voting(self):
        orch = AgentOrchestrator(
            clock=_clock,
            agent_capabilities={"agent-a": ("search", "deploy")},
            admitted_capabilities=("search",),
        )
        plan = orch.create_plan("agent-a", "goal")
        proposal = AgentProposal(
            proposal_id="p1",
            agent_id="agent-a",
            action="deploy",
            description="Deploy change",
            required_capabilities=("deploy",),
        )

        with pytest.raises(ValueError, match="^proposal requires unadmitted capabilities$") as exc_info:
            orch.add_proposal(plan.plan_id, proposal)

        assert "deploy" not in str(exc_info.value)
        assert plan.proposals == []
        assert plan.proposal_proofs[0].decision == "rejected"
        assert plan.proposal_proofs[0].manifest_admitted is False

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
        assert [proof.decision for proof in plan.vote_proofs] == ["accepted", "accepted"]
        assert [proof.vote for proof in plan.vote_proofs] == ["approve", "approve"]

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
        assert plan.vote_proofs[0].decision == "rejected"
        assert plan.vote_proofs[0].reason == "plan not accepting votes"

    def test_vote_unknown_agent(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^voting agent unavailable$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "ghost", Vote.APPROVE)
        assert "ghost" not in str(exc_info.value)
        assert plan.vote_proofs[0].decision == "rejected"
        assert plan.vote_proofs[0].voter_registered is False

    def test_vote_rejects_duplicate_voter(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)

        with pytest.raises(ValueError, match="^vote already recorded$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.REJECT)

        assert "agent-a" not in str(exc_info.value)
        assert plan.votes["agent-a"] == Vote.APPROVE
        assert plan.vote_proofs[-1].decision == "rejected"
        assert plan.vote_proofs[-1].reason == "vote already recorded"

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
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].decision == "executed"
        assert result.dispatch_proofs[0].reason == "proposal dispatched"

    def test_execute_without_quorum_fails(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        result = orchestrator.execute_plan(plan.plan_id)
        assert result.phase == OrchestrationPhase.FAILED
        assert result.results == []
        assert len(result.dispatch_proofs) == 1
        assert result.dispatch_proofs[0].decision == "blocked"
        assert result.dispatch_proofs[0].reason == "consensus quorum not met"
        assert result.dispatch_proofs[0].quorum_met is False

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
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].agent_registered is True
        assert result.dispatch_proofs[0].manifest_admitted is True

    def test_execute_suppresses_executor_reserved_result_keys(self, orchestrator):
        class SpoofedProofKey:
            def __str__(self) -> str:
                return "proof_id"

        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)

        result = orchestrator.execute_plan(
            plan.plan_id,
            executor=lambda p: {
                "proposal_id": "spoofed",
                "proof_id": "spoofed",
                "success": False,
                "error": "spoofed",
                "suppressed_executor_keys": ("spoofed",),
                SpoofedProofKey(): "spoofed",
                "output": f"executed {p.proposal_id}",
            },
        )

        assert result.phase == OrchestrationPhase.COMPLETED
        assert result.results[0]["proposal_id"] == "p1"
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.results[0]["success"] is True
        assert result.results[0]["output"] == "executed p1"
        assert "error" not in result.results[0]
        assert result.results[0]["suppressed_executor_keys"] == (
            "proposal_id",
            "proof_id",
            "success",
            "error",
            "suppressed_executor_keys",
            "proof_id",
        )

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
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].decision == "failed"
        assert result.dispatch_proofs[0].reason == "executor error"

    def test_execute_revalidates_proposal_agent_availability(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1",
            agent_id="agent-c",
            action="deploy",
            description="Deploy change",
            required_capabilities=("deploy",),
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        orchestrator.unregister_agent("agent-c")

        result = orchestrator.execute_plan(plan.plan_id)

        assert result.phase == OrchestrationPhase.FAILED
        assert result.results[0]["success"] is False
        assert result.results[0]["error"] == "proposal agent unavailable"
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].agent_registered is False
        assert result.dispatch_proofs[0].decision == "blocked"

    def test_execute_revalidates_manifest_admission(self):
        orch = AgentOrchestrator(
            clock=_clock,
            agent_capabilities={
                "agent-a": ("deploy",),
                "agent-b": ("deploy",),
            },
            admitted_capabilities=("deploy",),
        )
        plan = orch.create_plan("agent-a", "goal")
        orch.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1",
            agent_id="agent-a",
            action="deploy",
            description="Deploy change",
            required_capabilities=("deploy",),
        ))
        orch.submit_for_voting(plan.plan_id)
        orch.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orch.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        orch.set_admitted_capabilities(())

        result = orch.execute_plan(plan.plan_id)

        assert result.phase == OrchestrationPhase.FAILED
        assert result.results[0]["success"] is False
        assert result.results[0]["error"] == "proposal requires unadmitted capabilities"
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].manifest_gated is True
        assert result.dispatch_proofs[0].manifest_admitted is False

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
        assert result.proof_id == "handoff:1"
        assert result.payload["doc_id"] == "123"
        proofs = orchestrator.handoff_proofs()
        assert proofs[0]["proof_id"] == result.proof_id
        assert proofs[0]["decision"] == "transferred"
        assert proofs[0]["target_capable"] is True

    def test_handoff_missing_capability(self, orchestrator):
        result = orchestrator.handoff("agent-a", "agent-b",
                                       required_capabilities=("deploy",))
        assert not result.success
        assert result.proof_id == "handoff:1"
        assert result.error == "target agent lacks required capabilities"
        assert "deploy" not in result.error
        proofs = orchestrator.handoff_proofs()
        assert proofs[0]["decision"] == "blocked"
        assert proofs[0]["target_capable"] is False
        assert proofs[0]["required_capability_count"] == 1

    def test_handoff_unknown_source(self, orchestrator):
        result = orchestrator.handoff("ghost", "agent-a")
        assert not result.success
        assert result.proof_id == "handoff:1"
        assert result.error == "source agent unavailable"
        assert "ghost" not in result.error
        proofs = orchestrator.handoff_proofs()
        assert proofs[0]["source_registered"] is False
        assert proofs[0]["target_registered"] is True
        assert proofs[0]["reason"] == "source agent unavailable"

    def test_handoff_unknown_target(self, orchestrator):
        result = orchestrator.handoff("agent-a", "ghost")
        assert not result.success
        assert result.proof_id == "handoff:1"
        assert result.error == "target agent unavailable"
        assert "ghost" not in result.error
        proofs = orchestrator.handoff_proofs()
        assert proofs[0]["source_registered"] is True
        assert proofs[0]["target_registered"] is False
        assert proofs[0]["reason"] == "target agent unavailable"

    def test_handoff_blocks_unmanifested_required_capability(self):
        orch = AgentOrchestrator(
            clock=_clock,
            agent_capabilities={
                "agent-a": ("search",),
                "agent-b": ("search", "deploy"),
            },
            admitted_capabilities=("search",),
        )

        result = orch.handoff("agent-a", "agent-b", required_capabilities=("deploy",))

        assert result.success is False
        assert result.proof_id == "handoff:1"
        assert result.error == "required capabilities are not manifest admitted"
        assert "deploy" not in result.error
        proofs = orch.handoff_proofs()
        assert proofs[0]["manifest_gated"] is True
        assert proofs[0]["manifest_admitted"] is False
        assert proofs[0]["reason"] == "required capabilities are not manifest admitted"

    def test_handoff_summary_counts_attempts_and_successes(self, orchestrator):
        orchestrator.handoff("agent-a", "agent-c", required_capabilities=("search",))
        orchestrator.handoff("agent-a", "agent-b", required_capabilities=("deploy",))

        summary = orchestrator.summary()

        assert summary["total_handoffs"] == 2
        assert summary["successful_handoffs"] == 1
        assert summary["handoff_proofs"] == 2

    def test_handoff_proofs_limit_is_bounded(self, orchestrator):
        orchestrator.handoff("agent-a", "agent-c", required_capabilities=("search",))
        orchestrator.handoff("agent-a", "agent-b", required_capabilities=("deploy",))

        assert orchestrator.handoff_proofs(limit=0) == []
        assert [proof["proof_id"] for proof in orchestrator.handoff_proofs(limit=1)] == ["handoff:2"]

    def test_find_capable_agents(self, orchestrator):
        agents = orchestrator.find_capable_agents(("code", "deploy"))
        assert agents == ["agent-c"]

    def test_find_capable_agents_llm(self, orchestrator):
        agents = orchestrator.find_capable_agents(("llm",))
        assert set(agents) == {"agent-a", "agent-b"}

    def test_find_capable_agents_excludes_unmanifested_capabilities(self):
        orch = AgentOrchestrator(
            clock=_clock,
            agent_capabilities={
                "agent-a": ("search",),
                "agent-b": ("deploy",),
            },
            admitted_capabilities=("search",),
        )

        assert orch.find_capable_agents(("search",)) == ["agent-a"]
        assert orch.find_capable_agents(("deploy",)) == []

    def test_manifest_read_model_builds_gated_orchestrator(self):
        orch = AgentOrchestrator.from_manifest_read_model(
            clock=_clock,
            agent_capabilities={"agent-a": ("search", "deploy")},
            manifest_read_model={
                "capability_ids": ("search",),
                "manifest_count": 1,
            },
        )

        summary = orch.summary()
        assert orch.manifest_gated is True
        assert summary["manifest_gated"] is True
        assert summary["admitted_capability_count"] == 1
        assert orch.find_capable_agents(("deploy",)) == []


class TestSummary:
    def test_summary(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="search", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        orchestrator.execute_plan(plan.plan_id)
        s = orchestrator.summary()
        assert s["registered_agents"] == 3
        assert s["total_plans"] == 1
        assert s["active_plans"] == 0
        assert s["plans_by_phase"] == {"completed": 1}
        assert s["dispatch_proofs"] == 1
        assert s["dispatch_decisions"] == {"executed": 1}
        assert s["handoff_decisions"] == {}
        assert s["proposal_proofs"] == 1
        assert s["proposal_decisions"] == {"accepted": 1}
        assert s["vote_proofs"] == 2
        assert s["vote_decisions"] == {"accepted": 2}

    def test_plan_to_dict(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        d = plan.to_dict()
        assert d["plan_id"] == plan.plan_id
        assert d["phase"] == "planning"
        assert d["approval_count"] == 0
        assert d["proposal_proofs"] == []
        assert d["vote_proofs"] == []
        assert d["dispatch_proofs"] == []

    def test_plan_to_dict_includes_dispatch_proofs(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="search", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)

        result = orchestrator.execute_plan(plan.plan_id)
        data = result.to_dict()

        assert len(data["dispatch_proofs"]) == 1
        assert data["dispatch_proofs"][0]["proof_id"] == result.results[0]["proof_id"]
        assert data["dispatch_proofs"][0]["decision"] == "executed"
        assert data["dispatch_proofs"][0]["required_capability_count"] == 0

    def test_read_model_bounds_recent_proofs_and_aggregates_decisions(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="search", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        orchestrator.execute_plan(plan.plan_id)
        orchestrator.handoff("agent-a", "agent-c", required_capabilities=("search",))
        orchestrator.handoff("agent-a", "agent-b", required_capabilities=("deploy",))

        model = orchestrator.read_model(proof_limit=1)

        assert model["summary"]["plans_by_phase"] == {"completed": 1}
        assert model["summary"]["proposal_decisions"] == {"accepted": 1}
        assert model["summary"]["vote_decisions"] == {"accepted": 2}
        assert model["summary"]["dispatch_decisions"] == {"executed": 1}
        assert model["summary"]["handoff_decisions"] == {
            "transferred": 1,
            "blocked": 1,
        }
        assert len(model["recent_proposal_proofs"]) == 1
        assert len(model["recent_vote_proofs"]) == 1
        assert len(model["recent_dispatch_proofs"]) == 1
        assert len(model["recent_handoff_proofs"]) == 1
        assert model["recent_proposal_proofs"][0]["decision"] == "accepted"
        assert model["recent_vote_proofs"][0]["agent_id"] == "agent-b"
        assert model["recent_handoff_proofs"][0]["decision"] == "blocked"
