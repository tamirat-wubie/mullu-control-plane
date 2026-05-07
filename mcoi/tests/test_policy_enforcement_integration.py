"""Tests for PolicyEnforcementIntegration bridge.

Covers constructor validation, all six enforce_* methods (allowed / denied /
step-up paths), memory-mesh and graph attachment, event emission, revoked and
suspended session handling, constraint-based denial, and the end-to-end golden
path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.governance.policy.enforcement import PolicyEnforcementEngine
from mcoi_runtime.core.policy_enforcement_integration import PolicyEnforcementIntegration
from mcoi_runtime.contracts.policy_enforcement import (
    SessionStatus,
    SessionKind,
    PrivilegeLevel,
    EnforcementDecision,
    RevocationReason,
    StepUpStatus,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ── Shared keys expected in every enforce_* return dict ──────────────
ENFORCE_KEYS = {"session_id", "resource_type", "action", "decision", "reason"}

GRAPH_KEYS = {
    "scope_ref_id",
    "total_sessions",
    "active_sessions",
    "total_constraints",
    "total_step_ups",
    "total_enforcements",
    "total_revocations",
    "total_bindings",
    "total_audits",
}


# ── Fixture ──────────────────────────────────────────────────────────
@pytest.fixture()
def env():
    """Create es, mm, eng, bridge and open a STANDARD session 's1' for 'alice'."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = PolicyEnforcementEngine(es)
    bridge = PolicyEnforcementIntegration(eng, es, mm)
    eng.open_session("s1", "alice")
    return es, mm, eng, bridge


# =====================================================================
# Constructor validation  (3 tests)
# =====================================================================


class TestConstructorValidation:
    def test_reject_invalid_enforcement_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementIntegration("not-an-engine", es, mm)

    def test_reject_invalid_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = PolicyEnforcementEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementIntegration(eng, "not-an-es", mm)

    def test_reject_invalid_memory_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = PolicyEnforcementEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementIntegration(eng, es, "not-a-mm")


# =====================================================================
# enforce_campaign_action  (2 tests)
# =====================================================================


