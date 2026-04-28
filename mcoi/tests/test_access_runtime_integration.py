"""Tests for AccessRuntimeIntegration bridge.

Covers constructor validation, all authorize_* methods (allowed + denied),
memory mesh attachment, graph attachment, event emission, delegation flows,
budget approval semantics, disabled identity denial, and end-to-end golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.governance.guards.access import AccessRuntimeEngine
from mcoi_runtime.core.access_runtime_integration import AccessRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.access_runtime import (
    IdentityKind,
    RoleKind,
    PermissionEffect,
    AccessDecision,
    DelegationStatus,
    AuthContextKind,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# -----------------------------------------------------------------------
# Fixtures and helpers
# -----------------------------------------------------------------------


@pytest.fixture
def env():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = AccessRuntimeEngine(es)
    integ = AccessRuntimeIntegration(eng, es, mm)
    return es, mm, eng, integ


def _setup_admin(eng: AccessRuntimeEngine) -> None:
    """Register identity + role + binding + rules for most tests."""
    eng.register_identity("alice", "Alice", tenant_id="t1")
    eng.register_role(
        "admin",
        "Admin",
        kind=RoleKind.ADMIN,
        permissions=[
            "campaign:create",
            "portfolio:modify",
            "connector:use",
            "budget:modify",
            "program:modify",
            "environment:promote",
        ],
    )
    eng.bind_role(
        "rb1", "alice", "admin",
        scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
    )
    eng.add_permission_rule("r1", "campaign", "create", PermissionEffect.ALLOW)
    eng.add_permission_rule("r2", "budget", "modify", PermissionEffect.REQUIRE_APPROVAL)


# -----------------------------------------------------------------------
# 1. Constructor validation (3 tests)
# -----------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor rejects invalid dependency types."""

    def test_invalid_access_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="access_engine"):
            AccessRuntimeIntegration("not-an-engine", es, mm)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = AccessRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            AccessRuntimeIntegration(eng, "not-a-spine", mm)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = AccessRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            AccessRuntimeIntegration(eng, es, "not-a-mesh")


