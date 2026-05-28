"""Governed invoice swarm workflow.

Purpose: prove the S2 swarm fabric against invoice handling with document,
vendor, finance, budget, policy, risk, and verifier specialists.
Governance scope: bounded specialist claims, approval-gated payment intent,
terminal proof, and no autonomous side effects.
Dependencies: decimal arithmetic, swarm supervisor, and minimal MIL gate.
Invariants: invoice facts are claims until quorum and MIL verification pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .agent_registry import AgentRegistry
from .contracts import AgentIdentity, SwarmClaim, SwarmClosureCertificate, SwarmGoal, SwarmTask, TaskLease, WHQRGate
from .mil import MILProgram, MILStaticVerifier, MILVerification, compile_invoice_mil
from .supervisor import SpecialistWorker, SupervisorAgent, SwarmRunResult


@dataclass(frozen=True)
class InvoiceSwarmRequest:
    """Input facts for a deterministic invoice swarm demo."""

    goal_id: str
    tenant_id: str
    invoice_ref: str
    invoice_amount_usd: Decimal
    vendor_verified: bool
    duplicate_found: bool
    budget_available: bool
    policy_requires_approval: bool
    human_approved: bool = False

    def __post_init__(self) -> None:
        if not self.goal_id or not self.goal_id.strip():
            raise ValueError("goal_id must be non-empty")
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty")
        if not self.invoice_ref or not self.invoice_ref.strip():
            raise ValueError("invoice_ref must be non-empty")
        if self.invoice_amount_usd <= Decimal("0.00"):
            raise ValueError("invoice_amount_usd must be positive")


@dataclass(frozen=True)
class InvoiceSwarmResult:
    """Invoice swarm result plus MIL verification state."""

    swarm: SwarmRunResult
    mil_program: MILProgram
    mil_verification: MILVerification
    closure: SwarmClosureCertificate | None


class InvoiceFactWorker:
    """Specialist worker that maps one invoice fact into one WHQR claim."""

    def __init__(self, claim: SwarmClaim) -> None:
        self._claim = claim

    def run(self, *, task: SwarmTask, lease: TaskLease, identity: AgentIdentity) -> SwarmClaim:
        """Return the bounded claim for the assigned task."""

        if lease.agent_id != identity.agent_id:
            raise ValueError("lease identity mismatch")
        if lease.task_id != task.task_id:
            raise ValueError("lease task mismatch")
        return self._claim


def build_invoice_goal(request: InvoiceSwarmRequest) -> SwarmGoal:
    """Compile an invoice request into fixed S2 specialist tasks."""

    return SwarmGoal(
        goal_id=request.goal_id,
        tenant_id=request.tenant_id,
        description="Governed invoice handling",
        max_cost_usd=Decimal("1.00"),
        task_specs=(
            _task_spec("task_document_extract", "document_analysis", "invoice.read", request.invoice_ref, "invoice_fields"),
            _task_spec("task_vendor_verify", "vendor_analysis", "vendor.verify", request.invoice_ref, "vendor_claim"),
            _task_spec("task_duplicate_check", "finance_analysis", "ledger.query", request.invoice_ref, "duplicate_claim"),
            _task_spec("task_budget_check", "budget_analysis", "budget.check", request.invoice_ref, "budget_claim"),
            _task_spec("task_policy_check", "policy_analysis", "policy.check", request.invoice_ref, "approval_claim"),
            _task_spec("task_risk_classify", "risk_analysis", "risk.classify", request.invoice_ref, "risk_claim"),
            _task_spec("task_invoice_verify", "verifier_analysis", "proof.verify", request.invoice_ref, "verification_claim"),
        ),
    )


def default_invoice_registry(tenant_id: str) -> AgentRegistry:
    """Return the fixed specialist registry for invoice S2 swarm work."""

    registry = AgentRegistry()
    for agent_id, role, capability in (
        ("document_agent_v1", "document_analysis", "invoice.read"),
        ("vendor_agent_v1", "vendor_analysis", "vendor.verify"),
        ("finance_agent_v1", "finance_analysis", "ledger.query"),
        ("budget_agent_v1", "budget_analysis", "budget.check"),
        ("policy_agent_v1", "policy_analysis", "policy.check"),
        ("risk_agent_v1", "risk_analysis", "risk.classify"),
        ("verifier_agent_v1", "verifier_analysis", "proof.verify"),
    ):
        registry.register(
            AgentIdentity(
                agent_id=agent_id,
                tenant_id=tenant_id,
                role=role,
                allowed_capabilities=(capability,),
                forbidden_capabilities=("payment.dispatch", "approval.self_grant", "policy.modify"),
                budget_scope="analysis_only",
                memory_scope=f"{tenant_id}.{role}",
                requires_supervisor=True,
            )
        )
    return registry


def invoice_workers(request: InvoiceSwarmRequest) -> dict[str, SpecialistWorker]:
    """Return deterministic invoice specialist workers for request facts."""

    approval_gate = WHQRGate.PASS
    approval_reason = "approval not required or already present"
    if request.policy_requires_approval and not request.human_approved:
        approval_gate = WHQRGate.UNKNOWN
        approval_reason = "manager approval required before payment intent"
    return {
        "document_agent_v1": InvoiceFactWorker(
            SwarmClaim("what", "invoice_fields", WHQRGate.PASS, "invoice reference and amount present")
        ),
        "vendor_agent_v1": InvoiceFactWorker(
            SwarmClaim(
                "who",
                "vendor_identity",
                WHQRGate.PASS if request.vendor_verified else WHQRGate.FAIL,
                "vendor profile verified" if request.vendor_verified else "vendor profile missing",
            )
        ),
        "finance_agent_v1": InvoiceFactWorker(
            SwarmClaim(
                "which",
                "duplicate_invoice",
                WHQRGate.FAIL if request.duplicate_found else WHQRGate.PASS,
                "duplicate invoice found" if request.duplicate_found else "no duplicate invoice found",
            )
        ),
        "budget_agent_v1": InvoiceFactWorker(
            SwarmClaim(
                "how_much",
                "budget_window",
                WHQRGate.PASS if request.budget_available else WHQRGate.BUDGET_UNKNOWN,
                "budget window covers invoice" if request.budget_available else "budget availability unresolved",
            )
        ),
        "policy_agent_v1": InvoiceFactWorker(
            SwarmClaim("who", "approval_authority", approval_gate, approval_reason)
        ),
        "risk_agent_v1": InvoiceFactWorker(
            SwarmClaim("under_what_conditions", "invoice_risk", WHQRGate.PASS, "risk remains within invoice lane")
        ),
        "verifier_agent_v1": InvoiceFactWorker(
            SwarmClaim("why", "invoice_payment_basis", WHQRGate.PASS, "all upstream claims are receipt-bearing")
        ),
    }


def run_invoice_swarm(request: InvoiceSwarmRequest) -> InvoiceSwarmResult:
    """Run the governed invoice workflow through swarm and MIL gates."""

    supervisor = SupervisorAgent(
        registry=default_invoice_registry(request.tenant_id),
        workers=invoice_workers(request),
    )
    swarm_result = supervisor.run_goal(build_invoice_goal(request))
    request_payment = request.human_approved and swarm_result.closure is not None
    mil_program = compile_invoice_mil(
        request.goal_id,
        request_payment=request_payment,
        human_approved=request.human_approved,
    )
    mil_verification = MILStaticVerifier().verify(
        program=mil_program,
        decision=swarm_result.decision,
        human_approved=request.human_approved,
    )
    closure = swarm_result.closure if mil_verification.passed else None
    return InvoiceSwarmResult(
        swarm=swarm_result,
        mil_program=mil_program,
        mil_verification=mil_verification,
        closure=closure,
    )


def _task_spec(task_id: str, role: str, capability: str, invoice_ref: str, expected_output: str) -> dict[str, object]:
    """Build one explicit invoice task specification."""

    return {
        "task_id": task_id,
        "required_role": role,
        "required_capabilities": (capability,),
        "input_refs": (invoice_ref,),
        "expected_output": expected_output,
        "risk": "medium",
    }
