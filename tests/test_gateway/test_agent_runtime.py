"""Gateway agent runtime coordination tests.

Purpose: verify multi-agent runtime authority inheritance and receipts.
Governance scope: tenant isolation, capability scope, memory scope, budget
scope, task admission, handoff closure, approval separation, and schema anchor.
Dependencies: gateway.agent_runtime and schemas/agent_runtime_snapshot.schema.json.
Invariants:
  - Child agents inherit only a subset of parent authority.
  - Agents cannot accept tasks outside their capability or budget scope.
  - Handoffs preserve tenant, capability, budget, and context evidence.
  - Agents cannot approve their own high-risk action.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.agent_runtime import (
    AgentReceiptStatus,
    AgentRuntimeCoordinator,
    AgentRuntimeIdentity,
    AgentRuntimeStatus,
    AgentTaskStatus,
    agent_runtime_snapshot_to_json_dict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "agent_runtime_snapshot.schema.json"


def test_child_agent_lease_is_parent_authority_subset() -> None:
    coordinator = _coordinator_with_supervisor()

    child, lease, receipt = coordinator.spawn_child_agent(
        parent_agent_id="agent-supervisor",
        child_agent_id="agent-finance",
        tenant_id="tenant-a",
        role="finance_agent",
        capability_scope=("payment.dispatch", "invoice.read"),
        memory_scope=("invoice",),
        budget_scope_cents=5000,
        issued_at="2026-05-05T12:00:00Z",
        expires_at="2026-05-05T13:00:00Z",
        evidence_refs=("proof://lease/request-001",),
    )

    assert child is not None
    assert lease is not None
    assert receipt.status == AgentReceiptStatus.ACCEPTED
    assert child.parent_agent_id == "agent-supervisor"
    assert set(child.capability_scope) == {"payment.dispatch", "invoice.read"}
    assert lease.budget_scope_cents == 5000
    assert child.identity_hash
    assert lease.lease_hash


def test_child_agent_cannot_exceed_parent_capability_memory_or_budget() -> None:
    coordinator = _coordinator_with_supervisor()

    child, lease, receipt = coordinator.spawn_child_agent(
        parent_agent_id="agent-supervisor",
        child_agent_id="agent-policy",
        tenant_id="tenant-a",
        role="policy_agent",
        capability_scope=("authority.grant",),
        memory_scope=("invoice",),
        budget_scope_cents=500,
        issued_at="2026-05-05T12:00:00Z",
        expires_at="2026-05-05T13:00:00Z",
        evidence_refs=("proof://lease/request-002",),
    )

    assert child is None
    assert lease is None
    assert receipt.status == AgentReceiptStatus.REJECTED
    assert receipt.reason == "child_capability_exceeds_parent"

    child, lease, receipt = coordinator.spawn_child_agent(
        parent_agent_id="agent-supervisor",
        child_agent_id="agent-overbudget",
        tenant_id="tenant-a",
        role="finance_agent",
        capability_scope=("invoice.read",),
        memory_scope=("invoice",),
        budget_scope_cents=20000,
        issued_at="2026-05-05T12:00:00Z",
        expires_at="2026-05-05T13:00:00Z",
        evidence_refs=("proof://lease/request-003",),
    )

    assert child is None
    assert lease is None
    assert receipt.status == AgentReceiptStatus.REJECTED
    assert receipt.reason == "child_budget_exceeds_parent"


def test_task_assignment_requires_capability_budget_and_high_risk_evidence() -> None:
    coordinator = _coordinator_with_supervisor()
    _spawn_finance_agent(coordinator)

    accepted, accepted_receipt = coordinator.assign_task(
        task_id="task-pay-001",
        agent_id="agent-finance",
        tenant_id="tenant-a",
        capability="payment.dispatch",
        goal_id="goal-pay-invoice",
        risk_tier="high",
        budget_cents=3000,
        evidence_refs=("approval://case-001", "invoice://001"),
    )
    rejected, rejected_receipt = coordinator.assign_task(
        task_id="task-policy-001",
        agent_id="agent-finance",
        tenant_id="tenant-a",
        capability="policy.modify",
        goal_id="goal-policy",
        risk_tier="critical",
        budget_cents=100,
    )

    assert accepted.status == AgentTaskStatus.ACCEPTED
    assert accepted_receipt.status == AgentReceiptStatus.ACCEPTED
    assert accepted.task_hash
    assert rejected.status == AgentTaskStatus.REJECTED
    assert rejected_receipt.status == AgentReceiptStatus.REJECTED
    assert rejected_receipt.reason == "capability_not_in_agent_scope"


def test_handoff_preserves_scope_and_rejects_cross_tenant_expansion() -> None:
    coordinator = _coordinator_with_supervisor()
    _spawn_finance_agent(coordinator)

    handoff, receipt = coordinator.record_handoff(
        handoff_id="handoff-001",
        from_agent_id="agent-supervisor",
        to_agent_id="agent-finance",
        tenant_id="tenant-a",
        goal_id="goal-pay-invoice",
        task_id="task-pay-001",
        capability_scope=("payment.dispatch",),
        budget_cents=4000,
        context_refs=("trace://run-001", "approval://case-001"),
        handed_off_at="2026-05-05T12:10:00Z",
    )

    assert handoff is not None
    assert receipt.status == AgentReceiptStatus.RECORDED
    assert handoff.handoff_hash
    assert handoff.capability_scope == ("payment.dispatch",)

    handoff, receipt = coordinator.record_handoff(
        handoff_id="handoff-002",
        from_agent_id="agent-supervisor",
        to_agent_id="agent-finance",
        tenant_id="tenant-b",
        goal_id="goal-pay-invoice",
        task_id="task-pay-001",
        capability_scope=("payment.dispatch",),
        budget_cents=4000,
        context_refs=("trace://run-002",),
    )

    assert handoff is None
    assert receipt.status == AgentReceiptStatus.REJECTED
    assert receipt.reason == "tenant_boundary_denied"


def test_self_approval_high_risk_is_denied() -> None:
    coordinator = _coordinator_with_supervisor()

    denied = coordinator.evaluate_approval(
        approver_agent_id="agent-supervisor",
        requester_agent_id="agent-supervisor",
        tenant_id="tenant-a",
        risk_tier="high",
        evidence_refs=("approval://attempt-001",),
    )
    accepted = coordinator.evaluate_approval(
        approver_agent_id="agent-supervisor",
        requester_agent_id="agent-finance",
        tenant_id="tenant-a",
        risk_tier="medium",
        evidence_refs=("approval://attempt-002",),
    )

    assert denied.status == AgentReceiptStatus.REJECTED
    assert denied.reason == "self_approval_forbidden"
    assert accepted.status == AgentReceiptStatus.ACCEPTED
    assert accepted.reason == "approval_authority_satisfied"


def test_agent_runtime_snapshot_schema_exposes_coordination_contract() -> None:
    coordinator = _coordinator_with_supervisor()
    _spawn_finance_agent(coordinator)
    coordinator.assign_task(
        task_id="task-pay-001",
        agent_id="agent-finance",
        tenant_id="tenant-a",
        capability="payment.dispatch",
        goal_id="goal-pay-invoice",
        risk_tier="high",
        budget_cents=3000,
        evidence_refs=("approval://case-001",),
    )
    snapshot = coordinator.snapshot(tenant_id="tenant-a")
    payload = agent_runtime_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:agent-runtime-snapshot:1"
    assert schema["$defs"]["agent_runtime_identity"]["properties"]["status"]["enum"] == [
        "active",
        "suspended",
        "revoked",
    ]
    assert len(payload["agents"]) == 2
    assert len(payload["leases"]) == 1
    assert payload["snapshot_hash"]


def _coordinator_with_supervisor() -> AgentRuntimeCoordinator:
    coordinator = AgentRuntimeCoordinator(clock=lambda: "2026-05-05T12:00:00Z")
    coordinator.register_root_agent(AgentRuntimeIdentity(
        agent_id="agent-supervisor",
        tenant_id="tenant-a",
        role="supervisor_agent",
        status=AgentRuntimeStatus.ACTIVE,
        capability_scope=("payment.dispatch", "invoice.read", "invoice.verify", "email.send"),
        memory_scope=("invoice", "vendor", "approval"),
        budget_scope_cents=10000,
        evidence_refs=("directory://agent-supervisor",),
    ))
    return coordinator


def _spawn_finance_agent(coordinator: AgentRuntimeCoordinator) -> None:
    coordinator.spawn_child_agent(
        parent_agent_id="agent-supervisor",
        child_agent_id="agent-finance",
        tenant_id="tenant-a",
        role="finance_agent",
        capability_scope=("payment.dispatch", "invoice.read"),
        memory_scope=("invoice",),
        budget_scope_cents=5000,
        issued_at="2026-05-05T12:00:00Z",
        expires_at="2026-05-05T13:00:00Z",
        evidence_refs=("proof://lease/request-001",),
    )
