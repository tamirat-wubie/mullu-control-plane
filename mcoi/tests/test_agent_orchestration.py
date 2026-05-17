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
        proofs = orchestrator.registration_proofs()
        assert len(proofs) == 3
        assert [proof["decision"] for proof in proofs] == [
            "registered",
            "registered",
            "registered",
        ]
        assert proofs[0]["agent_id"] == "agent-a"
        assert proofs[0]["current_capability_count"] == 2
        assert proofs[0]["previous_registered"] is False
        assert proofs[0]["current_registered"] is True
        assert proofs[0]["registered_agent_count"] == 1
        assert proofs[0]["total_plan_count"] == 0
        assert proofs[0]["active_plan_count"] == 0
        assert proofs[0]["active_proposal_count"] == 0

    def test_register_existing_agent_records_update(self, orchestrator):
        orchestrator.register_agent("agent-a", ("deploy",))

        proofs = orchestrator.registration_proofs()

        assert orchestrator.agent_count == 3
        assert len(proofs) == 4
        assert proofs[-1]["agent_id"] == "agent-a"
        assert proofs[-1]["action"] == "register"
        assert proofs[-1]["decision"] == "updated"
        assert proofs[-1]["reason"] == "agent capabilities updated"
        assert proofs[-1]["previous_registered"] is True
        assert proofs[-1]["current_registered"] is True
        assert proofs[-1]["previous_capability_count"] == 2
        assert proofs[-1]["current_capability_count"] == 1
        assert proofs[-1]["registered_agent_count"] == 3
        assert proofs[-1]["total_plan_count"] == 0
        assert proofs[-1]["active_plan_count"] == 0
        assert proofs[-1]["active_proposal_count"] == 0

    def test_register_existing_agent_records_active_plan_impact(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1",
            agent_id="agent-a",
            action="search",
            description="Search docs",
            required_capabilities=("search",),
        ))

        orchestrator.register_agent("agent-a", ("search", "deploy"))
        proof = orchestrator.registration_proofs()[-1]

        assert proof["decision"] == "updated"
        assert proof["registered_agent_count"] == 3
        assert proof["total_plan_count"] == 1
        assert proof["active_plan_count"] == 1
        assert proof["active_proposal_count"] == 1
        assert "search" not in repr(proof)
        assert "deploy" not in repr(proof)

    def test_unregister(self, orchestrator):
        orchestrator.unregister_agent("agent-c")
        proofs = orchestrator.registration_proofs()
        assert orchestrator.agent_count == 2
        assert len(proofs) == 4
        assert proofs[-1]["agent_id"] == "agent-c"
        assert proofs[-1]["action"] == "unregister"
        assert proofs[-1]["decision"] == "unregistered"
        assert proofs[-1]["reason"] == "agent unregistered"
        assert proofs[-1]["previous_registered"] is True
        assert proofs[-1]["current_registered"] is False
        assert proofs[-1]["previous_capability_count"] == 3
        assert proofs[-1]["current_capability_count"] == 0
        assert proofs[-1]["registered_agent_count"] == 2
        assert proofs[-1]["total_plan_count"] == 0
        assert proofs[-1]["active_plan_count"] == 0
        assert proofs[-1]["active_proposal_count"] == 0

    def test_unregister_nonexistent(self, orchestrator):
        orchestrator.unregister_agent("ghost")  # no error
        proofs = orchestrator.registration_proofs()
        assert orchestrator.agent_count == 3
        assert len(proofs) == 4
        assert proofs[-1]["agent_id"] == "ghost"
        assert proofs[-1]["action"] == "unregister"
        assert proofs[-1]["decision"] == "ignored"
        assert proofs[-1]["reason"] == "agent unavailable"
        assert proofs[-1]["previous_registered"] is False
        assert proofs[-1]["current_registered"] is False
        assert proofs[-1]["registered_agent_count"] == 3
        assert proofs[-1]["active_plan_count"] == 0
        assert proofs[-1]["active_proposal_count"] == 0

    def test_registration_proofs_limit_is_bounded(self, orchestrator):
        assert orchestrator.registration_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.registration_proofs(limit=1)
        ] == ["registry:3"]


