"""Gateway user-owned agent identity tests.

Purpose: verify persistent agent identities bind owners, tenants, capabilities,
memory scope, approval scope, delegation scope, budgets, evidence, and
reputation without bypassing central governance.
Governance scope: accountable identity, tenant isolation, no self-approval,
policy mutation blocking, lease-bound delegation, budget enforcement, and
schema compatibility.
Dependencies: gateway.agent_identity and schemas/agent_identity.schema.json.
Invariants:
  - Agent identities cannot approve themselves or mutate policy.
  - Allowed and forbidden capability scopes remain disjoint.
  - Memory, delegation, and budget gates deny before execution.
  - Reputation updates require evidence refs.
"""

from __future__ import annotations

from pathlib import Path

from gateway.agent_identity import (
    AgentActionRequest,
    AgentApprovalScope,
    AgentBudget,
    AgentDelegationScope,
    AgentIdentity,
    AgentIdentityRegistry,
    AgentMemoryScope,
    AgentOutcome,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "agent_identity.schema.json"


def test_agent_identity_registers_schema_valid_accountable_record() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    identity = registry.register(_identity())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), identity.to_json_dict())

    assert errors == []
    assert identity.identity_hash
    assert identity.metadata["identity_is_accountable"] is True
    assert identity.metadata["agent_cannot_approve_self"] is True
    assert "policy.modify" in identity.forbidden_capabilities
    assert registry.read_model()["agent_count"] == 1


def test_agent_identity_denies_self_approval_and_policy_mutation() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    registry.register(_identity(allowed_capabilities=("invoice.read", "approval.grant")))

    self_approval = registry.evaluate(
        _request(
            capability="approval.grant",
            operation="grant_approval",
            approval_target_agent_id="agent-finance-1",
        ),
    )
    try:
        _identity(allowed_capabilities=("policy.modify",))
    except ValueError as exc:
        policy_error = str(exc)
    else:
        policy_error = ""

    assert self_approval.allowed is False
    assert self_approval.reason == "self_approval_forbidden"
    assert self_approval.metadata["decision_is_not_execution"] is True
    assert policy_error == "policy_mutation_forbidden"


def test_agent_identity_enforces_memory_and_budget_scope() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    registry.register(
        _identity(
            budget=AgentBudget(daily_action_limit=1, daily_cost_limit=0.25, per_action_cost_limit=0.25),
        ),
    )

    memory_denied = registry.evaluate(
        _request(
            request_id="agent-request-1",
            memory_class="policy_memory",
            memory_use="execution",
        ),
    )
    allowed = registry.evaluate(
        _request(
            request_id="agent-request-2",
            cost_estimate=0.10,
            memory_class="semantic_fact_memory",
            memory_use="planning",
        ),
    )
    budget_denied = registry.evaluate(_request(request_id="agent-request-3", cost_estimate=0.10))

    assert allowed.allowed is True
    assert budget_denied.allowed is False
    assert budget_denied.reason == "daily_action_budget_exhausted"
    assert memory_denied.allowed is False
    assert memory_denied.reason == "memory_class_not_allowed_for_execution"


def test_agent_identity_delegation_requires_lease_scope() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    registry.register(_identity())

    allowed = registry.evaluate(
        _request(
            capability="worker.dispatch",
            operation="delegate",
            target_worker_capability="document.extract",
            delegation_depth=1,
            evidence_refs=("proof://delegation-evidence",),
            risk_tier="high",
        ),
    )
    denied = registry.evaluate(
        _request(
            request_id="agent-request-2",
            capability="worker.dispatch",
            operation="delegate",
            target_worker_capability="payment.dispatch",
            delegation_depth=1,
            evidence_refs=("proof://delegation-evidence",),
            risk_tier="high",
        ),
    )

    assert allowed.allowed is True
    assert "active_worker_lease" in allowed.required_controls
    assert "terminal_closure" in allowed.required_controls
    assert denied.allowed is False
    assert denied.reason == "worker_capability_not_allowed"