class TestCampaignAction:
    def test_allowed(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_campaign_action("s1", "create")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "campaign"

    def test_denied_unknown_session(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_campaign_action("no-such-session", "create")
        assert result["decision"] == "denied"


# =====================================================================
# enforce_connector_action  (2 tests)
# =====================================================================


class TestConnectorAction:
    def test_allowed(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_connector_action("s1", "connect")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "connector"

    def test_denied_unknown_session(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_connector_action("ghost", "connect")
        assert result["decision"] == "denied"


# =====================================================================
# enforce_budget_action  (2 tests)
# =====================================================================


class TestBudgetAction:
    def test_step_up_required_at_standard(self, env):
        _es, _mm, _eng, bridge = env
        # s1 has STANDARD privilege; budget default requires ELEVATED
        result = bridge.enforce_budget_action("s1")
        assert result["decision"] == "step_up_required"

    def test_allowed_at_elevated(self, env):
        _es, _mm, eng, bridge = env
        # Elevate s1 via step-up workflow
        eng.request_step_up("su1", "s1", "alice", requested_level=PrivilegeLevel.ELEVATED)
        eng.approve_step_up("d1", "su1", "admin")
        result = bridge.enforce_budget_action("s1")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "budget"


# =====================================================================
# enforce_environment_promotion  (2 tests)
# =====================================================================


class TestEnvironmentPromotion:
    def test_step_up_required_at_standard(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_environment_promotion("s1")
        assert result["decision"] == "step_up_required"

    def test_allowed_at_elevated(self, env):
        _es, _mm, eng, bridge = env
        eng.request_step_up("su2", "s1", "alice", requested_level=PrivilegeLevel.ELEVATED)
        eng.approve_step_up("d2", "su2", "admin")
        result = bridge.enforce_environment_promotion("s1")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "environment"
        assert result["action"] == "promote"


# =====================================================================
# enforce_change_execution  (2 tests)
# =====================================================================


class TestChangeExecution:
    def test_allowed(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_change_execution("s1", "workflow", "deploy")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "workflow"

    def test_denied_unknown_session(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_change_execution("nope", "workflow", "deploy")
        assert result["decision"] == "denied"


# =====================================================================
# enforce_executive_intervention  (2 tests)
# =====================================================================


class TestExecutiveIntervention:
    def test_step_up_required_at_standard(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_executive_intervention("s1")
        assert result["decision"] == "step_up_required"

    def test_allowed_at_admin(self, env):
        _es, _mm, eng, bridge = env
        eng.request_step_up("su3", "s1", "alice", requested_level=PrivilegeLevel.ADMIN)
        eng.approve_step_up("d3", "su3", "admin")
        result = bridge.enforce_executive_intervention("s1")
        assert result["decision"] == "allowed"
        assert result["resource_type"] == "executive"
        assert result["action"] == "override"


# =====================================================================
# Memory mesh attachment  (1 test)
# =====================================================================


class TestMemoryMeshAttachment:
    def test_returns_memory_record_with_correct_tags(self, env):
        _es, _mm, _eng, bridge = env
        mem = bridge.attach_session_audit_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)
        assert mem.title == "Session enforcement state"
        assert "scope-1" not in mem.title
        assert mem.scope_ref_id == "scope-1"
        assert "session" in mem.tags
        assert "enforcement" in mem.tags
        assert "policy" in mem.tags


# =====================================================================
# Graph attachment  (1 test)
# =====================================================================


class TestGraphAttachment:
    def test_returns_dict_with_all_expected_keys(self, env):
        _es, _mm, _eng, bridge = env
        graph = bridge.attach_session_audit_to_graph("scope-2")
        assert isinstance(graph, dict)
        assert graph.keys() == GRAPH_KEYS
        assert graph["scope_ref_id"] == "scope-2"
        assert graph["total_sessions"] >= 1


# =====================================================================
# Events emitted count increases  (1 test)
# =====================================================================


class TestEventsEmitted:
    def test_event_count_increases(self, env):
        es, _mm, _eng, bridge = env
        before = es.event_count
        bridge.enforce_campaign_action("s1", "read")
        after = es.event_count
        assert after > before


# =====================================================================
# Return shape for each enforce method  (6 tests)
# =====================================================================


class TestReturnShape:
    def test_campaign_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_campaign_action("s1", "read")
        assert result.keys() == ENFORCE_KEYS

    def test_connector_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_connector_action("s1", "read")
        assert result.keys() == ENFORCE_KEYS

    def test_budget_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_budget_action("s1")
        assert result.keys() == ENFORCE_KEYS

    def test_environment_promotion_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_environment_promotion("s1")
        assert result.keys() == ENFORCE_KEYS

    def test_change_execution_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_change_execution("s1", "res", "act")
        assert result.keys() == ENFORCE_KEYS

    def test_executive_intervention_shape(self, env):
        _es, _mm, _eng, bridge = env
        result = bridge.enforce_executive_intervention("s1")
        assert result.keys() == ENFORCE_KEYS


# =====================================================================
# End-to-end golden path  (1 test)
# =====================================================================


class TestGoldenPath:
    def test_full_lifecycle(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = PolicyEnforcementEngine(es)
        bridge = PolicyEnforcementIntegration(eng, es, mm)

        # 1. Open session
        eng.open_session("gp1", "bob")

        # 2. Enforce all 6 types at STANDARD
        r_camp = bridge.enforce_campaign_action("gp1", "create")
        assert r_camp["decision"] == "allowed"

        r_conn = bridge.enforce_connector_action("gp1", "connect")
        assert r_conn["decision"] == "allowed"

        r_budget = bridge.enforce_budget_action("gp1")
        assert r_budget["decision"] == "step_up_required"

        r_envp = bridge.enforce_environment_promotion("gp1")
        assert r_envp["decision"] == "step_up_required"

        r_chg = bridge.enforce_change_execution("gp1", "pipeline", "run")
        assert r_chg["decision"] == "allowed"

        r_exec = bridge.enforce_executive_intervention("gp1")
        assert r_exec["decision"] == "step_up_required"

        # 3. Step-up for budget (elevate to ELEVATED)
        eng.request_step_up("su-gp", "gp1", "bob", requested_level=PrivilegeLevel.ELEVATED)
        eng.approve_step_up("d-gp", "su-gp", "admin")
        r_budget2 = bridge.enforce_budget_action("gp1")
        assert r_budget2["decision"] == "allowed"

        # 4. Revoke the session
        eng.revoke_session("gp1", RevocationReason.POLICY_VIOLATION)

        # 5. Verify all enforce methods return 'revoked' after revocation
        for method, args in [
            (bridge.enforce_campaign_action, ("gp1", "create")),
            (bridge.enforce_connector_action, ("gp1", "connect")),
            (bridge.enforce_budget_action, ("gp1",)),
            (bridge.enforce_environment_promotion, ("gp1",)),
            (bridge.enforce_change_execution, ("gp1", "pipeline", "run")),
            (bridge.enforce_executive_intervention, ("gp1",)),
        ]:
            res = method(*args)
            assert res["decision"] == "revoked", f"{method.__name__} should be revoked"

        # 6. Memory mesh attachment
        mem = bridge.attach_session_audit_to_memory_mesh("gp-scope")
        assert isinstance(mem, MemoryRecord)

        # 7. Graph attachment
        graph = bridge.attach_session_audit_to_graph("gp-scope")
        assert graph.keys() == GRAPH_KEYS
        assert graph["total_revocations"] >= 1
        assert graph["total_enforcements"] >= 6


# =====================================================================
# Revoked session returns 'revoked' for all enforce methods  (1 test)
# =====================================================================


class TestRevokedSession:
    def test_all_methods_return_revoked(self, env):
        _es, _mm, eng, bridge = env
        eng.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)

        assert bridge.enforce_campaign_action("s1", "x")["decision"] == "revoked"
        assert bridge.enforce_connector_action("s1", "x")["decision"] == "revoked"
        assert bridge.enforce_budget_action("s1")["decision"] == "revoked"
        assert bridge.enforce_environment_promotion("s1")["decision"] == "revoked"
        assert bridge.enforce_change_execution("s1", "r", "a")["decision"] == "revoked"
        assert bridge.enforce_executive_intervention("s1")["decision"] == "revoked"


# =====================================================================
# Suspended session returns 'suspended' decision  (1 test)
# =====================================================================


class TestSuspendedSession:
    def test_all_methods_return_suspended(self, env):
        _es, _mm, eng, bridge = env
        eng.suspend_session("s1")

        assert bridge.enforce_campaign_action("s1", "x")["decision"] == "suspended"
        assert bridge.enforce_connector_action("s1", "x")["decision"] == "suspended"
        assert bridge.enforce_budget_action("s1")["decision"] == "suspended"
        assert bridge.enforce_environment_promotion("s1")["decision"] == "suspended"
        assert bridge.enforce_change_execution("s1", "r", "a")["decision"] == "suspended"
        assert bridge.enforce_executive_intervention("s1")["decision"] == "suspended"


# =====================================================================
# Constraint blocks environment mismatch through bridge  (1 test)
# =====================================================================


class TestConstraintEnvironmentMismatch:
    def test_denied_when_environment_mismatches_constraint(self, env):
        _es, _mm, eng, bridge = env
        # Add constraint that locks s1 to environment "prod"
        eng.add_constraint(
            "c1", "s1",
            environment_id="prod",
        )
        # Request an action in "staging" — should be denied
        result = bridge.enforce_campaign_action(
            "s1", "create", environment_id="staging",
        )
        assert result["decision"] == "denied"
        assert "environment constraint" in result["reason"]

        # Same environment should be allowed
        result_ok = bridge.enforce_campaign_action(
            "s1", "create", environment_id="prod",
        )
        assert result_ok["decision"] == "allowed"
