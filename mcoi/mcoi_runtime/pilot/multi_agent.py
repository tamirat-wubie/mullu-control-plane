"""Phase 160 — Autonomous Multi-Agent Delegation Layer."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# 160A — Agent roles
@dataclass(frozen=True)
class AgentRole:
    role_id: str
    name: str
    kind: str  # "planner"/"investigator"/"compliance"/"financial"/"operator"/"coordinator"
    authority_level: str  # "autonomous"/"supervised"/"restricted"
    max_delegation_depth: int = 3
    allowed_runtimes: tuple[str, ...] = ()


# 160B — Delegation rules
@dataclass(frozen=True)
class DelegationRule:
    rule_id: str
    from_role: str
    to_role: str
    requires_approval: bool = False
    max_chain_length: int = 3


# 160C — Agent actions
@dataclass
class AgentAction:
    action_id: str
    agent_role: str
    target_runtime: str
    operation: str
    status: str = "proposed"  # "proposed"/"approved"/"executed"/"denied"/"rolled_back"
    evidence_ref: str = ""
    decided_by: str = ""


# 160D — Predefined roles
PREDEFINED_ROLES: dict[str, AgentRole] = {
    "planner": AgentRole(
        role_id="planner",
        name="Planning Agent",
        kind="planner",
        authority_level="autonomous",
        max_delegation_depth=3,
        allowed_runtimes=("planning", "coordination", "analysis"),
    ),
    "investigator": AgentRole(
        role_id="investigator",
        name="Investigation Agent",
        kind="investigator",
        authority_level="supervised",
        max_delegation_depth=2,
        allowed_runtimes=("evidence", "analysis", "research"),
    ),
    "compliance_agent": AgentRole(
        role_id="compliance_agent",
        name="Compliance Agent",
        kind="compliance",
        authority_level="restricted",
        max_delegation_depth=1,
        allowed_runtimes=("governance", "audit", "policy"),
    ),
    "financial_agent": AgentRole(
        role_id="financial_agent",
        name="Financial Agent",
        kind="financial",
        authority_level="restricted",
        max_delegation_depth=1,
        allowed_runtimes=("ledger", "billing", "reporting"),
    ),
    "operator_agent": AgentRole(
        role_id="operator_agent",
        name="Operator Agent",
        kind="operator",
        authority_level="supervised",
        max_delegation_depth=2,
        allowed_runtimes=("execution", "remediation", "deployment"),
    ),
    "coordinator": AgentRole(
        role_id="coordinator",
        name="Coordination Agent",
        kind="coordinator",
        authority_level="autonomous",
        max_delegation_depth=3,
        allowed_runtimes=("coordination", "planning", "routing"),
    ),
}


# 160E — Delegation rules
DELEGATION_RULES: tuple[DelegationRule, ...] = (
    DelegationRule("dr-01", from_role="planner", to_role="investigator", requires_approval=False, max_chain_length=3),
    DelegationRule("dr-02", from_role="planner", to_role="operator_agent", requires_approval=False, max_chain_length=2),
    DelegationRule("dr-03", from_role="investigator", to_role="compliance_agent", requires_approval=True, max_chain_length=2),
    DelegationRule("dr-04", from_role="coordinator", to_role="planner", requires_approval=False, max_chain_length=3),
    DelegationRule("dr-05", from_role="coordinator", to_role="financial_agent", requires_approval=True, max_chain_length=2),
    DelegationRule("dr-06", from_role="operator_agent", to_role="investigator", requires_approval=True, max_chain_length=2),
    DelegationRule("dr-07", from_role="compliance_agent", to_role="financial_agent", requires_approval=True, max_chain_length=1),
    DelegationRule("dr-08", from_role="planner", to_role="financial_agent", requires_approval=True, max_chain_length=2),
)

_DELEGATION_INDEX: dict[tuple[str, str], DelegationRule] = {
    (r.from_role, r.to_role): r for r in DELEGATION_RULES
}


# 160F — Orchestrator
class MultiAgentOrchestrator:
    """Governs multi-agent delegation with full audit trail."""

    def __init__(self) -> None:
        self._registered_agents: dict[str, AgentRole] = {}
        self._actions: dict[str, AgentAction] = {}
        self._delegation_chain: list[dict[str, str]] = []

    # --- Agent registration ---
    def register_agent(self, role_id: str) -> AgentRole:
        if role_id not in PREDEFINED_ROLES:
            raise ValueError(f"Unknown role: {role_id}")
        role = PREDEFINED_ROLES[role_id]
        self._registered_agents[role_id] = role
        return role

    # --- Action lifecycle ---
    def propose_action(
        self,
        action_id: str,
        agent_role: str,
        target_runtime: str,
        operation: str,
    ) -> AgentAction:
        if agent_role not in self._registered_agents:
            raise ValueError(f"Agent not registered: {agent_role}")
        role = self._registered_agents[agent_role]
        if target_runtime not in role.allowed_runtimes:
            raise ValueError(
                f"Runtime '{target_runtime}' not allowed for role '{agent_role}'"
            )
        action = AgentAction(
            action_id=action_id,
            agent_role=agent_role,
            target_runtime=target_runtime,
            operation=operation,
            status="proposed",
        )
        self._actions[action_id] = action
        return action

    def approve_action(self, action_id: str, approver: str) -> AgentAction:
        action = self._actions.get(action_id)
        if action is None:
            raise ValueError(f"Action not found: {action_id}")
        if action.status != "proposed":
            raise ValueError(f"Action '{action_id}' is not in proposed state")
        action.status = "approved"
        action.decided_by = approver
        return action

    def execute_action(self, action_id: str) -> AgentAction:
        action = self._actions.get(action_id)
        if action is None:
            raise ValueError(f"Action not found: {action_id}")
        if action.status != "approved":
            raise ValueError(f"Action '{action_id}' must be approved before execution")
        action.status = "executed"
        return action

    def deny_action(self, action_id: str, reason: str) -> AgentAction:
        action = self._actions.get(action_id)
        if action is None:
            raise ValueError(f"Action not found: {action_id}")
        action.status = "denied"
        action.evidence_ref = reason
        return action

    def rollback_action(self, action_id: str) -> AgentAction:
        action = self._actions.get(action_id)
        if action is None:
            raise ValueError(f"Action not found: {action_id}")
        if action.status != "executed":
            raise ValueError(f"Only executed actions can be rolled back")
        action.status = "rolled_back"
        return action

    # --- Delegation ---
    def delegate(
        self, from_role: str, to_role: str, task: str
    ) -> dict[str, Any]:
        if from_role not in self._registered_agents:
            raise ValueError(f"Source agent not registered: {from_role}")
        if to_role not in self._registered_agents:
            raise ValueError(f"Target agent not registered: {to_role}")

        rule = _DELEGATION_INDEX.get((from_role, to_role))
        if rule is None:
            raise ValueError(
                f"No delegation rule from '{from_role}' to '{to_role}'"
            )

        # Check chain depth
        current_depth = sum(
            1 for d in self._delegation_chain if d["from_role"] == from_role
        ) + 1
        if current_depth > rule.max_chain_length:
            raise ValueError(
                f"Delegation chain depth {current_depth} exceeds max {rule.max_chain_length}"
            )

        entry = {
            "from_role": from_role,
            "to_role": to_role,
            "task": task,
            "requires_approval": rule.requires_approval,
        }
        self._delegation_chain.append(entry)
        return entry

    # --- Audit ---
    def action_audit_trail(self) -> list[AgentAction]:
        return list(self._actions.values())

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for action in self._actions.values():
            counts[action.status] = counts.get(action.status, 0) + 1
        return counts
