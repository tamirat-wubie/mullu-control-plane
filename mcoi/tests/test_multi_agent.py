"""Phase 160 — Autonomous Multi-Agent Delegation Layer Tests."""
import pytest
from mcoi_runtime.pilot.multi_agent import (
    AgentRole,
    DelegationRule,
    AgentAction,
    PREDEFINED_ROLES,
    DELEGATION_RULES,
    MultiAgentOrchestrator,
)


class TestDataclasses:
    def test_agent_role_frozen(self):
        role = PREDEFINED_ROLES["planner"]
        with pytest.raises(AttributeError):
            role.name = "changed"

    def test_delegation_rule_frozen(self):
        rule = DELEGATION_RULES[0]
        with pytest.raises(AttributeError):
            rule.requires_approval = True

    def test_predefined_roles_has_6(self):
        assert len(PREDEFINED_ROLES) == 6
        assert set(PREDEFINED_ROLES.keys()) == {
            "planner", "investigator", "compliance_agent",
            "financial_agent", "operator_agent", "coordinator",
        }

    def test_delegation_rules_has_8(self):
        assert len(DELEGATION_RULES) == 8


class TestOrchestrator:
    def test_register_agent(self):
        orch = MultiAgentOrchestrator()
        role = orch.register_agent("planner")
        assert role.kind == "planner"

    def test_register_unknown_role_fails(self):
        orch = MultiAgentOrchestrator()
        with pytest.raises(ValueError, match=r"^unknown role$") as excinfo:
            orch.register_agent("nonexistent")
        assert "nonexistent" not in str(excinfo.value)

    def test_propose_action(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        action = orch.propose_action("a1", "investigator", "evidence", "collect_data")
        assert action.status == "proposed"

    def test_propose_action_bad_runtime(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        with pytest.raises(ValueError, match=r"^runtime not allowed for role$") as excinfo:
            orch.propose_action("a1", "investigator", "ledger", "collect_data")
        assert "investigator" not in str(excinfo.value)
        assert "ledger" not in str(excinfo.value)

    def test_approve_and_execute(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.propose_action("a1", "investigator", "evidence", "collect_data")
        orch.approve_action("a1", "compliance_agent")
        action = orch.execute_action("a1")
        assert action.status == "executed"

    def test_execute_without_approval_fails(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.propose_action("a1", "investigator", "evidence", "collect_data")
        with pytest.raises(ValueError, match=r"^action must be approved before execution$") as excinfo:
            orch.execute_action("a1")
        assert "a1" not in str(excinfo.value)

    def test_deny_action(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.propose_action("a1", "investigator", "evidence", "collect_data")
        action = orch.deny_action("a1", "insufficient evidence")
        assert action.status == "denied"

    def test_rollback_action(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.propose_action("a1", "investigator", "evidence", "collect_data")
        orch.approve_action("a1", "compliance_agent")
        orch.execute_action("a1")
        action = orch.rollback_action("a1")
        assert action.status == "rolled_back"

    def test_delegate_valid(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("planner")
        orch.register_agent("investigator")
        entry = orch.delegate("planner", "investigator", "research task X")
        assert entry["from_role"] == "planner"
        assert entry["to_role"] == "investigator"
        assert entry["requires_approval"] is False

    def test_delegate_no_rule_fails(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.register_agent("planner")
        with pytest.raises(ValueError, match=r"^delegation rule unavailable$") as excinfo:
            orch.delegate("investigator", "planner", "invalid task")
        assert "investigator" not in str(excinfo.value)
        assert "planner" not in str(excinfo.value)

    def test_summary_counts(self):
        orch = MultiAgentOrchestrator()
        orch.register_agent("investigator")
        orch.propose_action("a1", "investigator", "evidence", "op1")
        orch.propose_action("a2", "investigator", "analysis", "op2")
        orch.approve_action("a1", "approver")
        s = orch.summary()
        assert s["proposed"] == 1
        assert s["approved"] == 1


class TestGoldenProof:
    """Golden proof: planner delegates to investigator, investigator proposes,
    compliance approves, action executes, audit trail complete."""

    def test_full_delegation_lifecycle(self):
        orch = MultiAgentOrchestrator()

        # Register agents
        orch.register_agent("planner")
        orch.register_agent("investigator")
        orch.register_agent("compliance_agent")

        # 1. Planner delegates to investigator
        delegation = orch.delegate("planner", "investigator", "investigate anomaly #42")
        assert delegation["from_role"] == "planner"
        assert delegation["to_role"] == "investigator"

        # 2. Investigator proposes action
        action = orch.propose_action(
            "golden-a1", "investigator", "evidence", "collect_anomaly_data"
        )
        assert action.status == "proposed"

        # 3. Compliance approves
        orch.approve_action("golden-a1", "compliance_agent")
        assert action.status == "approved"
        assert action.decided_by == "compliance_agent"

        # 4. Action executes
        orch.execute_action("golden-a1")
        assert action.status == "executed"

        # 5. Audit trail complete
        trail = orch.action_audit_trail()
        assert len(trail) == 1
        assert trail[0].action_id == "golden-a1"
        assert trail[0].status == "executed"

        # Summary
        s = orch.summary()
        assert s["executed"] == 1
