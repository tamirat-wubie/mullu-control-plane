"""Governed swarm work fabric.

Purpose: expose S2 supervisor-led swarm coordination primitives for bounded
specialist symbolic intelligence workers.
Governance scope: identity, capability, budget, lease, proof, trace, and
approval boundaries.
Dependencies: local swarm modules.
Invariants: universal work decomposition does not imply universal authority.
"""

from .agent_registry import AgentRegistry
from .audit_store import SwarmAuditStore
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
    SwarmTaskRisk,
    TaskLease,
    WHQRGate,
)
from .lease_manager import TaskLeaseManager
from .message_bus import AgentMessageBus
from .mil import MILInstruction, MILInstructionKind, MILProgram, MILStaticVerifier, MILVerification
from .quorum import QuorumEngine
from .record import SwarmAuditRecord, invoice_result_to_audit_record
from .runtime_api import InvoiceSwarmRuntime, RuntimeEnvelope
from .fastapi_router import SwarmFastAPIAdapter, SwarmRouteSpec, create_fastapi_router
from .shared_workspace import SharedWorkspace
from .supervisor import SpecialistWorker, SupervisorAgent, SwarmRunResult
from .swarm_planner import SwarmPlan, SwarmPlanner
from .task_decomposer import TaskDecomposer
from .trace import SwarmTrace
from .verifier import VerificationResult, VerifierAgent

__all__ = [
    "AgentIdentity",
    "AgentMessageBus",
    "AgentRegistry",
    "ConflictResolver",
    "MILInstruction",
    "MILInstructionKind",
    "MILProgram",
    "MILStaticVerifier",
    "MILVerification",
    "QuorumEngine",
    "RuntimeEnvelope",
    "SharedWorkspace",
    "SpecialistWorker",
    "SupervisorAgent",
    "SwarmFastAPIAdapter",
    "SwarmRouteSpec",
    "InvoiceSwarmRuntime",
    "SwarmAuditRecord",
    "SwarmAuditStore",
    "SwarmClaim",
    "SwarmClosureCertificate",
    "SwarmClosureFactory",
    "SwarmConflict",
    "SwarmDecision",
    "SwarmDecisionVerdict",
    "SwarmGoal",
    "SwarmInvariantViolation",
    "SwarmMessage",
    "SwarmMessageType",
    "SwarmPlan",
    "SwarmPlanner",
    "SwarmReceipt",
    "SwarmRunResult",
    "SwarmTask",
    "SwarmTaskRisk",
    "SwarmTrace",
    "TaskDecomposer",
    "TaskLease",
    "TaskLeaseManager",
    "VerificationResult",
    "VerifierAgent",
    "WHQRGate",
    "create_fastapi_router",
    "invoice_result_to_audit_record",
]
