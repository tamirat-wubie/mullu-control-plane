"""Tests for the governed swarm work fabric.

Purpose: verify S2 supervisor-led swarm invariants for identity, leases,
structured claims, quorum, conflicts, verification, and closure.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS checks.
Dependencies: mcoi_runtime.swarm.
Invariants: no anonymous agent, no side effects by specialists, no lease without
authority, no closure without receipts and trace.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from mcoi_runtime.swarm import (
    AgentIdentity,
    AgentRegistry,
    SupervisorAgent,
    SwarmClaim,
    SwarmDecisionVerdict,
    SwarmGoal,
    SwarmInvariantViolation,
    SwarmTask,
    SwarmTaskRisk,
    TaskDecomposer,
    TaskLease,
    TaskLeaseManager,
    WHQRGate,
)


class FixedClaimWorker:
    """Deterministic specialist worker for tests."""

    def __init__(self, claim: SwarmClaim) -> None:
        self.claim = claim
        self.calls: list[tuple[str, str]] = []

    def run(self, *, task: SwarmTask, lease: TaskLease, identity: AgentIdentity) -> SwarmClaim:
        self.calls.append((task.task_id, lease.lease_id))
        return self.claim


def _identity(agent_id: str, role: str, capabilities: tuple[str, ...]) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        tenant_id="tenant_a",
        role=role,
        allowed_capabilities=capabilities,
        forbidden_capabilities=("payment.dispatch", "approval.self_grant"),
        budget_scope="analysis_only",
        memory_scope=f"tenant_a.{role}",
        requires_supervisor=True,
    )


def _goal(*, unknown_budget: bool = False) -> SwarmGoal:
    budget_gate = "budget.check_unknown" if unknown_budget else "budget.check"
    return SwarmGoal(
        goal_id="goal_invoice_001",
        tenant_id="tenant_a",
        description="Handle vendor invoice through governed specialists",
        max_cost_usd=Decimal("1.00"),
        task_specs=(
            {
                "task_id": "task_document_extract",
                "required_role": "document_analysis",
                "required_capabilities": ("invoice.read",),
                "input_refs": ("invoice_001",),
                "expected_output": "invoice_fields",
                "risk": "low",
            },
            {
                "task_id": "task_budget_check",
                "required_role": "budget_analysis",
                "required_capabilities": (budget_gate,),
                "input_refs": ("invoice_001",),
                "expected_output": "budget_window_claim",
                "risk": "medium",
            },
        ),
    )


def test_supervisor_led_swarm_closes_with_receipts_and_proof_stamp() -> None:
    registry = AgentRegistry()
    document_identity = _identity("document_agent_v1", "document_analysis", ("invoice.read",))
    budget_identity = _identity("budget_agent_v1", "budget_analysis", ("budget.check",))
    registry.register(document_identity)
    registry.register(budget_identity)
    supervisor = SupervisorAgent(
        registry=registry,
        workers={
            "document_agent_v1": FixedClaimWorker(
                SwarmClaim("what", "invoice_fields", WHQRGate.PASS, "invoice fields extracted")
            ),
            "budget_agent_v1": FixedClaimWorker(
                SwarmClaim("which", "budget_window", WHQRGate.PASS, "budget window available")
            ),
        },
    )

    result = supervisor.run_goal(_goal())

    assert result.decision.verdict is SwarmDecisionVerdict.PASSED
    assert result.verification.passed is True
    assert result.closure is not None
    assert len(result.receipts) == 2
    assert result.closure.proof_stamp


def test_identity_rejects_anonymous_agent_and_forbidden_overlap() -> None:
    import mcoi.swarm as requested_swarm_path

    assert requested_swarm_path.AgentRegistry is AgentRegistry
    assert requested_swarm_path.WHQRGate.PASS is WHQRGate.PASS
    assert requested_swarm_path.SupervisorAgent is SupervisorAgent
    with pytest.raises(SwarmInvariantViolation, match="agent_id"):
        AgentIdentity(agent_id="", tenant_id="tenant_a", role="risk", allowed_capabilities=("risk.classify",))
    with pytest.raises(SwarmInvariantViolation, match="both allowed and forbidden"):
        AgentIdentity(
            agent_id="risk_agent_v1",
            tenant_id="tenant_a",
            role="risk",
            allowed_capabilities=("risk.classify",),
            forbidden_capabilities=("risk.classify",),
        )


def test_lease_requires_agent_authority_and_denies_side_effects() -> None:
    lease_manager = TaskLeaseManager()
    agent = _identity("finance_agent_v1", "finance_analysis", ("ledger.query",))
    task = SwarmTask(
        task_id="task_duplicate_check",
        goal_id="goal_invoice_001",
        tenant_id="tenant_a",
        required_role="finance_analysis",
        required_capabilities=("ledger.query",),
        input_refs=("invoice_001",),
        expected_output="duplicate_claim",
    )

    lease = lease_manager.issue(agent, task, max_cost_usd=Decimal("0.25"))

    assert lease.agent_id == "finance_agent_v1"
    assert lease.allowed_actions == ("ledger.query",)
    assert lease.side_effects_allowed is False
    assert lease.max_cost_usd == Decimal("0.25")
    with pytest.raises(SwarmInvariantViolation, match="lacks required"):
        lease_manager.issue(agent, SwarmTask(**{**task.__dict__, "required_capabilities": ("payment.dispatch",)}))


def test_task_decomposition_rejects_agent_side_effect_authority() -> None:
    goal = SwarmGoal(
        goal_id="goal_bad_001",
        tenant_id="tenant_a",
        description="Bad side-effect grant",
        task_specs=(
            {
                "task_id": "task_payment_dispatch",
                "required_role": "payment_review",
                "required_capabilities": ("payment.review",),
                "input_refs": ("invoice_001",),
                "expected_output": "payment_receipt",
                "side_effects_allowed": True,
            },
        ),
    )
    registry = AgentRegistry()
    registry.register(_identity("payment_agent_v1", "payment_review", ("payment.review",)))
    supervisor = SupervisorAgent(
        registry=registry,
        workers={
            "payment_agent_v1": FixedClaimWorker(
                SwarmClaim("how", "payment_dispatch", WHQRGate.PASS, "should never run")
            )
        },
    )

    with pytest.raises(SwarmInvariantViolation, match="cannot grant side effects"):
        supervisor.run_goal(goal)


def test_task_decomposition_rejects_loose_spec_field_types() -> None:
    decomposer = TaskDecomposer()
    base_spec = {
        "task_id": "task_document_extract",
        "required_role": "document_analysis",
        "required_capabilities": ("invoice.read",),
        "input_refs": ("invoice_001",),
        "expected_output": "invoice_fields",
    }

    for field_name, invalid_value, expected_reason in (
        ("task_id", 101, "task_id must be a string"),
        ("task_id", "   ", "task_id must be a non-empty string"),
        ("required_role", "   ", "required_role must be a non-empty string"),
        ("required_capabilities", "invoice.read", "required_capabilities must be a sequence of strings"),
        ("required_capabilities", ("",), "required_capabilities\\[0\\] must be a non-empty string"),
        ("input_refs", ("invoice_001", 9), "input_refs\\[1\\] must be a string"),
        ("input_refs", ("invoice_001", "   "), "input_refs\\[1\\] must be a non-empty string"),
        ("expected_output", "", "expected_output must be a non-empty string"),
        ("deadline", "   ", "deadline must be a non-empty string"),
        ("requires_receipt", "false", "requires_receipt must be a boolean"),
    ):
        goal = SwarmGoal(
            goal_id=f"goal_bad_{field_name}",
            tenant_id="tenant_a",
            description="Malformed task spec",
            task_specs=({**base_spec, field_name: invalid_value},),
        )

        with pytest.raises(SwarmInvariantViolation, match=expected_reason):
            decomposer.decompose(goal)


def test_swarm_goal_rejects_malformed_task_spec_shape() -> None:
    base_spec = {
        "required_role": "document_analysis",
        "expected_output": "invoice_fields",
    }

    with pytest.raises(SwarmInvariantViolation, match="task_specs must be a tuple of task spec mappings"):
        SwarmGoal(
            goal_id="goal_list_specs",
            tenant_id="tenant_a",
            description="Malformed task spec container",
            task_specs=[base_spec],
        )

    with pytest.raises(SwarmInvariantViolation, match="task_specs\\[0\\] must be a mapping"):
        SwarmGoal(
            goal_id="goal_string_spec",
            tenant_id="tenant_a",
            description="Malformed task spec item",
            task_specs=("not_a_mapping",),
        )

    with pytest.raises(SwarmInvariantViolation, match="task_specs\\[0\\] must be a mapping"):
        SwarmGoal(
            goal_id="goal_sequence_spec",
            tenant_id="tenant_a",
            description="Malformed task spec item",
            task_specs=(("required_role", "document_analysis"),),
        )


def test_task_decomposition_rejects_unsupported_fields_and_invalid_risk() -> None:
    decomposer = TaskDecomposer()
    base_spec = {
        "task_id": "task_document_extract",
        "required_role": "document_analysis",
        "required_capabilities": ("invoice.read",),
        "input_refs": ("invoice_001",),
        "expected_output": "invoice_fields",
    }
    unsupported_goal = SwarmGoal(
        goal_id="goal_unsupported_spec",
        tenant_id="tenant_a",
        description="Unsupported task spec",
        task_specs=({**base_spec, "approval_override": "manager"},),
    )
    invalid_risk_goal = SwarmGoal(
        goal_id="goal_invalid_risk",
        tenant_id="tenant_a",
        description="Invalid risk spec",
        task_specs=({**base_spec, "risk": "critical"},),
    )
    enum_risk_goal = SwarmGoal(
        goal_id="goal_enum_risk",
        tenant_id="tenant_a",
        description="Enum risk spec",
        task_specs=({**base_spec, "risk": SwarmTaskRisk.MEDIUM},),
    )

    with pytest.raises(SwarmInvariantViolation, match="unsupported task spec field: approval_override"):
        decomposer.decompose(unsupported_goal)
    with pytest.raises(SwarmInvariantViolation, match="risk must be one of"):
        decomposer.decompose(invalid_risk_goal)
    tasks = decomposer.decompose(enum_risk_goal)
    assert len(tasks) == 1
    assert tasks[0].task_id == "task_document_extract"
    assert tasks[0].risk is SwarmTaskRisk.MEDIUM


def test_conflicting_claims_escalate_without_closure() -> None:
    registry = AgentRegistry()
    registry.register(_identity("vendor_agent_v1", "vendor_analysis", ("vendor.verify",)))
    registry.register(_identity("risk_agent_v1", "risk_analysis", ("risk.classify",)))
    supervisor = SupervisorAgent(
        registry=registry,
        workers={
            "vendor_agent_v1": FixedClaimWorker(
                SwarmClaim("who", "vendor_owner", WHQRGate.PASS, "vendor profile verified")
            ),
            "risk_agent_v1": FixedClaimWorker(
                SwarmClaim("who", "vendor_owner", WHQRGate.FAIL, "owner evidence conflicts")
            ),
        },
    )
    goal = SwarmGoal(
        goal_id="goal_vendor_001",
        tenant_id="tenant_a",
        description="Verify vendor with critique",
        task_specs=(
            {
                "task_id": "task_vendor_verify",
                "required_role": "vendor_analysis",
                "required_capabilities": ("vendor.verify",),
                "input_refs": ("invoice_001",),
                "expected_output": "vendor_claim",
            },
            {
                "task_id": "task_risk_check",
                "required_role": "risk_analysis",
                "required_capabilities": ("risk.classify",),
                "input_refs": ("invoice_001",),
                "expected_output": "risk_claim",
            },
        ),
    )

    result = supervisor.run_goal(goal)

    assert result.decision.verdict is SwarmDecisionVerdict.ESCALATE
    assert result.decision.requires_human_approval is True
    assert len(result.conflicts) == 1
    assert result.closure is None
    assert result.verification.reason == "conflict_requires_review"


def test_unknown_claim_escalates_without_terminal_closure() -> None:
    registry = AgentRegistry()
    registry.register(_identity("document_agent_v1", "document_analysis", ("invoice.read",)))
    registry.register(_identity("budget_agent_v1", "budget_analysis", ("budget.check_unknown",)))
    supervisor = SupervisorAgent(
        registry=registry,
        workers={
            "document_agent_v1": FixedClaimWorker(
                SwarmClaim("what", "invoice_fields", WHQRGate.PASS, "invoice fields extracted")
            ),
            "budget_agent_v1": FixedClaimWorker(
                SwarmClaim("which", "budget_window", WHQRGate.BUDGET_UNKNOWN, "budget source unavailable")
            ),
        },
    )

    result = supervisor.run_goal(_goal(unknown_budget=True))

    assert result.decision.verdict is SwarmDecisionVerdict.ESCALATE
    assert result.decision.reason == "unknown_claim_present"
    assert result.verification.passed is False
    assert result.closure is None
    assert len(result.receipts) == 2
