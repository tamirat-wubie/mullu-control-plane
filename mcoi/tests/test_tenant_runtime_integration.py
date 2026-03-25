"""Purpose: comprehensive tests for the TenantRuntimeIntegration bridge.
Governance scope: tenant runtime integration bridge tests only.
Dependencies: tenant_runtime engine, event_spine, memory_mesh,
    tenant_runtime_integration bridge, core invariants.
Invariants:
  - Every bind_* call returns an immutable dict with expected keys.
  - Memory mesh attachment produces a valid MemoryRecord.
  - Graph attachment returns expected aggregates.
  - Constructor validates all argument types.
  - Events are emitted for every integration operation.
  - Isolation enforcement propagates through integration layer.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.tenant_runtime import TenantRuntimeEngine
from mcoi_runtime.core.tenant_runtime_integration import TenantRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.tenant_runtime import (
    TenantStatus,
    WorkspaceStatus,
    EnvironmentKind,
    IsolationLevel,
    ScopeBoundaryKind,
    PromotionStatus,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = TenantRuntimeEngine(es)
    integ = TenantRuntimeIntegration(eng, es, mm)
    return es, mm, eng, integ


def _setup_tenant_workspace_env(eng: TenantRuntimeEngine):
    """Helper: register tenant t-1, workspace ws-1, and two environments."""
    eng.register_tenant("t-1", "Tenant One")
    eng.register_workspace("ws-1", "t-1", "Workspace One")
    eng.register_environment("env-dev-1", "ws-1", EnvironmentKind.DEVELOPMENT)
    eng.register_environment("env-stg-1", "ws-1", EnvironmentKind.STAGING)


def _setup_two_workspaces(eng: TenantRuntimeEngine):
    """Helper: register tenant t-1 with two workspaces and environments."""
    eng.register_tenant("t-1", "Tenant One")
    eng.register_workspace("ws-1", "t-1", "Workspace One")
    eng.register_workspace("ws-2", "t-1", "Workspace Two")
    eng.register_environment("env-dev-1", "ws-1", EnvironmentKind.DEVELOPMENT)
    eng.register_environment("env-dev-2", "ws-2", EnvironmentKind.DEVELOPMENT)


# ===========================================================================
# 1. Constructor validation
# ===========================================================================


class TestConstructorValidation:
    """Constructor must reject invalid argument types."""

    def test_invalid_tenant_engine_raises(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="tenant_engine"):
            TenantRuntimeIntegration("not-an-engine", es, mm)

    def test_invalid_event_spine_raises(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = TenantRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            TenantRuntimeIntegration(eng, "not-a-spine", mm)

    def test_invalid_memory_engine_raises(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = TenantRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            TenantRuntimeIntegration(eng, es, "not-a-mesh")


# ===========================================================================
# 2. bind_* method tests (one per method)
# ===========================================================================


class TestBindCampaignToWorkspace:
    def test_returns_campaign_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_campaign_to_workspace(
            "b-camp-1", "ws-1", "camp-ref-1", environment_id="env-dev-1",
        )
        assert result["resource_type"] == "campaign"
        assert result["binding_id"] == "b-camp-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "camp-ref-1"

    def test_campaign_binding_without_environment(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_campaign_to_workspace("b-camp-2", "ws-1", "camp-ref-2")
        assert result["resource_type"] == "campaign"
        assert result["binding_id"] == "b-camp-2"


class TestBindPortfolioToWorkspace:
    def test_returns_portfolio_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_portfolio_to_workspace(
            "b-port-1", "ws-1", "port-ref-1", environment_id="env-dev-1",
        )
        assert result["resource_type"] == "portfolio"
        assert result["binding_id"] == "b-port-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "port-ref-1"

    def test_portfolio_binding_without_environment(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_portfolio_to_workspace("b-port-2", "ws-1", "port-ref-2")
        assert result["resource_type"] == "portfolio"


class TestBindBudgetToTenant:
    def test_returns_budget_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_budget_to_tenant("b-bud-1", "ws-1", "bud-ref-1")
        assert result["resource_type"] == "budget"
        assert result["binding_id"] == "b-bud-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "bud-ref-1"


class TestBindConnectorToEnvironment:
    def test_returns_connector_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_connector_to_environment(
            "b-conn-1", "ws-1", "conn-ref-1", "env-dev-1",
        )
        assert result["resource_type"] == "connector"
        assert result["binding_id"] == "b-conn-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "conn-ref-1"
        assert result["environment_id"] == "env-dev-1"

    def test_connector_binding_includes_environment_id(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_connector_to_environment(
            "b-conn-2", "ws-1", "conn-ref-2", "env-stg-1",
        )
        assert result["environment_id"] == "env-stg-1"


class TestBindMemoryScopeToWorkspace:
    def test_returns_memory_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_memory_scope_to_workspace(
            "b-mem-1", "ws-1", "mem-ref-1",
        )
        assert result["resource_type"] == "memory"
        assert result["binding_id"] == "b-mem-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "mem-ref-1"


class TestBindProgramToTenant:
    def test_returns_program_binding(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_program_to_tenant("b-prog-1", "ws-1", "prog-ref-1")
        assert result["resource_type"] == "program"
        assert result["binding_id"] == "b-prog-1"
        assert result["workspace_id"] == "ws-1"
        assert result["resource_ref_id"] == "prog-ref-1"


# ===========================================================================
# 3. attach_tenant_state_to_memory_mesh
# ===========================================================================


class TestAttachTenantStateToMemoryMesh:
    def test_returns_memory_record(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert isinstance(mem, MemoryRecord)
        assert "tenant" in mem.tags
        assert "workspace" in mem.tags
        assert "environment" in mem.tags

    def test_memory_record_has_tenant_id_in_content(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert mem.content["tenant_id"] == "t-1"

    def test_memory_record_scope_ref_id(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert mem.scope_ref_id == "t-1"


# ===========================================================================
# 4. attach_tenant_state_to_graph
# ===========================================================================


class TestAttachTenantStateToGraph:
    def test_returns_expected_keys(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        graph = integ.attach_tenant_state_to_graph("t-1")
        assert graph["tenant_id"] == "t-1"
        assert "total_workspaces" in graph
        assert "active_workspaces" in graph
        assert "total_environments" in graph
        assert "total_bindings" in graph
        assert "total_violations" in graph
        assert "violation_ids" in graph
        assert "total_promotions" in graph

    def test_graph_workspace_counts(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        graph = integ.attach_tenant_state_to_graph("t-1")
        assert graph["total_workspaces"] == 1
        assert graph["active_workspaces"] == 1

    def test_graph_environment_count(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        graph = integ.attach_tenant_state_to_graph("t-1")
        # Two environments registered via _setup_tenant_workspace_env
        assert graph["total_environments"] == eng.environment_count

    def test_graph_zero_violations_initially(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        graph = integ.attach_tenant_state_to_graph("t-1")
        assert graph["total_violations"] == 0
        assert graph["violation_ids"] == []


# ===========================================================================
# 5. Events emitted check
# ===========================================================================


class TestEventsEmitted:
    def test_bind_campaign_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_campaign_to_workspace("b-camp-e1", "ws-1", "camp-ref-e1")
        assert es.event_count > initial_count

    def test_bind_portfolio_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_portfolio_to_workspace("b-port-e1", "ws-1", "port-ref-e1")
        assert es.event_count > initial_count

    def test_bind_budget_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_budget_to_tenant("b-bud-e1", "ws-1", "bud-ref-e1")
        assert es.event_count > initial_count

    def test_bind_connector_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_connector_to_environment("b-conn-e1", "ws-1", "conn-ref-e1", "env-dev-1")
        assert es.event_count > initial_count

    def test_bind_memory_scope_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_memory_scope_to_workspace("b-mem-e1", "ws-1", "mem-ref-e1")
        assert es.event_count > initial_count

    def test_bind_program_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.bind_program_to_tenant("b-prog-e1", "ws-1", "prog-ref-e1")
        assert es.event_count > initial_count

    def test_attach_memory_mesh_emits_event(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        initial_count = es.event_count
        integ.attach_tenant_state_to_memory_mesh("t-1")
        assert es.event_count > initial_count


# ===========================================================================
# 6. End-to-end golden scenario
# ===========================================================================


class TestEndToEndGoldenScenario:
    def test_full_lifecycle(self, env):
        """Register tenant + workspaces, bind all resource types, memory, graph."""
        es, mm, eng, integ = env

        # Register tenant with two workspaces
        eng.register_tenant("t-gold", "Gold Tenant")
        eng.register_workspace("ws-gold-1", "t-gold", "Gold WS 1")
        eng.register_workspace("ws-gold-2", "t-gold", "Gold WS 2")
        eng.register_environment("env-g-dev", "ws-gold-1", EnvironmentKind.DEVELOPMENT)
        eng.register_environment("env-g-stg", "ws-gold-1", EnvironmentKind.STAGING)
        eng.register_environment("env-g-dev2", "ws-gold-2", EnvironmentKind.DEVELOPMENT)

        # Bind all resource types
        camp = integ.bind_campaign_to_workspace(
            "bg-camp", "ws-gold-1", "camp-g1", environment_id="env-g-dev",
        )
        assert camp["resource_type"] == "campaign"

        port = integ.bind_portfolio_to_workspace(
            "bg-port", "ws-gold-1", "port-g1", environment_id="env-g-stg",
        )
        assert port["resource_type"] == "portfolio"

        bud = integ.bind_budget_to_tenant("bg-bud", "ws-gold-1", "bud-g1")
        assert bud["resource_type"] == "budget"

        conn = integ.bind_connector_to_environment(
            "bg-conn", "ws-gold-1", "conn-g1", "env-g-dev",
        )
        assert conn["resource_type"] == "connector"

        mem_bind = integ.bind_memory_scope_to_workspace(
            "bg-mem", "ws-gold-2", "mem-g1",
        )
        assert mem_bind["resource_type"] == "memory"

        prog = integ.bind_program_to_tenant("bg-prog", "ws-gold-2", "prog-g1")
        assert prog["resource_type"] == "program"

        # Attach memory mesh
        mem_rec = integ.attach_tenant_state_to_memory_mesh("t-gold")
        assert isinstance(mem_rec, MemoryRecord)
        assert mem_rec.content["total_workspaces"] == 2
        assert mem_rec.content["total_bindings"] == 6

        # Attach graph
        graph = integ.attach_tenant_state_to_graph("t-gold")
        assert graph["total_workspaces"] == 2
        assert graph["active_workspaces"] == 2
        assert graph["total_bindings"] == 6
        assert graph["total_violations"] == 0
        assert graph["violation_ids"] == []


# ===========================================================================
# 7. Isolation enforcement via integration
# ===========================================================================


class TestIsolationEnforcementViaIntegration:
    def test_strict_policy_blocks_duplicate_resource_binding(self, env):
        """STRICT campaign policy prevents same resource bound to different workspace."""
        es, mm, eng, integ = env
        _setup_two_workspaces(eng)

        # Add STRICT campaign boundary policy
        eng.add_boundary_policy(
            "pol-strict-camp", "t-1", ScopeBoundaryKind.CAMPAIGN,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )

        # Bind campaign to ws-1
        integ.bind_campaign_to_workspace("b-iso-1", "ws-1", "shared-camp-ref")

        # Attempt to bind same campaign to ws-2 should fail
        with pytest.raises(RuntimeCoreInvariantError, match="Isolation violation"):
            integ.bind_campaign_to_workspace("b-iso-2", "ws-2", "shared-camp-ref")

    def test_standard_policy_allows_duplicate_binding(self, env):
        """STANDARD isolation allows same resource on different workspaces."""
        es, mm, eng, integ = env
        _setup_two_workspaces(eng)

        # Add STANDARD campaign boundary policy (not STRICT)
        eng.add_boundary_policy(
            "pol-std-camp", "t-1", ScopeBoundaryKind.CAMPAIGN,
            isolation_level=IsolationLevel.STANDARD, enforced=True,
        )

        integ.bind_campaign_to_workspace("b-std-1", "ws-1", "shared-camp-ref")
        result = integ.bind_campaign_to_workspace("b-std-2", "ws-2", "shared-camp-ref")
        assert result["resource_type"] == "campaign"

    def test_strict_budget_policy_blocks_cross_workspace_binding(self, env):
        """STRICT budget policy also enforces isolation."""
        es, mm, eng, integ = env
        _setup_two_workspaces(eng)

        eng.add_boundary_policy(
            "pol-strict-bud", "t-1", ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )

        integ.bind_budget_to_tenant("b-biso-1", "ws-1", "shared-bud-ref")
        with pytest.raises(RuntimeCoreInvariantError, match="Isolation violation"):
            integ.bind_budget_to_tenant("b-biso-2", "ws-2", "shared-bud-ref")


# ===========================================================================
# 8. Environment-scoped connector binding verification
# ===========================================================================


class TestEnvironmentScopedConnectorBinding:
    def test_connector_bound_to_specific_environment(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        result = integ.bind_connector_to_environment(
            "b-conn-env1", "ws-1", "conn-env-ref", "env-dev-1",
        )
        assert result["environment_id"] == "env-dev-1"
        assert result["resource_type"] == "connector"

        # Verify the binding exists on the engine level for that environment
        bindings = eng.bindings_for_environment("env-dev-1")
        assert len(bindings) >= 1
        found = any(b.resource_ref_id == "conn-env-ref" for b in bindings)
        assert found

    def test_connector_bound_to_different_environments(self, env):
        """Same connector ref can bind to different environments."""
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        r1 = integ.bind_connector_to_environment(
            "b-conn-de1", "ws-1", "conn-shared", "env-dev-1",
        )
        r2 = integ.bind_connector_to_environment(
            "b-conn-de2", "ws-1", "conn-shared", "env-stg-1",
        )
        assert r1["environment_id"] == "env-dev-1"
        assert r2["environment_id"] == "env-stg-1"

    def test_connector_rejects_unknown_environment(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        with pytest.raises(RuntimeCoreInvariantError, match="Unknown environment_id"):
            integ.bind_connector_to_environment(
                "b-conn-bad", "ws-1", "conn-ref", "env-nonexistent",
            )


# ===========================================================================
# 9. Graph with violations
# ===========================================================================


class TestGraphWithViolations:
    def test_graph_reflects_detected_violations(self, env):
        """Graph output includes violations after detect_isolation_violations."""
        es, mm, eng, integ = env

        # Set up two tenants sharing a resource (cross-tenant violation scenario)
        eng.register_tenant("t-a", "Tenant A")
        eng.register_tenant("t-b", "Tenant B")
        eng.register_workspace("ws-a", "t-a", "WS A")
        eng.register_workspace("ws-b", "t-b", "WS B")

        # Add strict campaign policy for tenant A
        eng.add_boundary_policy(
            "pol-a-strict", "t-a", ScopeBoundaryKind.CAMPAIGN,
            isolation_level=IsolationLevel.STRICT, enforced=True,
        )

        # Bind same campaign ref to workspaces in different tenants
        # (no STRICT policy check across tenants at bind time for different tenants,
        #  but detect_isolation_violations catches cross-tenant sharing)
        eng.bind_workspace_resource(
            "bx-1", "ws-a", "shared-camp", ScopeBoundaryKind.CAMPAIGN,
        )
        eng.bind_workspace_resource(
            "bx-2", "ws-b", "shared-camp", ScopeBoundaryKind.CAMPAIGN,
        )

        violations = eng.detect_isolation_violations()
        assert len(violations) >= 1

        graph = integ.attach_tenant_state_to_graph("t-a")
        assert graph["total_violations"] >= 1
        assert len(graph["violation_ids"]) >= 1


# ===========================================================================
# 10. Memory content keys verification
# ===========================================================================


class TestMemoryContentKeys:
    def test_memory_record_content_keys(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        # Bind some resources so counts are non-zero
        integ.bind_campaign_to_workspace("b-ck-1", "ws-1", "camp-ck-1")
        integ.bind_budget_to_tenant("b-ck-2", "ws-1", "bud-ck-1")

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        content = mem.content

        expected_keys = {
            "tenant_id", "total_workspaces", "workspace_ids",
            "total_environments", "total_bindings", "total_policies",
            "total_violations", "total_promotions", "total_decisions",
        }
        assert expected_keys.issubset(set(content.keys()))

    def test_memory_content_workspace_ids_match(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert "ws-1" in mem.content["workspace_ids"]

    def test_memory_content_totals_are_non_negative(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert mem.content["total_workspaces"] >= 0
        assert mem.content["total_environments"] >= 0
        assert mem.content["total_bindings"] >= 0
        assert mem.content["total_violations"] >= 0
        assert mem.content["total_promotions"] >= 0
        assert mem.content["total_decisions"] >= 0

    def test_memory_content_with_bindings_reflects_count(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        integ.bind_campaign_to_workspace("b-mc-1", "ws-1", "camp-mc-1")
        integ.bind_budget_to_tenant("b-mc-2", "ws-1", "bud-mc-1")
        integ.bind_program_to_tenant("b-mc-3", "ws-1", "prog-mc-1")

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert mem.content["total_bindings"] == 3

    def test_memory_title_contains_tenant_id(self, env):
        es, mm, eng, integ = env
        _setup_tenant_workspace_env(eng)

        mem = integ.attach_tenant_state_to_memory_mesh("t-1")
        assert "t-1" in mem.title
