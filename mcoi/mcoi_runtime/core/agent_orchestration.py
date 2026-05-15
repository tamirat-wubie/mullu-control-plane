"""Phase 222C — Agent Orchestration Protocol.

Purpose: Coordinate multi-agent workflows with governed handoffs, capability
    negotiation, and consensus protocols. Agents can propose, vote, and
    execute plans through a governed orchestrator.
Dependencies: agent_protocol, agent_chain.
Invariants:
  - All orchestration decisions are auditable.
  - Agent handoffs require capability matching.
  - Handoff attempts carry bounded proof records.
  - Proposals require a registered proposer with matching capabilities.
  - Proposal and vote mutations carry bounded proof records.
  - Voting submission transitions carry bounded proof records.
  - Execution readiness transitions carry bounded proof records.
  - Dispatch results carry bounded proof records.
  - Observability read models are bounded and aggregated.
  - Consensus requires quorum (majority of registered agents).
  - Plans are immutable once approved.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
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


_GOVERNED_RESULT_KEYS = frozenset({
    "proposal_id",
    "proof_id",
    "success",
    "error",
    "suppressed_executor_keys",
})


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
class DispatchProof:
    """Bounded proof record for an orchestration dispatch decision."""
    proof_id: str
    plan_id: str
    proposal_id: str
    agent_id: str
    decision: str
    reason: str
    checked_at: str
    quorum_met: bool
    agent_registered: bool
    agent_capable: bool
    manifest_admitted: bool
    manifest_gated: bool
    required_capability_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "quorum_met": self.quorum_met,
            "agent_registered": self.agent_registered,
            "agent_capable": self.agent_capable,
            "manifest_admitted": self.manifest_admitted,
            "manifest_gated": self.manifest_gated,
            "required_capability_count": self.required_capability_count,
        }


@dataclass
class ProposalProof:
    """Bounded proof record for a proposal admission decision."""
    proof_id: str
    plan_id: str
    proposal_id: str
    agent_id: str
    decision: str
    reason: str
    checked_at: str
    plan_phase: str
    agent_registered: bool
    agent_capable: bool
    manifest_admitted: bool
    manifest_gated: bool
    required_capability_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "plan_phase": self.plan_phase,
            "agent_registered": self.agent_registered,
            "agent_capable": self.agent_capable,
            "manifest_admitted": self.manifest_admitted,
            "manifest_gated": self.manifest_gated,
            "required_capability_count": self.required_capability_count,
        }


@dataclass
class VoteProof:
    """Bounded proof record for a vote mutation decision."""
    proof_id: str
    plan_id: str
    agent_id: str
    vote: str
    decision: str
    reason: str
    checked_at: str
    plan_phase: str
    voter_registered: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "agent_id": self.agent_id,
            "vote": self.vote,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "plan_phase": self.plan_phase,
            "voter_registered": self.voter_registered,
        }


@dataclass
class VotingSubmissionProof:
    """Bounded proof record for a planning-to-voting transition."""
    proof_id: str
    plan_id: str
    decision: str
    reason: str
    checked_at: str
    from_phase: str
    to_phase: str
    proposal_count: int
    voter_count: int
    quorum_possible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "proposal_count": self.proposal_count,
            "voter_count": self.voter_count,
            "quorum_possible": self.quorum_possible,
        }


@dataclass
class ExecutionReadinessProof:
    """Bounded proof record for a voting-to-execution transition."""
    proof_id: str
    plan_id: str
    decision: str
    reason: str
    checked_at: str
    from_phase: str
    to_phase: str
    proposal_count: int
    vote_count: int
    approval_count: int
    rejection_count: int
    voter_count: int
    quorum_met: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "proposal_count": self.proposal_count,
            "vote_count": self.vote_count,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "voter_count": self.voter_count,
            "quorum_met": self.quorum_met,
        }


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
    proposal_proofs: list[ProposalProof] = field(default_factory=list)
    vote_proofs: list[VoteProof] = field(default_factory=list)
    submission_proofs: list[VotingSubmissionProof] = field(default_factory=list)
    execution_proofs: list[ExecutionReadinessProof] = field(default_factory=list)
    dispatch_proofs: list[DispatchProof] = field(default_factory=list)
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
            "proposal_proofs": [proof.to_dict() for proof in self.proposal_proofs],
            "vote_proofs": [proof.to_dict() for proof in self.vote_proofs],
            "submission_proofs": [proof.to_dict() for proof in self.submission_proofs],
            "execution_proofs": [proof.to_dict() for proof in self.execution_proofs],
            "dispatch_proofs": [proof.to_dict() for proof in self.dispatch_proofs],
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
    proof_id: str = ""


@dataclass
class HandoffProof:
    """Bounded proof record for an agent-to-agent handoff decision."""
    proof_id: str
    from_agent: str
    to_agent: str
    decision: str
    reason: str
    checked_at: str
    source_registered: bool
    target_registered: bool
    target_capable: bool
    manifest_admitted: bool
    manifest_gated: bool
    required_capability_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "source_registered": self.source_registered,
            "target_registered": self.target_registered,
            "target_capable": self.target_capable,
            "manifest_admitted": self.manifest_admitted,
            "manifest_gated": self.manifest_gated,
            "required_capability_count": self.required_capability_count,
        }


@dataclass(frozen=True)
class SanitizedExecutorResult:
    """Executor output after governed result keys are suppressed."""
    output: dict[str, Any]
    suppressed_keys: tuple[str, ...]


class AgentOrchestrator:
    """Governs multi-agent coordination, consensus, and handoffs."""

    def __init__(self, clock: Callable[[], str],
                 agent_capabilities: dict[str, tuple[str, ...]] | None = None,
                 admitted_capabilities: tuple[str, ...] | None = None):
        self._clock = clock
        self._capabilities: dict[str, tuple[str, ...]] = dict(agent_capabilities or {})
        self._admitted_capabilities: frozenset[str] | None = _normalize_admitted_capabilities(admitted_capabilities)
        self._plans: dict[str, OrchestrationPlan] = {}
        self._handoffs: list[HandoffResult] = []
        self._handoff_proofs: list[HandoffProof] = []
        self._total_plans = 0
        self._total_handoffs = 0

    @classmethod
    def from_manifest_read_model(
        cls,
        *,
        clock: Callable[[], str],
        manifest_read_model: Mapping[str, Any] | None,
        agent_capabilities: dict[str, tuple[str, ...]] | None = None,
    ) -> "AgentOrchestrator":
        """Build an orchestrator constrained by admitted manifest capability ids."""
        return cls(
            clock=clock,
            agent_capabilities=agent_capabilities,
            admitted_capabilities=_capability_ids_from_manifest_read_model(manifest_read_model),
        )

    def register_agent(self, agent_id: str, capabilities: tuple[str, ...]) -> None:
        self._capabilities[agent_id] = capabilities

    def unregister_agent(self, agent_id: str) -> None:
        self._capabilities.pop(agent_id, None)

    @property
    def agent_count(self) -> int:
        return len(self._capabilities)

    @property
    def manifest_gated(self) -> bool:
        return self._admitted_capabilities is not None

    def set_admitted_capabilities(self, admitted_capabilities: tuple[str, ...] | None) -> None:
        """Replace the manifest-admitted capability set used by planning."""
        self._admitted_capabilities = _normalize_admitted_capabilities(admitted_capabilities)

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
            plan.proposal_proofs.append(
                self._build_proposal_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="rejected",
                    reason="plan not accepting proposals",
                )
            )
            raise ValueError("plan not accepting proposals")
        if any(existing.proposal_id == proposal.proposal_id for existing in plan.proposals):
            plan.proposal_proofs.append(
                self._build_proposal_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="rejected",
                    reason="proposal already recorded",
                )
            )
            raise ValueError("proposal already recorded")
        admission_error = self._proposal_admission_error(proposal)
        if admission_error:
            plan.proposal_proofs.append(
                self._build_proposal_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="rejected",
                    reason=admission_error,
                )
            )
            raise ValueError(admission_error)
        plan.proposals.append(proposal)
        plan.proposal_proofs.append(
            self._build_proposal_proof(
                plan=plan,
                proposal=proposal,
                decision="accepted",
                reason="proposal admitted",
            )
        )

    def submit_for_voting(self, plan_id: str) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if plan.phase != OrchestrationPhase.PLANNING:
            plan.submission_proofs.append(
                self._build_submission_proof(
                    plan=plan,
                    decision="rejected",
                    reason="plan not accepting submission",
                    to_phase=plan.phase,
                )
            )
            raise ValueError("plan not accepting submission")
        if not plan.proposals:
            plan.submission_proofs.append(
                self._build_submission_proof(
                    plan=plan,
                    decision="rejected",
                    reason="empty plan",
                    to_phase=plan.phase,
                )
            )
            raise ValueError("Cannot vote on empty plan")
        plan.submission_proofs.append(
            self._build_submission_proof(
                plan=plan,
                decision="accepted",
                reason="submitted for voting",
                to_phase=OrchestrationPhase.VOTING,
            )
        )
        plan.phase = OrchestrationPhase.VOTING

    def cast_vote(self, plan_id: str, agent_id: str, vote: Vote) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError("plan unavailable")
        if plan.phase != OrchestrationPhase.VOTING:
            plan.vote_proofs.append(
                self._build_vote_proof(
                    plan=plan,
                    agent_id=agent_id,
                    vote=vote,
                    decision="rejected",
                    reason="plan not accepting votes",
                )
            )
            raise ValueError("plan not accepting votes")
        if agent_id not in self._capabilities:
            plan.vote_proofs.append(
                self._build_vote_proof(
                    plan=plan,
                    agent_id=agent_id,
                    vote=vote,
                    decision="rejected",
                    reason="voting agent unavailable",
                )
            )
            raise ValueError("voting agent unavailable")
        if agent_id in plan.votes:
            plan.vote_proofs.append(
                self._build_vote_proof(
                    plan=plan,
                    agent_id=agent_id,
                    vote=vote,
                    decision="rejected",
                    reason="vote already recorded",
                )
            )
            raise ValueError("vote already recorded")
        plan.votes[agent_id] = vote
        plan.vote_proofs.append(
            self._build_vote_proof(
                plan=plan,
                agent_id=agent_id,
                vote=vote,
                decision="accepted",
                reason="vote recorded",
            )
        )

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
            plan.execution_proofs.append(
                self._build_execution_readiness_proof(
                    plan=plan,
                    decision="rejected",
                    reason="plan not ready for execution",
                    to_phase=plan.phase,
                )
            )
            raise ValueError("plan not ready for execution")
        if not plan.has_quorum(self.agent_count):
            plan.execution_proofs.append(
                self._build_execution_readiness_proof(
                    plan=plan,
                    decision="blocked",
                    reason="consensus quorum not met",
                    to_phase=OrchestrationPhase.FAILED,
                )
            )
            proof = self._build_dispatch_proof(
                plan=plan,
                proposal=None,
                decision="blocked",
                reason="consensus quorum not met",
                quorum_met=False,
            )
            plan.dispatch_proofs.append(proof)
            plan.phase = OrchestrationPhase.FAILED
            return plan

        plan.execution_proofs.append(
            self._build_execution_readiness_proof(
                plan=plan,
                decision="accepted",
                reason="execution admitted",
                to_phase=OrchestrationPhase.EXECUTING,
            )
        )
        plan.phase = OrchestrationPhase.EXECUTING
        for proposal in sorted(plan.proposals, key=lambda p: -p.priority):
            admission_error = self._proposal_admission_error(proposal)
            if admission_error:
                proof = self._build_dispatch_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="blocked",
                    reason=admission_error,
                    quorum_met=True,
                )
                plan.dispatch_proofs.append(proof)
                plan.results.append({
                    "proposal_id": proposal.proposal_id,
                    "proof_id": proof.proof_id,
                    "success": False,
                    "error": admission_error,
                })
                continue
            try:
                if executor:
                    result = executor(proposal)
                else:
                    result = {"status": "executed", "proposal_id": proposal.proposal_id}
                safe_result = _sanitize_executor_result(result)
                proof = self._build_dispatch_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="executed",
                    reason="proposal dispatched",
                    quorum_met=True,
                )
                plan.dispatch_proofs.append(proof)
                result_record = {
                    "proposal_id": proposal.proposal_id,
                    "proof_id": proof.proof_id,
                    "success": True,
                    **safe_result.output,
                }
                if safe_result.suppressed_keys:
                    result_record["suppressed_executor_keys"] = safe_result.suppressed_keys
                plan.results.append(result_record)
            except Exception as e:
                proof = self._build_dispatch_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="failed",
                    reason="executor error",
                    quorum_met=True,
                )
                plan.dispatch_proofs.append(proof)
                plan.results.append({
                    "proposal_id": proposal.proposal_id,
                    "proof_id": proof.proof_id,
                    "success": False,
                    "error": _classify_orchestration_exception(e),
                })

        all_ok = all(r.get("success") for r in plan.results)
        plan.phase = OrchestrationPhase.COMPLETED if all_ok else OrchestrationPhase.FAILED
        return plan

    def handoff(self, from_agent: str, to_agent: str,
                required_capabilities: tuple[str, ...] = (),
                payload: dict[str, Any] | None = None) -> HandoffResult:
        handoff_error = self._handoff_admission_error(
            from_agent,
            to_agent,
            required_capabilities,
        )
        if handoff_error:
            proof = self._build_handoff_proof(
                from_agent=from_agent,
                to_agent=to_agent,
                required_capabilities=required_capabilities,
                decision="blocked",
                reason=handoff_error,
            )
            self._handoff_proofs.append(proof)
            self._total_handoffs += 1
            return HandoffResult(
                from_agent,
                to_agent,
                False,
                proof_id=proof.proof_id,
                error=handoff_error,
            )

        proof = self._build_handoff_proof(
            from_agent=from_agent,
            to_agent=to_agent,
            required_capabilities=required_capabilities,
            decision="transferred",
            reason="handoff admitted",
        )
        self._handoff_proofs.append(proof)
        result = HandoffResult(
            from_agent,
            to_agent,
            True,
            proof_id=proof.proof_id,
            payload=payload or {},
        )
        self._handoffs.append(result)
        self._total_handoffs += 1
        return result

    def find_capable_agents(self, required: tuple[str, ...]) -> list[str]:
        if self._unadmitted_capabilities(required):
            return []
        required_set = set(required)
        return [aid for aid, caps in self._capabilities.items() if required_set <= set(caps)]

    def get_plan(self, plan_id: str) -> OrchestrationPlan | None:
        return self._plans.get(plan_id)

    def read_model(self, proof_limit: int = 20) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "recent_proposal_proofs": self._recent_proposal_proofs(proof_limit),
            "recent_vote_proofs": self._recent_vote_proofs(proof_limit),
            "recent_submission_proofs": self._recent_submission_proofs(proof_limit),
            "recent_execution_proofs": self._recent_execution_proofs(proof_limit),
            "recent_dispatch_proofs": self._recent_dispatch_proofs(proof_limit),
            "recent_handoff_proofs": self.handoff_proofs(limit=proof_limit),
        }

    def handoff_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._handoff_proofs[-limit:]]

    def summary(self) -> dict[str, Any]:
        return {
            "registered_agents": self.agent_count,
            "total_plans": self._total_plans,
            "active_plans": sum(1 for p in self._plans.values()
                                if p.phase in (OrchestrationPhase.PLANNING,
                                               OrchestrationPhase.VOTING,
                                               OrchestrationPhase.EXECUTING)),
            "plans_by_phase": _count_by_value(p.phase.value for p in self._plans.values()),
            "total_handoffs": self._total_handoffs,
            "successful_handoffs": len(self._handoffs),
            "handoff_proofs": len(self._handoff_proofs),
            "handoff_decisions": _count_by_value(
                proof.decision for proof in self._handoff_proofs
            ),
            "manifest_gated": self.manifest_gated,
            "admitted_capability_count": (
                0 if self._admitted_capabilities is None else len(self._admitted_capabilities)
            ),
            "dispatch_proofs": sum(len(p.dispatch_proofs) for p in self._plans.values()),
            "dispatch_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.dispatch_proofs
            ),
            "proposal_proofs": sum(len(p.proposal_proofs) for p in self._plans.values()),
            "proposal_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.proposal_proofs
            ),
            "vote_proofs": sum(len(p.vote_proofs) for p in self._plans.values()),
            "vote_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.vote_proofs
            ),
            "submission_proofs": sum(len(p.submission_proofs) for p in self._plans.values()),
            "submission_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.submission_proofs
            ),
            "execution_proofs": sum(len(p.execution_proofs) for p in self._plans.values()),
            "execution_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.execution_proofs
            ),
        }

    def _recent_proposal_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.proposal_proofs
        ]
        return [proof.to_dict() for proof in proofs[-limit:]]

    def _recent_vote_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.vote_proofs
        ]
        return [proof.to_dict() for proof in proofs[-limit:]]

    def _recent_submission_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.submission_proofs
        ]
        return [proof.to_dict() for proof in proofs[-limit:]]

    def _recent_execution_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.execution_proofs
        ]
        return [proof.to_dict() for proof in proofs[-limit:]]

    def _recent_dispatch_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.dispatch_proofs
        ]
        return [proof.to_dict() for proof in proofs[-limit:]]

    def _unadmitted_capabilities(self, required: tuple[str, ...]) -> tuple[str, ...]:
        if self._admitted_capabilities is None:
            return ()
        return tuple(
            capability
            for capability in required
            if capability not in self._admitted_capabilities
        )

    def _missing_agent_capabilities(
        self,
        agent_id: str,
        required: tuple[str, ...],
    ) -> tuple[str, ...]:
        agent_capabilities = set(self._capabilities.get(agent_id, ()))
        return tuple(
            capability
            for capability in required
            if capability not in agent_capabilities
        )

    def _proposal_admission_error(self, proposal: AgentProposal) -> str:
        if proposal.agent_id not in self._capabilities:
            return "proposal agent unavailable"
        if self._missing_agent_capabilities(
            proposal.agent_id,
            proposal.required_capabilities,
        ):
            return "proposal agent lacks required capabilities"
        if self._unadmitted_capabilities(proposal.required_capabilities):
            return "proposal requires unadmitted capabilities"
        return ""

    def _build_proposal_proof(
        self,
        *,
        plan: OrchestrationPlan,
        proposal: AgentProposal,
        decision: str,
        reason: str,
    ) -> ProposalProof:
        required_capabilities = proposal.required_capabilities
        agent_registered = proposal.agent_id in self._capabilities
        agent_capable = bool(
            agent_registered
            and not self._missing_agent_capabilities(
                proposal.agent_id,
                required_capabilities,
            )
        )
        manifest_admitted = not self._unadmitted_capabilities(required_capabilities)
        proof_index = len(plan.proposal_proofs) + 1
        return ProposalProof(
            proof_id=f"{plan.plan_id}:proposal:{proof_index}",
            plan_id=plan.plan_id,
            proposal_id=proposal.proposal_id,
            agent_id=proposal.agent_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            plan_phase=plan.phase.value,
            agent_registered=agent_registered,
            agent_capable=agent_capable,
            manifest_admitted=manifest_admitted,
            manifest_gated=self.manifest_gated,
            required_capability_count=len(required_capabilities),
        )

    def _build_vote_proof(
        self,
        *,
        plan: OrchestrationPlan,
        agent_id: str,
        vote: Vote,
        decision: str,
        reason: str,
    ) -> VoteProof:
        proof_index = len(plan.vote_proofs) + 1
        return VoteProof(
            proof_id=f"{plan.plan_id}:vote:{proof_index}",
            plan_id=plan.plan_id,
            agent_id=agent_id,
            vote=vote.value,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            plan_phase=plan.phase.value,
            voter_registered=agent_id in self._capabilities,
        )

    def _build_submission_proof(
        self,
        *,
        plan: OrchestrationPlan,
        decision: str,
        reason: str,
        to_phase: OrchestrationPhase,
    ) -> VotingSubmissionProof:
        proof_index = len(plan.submission_proofs) + 1
        return VotingSubmissionProof(
            proof_id=f"{plan.plan_id}:submission:{proof_index}",
            plan_id=plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            from_phase=plan.phase.value,
            to_phase=to_phase.value,
            proposal_count=len(plan.proposals),
            voter_count=self.agent_count,
            quorum_possible=self.agent_count > 0 and bool(plan.proposals),
        )

    def _build_execution_readiness_proof(
        self,
        *,
        plan: OrchestrationPlan,
        decision: str,
        reason: str,
        to_phase: OrchestrationPhase,
    ) -> ExecutionReadinessProof:
        proof_index = len(plan.execution_proofs) + 1
        return ExecutionReadinessProof(
            proof_id=f"{plan.plan_id}:execution:{proof_index}",
            plan_id=plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            from_phase=plan.phase.value,
            to_phase=to_phase.value,
            proposal_count=len(plan.proposals),
            vote_count=len(plan.votes),
            approval_count=plan.approval_count,
            rejection_count=plan.rejection_count,
            voter_count=self.agent_count,
            quorum_met=plan.has_quorum(self.agent_count),
        )

    def _handoff_admission_error(
        self,
        from_agent: str,
        to_agent: str,
        required_capabilities: tuple[str, ...],
    ) -> str:
        if from_agent not in self._capabilities:
            return "source agent unavailable"
        if to_agent not in self._capabilities:
            return "target agent unavailable"
        if self._missing_agent_capabilities(to_agent, required_capabilities):
            return "target agent lacks required capabilities"
        if self._unadmitted_capabilities(required_capabilities):
            return "required capabilities are not manifest admitted"
        return ""

    def _build_dispatch_proof(
        self,
        *,
        plan: OrchestrationPlan,
        proposal: AgentProposal | None,
        decision: str,
        reason: str,
        quorum_met: bool,
    ) -> DispatchProof:
        proposal_id = "" if proposal is None else proposal.proposal_id
        agent_id = "" if proposal is None else proposal.agent_id
        required_capabilities = () if proposal is None else proposal.required_capabilities
        agent_registered = bool(proposal is not None and agent_id in self._capabilities)
        agent_capable = bool(
            proposal is not None
            and not self._missing_agent_capabilities(agent_id, required_capabilities)
        )
        manifest_admitted = not self._unadmitted_capabilities(required_capabilities)
        proof_index = len(plan.dispatch_proofs) + 1
        return DispatchProof(
            proof_id=f"{plan.plan_id}:{proposal_id or 'plan'}:{proof_index}",
            plan_id=plan.plan_id,
            proposal_id=proposal_id,
            agent_id=agent_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            quorum_met=quorum_met,
            agent_registered=agent_registered,
            agent_capable=agent_capable,
            manifest_admitted=manifest_admitted,
            manifest_gated=self.manifest_gated,
            required_capability_count=len(required_capabilities),
        )

    def _build_handoff_proof(
        self,
        *,
        from_agent: str,
        to_agent: str,
        required_capabilities: tuple[str, ...],
        decision: str,
        reason: str,
    ) -> HandoffProof:
        source_registered = from_agent in self._capabilities
        target_registered = to_agent in self._capabilities
        target_capable = bool(
            target_registered
            and not self._missing_agent_capabilities(to_agent, required_capabilities)
        )
        manifest_admitted = not self._unadmitted_capabilities(required_capabilities)
        proof_index = len(self._handoff_proofs) + 1
        return HandoffProof(
            proof_id=f"handoff:{proof_index}",
            from_agent=from_agent,
            to_agent=to_agent,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            source_registered=source_registered,
            target_registered=target_registered,
            target_capable=target_capable,
            manifest_admitted=manifest_admitted,
            manifest_gated=self.manifest_gated,
            required_capability_count=len(required_capabilities),
        )


def _normalize_admitted_capabilities(values: tuple[str, ...] | None) -> frozenset[str] | None:
    if values is None:
        return None
    return frozenset(str(value).strip() for value in values if str(value).strip())


def _capability_ids_from_manifest_read_model(read_model: Mapping[str, Any] | None) -> tuple[str, ...] | None:
    if read_model is None:
        return None
    raw_ids = read_model.get("capability_ids", ())
    if not isinstance(raw_ids, (tuple, list)):
        return ()
    return tuple(str(capability_id).strip() for capability_id in raw_ids if str(capability_id).strip())


def _sanitize_executor_result(raw_result: Mapping[str, Any]) -> SanitizedExecutorResult:
    if not isinstance(raw_result, Mapping):
        raise TypeError("executor output must be a mapping")
    output: dict[str, Any] = {}
    suppressed_keys: list[str] = []
    for key, value in raw_result.items():
        normalized_key = str(key)
        if normalized_key in _GOVERNED_RESULT_KEYS:
            suppressed_keys.append(normalized_key)
            continue
        output[normalized_key] = value
    return SanitizedExecutorResult(
        output=output,
        suppressed_keys=tuple(suppressed_keys),
    )


def _count_by_value(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
