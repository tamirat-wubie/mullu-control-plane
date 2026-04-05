"""Purpose: comprehensive tests for the AccessRuntimeEngine.
Governance scope: runtime-core access / identity / authorization engine.
Dependencies: access_runtime contracts, event_spine, core invariants.
Invariants:
  - Evaluation is fail-closed: default is DENY.
  - DENY rules take precedence over ALLOW.
  - REQUIRE_APPROVAL rules take precedence over ALLOW but not DENY.
  - Disabled identities are always denied.
  - Expired / revoked delegations are not considered.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.access_runtime import (
    IdentityKind,
    RoleKind,
    PermissionEffect,
    AccessDecision,
    DelegationStatus,
    AuthContextKind,
)


# =====================================================================
# Fixture
# =====================================================================


@pytest.fixture
def env():
    es = EventSpineEngine()
    eng = AccessRuntimeEngine(es)
    return es, eng


# =====================================================================
# Helpers
# =====================================================================


def _setup_identity(eng, identity_id="id-1", name="Alice",
                    kind=IdentityKind.HUMAN, tenant_id="t1", enabled=True):
    return eng.register_identity(
        identity_id, name, kind=kind, tenant_id=tenant_id, enabled=enabled,
    )


def _setup_role(eng, role_id="role-admin", name="Admin",
                kind=RoleKind.ADMIN, permissions=None, description=""):
    return eng.register_role(
        role_id, name, kind=kind,
        permissions=permissions or ["campaign:read", "campaign:write"],
        description=description,
    )


def _setup_full(eng, identity_id="id-1", name="Alice",
                role_id="role-admin", role_name="Admin",
                permissions=None, tenant_id="t1",
                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1"):
    """Register identity + role + binding, return binding."""
    _setup_identity(eng, identity_id, name, tenant_id=tenant_id)
    _setup_role(eng, role_id, role_name, permissions=permissions)
    return eng.bind_role(
        f"bind-{identity_id}-{role_id}", identity_id, role_id,
        scope_kind=scope_kind, scope_ref_id=scope_ref_id,
    )


# =====================================================================
# 1. Constructor / Init
# =====================================================================


class TestConstructor:
    def test_requires_event_spine_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AccessRuntimeEngine("not-an-engine")

    def test_accepts_valid_event_spine(self, env):
        _, eng = env
        assert eng.identity_count == 0

    def test_initial_counts_are_zero(self, env):
        _, eng = env
        assert eng.identity_count == 0
        assert eng.role_count == 0
        assert eng.rule_count == 0
        assert eng.binding_count == 0
        assert eng.delegation_count == 0
        assert eng.evaluation_count == 0
        assert eng.violation_count == 0
        assert eng.audit_count == 0


# =====================================================================
# 2. Identity Management
# =====================================================================


class TestRegisterIdentity:
    def test_register_human_identity(self, env):
        _, eng = env
        rec = _setup_identity(eng)
        assert rec.identity_id == "id-1"
        assert rec.name == "Alice"
        assert rec.kind == IdentityKind.HUMAN
        assert rec.tenant_id == "t1"
        assert rec.enabled is True
        assert rec.created_at != ""
        assert eng.identity_count == 1

    def test_register_service_identity(self, env):
        _, eng = env
        rec = eng.register_identity("svc-1", "MyService",
                                     kind=IdentityKind.SERVICE, tenant_id="t1")
        assert rec.kind == IdentityKind.SERVICE

    def test_register_operator_identity(self, env):
        _, eng = env
        rec = eng.register_identity("op-1", "Operator",
                                     kind=IdentityKind.OPERATOR, tenant_id="t1")
        assert rec.kind == IdentityKind.OPERATOR

    def test_register_system_identity(self, env):
        _, eng = env
        rec = eng.register_identity("sys-1", "System",
                                     kind=IdentityKind.SYSTEM, tenant_id="t1")
        assert rec.kind == IdentityKind.SYSTEM

    def test_register_api_key_identity(self, env):
        _, eng = env
        rec = eng.register_identity("key-1", "APIKey",
                                     kind=IdentityKind.API_KEY, tenant_id="t1")
        assert rec.kind == IdentityKind.API_KEY

    def test_register_disabled_identity(self, env):
        _, eng = env
        rec = eng.register_identity("id-d", "Disabled", tenant_id="t1", enabled=False)
        assert rec.enabled is False

    def test_duplicate_identity_raises(self, env):
        _, eng = env
        _setup_identity(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _setup_identity(eng)

    def test_register_emits_event(self, env):
        es, eng = env
        _setup_identity(eng)
        assert es.event_count >= 1

    def test_register_multiple_identities(self, env):
        _, eng = env
        eng.register_identity("a", "A", tenant_id="t1")
        eng.register_identity("b", "B", tenant_id="t1")
        eng.register_identity("c", "C", tenant_id="t2")
        assert eng.identity_count == 3


class TestDisableEnableIdentity:
    def test_disable_identity(self, env):
        _, eng = env
        _setup_identity(eng)
        rec = eng.disable_identity("id-1")
        assert rec.enabled is False

    def test_disable_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.disable_identity("unknown")

    def test_enable_identity(self, env):
        _, eng = env
        _setup_identity(eng, enabled=False)
        rec = eng.enable_identity("id-1")
        assert rec.enabled is True

    def test_enable_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.enable_identity("unknown")

    def test_disable_then_enable(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.disable_identity("id-1")
        rec = eng.enable_identity("id-1")
        assert rec.enabled is True

    def test_disable_preserves_other_fields(self, env):
        _, eng = env
        orig = _setup_identity(eng, name="Alice", tenant_id="t1")
        disabled = eng.disable_identity("id-1")
        assert disabled.name == orig.name
        assert disabled.tenant_id == orig.tenant_id
        assert disabled.kind == orig.kind


class TestGetIdentity:
    def test_get_existing(self, env):
        _, eng = env
        _setup_identity(eng)
        rec = eng.get_identity("id-1")
        assert rec.identity_id == "id-1"

    def test_get_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_identity("nope")


class TestIdentitiesForTenant:
    def test_returns_matching_identities(self, env):
        _, eng = env
        eng.register_identity("a", "A", tenant_id="t1")
        eng.register_identity("b", "B", tenant_id="t1")
        eng.register_identity("c", "C", tenant_id="t2")
        result = eng.identities_for_tenant("t1")
        assert len(result) == 2
        ids = {r.identity_id for r in result}
        assert ids == {"a", "b"}

    def test_returns_empty_for_unknown_tenant(self, env):
        _, eng = env
        assert eng.identities_for_tenant("ghost") == ()

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.identities_for_tenant("t1")
        assert isinstance(result, tuple)


# =====================================================================
# 3. Role Management
# =====================================================================


class TestRegisterRole:
    def test_register_role_basic(self, env):
        _, eng = env
        rec = _setup_role(eng)
        assert rec.role_id == "role-admin"
        assert rec.name == "Admin"
        assert rec.kind == RoleKind.ADMIN
        assert "campaign:read" in rec.permissions
        assert eng.role_count == 1

    def test_register_role_all_kinds(self, env):
        _, eng = env
        for i, kind in enumerate(RoleKind):
            eng.register_role(f"r-{i}", f"Role-{i}", kind=kind)
        assert eng.role_count == len(RoleKind)

    def test_duplicate_role_raises(self, env):
        _, eng = env
        _setup_role(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _setup_role(eng)

    def test_role_with_no_permissions(self, env):
        _, eng = env
        rec = eng.register_role("r-empty", "Empty", permissions=[])
        assert rec.permissions == ()

    def test_role_with_wildcard_permission(self, env):
        _, eng = env
        rec = eng.register_role("r-super", "Super", permissions=["*:*"])
        assert "*:*" in rec.permissions

    def test_role_emits_event(self, env):
        es, eng = env
        before = es.event_count
        _setup_role(eng)
        assert es.event_count > before

    def test_role_description_stored(self, env):
        _, eng = env
        rec = eng.register_role("r-desc", "Described",
                                description="A descriptive role")
        assert rec.description == "A descriptive role"


# =====================================================================
# 4. Permission Rules
# =====================================================================


class TestAddPermissionRule:
    def test_add_allow_rule(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-1", "campaign", "read", PermissionEffect.ALLOW,
        )
        assert rule.rule_id == "rule-1"
        assert rule.effect == PermissionEffect.ALLOW
        assert eng.rule_count == 1

    def test_add_deny_rule(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-d", "campaign", "delete", PermissionEffect.DENY,
        )
        assert rule.effect == PermissionEffect.DENY

    def test_add_require_approval_rule(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-ra", "budget", "modify", PermissionEffect.REQUIRE_APPROVAL,
        )
        assert rule.effect == PermissionEffect.REQUIRE_APPROVAL

    def test_duplicate_rule_raises(self, env):
        _, eng = env
        eng.add_permission_rule("rule-1", "x", "y", PermissionEffect.ALLOW)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.add_permission_rule("rule-1", "a", "b", PermissionEffect.DENY)

    def test_rule_scope(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-scoped", "campaign", "read", PermissionEffect.ALLOW,
            scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws-1",
        )
        assert rule.scope_kind == AuthContextKind.WORKSPACE
        assert rule.scope_ref_id == "ws-1"

    def test_rule_conditions(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-cond", "campaign", "read", PermissionEffect.ALLOW,
            conditions={"max_budget": 1000},
        )
        assert rule.conditions["max_budget"] == 1000

    def test_rule_emits_event(self, env):
        es, eng = env
        before = es.event_count
        eng.add_permission_rule("rule-1", "x", "y", PermissionEffect.ALLOW)
        assert es.event_count > before

    def test_global_scope_rule(self, env):
        _, eng = env
        rule = eng.add_permission_rule(
            "rule-g", "campaign", "read", PermissionEffect.ALLOW,
            scope_kind=AuthContextKind.GLOBAL,
        )
        assert rule.scope_kind == AuthContextKind.GLOBAL


# =====================================================================
# 5. Role Binding
# =====================================================================


class TestBindRole:
    def test_bind_role_basic(self, env):
        _, eng = env
        _setup_identity(eng)
        _setup_role(eng)
        binding = eng.bind_role("bind-1", "id-1", "role-admin",
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        assert binding.binding_id == "bind-1"
        assert binding.identity_id == "id-1"
        assert binding.role_id == "role-admin"
        assert eng.binding_count == 1

    def test_duplicate_binding_raises(self, env):
        _, eng = env
        _setup_identity(eng)
        _setup_role(eng)
        eng.bind_role("bind-1", "id-1", "role-admin")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.bind_role("bind-1", "id-1", "role-admin")

    def test_unknown_identity_raises(self, env):
        _, eng = env
        _setup_role(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown identity") as exc_info:
            eng.bind_role("bind-1", "ghost", "role-admin")
        assert "ghost" not in str(exc_info.value)

    def test_unknown_role_raises(self, env):
        _, eng = env
        _setup_identity(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown role") as exc_info:
            eng.bind_role("bind-1", "id-1", "ghost-role")
        assert "ghost-role" not in str(exc_info.value)

    def test_binding_emits_event(self, env):
        es, eng = env
        _setup_identity(eng)
        _setup_role(eng)
        before = es.event_count
        eng.bind_role("bind-1", "id-1", "role-admin")
        assert es.event_count > before

    def test_multiple_bindings_per_identity(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.register_role("r1", "R1", permissions=["a:b"])
        eng.register_role("r2", "R2", permissions=["c:d"])
        eng.bind_role("b1", "id-1", "r1")
        eng.bind_role("b2", "id-1", "r2")
        assert eng.binding_count == 2


class TestBindingsForIdentity:
    def test_returns_bindings(self, env):
        _, eng = env
        _setup_identity(eng)
        _setup_role(eng)
        eng.bind_role("b1", "id-1", "role-admin",
                      scope_kind=AuthContextKind.TENANT)
        result = eng.bindings_for_identity("id-1")
        assert len(result) == 1

    def test_filter_by_scope_kind(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.register_role("r1", "R1", permissions=["a:b"])
        eng.register_role("r2", "R2", permissions=["c:d"])
        eng.bind_role("b1", "id-1", "r1", scope_kind=AuthContextKind.TENANT)
        eng.bind_role("b2", "id-1", "r2", scope_kind=AuthContextKind.WORKSPACE)
        tenant_only = eng.bindings_for_identity("id-1",
                                                 scope_kind=AuthContextKind.TENANT)
        assert len(tenant_only) == 1
        assert tenant_only[0].scope_kind == AuthContextKind.TENANT

    def test_no_bindings_returns_empty(self, env):
        _, eng = env
        assert eng.bindings_for_identity("id-1") == ()

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.bindings_for_identity("id-1")
        assert isinstance(result, tuple)


# =====================================================================
# 6. Delegation
# =====================================================================


class TestDelegatePermission:
    def test_delegate_basic(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r1", "R1", permissions=["campaign:write"])
        d = eng.delegate_permission("del-1", "from-1", "to-1", "r1",
                                     scope_kind=AuthContextKind.WORKSPACE,
                                     scope_ref_id="ws-1")
        assert d.delegation_id == "del-1"
        assert d.status == DelegationStatus.ACTIVE
        assert d.from_identity_id == "from-1"
        assert d.to_identity_id == "to-1"
        assert eng.delegation_count == 1

    def test_duplicate_delegation_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.delegate_permission("del-1", "f", "t", "r")

    def test_unknown_from_identity_raises(self, env):
        _, eng = env
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown from"):
            eng.delegate_permission("del-1", "ghost", "t", "r")

    def test_unknown_to_identity_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown to") as exc_info:
            eng.delegate_permission("del-1", "f", "ghost", "r")
        assert "ghost" not in str(exc_info.value)

    def test_unknown_role_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown role"):
            eng.delegate_permission("del-1", "f", "t", "ghost")

    def test_delegation_emits_event(self, env):
        es, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        before = es.event_count
        eng.delegate_permission("del-1", "f", "t", "r")
        assert es.event_count > before

    def test_delegation_with_expires_at(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        d = eng.delegate_permission("del-1", "f", "t", "r",
                                     expires_at="2099-12-31T23:59:59+00:00")
        assert d.expires_at == "2099-12-31T23:59:59+00:00"


class TestRevokeDelegation:
    def test_revoke_active_delegation(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        d = eng.revoke_delegation("del-1")
        assert d.status == DelegationStatus.REVOKED

    def test_revoke_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.revoke_delegation("ghost")

    def test_revoke_already_revoked_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        eng.revoke_delegation("del-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.revoke_delegation("del-1")
        assert str(exc_info.value) == "cannot revoke delegation from current status"
        assert "revoked" not in str(exc_info.value)

    def test_revoke_expired_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        eng.expire_delegation("del-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.revoke_delegation("del-1")
        assert str(exc_info.value) == "cannot revoke delegation from current status"
        assert "expired" not in str(exc_info.value)

    def test_revoke_emits_event(self, env):
        es, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        before = es.event_count
        eng.revoke_delegation("del-1")
        assert es.event_count > before


class TestExpireDelegation:
    def test_expire_active_delegation(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        d = eng.expire_delegation("del-1")
        assert d.status == DelegationStatus.EXPIRED

    def test_expire_unknown_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.expire_delegation("ghost")

    def test_expire_already_expired_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        eng.expire_delegation("del-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.expire_delegation("del-1")
        assert str(exc_info.value) == "cannot expire delegation from current status"
        assert "expired" not in str(exc_info.value)

    def test_expire_revoked_raises(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("del-1", "f", "t", "r")
        eng.revoke_delegation("del-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.expire_delegation("del-1")
        assert str(exc_info.value) == "cannot expire delegation from current status"
        assert "revoked" not in str(exc_info.value)


class TestActiveDelegationsForIdentity:
    def test_returns_active_only(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("d1", "f", "t", "r")
        eng.delegate_permission("d2", "f", "t", "r")
        eng.revoke_delegation("d2")
        active = eng.active_delegations_for_identity("t")
        assert len(active) == 1
        assert active[0].delegation_id == "d1"

    def test_empty_when_none_active(self, env):
        _, eng = env
        assert eng.active_delegations_for_identity("anyone") == ()

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.active_delegations_for_identity("x")
        assert isinstance(result, tuple)


# =====================================================================
# 7. Access Evaluation
# =====================================================================


class TestEvaluateAccessBasic:
    def test_unknown_identity_denied(self, env):
        _, eng = env
        ev = eng.evaluate_access("req-1", "ghost", "campaign", "read")
        assert ev.decision == AccessDecision.DENIED
        assert "unknown" in ev.reason

    def test_disabled_identity_denied(self, env):
        _, eng = env
        _setup_identity(eng, enabled=True)
        eng.disable_identity("id-1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read")
        assert ev.decision == AccessDecision.DENIED
        assert "disabled" in ev.reason

    def test_no_permission_denied(self, env):
        _, eng = env
        _setup_identity(eng)
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read")
        assert ev.decision == AccessDecision.DENIED
        assert "no matching" in ev.reason

    def test_allowed_with_matching_permission(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read", "campaign:write"])
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_evaluation_increments_count(self, env):
        _, eng = env
        _setup_identity(eng)
        assert eng.evaluation_count == 0
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        assert eng.evaluation_count == 1

    def test_evaluation_records_audit(self, env):
        _, eng = env
        _setup_identity(eng)
        assert eng.audit_count == 0
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        assert eng.audit_count == 1

    def test_evaluation_returns_immutable_record(self, env):
        _, eng = env
        _setup_identity(eng)
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read")
        with pytest.raises(AttributeError):
            ev.decision = AccessDecision.ALLOWED  # type: ignore[misc]


class TestEvaluateAccessDenyPrecedence:
    def test_deny_overrides_allow(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("allow-r", "campaign", "read",
                                PermissionEffect.ALLOW,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        eng.add_permission_rule("deny-r", "campaign", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED
        assert "deny" in ev.reason

    def test_deny_overrides_require_approval(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("ra-r", "campaign", "read",
                                PermissionEffect.REQUIRE_APPROVAL,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        eng.add_permission_rule("deny-r", "campaign", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED


class TestEvaluateAccessRequireApproval:
    def test_require_approval_overrides_allow(self, env):
        _, eng = env
        _setup_full(eng, permissions=["budget:modify"])
        eng.add_permission_rule("allow-r", "budget", "modify",
                                PermissionEffect.ALLOW,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        eng.add_permission_rule("ra-r", "budget", "modify",
                                PermissionEffect.REQUIRE_APPROVAL,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "budget", "modify",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.REQUIRES_APPROVAL


class TestEvaluateAccessWildcard:
    def test_wildcard_resource_action_grants_access(self, env):
        _, eng = env
        _setup_full(eng, permissions=["*:*"])
        ev = eng.evaluate_access("req-1", "id-1", "anything", "whatever",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_resource_wildcard_action(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:*"])
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "delete",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_wildcard_does_not_override_deny_rule(self, env):
        _, eng = env
        _setup_full(eng, permissions=["*:*"])
        eng.add_permission_rule("deny-all", "campaign", "delete",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "delete",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED


class TestEvaluateAccessDelegation:
    def test_active_delegation_grants_access(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r-write", "Writer",
                          permissions=["campaign:write"])
        eng.delegate_permission("del-1", "from-1", "to-1", "r-write",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        ev = eng.evaluate_access("req-1", "to-1", "campaign", "write",
                                  scope_kind=AuthContextKind.WORKSPACE,
                                  scope_ref_id="ws-1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_revoked_delegation_does_not_grant(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r-write", "Writer",
                          permissions=["campaign:write"])
        eng.delegate_permission("del-1", "from-1", "to-1", "r-write",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        eng.revoke_delegation("del-1")
        ev = eng.evaluate_access("req-1", "to-1", "campaign", "write",
                                  scope_kind=AuthContextKind.WORKSPACE,
                                  scope_ref_id="ws-1")
        assert ev.decision == AccessDecision.DENIED

    def test_expired_delegation_does_not_grant(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r-write", "Writer",
                          permissions=["campaign:write"])
        eng.delegate_permission("del-1", "from-1", "to-1", "r-write",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        eng.expire_delegation("del-1")
        ev = eng.evaluate_access("req-1", "to-1", "campaign", "write",
                                  scope_kind=AuthContextKind.WORKSPACE,
                                  scope_ref_id="ws-1")
        assert ev.decision == AccessDecision.DENIED


class TestEvaluateAccessScopeHierarchy:
    def test_global_binding_applies_everywhere(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-global", permissions=["campaign:read"])
        eng.bind_role("b-g", "u1", "r-global",
                      scope_kind=AuthContextKind.GLOBAL)
        for sk in (AuthContextKind.TENANT, AuthContextKind.WORKSPACE,
                   AuthContextKind.ENVIRONMENT):
            ev = eng.evaluate_access(f"req-{sk.value}", "u1", "campaign", "read",
                                      scope_kind=sk, scope_ref_id="any")
            assert ev.decision == AccessDecision.ALLOWED, f"Failed for {sk}"

    def test_tenant_binding_applies_to_workspace(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-t", permissions=["campaign:read"])
        eng.bind_role("b-t", "u1", "r-t",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-ws", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.WORKSPACE,
                                  scope_ref_id="ws-1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_tenant_binding_applies_to_environment(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-t", permissions=["campaign:read"])
        eng.bind_role("b-t", "u1", "r-t",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-env", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.ENVIRONMENT,
                                  scope_ref_id="env-1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_workspace_binding_applies_to_environment(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-ws", permissions=["campaign:read"])
        eng.bind_role("b-ws", "u1", "r-ws",
                      scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws-1")
        ev = eng.evaluate_access("req-env", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.ENVIRONMENT,
                                  scope_ref_id="env-1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_workspace_binding_does_not_apply_to_tenant(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-ws", permissions=["campaign:read"])
        eng.bind_role("b-ws", "u1", "r-ws",
                      scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws-1")
        ev = eng.evaluate_access("req-t", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_environment_binding_does_not_apply_to_workspace(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-env", permissions=["campaign:read"])
        eng.bind_role("b-env", "u1", "r-env",
                      scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-1")
        ev = eng.evaluate_access("req-ws", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.WORKSPACE,
                                  scope_ref_id="ws-1")
        assert ev.decision == AccessDecision.DENIED

    def test_environment_binding_does_not_apply_to_tenant(self, env):
        _, eng = env
        _setup_identity(eng, identity_id="u1", tenant_id="t1")
        _setup_role(eng, role_id="r-env", permissions=["campaign:read"])
        eng.bind_role("b-env", "u1", "r-env",
                      scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="env-1")
        ev = eng.evaluate_access("req-t", "u1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_global_rule_deny_applies_to_all_scopes(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("deny-global", "campaign", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.GLOBAL)
        for sk in (AuthContextKind.TENANT, AuthContextKind.WORKSPACE,
                   AuthContextKind.ENVIRONMENT):
            ev = eng.evaluate_access(f"req-{sk.value}", "id-1", "campaign", "read",
                                      scope_kind=sk, scope_ref_id="any")
            assert ev.decision == AccessDecision.DENIED, f"Failed for {sk}"


class TestEvaluateAccessMatchingRuleIds:
    def test_matching_rule_ids_populated(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("allow-r", "campaign", "read",
                                PermissionEffect.ALLOW,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert "allow-r" in ev.matching_rule_ids

    def test_matching_role_ids_populated(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert "role-admin" in ev.matching_role_ids


# =====================================================================
# 8. List Effective Permissions
# =====================================================================


class TestListEffectivePermissions:
    def test_returns_permissions_for_identity(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read", "campaign:write"])
        perms = eng.list_effective_permissions("id-1", AuthContextKind.TENANT, "t1")
        assert "campaign:read" in perms
        assert "campaign:write" in perms

    def test_unknown_identity_raises(self, env):
        _, eng = env
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.list_effective_permissions("ghost", AuthContextKind.TENANT)

    def test_disabled_identity_returns_empty(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.disable_identity("id-1")
        perms = eng.list_effective_permissions("id-1", AuthContextKind.TENANT, "t1")
        assert perms == ()

    def test_includes_delegated_permissions(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r-write", "Writer",
                          permissions=["campaign:write"])
        eng.delegate_permission("del-1", "from-1", "to-1", "r-write",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        perms = eng.list_effective_permissions("to-1",
                                               AuthContextKind.WORKSPACE, "ws-1")
        assert "campaign:write" in perms

    def test_revoked_delegation_not_included(self, env):
        _, eng = env
        eng.register_identity("from-1", "From", tenant_id="t1")
        eng.register_identity("to-1", "To", tenant_id="t1")
        eng.register_role("r-write", "Writer",
                          permissions=["campaign:write"])
        eng.delegate_permission("del-1", "from-1", "to-1", "r-write",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        eng.revoke_delegation("del-1")
        perms = eng.list_effective_permissions("to-1",
                                               AuthContextKind.WORKSPACE, "ws-1")
        assert "campaign:write" not in perms

    def test_returns_sorted_tuple(self, env):
        _, eng = env
        _setup_full(eng, permissions=["z:z", "a:a", "m:m"])
        perms = eng.list_effective_permissions("id-1", AuthContextKind.TENANT, "t1")
        assert perms == tuple(sorted(perms))
        assert isinstance(perms, tuple)

    def test_no_bindings_returns_empty(self, env):
        _, eng = env
        _setup_identity(eng)
        perms = eng.list_effective_permissions("id-1", AuthContextKind.TENANT, "t1")
        assert perms == ()

    def test_multiple_roles_merged(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.register_role("r1", "R1", permissions=["a:b"])
        eng.register_role("r2", "R2", permissions=["c:d"])
        eng.bind_role("b1", "id-1", "r1",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.bind_role("b2", "id-1", "r2",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        perms = eng.list_effective_permissions("id-1", AuthContextKind.TENANT, "t1")
        assert "a:b" in perms
        assert "c:d" in perms


# =====================================================================
# 9. Violation Detection
# =====================================================================


class TestDetectViolations:
    def test_no_violations_when_no_denials(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.evaluate_access("req-1", "id-1", "campaign", "read",
                            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        violations = eng.detect_violations()
        assert len(violations) == 0

    def test_violation_detected_on_denial(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        violations = eng.detect_violations()
        assert len(violations) >= 1
        assert eng.violation_count >= 1

    def test_dedup_violations(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        v1 = eng.detect_violations()
        v2 = eng.detect_violations()
        assert len(v2) == 0  # second scan produces no new violations
        assert eng.violation_count == len(v1)

    def test_violation_has_identity_id(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        violations = eng.detect_violations()
        assert violations[0].identity_id == "id-1"

    def test_violation_emits_event(self, env):
        es, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        before = es.event_count
        eng.detect_violations()
        assert es.event_count > before

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.detect_violations()
        assert isinstance(result, tuple)


class TestViolationsForIdentity:
    def test_returns_matching_violations(self, env):
        _, eng = env
        eng.register_identity("a", "A", tenant_id="t1")
        eng.register_identity("b", "B", tenant_id="t1")
        eng.evaluate_access("req-a", "a", "campaign", "read")
        eng.evaluate_access("req-b", "b", "campaign", "read")
        eng.detect_violations()
        va = eng.violations_for_identity("a")
        vb = eng.violations_for_identity("b")
        assert all(v.identity_id == "a" for v in va)
        assert all(v.identity_id == "b" for v in vb)

    def test_returns_empty_for_no_violations(self, env):
        _, eng = env
        assert eng.violations_for_identity("ghost") == ()


# =====================================================================
# 10. Access Snapshot
# =====================================================================


class TestAccessSnapshot:
    def test_snapshot_basic(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        snap = eng.access_snapshot("snap-1", "t1")
        assert snap.snapshot_id == "snap-1"
        assert snap.scope_ref_id == "t1"
        assert snap.total_identities == 1
        assert snap.total_roles == 1
        assert snap.total_bindings == 1
        assert snap.captured_at != ""

    def test_duplicate_snapshot_raises(self, env):
        _, eng = env
        eng.access_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.access_snapshot("snap-1")

    def test_snapshot_counts_delegations(self, env):
        _, eng = env
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("d1", "f", "t", "r")
        eng.delegate_permission("d2", "f", "t", "r")
        eng.revoke_delegation("d2")
        snap = eng.access_snapshot("snap-1")
        assert snap.active_delegations == 1

    def test_snapshot_counts_violations(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "x", "y")
        eng.detect_violations()
        snap = eng.access_snapshot("snap-1")
        assert snap.total_violations >= 1

    def test_snapshot_counts_evaluations(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "x", "y")
        eng.evaluate_access("req-2", "id-1", "x", "y")
        snap = eng.access_snapshot("snap-1")
        assert snap.total_evaluations == 2

    def test_snapshot_emits_event(self, env):
        es, eng = env
        before = es.event_count
        eng.access_snapshot("snap-1")
        assert es.event_count > before


# =====================================================================
# 11. Audit Trail
# =====================================================================


class TestAuditsForIdentity:
    def test_returns_audit_records(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        audits = eng.audits_for_identity("id-1")
        assert len(audits) >= 1
        assert audits[0].identity_id == "id-1"

    def test_returns_empty_for_unknown(self, env):
        _, eng = env
        assert eng.audits_for_identity("ghost") == ()

    def test_returns_tuple(self, env):
        _, eng = env
        result = eng.audits_for_identity("anyone")
        assert isinstance(result, tuple)

    def test_multiple_audits_tracked(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "campaign", "read")
        eng.evaluate_access("req-2", "id-1", "campaign", "write")
        audits = eng.audits_for_identity("id-1")
        assert len(audits) == 2


# =====================================================================
# 12. State Hash
# =====================================================================


class TestStateHash:
    def test_state_hash_is_16_chars(self, env):
        _, eng = env
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_state_hash_changes_with_mutations(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _setup_identity(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_deterministic(self, env):
        _, eng = env
        _setup_identity(eng)
        assert eng.state_hash() == eng.state_hash()

    def test_state_hash_changes_with_role(self, env):
        _, eng = env
        h1 = eng.state_hash()
        _setup_role(eng)
        h2 = eng.state_hash()
        assert h1 != h2


# =====================================================================
# 13. Properties
# =====================================================================


class TestProperties:
    def test_identity_count(self, env):
        _, eng = env
        assert eng.identity_count == 0
        _setup_identity(eng)
        assert eng.identity_count == 1

    def test_role_count(self, env):
        _, eng = env
        assert eng.role_count == 0
        _setup_role(eng)
        assert eng.role_count == 1

    def test_rule_count(self, env):
        _, eng = env
        assert eng.rule_count == 0
        eng.add_permission_rule("r1", "x", "y", PermissionEffect.ALLOW)
        assert eng.rule_count == 1

    def test_binding_count(self, env):
        _, eng = env
        assert eng.binding_count == 0
        _setup_identity(eng)
        _setup_role(eng)
        eng.bind_role("b1", "id-1", "role-admin")
        assert eng.binding_count == 1

    def test_delegation_count(self, env):
        _, eng = env
        assert eng.delegation_count == 0
        eng.register_identity("f", "F", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("d1", "f", "t", "r")
        assert eng.delegation_count == 1

    def test_evaluation_count(self, env):
        _, eng = env
        assert eng.evaluation_count == 0
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "x", "y")
        assert eng.evaluation_count == 1

    def test_violation_count(self, env):
        _, eng = env
        assert eng.violation_count == 0
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "x", "y")
        eng.detect_violations()
        assert eng.violation_count >= 1

    def test_audit_count(self, env):
        _, eng = env
        assert eng.audit_count == 0
        _setup_identity(eng)
        eng.evaluate_access("req-1", "id-1", "x", "y")
        assert eng.audit_count >= 1


# =====================================================================
# 14. Golden Scenario 1: Tenant admin allowed, cross-tenant user denied
# =====================================================================


class TestGoldenScenario1TenantIsolation:
    def test_admin_in_own_tenant_allowed(self, env):
        _, eng = env
        eng.register_identity("admin-t1", "AdminT1",
                               kind=IdentityKind.HUMAN, tenant_id="t1")
        eng.register_role("r-admin", "TenantAdmin", kind=RoleKind.ADMIN,
                          permissions=["campaign:read", "campaign:write",
                                       "campaign:delete"])
        eng.bind_role("b-admin-t1", "admin-t1", "r-admin",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-admin-t1", "admin-t1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_viewer_in_other_tenant_denied(self, env):
        _, eng = env
        eng.register_identity("viewer-t2", "ViewerT2",
                               kind=IdentityKind.HUMAN, tenant_id="t2")
        eng.register_role("r-viewer", "Viewer", kind=RoleKind.VIEWER,
                          permissions=["campaign:read"])
        eng.bind_role("b-viewer-t2", "viewer-t2", "r-viewer",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t2")
        ev = eng.evaluate_access("req-viewer-t2", "viewer-t2", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_full_cross_tenant_scenario(self, env):
        _, eng = env
        # Set up two tenants
        eng.register_identity("admin-t1", "AdminT1", tenant_id="t1")
        eng.register_identity("viewer-t2", "ViewerT2", tenant_id="t2")
        eng.register_role("r-admin", "Admin", kind=RoleKind.ADMIN,
                          permissions=["campaign:read", "campaign:write"])
        eng.register_role("r-viewer", "Viewer", kind=RoleKind.VIEWER,
                          permissions=["campaign:read"])
        eng.bind_role("b-admin", "admin-t1", "r-admin",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.bind_role("b-viewer", "viewer-t2", "r-viewer",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t2")

        # Admin accesses own tenant: allowed
        ev_admin = eng.evaluate_access("req-1", "admin-t1", "campaign", "write",
                                        scope_kind=AuthContextKind.TENANT,
                                        scope_ref_id="t1")
        assert ev_admin.decision == AccessDecision.ALLOWED

        # Viewer accesses other tenant: denied
        ev_viewer = eng.evaluate_access("req-2", "viewer-t2", "campaign", "read",
                                         scope_kind=AuthContextKind.TENANT,
                                         scope_ref_id="t1")
        assert ev_viewer.decision == AccessDecision.DENIED

        # Detect violations
        violations = eng.detect_violations()
        assert len(violations) >= 1
        v_ids = {v.identity_id for v in violations}
        assert "viewer-t2" in v_ids


# =====================================================================
# 15. Golden Scenario 2: Dev operator denied prod connector usage
# =====================================================================


class TestGoldenScenario2DevDeniedProd:
    def test_dev_operator_denied_prod_connector(self, env):
        _, eng = env
        eng.register_identity("dev-op", "DevOperator",
                               kind=IdentityKind.OPERATOR, tenant_id="t1")
        eng.register_role("r-dev", "Developer", kind=RoleKind.DEVELOPER,
                          permissions=["connector:use", "connector:read"])
        eng.bind_role("b-dev", "dev-op", "r-dev",
                      scope_kind=AuthContextKind.ENVIRONMENT, scope_ref_id="dev")

        # DENY rule for connector:use in prod environment
        eng.add_permission_rule("deny-prod-connector", "connector", "use",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.ENVIRONMENT,
                                scope_ref_id="prod")

        # Dev can use connectors in dev
        ev_dev = eng.evaluate_access("req-dev", "dev-op", "connector", "use",
                                      scope_kind=AuthContextKind.ENVIRONMENT,
                                      scope_ref_id="dev")
        assert ev_dev.decision == AccessDecision.ALLOWED

        # Dev cannot use connectors in prod (DENY rule)
        ev_prod = eng.evaluate_access("req-prod", "dev-op", "connector", "use",
                                       scope_kind=AuthContextKind.ENVIRONMENT,
                                       scope_ref_id="prod")
        assert ev_prod.decision == AccessDecision.DENIED

    def test_dev_denied_even_with_wildcard_role(self, env):
        _, eng = env
        eng.register_identity("dev-op", "DevOperator",
                               kind=IdentityKind.OPERATOR, tenant_id="t1")
        eng.register_role("r-super", "Super", permissions=["*:*"])
        eng.bind_role("b-super", "dev-op", "r-super",
                      scope_kind=AuthContextKind.GLOBAL)
        eng.add_permission_rule("deny-prod", "connector", "use",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.ENVIRONMENT,
                                scope_ref_id="prod")
        ev = eng.evaluate_access("req-prod", "dev-op", "connector", "use",
                                  scope_kind=AuthContextKind.ENVIRONMENT,
                                  scope_ref_id="prod")
        assert ev.decision == AccessDecision.DENIED


# =====================================================================
# 16. Golden Scenario 3: Temporary delegation allows bounded intervention
# =====================================================================


class TestGoldenScenario3TemporaryDelegation:
    def test_delegate_use_revoke_deny(self, env):
        _, eng = env
        eng.register_identity("manager", "Manager", tenant_id="t1")
        eng.register_identity("agent", "Agent", tenant_id="t1")
        eng.register_role("r-campaign", "CampaignOps",
                          permissions=["campaign:write", "campaign:read"])
        eng.bind_role("b-mgr", "manager", "r-campaign",
                      scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws-1")

        # Agent cannot access before delegation
        ev_before = eng.evaluate_access("req-0", "agent", "campaign", "write",
                                         scope_kind=AuthContextKind.WORKSPACE,
                                         scope_ref_id="ws-1")
        assert ev_before.decision == AccessDecision.DENIED

        # Delegate to agent
        eng.delegate_permission("del-temp", "manager", "agent", "r-campaign",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1",
                                 expires_at="2099-12-31T23:59:59+00:00")

        # Agent can access during delegation
        ev_during = eng.evaluate_access("req-1", "agent", "campaign", "write",
                                         scope_kind=AuthContextKind.WORKSPACE,
                                         scope_ref_id="ws-1")
        assert ev_during.decision == AccessDecision.ALLOWED

        # Revoke delegation
        eng.revoke_delegation("del-temp")

        # Agent denied after revocation
        ev_after = eng.evaluate_access("req-2", "agent", "campaign", "write",
                                        scope_kind=AuthContextKind.WORKSPACE,
                                        scope_ref_id="ws-1")
        assert ev_after.decision == AccessDecision.DENIED

    def test_delegation_status_transitions(self, env):
        _, eng = env
        eng.register_identity("m", "M", tenant_id="t1")
        eng.register_identity("a", "A", tenant_id="t1")
        eng.register_role("r", "R", permissions=["campaign:write"])

        d = eng.delegate_permission("del-1", "m", "a", "r")
        assert d.status == DelegationStatus.ACTIVE

        d_revoked = eng.revoke_delegation("del-1")
        assert d_revoked.status == DelegationStatus.REVOKED

        # Cannot re-activate
        with pytest.raises(RuntimeCoreInvariantError):
            eng.revoke_delegation("del-1")


# =====================================================================
# 17. Golden Scenario 4: Budget change requires privileged role
# =====================================================================


class TestGoldenScenario4BudgetRequiresApproval:
    def test_budget_modify_requires_approval(self, env):
        _, eng = env
        eng.register_identity("finance-user", "Finance",
                               kind=IdentityKind.HUMAN, tenant_id="t1")
        eng.register_role("r-finance", "Finance", kind=RoleKind.OPERATOR,
                          permissions=["budget:read", "budget:modify"])
        eng.bind_role("b-fin", "finance-user", "r-finance",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.add_permission_rule("ra-budget", "budget", "modify",
                                PermissionEffect.REQUIRE_APPROVAL,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")

        ev = eng.evaluate_access("req-budget", "finance-user", "budget", "modify",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.REQUIRES_APPROVAL

    def test_budget_read_still_allowed(self, env):
        _, eng = env
        eng.register_identity("finance-user", "Finance", tenant_id="t1")
        eng.register_role("r-finance", "Finance",
                          permissions=["budget:read", "budget:modify"])
        eng.bind_role("b-fin", "finance-user", "r-finance",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.add_permission_rule("ra-budget", "budget", "modify",
                                PermissionEffect.REQUIRE_APPROVAL,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")

        ev = eng.evaluate_access("req-read", "finance-user", "budget", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_budget_deny_overrides_require_approval(self, env):
        _, eng = env
        eng.register_identity("user", "User", tenant_id="t1")
        eng.register_role("r", "R", permissions=["budget:modify"])
        eng.bind_role("b", "user", "r",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.add_permission_rule("ra", "budget", "modify",
                                PermissionEffect.REQUIRE_APPROVAL,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        eng.add_permission_rule("deny", "budget", "modify",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")

        ev = eng.evaluate_access("req-1", "user", "budget", "modify",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED


# =====================================================================
# 18. Golden Scenario 5: Expired delegation stops access immediately
# =====================================================================


class TestGoldenScenario5ExpiredDelegation:
    def test_expired_delegation_denies(self, env):
        _, eng = env
        eng.register_identity("owner", "Owner", tenant_id="t1")
        eng.register_identity("temp", "Temp", tenant_id="t1")
        eng.register_role("r-ops", "Ops", permissions=["campaign:write"])

        eng.delegate_permission("del-exp", "owner", "temp", "r-ops",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")

        # Access allowed while active
        ev_active = eng.evaluate_access("req-a", "temp", "campaign", "write",
                                         scope_kind=AuthContextKind.WORKSPACE,
                                         scope_ref_id="ws-1")
        assert ev_active.decision == AccessDecision.ALLOWED

        # Expire
        eng.expire_delegation("del-exp")

        # Access denied after expiry
        ev_expired = eng.evaluate_access("req-b", "temp", "campaign", "write",
                                          scope_kind=AuthContextKind.WORKSPACE,
                                          scope_ref_id="ws-1")
        assert ev_expired.decision == AccessDecision.DENIED

    def test_expired_not_in_active_delegations(self, env):
        _, eng = env
        eng.register_identity("o", "O", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=[])
        eng.delegate_permission("d1", "o", "t", "r")
        eng.expire_delegation("d1")
        active = eng.active_delegations_for_identity("t")
        assert len(active) == 0

    def test_expired_not_in_effective_permissions(self, env):
        _, eng = env
        eng.register_identity("o", "O", tenant_id="t1")
        eng.register_identity("t", "T", tenant_id="t1")
        eng.register_role("r", "R", permissions=["special:perm"])
        eng.delegate_permission("d1", "o", "t", "r",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        eng.expire_delegation("d1")
        perms = eng.list_effective_permissions("t",
                                               AuthContextKind.WORKSPACE, "ws-1")
        assert "special:perm" not in perms


# =====================================================================
# 19. Golden Scenario 6: Scope hierarchy — tenant applies to sub-scopes
# =====================================================================


class TestGoldenScenario6ScopeHierarchy:
    def test_tenant_binding_covers_workspace_and_environment(self, env):
        _, eng = env
        eng.register_identity("u1", "User1", tenant_id="t1")
        eng.register_role("r-tenant", "TenantRole",
                          permissions=["resource:read", "resource:write"])
        eng.bind_role("b-t", "u1", "r-tenant",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")

        # Workspace access
        ev_ws = eng.evaluate_access("req-ws", "u1", "resource", "read",
                                     scope_kind=AuthContextKind.WORKSPACE,
                                     scope_ref_id="ws-1")
        assert ev_ws.decision == AccessDecision.ALLOWED

        # Environment access
        ev_env = eng.evaluate_access("req-env", "u1", "resource", "write",
                                      scope_kind=AuthContextKind.ENVIRONMENT,
                                      scope_ref_id="env-1")
        assert ev_env.decision == AccessDecision.ALLOWED

    def test_workspace_binding_covers_environment_not_tenant(self, env):
        _, eng = env
        eng.register_identity("u1", "User1", tenant_id="t1")
        eng.register_role("r-ws", "WSRole",
                          permissions=["resource:read"])
        eng.bind_role("b-ws", "u1", "r-ws",
                      scope_kind=AuthContextKind.WORKSPACE, scope_ref_id="ws-1")

        # Environment: allowed
        ev_env = eng.evaluate_access("req-env", "u1", "resource", "read",
                                      scope_kind=AuthContextKind.ENVIRONMENT,
                                      scope_ref_id="env-1")
        assert ev_env.decision == AccessDecision.ALLOWED

        # Tenant: denied
        ev_t = eng.evaluate_access("req-t", "u1", "resource", "read",
                                    scope_kind=AuthContextKind.TENANT,
                                    scope_ref_id="t1")
        assert ev_t.decision == AccessDecision.DENIED

    def test_global_binding_covers_all(self, env):
        _, eng = env
        eng.register_identity("u1", "User1", tenant_id="t1")
        eng.register_role("r-g", "GlobalRole",
                          permissions=["resource:read"])
        eng.bind_role("b-g", "u1", "r-g",
                      scope_kind=AuthContextKind.GLOBAL)

        for sk, ref in [
            (AuthContextKind.GLOBAL, "*"),
            (AuthContextKind.TENANT, "t1"),
            (AuthContextKind.WORKSPACE, "ws-1"),
            (AuthContextKind.ENVIRONMENT, "env-1"),
        ]:
            ev = eng.evaluate_access(f"req-{sk.value}-{ref}", "u1",
                                      "resource", "read",
                                      scope_kind=sk, scope_ref_id=ref)
            assert ev.decision == AccessDecision.ALLOWED, \
                f"Expected ALLOWED for {sk.value}/{ref}"

    def test_delegation_scope_hierarchy_applies(self, env):
        _, eng = env
        eng.register_identity("from", "From", tenant_id="t1")
        eng.register_identity("to", "To", tenant_id="t1")
        eng.register_role("r-t", "TenantRole",
                          permissions=["resource:write"])
        eng.delegate_permission("del-1", "from", "to", "r-t",
                                 scope_kind=AuthContextKind.TENANT,
                                 scope_ref_id="t1")

        # Workspace access via tenant delegation
        ev_ws = eng.evaluate_access("req-ws", "to", "resource", "write",
                                     scope_kind=AuthContextKind.WORKSPACE,
                                     scope_ref_id="ws-1")
        assert ev_ws.decision == AccessDecision.ALLOWED

        # Environment access via tenant delegation
        ev_env = eng.evaluate_access("req-env", "to", "resource", "write",
                                      scope_kind=AuthContextKind.ENVIRONMENT,
                                      scope_ref_id="env-1")
        assert ev_env.decision == AccessDecision.ALLOWED


# =====================================================================
# 20. Edge Cases
# =====================================================================


class TestEdgeCases:
    def test_identity_with_no_role_bindings_denied(self, env):
        _, eng = env
        _setup_identity(eng)
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_role_with_empty_permissions_denied(self, env):
        _, eng = env
        _setup_identity(eng)
        eng.register_role("r-empty", "Empty", permissions=[])
        eng.bind_role("b1", "id-1", "r-empty",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_disabled_identity_with_bindings_denied(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.disable_identity("id-1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_re_enabled_identity_allowed(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.disable_identity("id-1")
        eng.enable_identity("id-1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_multiple_deny_rules_still_denied(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("deny-1", "campaign", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.add_permission_rule("deny-2", "campaign", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.GLOBAL)
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_deny_rule_on_different_resource_does_not_block(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("deny-other", "budget", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_deny_rule_on_different_action_does_not_block(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        eng.add_permission_rule("deny-write", "campaign", "write",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.ALLOWED

    def test_wildcard_deny_blocks_all_actions(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read", "campaign:write"])
        eng.add_permission_rule("deny-all-campaign", "campaign", "*",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev_read = eng.evaluate_access("req-r", "id-1", "campaign", "read",
                                       scope_kind=AuthContextKind.TENANT,
                                       scope_ref_id="t1")
        ev_write = eng.evaluate_access("req-w", "id-1", "campaign", "write",
                                        scope_kind=AuthContextKind.TENANT,
                                        scope_ref_id="t1")
        assert ev_read.decision == AccessDecision.DENIED
        assert ev_write.decision == AccessDecision.DENIED

    def test_wildcard_resource_deny_blocks_all_resources(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read", "budget:read"])
        eng.add_permission_rule("deny-star", "*", "read",
                                PermissionEffect.DENY,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_snapshot_after_complex_state(self, env):
        _, eng = env
        eng.register_identity("a", "A", tenant_id="t1")
        eng.register_identity("b", "B", tenant_id="t1")
        eng.register_role("r1", "R1", permissions=["x:y"])
        eng.register_role("r2", "R2", permissions=["a:b"])
        eng.bind_role("b1", "a", "r1",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.bind_role("b2", "b", "r2",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.delegate_permission("d1", "a", "b", "r1",
                                 scope_kind=AuthContextKind.WORKSPACE,
                                 scope_ref_id="ws-1")
        eng.add_permission_rule("rule-1", "x", "y", PermissionEffect.ALLOW,
                                scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.evaluate_access("req-1", "a", "x", "y",
                            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.evaluate_access("req-2", "b", "z", "z",
                            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.detect_violations()

        snap = eng.access_snapshot("snap-complex", "t1")
        assert snap.total_identities == 2
        assert snap.total_roles == 2
        assert snap.total_bindings == 2
        assert snap.total_rules == 1
        assert snap.active_delegations == 1
        assert snap.total_evaluations == 2
        assert snap.total_violations >= 1

    def test_allow_rule_without_matching_role_permission_denied(self, env):
        """An ALLOW rule exists but the identity lacks the role permission."""
        _, eng = env
        _setup_identity(eng)
        eng.register_role("r-no-perm", "NoPerm", permissions=[])
        eng.bind_role("b1", "id-1", "r-no-perm",
                      scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        eng.add_permission_rule("allow-campaign", "campaign", "read",
                                PermissionEffect.ALLOW,
                                scope_kind=AuthContextKind.TENANT,
                                scope_ref_id="t1")
        ev = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                  scope_kind=AuthContextKind.TENANT,
                                  scope_ref_id="t1")
        assert ev.decision == AccessDecision.DENIED

    def test_multiple_evaluations_independent(self, env):
        _, eng = env
        _setup_full(eng, permissions=["campaign:read"])
        ev1 = eng.evaluate_access("req-1", "id-1", "campaign", "read",
                                   scope_kind=AuthContextKind.TENANT,
                                   scope_ref_id="t1")
        ev2 = eng.evaluate_access("req-2", "id-1", "campaign", "write",
                                   scope_kind=AuthContextKind.TENANT,
                                   scope_ref_id="t1")
        assert ev1.decision == AccessDecision.ALLOWED
        assert ev2.decision == AccessDecision.DENIED
        assert ev1.evaluation_id != ev2.evaluation_id

    def test_cross_tenant_violation_reason(self, env):
        _, eng = env
        eng.register_identity("cross", "Cross", tenant_id="t2")
        eng.evaluate_access("req-cross", "cross", "campaign", "read",
                            scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        violations = eng.detect_violations()
        assert len(violations) >= 1
        cross_v = [v for v in violations if v.identity_id == "cross"]
        assert len(cross_v) >= 1
        assert cross_v[0].reason == "cross-tenant access attempt"
        assert "t2" not in cross_v[0].reason