# -----------------------------------------------------------------------
# 2. authorize_campaign_action (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizeCampaignAction:

    def test_allowed(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_campaign_action(
            "req-1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "campaign"
        assert result["action"] == "create"
        assert result["decision"] == AccessDecision.ALLOWED.value
        assert isinstance(result["reason"], str)

    def test_denied_no_permission(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_campaign_action(
            "req-2", "alice", "delete",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "campaign"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 3. authorize_portfolio_action (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizePortfolioAction:

    def test_allowed(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_portfolio_action(
            "req-3", "alice", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert result["resource_type"] == "portfolio"
        assert result["action"] == "modify"
        assert result["decision"] == AccessDecision.ALLOWED.value

    def test_denied_unknown_identity(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_portfolio_action(
            "req-4", "unknown-user", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert result["resource_type"] == "portfolio"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 4. authorize_connector_use (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizeConnectorUse:

    def test_allowed(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_connector_use(
            "req-5", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert result["resource_type"] == "connector"
        assert result["action"] == "use"
        assert result["decision"] == AccessDecision.ALLOWED.value

    def test_denied_no_role(self, env):
        es, mm, eng, integ = env
        eng.register_identity("bob", "Bob", tenant_id="t2")
        result = integ.authorize_connector_use(
            "req-6", "bob",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert result["resource_type"] == "connector"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 5. authorize_budget_change (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizeBudgetChange:

    def test_requires_approval(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_budget_change(
            "req-7", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "budget"
        assert result["action"] == "modify"
        assert result["decision"] == AccessDecision.REQUIRES_APPROVAL.value

    def test_denied_no_permission(self, env):
        es, mm, eng, integ = env
        eng.register_identity("viewer", "Viewer", tenant_id="t1")
        eng.register_role("viewrole", "ViewRole", kind=RoleKind.VIEWER, permissions=[])
        eng.bind_role(
            "rb-v", "viewer", "viewrole",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        result = integ.authorize_budget_change(
            "req-8", "viewer", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "budget"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 6. authorize_program_change (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizeProgramChange:

    def test_allowed(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_program_change(
            "req-9", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "program"
        assert result["action"] == "modify"
        assert result["decision"] == AccessDecision.ALLOWED.value

    def test_denied_unknown_identity(self, env):
        es, mm, eng, integ = env
        result = integ.authorize_program_change(
            "req-10", "ghost", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["resource_type"] == "program"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 7. authorize_environment_promotion (2 tests)
# -----------------------------------------------------------------------


class TestAuthorizeEnvironmentPromotion:

    def test_allowed(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_environment_promotion(
            "req-11", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-prod",
        )
        assert result["resource_type"] == "environment"
        assert result["action"] == "promote"
        assert result["decision"] == AccessDecision.ALLOWED.value

    def test_denied_no_permission(self, env):
        es, mm, eng, integ = env
        eng.register_identity("bob", "Bob", tenant_id="t1")
        result = integ.authorize_environment_promotion(
            "req-12", "bob",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-prod",
        )
        assert result["resource_type"] == "environment"
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 8. Memory mesh attachment (1 test)
# -----------------------------------------------------------------------


class TestMemoryMeshAttachment:

    def test_attach_access_audit_to_memory_mesh(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        # Perform an authorization so there is audit data
        integ.authorize_campaign_action(
            "req-m1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        mem = integ.attach_access_audit_to_memory_mesh("t1")
        assert isinstance(mem, MemoryRecord)
        assert "access" in mem.tags
        assert "identity" in mem.tags
        assert "authorization" in mem.tags
        assert mem.content["scope_ref_id"] == "t1"
        assert mem.content["total_identities"] >= 1
        assert mem.content["total_roles"] >= 1
        assert mem.content["total_bindings"] >= 1
        assert mem.content["total_evaluations"] >= 1

    def test_memory_title_redacts_scope_ref(self, env):
        _es, _mm, eng, integ = env
        _setup_admin(eng)
        mem = integ.attach_access_audit_to_memory_mesh("tenant-secret")
        assert mem.title == "Access audit state"
        assert "tenant-secret" not in mem.title


# -----------------------------------------------------------------------
# 9. Graph attachment (1 test)
# -----------------------------------------------------------------------


class TestGraphAttachment:

    def test_attach_access_audit_to_graph(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        integ.authorize_campaign_action(
            "req-g1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        graph = integ.attach_access_audit_to_graph("t1")
        assert graph["scope_ref_id"] == "t1"
        assert "total_identities" in graph
        assert "total_roles" in graph
        assert "total_bindings" in graph
        assert "total_violations" in graph
        assert "active_delegations" in graph
        assert "total_evaluations" in graph
        assert "total_audits" in graph
        assert graph["total_identities"] >= 1
        assert graph["total_evaluations"] >= 1


# -----------------------------------------------------------------------
# 10. Events emitted (1 test)
# -----------------------------------------------------------------------


class TestEventsEmitted:

    def test_authorization_emits_events(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        initial_count = es.event_count
        integ.authorize_campaign_action(
            "req-ev1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        # The access engine evaluate_access emits an event, and the
        # integration layer emits another one.
        assert es.event_count > initial_count


# -----------------------------------------------------------------------
# 11. End-to-end golden path (1 test)
# -----------------------------------------------------------------------


class TestEndToEndGolden:

    def test_full_lifecycle(self, env):
        es, mm, eng, integ = env

        # 1. Register identities
        eng.register_identity("alice", "Alice", tenant_id="t1")
        eng.register_identity("bob", "Bob", tenant_id="t1")

        # 2. Register role with all permissions
        eng.register_role(
            "admin", "Admin", kind=RoleKind.ADMIN,
            permissions=[
                "campaign:create", "portfolio:modify", "connector:use",
                "budget:modify", "program:modify", "environment:promote",
            ],
        )

        # 3. Bind role to alice
        eng.bind_role(
            "rb-golden", "alice", "admin",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )

        # 4. Add permission rules
        eng.add_permission_rule("pr-c", "campaign", "create", PermissionEffect.ALLOW)
        eng.add_permission_rule("pr-p", "portfolio", "modify", PermissionEffect.ALLOW)
        eng.add_permission_rule("pr-conn", "connector", "use", PermissionEffect.ALLOW)
        eng.add_permission_rule("pr-b", "budget", "modify", PermissionEffect.REQUIRE_APPROVAL)
        eng.add_permission_rule("pr-prog", "program", "modify", PermissionEffect.ALLOW)
        eng.add_permission_rule("pr-env", "environment", "promote", PermissionEffect.ALLOW)

        # 5. Alice authorizes all types
        r_camp = integ.authorize_campaign_action(
            "g1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r_camp["decision"] == AccessDecision.ALLOWED.value

        r_port = integ.authorize_portfolio_action(
            "g2", "alice", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert r_port["decision"] == AccessDecision.ALLOWED.value

        r_conn = integ.authorize_connector_use(
            "g3", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert r_conn["decision"] == AccessDecision.ALLOWED.value

        r_budget = integ.authorize_budget_change(
            "g4", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r_budget["decision"] == AccessDecision.REQUIRES_APPROVAL.value

        r_prog = integ.authorize_program_change(
            "g5", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r_prog["decision"] == AccessDecision.ALLOWED.value

        r_env = integ.authorize_environment_promotion(
            "g6", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-prod",
        )
        assert r_env["decision"] == AccessDecision.ALLOWED.value

        # 6. Delegate admin role from alice to bob
        eng.delegate_permission(
            "del-1", "alice", "bob", "admin",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
            expires_at="2099-12-31T23:59:59+00:00",
        )

        # 7. Bob authorizes via delegation
        r_bob_camp = integ.authorize_campaign_action(
            "g7", "bob", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r_bob_camp["decision"] == AccessDecision.ALLOWED.value

        # 8. Revoke delegation
        eng.revoke_delegation("del-1")

        # 9. Bob is now denied
        r_bob_denied = integ.authorize_campaign_action(
            "g8", "bob", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r_bob_denied["decision"] == AccessDecision.DENIED.value

        # 10. Attach to memory mesh
        mem = integ.attach_access_audit_to_memory_mesh("t1")
        assert isinstance(mem, MemoryRecord)
        assert mem.content["total_evaluations"] >= 8

        # 11. Attach to graph
        graph = integ.attach_access_audit_to_graph("t1")
        assert graph["total_evaluations"] >= 8
        assert graph["active_delegations"] == 0  # revoked


# -----------------------------------------------------------------------
# 12. Budget requires-approval semantics (1 test)
# -----------------------------------------------------------------------


class TestBudgetRequiresApproval:

    def test_budget_modify_yields_requires_approval(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        result = integ.authorize_budget_change(
            "req-ba1", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["decision"] == AccessDecision.REQUIRES_APPROVAL.value
        assert result["resource_type"] == "budget"
        assert result["action"] == "modify"


# -----------------------------------------------------------------------
# 13. Disabled identity denied across all methods (1 test)
# -----------------------------------------------------------------------


class TestDisabledIdentityDenied:

    def test_disabled_identity_denied_everywhere(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        eng.disable_identity("alice")

        r1 = integ.authorize_campaign_action(
            "d1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r1["decision"] == AccessDecision.DENIED.value

        r2 = integ.authorize_portfolio_action(
            "d2", "alice", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert r2["decision"] == AccessDecision.DENIED.value

        r3 = integ.authorize_connector_use(
            "d3", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert r3["decision"] == AccessDecision.DENIED.value

        r4 = integ.authorize_budget_change(
            "d4", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r4["decision"] == AccessDecision.DENIED.value

        r5 = integ.authorize_program_change(
            "d5", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r5["decision"] == AccessDecision.DENIED.value

        r6 = integ.authorize_environment_promotion(
            "d6", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-prod",
        )
        assert r6["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 14. Additional coverage: return dict shape and immutability (6 tests)
# -----------------------------------------------------------------------


class TestReturnShape:
    """Every authorize_* returns a dict with the expected keys."""

    def test_campaign_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_campaign_action(
            "k1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert set(r.keys()) == {
            "request_id", "identity_id", "resource_type",
            "action", "decision", "reason",
        }
        assert r["request_id"] == "k1"
        assert r["identity_id"] == "alice"

    def test_portfolio_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_portfolio_action(
            "k2", "alice", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert r["request_id"] == "k2"
        assert r["resource_type"] == "portfolio"

    def test_connector_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_connector_use(
            "k3", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert r["request_id"] == "k3"
        assert r["action"] == "use"

    def test_budget_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_budget_change(
            "k4", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r["request_id"] == "k4"
        assert r["resource_type"] == "budget"

    def test_program_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_program_change(
            "k5", "alice", "modify",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert r["request_id"] == "k5"
        assert r["resource_type"] == "program"

    def test_environment_keys(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        r = integ.authorize_environment_promotion(
            "k6", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-prod",
        )
        assert r["request_id"] == "k6"
        assert r["resource_type"] == "environment"
        assert r["action"] == "promote"


# -----------------------------------------------------------------------
# 15. Explicit deny rule overrides allow (1 test)
# -----------------------------------------------------------------------


class TestExplicitDeny:

    def test_deny_rule_overrides_allow(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        eng.add_permission_rule(
            "deny-campaign", "campaign", "create", PermissionEffect.DENY,
        )
        result = integ.authorize_campaign_action(
            "req-deny1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert result["decision"] == AccessDecision.DENIED.value


# -----------------------------------------------------------------------
# 16. Graph reflects delegations correctly (1 test)
# -----------------------------------------------------------------------


class TestGraphDelegationCount:

    def test_active_delegations_counted(self, env):
        es, mm, eng, integ = env
        eng.register_identity("alice", "Alice", tenant_id="t1")
        eng.register_identity("bob", "Bob", tenant_id="t1")
        eng.register_role(
            "admin", "Admin", kind=RoleKind.ADMIN,
            permissions=["campaign:create"],
        )
        eng.bind_role(
            "rb1", "alice", "admin",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        eng.delegate_permission(
            "del-g1", "alice", "bob", "admin",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
            expires_at="2099-12-31T23:59:59+00:00",
        )
        graph = integ.attach_access_audit_to_graph("t1")
        assert graph["active_delegations"] == 1

        eng.revoke_delegation("del-g1")
        graph2 = integ.attach_access_audit_to_graph("t1")
        assert graph2["active_delegations"] == 0


# -----------------------------------------------------------------------
# 17. Memory mesh content fields are correct (1 test)
# -----------------------------------------------------------------------


class TestMemoryMeshContent:

    def test_content_has_expected_fields(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        mem = integ.attach_access_audit_to_memory_mesh("t1")
        expected_keys = {
            "scope_ref_id", "total_identities", "total_roles",
            "total_bindings", "total_rules", "total_delegations",
            "total_evaluations", "total_violations", "total_audits",
        }
        assert set(mem.content.keys()) == expected_keys


# -----------------------------------------------------------------------
# 18. Multiple authorizations accumulate evaluations (1 test)
# -----------------------------------------------------------------------


class TestEvaluationAccumulation:

    def test_evaluations_accumulate(self, env):
        es, mm, eng, integ = env
        _setup_admin(eng)
        assert eng.evaluation_count == 0

        integ.authorize_campaign_action(
            "acc1", "alice", "create",
            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1",
        )
        assert eng.evaluation_count == 1

        integ.authorize_portfolio_action(
            "acc2", "alice", "modify",
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws1",
        )
        assert eng.evaluation_count == 2

        integ.authorize_connector_use(
            "acc3", "alice",
            scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env1",
        )
        assert eng.evaluation_count == 3