class TestPlanLifecycle:
    def test_create_plan(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "Summarize document")
        proofs = orchestrator.plan_creation_proofs()

        assert plan.plan_id
        assert plan.phase == OrchestrationPhase.PLANNING
        assert plan.initiator_id == "agent-a"
        assert len(proofs) == 1
        assert proofs[0]["plan_id"] == plan.plan_id
        assert proofs[0]["initiator_id"] == "agent-a"
        assert proofs[0]["decision"] == "created"
        assert proofs[0]["reason"] == "plan created"
        assert proofs[0]["plan_phase"] == "planning"
        assert proofs[0]["initiator_registered"] is True
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["total_plan_count_before"] == 0
        assert proofs[0]["total_plan_count_after"] == 1
        assert proofs[0]["active_plan_count_before"] == 0
        assert proofs[0]["active_plan_count_after"] == 1
        assert proofs[0]["active_proposal_count_before"] == 0
        assert proofs[0]["active_proposal_count_after"] == 0
        assert "goal" not in proofs[0]

    def test_create_plan_unknown_agent(self, orchestrator):
        with pytest.raises(ValueError, match="^initiator agent unavailable$") as exc_info:
            orchestrator.create_plan("ghost", "goal")
        proofs = orchestrator.plan_creation_proofs()

        assert "ghost" not in str(exc_info.value)
        assert len(proofs) == 1
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["initiator_id"] == "ghost"
        assert proofs[0]["decision"] == "rejected"
        assert proofs[0]["reason"] == "initiator agent unavailable"
        assert proofs[0]["plan_phase"] == ""
        assert proofs[0]["initiator_registered"] is False
        assert proofs[0]["total_plan_count_before"] == 0
        assert proofs[0]["total_plan_count_after"] == 0
        assert proofs[0]["active_plan_count_before"] == 0
        assert proofs[0]["active_plan_count_after"] == 0
        assert proofs[0]["active_proposal_count_before"] == 0
        assert proofs[0]["active_proposal_count_after"] == 0
        assert "goal" not in proofs[0]

    def test_create_plan_records_existing_active_surface(self, orchestrator):
        first = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(first.plan_id, AgentProposal(
            proposal_id="p1",
            agent_id="agent-a",
            action="search",
            description="Search docs",
            required_capabilities=("search",),
        ))

        second = orchestrator.create_plan("agent-b", "goal")
        proof = orchestrator.plan_creation_proofs()[-1]

        assert second.plan_id
        assert proof["decision"] == "created"
        assert proof["total_plan_count_before"] == 1
        assert proof["total_plan_count_after"] == 2
        assert proof["active_plan_count_before"] == 1
        assert proof["active_plan_count_after"] == 2
        assert proof["active_proposal_count_before"] == 1
        assert proof["active_proposal_count_after"] == 1

    def test_plan_creation_proofs_limit_is_bounded(self, orchestrator):
        orchestrator.create_plan("agent-a", "goal")
        orchestrator.create_plan("agent-b", "goal")

        assert orchestrator.plan_creation_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.plan_creation_proofs(limit=1)
        ] == ["plan-create:2"]

    def test_get_plan_records_lookup_proofs(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")

        assert orchestrator.get_plan(plan.plan_id) is plan
        assert orchestrator.get_plan("missing-plan") is None
        proofs = orchestrator.plan_lookup_proofs()

        assert [proof["decision"] for proof in proofs] == ["found", "unavailable"]
        assert proofs[0]["action"] == "get_plan"
        assert proofs[0]["plan_id"] == plan.plan_id
        assert proofs[0]["plan_available"] is True
        assert proofs[0]["plan_phase"] == "planning"
        assert proofs[0]["active_plan_count"] == 1
        assert proofs[1]["action"] == "get_plan"
        assert proofs[1]["plan_id"] == ""
        assert proofs[1]["plan_available"] is False
        assert proofs[1]["reason"] == "plan unavailable"
        assert "missing-plan" not in repr(proofs[1])

    def test_plan_lookup_proofs_limit_is_bounded(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.get_plan(plan.plan_id)
        orchestrator.get_plan("missing-plan")

        assert orchestrator.plan_lookup_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.plan_lookup_proofs(limit=1)
        ] == ["plan-lookup:2"]

    def test_add_proposal(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        orchestrator.add_proposal(plan.plan_id, proposal)
        assert len(plan.proposals) == 1
        assert len(plan.proposal_proofs) == 1
        proof = plan.proposal_proofs[0]
        assert proof.decision == "accepted"
        assert proof.reason == "proposal admitted"
        assert proof.proposal_count_before == 0
        assert proof.proposal_count_after == 1
        assert proof.active_proposal_count_before == 0
        assert proof.active_proposal_count_after == 1

    def test_add_proposal_wrong_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        proposal = AgentProposal(proposal_id="p1", agent_id="agent-a",
                                 action="search", description="d")
        orchestrator.add_proposal(plan.plan_id, proposal)
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^plan not accepting proposals$") as exc_info:
            orchestrator.add_proposal(plan.plan_id, proposal)
        assert OrchestrationPhase.VOTING.value not in str(exc_info.value)
        proof = plan.proposal_proofs[-1]
        assert proof.decision == "rejected"
        assert proof.reason == "plan not accepting proposals"
        assert proof.proposal_count_before == 1
        assert proof.proposal_count_after == 1
        assert proof.active_proposal_count_before == 1
        assert proof.active_proposal_count_after == 1

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
        proof = plan.proposal_proofs[-1]
        assert proof.decision == "rejected"
        assert proof.reason == "proposal already recorded"
        assert proof.proposal_count_before == 1
        assert proof.proposal_count_after == 1
        assert proof.active_proposal_count_before == 1
        assert proof.active_proposal_count_after == 1

    def test_add_proposal_plan_unavailable(self, orchestrator):
        proposal = AgentProposal(
            proposal_id="p1", agent_id="agent-a",
            action="search", description="Search docs",
        )
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.add_proposal("missing-plan", proposal)
        proofs = orchestrator.plan_lookup_proofs()

        assert "missing-plan" not in str(exc_info.value)
        assert len(proofs) == 1
        assert proofs[0]["action"] == "add_proposal"
        assert proofs[0]["decision"] == "unavailable"
        assert proofs[0]["reason"] == "plan unavailable"
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["plan_available"] is False
        assert "missing-plan" not in repr(proofs[0])

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
        proof = plan.proposal_proofs[0]
        assert proof.decision == "rejected"
        assert proof.agent_registered is False
        assert proof.proposal_count_before == 0
        assert proof.proposal_count_after == 0
        assert proof.active_proposal_count_before == 0
        assert proof.active_proposal_count_after == 0

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
        proof = plan.proposal_proofs[0]
        assert proof.decision == "rejected"
        assert proof.agent_capable is False
        assert proof.proposal_count_before == 0
        assert proof.proposal_count_after == 0
        assert proof.active_proposal_count_before == 0
        assert proof.active_proposal_count_after == 0

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
        proof = plan.proposal_proofs[0]
        assert proof.decision == "rejected"
        assert proof.manifest_admitted is False
        assert proof.proposal_count_before == 0
        assert proof.proposal_count_after == 0
        assert proof.active_proposal_count_before == 0
        assert proof.active_proposal_count_after == 0

    def test_submit_empty_plan_fails(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="empty plan"):
            orchestrator.submit_for_voting(plan.plan_id)
        assert len(plan.submission_proofs) == 1
        assert plan.submission_proofs[0].decision == "rejected"
        assert plan.submission_proofs[0].reason == "empty plan"
        assert plan.submission_proofs[0].proposal_count == 0
        assert plan.submission_proofs[0].quorum_possible is False
        assert plan.submission_proofs[0].phase_changed is False
        assert plan.submission_proofs[0].active_plan_count_before == 1
        assert plan.submission_proofs[0].active_plan_count_after == 1
        assert plan.submission_proofs[0].active_proposal_count_before == 0
        assert plan.submission_proofs[0].active_proposal_count_after == 0
        assert plan.submission_proofs[0].from_phase_plan_count_before == 1
        assert plan.submission_proofs[0].from_phase_plan_count_after == 1
        assert plan.submission_proofs[0].to_phase_plan_count_before == 1
        assert plan.submission_proofs[0].to_phase_plan_count_after == 1

    def test_submit_for_voting_plan_unavailable_records_lookup(self, orchestrator):
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.submit_for_voting("missing-plan")
        proofs = orchestrator.plan_lookup_proofs()

        assert "missing-plan" not in str(exc_info.value)
        assert len(proofs) == 1
        assert proofs[0]["action"] == "submit_for_voting"
        assert proofs[0]["decision"] == "unavailable"
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["plan_available"] is False


class TestCapabilityPolicy:
    def test_constructor_records_initial_manifest_binding(self):
        orch = AgentOrchestrator(
            clock=_clock,
            agent_capabilities={"agent-a": ("search",)},
            admitted_capabilities=("search", "deploy"),
        )
        proofs = orch.manifest_binding_proofs()

        assert len(proofs) == 1
        assert proofs[0]["proof_id"] == "manifest-binding:1"
        assert proofs[0]["action"] == "initialize"
        assert proofs[0]["decision"] == "gated"
        assert proofs[0]["reason"] == "manifest binding gated"
        assert proofs[0]["manifest_read_model_available"] is False
        assert proofs[0]["raw_capability_count"] == 2
        assert proofs[0]["admitted_capability_count"] == 2
        assert proofs[0]["manifest_gated"] is True
        assert proofs[0]["registered_agent_count"] == 1
        assert "search" not in repr(proofs[0])
        assert "deploy" not in repr(proofs[0])

    def test_set_admitted_capabilities_records_policy_transitions(self, orchestrator):
        orchestrator.set_admitted_capabilities(("search",))
        orchestrator.set_admitted_capabilities(("search", "deploy"))
        orchestrator.set_admitted_capabilities(("deploy", "search"))
        orchestrator.set_admitted_capabilities(None)

        proofs = orchestrator.capability_policy_proofs()

        assert [proof["decision"] for proof in proofs] == [
            "gated",
            "updated",
            "unchanged",
            "ungated",
        ]
        assert proofs[0]["previous_manifest_gated"] is False
        assert proofs[0]["current_manifest_gated"] is True
        assert proofs[0]["previous_admitted_capability_count"] == 0
        assert proofs[0]["current_admitted_capability_count"] == 1
        assert proofs[0]["added_capability_count"] == 1
        assert proofs[0]["removed_capability_count"] == 0
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["total_plan_count"] == 0
        assert proofs[0]["active_plan_count"] == 0
        assert proofs[0]["active_proposal_count"] == 0
        assert proofs[1]["previous_admitted_capability_count"] == 1
        assert proofs[1]["current_admitted_capability_count"] == 2
        assert proofs[1]["added_capability_count"] == 1
        assert proofs[1]["removed_capability_count"] == 0
        assert proofs[2]["reason"] == "capability policy unchanged"
        assert proofs[2]["added_capability_count"] == 0
        assert proofs[2]["removed_capability_count"] == 0
        assert proofs[3]["previous_manifest_gated"] is True
        assert proofs[3]["current_manifest_gated"] is False
        assert proofs[3]["current_admitted_capability_count"] == 0
        assert proofs[3]["removed_capability_count"] == 2

    def test_capability_policy_proof_records_active_plan_impact(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1",
            agent_id="agent-a",
            action="search",
            description="Search docs",
            required_capabilities=("search",),
        ))

        orchestrator.set_admitted_capabilities(("search",))
        proof = orchestrator.capability_policy_proofs()[0]

        assert proof["decision"] == "gated"
        assert proof["registered_agent_count"] == 3
        assert proof["total_plan_count"] == 1
        assert proof["active_plan_count"] == 1
        assert proof["active_proposal_count"] == 1
        assert "search" not in repr(proof)

    def test_capability_policy_proofs_limit_is_bounded(self, orchestrator):
        orchestrator.set_admitted_capabilities(("search",))
        orchestrator.set_admitted_capabilities(None)

        assert orchestrator.capability_policy_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.capability_policy_proofs(limit=1)
        ] == ["capability-policy:2"]

    def test_manifest_binding_proofs_limit_is_bounded(self, orchestrator):
        assert orchestrator.manifest_binding_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.manifest_binding_proofs(limit=1)
        ] == ["manifest-binding:1"]


