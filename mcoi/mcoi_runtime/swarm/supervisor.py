"""Supervisor runtime for S2 governed swarm work.

Purpose: coordinate specialist tasks through registry selection, leases,
structured claims, conflict checks, quorum, verification, and closure.
Governance scope: bounded authority, no peer delegation, no autonomous side
effects, receipt-backed proof.
Dependencies: swarm registry, planner, leases, workspace, conflict resolver,
quorum, verifier, trace, and closure.
Invariants: specialists only emit claims and receipts; runtime alone may close.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .agent_registry import AgentRegistry
from .closure import SwarmClosureFactory
from .conflict_resolver import ConflictResolver, SwarmConflict
from .contracts import (
    AgentIdentity,
    SwarmClaim,
    SwarmClosureCertificate,
    SwarmDecision,
    SwarmDecisionVerdict,
    SwarmGoal,
    SwarmInvariantViolation,
    SwarmMessage,
    SwarmMessageType,
    SwarmReceipt,
    SwarmTask,
    TaskLease,
)
from .lease_manager import TaskLeaseManager
from .quorum import QuorumEngine
from .shared_workspace import SharedWorkspace
from .swarm_planner import SwarmPlan, SwarmPlanner
from .trace import SwarmTrace
from .verifier import VerificationResult, VerifierAgent


class SpecialistWorker(Protocol):
    """Protocol for bounded specialist workers."""

    def run(self, *, task: SwarmTask, lease: TaskLease, identity: AgentIdentity) -> SwarmClaim:
        """Return a structured claim without performing side effects."""


@dataclass(frozen=True)
class SwarmRunResult:
    """Supervisor run result."""

    plan: SwarmPlan
    decision: SwarmDecision
    conflicts: tuple[SwarmConflict, ...]
    receipts: tuple[SwarmReceipt, ...]
    verification: VerificationResult
    closure: SwarmClosureCertificate | None


class SupervisorAgent:
    """S2 supervisor-led governed swarm coordinator."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        workers: dict[str, SpecialistWorker],
        planner: SwarmPlanner | None = None,
        lease_manager: TaskLeaseManager | None = None,
        workspace: SharedWorkspace | None = None,
        conflict_resolver: ConflictResolver | None = None,
        quorum_engine: QuorumEngine | None = None,
        verifier: VerifierAgent | None = None,
        closure_factory: SwarmClosureFactory | None = None,
        trace: SwarmTrace | None = None,
        supervisor_agent_id: str = "supervisor_agent_v1",
    ) -> None:
        self.registry = registry
        self.workers = workers
        self.planner = planner or SwarmPlanner()
        self.lease_manager = lease_manager or TaskLeaseManager()
        self.workspace = workspace or SharedWorkspace()
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.quorum_engine = quorum_engine or QuorumEngine()
        self.verifier = verifier or VerifierAgent()
        self.closure_factory = closure_factory or SwarmClosureFactory()
        self.trace = trace or SwarmTrace()
        self.supervisor_agent_id = supervisor_agent_id

    def run_goal(self, goal: SwarmGoal) -> SwarmRunResult:
        """Run a goal through the S2 governed swarm fabric."""

        plan = self.planner.decompose(goal)
        self.trace.append(
            goal_id=goal.goal_id,
            event_type="goal_decomposed",
            actor_id=self.supervisor_agent_id,
            caused_by=goal.goal_id,
            summary=f"planned {len(plan.tasks)} bounded tasks",
        )
        receipts: list[SwarmReceipt] = []
        for task in plan.tasks:
            identity = self.registry.select(task)
            worker = self._worker_for(identity)
            lease = self.lease_manager.issue(identity, task, max_cost_usd=Decimal("0.00"))
            self.trace.append(
                goal_id=goal.goal_id,
                event_type="lease_issued",
                actor_id=self.supervisor_agent_id,
                caused_by=task.task_id,
                summary=f"issued {lease.lease_id} to {identity.agent_id}",
            )
            claim = worker.run(task=task, lease=lease, identity=identity)
            message = SwarmMessage(
                message_id=f"msg_{len(self.workspace.messages_for_goal(goal.goal_id)) + 1:06d}",
                goal_id=goal.goal_id,
                task_id=task.task_id,
                from_agent=identity.agent_id,
                to_agent=self.supervisor_agent_id,
                message_type=SwarmMessageType.CLAIM,
                claim=claim,
                evidence_refs=(lease.lease_id,),
                confidence=Decimal("1.0"),
            )
            self.workspace.append_message(message)
            receipt = SwarmReceipt(
                receipt_id=f"receipt_{len(receipts) + 1:06d}",
                goal_id=goal.goal_id,
                task_id=task.task_id,
                agent_id=identity.agent_id,
                lease_id=lease.lease_id,
                outcome=claim.gate.value,
                evidence_refs=(message.message_id,),
            )
            self.workspace.append_receipt(receipt)
            receipts.append(receipt)
            self.trace.append(
                goal_id=goal.goal_id,
                event_type="claim_received",
                actor_id=identity.agent_id,
                caused_by=lease.lease_id,
                summary=f"{claim.role}:{claim.target}:{claim.gate.value}",
            )
        messages = self.workspace.messages_for_goal(goal.goal_id)
        conflicts = self.conflict_resolver.detect(messages)
        if conflicts:
            decision = SwarmDecision(
                decision_id=f"{goal.goal_id}_decision",
                goal_id=goal.goal_id,
                verdict=SwarmDecisionVerdict.ESCALATE,
                reason="conflict_detected",
                message_ids=tuple(message.message_id for message in messages),
                requires_human_approval=True,
            )
            verification = VerificationResult(False, "conflict_requires_review")
            return SwarmRunResult(plan, decision, conflicts, tuple(receipts), verification, None)
        decision = self.quorum_engine.decide(goal.goal_id, messages)
        traces = self.trace.for_goal(goal.goal_id)
        verification = self.verifier.verify(
            tasks=plan.tasks,
            decision=decision,
            receipts=tuple(receipts),
            traces=traces,
        )
        closure = None
        if verification.passed:
            closure = self.closure_factory.close(
                decision=decision,
                verification=verification,
                receipts=tuple(receipts),
                traces=traces,
            )
        return SwarmRunResult(plan, decision, conflicts, tuple(receipts), verification, closure)

    def _worker_for(self, identity: AgentIdentity) -> SpecialistWorker:
        """Return a worker implementation for an identity."""

        try:
            return self.workers[identity.agent_id]
        except KeyError as exc:
            raise SwarmInvariantViolation(f"missing worker for agent_id: {identity.agent_id}") from exc
