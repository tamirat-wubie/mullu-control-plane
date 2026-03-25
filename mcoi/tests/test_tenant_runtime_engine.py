"""Purpose: comprehensive pytest tests for TenantRuntimeEngine.
Governance scope: tenant, workspace, environment isolation; boundary policies;
    resource bindings; environment promotions; isolation violation detection;
    tenant health; decisions; closure reports; event emission; state hashing.
Dependencies: mcoi_runtime contracts and core modules.
Invariants:
  - Every mutation emits at least one event.
  - All invariant violations raise RuntimeCoreInvariantError.
  - All returns are immutable contract records.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.tenant_runtime import TenantRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.tenant_runtime import (
    TenantStatus,
    WorkspaceStatus,
    EnvironmentKind,
    IsolationLevel,
    ScopeBoundaryKind,
    PromotionStatus,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def env():
    es = EventSpineEngine()
    eng = TenantRuntimeEngine(es)
    return es, eng


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    """Engine construction and initial state."""

    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            TenantRuntimeEngine("not-an-engine")

    def test_initial_counts_zero(self, env):
        _, eng = env
        assert eng.tenant_count == 0
        assert eng.workspace_count == 0
        assert eng.environment_count == 0
        assert eng.policy_count == 0
        assert eng.binding_count == 0
        assert eng.promotion_count == 0
        assert eng.violation_count == 0
        assert eng.decision_count == 0

    def test_initial_state_hash_is_string(self, env):
        _, eng = env
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ---------------------------------------------------------------------------
# Tenant registration
# ---------------------------------------------------------------------------


class TestTenantRegistration:
    """register_tenant, get_tenant, set_tenant_status."""

    def test_register_basic(self, env):
        es, eng = env
        t = eng.register_tenant("t1", "Tenant 1", isolation_level=IsolationLevel.STRICT, owner="alice")
        assert t.tenant_id == "t1"
        assert t.name == "Tenant 1"
        assert t.status == TenantStatus.ACTIVE
        assert t.isolation_level == IsolationLevel.STRICT
        assert t.owner == "alice"
        assert t.workspace_ids == ()
        assert eng.tenant_count == 1

    def test_register_emits_event(self, env):
        es, eng = env
        before = len(es.list_events())
        eng.register_tenant("t1", "T1", owner="x")
        assert len(es.list_events()) > before

    def test_register_dup_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_tenant("t1", "T1 again", owner="y")

    def test_get_tenant_returns_record(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        t = eng.get_tenant("t1")
        assert t.tenant_id == "t1"

    def test_get_unknown_tenant_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_tenant("no-such")

    def test_set_tenant_status(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        updated = eng.set_tenant_status("t1", TenantStatus.SUSPENDED)
        assert updated.status == TenantStatus.SUSPENDED
        assert len(es.list_events()) > before

    def test_set_status_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.set_tenant_status("no-such", TenantStatus.ACTIVE)

    def test_register_default_isolation(self, env):
        _, eng = env
        t = eng.register_tenant("t1", "T1", owner="x")
        assert t.isolation_level == IsolationLevel.STANDARD

    def test_register_multiple_tenants(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_tenant("t3", "T3", owner="c")
        assert eng.tenant_count == 3

    def test_set_all_statuses(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        for s in TenantStatus:
            updated = eng.set_tenant_status("t1", s)
            assert updated.status == s

    def test_created_at_populated(self, env):
        _, eng = env
        t = eng.register_tenant("t1", "T1", owner="x")
        assert t.created_at != ""


# ---------------------------------------------------------------------------
# Workspace registration
# ---------------------------------------------------------------------------


class TestWorkspaceRegistration:
    """register_workspace, get_workspace, set_workspace_status, workspaces_for_tenant."""

    def test_register_basic(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        ws = eng.register_workspace("ws1", "t1", "Workspace 1", isolation_level=IsolationLevel.STRICT)
        assert ws.workspace_id == "ws1"
        assert ws.tenant_id == "t1"
        assert ws.status == WorkspaceStatus.ACTIVE
        assert ws.isolation_level == IsolationLevel.STRICT
        assert eng.workspace_count == 1
        assert len(es.list_events()) > before

    def test_workspace_added_to_tenant(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        t = eng.get_tenant("t1")
        assert "ws1" in t.workspace_ids

    def test_dup_workspace_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_workspace("ws1", "t1", "WS1 copy")

    def test_unknown_tenant_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown tenant"):
            eng.register_workspace("ws1", "no-tenant", "WS1")

    def test_get_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        ws = eng.get_workspace("ws1")
        assert ws.workspace_id == "ws1"

    def test_get_unknown_workspace_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_workspace("no-such")

    def test_set_workspace_status(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        before = len(es.list_events())
        updated = eng.set_workspace_status("ws1", WorkspaceStatus.SUSPENDED)
        assert updated.status == WorkspaceStatus.SUSPENDED
        assert len(es.list_events()) > before

    def test_set_workspace_status_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.set_workspace_status("no-such", WorkspaceStatus.ACTIVE)

    def test_workspaces_for_tenant(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        wss = eng.workspaces_for_tenant("t1")
        assert len(wss) == 2
        ids = {w.workspace_id for w in wss}
        assert ids == {"ws1", "ws2"}

    def test_workspaces_for_tenant_empty(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        assert eng.workspaces_for_tenant("t1") == ()

    def test_workspaces_cross_tenant_isolated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        assert len(eng.workspaces_for_tenant("t1")) == 1
        assert len(eng.workspaces_for_tenant("t2")) == 1

    def test_default_workspace_isolation(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        ws = eng.register_workspace("ws1", "t1", "WS1")
        assert ws.isolation_level == IsolationLevel.STANDARD

    def test_register_many_workspaces(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        for i in range(10):
            eng.register_workspace(f"ws{i}", "t1", f"WS{i}")
        assert eng.workspace_count == 10
        t = eng.get_tenant("t1")
        assert len(t.workspace_ids) == 10


# ---------------------------------------------------------------------------
# Environment registration
# ---------------------------------------------------------------------------


class TestEnvironmentRegistration:
    """register_environment, get_environment, environments_for_workspace."""

    def test_register_basic(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        before = len(es.list_events())
        e = eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT, name="dev-1")
        assert e.environment_id == "env1"
        assert e.workspace_id == "ws1"
        assert e.kind == EnvironmentKind.DEVELOPMENT
        assert e.name == "dev-1"
        assert eng.environment_count == 1
        assert len(es.list_events()) > before

    def test_env_added_to_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        ws = eng.get_workspace("ws1")
        assert "env1" in ws.environment_ids

    def test_dup_env_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_environment("env1", "ws1", EnvironmentKind.STAGING)

    def test_unknown_workspace_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown workspace"):
            eng.register_environment("env1", "no-ws", EnvironmentKind.DEVELOPMENT)

    def test_get_environment(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.STAGING)
        e = eng.get_environment("env1")
        assert e.kind == EnvironmentKind.STAGING

    def test_get_unknown_env_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_environment("no-such")

    def test_environments_for_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("env2", "ws1", EnvironmentKind.STAGING)
        envs = eng.environments_for_workspace("ws1")
        assert len(envs) == 2

    def test_environments_for_workspace_empty(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        assert eng.environments_for_workspace("ws1") == ()

    def test_auto_name(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        e = eng.register_environment("env1", "ws1", EnvironmentKind.SANDBOX)
        assert "sandbox" in e.name.lower()

    def test_all_environment_kinds(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        for i, kind in enumerate(EnvironmentKind):
            e = eng.register_environment(f"env{i}", "ws1", kind)
            assert e.kind == kind
        assert eng.environment_count == len(EnvironmentKind)


# ---------------------------------------------------------------------------
# Boundary policies
# ---------------------------------------------------------------------------


class TestBoundaryPolicies:
    """add_boundary_policy, policies_for_tenant, enforced_policies_for_tenant."""

    def test_add_basic(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        p = eng.add_boundary_policy(
            "pol1", "t1", ScopeBoundaryKind.MEMORY,
            isolation_level=IsolationLevel.STRICT, enforced=True,
            description="Memory isolation",
        )
        assert p.policy_id == "pol1"
        assert p.tenant_id == "t1"
        assert p.boundary_kind == ScopeBoundaryKind.MEMORY
        assert p.isolation_level == IsolationLevel.STRICT
        assert p.enforced is True
        assert eng.policy_count == 1
        assert len(es.list_events()) > before

    def test_dup_policy_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.CONNECTOR)

    def test_unknown_tenant_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown tenant"):
            eng.add_boundary_policy("pol1", "no-t", ScopeBoundaryKind.MEMORY)

    def test_policies_for_tenant(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        eng.add_boundary_policy("pol2", "t1", ScopeBoundaryKind.CONNECTOR)
        pols = eng.policies_for_tenant("t1")
        assert len(pols) == 2

    def test_enforced_policies(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, enforced=True)
        eng.add_boundary_policy("pol2", "t1", ScopeBoundaryKind.CONNECTOR, enforced=False)
        enforced = eng.enforced_policies_for_tenant("t1")
        assert len(enforced) == 1
        assert enforced[0].policy_id == "pol1"

    def test_enforced_policies_filtered_by_kind(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, enforced=True)
        eng.add_boundary_policy("pol2", "t1", ScopeBoundaryKind.CONNECTOR, enforced=True)
        mem_only = eng.enforced_policies_for_tenant("t1", boundary_kind=ScopeBoundaryKind.MEMORY)
        assert len(mem_only) == 1
        assert mem_only[0].boundary_kind == ScopeBoundaryKind.MEMORY

    def test_enforced_policies_none_kind_returns_all(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, enforced=True)
        eng.add_boundary_policy("pol2", "t1", ScopeBoundaryKind.CONNECTOR, enforced=True)
        all_enforced = eng.enforced_policies_for_tenant("t1", boundary_kind=None)
        assert len(all_enforced) == 2

    def test_all_boundary_kinds(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        for i, kind in enumerate(ScopeBoundaryKind):
            eng.add_boundary_policy(f"pol{i}", "t1", kind)
        assert eng.policy_count == len(ScopeBoundaryKind)

    def test_policies_cross_tenant_isolated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        eng.add_boundary_policy("pol2", "t2", ScopeBoundaryKind.MEMORY)
        assert len(eng.policies_for_tenant("t1")) == 1
        assert len(eng.policies_for_tenant("t2")) == 1


# ---------------------------------------------------------------------------
# Workspace resource bindings
# ---------------------------------------------------------------------------


class TestWorkspaceBindings:
    """bind_workspace_resource, bindings_for_workspace, bindings_for_environment."""

    def test_bind_basic(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        before = len(es.list_events())
        b = eng.bind_workspace_resource(
            "b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN,
        )
        assert b.binding_id == "b1"
        assert b.workspace_id == "ws1"
        assert b.resource_ref_id == "res-1"
        assert b.resource_type == ScopeBoundaryKind.CAMPAIGN
        assert eng.binding_count == 1
        assert len(es.list_events()) > before

    def test_bind_with_environment(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.PRODUCTION)
        b = eng.bind_workspace_resource(
            "b1", "ws1", "res-1", ScopeBoundaryKind.CONNECTOR,
            environment_id="env1",
        )
        assert b.environment_id == "env1"

    def test_bind_added_to_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        ws = eng.get_workspace("ws1")
        assert "b1" in ws.resource_bindings

    def test_dup_binding_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.bind_workspace_resource("b1", "ws1", "res-2", ScopeBoundaryKind.CAMPAIGN)

    def test_unknown_workspace_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown workspace"):
            eng.bind_workspace_resource("b1", "no-ws", "res-1", ScopeBoundaryKind.CAMPAIGN)

    def test_unknown_environment_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown environment"):
            eng.bind_workspace_resource(
                "b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN,
                environment_id="no-env",
            )

    def test_strict_isolation_blocks_cross_workspace_same_tenant(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.add_boundary_policy(
            "pol1", "t1", ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )
        eng.bind_workspace_resource("b1", "ws1", "budget-1", ScopeBoundaryKind.BUDGET)
        with pytest.raises(RuntimeCoreInvariantError, match="Isolation violation"):
            eng.bind_workspace_resource("b2", "ws2", "budget-1", ScopeBoundaryKind.BUDGET)

    def test_standard_isolation_allows_cross_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.add_boundary_policy(
            "pol1", "t1", ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.STANDARD, enforced=True,
        )
        eng.bind_workspace_resource("b1", "ws1", "budget-1", ScopeBoundaryKind.BUDGET)
        b2 = eng.bind_workspace_resource("b2", "ws2", "budget-1", ScopeBoundaryKind.BUDGET)
        assert b2.binding_id == "b2"

    def test_unenforced_strict_policy_allows_sharing(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.add_boundary_policy(
            "pol1", "t1", ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.STRICT, enforced=False,
        )
        eng.bind_workspace_resource("b1", "ws1", "budget-1", ScopeBoundaryKind.BUDGET)
        b2 = eng.bind_workspace_resource("b2", "ws2", "budget-1", ScopeBoundaryKind.BUDGET)
        assert b2.binding_id == "b2"

    def test_bindings_for_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        eng.bind_workspace_resource("b2", "ws1", "res-2", ScopeBoundaryKind.CONNECTOR)
        bs = eng.bindings_for_workspace("ws1")
        assert len(bs) == 2

    def test_bindings_for_workspace_filtered(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        eng.bind_workspace_resource("b2", "ws1", "res-2", ScopeBoundaryKind.CONNECTOR)
        camp = eng.bindings_for_workspace("ws1", resource_type=ScopeBoundaryKind.CAMPAIGN)
        assert len(camp) == 1
        assert camp[0].resource_type == ScopeBoundaryKind.CAMPAIGN

    def test_bindings_for_environment(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.PRODUCTION)
        eng.register_environment("env2", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CONNECTOR, environment_id="env1")
        eng.bind_workspace_resource("b2", "ws1", "res-2", ScopeBoundaryKind.CONNECTOR, environment_id="env2")
        prod_binds = eng.bindings_for_environment("env1")
        assert len(prod_binds) == 1
        assert prod_binds[0].binding_id == "b1"

    def test_bindings_for_environment_empty(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        assert eng.bindings_for_environment("env1") == ()

    def test_same_resource_same_workspace_ok(self, env):
        """Binding same resource twice to same workspace with different IDs is allowed."""
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.add_boundary_policy(
            "pol1", "t1", ScopeBoundaryKind.CAMPAIGN,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        b2 = eng.bind_workspace_resource("b2", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        assert b2.binding_id == "b2"

    def test_no_policy_allows_cross_workspace(self, env):
        """Without any policy, resource sharing across workspaces is allowed."""
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.BUDGET)
        b2 = eng.bind_workspace_resource("b2", "ws2", "res-1", ScopeBoundaryKind.BUDGET)
        assert b2.binding_id == "b2"


# ---------------------------------------------------------------------------
# Environment promotion
# ---------------------------------------------------------------------------


class TestEnvironmentPromotion:
    """promote_environment with valid/invalid paths and compliance gating."""

    def _setup_envs(self, eng, kinds):
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        result = []
        for i, kind in enumerate(kinds):
            e = eng.register_environment(f"env{i}", "ws1", kind)
            result.append(e)
        return result

    def test_dev_to_staging(self, env):
        es, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.STAGING])
        before = len(es.list_events())
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True, promoted_by="alice")
        assert p.status == PromotionStatus.COMPLETED
        assert p.compliance_check_passed is True
        assert eng.promotion_count == 1
        assert len(es.list_events()) > before

    def test_dev_to_sandbox(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.SANDBOX])
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)
        assert p.status == PromotionStatus.COMPLETED

    def test_sandbox_to_staging(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.SANDBOX, EnvironmentKind.STAGING])
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)
        assert p.status == PromotionStatus.COMPLETED

    def test_staging_to_prod_with_compliance(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.STAGING, EnvironmentKind.PRODUCTION])
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True, promoted_by="admin")
        assert p.status == PromotionStatus.COMPLETED
        assert p.completed_at != ""

    def test_staging_to_prod_no_compliance_fails(self, env):
        es, eng = env
        self._setup_envs(eng, [EnvironmentKind.STAGING, EnvironmentKind.PRODUCTION])
        before = len(es.list_events())
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=False)
        assert p.status == PromotionStatus.FAILED
        assert p.compliance_check_passed is False
        assert eng.promotion_count == 1
        assert len(es.list_events()) > before

    def test_invalid_path_dev_to_prod_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.PRODUCTION])
        with pytest.raises(RuntimeCoreInvariantError, match="Invalid promotion path"):
            eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)

    def test_invalid_path_prod_to_dev_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.PRODUCTION, EnvironmentKind.DEVELOPMENT])
        with pytest.raises(RuntimeCoreInvariantError, match="Invalid promotion path"):
            eng.promote_environment("p1", "env0", "env1")

    def test_invalid_path_staging_to_dev_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.STAGING, EnvironmentKind.DEVELOPMENT])
        with pytest.raises(RuntimeCoreInvariantError, match="Invalid promotion path"):
            eng.promote_environment("p1", "env0", "env1")

    def test_invalid_path_sandbox_to_prod_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.SANDBOX, EnvironmentKind.PRODUCTION])
        with pytest.raises(RuntimeCoreInvariantError, match="Invalid promotion path"):
            eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)

    def test_invalid_path_prod_to_staging_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.PRODUCTION, EnvironmentKind.STAGING])
        with pytest.raises(RuntimeCoreInvariantError, match="Invalid promotion path"):
            eng.promote_environment("p1", "env0", "env1")

    def test_dup_promotion_raises(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.STAGING])
        eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)

    def test_unknown_source_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.STAGING)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown source"):
            eng.promote_environment("p1", "no-env", "env1")

    def test_unknown_target_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env0", "ws1", EnvironmentKind.DEVELOPMENT)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown target"):
            eng.promote_environment("p1", "env0", "no-env")

    def test_promotion_updates_target_promoted_from(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.STAGING])
        eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)
        target = eng.get_environment("env1")
        assert target.promoted_from == "env0"

    def test_failed_promotion_does_not_update_promoted_from(self, env):
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.STAGING, EnvironmentKind.PRODUCTION])
        eng.promote_environment("p1", "env0", "env1", compliance_check_passed=False)
        target = eng.get_environment("env1")
        assert target.promoted_from == ""

    def test_dev_to_staging_no_compliance_completes(self, env):
        """Non-prod promotions complete even without compliance_check_passed."""
        _, eng = env
        self._setup_envs(eng, [EnvironmentKind.DEVELOPMENT, EnvironmentKind.STAGING])
        p = eng.promote_environment("p1", "env0", "env1", compliance_check_passed=False)
        assert p.status == PromotionStatus.COMPLETED


# ---------------------------------------------------------------------------
# Isolation violation detection
# ---------------------------------------------------------------------------


class TestIsolationViolationDetection:
    """detect_isolation_violations, violations_for_tenant."""

    def test_no_violations_when_clean(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "mem-1", ScopeBoundaryKind.MEMORY)
        violations = eng.detect_isolation_violations()
        assert len(violations) == 0

    def test_cross_tenant_violation_detected(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "shared-mem", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "shared-mem", ScopeBoundaryKind.MEMORY)
        before = len(es.list_events())
        violations = eng.detect_isolation_violations()
        assert len(violations) >= 1
        assert violations[0].violating_resource_ref == "shared-mem"
        assert violations[0].escalated is True
        assert eng.violation_count >= 1
        assert len(es.list_events()) > before

    def test_violation_dedup(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "shared-mem", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "shared-mem", ScopeBoundaryKind.MEMORY)
        v1 = eng.detect_isolation_violations()
        v2 = eng.detect_isolation_violations()
        assert len(v2) == 0  # already detected, deduped

    def test_violations_for_tenant(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.CONNECTOR, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "conn-1", ScopeBoundaryKind.CONNECTOR)
        eng.bind_workspace_resource("b2", "ws2", "conn-1", ScopeBoundaryKind.CONNECTOR)
        eng.detect_isolation_violations()
        t1_viol = eng.violations_for_tenant("t1")
        assert len(t1_viol) >= 1
        assert all(v.tenant_id == "t1" for v in t1_viol)

    def test_no_violation_without_strict_policy(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STANDARD)
        eng.bind_workspace_resource("b1", "ws1", "mem-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "mem-1", ScopeBoundaryKind.MEMORY)
        violations = eng.detect_isolation_violations()
        assert len(violations) == 0

    def test_no_violation_unenforced_policy(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT, enforced=False)
        eng.bind_workspace_resource("b1", "ws1", "mem-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "mem-1", ScopeBoundaryKind.MEMORY)
        violations = eng.detect_isolation_violations()
        assert len(violations) == 0

    def test_violation_description_includes_tenants(self, env):
        _, eng = env
        eng.register_tenant("t1", "Alpha", owner="a")
        eng.register_tenant("t2", "Beta", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.GRAPH, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "graph-1", ScopeBoundaryKind.GRAPH)
        eng.bind_workspace_resource("b2", "ws2", "graph-1", ScopeBoundaryKind.GRAPH)
        viols = eng.detect_isolation_violations()
        assert len(viols) >= 1
        assert "t1" in viols[0].description
        assert "t2" in viols[0].description

    def test_empty_engine_no_violations(self, env):
        _, eng = env
        assert eng.detect_isolation_violations() == ()

    def test_multiple_resources_one_shared(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "mem-unique", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws1", "mem-shared", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b3", "ws2", "mem-shared", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b4", "ws2", "mem-only-t2", ScopeBoundaryKind.MEMORY)
        viols = eng.detect_isolation_violations()
        shared_refs = {v.violating_resource_ref for v in viols}
        assert "mem-shared" in shared_refs
        assert "mem-unique" not in shared_refs
        assert "mem-only-t2" not in shared_refs


# ---------------------------------------------------------------------------
# Tenant health
# ---------------------------------------------------------------------------


class TestTenantHealth:
    """tenant_health."""

    def test_health_empty_tenant(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        h = eng.tenant_health("t1")
        assert h.tenant_id == "t1"
        assert h.total_workspaces == 0
        assert h.active_workspaces == 0
        assert h.total_environments == 0
        assert h.total_bindings == 0
        assert h.total_violations == 0
        assert h.compliance_pct == 100.0
        assert len(es.list_events()) > before

    def test_health_with_workspaces(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.set_workspace_status("ws2", WorkspaceStatus.SUSPENDED)
        h = eng.tenant_health("t1")
        assert h.total_workspaces == 2
        assert h.active_workspaces == 1

    def test_health_counts_environments(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("env2", "ws1", EnvironmentKind.STAGING)
        h = eng.tenant_health("t1")
        assert h.total_environments == 2

    def test_health_counts_bindings(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        eng.bind_workspace_resource("b2", "ws1", "res-2", ScopeBoundaryKind.CONNECTOR)
        h = eng.tenant_health("t1")
        assert h.total_bindings == 2

    def test_health_counts_violations(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "mem-shared", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "mem-shared", ScopeBoundaryKind.MEMORY)
        eng.detect_isolation_violations()
        h = eng.tenant_health("t1")
        assert h.total_violations >= 1
        assert h.compliance_pct < 100.0

    def test_health_unknown_tenant_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.tenant_health("no-such")

    def test_health_compliance_100_no_violations(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        h = eng.tenant_health("t1")
        assert h.compliance_pct == 100.0

    def test_health_assessed_at_populated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        h = eng.tenant_health("t1")
        assert h.assessed_at != ""


# ---------------------------------------------------------------------------
# Tenant decisions
# ---------------------------------------------------------------------------


class TestTenantDecisions:
    """record_decision."""

    def test_record_basic(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        d = eng.record_decision(
            "d1", "t1", "Use STRICT isolation",
            description="Compliance requirement",
            confidence=0.95,
            decided_by="cto",
        )
        assert d.decision_id == "d1"
        assert d.tenant_id == "t1"
        assert d.title == "Use STRICT isolation"
        assert d.confidence == 0.95
        assert d.decided_by == "cto"
        assert eng.decision_count == 1
        assert len(es.list_events()) > before

    def test_dup_decision_raises(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.record_decision("d1", "t1", "Decision A", confidence=0.5)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_decision("d1", "t1", "Decision B", confidence=0.5)

    def test_unknown_tenant_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown tenant"):
            eng.record_decision("d1", "no-t", "Decision", confidence=0.5)

    def test_multiple_decisions(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        for i in range(5):
            eng.record_decision(f"d{i}", "t1", f"Decision {i}", confidence=0.1 * (i + 1))
        assert eng.decision_count == 5

    def test_decided_at_populated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        d = eng.record_decision("d1", "t1", "Dec", confidence=0.5)
        assert d.decided_at != ""


# ---------------------------------------------------------------------------
# Tenant closure
# ---------------------------------------------------------------------------


class TestTenantClosure:
    """close_tenant."""

    def test_close_empty_tenant(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        before = len(es.list_events())
        report = eng.close_tenant("rpt1", "t1")
        assert report.report_id == "rpt1"
        assert report.tenant_id == "t1"
        assert report.total_workspaces == 0
        assert report.total_environments == 0
        assert report.total_bindings == 0
        assert report.total_promotions == 0
        assert report.total_violations == 0
        assert report.total_decisions == 0
        assert report.compliance_pct == 100.0
        t = eng.get_tenant("t1")
        assert t.status == TenantStatus.ARCHIVED
        assert len(es.list_events()) > before

    def test_close_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.close_tenant("rpt1", "no-such")

    def test_close_with_data(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("env2", "ws1", EnvironmentKind.STAGING)
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        eng.promote_environment("p1", "env1", "env2", compliance_check_passed=True)
        eng.record_decision("d1", "t1", "Dec 1", confidence=0.8)
        report = eng.close_tenant("rpt1", "t1")
        assert report.total_workspaces == 1
        assert report.total_environments == 2
        assert report.total_bindings == 1
        assert report.total_promotions == 1
        assert report.total_decisions == 1

    def test_close_sets_archived(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.close_tenant("rpt1", "t1")
        assert eng.get_tenant("t1").status == TenantStatus.ARCHIVED

    def test_closed_at_populated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        report = eng.close_tenant("rpt1", "t1")
        assert report.closed_at != ""


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    """state_hash."""

    def test_hash_changes_on_mutation(self, env):
        _, eng = env
        h0 = eng.state_hash()
        eng.register_tenant("t1", "T1", owner="x")
        h1 = eng.state_hash()
        assert h0 != h1

    def test_hash_deterministic(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        assert eng.state_hash() == eng.state_hash()

    def test_hash_length_16(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        assert len(eng.state_hash()) == 64

    def test_hash_changes_on_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        h1 = eng.state_hash()
        eng.register_workspace("ws1", "t1", "WS1")
        h2 = eng.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Every mutation emits at least one event."""

    def test_register_tenant_emits(self, env):
        es, eng = env
        c0 = len(es.list_events())
        eng.register_tenant("t1", "T1", owner="x")
        assert len(es.list_events()) == c0 + 1

    def test_set_tenant_status_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.set_tenant_status("t1", TenantStatus.SUSPENDED)
        assert len(es.list_events()) == c0 + 1

    def test_register_workspace_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.register_workspace("ws1", "t1", "WS1")
        assert len(es.list_events()) == c0 + 1

    def test_set_workspace_status_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        c0 = len(es.list_events())
        eng.set_workspace_status("ws1", WorkspaceStatus.ARCHIVED)
        assert len(es.list_events()) == c0 + 1

    def test_register_environment_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        c0 = len(es.list_events())
        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        assert len(es.list_events()) == c0 + 1

    def test_add_boundary_policy_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        assert len(es.list_events()) == c0 + 1

    def test_bind_workspace_resource_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        c0 = len(es.list_events())
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        assert len(es.list_events()) == c0 + 1

    def test_promote_environment_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env0", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("env1", "ws1", EnvironmentKind.STAGING)
        c0 = len(es.list_events())
        eng.promote_environment("p1", "env0", "env1", compliance_check_passed=True)
        assert len(es.list_events()) == c0 + 1

    def test_promotion_blocked_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("env0", "ws1", EnvironmentKind.STAGING)
        eng.register_environment("env1", "ws1", EnvironmentKind.PRODUCTION)
        c0 = len(es.list_events())
        eng.promote_environment("p1", "env0", "env1", compliance_check_passed=False)
        assert len(es.list_events()) == c0 + 1

    def test_detect_violations_emits_when_found(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "mem-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "mem-1", ScopeBoundaryKind.MEMORY)
        c0 = len(es.list_events())
        eng.detect_isolation_violations()
        assert len(es.list_events()) > c0

    def test_tenant_health_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.tenant_health("t1")
        assert len(es.list_events()) == c0 + 1

    def test_record_decision_emits(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.record_decision("d1", "t1", "Title", confidence=0.5)
        assert len(es.list_events()) == c0 + 1

    def test_close_tenant_emits_multiple(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        c0 = len(es.list_events())
        eng.close_tenant("rpt1", "t1")
        # close_tenant calls tenant_health + set_tenant_status + emits own event = 3+
        assert len(es.list_events()) >= c0 + 3


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    """Property counters track state correctly."""

    def test_all_counts_grow(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        assert eng.tenant_count == 1

        eng.register_workspace("ws1", "t1", "WS1")
        assert eng.workspace_count == 1

        eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        assert eng.environment_count == 1

        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        assert eng.policy_count == 1

        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CAMPAIGN)
        assert eng.binding_count == 1

        eng.register_environment("env2", "ws1", EnvironmentKind.STAGING)
        eng.promote_environment("p1", "env1", "env2", compliance_check_passed=True)
        assert eng.promotion_count == 1

        eng.record_decision("d1", "t1", "Dec", confidence=0.5)
        assert eng.decision_count == 1

    def test_violation_count_after_detect(self, env):
        _, eng = env
        assert eng.violation_count == 0
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "mem", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "mem", ScopeBoundaryKind.MEMORY)
        eng.detect_isolation_violations()
        assert eng.violation_count >= 1


# ---------------------------------------------------------------------------
# Golden Scenario 1: Two tenants share runtime but not memory/connectors
# ---------------------------------------------------------------------------


class TestGoldenTwoTenantsShareRuntime:
    """Two tenants with STRICT memory+connector policies; unique resources each.
    No cross-tenant violations should exist."""

    def test_no_cross_tenant_violations(self, env):
        es, eng = env
        # Register two tenants
        eng.register_tenant("alpha", "Alpha Corp", isolation_level=IsolationLevel.STRICT, owner="alice")
        eng.register_tenant("beta", "Beta Inc", isolation_level=IsolationLevel.STRICT, owner="bob")

        # STRICT policies on both
        eng.add_boundary_policy("pol-a-mem", "alpha", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.add_boundary_policy("pol-a-conn", "alpha", ScopeBoundaryKind.CONNECTOR, isolation_level=IsolationLevel.STRICT)
        eng.add_boundary_policy("pol-b-mem", "beta", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.add_boundary_policy("pol-b-conn", "beta", ScopeBoundaryKind.CONNECTOR, isolation_level=IsolationLevel.STRICT)

        # Workspaces
        eng.register_workspace("ws-a", "alpha", "Alpha Main")
        eng.register_workspace("ws-b", "beta", "Beta Main")

        # Bind unique resources to each
        eng.bind_workspace_resource("b-a-mem", "ws-a", "mem-alpha-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b-a-conn", "ws-a", "conn-alpha-1", ScopeBoundaryKind.CONNECTOR)
        eng.bind_workspace_resource("b-b-mem", "ws-b", "mem-beta-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b-b-conn", "ws-b", "conn-beta-1", ScopeBoundaryKind.CONNECTOR)

        violations = eng.detect_isolation_violations()
        assert len(violations) == 0

        h_a = eng.tenant_health("alpha")
        h_b = eng.tenant_health("beta")
        assert h_a.compliance_pct == 100.0
        assert h_b.compliance_pct == 100.0
        assert len(es.list_events()) > 0


# ---------------------------------------------------------------------------
# Golden Scenario 2: Workspace budget isolated from another workspace
# ---------------------------------------------------------------------------


class TestGoldenWorkspaceBudgetIsolation:
    """STRICT budget policy blocks same budget binding to two workspaces."""

    def test_budget_isolation(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "Ops")
        eng.register_workspace("ws2", "t1", "Marketing")
        eng.add_boundary_policy(
            "pol-budget", "t1", ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.STRICT, enforced=True,
            description="Budget isolation between workspaces",
        )
        eng.bind_workspace_resource("b1", "ws1", "budget-2025-Q1", ScopeBoundaryKind.BUDGET)
        with pytest.raises(RuntimeCoreInvariantError, match="Isolation violation"):
            eng.bind_workspace_resource("b2", "ws2", "budget-2025-Q1", ScopeBoundaryKind.BUDGET)
        assert eng.binding_count == 1


# ---------------------------------------------------------------------------
# Golden Scenario 3: Prod connector not accessible from dev workspace
# ---------------------------------------------------------------------------


class TestGoldenProdConnectorNotInDev:
    """Connector bound to prod environment; dev environment has no access."""

    def test_prod_connector_isolated(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("dev", "ws1", EnvironmentKind.DEVELOPMENT, name="dev")
        eng.register_environment("prod", "ws1", EnvironmentKind.PRODUCTION, name="prod")

        # Bind connector exclusively to prod environment
        eng.bind_workspace_resource(
            "b-conn-prod", "ws1", "db-connector-prod", ScopeBoundaryKind.CONNECTOR,
            environment_id="prod",
        )

        # Verify: prod environment has the binding
        prod_bindings = eng.bindings_for_environment("prod")
        assert len(prod_bindings) == 1
        assert prod_bindings[0].resource_ref_id == "db-connector-prod"

        # Verify: dev environment has no bindings
        dev_bindings = eng.bindings_for_environment("dev")
        assert len(dev_bindings) == 0


# ---------------------------------------------------------------------------
# Golden Scenario 4: Promotion blocked by failed compliance control
# ---------------------------------------------------------------------------


class TestGoldenPromotionBlockedCompliance:
    """staging->prod without compliance_check_passed -> FAILED status."""

    def test_blocked_promotion(self, env):
        es, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("stg", "ws1", EnvironmentKind.STAGING, name="staging")
        eng.register_environment("prd", "ws1", EnvironmentKind.PRODUCTION, name="production")

        before = len(es.list_events())
        promo = eng.promote_environment(
            "promo-1", "stg", "prd",
            compliance_check_passed=False,
            promoted_by="junior-dev",
        )
        assert promo.status == PromotionStatus.FAILED
        assert promo.compliance_check_passed is False
        assert promo.promoted_by == "junior-dev"
        assert eng.promotion_count == 1

        # Target should NOT have promoted_from set
        target = eng.get_environment("prd")
        assert target.promoted_from == ""

        # Event was emitted
        assert len(es.list_events()) > before

    def test_same_promotion_succeeds_with_compliance(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("stg", "ws1", EnvironmentKind.STAGING)
        eng.register_environment("prd", "ws1", EnvironmentKind.PRODUCTION)

        promo = eng.promote_environment(
            "promo-ok", "stg", "prd",
            compliance_check_passed=True,
            promoted_by="senior-dev",
        )
        assert promo.status == PromotionStatus.COMPLETED
        target = eng.get_environment("prd")
        assert target.promoted_from == "stg"


# ---------------------------------------------------------------------------
# Golden Scenario 5: Isolation violation detected and escalated
# ---------------------------------------------------------------------------


class TestGoldenIsolationViolationEscalated:
    """Shared resource across tenants detected by detect_isolation_violations."""

    def test_violation_detected_and_escalated(self, env):
        es, eng = env
        eng.register_tenant("corp-a", "Corp A", owner="a")
        eng.register_tenant("corp-b", "Corp B", owner="b")
        eng.register_workspace("ws-a", "corp-a", "WS-A")
        eng.register_workspace("ws-b", "corp-b", "WS-B")

        # STRICT memory policy for corp-a
        eng.add_boundary_policy(
            "pol-mem-a", "corp-a", ScopeBoundaryKind.MEMORY,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )

        # Both tenants bind the SAME memory resource (cross-tenant leak)
        eng.bind_workspace_resource("b-a", "ws-a", "shared-memory-block", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b-b", "ws-b", "shared-memory-block", ScopeBoundaryKind.MEMORY)

        before_events = len(es.list_events())
        violations = eng.detect_isolation_violations()
        assert len(violations) >= 1
        assert len(es.list_events()) > before_events

        v = violations[0]
        assert v.violating_resource_ref == "shared-memory-block"
        assert v.escalated is True
        assert v.boundary_kind == ScopeBoundaryKind.MEMORY
        assert v.tenant_id == "corp-a"

        # Confirm in violations_for_tenant
        t_viol = eng.violations_for_tenant("corp-a")
        assert len(t_viol) >= 1

        # Health reflects violation
        h = eng.tenant_health("corp-a")
        assert h.total_violations >= 1
        assert h.compliance_pct < 100.0


# ---------------------------------------------------------------------------
# Golden Scenario 6: Full tenant lifecycle
# ---------------------------------------------------------------------------


class TestGoldenFullLifecycle:
    """Register -> workspaces -> environments -> bind -> promote -> health -> close."""

    def test_full_lifecycle(self, env):
        es, eng = env
        initial_events = len(es.list_events())

        # 1. Register tenant
        tenant = eng.register_tenant(
            "lifecycle-t", "Lifecycle Tenant",
            isolation_level=IsolationLevel.STRICT, owner="owner",
        )
        assert tenant.status == TenantStatus.ACTIVE

        # 2. Register workspaces
        ws1 = eng.register_workspace("lc-ws1", "lifecycle-t", "Primary")
        ws2 = eng.register_workspace("lc-ws2", "lifecycle-t", "Secondary")
        assert eng.workspace_count == 2

        # 3. Register environments
        dev = eng.register_environment("lc-dev", "lc-ws1", EnvironmentKind.DEVELOPMENT, name="dev")
        sandbox = eng.register_environment("lc-sandbox", "lc-ws1", EnvironmentKind.SANDBOX, name="sandbox")
        staging = eng.register_environment("lc-staging", "lc-ws1", EnvironmentKind.STAGING, name="staging")
        prod = eng.register_environment("lc-prod", "lc-ws1", EnvironmentKind.PRODUCTION, name="prod")
        assert eng.environment_count == 4

        # 4. Add policies
        eng.add_boundary_policy("lc-pol1", "lifecycle-t", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.add_boundary_policy("lc-pol2", "lifecycle-t", ScopeBoundaryKind.CONNECTOR, isolation_level=IsolationLevel.STRICT)

        # 5. Bind resources
        eng.bind_workspace_resource("lc-b1", "lc-ws1", "mem-1", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("lc-b2", "lc-ws1", "conn-1", ScopeBoundaryKind.CONNECTOR, environment_id="lc-prod")
        eng.bind_workspace_resource("lc-b3", "lc-ws2", "mem-2", ScopeBoundaryKind.MEMORY)
        assert eng.binding_count == 3

        # 6. Promote dev -> sandbox -> staging -> prod
        p1 = eng.promote_environment("lc-p1", "lc-dev", "lc-sandbox", compliance_check_passed=True, promoted_by="dev")
        assert p1.status == PromotionStatus.COMPLETED

        p2 = eng.promote_environment("lc-p2", "lc-sandbox", "lc-staging", compliance_check_passed=True, promoted_by="qa")
        assert p2.status == PromotionStatus.COMPLETED

        # First attempt: no compliance -> FAILED
        p3_fail = eng.promote_environment("lc-p3f", "lc-staging", "lc-prod", compliance_check_passed=False, promoted_by="junior")
        assert p3_fail.status == PromotionStatus.FAILED

        # Second attempt: with compliance -> COMPLETED
        p3 = eng.promote_environment("lc-p3", "lc-staging", "lc-prod", compliance_check_passed=True, promoted_by="senior")
        assert p3.status == PromotionStatus.COMPLETED
        assert eng.promotion_count == 4

        # 7. Record decisions
        eng.record_decision("lc-d1", "lifecycle-t", "Adopt STRICT isolation", confidence=0.9, decided_by="cto")
        assert eng.decision_count == 1

        # 8. Health check
        health = eng.tenant_health("lifecycle-t")
        assert health.total_workspaces == 2
        assert health.active_workspaces == 2
        assert health.total_environments == 4
        assert health.total_bindings == 3
        assert health.total_violations == 0
        assert health.compliance_pct == 100.0

        # 9. Close tenant
        report = eng.close_tenant("lc-rpt", "lifecycle-t")
        assert report.total_workspaces == 2
        assert report.total_environments == 4
        assert report.total_bindings == 3
        assert report.total_promotions == 4
        assert report.total_decisions == 1
        assert report.total_violations == 0
        assert report.compliance_pct == 100.0

        # Tenant is now ARCHIVED
        assert eng.get_tenant("lifecycle-t").status == TenantStatus.ARCHIVED

        # Events were emitted throughout
        total_events = len(es.list_events())
        assert total_events > initial_events + 15  # many mutations occurred

        # State hash is stable
        h = eng.state_hash()
        assert h == eng.state_hash()
        assert len(h) == 64


# ---------------------------------------------------------------------------
# Edge cases and extra coverage
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Additional edge-case tests for full coverage."""

    def test_empty_owner_allowed(self, env):
        _, eng = env
        t = eng.register_tenant("t1", "T1", owner="")
        assert t.owner == ""

    def test_workspace_default_empty_bindings(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        ws = eng.register_workspace("ws1", "t1", "WS1")
        assert ws.resource_bindings == ()
        assert ws.environment_ids == ()

    def test_environment_default_empty_promoted_from(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        e = eng.register_environment("env1", "ws1", EnvironmentKind.DEVELOPMENT)
        assert e.promoted_from == ""

    def test_close_tenant_with_violations(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_tenant("t2", "T2", owner="b")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t2", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "shared", ScopeBoundaryKind.MEMORY)
        eng.bind_workspace_resource("b2", "ws2", "shared", ScopeBoundaryKind.MEMORY)
        eng.detect_isolation_violations()
        report = eng.close_tenant("rpt1", "t1")
        assert report.total_violations >= 1
        assert report.compliance_pct < 100.0

    def test_multiple_workspaces_multiple_environments(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.register_environment("e1", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("e2", "ws1", EnvironmentKind.STAGING)
        eng.register_environment("e3", "ws2", EnvironmentKind.PRODUCTION)
        assert len(eng.environments_for_workspace("ws1")) == 2
        assert len(eng.environments_for_workspace("ws2")) == 1

    def test_bindings_for_workspace_none_type_returns_all(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "r1", ScopeBoundaryKind.CAMPAIGN)
        eng.bind_workspace_resource("b2", "ws1", "r2", ScopeBoundaryKind.MEMORY)
        all_b = eng.bindings_for_workspace("ws1", resource_type=None)
        assert len(all_b) == 2

    def test_multiple_isolation_levels(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        for i, level in enumerate(IsolationLevel):
            eng.add_boundary_policy(f"p{i}", "t1", ScopeBoundaryKind.MEMORY, isolation_level=level)
        assert eng.policy_count == len(IsolationLevel)

    def test_state_hash_differs_per_policy(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        h_before = eng.state_hash()
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY)
        h_after = eng.state_hash()
        assert h_before != h_after

    def test_state_hash_differs_per_binding(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        h_before = eng.state_hash()
        eng.bind_workspace_resource("b1", "ws1", "res", ScopeBoundaryKind.CAMPAIGN)
        assert eng.state_hash() != h_before

    def test_state_hash_differs_per_decision(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        h_before = eng.state_hash()
        eng.record_decision("d1", "t1", "Dec", confidence=0.5)
        assert eng.state_hash() != h_before

    def test_workspaces_for_nonexistent_tenant_returns_empty(self, env):
        _, eng = env
        assert eng.workspaces_for_tenant("no-such") == ()

    def test_detect_violations_no_policies_no_violations(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="a")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.bind_workspace_resource("b1", "ws1", "res", ScopeBoundaryKind.MEMORY)
        assert eng.detect_isolation_violations() == ()

    def test_strict_isolation_different_resource_types_ok(self, env):
        """STRICT on MEMORY does not block CONNECTOR sharing."""
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_workspace("ws2", "t1", "WS2")
        eng.add_boundary_policy("pol1", "t1", ScopeBoundaryKind.MEMORY, isolation_level=IsolationLevel.STRICT)
        eng.bind_workspace_resource("b1", "ws1", "res-1", ScopeBoundaryKind.CONNECTOR)
        b2 = eng.bind_workspace_resource("b2", "ws2", "res-1", ScopeBoundaryKind.CONNECTOR)
        assert b2.binding_id == "b2"

    def test_promotion_chain_dev_sandbox_staging(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        eng.register_environment("dev", "ws1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("sb", "ws1", EnvironmentKind.SANDBOX)
        eng.register_environment("stg", "ws1", EnvironmentKind.STAGING)
        p1 = eng.promote_environment("p1", "dev", "sb", compliance_check_passed=True)
        assert p1.status == PromotionStatus.COMPLETED
        p2 = eng.promote_environment("p2", "sb", "stg", compliance_check_passed=True)
        assert p2.status == PromotionStatus.COMPLETED
        assert eng.get_environment("sb").promoted_from == "dev"
        assert eng.get_environment("stg").promoted_from == "sb"

    def test_event_count_grows_monotonically(self, env):
        es, eng = env
        counts = [len(es.list_events())]
        eng.register_tenant("t1", "T1", owner="x")
        counts.append(len(es.list_events()))
        eng.register_workspace("ws1", "t1", "WS1")
        counts.append(len(es.list_events()))
        eng.register_environment("e1", "ws1", EnvironmentKind.DEVELOPMENT)
        counts.append(len(es.list_events()))
        eng.add_boundary_policy("p1", "t1", ScopeBoundaryKind.MEMORY)
        counts.append(len(es.list_events()))
        eng.bind_workspace_resource("b1", "ws1", "r1", ScopeBoundaryKind.CAMPAIGN)
        counts.append(len(es.list_events()))
        eng.record_decision("d1", "t1", "Dec", confidence=0.5)
        counts.append(len(es.list_events()))
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1]

    def test_frozen_returns(self, env):
        """Contract records are frozen (immutable)."""
        _, eng = env
        t = eng.register_tenant("t1", "T1", owner="x")
        with pytest.raises(AttributeError):
            t.name = "changed"

    def test_frozen_workspace(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        ws = eng.register_workspace("ws1", "t1", "WS1")
        with pytest.raises(AttributeError):
            ws.name = "changed"

    def test_frozen_environment(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        e = eng.register_environment("e1", "ws1", EnvironmentKind.DEVELOPMENT)
        with pytest.raises(AttributeError):
            e.kind = EnvironmentKind.PRODUCTION

    def test_frozen_policy(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        p = eng.add_boundary_policy("p1", "t1", ScopeBoundaryKind.MEMORY)
        with pytest.raises(AttributeError):
            p.enforced = False

    def test_frozen_binding(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        eng.register_workspace("ws1", "t1", "WS1")
        b = eng.bind_workspace_resource("b1", "ws1", "r1", ScopeBoundaryKind.CAMPAIGN)
        with pytest.raises(AttributeError):
            b.resource_ref_id = "changed"

    def test_frozen_health(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        h = eng.tenant_health("t1")
        with pytest.raises(AttributeError):
            h.compliance_pct = 0.0

    def test_frozen_decision(self, env):
        _, eng = env
        eng.register_tenant("t1", "T1", owner="x")
        d = eng.record_decision("d1", "t1", "Dec", confidence=0.5)
        with pytest.raises(AttributeError):
            d.title = "changed"