class TestVotingAndConsensus:
    def test_voting_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        assert plan.phase == OrchestrationPhase.VOTING
        assert len(plan.submission_proofs) == 1
        assert plan.submission_proofs[0].decision == "accepted"
        assert plan.submission_proofs[0].reason == "submitted for voting"
        assert plan.submission_proofs[0].from_phase == "planning"
        assert plan.submission_proofs[0].to_phase == "voting"
        assert plan.submission_proofs[0].proposal_count == 1
        assert plan.submission_proofs[0].voter_count == 3
        assert plan.submission_proofs[0].quorum_possible is True
        assert plan.submission_proofs[0].phase_changed is True
        assert plan.submission_proofs[0].active_plan_count_before == 1
        assert plan.submission_proofs[0].active_plan_count_after == 1
        assert plan.submission_proofs[0].active_proposal_count_before == 1
        assert plan.submission_proofs[0].active_proposal_count_after == 1
        assert plan.submission_proofs[0].from_phase_plan_count_before == 1
        assert plan.submission_proofs[0].from_phase_plan_count_after == 0
        assert plan.submission_proofs[0].to_phase_plan_count_before == 0
        assert plan.submission_proofs[0].to_phase_plan_count_after == 1

    def test_submit_for_voting_wrong_phase_records_proof(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)

        with pytest.raises(ValueError, match="^plan not accepting submission$") as exc_info:
            orchestrator.submit_for_voting(plan.plan_id)

        assert OrchestrationPhase.VOTING.value not in str(exc_info.value)
        assert len(plan.submission_proofs) == 2
        assert plan.submission_proofs[-1].decision == "rejected"
        assert plan.submission_proofs[-1].reason == "plan not accepting submission"
        assert plan.submission_proofs[-1].from_phase == "voting"
        assert plan.submission_proofs[-1].to_phase == "voting"
        assert plan.submission_proofs[-1].phase_changed is False
        assert plan.submission_proofs[-1].active_plan_count_before == 1
        assert plan.submission_proofs[-1].active_plan_count_after == 1
        assert plan.submission_proofs[-1].active_proposal_count_before == 1
        assert plan.submission_proofs[-1].active_proposal_count_after == 1
        assert plan.submission_proofs[-1].from_phase_plan_count_before == 1
        assert plan.submission_proofs[-1].from_phase_plan_count_after == 1
        assert plan.submission_proofs[-1].to_phase_plan_count_before == 1
        assert plan.submission_proofs[-1].to_phase_plan_count_after == 1

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
        assert plan.vote_proofs[0].vote_count_before == 0
        assert plan.vote_proofs[0].vote_count_after == 1
        assert plan.vote_proofs[0].approval_count_before == 0
        assert plan.vote_proofs[0].approval_count_after == 1
        assert plan.vote_proofs[0].rejection_count_before == 0
        assert plan.vote_proofs[0].rejection_count_after == 0
        assert plan.vote_proofs[1].vote_count_before == 1
        assert plan.vote_proofs[1].vote_count_after == 2
        assert plan.vote_proofs[1].approval_count_before == 1
        assert plan.vote_proofs[1].approval_count_after == 2
        assert plan.vote_proofs[1].rejection_count_before == 0
        assert plan.vote_proofs[1].rejection_count_after == 0

    def test_quorum_reached(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.APPROVE)
        assert orchestrator.check_consensus(plan.plan_id)
        proofs = orchestrator.consensus_proofs()
        assert len(proofs) == 1
        assert proofs[0]["plan_id"] == plan.plan_id
        assert proofs[0]["decision"] == "met"
        assert proofs[0]["reason"] == "consensus quorum met"
        assert proofs[0]["plan_phase"] == "voting"
        assert proofs[0]["plan_available"] is True
        assert proofs[0]["vote_count"] == 2
        assert proofs[0]["approval_count"] == 2
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["quorum_threshold"] == 2
        assert proofs[0]["total_plan_count"] == 1
        assert proofs[0]["active_plan_count"] == 1
        assert proofs[0]["active_proposal_count"] == 1
        assert proofs[0]["consensus_proof_count_before"] == 0
        assert proofs[0]["consensus_proof_count_after"] == 1
        assert proofs[0]["quorum_met"] is True

    def test_quorum_not_reached(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        orchestrator.cast_vote(plan.plan_id, "agent-b", Vote.REJECT)
        orchestrator.cast_vote(plan.plan_id, "agent-c", Vote.REJECT)
        vote_proof = plan.vote_proofs[-1]
        assert not orchestrator.check_consensus(plan.plan_id)
        proofs = orchestrator.consensus_proofs()
        assert vote_proof.vote_count_before == 2
        assert vote_proof.vote_count_after == 3
        assert vote_proof.approval_count_before == 1
        assert vote_proof.approval_count_after == 1
        assert vote_proof.rejection_count_before == 1
        assert vote_proof.rejection_count_after == 2
        assert len(proofs) == 1
        assert proofs[0]["plan_id"] == plan.plan_id
        assert proofs[0]["decision"] == "not_met"
        assert proofs[0]["reason"] == "consensus quorum not met"
        assert proofs[0]["vote_count"] == 3
        assert proofs[0]["approval_count"] == 1
        assert proofs[0]["rejection_count"] == 2
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["quorum_threshold"] == 2
        assert proofs[0]["total_plan_count"] == 1
        assert proofs[0]["active_plan_count"] == 1
        assert proofs[0]["active_proposal_count"] == 1
        assert proofs[0]["consensus_proof_count_before"] == 0
        assert proofs[0]["consensus_proof_count_after"] == 1
        assert proofs[0]["quorum_met"] is False

    def test_check_consensus_unavailable_plan_records_proof(self, orchestrator):
        assert not orchestrator.check_consensus("missing-plan")
        proofs = orchestrator.consensus_proofs()
        assert len(proofs) == 1
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["decision"] == "unavailable"
        assert proofs[0]["reason"] == "plan unavailable"
        assert proofs[0]["plan_phase"] == ""
        assert proofs[0]["plan_available"] is False
        assert proofs[0]["vote_count"] == 0
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["quorum_threshold"] == 2
        assert proofs[0]["total_plan_count"] == 0
        assert proofs[0]["active_plan_count"] == 0
        assert proofs[0]["active_proposal_count"] == 0
        assert proofs[0]["consensus_proof_count_before"] == 0
        assert proofs[0]["consensus_proof_count_after"] == 1
        assert proofs[0]["quorum_met"] is False

    def test_consensus_proofs_limit_is_bounded(self, orchestrator):
        first = orchestrator.create_plan("agent-a", "goal")
        second = orchestrator.create_plan("agent-b", "goal")
        orchestrator.check_consensus(first.plan_id)
        orchestrator.check_consensus(second.plan_id)

        assert orchestrator.consensus_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.consensus_proofs(limit=1)
        ] == ["consensus:2"]

    def test_vote_wrong_phase(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="^plan not accepting votes$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "agent-a", Vote.APPROVE)
        assert OrchestrationPhase.PLANNING.value not in str(exc_info.value)
        proof = plan.vote_proofs[0]
        assert proof.decision == "rejected"
        assert proof.reason == "plan not accepting votes"
        assert proof.vote_count_before == 0
        assert proof.vote_count_after == 0
        assert proof.approval_count_before == 0
        assert proof.approval_count_after == 0
        assert proof.rejection_count_before == 0
        assert proof.rejection_count_after == 0

    def test_vote_unknown_agent(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        orchestrator.add_proposal(plan.plan_id, AgentProposal(
            proposal_id="p1", agent_id="agent-a", action="a", description="d",
        ))
        orchestrator.submit_for_voting(plan.plan_id)
        with pytest.raises(ValueError, match="^voting agent unavailable$") as exc_info:
            orchestrator.cast_vote(plan.plan_id, "ghost", Vote.APPROVE)
        assert "ghost" not in str(exc_info.value)
        proof = plan.vote_proofs[0]
        assert proof.decision == "rejected"
        assert proof.voter_registered is False
        assert proof.vote_count_before == 0
        assert proof.vote_count_after == 0
        assert proof.approval_count_before == 0
        assert proof.approval_count_after == 0
        assert proof.rejection_count_before == 0
        assert proof.rejection_count_after == 0

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
        proof = plan.vote_proofs[-1]
        assert proof.decision == "rejected"
        assert proof.reason == "vote already recorded"
        assert proof.vote_count_before == 1
        assert proof.vote_count_after == 1
        assert proof.approval_count_before == 1
        assert proof.approval_count_after == 1
        assert proof.rejection_count_before == 0
        assert proof.rejection_count_after == 0

    def test_vote_plan_unavailable(self, orchestrator):
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.cast_vote("missing-plan", "agent-a", Vote.APPROVE)
        proofs = orchestrator.plan_lookup_proofs()

        assert "missing-plan" not in str(exc_info.value)
        assert len(proofs) == 1
        assert proofs[0]["action"] == "cast_vote"
        assert proofs[0]["decision"] == "unavailable"
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["plan_available"] is False


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
        assert result.dispatch_proofs[0].suppressed_executor_key_count == 1
        assert result.dispatch_proofs[0].dispatch_count_before == 0
        assert result.dispatch_proofs[0].dispatch_count_after == 1
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_before == 0
        assert result.dispatch_proofs[0].successful_result_count_after == 1
        assert result.dispatch_proofs[0].failed_result_count_before == 0
        assert result.dispatch_proofs[0].failed_result_count_after == 0
        assert len(result.execution_proofs) == 1
        assert result.execution_proofs[0].decision == "accepted"
        assert result.execution_proofs[0].reason == "execution admitted"
        assert result.execution_proofs[0].from_phase == "voting"
        assert result.execution_proofs[0].to_phase == "executing"
        assert result.execution_proofs[0].proposal_count == 1
        assert result.execution_proofs[0].vote_count == 2
        assert result.execution_proofs[0].approval_count == 2
        assert result.execution_proofs[0].quorum_met is True
        assert result.execution_proofs[0].phase_changed is True
        assert result.execution_proofs[0].active_plan_count_before == 1
        assert result.execution_proofs[0].active_plan_count_after == 1
        assert result.execution_proofs[0].active_proposal_count_before == 1
        assert result.execution_proofs[0].active_proposal_count_after == 1
        assert result.execution_proofs[0].from_phase_plan_count_before == 1
        assert result.execution_proofs[0].from_phase_plan_count_after == 0
        assert result.execution_proofs[0].to_phase_plan_count_before == 0
        assert result.execution_proofs[0].to_phase_plan_count_after == 1
        assert len(result.finalization_proofs) == 1
        assert result.finalization_proofs[0].decision == "completed"
        assert result.finalization_proofs[0].reason == "all dispatches succeeded"
        assert result.finalization_proofs[0].from_phase == "executing"
        assert result.finalization_proofs[0].to_phase == "completed"
        assert result.finalization_proofs[0].proposal_count == 1
        assert result.finalization_proofs[0].result_count == 1
        assert result.finalization_proofs[0].successful_result_count == 1
        assert result.finalization_proofs[0].failed_result_count == 0
        assert result.finalization_proofs[0].dispatch_count == 1
        assert result.finalization_proofs[0].quorum_met is True
        assert result.finalization_proofs[0].phase_changed is True
        assert result.finalization_proofs[0].active_plan_count_before == 1
        assert result.finalization_proofs[0].active_plan_count_after == 0
        assert result.finalization_proofs[0].active_proposal_count_before == 1
        assert result.finalization_proofs[0].active_proposal_count_after == 0
        assert result.finalization_proofs[0].from_phase_plan_count_before == 1
        assert result.finalization_proofs[0].from_phase_plan_count_after == 0
        assert result.finalization_proofs[0].to_phase_plan_count_before == 0
        assert result.finalization_proofs[0].to_phase_plan_count_after == 1

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
        assert result.dispatch_proofs[0].dispatch_count_before == 0
        assert result.dispatch_proofs[0].dispatch_count_after == 1
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 0
        assert result.dispatch_proofs[0].successful_result_count_before == 0
        assert result.dispatch_proofs[0].successful_result_count_after == 0
        assert result.dispatch_proofs[0].failed_result_count_before == 0
        assert result.dispatch_proofs[0].failed_result_count_after == 0
        assert len(result.execution_proofs) == 1
        assert result.execution_proofs[0].decision == "blocked"
        assert result.execution_proofs[0].reason == "consensus quorum not met"
        assert result.execution_proofs[0].from_phase == "voting"
        assert result.execution_proofs[0].to_phase == "failed"
        assert result.execution_proofs[0].approval_count == 1
        assert result.execution_proofs[0].voter_count == 3
        assert result.execution_proofs[0].quorum_met is False
        assert result.execution_proofs[0].phase_changed is True
        assert result.execution_proofs[0].active_plan_count_before == 1
        assert result.execution_proofs[0].active_plan_count_after == 0
        assert result.execution_proofs[0].active_proposal_count_before == 1
        assert result.execution_proofs[0].active_proposal_count_after == 0
        assert result.execution_proofs[0].from_phase_plan_count_before == 1
        assert result.execution_proofs[0].from_phase_plan_count_after == 0
        assert result.execution_proofs[0].to_phase_plan_count_before == 0
        assert result.execution_proofs[0].to_phase_plan_count_after == 1
        assert len(result.finalization_proofs) == 1
        assert result.finalization_proofs[0].decision == "failed"
        assert result.finalization_proofs[0].reason == "consensus quorum not met"
        assert result.finalization_proofs[0].from_phase == "voting"
        assert result.finalization_proofs[0].to_phase == "failed"
        assert result.finalization_proofs[0].result_count == 0
        assert result.finalization_proofs[0].dispatch_count == 1
        assert result.finalization_proofs[0].quorum_met is False
        assert result.finalization_proofs[0].phase_changed is True
        assert result.finalization_proofs[0].active_plan_count_before == 1
        assert result.finalization_proofs[0].active_plan_count_after == 0
        assert result.finalization_proofs[0].active_proposal_count_before == 1
        assert result.finalization_proofs[0].active_proposal_count_after == 0
        assert result.finalization_proofs[0].from_phase_plan_count_before == 1
        assert result.finalization_proofs[0].from_phase_plan_count_after == 0
        assert result.finalization_proofs[0].to_phase_plan_count_before == 0
        assert result.finalization_proofs[0].to_phase_plan_count_after == 1

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
        assert result.dispatch_proofs[0].suppressed_executor_key_count == 0
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_after == 1
        assert result.dispatch_proofs[0].failed_result_count_after == 0

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
        assert result.dispatch_proofs[0].suppressed_executor_key_count == 6
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_after == 1
        assert result.dispatch_proofs[0].failed_result_count_after == 0

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
        assert result.dispatch_proofs[0].dispatch_count_before == 0
        assert result.dispatch_proofs[0].dispatch_count_after == 1
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_after == 0
        assert result.dispatch_proofs[0].failed_result_count_after == 1
        assert result.finalization_proofs[0].decision == "failed"
        assert result.finalization_proofs[0].reason == "one or more dispatches failed"
        assert result.finalization_proofs[0].failed_result_count == 1
        assert result.finalization_proofs[0].from_phase == "executing"
        assert result.finalization_proofs[0].to_phase == "failed"
        assert result.finalization_proofs[0].phase_changed is True
        assert result.finalization_proofs[0].active_plan_count_before == 1
        assert result.finalization_proofs[0].active_plan_count_after == 0
        assert result.finalization_proofs[0].active_proposal_count_before == 1
        assert result.finalization_proofs[0].active_proposal_count_after == 0
        assert result.finalization_proofs[0].from_phase_plan_count_before == 1
        assert result.finalization_proofs[0].from_phase_plan_count_after == 0
        assert result.finalization_proofs[0].to_phase_plan_count_before == 0
        assert result.finalization_proofs[0].to_phase_plan_count_after == 1

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
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_after == 0
        assert result.dispatch_proofs[0].failed_result_count_after == 1
        assert result.finalization_proofs[0].decision == "failed"
        assert result.finalization_proofs[0].failed_result_count == 1

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
        policy_proofs = orch.capability_policy_proofs()

        assert result.phase == OrchestrationPhase.FAILED
        assert result.results[0]["success"] is False
        assert result.results[0]["error"] == "proposal requires unadmitted capabilities"
        assert result.results[0]["proof_id"] == result.dispatch_proofs[0].proof_id
        assert result.dispatch_proofs[0].manifest_gated is True
        assert result.dispatch_proofs[0].manifest_admitted is False
        assert result.dispatch_proofs[0].result_count_before == 0
        assert result.dispatch_proofs[0].result_count_after == 1
        assert result.dispatch_proofs[0].successful_result_count_after == 0
        assert result.dispatch_proofs[0].failed_result_count_after == 1
        assert len(policy_proofs) == 1
        assert policy_proofs[0]["decision"] == "updated"
        assert policy_proofs[0]["previous_admitted_capability_count"] == 1
        assert policy_proofs[0]["current_admitted_capability_count"] == 0
        assert policy_proofs[0]["removed_capability_count"] == 1
        assert policy_proofs[0]["registered_agent_count"] == 2
        assert policy_proofs[0]["total_plan_count"] == 1
        assert policy_proofs[0]["active_plan_count"] == 1
        assert policy_proofs[0]["active_proposal_count"] == 1
        assert result.finalization_proofs[0].decision == "failed"
        assert result.finalization_proofs[0].failed_result_count == 1

    def test_execute_plan_wrong_phase_is_bounded(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        with pytest.raises(ValueError, match="^plan not ready for execution$") as exc_info:
            orchestrator.execute_plan(plan.plan_id)
        assert OrchestrationPhase.PLANNING.value not in str(exc_info.value)
        assert len(plan.execution_proofs) == 1
        assert plan.execution_proofs[0].decision == "rejected"
        assert plan.execution_proofs[0].reason == "plan not ready for execution"
        assert plan.execution_proofs[0].from_phase == "planning"
        assert plan.execution_proofs[0].to_phase == "planning"
        assert plan.execution_proofs[0].quorum_met is False
        assert plan.execution_proofs[0].phase_changed is False
        assert plan.execution_proofs[0].active_plan_count_before == 1
        assert plan.execution_proofs[0].active_plan_count_after == 1
        assert plan.execution_proofs[0].active_proposal_count_before == 0
        assert plan.execution_proofs[0].active_proposal_count_after == 0
        assert plan.execution_proofs[0].from_phase_plan_count_before == 1
        assert plan.execution_proofs[0].from_phase_plan_count_after == 1
        assert plan.execution_proofs[0].to_phase_plan_count_before == 1
        assert plan.execution_proofs[0].to_phase_plan_count_after == 1

    def test_execute_plan_unavailable_is_bounded(self, orchestrator):
        with pytest.raises(ValueError, match="^plan unavailable$") as exc_info:
            orchestrator.execute_plan("missing-plan")
        proofs = orchestrator.plan_lookup_proofs()

        assert "missing-plan" not in str(exc_info.value)
        assert len(proofs) == 1
        assert proofs[0]["action"] == "execute_plan"
        assert proofs[0]["decision"] == "unavailable"
        assert proofs[0]["reason"] == "plan unavailable"
        assert proofs[0]["plan_id"] == ""
        assert proofs[0]["plan_available"] is False


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
        proofs = orchestrator.capability_discovery_proofs()

        assert agents == ["agent-c"]
        assert len(proofs) == 1
        assert proofs[0]["proof_id"] == "capability-discovery:1"
        assert proofs[0]["decision"] == "matched"
        assert proofs[0]["reason"] == "capable agents matched"
        assert proofs[0]["required_capability_count"] == 2
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["matched_agent_count"] == 1
        assert proofs[0]["manifest_gated"] is False
        assert proofs[0]["manifest_admitted"] is True
        assert "code" not in repr(proofs[0])
        assert "agent-c" not in repr(proofs[0])

    def test_find_capable_agents_llm(self, orchestrator):
        agents = orchestrator.find_capable_agents(("llm",))
        assert set(agents) == {"agent-a", "agent-b"}

    def test_find_capable_agents_records_empty_match(self, orchestrator):
        agents = orchestrator.find_capable_agents(("deploy", "llm"))
        proofs = orchestrator.capability_discovery_proofs()

        assert agents == []
        assert len(proofs) == 1
        assert proofs[0]["decision"] == "empty"
        assert proofs[0]["reason"] == "no capable agents matched"
        assert proofs[0]["required_capability_count"] == 2
        assert proofs[0]["registered_agent_count"] == 3
        assert proofs[0]["matched_agent_count"] == 0
        assert proofs[0]["manifest_admitted"] is True

    def test_capability_discovery_proofs_limit_is_bounded(self, orchestrator):
        orchestrator.find_capable_agents(("llm",))
        orchestrator.find_capable_agents(("deploy", "llm"))

        assert orchestrator.capability_discovery_proofs(limit=0) == []
        assert [
            proof["proof_id"]
            for proof in orchestrator.capability_discovery_proofs(limit=1)
        ] == ["capability-discovery:2"]

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
        proofs = orch.capability_discovery_proofs()
        assert [proof["decision"] for proof in proofs] == ["matched", "blocked"]
        assert proofs[-1]["reason"] == "required capabilities are not manifest admitted"
        assert proofs[-1]["manifest_gated"] is True
        assert proofs[-1]["manifest_admitted"] is False
        assert proofs[-1]["matched_agent_count"] == 0
        assert "deploy" not in repr(proofs[-1])

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
        binding_proofs = orch.manifest_binding_proofs()

        assert orch.manifest_gated is True
        assert summary["manifest_gated"] is True
        assert summary["admitted_capability_count"] == 1
        assert summary["manifest_binding_decisions"] == {"gated": 1}
        assert binding_proofs[0]["action"] == "from_manifest_read_model"
        assert binding_proofs[0]["decision"] == "gated"
        assert binding_proofs[0]["manifest_read_model_available"] is True
        assert binding_proofs[0]["raw_capability_count"] == 1
        assert binding_proofs[0]["admitted_capability_count"] == 1
        assert binding_proofs[0]["registered_agent_count"] == 1
        assert "search" not in repr(binding_proofs[0])
        assert orch.find_capable_agents(("deploy",)) == []
        proofs = orch.capability_discovery_proofs()
        assert proofs[0]["decision"] == "blocked"
        assert proofs[0]["manifest_admitted"] is False

    def test_manifest_read_model_none_records_ungated_binding(self):
        orch = AgentOrchestrator.from_manifest_read_model(
            clock=_clock,
            agent_capabilities={"agent-a": ("search",)},
            manifest_read_model=None,
        )
        proofs = orch.manifest_binding_proofs()

        assert orch.manifest_gated is False
        assert len(proofs) == 1
        assert proofs[0]["action"] == "from_manifest_read_model"
        assert proofs[0]["decision"] == "ungated"
        assert proofs[0]["reason"] == "manifest binding ungated"
        assert proofs[0]["manifest_read_model_available"] is False
        assert proofs[0]["raw_capability_count"] == 0
        assert proofs[0]["admitted_capability_count"] == 0
        assert proofs[0]["manifest_gated"] is False
        assert proofs[0]["registered_agent_count"] == 1


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
        assert s["registration_proofs"] == 3
        assert s["registration_decisions"] == {"registered": 3}
        assert s["plan_creation_proofs"] == 1
        assert s["plan_creation_decisions"] == {"created": 1}
        assert s["capability_policy_proofs"] == 0
        assert s["capability_policy_decisions"] == {}
        assert s["consensus_proofs"] == 0
        assert s["consensus_decisions"] == {}
        assert s["capability_discovery_proofs"] == 0
        assert s["capability_discovery_decisions"] == {}
        assert s["plan_lookup_proofs"] == 0
        assert s["plan_lookup_decisions"] == {}
        assert s["manifest_binding_proofs"] == 1
        assert s["manifest_binding_decisions"] == {"ungated": 1}
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
        assert s["submission_proofs"] == 1
        assert s["submission_decisions"] == {"accepted": 1}
        assert s["execution_proofs"] == 1
        assert s["execution_decisions"] == {"accepted": 1}
        assert s["finalization_proofs"] == 1
        assert s["finalization_decisions"] == {"completed": 1}

    def test_plan_to_dict(self, orchestrator):
        plan = orchestrator.create_plan("agent-a", "goal")
        d = plan.to_dict()
        assert d["plan_id"] == plan.plan_id
        assert d["phase"] == "planning"
        assert d["approval_count"] == 0
        assert d["proposal_proofs"] == []
        assert d["vote_proofs"] == []
        assert d["submission_proofs"] == []
        assert d["execution_proofs"] == []
        assert d["dispatch_proofs"] == []
        assert d["finalization_proofs"] == []

    def test_plan_to_dict_includes_dispatch_and_finalization_proofs(self, orchestrator):
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
        assert data["dispatch_proofs"][0]["suppressed_executor_key_count"] == 1
        assert data["dispatch_proofs"][0]["dispatch_count_after"] == 1
        assert data["dispatch_proofs"][0]["result_count_after"] == 1
        assert data["dispatch_proofs"][0]["successful_result_count_after"] == 1
        assert len(data["finalization_proofs"]) == 1
        assert data["finalization_proofs"][0]["decision"] == "completed"
        assert data["finalization_proofs"][0]["to_phase"] == "completed"
        assert data["finalization_proofs"][0]["phase_changed"] is True
        assert data["finalization_proofs"][0]["active_plan_count_after"] == 0

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
        assert model["summary"]["registration_decisions"] == {"registered": 3}
        assert model["summary"]["plan_creation_decisions"] == {"created": 1}
        assert model["summary"]["capability_policy_decisions"] == {}
        assert model["summary"]["consensus_decisions"] == {}
        assert model["summary"]["capability_discovery_decisions"] == {}
        assert model["summary"]["plan_lookup_decisions"] == {}
        assert model["summary"]["manifest_binding_decisions"] == {"ungated": 1}
        assert model["summary"]["proposal_decisions"] == {"accepted": 1}
        assert model["summary"]["vote_decisions"] == {"accepted": 2}
        assert model["summary"]["submission_decisions"] == {"accepted": 1}
        assert model["summary"]["execution_decisions"] == {"accepted": 1}
        assert model["summary"]["dispatch_decisions"] == {"executed": 1}
        assert model["summary"]["finalization_decisions"] == {"completed": 1}
        assert model["summary"]["handoff_decisions"] == {
            "transferred": 1,
            "blocked": 1,
        }
        assert len(model["recent_proposal_proofs"]) == 1
        assert len(model["recent_registration_proofs"]) == 1
        assert len(model["recent_plan_creation_proofs"]) == 1
        assert len(model["recent_capability_policy_proofs"]) == 0
        assert len(model["recent_consensus_proofs"]) == 0
        assert len(model["recent_capability_discovery_proofs"]) == 0
        assert len(model["recent_plan_lookup_proofs"]) == 0
        assert len(model["recent_manifest_binding_proofs"]) == 1
        assert len(model["recent_vote_proofs"]) == 1
        assert len(model["recent_submission_proofs"]) == 1
        assert len(model["recent_execution_proofs"]) == 1
        assert len(model["recent_dispatch_proofs"]) == 1
        assert len(model["recent_finalization_proofs"]) == 1
        assert len(model["recent_handoff_proofs"]) == 1
        assert model["recent_proposal_proofs"][0]["decision"] == "accepted"
        assert model["recent_proposal_proofs"][0]["proposal_count_after"] == 1
        assert model["recent_registration_proofs"][0]["agent_id"] == "agent-c"
        assert model["recent_plan_creation_proofs"][0]["plan_id"] == plan.plan_id
        assert model["recent_vote_proofs"][0]["agent_id"] == "agent-b"
        assert model["recent_vote_proofs"][0]["vote_count_after"] == 2
        assert model["recent_vote_proofs"][0]["approval_count_after"] == 2
        assert model["recent_submission_proofs"][0]["decision"] == "accepted"
        assert model["recent_submission_proofs"][0]["phase_changed"] is True
        assert model["recent_submission_proofs"][0]["from_phase_plan_count_after"] == 0
        assert model["recent_submission_proofs"][0]["to_phase_plan_count_after"] == 1
        assert model["recent_execution_proofs"][0]["decision"] == "accepted"
        assert model["recent_execution_proofs"][0]["phase_changed"] is True
        assert model["recent_execution_proofs"][0]["from_phase_plan_count_after"] == 0
        assert model["recent_execution_proofs"][0]["to_phase_plan_count_after"] == 1
        assert model["recent_finalization_proofs"][0]["decision"] == "completed"
        assert model["recent_finalization_proofs"][0]["phase_changed"] is True
        assert model["recent_finalization_proofs"][0]["active_plan_count_after"] == 0
        assert model["recent_finalization_proofs"][0]["active_proposal_count_after"] == 0
        assert model["recent_dispatch_proofs"][0]["dispatch_count_after"] == 1
        assert model["recent_dispatch_proofs"][0]["result_count_after"] == 1
        assert model["recent_dispatch_proofs"][0]["successful_result_count_after"] == 1
        assert model["recent_manifest_binding_proofs"][0]["decision"] == "ungated"
        assert model["recent_handoff_proofs"][0]["decision"] == "blocked"
