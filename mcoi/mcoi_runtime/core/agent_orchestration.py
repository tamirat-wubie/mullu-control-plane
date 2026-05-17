"""Phase 222C — Agent Orchestration Protocol.

Purpose: Coordinate multi-agent workflows with governed handoffs, capability
    negotiation, and consensus protocols. Agents can propose, vote, and
    execute plans through a governed orchestrator.
Dependencies: agent_protocol, agent_chain.
Invariants:
  - All orchestration decisions are auditable.
  - Agent registry mutations carry bounded proof records.
  - Agent registry proofs carry bounded runtime impact counts.
  - Plan creation admission carries bounded proof records.
  - Plan creation proofs carry bounded active-surface transition counts.
  - Plan lookup observations carry bounded proof records.
  - Manifest binding bootstrap carries bounded proof records.
  - Capability admission policy changes carry bounded proof records.
  - Capability policy proofs carry bounded runtime impact counts.
  - Capability discovery observations carry bounded proof records.
  - Capability discovery proofs carry bounded active-surface records.
  - Agent handoffs require capability matching.
  - Handoff attempts carry bounded proof records.
  - Proposals require a registered proposer with matching capabilities.
  - Proposal and vote mutations carry bounded proof records.
  - Proposal proofs carry bounded proposal-count transition records.
  - Vote proofs carry bounded vote-count transition records.
  - Voting submission transitions carry bounded proof records.
  - Voting submission proofs carry bounded phase-surface transition records.
  - Consensus observations carry bounded proof records.
  - Consensus proofs carry bounded threshold and active-surface records.
  - Execution readiness transitions carry bounded proof records.
  - Execution readiness proofs carry bounded phase-surface transition records.
  - Dispatch results carry bounded proof records.
  - Dispatch proofs carry bounded result and dispatch-count transition records.
  - Executor result suppression is counted in dispatch proof records.
  - Plan finalization transitions carry bounded proof records.
  - Plan finalization proofs carry bounded terminal phase-surface records.
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
    suppressed_executor_key_count: int
    dispatch_count_before: int
    dispatch_count_after: int
    result_count_before: int
    result_count_after: int
    successful_result_count_before: int
    successful_result_count_after: int
    failed_result_count_before: int
    failed_result_count_after: int

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
            "suppressed_executor_key_count": self.suppressed_executor_key_count,
            "dispatch_count_before": self.dispatch_count_before,
            "dispatch_count_after": self.dispatch_count_after,
            "result_count_before": self.result_count_before,
            "result_count_after": self.result_count_after,
            "successful_result_count_before": self.successful_result_count_before,
            "successful_result_count_after": self.successful_result_count_after,
            "failed_result_count_before": self.failed_result_count_before,
            "failed_result_count_after": self.failed_result_count_after,
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
    proposal_count_before: int
    proposal_count_after: int
    active_proposal_count_before: int
    active_proposal_count_after: int

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
            "proposal_count_before": self.proposal_count_before,
            "proposal_count_after": self.proposal_count_after,
            "active_proposal_count_before": self.active_proposal_count_before,
            "active_proposal_count_after": self.active_proposal_count_after,
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
    vote_count_before: int
    vote_count_after: int
    approval_count_before: int
    approval_count_after: int
    rejection_count_before: int
    rejection_count_after: int

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
            "vote_count_before": self.vote_count_before,
            "vote_count_after": self.vote_count_after,
            "approval_count_before": self.approval_count_before,
            "approval_count_after": self.approval_count_after,
            "rejection_count_before": self.rejection_count_before,
            "rejection_count_after": self.rejection_count_after,
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
    phase_changed: bool
    active_plan_count_before: int
    active_plan_count_after: int
    active_proposal_count_before: int
    active_proposal_count_after: int
    from_phase_plan_count_before: int
    from_phase_plan_count_after: int
    to_phase_plan_count_before: int
    to_phase_plan_count_after: int

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
            "phase_changed": self.phase_changed,
            "active_plan_count_before": self.active_plan_count_before,
            "active_plan_count_after": self.active_plan_count_after,
            "active_proposal_count_before": self.active_proposal_count_before,
            "active_proposal_count_after": self.active_proposal_count_after,
            "from_phase_plan_count_before": self.from_phase_plan_count_before,
            "from_phase_plan_count_after": self.from_phase_plan_count_after,
            "to_phase_plan_count_before": self.to_phase_plan_count_before,
            "to_phase_plan_count_after": self.to_phase_plan_count_after,
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
    phase_changed: bool
    active_plan_count_before: int
    active_plan_count_after: int
    active_proposal_count_before: int
    active_proposal_count_after: int
    from_phase_plan_count_before: int
    from_phase_plan_count_after: int
    to_phase_plan_count_before: int
    to_phase_plan_count_after: int

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
            "phase_changed": self.phase_changed,
            "active_plan_count_before": self.active_plan_count_before,
            "active_plan_count_after": self.active_plan_count_after,
            "active_proposal_count_before": self.active_proposal_count_before,
            "active_proposal_count_after": self.active_proposal_count_after,
            "from_phase_plan_count_before": self.from_phase_plan_count_before,
            "from_phase_plan_count_after": self.from_phase_plan_count_after,
            "to_phase_plan_count_before": self.to_phase_plan_count_before,
            "to_phase_plan_count_after": self.to_phase_plan_count_after,
        }


@dataclass
class PlanFinalizationProof:
    """Bounded proof record for an execution-to-terminal transition."""
    proof_id: str
    plan_id: str
    decision: str
    reason: str
    checked_at: str
    from_phase: str
    to_phase: str
    proposal_count: int
    result_count: int
    successful_result_count: int
    failed_result_count: int
    dispatch_count: int
    quorum_met: bool
    phase_changed: bool
    active_plan_count_before: int
    active_plan_count_after: int
    active_proposal_count_before: int
    active_proposal_count_after: int
    from_phase_plan_count_before: int
    from_phase_plan_count_after: int
    to_phase_plan_count_before: int
    to_phase_plan_count_after: int

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
            "result_count": self.result_count,
            "successful_result_count": self.successful_result_count,
            "failed_result_count": self.failed_result_count,
            "dispatch_count": self.dispatch_count,
            "quorum_met": self.quorum_met,
            "phase_changed": self.phase_changed,
            "active_plan_count_before": self.active_plan_count_before,
            "active_plan_count_after": self.active_plan_count_after,
            "active_proposal_count_before": self.active_proposal_count_before,
            "active_proposal_count_after": self.active_proposal_count_after,
            "from_phase_plan_count_before": self.from_phase_plan_count_before,
            "from_phase_plan_count_after": self.from_phase_plan_count_after,
            "to_phase_plan_count_before": self.to_phase_plan_count_before,
            "to_phase_plan_count_after": self.to_phase_plan_count_after,
        }


@dataclass
class AgentRegistryProof:
    """Bounded proof record for agent registry mutations."""
    proof_id: str
    agent_id: str
    action: str
    decision: str
    reason: str
    checked_at: str
    previous_registered: bool
    current_registered: bool
    previous_capability_count: int
    current_capability_count: int
    manifest_gated: bool
    admitted_capability_count: int
    registered_agent_count: int
    total_plan_count: int
    active_plan_count: int
    active_proposal_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "previous_registered": self.previous_registered,
            "current_registered": self.current_registered,
            "previous_capability_count": self.previous_capability_count,
            "current_capability_count": self.current_capability_count,
            "manifest_gated": self.manifest_gated,
            "admitted_capability_count": self.admitted_capability_count,
            "registered_agent_count": self.registered_agent_count,
            "total_plan_count": self.total_plan_count,
            "active_plan_count": self.active_plan_count,
            "active_proposal_count": self.active_proposal_count,
        }


@dataclass
class PlanCreationProof:
    """Bounded proof record for plan creation admission decisions."""
    proof_id: str
    plan_id: str
    initiator_id: str
    decision: str
    reason: str
    checked_at: str
    plan_phase: str
    initiator_registered: bool
    registered_agent_count: int
    manifest_gated: bool
    admitted_capability_count: int
    total_plan_count_before: int
    total_plan_count_after: int
    active_plan_count_before: int
    active_plan_count_after: int
    active_proposal_count_before: int
    active_proposal_count_after: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "initiator_id": self.initiator_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "plan_phase": self.plan_phase,
            "initiator_registered": self.initiator_registered,
            "registered_agent_count": self.registered_agent_count,
            "manifest_gated": self.manifest_gated,
            "admitted_capability_count": self.admitted_capability_count,
            "total_plan_count_before": self.total_plan_count_before,
            "total_plan_count_after": self.total_plan_count_after,
            "active_plan_count_before": self.active_plan_count_before,
            "active_plan_count_after": self.active_plan_count_after,
            "active_proposal_count_before": self.active_proposal_count_before,
            "active_proposal_count_after": self.active_proposal_count_after,
        }


@dataclass
class CapabilityPolicyProof:
    """Bounded proof record for manifest admission policy mutations."""
    proof_id: str
    action: str
    decision: str
    reason: str
    checked_at: str
    previous_manifest_gated: bool
    current_manifest_gated: bool
    previous_admitted_capability_count: int
    current_admitted_capability_count: int
    added_capability_count: int
    removed_capability_count: int
    registered_agent_count: int
    total_plan_count: int
    active_plan_count: int
    active_proposal_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "previous_manifest_gated": self.previous_manifest_gated,
            "current_manifest_gated": self.current_manifest_gated,
            "previous_admitted_capability_count": self.previous_admitted_capability_count,
            "current_admitted_capability_count": self.current_admitted_capability_count,
            "added_capability_count": self.added_capability_count,
            "removed_capability_count": self.removed_capability_count,
            "registered_agent_count": self.registered_agent_count,
            "total_plan_count": self.total_plan_count,
            "active_plan_count": self.active_plan_count,
            "active_proposal_count": self.active_proposal_count,
        }


@dataclass
class ConsensusObservationProof:
    """Bounded proof record for a consensus observation."""
    proof_id: str
    plan_id: str
    decision: str
    reason: str
    checked_at: str
    plan_phase: str
    plan_available: bool
    proposal_count: int
    vote_count: int
    approval_count: int
    rejection_count: int
    registered_agent_count: int
    quorum_threshold: int
    total_plan_count: int
    active_plan_count: int
    active_proposal_count: int
    consensus_proof_count_before: int
    consensus_proof_count_after: int
    quorum_met: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "plan_phase": self.plan_phase,
            "plan_available": self.plan_available,
            "proposal_count": self.proposal_count,
            "vote_count": self.vote_count,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "registered_agent_count": self.registered_agent_count,
            "quorum_threshold": self.quorum_threshold,
            "total_plan_count": self.total_plan_count,
            "active_plan_count": self.active_plan_count,
            "active_proposal_count": self.active_proposal_count,
            "consensus_proof_count_before": self.consensus_proof_count_before,
            "consensus_proof_count_after": self.consensus_proof_count_after,
            "quorum_met": self.quorum_met,
        }


@dataclass
class CapabilityDiscoveryProof:
    """Bounded proof record for capability discovery observations."""
    proof_id: str
    decision: str
    reason: str
    checked_at: str
    required_capability_count: int
    registered_agent_count: int
    matched_agent_count: int
    manifest_gated: bool
    manifest_admitted: bool
    total_plan_count: int
    active_plan_count: int
    active_proposal_count: int
    capability_discovery_proof_count_before: int
    capability_discovery_proof_count_after: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "required_capability_count": self.required_capability_count,
            "registered_agent_count": self.registered_agent_count,
            "matched_agent_count": self.matched_agent_count,
            "manifest_gated": self.manifest_gated,
            "manifest_admitted": self.manifest_admitted,
            "total_plan_count": self.total_plan_count,
            "active_plan_count": self.active_plan_count,
            "active_proposal_count": self.active_proposal_count,
            "capability_discovery_proof_count_before": (
                self.capability_discovery_proof_count_before
            ),
            "capability_discovery_proof_count_after": (
                self.capability_discovery_proof_count_after
            ),
        }


@dataclass
class PlanLookupProof:
    """Bounded proof record for plan lookup observations."""
    proof_id: str
    action: str
    decision: str
    reason: str
    checked_at: str
    plan_id: str
    plan_available: bool
    plan_phase: str
    registered_agent_count: int
    total_plan_count: int
    active_plan_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "plan_id": self.plan_id,
            "plan_available": self.plan_available,
            "plan_phase": self.plan_phase,
            "registered_agent_count": self.registered_agent_count,
            "total_plan_count": self.total_plan_count,
            "active_plan_count": self.active_plan_count,
        }


@dataclass
class ManifestBindingProof:
    """Bounded proof record for initial manifest binding state."""
    proof_id: str
    action: str
    decision: str
    reason: str
    checked_at: str
    manifest_read_model_available: bool
    raw_capability_count: int
    admitted_capability_count: int
    manifest_gated: bool
    registered_agent_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "checked_at": self.checked_at,
            "manifest_read_model_available": self.manifest_read_model_available,
            "raw_capability_count": self.raw_capability_count,
            "admitted_capability_count": self.admitted_capability_count,
            "manifest_gated": self.manifest_gated,
            "registered_agent_count": self.registered_agent_count,
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
    finalization_proofs: list[PlanFinalizationProof] = field(default_factory=list)
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
            "finalization_proofs": [proof.to_dict() for proof in self.finalization_proofs],
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
                 admitted_capabilities: tuple[str, ...] | None = None,
                 manifest_read_model_available: bool = False,
                 manifest_raw_capability_count: int | None = None,
                 manifest_binding_action: str = "initialize"):
        self._clock = clock
        self._capabilities: dict[str, tuple[str, ...]] = dict(agent_capabilities or {})
        self._admitted_capabilities: frozenset[str] | None = _normalize_admitted_capabilities(admitted_capabilities)
        self._plans: dict[str, OrchestrationPlan] = {}
        self._handoffs: list[HandoffResult] = []
        self._handoff_proofs: list[HandoffProof] = []
        self._registration_proofs: list[AgentRegistryProof] = []
        self._plan_creation_proofs: list[PlanCreationProof] = []
        self._capability_policy_proofs: list[CapabilityPolicyProof] = []
        self._consensus_proofs: list[ConsensusObservationProof] = []
        self._capability_discovery_proofs: list[CapabilityDiscoveryProof] = []
        self._plan_lookup_proofs: list[PlanLookupProof] = []
        self._manifest_binding_proofs: list[ManifestBindingProof] = []
        self._total_plans = 0
        self._total_handoffs = 0
        self._manifest_binding_proofs.append(
            self._build_manifest_binding_proof(
                action=manifest_binding_action,
                manifest_read_model_available=manifest_read_model_available,
                raw_capability_count=(
                    len(admitted_capabilities or ())
                    if manifest_raw_capability_count is None
                    else manifest_raw_capability_count
                ),
            )
        )

    @classmethod
    def from_manifest_read_model(
        cls,
        *,
        clock: Callable[[], str],
        manifest_read_model: Mapping[str, Any] | None,
        agent_capabilities: dict[str, tuple[str, ...]] | None = None,
    ) -> "AgentOrchestrator":
        """Build an orchestrator constrained by admitted manifest capability ids."""
        admitted_capabilities = _capability_ids_from_manifest_read_model(manifest_read_model)
        return cls(
            clock=clock,
            agent_capabilities=agent_capabilities,
            admitted_capabilities=admitted_capabilities,
            manifest_read_model_available=manifest_read_model is not None,
            manifest_raw_capability_count=len(admitted_capabilities or ()),
            manifest_binding_action="from_manifest_read_model",
        )

    def register_agent(self, agent_id: str, capabilities: tuple[str, ...]) -> None:
        previous_capabilities = self._capabilities.get(agent_id)
        current_capabilities = tuple(capabilities)
        self._capabilities[agent_id] = current_capabilities
        self._registration_proofs.append(
            self._build_registration_proof(
                agent_id=agent_id,
                action="register",
                decision="updated" if previous_capabilities is not None else "registered",
                reason=(
                    "agent capabilities updated"
                    if previous_capabilities is not None
                    else "agent registered"
                ),
                previous_capabilities=previous_capabilities,
                current_capabilities=current_capabilities,
            )
        )

    def unregister_agent(self, agent_id: str) -> None:
        previous_capabilities = self._capabilities.pop(agent_id, None)
        self._registration_proofs.append(
            self._build_registration_proof(
                agent_id=agent_id,
                action="unregister",
                decision="unregistered" if previous_capabilities is not None else "ignored",
                reason=(
                    "agent unregistered"
                    if previous_capabilities is not None
                    else "agent unavailable"
                ),
                previous_capabilities=previous_capabilities,
                current_capabilities=None,
            )
        )

    @property
    def agent_count(self) -> int:
        return len(self._capabilities)

    @property
    def manifest_gated(self) -> bool:
        return self._admitted_capabilities is not None

    def set_admitted_capabilities(self, admitted_capabilities: tuple[str, ...] | None) -> None:
        """Replace the manifest-admitted capability set used by planning."""
        previous_admitted_capabilities = self._admitted_capabilities
        current_admitted_capabilities = _normalize_admitted_capabilities(admitted_capabilities)
        self._admitted_capabilities = current_admitted_capabilities
        self._capability_policy_proofs.append(
            self._build_capability_policy_proof(
                previous_admitted_capabilities=previous_admitted_capabilities,
                current_admitted_capabilities=current_admitted_capabilities,
            )
        )

    def create_plan(self, initiator_id: str, goal: str) -> OrchestrationPlan:
        total_plan_count_before = self._total_plans
        active_plan_count_before = self._active_plan_count()
        active_proposal_count_before = self._active_proposal_count()
        if initiator_id not in self._capabilities:
            self._plan_creation_proofs.append(
                self._build_plan_creation_proof(
                    plan_id="",
                    initiator_id=initiator_id,
                    decision="rejected",
                    reason="initiator agent unavailable",
                    plan_phase="",
                    total_plan_count_before=total_plan_count_before,
                    total_plan_count_after=self._total_plans,
                    active_plan_count_before=active_plan_count_before,
                    active_plan_count_after=self._active_plan_count(),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
                )
            )
            raise ValueError("initiator agent unavailable")
        plan = OrchestrationPlan(
            plan_id=uuid.uuid4().hex[:12],
            initiator_id=initiator_id,
            goal=goal,
            created_at=self._clock(),
        )
        self._plans[plan.plan_id] = plan
        self._total_plans += 1
        self._plan_creation_proofs.append(
            self._build_plan_creation_proof(
                plan_id=plan.plan_id,
                initiator_id=initiator_id,
                decision="created",
                reason="plan created",
                plan_phase=plan.phase.value,
                total_plan_count_before=total_plan_count_before,
                total_plan_count_after=self._total_plans,
                active_plan_count_before=active_plan_count_before,
                active_plan_count_after=self._active_plan_count(),
                active_proposal_count_before=active_proposal_count_before,
                active_proposal_count_after=self._active_proposal_count(),
            )
        )
        return plan

    def add_proposal(self, plan_id: str, proposal: AgentProposal) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            self._record_plan_lookup(
                action="add_proposal",
                plan=None,
                decision="unavailable",
                reason="plan unavailable",
            )
            raise ValueError("plan unavailable")
        proposal_count_before = len(plan.proposals)
        active_proposal_count_before = self._active_proposal_count()
        if plan.phase != OrchestrationPhase.PLANNING:
            plan.proposal_proofs.append(
                self._build_proposal_proof(
                    plan=plan,
                    proposal=proposal,
                    decision="rejected",
                    reason="plan not accepting proposals",
                    proposal_count_before=proposal_count_before,
                    proposal_count_after=len(plan.proposals),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
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
                    proposal_count_before=proposal_count_before,
                    proposal_count_after=len(plan.proposals),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
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
                    proposal_count_before=proposal_count_before,
                    proposal_count_after=len(plan.proposals),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
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
                proposal_count_before=proposal_count_before,
                proposal_count_after=len(plan.proposals),
                active_proposal_count_before=active_proposal_count_before,
                active_proposal_count_after=self._active_proposal_count(),
            )
        )

    def submit_for_voting(self, plan_id: str) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            self._record_plan_lookup(
                action="submit_for_voting",
                plan=None,
                decision="unavailable",
                reason="plan unavailable",
            )
            raise ValueError("plan unavailable")
        from_phase = plan.phase
        active_plan_count_before = self._active_plan_count()
        active_proposal_count_before = self._active_proposal_count()
        from_phase_plan_count_before = self._phase_plan_count(from_phase)
        if plan.phase != OrchestrationPhase.PLANNING:
            plan.submission_proofs.append(
                self._build_submission_proof(
                    plan=plan,
                    decision="rejected",
                    reason="plan not accepting submission",
                    from_phase=from_phase,
                    to_phase=plan.phase,
                    active_plan_count_before=active_plan_count_before,
                    active_plan_count_after=self._active_plan_count(),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
                    from_phase_plan_count_before=from_phase_plan_count_before,
                    from_phase_plan_count_after=self._phase_plan_count(from_phase),
                    to_phase_plan_count_before=from_phase_plan_count_before,
                    to_phase_plan_count_after=self._phase_plan_count(plan.phase),
                )
            )
            raise ValueError("plan not accepting submission")
        if not plan.proposals:
            plan.submission_proofs.append(
                self._build_submission_proof(
                    plan=plan,
                    decision="rejected",
                    reason="empty plan",
                    from_phase=from_phase,
                    to_phase=plan.phase,
                    active_plan_count_before=active_plan_count_before,
                    active_plan_count_after=self._active_plan_count(),
                    active_proposal_count_before=active_proposal_count_before,
                    active_proposal_count_after=self._active_proposal_count(),
                    from_phase_plan_count_before=from_phase_plan_count_before,
                    from_phase_plan_count_after=self._phase_plan_count(from_phase),
                    to_phase_plan_count_before=from_phase_plan_count_before,
                    to_phase_plan_count_after=self._phase_plan_count(plan.phase),
                )
            )
            raise ValueError("Cannot vote on empty plan")
        to_phase = OrchestrationPhase.VOTING
        to_phase_plan_count_before = self._phase_plan_count(to_phase)
        plan.phase = to_phase
        plan.submission_proofs.append(
            self._build_submission_proof(
                plan=plan,
                decision="accepted",
                reason="submitted for voting",
                from_phase=from_phase,
                to_phase=to_phase,
                active_plan_count_before=active_plan_count_before,
                active_plan_count_after=self._active_plan_count(),
                active_proposal_count_before=active_proposal_count_before,
                active_proposal_count_after=self._active_proposal_count(),
                from_phase_plan_count_before=from_phase_plan_count_before,
                from_phase_plan_count_after=self._phase_plan_count(from_phase),
                to_phase_plan_count_before=to_phase_plan_count_before,
                to_phase_plan_count_after=self._phase_plan_count(to_phase),
            )
        )

    def cast_vote(self, plan_id: str, agent_id: str, vote: Vote) -> None:
        plan = self._plans.get(plan_id)
        if not plan:
            self._record_plan_lookup(
                action="cast_vote",
                plan=None,
                decision="unavailable",
                reason="plan unavailable",
            )
            raise ValueError("plan unavailable")
        vote_count_before = len(plan.votes)
        approval_count_before = plan.approval_count
        rejection_count_before = plan.rejection_count
        if plan.phase != OrchestrationPhase.VOTING:
            plan.vote_proofs.append(
                self._build_vote_proof(
                    plan=plan,
                    agent_id=agent_id,
                    vote=vote,
                    decision="rejected",
                    reason="plan not accepting votes",
                    vote_count_before=vote_count_before,
                    vote_count_after=len(plan.votes),
                    approval_count_before=approval_count_before,
                    approval_count_after=plan.approval_count,
                    rejection_count_before=rejection_count_before,
                    rejection_count_after=plan.rejection_count,
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
                    vote_count_before=vote_count_before,
                    vote_count_after=len(plan.votes),
                    approval_count_before=approval_count_before,
                    approval_count_after=plan.approval_count,
                    rejection_count_before=rejection_count_before,
                    rejection_count_after=plan.rejection_count,
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
                    vote_count_before=vote_count_before,
                    vote_count_after=len(plan.votes),
                    approval_count_before=approval_count_before,
                    approval_count_after=plan.approval_count,
                    rejection_count_before=rejection_count_before,
                    rejection_count_after=plan.rejection_count,
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
                vote_count_before=vote_count_before,
                vote_count_after=len(plan.votes),
                approval_count_before=approval_count_before,
                approval_count_after=plan.approval_count,
                rejection_count_before=rejection_count_before,
                rejection_count_after=plan.rejection_count,
            )
        )

    def check_consensus(self, plan_id: str) -> bool:
        plan = self._plans.get(plan_id)
        if not plan:
            self._consensus_proofs.append(
                self._build_consensus_proof(
                    plan=None,
                    decision="unavailable",
                    reason="plan unavailable",
                )
            )
            return False
        quorum_met = plan.has_quorum(self.agent_count)
        self._consensus_proofs.append(
            self._build_consensus_proof(
                plan=plan,
                decision="met" if quorum_met else "not_met",
                reason=(
                    "consensus quorum met"
                    if quorum_met
                    else "consensus quorum not met"
                ),
            )
        )
        return quorum_met

    def execute_plan(self, plan_id: str,
                     executor: Callable[[AgentProposal], dict[str, Any]] | None = None) -> OrchestrationPlan:
        plan = self._plans.get(plan_id)
        if not plan:
            self._record_plan_lookup(
                action="execute_plan",
                plan=None,
                decision="unavailable",
                reason="plan unavailable",
            )
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
                result_success=None,
            )
            plan.dispatch_proofs.append(proof)
            self._finalize_plan(
                plan,
                to_phase=OrchestrationPhase.FAILED,
                decision="failed",
                reason="consensus quorum not met",
            )
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
                    result_success=False,
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
                    suppressed_executor_key_count=len(safe_result.suppressed_keys),
                    result_success=True,
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
                    result_success=False,
                )
                plan.dispatch_proofs.append(proof)
                plan.results.append({
                    "proposal_id": proposal.proposal_id,
                    "proof_id": proof.proof_id,
                    "success": False,
                    "error": _classify_orchestration_exception(e),
                })

        all_ok = all(r.get("success") for r in plan.results)
        self._finalize_plan(
            plan,
            to_phase=OrchestrationPhase.COMPLETED if all_ok else OrchestrationPhase.FAILED,
            decision="completed" if all_ok else "failed",
            reason=(
                "all dispatches succeeded"
                if all_ok
                else "one or more dispatches failed"
            ),
        )
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
            self._capability_discovery_proofs.append(
                self._build_capability_discovery_proof(
                    required=required,
                    matched_agent_count=0,
                    decision="blocked",
                    reason="required capabilities are not manifest admitted",
                    manifest_admitted=False,
                )
            )
            return []
        required_set = set(required)
        agents = [
            aid
            for aid, caps in self._capabilities.items()
            if required_set <= set(caps)
        ]
        self._capability_discovery_proofs.append(
            self._build_capability_discovery_proof(
                required=required,
                matched_agent_count=len(agents),
                decision="matched" if agents else "empty",
                reason="capable agents matched" if agents else "no capable agents matched",
                manifest_admitted=True,
            )
        )
        return agents

    def get_plan(self, plan_id: str) -> OrchestrationPlan | None:
        plan = self._plans.get(plan_id)
        self._record_plan_lookup(
            action="get_plan",
            plan=plan,
            decision="found" if plan is not None else "unavailable",
            reason="plan found" if plan is not None else "plan unavailable",
        )
        return plan

    def read_model(self, proof_limit: int = 20) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "recent_registration_proofs": self.registration_proofs(limit=proof_limit),
            "recent_plan_creation_proofs": self.plan_creation_proofs(limit=proof_limit),
            "recent_capability_policy_proofs": self.capability_policy_proofs(limit=proof_limit),
            "recent_consensus_proofs": self.consensus_proofs(limit=proof_limit),
            "recent_capability_discovery_proofs": self.capability_discovery_proofs(
                limit=proof_limit,
            ),
            "recent_plan_lookup_proofs": self.plan_lookup_proofs(limit=proof_limit),
            "recent_manifest_binding_proofs": self.manifest_binding_proofs(
                limit=proof_limit,
            ),
            "recent_proposal_proofs": self._recent_proposal_proofs(proof_limit),
            "recent_vote_proofs": self._recent_vote_proofs(proof_limit),
            "recent_submission_proofs": self._recent_submission_proofs(proof_limit),
            "recent_execution_proofs": self._recent_execution_proofs(proof_limit),
            "recent_dispatch_proofs": self._recent_dispatch_proofs(proof_limit),
            "recent_finalization_proofs": self._recent_finalization_proofs(proof_limit),
            "recent_handoff_proofs": self.handoff_proofs(limit=proof_limit),
        }

    def handoff_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._handoff_proofs[-limit:]]

    def registration_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._registration_proofs[-limit:]]

    def plan_creation_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._plan_creation_proofs[-limit:]]

    def capability_policy_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._capability_policy_proofs[-limit:]]

    def consensus_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._consensus_proofs[-limit:]]

    def capability_discovery_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._capability_discovery_proofs[-limit:]]

    def plan_lookup_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._plan_lookup_proofs[-limit:]]

    def manifest_binding_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return [proof.to_dict() for proof in self._manifest_binding_proofs[-limit:]]

    def summary(self) -> dict[str, Any]:
        return {
            "registered_agents": self.agent_count,
            "registration_proofs": len(self._registration_proofs),
            "registration_decisions": _count_by_value(
                proof.decision for proof in self._registration_proofs
            ),
            "plan_creation_proofs": len(self._plan_creation_proofs),
            "plan_creation_decisions": _count_by_value(
                proof.decision for proof in self._plan_creation_proofs
            ),
            "capability_policy_proofs": len(self._capability_policy_proofs),
            "capability_policy_decisions": _count_by_value(
                proof.decision for proof in self._capability_policy_proofs
            ),
            "consensus_proofs": len(self._consensus_proofs),
            "consensus_decisions": _count_by_value(
                proof.decision for proof in self._consensus_proofs
            ),
            "capability_discovery_proofs": len(self._capability_discovery_proofs),
            "capability_discovery_decisions": _count_by_value(
                proof.decision for proof in self._capability_discovery_proofs
            ),
            "plan_lookup_proofs": len(self._plan_lookup_proofs),
            "plan_lookup_decisions": _count_by_value(
                proof.decision for proof in self._plan_lookup_proofs
            ),
            "manifest_binding_proofs": len(self._manifest_binding_proofs),
            "manifest_binding_decisions": _count_by_value(
                proof.decision for proof in self._manifest_binding_proofs
            ),
            "total_plans": self._total_plans,
            "active_plans": self._active_plan_count(),
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
            "finalization_proofs": sum(
                len(p.finalization_proofs) for p in self._plans.values()
            ),
            "finalization_decisions": _count_by_value(
                proof.decision
                for plan in self._plans.values()
                for proof in plan.finalization_proofs
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

    def _recent_finalization_proofs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        proofs = [
            proof
            for plan in self._plans.values()
            for proof in plan.finalization_proofs
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

    def _active_plan_count(self) -> int:
        return sum(
            1
            for plan in self._plans.values()
            if plan.phase in (
                OrchestrationPhase.PLANNING,
                OrchestrationPhase.VOTING,
                OrchestrationPhase.EXECUTING,
            )
        )

    def _active_proposal_count(self) -> int:
        return sum(
            len(plan.proposals)
            for plan in self._plans.values()
            if plan.phase in (
                OrchestrationPhase.PLANNING,
                OrchestrationPhase.VOTING,
                OrchestrationPhase.EXECUTING,
            )
        )

    def _phase_plan_count(self, phase: OrchestrationPhase) -> int:
        return sum(1 for plan in self._plans.values() if plan.phase == phase)

    @staticmethod
    def _successful_result_count(plan: OrchestrationPlan) -> int:
        return sum(1 for result in plan.results if result.get("success"))

    def _quorum_threshold(self) -> int:
        return self.agent_count // 2 + 1

    def _active_phase(self, phase: OrchestrationPhase) -> bool:
        return phase in (
            OrchestrationPhase.PLANNING,
            OrchestrationPhase.VOTING,
            OrchestrationPhase.EXECUTING,
        )

    def _active_plan_count_after_transition(
        self,
        from_phase: OrchestrationPhase,
        to_phase: OrchestrationPhase,
    ) -> int:
        active_plan_count = self._active_plan_count()
        if from_phase == to_phase:
            return active_plan_count
        if self._active_phase(from_phase) and not self._active_phase(to_phase):
            return active_plan_count - 1
        if not self._active_phase(from_phase) and self._active_phase(to_phase):
            return active_plan_count + 1
        return active_plan_count

    def _active_proposal_count_after_transition(
        self,
        plan: OrchestrationPlan,
        from_phase: OrchestrationPhase,
        to_phase: OrchestrationPhase,
    ) -> int:
        active_proposal_count = self._active_proposal_count()
        if from_phase == to_phase:
            return active_proposal_count
        if self._active_phase(from_phase) and not self._active_phase(to_phase):
            return active_proposal_count - len(plan.proposals)
        if not self._active_phase(from_phase) and self._active_phase(to_phase):
            return active_proposal_count + len(plan.proposals)
        return active_proposal_count

    def _phase_plan_count_after_transition(
        self,
        phase: OrchestrationPhase,
        from_phase: OrchestrationPhase,
        to_phase: OrchestrationPhase,
    ) -> int:
        phase_plan_count = self._phase_plan_count(phase)
        if from_phase == to_phase:
            return phase_plan_count
        if phase == from_phase:
            return phase_plan_count - 1
        if phase == to_phase:
            return phase_plan_count + 1
        return phase_plan_count

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
        proposal_count_before: int,
        proposal_count_after: int,
        active_proposal_count_before: int,
        active_proposal_count_after: int,
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
            proposal_count_before=proposal_count_before,
            proposal_count_after=proposal_count_after,
            active_proposal_count_before=active_proposal_count_before,
            active_proposal_count_after=active_proposal_count_after,
        )

    def _build_vote_proof(
        self,
        *,
        plan: OrchestrationPlan,
        agent_id: str,
        vote: Vote,
        decision: str,
        reason: str,
        vote_count_before: int,
        vote_count_after: int,
        approval_count_before: int,
        approval_count_after: int,
        rejection_count_before: int,
        rejection_count_after: int,
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
            vote_count_before=vote_count_before,
            vote_count_after=vote_count_after,
            approval_count_before=approval_count_before,
            approval_count_after=approval_count_after,
            rejection_count_before=rejection_count_before,
            rejection_count_after=rejection_count_after,
        )

    def _build_submission_proof(
        self,
        *,
        plan: OrchestrationPlan,
        decision: str,
        reason: str,
        from_phase: OrchestrationPhase,
        to_phase: OrchestrationPhase,
        active_plan_count_before: int,
        active_plan_count_after: int,
        active_proposal_count_before: int,
        active_proposal_count_after: int,
        from_phase_plan_count_before: int,
        from_phase_plan_count_after: int,
        to_phase_plan_count_before: int,
        to_phase_plan_count_after: int,
    ) -> VotingSubmissionProof:
        proof_index = len(plan.submission_proofs) + 1
        return VotingSubmissionProof(
            proof_id=f"{plan.plan_id}:submission:{proof_index}",
            plan_id=plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            from_phase=from_phase.value,
            to_phase=to_phase.value,
            proposal_count=len(plan.proposals),
            voter_count=self.agent_count,
            quorum_possible=self.agent_count > 0 and bool(plan.proposals),
            phase_changed=from_phase != to_phase,
            active_plan_count_before=active_plan_count_before,
            active_plan_count_after=active_plan_count_after,
            active_proposal_count_before=active_proposal_count_before,
            active_proposal_count_after=active_proposal_count_after,
            from_phase_plan_count_before=from_phase_plan_count_before,
            from_phase_plan_count_after=from_phase_plan_count_after,
            to_phase_plan_count_before=to_phase_plan_count_before,
            to_phase_plan_count_after=to_phase_plan_count_after,
        )

    def _build_execution_readiness_proof(
        self,
        *,
        plan: OrchestrationPlan,
        decision: str,
        reason: str,
        to_phase: OrchestrationPhase,
    ) -> ExecutionReadinessProof:
        from_phase = plan.phase
        active_plan_count_before = self._active_plan_count()
        active_proposal_count_before = self._active_proposal_count()
        from_phase_plan_count_before = self._phase_plan_count(from_phase)
        to_phase_plan_count_before = self._phase_plan_count(to_phase)
        proof_index = len(plan.execution_proofs) + 1
        return ExecutionReadinessProof(
            proof_id=f"{plan.plan_id}:execution:{proof_index}",
            plan_id=plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            from_phase=from_phase.value,
            to_phase=to_phase.value,
            proposal_count=len(plan.proposals),
            vote_count=len(plan.votes),
            approval_count=plan.approval_count,
            rejection_count=plan.rejection_count,
            voter_count=self.agent_count,
            quorum_met=plan.has_quorum(self.agent_count),
            phase_changed=from_phase != to_phase,
            active_plan_count_before=active_plan_count_before,
            active_plan_count_after=self._active_plan_count_after_transition(
                from_phase,
                to_phase,
            ),
            active_proposal_count_before=active_proposal_count_before,
            active_proposal_count_after=self._active_proposal_count_after_transition(
                plan,
                from_phase,
                to_phase,
            ),
            from_phase_plan_count_before=from_phase_plan_count_before,
            from_phase_plan_count_after=self._phase_plan_count_after_transition(
                from_phase,
                from_phase,
                to_phase,
            ),
            to_phase_plan_count_before=to_phase_plan_count_before,
            to_phase_plan_count_after=self._phase_plan_count_after_transition(
                to_phase,
                from_phase,
                to_phase,
            ),
        )

    def _finalize_plan(
        self,
        plan: OrchestrationPlan,
        *,
        to_phase: OrchestrationPhase,
        decision: str,
        reason: str,
    ) -> None:
        plan.finalization_proofs.append(
            self._build_finalization_proof(
                plan=plan,
                decision=decision,
                reason=reason,
                to_phase=to_phase,
            )
        )
        plan.phase = to_phase

    def _build_finalization_proof(
        self,
        *,
        plan: OrchestrationPlan,
        decision: str,
        reason: str,
        to_phase: OrchestrationPhase,
    ) -> PlanFinalizationProof:
        from_phase = plan.phase
        active_plan_count_before = self._active_plan_count()
        active_proposal_count_before = self._active_proposal_count()
        from_phase_plan_count_before = self._phase_plan_count(from_phase)
        to_phase_plan_count_before = self._phase_plan_count(to_phase)
        result_count = len(plan.results)
        successful_result_count = sum(1 for result in plan.results if result.get("success"))
        proof_index = len(plan.finalization_proofs) + 1
        return PlanFinalizationProof(
            proof_id=f"{plan.plan_id}:finalization:{proof_index}",
            plan_id=plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            from_phase=from_phase.value,
            to_phase=to_phase.value,
            proposal_count=len(plan.proposals),
            result_count=result_count,
            successful_result_count=successful_result_count,
            failed_result_count=result_count - successful_result_count,
            dispatch_count=len(plan.dispatch_proofs),
            quorum_met=plan.has_quorum(self.agent_count),
            phase_changed=from_phase != to_phase,
            active_plan_count_before=active_plan_count_before,
            active_plan_count_after=self._active_plan_count_after_transition(
                from_phase,
                to_phase,
            ),
            active_proposal_count_before=active_proposal_count_before,
            active_proposal_count_after=self._active_proposal_count_after_transition(
                plan,
                from_phase,
                to_phase,
            ),
            from_phase_plan_count_before=from_phase_plan_count_before,
            from_phase_plan_count_after=self._phase_plan_count_after_transition(
                from_phase,
                from_phase,
                to_phase,
            ),
            to_phase_plan_count_before=to_phase_plan_count_before,
            to_phase_plan_count_after=self._phase_plan_count_after_transition(
                to_phase,
                from_phase,
                to_phase,
            ),
        )

    def _build_registration_proof(
        self,
        *,
        agent_id: str,
        action: str,
        decision: str,
        reason: str,
        previous_capabilities: tuple[str, ...] | None,
        current_capabilities: tuple[str, ...] | None,
    ) -> AgentRegistryProof:
        proof_index = len(self._registration_proofs) + 1
        return AgentRegistryProof(
            proof_id=f"registry:{proof_index}",
            agent_id=agent_id,
            action=action,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            previous_registered=previous_capabilities is not None,
            current_registered=current_capabilities is not None,
            previous_capability_count=(
                0 if previous_capabilities is None else len(previous_capabilities)
            ),
            current_capability_count=(
                0 if current_capabilities is None else len(current_capabilities)
            ),
            manifest_gated=self.manifest_gated,
            admitted_capability_count=(
                0 if self._admitted_capabilities is None else len(self._admitted_capabilities)
            ),
            registered_agent_count=self.agent_count,
            total_plan_count=self._total_plans,
            active_plan_count=self._active_plan_count(),
            active_proposal_count=self._active_proposal_count(),
        )

    def _build_plan_creation_proof(
        self,
        *,
        plan_id: str,
        initiator_id: str,
        decision: str,
        reason: str,
        plan_phase: str,
        total_plan_count_before: int,
        total_plan_count_after: int,
        active_plan_count_before: int,
        active_plan_count_after: int,
        active_proposal_count_before: int,
        active_proposal_count_after: int,
    ) -> PlanCreationProof:
        proof_index = len(self._plan_creation_proofs) + 1
        return PlanCreationProof(
            proof_id=f"plan-create:{proof_index}",
            plan_id=plan_id,
            initiator_id=initiator_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            plan_phase=plan_phase,
            initiator_registered=initiator_id in self._capabilities,
            registered_agent_count=self.agent_count,
            manifest_gated=self.manifest_gated,
            admitted_capability_count=(
                0 if self._admitted_capabilities is None else len(self._admitted_capabilities)
            ),
            total_plan_count_before=total_plan_count_before,
            total_plan_count_after=total_plan_count_after,
            active_plan_count_before=active_plan_count_before,
            active_plan_count_after=active_plan_count_after,
            active_proposal_count_before=active_proposal_count_before,
            active_proposal_count_after=active_proposal_count_after,
        )

    def _build_capability_policy_proof(
        self,
        *,
        previous_admitted_capabilities: frozenset[str] | None,
        current_admitted_capabilities: frozenset[str] | None,
    ) -> CapabilityPolicyProof:
        previous_set = set(previous_admitted_capabilities or ())
        current_set = set(current_admitted_capabilities or ())
        if previous_admitted_capabilities == current_admitted_capabilities:
            decision = "unchanged"
            reason = "capability policy unchanged"
        elif previous_admitted_capabilities is None:
            decision = "gated"
            reason = "capability policy gated"
        elif current_admitted_capabilities is None:
            decision = "ungated"
            reason = "capability policy ungated"
        else:
            decision = "updated"
            reason = "capability policy updated"
        proof_index = len(self._capability_policy_proofs) + 1
        return CapabilityPolicyProof(
            proof_id=f"capability-policy:{proof_index}",
            action="set_admitted_capabilities",
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            previous_manifest_gated=previous_admitted_capabilities is not None,
            current_manifest_gated=current_admitted_capabilities is not None,
            previous_admitted_capability_count=len(previous_set),
            current_admitted_capability_count=len(current_set),
            added_capability_count=len(current_set - previous_set),
            removed_capability_count=len(previous_set - current_set),
            registered_agent_count=self.agent_count,
            total_plan_count=self._total_plans,
            active_plan_count=self._active_plan_count(),
            active_proposal_count=self._active_proposal_count(),
        )

    def _build_consensus_proof(
        self,
        *,
        plan: OrchestrationPlan | None,
        decision: str,
        reason: str,
    ) -> ConsensusObservationProof:
        consensus_proof_count_before = len(self._consensus_proofs)
        proof_index = consensus_proof_count_before + 1
        quorum_met = bool(plan is not None and plan.has_quorum(self.agent_count))
        return ConsensusObservationProof(
            proof_id=f"consensus:{proof_index}",
            plan_id="" if plan is None else plan.plan_id,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            plan_phase="" if plan is None else plan.phase.value,
            plan_available=plan is not None,
            proposal_count=0 if plan is None else len(plan.proposals),
            vote_count=0 if plan is None else len(plan.votes),
            approval_count=0 if plan is None else plan.approval_count,
            rejection_count=0 if plan is None else plan.rejection_count,
            registered_agent_count=self.agent_count,
            quorum_threshold=self._quorum_threshold(),
            total_plan_count=self._total_plans,
            active_plan_count=self._active_plan_count(),
            active_proposal_count=self._active_proposal_count(),
            consensus_proof_count_before=consensus_proof_count_before,
            consensus_proof_count_after=consensus_proof_count_before + 1,
            quorum_met=quorum_met,
        )

    def _build_capability_discovery_proof(
        self,
        *,
        required: tuple[str, ...],
        matched_agent_count: int,
        decision: str,
        reason: str,
        manifest_admitted: bool,
    ) -> CapabilityDiscoveryProof:
        capability_discovery_proof_count_before = len(self._capability_discovery_proofs)
        proof_index = capability_discovery_proof_count_before + 1
        return CapabilityDiscoveryProof(
            proof_id=f"capability-discovery:{proof_index}",
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            required_capability_count=len(required),
            registered_agent_count=self.agent_count,
            matched_agent_count=matched_agent_count,
            manifest_gated=self.manifest_gated,
            manifest_admitted=manifest_admitted,
            total_plan_count=self._total_plans,
            active_plan_count=self._active_plan_count(),
            active_proposal_count=self._active_proposal_count(),
            capability_discovery_proof_count_before=(
                capability_discovery_proof_count_before
            ),
            capability_discovery_proof_count_after=(
                capability_discovery_proof_count_before + 1
            ),
        )

    def _record_plan_lookup(
        self,
        *,
        action: str,
        plan: OrchestrationPlan | None,
        decision: str,
        reason: str,
    ) -> None:
        self._plan_lookup_proofs.append(
            self._build_plan_lookup_proof(
                action=action,
                plan=plan,
                decision=decision,
                reason=reason,
            )
        )

    def _build_plan_lookup_proof(
        self,
        *,
        action: str,
        plan: OrchestrationPlan | None,
        decision: str,
        reason: str,
    ) -> PlanLookupProof:
        proof_index = len(self._plan_lookup_proofs) + 1
        return PlanLookupProof(
            proof_id=f"plan-lookup:{proof_index}",
            action=action,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            plan_id="" if plan is None else plan.plan_id,
            plan_available=plan is not None,
            plan_phase="" if plan is None else plan.phase.value,
            registered_agent_count=self.agent_count,
            total_plan_count=self._total_plans,
            active_plan_count=self._active_plan_count(),
        )

    def _build_manifest_binding_proof(
        self,
        *,
        action: str,
        manifest_read_model_available: bool,
        raw_capability_count: int,
    ) -> ManifestBindingProof:
        admitted_capability_count = (
            0 if self._admitted_capabilities is None else len(self._admitted_capabilities)
        )
        decision = "gated" if self.manifest_gated else "ungated"
        reason = (
            "manifest binding gated"
            if self.manifest_gated
            else "manifest binding ungated"
        )
        proof_index = len(self._manifest_binding_proofs) + 1
        return ManifestBindingProof(
            proof_id=f"manifest-binding:{proof_index}",
            action=action,
            decision=decision,
            reason=reason,
            checked_at=self._clock(),
            manifest_read_model_available=manifest_read_model_available,
            raw_capability_count=raw_capability_count,
            admitted_capability_count=admitted_capability_count,
            manifest_gated=self.manifest_gated,
            registered_agent_count=self.agent_count,
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
        suppressed_executor_key_count: int = 0,
        result_success: bool | None = None,
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
        dispatch_count_before = len(plan.dispatch_proofs)
        result_count_before = len(plan.results)
        successful_result_count_before = self._successful_result_count(plan)
        failed_result_count_before = result_count_before - successful_result_count_before
        result_count_after = result_count_before + (0 if result_success is None else 1)
        successful_result_count_after = (
            successful_result_count_before + 1
            if result_success is True
            else successful_result_count_before
        )
        failed_result_count_after = (
            failed_result_count_before + 1
            if result_success is False
            else failed_result_count_before
        )
        proof_index = dispatch_count_before + 1
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
            suppressed_executor_key_count=suppressed_executor_key_count,
            dispatch_count_before=dispatch_count_before,
            dispatch_count_after=dispatch_count_before + 1,
            result_count_before=result_count_before,
            result_count_after=result_count_after,
            successful_result_count_before=successful_result_count_before,
            successful_result_count_after=successful_result_count_after,
            failed_result_count_before=failed_result_count_before,
            failed_result_count_after=failed_result_count_after,
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
