"""Phase 222C — Agent Orchestration Protocol.

Purpose: Coordinate multi-agent workflows with governed handoffs, capability
    negotiation, and consensus protocols. Agents can propose, vote, and
    execute plans through a governed orchestrator.
Dependencies: agent_protocol, agent_chain.
Invariants:
  - All orchestration decisions are auditable.
  - Agent handoffs require capability matching.
  - Consensus requires quorum (majority of registered agents).
  - Plans are immutable once approved.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


def _classify_orchestration_exception(exc: Exception) -> str:
    error_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"proposal timeout ({error_type})"
    if isinstance(exc, ConnectionError):
        return f"proposal network error ({error_type})"
    if isinstance(exc, PermissionError):
        return f"proposal access error ({error_type})"
    if isinstance(exc, ValueError):
        return f"proposal validation error ({error_type})"
    return f"proposal execution error ({error_type})"


@unique
class OrchestrationPhase(Enum):
    PLANNING = "planning"
    VOTING = "voting"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@unique
class Vote(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class AgentProposal:
    """A proposed action or plan step from an agent."""
    proposal_id: str
    agent_id: str
    action: str
    description: str
    required_capabilities: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0


@dataclass
class OrchestrationPlan:
    """A multi-agent execution plan requiring consensus."""
    plan_id: str
    initiator_id: str
    goal: str
    proposals: list[AgentProposal] = field(default_factory=list)
    votes: dict[str, Vote] = field(default_factory=dict)
    phase: OrchestrationPhase = OrchestrationPhase.PLANNING
    results: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""

    @property
    def approval_count(self) -> int:
        return sum(1 for v in self.votes.values() if v == Vote.APPROVE)

    @property
    def rejection_count(self) -> int:
        return sum(1 for v in self.votes.values() if v == Vote.REJECT)

    def has_quorum(self, total_agents: int) -> bool:
        return self.approval_count > total_agents / 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "initiator_id": self.initiator_id,
            "goal": self.goal,
            "phase": self.phase.value,
            "proposals": len(self.proposals),
            "votes": {k: v.value for k, v in self.votes.items()},
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "results": self.results,
            "created_at": self.created_at,
        }


@dataclass
class HandoffResult:
    """Result of an agent-to-agent handoff."""
    from_agent: str
    to_agent: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class AgentOrchestrator:
    """Governs multi-agent coordination, consensus, and handoffs."""

    def __init__(self, clock: Callable[[], str],
                 agent_capabilities: dict[str, tuple[str, ...]] | None = None):
        self._clock = clock
        self._capabilities: dict[str, tuple[str, ...]] = dict(agent_capabilities or {})
        self._plans: dict[str, OrchestrationPlan] = {}
        self._handoffs: list[HandoffResult] = []
        self._total_plans = 0
        self._total_handoffs = 0

    def register_agent(self, agent_id: str, capabilities: tuple[str, ...]) -> None:
        self._capabilities[agent_id] = capabilities

    def unregister_agent(self, agent_id: str) -> None:
        self._capabilities.pop(agent_id, None)

    @property
    def agent_count(self) -> int:
        return len(self._capabilities)

    def create_plan(self, initiator_id: str, goal: str) -> OrchestrationPlan:
        if initiator_id not in self._capabilities:
            raise ValueError("initiator agent unavailable")
        plan = OrchestrationPlan(
            plan_id=uuid.uuid4().hex[:12],
            initiator_id=initiator_id,
            goal=goal,
            created_at=self._clock(),
        )
        self._plans[plan.plan_id] = plan
        self._total_plans += 1
        return plan

    def add_proposal(self, plan_id: str, proposal: AgentProposal) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if plan.phase != OrchestrationPhase.PLANNING:
            raise ValueError("plan not accepting proposals")
        plan.proposals.append(proposal)

    def submit_for_voting(self, plan_id: str) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if not plan.proposals:
            raise ValueError("Cannot vote on empty plan")
        plan.phase = OrchestrationPhase.VOTING

    def cast_vote(self, plan_id: str, agent_id: str, vote: Vote) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if plan.phase != OrchestrationPhase.VOTING:
            raise ValueError("plan not accepting votes")
        if agent_id not in self._capabilities:
            raise ValueError("voting agent unavailable")
        plan.votes[agent_id] = vote

    def check_consensus(self, plan_id: str) -> bool:
        plan = self._plans.get(plan_id)
        if not plan:
            return False
        return plan.has_quorum(self.agent_count)

    def execute_plan(self, plan_id: str,
                     executor: Callable[[AgentProposal], dict[str, Any]] | None = None) -> OrchestrationPlan:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if plan.phase != OrchestrationPhase.VOTING:
            raise ValueError("plan not ready for execution")
        if not plan.has_quorum(self.agent_count):
            plan.phase = OrchestrationPhase.FAILED
            return plan

        plan.phase = OrchestrationPhase.EXECUTING
        for proposal in sorted(plan.proposals, key=lambda p: -p.priority):
            try:
                if executor:
                    result = executor(proposal)
                else:
                    result = {"status": "executed", "proposal_id": proposal.proposal_id}
                plan.results.append({"proposal_id": proposal.proposal_id, "success": True, **result})
            except Exception as e:
                plan.results.append({
                    "proposal_id": proposal.proposal_id,
                    "success": False,
                    "error": _classify_orchestration_exception(e),
                })

        all_ok = all(r.get("success") for r in plan.results)
        plan.phase = OrchestrationPhase.COMPLETED if all_ok else OrchestrationPhase.FAILED
        return plan

    def handoff(self, from_agent: str, to_agent: str,
                required_capabilities: tuple[str, ...] = (),
                payload: dict[str, Any] | None = None) -> HandoffResult:
        if from_agent not in self._capabilities:
            return HandoffResult(from_agent, to_agent, False, error="source agent unavailable")
        if to_agent not in self._capabilities:
            return HandoffResult(from_agent, to_agent, False, error="target agent unavailable")

        target_caps = set(self._capabilities[to_agent])
        missing = set(required_capabilities) - target_caps
        if missing:
            return HandoffResult(from_agent, to_agent, False,
                                 error="target agent lacks required capabilities")

        result = HandoffResult(from_agent, to_agent, True, payload=payload or {})
        self._handoffs.append(result)
        self._total_handoffs += 1
        return result

    def find_capable_agents(self, required: tuple[str, ...]) -> list[str]:
        required_set = set(required)
        return [aid for aid, caps in self._capabilities.items() if required_set <= set(caps)]

    def get_plan(self, plan_id: str) -> OrchestrationPlan | None:
        return self._plans.get(plan_id)

    def summary(self) -> dict[str, Any]:
        return {
            "registered_agents": self.agent_count,
            "total_plans": self._total_plans,
            "active_plans": sum(1 for p in self._plans.values()
                                if p.phase in (OrchestrationPhase.PLANNING,
                                               OrchestrationPhase.VOTING,
                                               OrchestrationPhase.EXECUTING)),
            "total_handoffs": self._total_handoffs,
        }