def test_agent_reputation_update_requires_evidence_and_stays_bounded() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    registry.register(_identity(reputation_score=0.99))

    updated = registry.record_outcome(_outcome(status="succeeded", risk_tier="critical"))
    try:
        AgentOutcome(
            outcome_id="agent-outcome-2",
            agent_id="agent-finance-1",
            tenant_id="tenant-a",
            command_id="cmd-2",
            status="failed",
            risk_tier="high",
            observed_at="2026-05-05T12:05:00+00:00",
            evidence_refs=(),
        )
    except ValueError as exc:
        evidence_error = str(exc)
    else:
        evidence_error = ""

    assert updated.reputation_score == 1.0
    assert updated.evidence_history[-1].evidence_type == "outcome:succeeded"
    assert updated.evidence_history[-1].command_id == "cmd-1"
    assert evidence_error == "evidence_refs_required"


def test_agent_identity_denies_unknown_execution_memory_class() -> None:
    registry = AgentIdentityRegistry(clock=lambda: "2026-05-05T12:00:00+00:00")
    registry.register(_identity())

    denied = registry.evaluate(
        _request(
            memory_class="raw_event_memory",
            memory_use="execution",
        ),
    )

    assert denied.allowed is False
    assert denied.reason == "memory_class_not_allowed_for_execution"
    assert denied.decision_id.startswith("agent-decision-")
    assert denied.decision_hash


def _identity(**overrides: object) -> AgentIdentity:
    payload = {
        "agent_id": "agent-finance-1",
        "owner_id": "user-finance-manager",
        "tenant_id": "tenant-a",
        "role": "finance_agent",
        "status": "active",
        "allowed_capabilities": (
            "invoice.read",
            "payment.propose",
            "approval.grant",
            "worker.dispatch",
        ),
        "forbidden_capabilities": ("payment.execute",),
        "budget": AgentBudget(daily_action_limit=10, daily_cost_limit=10.0, per_action_cost_limit=2.0),
        "memory_scope": AgentMemoryScope(
            planning_memory_classes=("semantic_fact_memory", "preference_memory", "risk_memory"),
            execution_memory_classes=("episodic_closure_memory", "procedural_runbook_memory"),
            forbidden_memory_classes=("contradiction_memory",),
        ),
        "approval_scope": AgentApprovalScope(
            can_request_approval=True,
            can_grant_approval=True,
            approval_roles=("finance_admin",),
            approval_limit=1000.0,
        ),
        "delegation_scope": AgentDelegationScope(
            can_delegate=True,
            allowed_worker_roles=("document_worker",),
            allowed_worker_capabilities=("document.extract",),
            max_depth=1,
        ),
        "evidence_history": (),
        "reputation_score": 0.80,
        "created_at": "2026-05-05T12:00:00+00:00",
        "updated_at": "2026-05-05T12:00:00+00:00",
    }
    payload.update(overrides)
    return AgentIdentity(**payload)


def _request(**overrides: object) -> AgentActionRequest:
    payload = {
        "request_id": "agent-request-1",
        "agent_id": "agent-finance-1",
        "tenant_id": "tenant-a",
        "capability": "invoice.read",
        "operation": "read",
        "risk_tier": "low",
        "cost_estimate": 0.0,
    }
    payload.update(overrides)
    return AgentActionRequest(**payload)


def _outcome(**overrides: object) -> AgentOutcome:
    payload = {
        "outcome_id": "agent-outcome-1",
        "agent_id": "agent-finance-1",
        "tenant_id": "tenant-a",
        "command_id": "cmd-1",
        "status": "succeeded",
        "risk_tier": "low",
        "observed_at": "2026-05-05T12:05:00+00:00",
        "evidence_refs": ("proof://agent-outcome-1",),
    }
    payload.update(overrides)
    return AgentOutcome(**payload)
