"""Tests for access / RBAC / delegation runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.access_runtime import (
    AccessAuditRecord,
    AccessDecision,
    AccessEvaluation,
    AccessRequest,
    AccessSnapshot,
    AccessViolation,
    AuthContextKind,
    DelegationRecord,
    DelegationStatus,
    IdentityKind,
    IdentityRecord,
    PermissionEffect,
    PermissionRule,
    RoleBinding,
    RoleKind,
    RoleRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _identity(**overrides) -> IdentityRecord:
    defaults = dict(identity_id="id-001", name="alice", kind=IdentityKind.HUMAN, tenant_id="tenant-001", created_at=TS)
    defaults.update(overrides)
    return IdentityRecord(**defaults)


def _role(**overrides) -> RoleRecord:
    defaults = dict(role_id="role-001", name="Admin", kind=RoleKind.ADMIN, created_at=TS)
    defaults.update(overrides)
    return RoleRecord(**defaults)


def _permission_rule(**overrides) -> PermissionRule:
    defaults = dict(
        rule_id="rule-001",
        resource_type="workspace",
        action="read",
        scope_ref_id="scope-001",
        created_at=TS,
    )
    defaults.update(overrides)
    return PermissionRule(**defaults)


def _role_binding(**overrides) -> RoleBinding:
    defaults = dict(
        binding_id="bind-001",
        identity_id="id-001",
        role_id="role-001",
        scope_ref_id="scope-001",
        bound_at=TS,
    )
    defaults.update(overrides)
    return RoleBinding(**defaults)


def _delegation(**overrides) -> DelegationRecord:
    defaults = dict(
        delegation_id="del-001",
        from_identity_id="id-001",
        to_identity_id="id-002",
        role_id="role-001",
        scope_ref_id="scope-001",
        delegated_at=TS,
    )
    defaults.update(overrides)
    return DelegationRecord(**defaults)


def _access_request(**overrides) -> AccessRequest:
    defaults = dict(
        request_id="req-001",
        identity_id="id-001",
        resource_type="workspace",
        action="read",
        requested_at=TS,
    )
    defaults.update(overrides)
    return AccessRequest(**defaults)


def _evaluation(**overrides) -> AccessEvaluation:
    defaults = dict(
        evaluation_id="eval-001",
        request_id="req-001",
        evaluated_at=TS,
    )
    defaults.update(overrides)
    return AccessEvaluation(**defaults)


def _violation(**overrides) -> AccessViolation:
    defaults = dict(
        violation_id="viol-001",
        identity_id="id-001",
        resource_type="workspace",
        action="read",
        scope_ref_id="scope-001",
        detected_at=TS,
    )
    defaults.update(overrides)
    return AccessViolation(**defaults)


def _snapshot(**overrides) -> AccessSnapshot:
    defaults = dict(snapshot_id="snap-001", captured_at=TS)
    defaults.update(overrides)
    return AccessSnapshot(**defaults)


def _audit(**overrides) -> AccessAuditRecord:
    defaults = dict(
        audit_id="aud-001",
        identity_id="id-001",
        action="read",
        resource_type="workspace",
        scope_ref_id="scope-001",
        recorded_at=TS,
    )
    defaults.update(overrides)
    return AccessAuditRecord(**defaults)


# ---------------------------------------------------------------------------
# Enum members
# ---------------------------------------------------------------------------


class TestEnumMembers:
    def test_identity_kind_members(self):
        expected = {"HUMAN", "SERVICE", "OPERATOR", "SYSTEM", "API_KEY"}
        assert {m.name for m in IdentityKind} == expected
        assert len(IdentityKind) == 5

    def test_role_kind_members(self):
        expected = {"ADMIN", "OPERATOR", "DEVELOPER", "VIEWER", "AUDITOR", "SERVICE", "CUSTOM"}
        assert {m.name for m in RoleKind} == expected
        assert len(RoleKind) == 7

    def test_permission_effect_members(self):
        expected = {"ALLOW", "DENY", "REQUIRE_APPROVAL"}
        assert {m.name for m in PermissionEffect} == expected
        assert len(PermissionEffect) == 3

    def test_access_decision_members(self):
        expected = {"ALLOWED", "DENIED", "REQUIRES_APPROVAL", "EXPIRED", "VIOLATION"}
        assert {m.name for m in AccessDecision} == expected
        assert len(AccessDecision) == 5

    def test_delegation_status_members(self):
        expected = {"ACTIVE", "EXPIRED", "REVOKED"}
        assert {m.name for m in DelegationStatus} == expected
        assert len(DelegationStatus) == 3

    def test_auth_context_kind_members(self):
        expected = {"TENANT", "WORKSPACE", "ENVIRONMENT", "GLOBAL"}
        assert {m.name for m in AuthContextKind} == expected
        assert len(AuthContextKind) == 4


# ---------------------------------------------------------------------------
# Construction tests (one class per dataclass)
# ---------------------------------------------------------------------------


class TestIdentityRecordConstruction:
    def test_minimal(self):
        r = _identity()
        assert r.identity_id == "id-001"
        assert r.name == "alice"
        assert r.kind is IdentityKind.HUMAN
        assert r.tenant_id == "tenant-001"
        assert r.enabled is True
        assert r.created_at == TS
        assert r.metadata == {}

    def test_full(self):
        r = _identity(
            kind=IdentityKind.SERVICE,
            tenant_id="t-001",
            enabled=False,
            metadata={"source": "ldap"},
        )
        assert r.kind is IdentityKind.SERVICE
        assert r.tenant_id == "t-001"
        assert r.enabled is False
        assert r.metadata["source"] == "ldap"


class TestRoleRecordConstruction:
    def test_minimal(self):
        r = _role()
        assert r.role_id == "role-001"
        assert r.name == "Admin"
        assert r.kind is RoleKind.ADMIN
        assert r.permissions == ()
        assert r.description == ""
        assert r.created_at == TS
        assert r.metadata == {}

    def test_full(self):
        r = _role(
            kind=RoleKind.DEVELOPER,
            permissions=("read", "write"),
            description="Dev role",
            metadata={"tier": "standard"},
        )
        assert r.kind is RoleKind.DEVELOPER
        assert r.permissions == ("read", "write")
        assert r.description == "Dev role"
        assert r.metadata["tier"] == "standard"


class TestPermissionRuleConstruction:
    def test_minimal(self):
        p = _permission_rule()
        assert p.rule_id == "rule-001"
        assert p.resource_type == "workspace"
        assert p.action == "read"
        assert p.effect is PermissionEffect.DENY
        assert p.scope_kind is AuthContextKind.TENANT
        assert p.scope_ref_id == "scope-001"
        assert p.conditions == {}
        assert p.created_at == TS

    def test_full(self):
        p = _permission_rule(
            effect=PermissionEffect.DENY,
            scope_kind=AuthContextKind.WORKSPACE,
            scope_ref_id="ws-001",
            conditions={"ip_range": "10.0.0.0/8"},
        )
        assert p.effect is PermissionEffect.DENY
        assert p.scope_kind is AuthContextKind.WORKSPACE
        assert p.scope_ref_id == "ws-001"
        assert p.conditions["ip_range"] == "10.0.0.0/8"


class TestRoleBindingConstruction:
    def test_minimal(self):
        b = _role_binding()
        assert b.binding_id == "bind-001"
        assert b.identity_id == "id-001"
        assert b.role_id == "role-001"
        assert b.scope_kind is AuthContextKind.TENANT
        assert b.scope_ref_id == "scope-001"
        assert b.bound_at == TS

    def test_full(self):
        b = _role_binding(
            scope_kind=AuthContextKind.ENVIRONMENT,
            scope_ref_id="env-001",
        )
        assert b.scope_kind is AuthContextKind.ENVIRONMENT
        assert b.scope_ref_id == "env-001"


class TestDelegationRecordConstruction:
    def test_minimal(self):
        d = _delegation()
        assert d.delegation_id == "del-001"
        assert d.from_identity_id == "id-001"
        assert d.to_identity_id == "id-002"
        assert d.role_id == "role-001"
        assert d.scope_kind is AuthContextKind.WORKSPACE
        assert d.scope_ref_id == "scope-001"
        assert d.status is DelegationStatus.ACTIVE
        assert d.expires_at == ""
        assert d.delegated_at == TS
        assert d.revoked_at == ""
        assert d.metadata == {}

    def test_full(self):
        d = _delegation(
            scope_kind=AuthContextKind.GLOBAL,
            scope_ref_id="global-ref",
            status=DelegationStatus.REVOKED,
            expires_at=TS2,
            revoked_at=TS2,
            metadata={"reason": "policy change"},
        )
        assert d.scope_kind is AuthContextKind.GLOBAL
        assert d.status is DelegationStatus.REVOKED
        assert d.expires_at == TS2
        assert d.revoked_at == TS2
        assert d.metadata["reason"] == "policy change"


class TestAccessRequestConstruction:
    def test_minimal(self):
        r = _access_request()
        assert r.request_id == "req-001"
        assert r.identity_id == "id-001"
        assert r.resource_type == "workspace"
        assert r.action == "read"
        assert r.scope_kind is AuthContextKind.TENANT
        assert r.scope_ref_id == ""
        assert r.requested_at == TS

    def test_full(self):
        r = _access_request(
            scope_kind=AuthContextKind.WORKSPACE,
            scope_ref_id="ws-001",
        )
        assert r.scope_kind is AuthContextKind.WORKSPACE
        assert r.scope_ref_id == "ws-001"


class TestAccessEvaluationConstruction:
    def test_minimal(self):
        e = _evaluation()
        assert e.evaluation_id == "eval-001"
        assert e.request_id == "req-001"
        assert e.decision is AccessDecision.DENIED
        assert e.matching_rule_ids == ()
        assert e.matching_role_ids == ()
        assert e.reason == ""
        assert e.evaluated_at == TS

    def test_full(self):
        e = _evaluation(
            decision=AccessDecision.DENIED,
            matching_rule_ids=("rule-001", "rule-002"),
            matching_role_ids=("role-001",),
            reason="IP not in allowed range",
        )
        assert e.decision is AccessDecision.DENIED
        assert e.matching_rule_ids == ("rule-001", "rule-002")
        assert e.matching_role_ids == ("role-001",)
        assert e.reason == "IP not in allowed range"


class TestAccessViolationConstruction:
    def test_minimal(self):
        v = _violation()
        assert v.violation_id == "viol-001"
        assert v.identity_id == "id-001"
        assert v.resource_type == "workspace"
        assert v.action == "read"
        assert v.scope_kind is AuthContextKind.TENANT
        assert v.scope_ref_id == "scope-001"
        assert v.reason == ""
        assert v.detected_at == TS
        assert v.metadata == {}

    def test_full(self):
        v = _violation(
            scope_kind=AuthContextKind.WORKSPACE,
            scope_ref_id="ws-001",
            resource_type="secret",
            action="delete",
            reason="Unauthorized secret deletion",
            metadata={"severity": "critical"},
        )
        assert v.scope_kind is AuthContextKind.WORKSPACE
        assert v.scope_ref_id == "ws-001"
        assert v.resource_type == "secret"
        assert v.action == "delete"
        assert v.reason == "Unauthorized secret deletion"
        assert v.metadata["severity"] == "critical"


class TestAccessSnapshotConstruction:
    def test_minimal(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_identities == 0
        assert s.total_roles == 0
        assert s.total_bindings == 0
        assert s.total_rules == 0
        assert s.active_delegations == 0
        assert s.total_violations == 0
        assert s.total_evaluations == 0
        assert s.captured_at == TS
        assert s.metadata == {}

    def test_full(self):
        s = _snapshot(
            total_identities=50,
            total_roles=10,
            total_bindings=120,
            total_rules=35,
            active_delegations=5,
            total_violations=3,
            total_evaluations=1000,
            metadata={"region": "us-east"},
        )
        assert s.total_identities == 50
        assert s.total_roles == 10
        assert s.total_bindings == 120
        assert s.total_rules == 35
        assert s.active_delegations == 5
        assert s.total_violations == 3
        assert s.total_evaluations == 1000
        assert s.metadata["region"] == "us-east"


class TestAccessAuditRecordConstruction:
    def test_minimal(self):
        a = _audit()
        assert a.audit_id == "aud-001"
        assert a.identity_id == "id-001"
        assert a.action == "read"
        assert a.resource_type == "workspace"
        assert a.decision is AccessDecision.DENIED
        assert a.scope_kind is AuthContextKind.TENANT
        assert a.scope_ref_id == "scope-001"
        assert a.recorded_at == TS
        assert a.metadata == {}

    def test_full(self):
        a = _audit(
            decision=AccessDecision.VIOLATION,
            scope_kind=AuthContextKind.GLOBAL,
            scope_ref_id="global-ref",
            action="write",
            resource_type="budget",
            metadata={"alert": True},
        )
        assert a.decision is AccessDecision.VIOLATION
        assert a.scope_kind is AuthContextKind.GLOBAL
        assert a.scope_ref_id == "global-ref"
        assert a.action == "write"
        assert a.resource_type == "budget"
        assert a.metadata["alert"] is True


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    def test_identity_record_frozen(self):
        r = _identity()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            r.name = "changed"  # type: ignore[misc]

    def test_role_record_frozen(self):
        r = _role()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            r.name = "changed"  # type: ignore[misc]

    def test_permission_rule_frozen(self):
        p = _permission_rule()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            p.action = "changed"  # type: ignore[misc]

    def test_role_binding_frozen(self):
        b = _role_binding()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            b.role_id = "changed"  # type: ignore[misc]

    def test_delegation_record_frozen(self):
        d = _delegation()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            d.status = DelegationStatus.REVOKED  # type: ignore[misc]

    def test_access_request_frozen(self):
        r = _access_request()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            r.action = "changed"  # type: ignore[misc]

    def test_access_evaluation_frozen(self):
        e = _evaluation()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            e.reason = "changed"  # type: ignore[misc]

    def test_access_violation_frozen(self):
        v = _violation()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            v.reason = "changed"  # type: ignore[misc]

    def test_access_snapshot_frozen(self):
        s = _snapshot()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            s.total_identities = 99  # type: ignore[misc]

    def test_access_audit_record_frozen(self):
        a = _audit()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            a.audit_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# require_non_empty_text (only * fields)
# ---------------------------------------------------------------------------


class TestRequireNonEmptyText:
    # IdentityRecord
    def test_identity_empty_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _identity(identity_id="")

    def test_identity_whitespace_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _identity(identity_id="   ")

    def test_identity_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            _identity(name="")

    # RoleRecord
    def test_role_empty_id(self):
        with pytest.raises(ValueError, match="role_id"):
            _role(role_id="")

    def test_role_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            _role(name="")

    # PermissionRule
    def test_permission_rule_empty_rule_id(self):
        with pytest.raises(ValueError, match="rule_id"):
            _permission_rule(rule_id="")

    def test_permission_rule_empty_resource_type(self):
        with pytest.raises(ValueError, match="resource_type"):
            _permission_rule(resource_type="")

    def test_permission_rule_empty_action(self):
        with pytest.raises(ValueError, match="action"):
            _permission_rule(action="")

    # RoleBinding
    def test_role_binding_empty_binding_id(self):
        with pytest.raises(ValueError, match="binding_id"):
            _role_binding(binding_id="")

    def test_role_binding_empty_identity_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _role_binding(identity_id="")

    def test_role_binding_empty_role_id(self):
        with pytest.raises(ValueError, match="role_id"):
            _role_binding(role_id="")

    # DelegationRecord
    def test_delegation_empty_delegation_id(self):
        with pytest.raises(ValueError, match="delegation_id"):
            _delegation(delegation_id="")

    def test_delegation_empty_from_identity_id(self):
        with pytest.raises(ValueError, match="from_identity_id"):
            _delegation(from_identity_id="")

    def test_delegation_empty_to_identity_id(self):
        with pytest.raises(ValueError, match="to_identity_id"):
            _delegation(to_identity_id="")

    def test_delegation_empty_role_id(self):
        with pytest.raises(ValueError, match="role_id"):
            _delegation(role_id="")

    # AccessRequest
    def test_access_request_empty_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _access_request(request_id="")

    def test_access_request_empty_identity_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _access_request(identity_id="")

    def test_access_request_empty_resource_type(self):
        with pytest.raises(ValueError, match="resource_type"):
            _access_request(resource_type="")

    def test_access_request_empty_action(self):
        with pytest.raises(ValueError, match="action"):
            _access_request(action="")

    # AccessEvaluation
    def test_evaluation_empty_evaluation_id(self):
        with pytest.raises(ValueError, match="evaluation_id"):
            _evaluation(evaluation_id="")

    def test_evaluation_empty_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _evaluation(request_id="")

    # AccessViolation
    def test_violation_empty_violation_id(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="")

    def test_violation_empty_identity_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _violation(identity_id="")

    # AccessSnapshot
    def test_snapshot_empty_snapshot_id(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    # AccessAuditRecord
    def test_audit_empty_audit_id(self):
        with pytest.raises(ValueError, match="audit_id"):
            _audit(audit_id="")

    def test_audit_empty_identity_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _audit(identity_id="")

    # Whitespace-only counts as empty
    def test_identity_tab_newline_id(self):
        with pytest.raises(ValueError, match="identity_id"):
            _identity(identity_id="\t\n ")

    def test_role_whitespace_name(self):
        with pytest.raises(ValueError, match="name"):
            _role(name="   \t")


# ---------------------------------------------------------------------------
# Optional fields accept empty string (no ValueError)
# ---------------------------------------------------------------------------


class TestOptionalFieldsAcceptEmpty:
    def test_identity_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _identity(tenant_id="")

    def test_role_description_empty(self):
        r = _role(description="")
        assert r.description == ""

    def test_permission_rule_scope_ref_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _permission_rule(scope_ref_id="")

    def test_role_binding_scope_ref_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _role_binding(scope_ref_id="")

    def test_delegation_scope_ref_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _delegation(scope_ref_id="")

    def test_delegation_expires_at_empty(self):
        d = _delegation(expires_at="")
        assert d.expires_at == ""

    def test_delegation_revoked_at_empty(self):
        d = _delegation(revoked_at="")
        assert d.revoked_at == ""

    def test_access_request_scope_ref_id_empty(self):
        r = _access_request(scope_ref_id="")
        assert r.scope_ref_id == ""

    def test_evaluation_reason_empty(self):
        e = _evaluation(reason="")
        assert e.reason == ""

    def test_violation_scope_ref_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _violation(scope_ref_id="")

    def test_violation_reason_empty(self):
        v = _violation(reason="")
        assert v.reason == ""

    def test_violation_resource_type_empty_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            _violation(resource_type="")

    def test_violation_action_empty_rejected(self):
        with pytest.raises(ValueError, match="action"):
            _violation(action="")

    def test_audit_scope_ref_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scope_ref_id"):
            _audit(scope_ref_id="")

    def test_audit_resource_type_empty_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            _audit(resource_type="")

    def test_audit_action_empty_rejected(self):
        with pytest.raises(ValueError, match="action"):
            _audit(action="")


# ---------------------------------------------------------------------------
# require_datetime_text
# ---------------------------------------------------------------------------


class TestRequireDatetimeText:
    def test_identity_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _identity(created_at="not-a-date")

    def test_role_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _role(created_at="nope")

    def test_permission_rule_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _permission_rule(created_at="invalid")

    def test_role_binding_invalid_bound_at(self):
        with pytest.raises(ValueError, match="bound_at"):
            _role_binding(bound_at="bad")

    def test_delegation_invalid_delegated_at(self):
        with pytest.raises(ValueError, match="delegated_at"):
            _delegation(delegated_at="bad")

    def test_access_request_invalid_requested_at(self):
        with pytest.raises(ValueError, match="requested_at"):
            _access_request(requested_at="bad")

    def test_evaluation_invalid_evaluated_at(self):
        with pytest.raises(ValueError, match="evaluated_at"):
            _evaluation(evaluated_at="bad")

    def test_violation_invalid_detected_at(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="bad")

    def test_snapshot_invalid_captured_at(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad")

    def test_audit_invalid_recorded_at(self):
        with pytest.raises(ValueError, match="recorded_at"):
            _audit(recorded_at="bad")

    def test_iso_z_suffix_accepted(self):
        r = _identity(created_at="2025-06-01T12:00:00Z")
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _identity(created_at="")


# ---------------------------------------------------------------------------
# Enum type validation
# ---------------------------------------------------------------------------


class TestEnumTypeValidation:
    def test_identity_kind_string_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _identity(kind="human")

    def test_role_kind_string_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _role(kind="admin")

    def test_permission_effect_string_rejected(self):
        with pytest.raises(ValueError, match="effect"):
            _permission_rule(effect="allow")

    def test_permission_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _permission_rule(scope_kind="tenant")

    def test_role_binding_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _role_binding(scope_kind="tenant")

    def test_delegation_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _delegation(scope_kind="tenant")

    def test_delegation_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _delegation(status="active")

    def test_access_request_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _access_request(scope_kind="workspace")

    def test_evaluation_decision_string_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _evaluation(decision="allowed")

    def test_violation_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _violation(scope_kind="tenant")

    def test_audit_decision_string_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _audit(decision="allowed")

    def test_audit_scope_kind_string_rejected(self):
        with pytest.raises(ValueError, match="scope_kind"):
            _audit(scope_kind="global")

    def test_identity_enabled_non_bool_rejected(self):
        with pytest.raises(ValueError, match="enabled"):
            _identity(enabled=1)


# ---------------------------------------------------------------------------
# require_non_negative_int
# ---------------------------------------------------------------------------


class TestRequireNonNegativeInt:
    # AccessSnapshot fields
    def test_snapshot_total_identities_zero(self):
        s = _snapshot(total_identities=0)
        assert s.total_identities == 0

    def test_snapshot_total_identities_positive(self):
        s = _snapshot(total_identities=10)
        assert s.total_identities == 10

    def test_snapshot_total_identities_negative_rejected(self):
        with pytest.raises(ValueError, match="total_identities"):
            _snapshot(total_identities=-1)

    def test_snapshot_total_roles_negative_rejected(self):
        with pytest.raises(ValueError, match="total_roles"):
            _snapshot(total_roles=-1)

    def test_snapshot_total_bindings_negative_rejected(self):
        with pytest.raises(ValueError, match="total_bindings"):
            _snapshot(total_bindings=-1)

    def test_snapshot_total_rules_negative_rejected(self):
        with pytest.raises(ValueError, match="total_rules"):
            _snapshot(total_rules=-1)

    def test_snapshot_active_delegations_negative_rejected(self):
        with pytest.raises(ValueError, match="active_delegations"):
            _snapshot(active_delegations=-1)

    def test_snapshot_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=-1)

    def test_snapshot_total_evaluations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_evaluations"):
            _snapshot(total_evaluations=-1)

    def test_bool_rejected_as_int(self):
        with pytest.raises(ValueError, match="total_identities"):
            _snapshot(total_identities=True)


# ---------------------------------------------------------------------------
# freeze_value (metadata, tuple fields)
# ---------------------------------------------------------------------------


class TestFreezeValue:
    def test_identity_metadata_frozen(self):
        r = _identity(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["new"] = "x"  # type: ignore[index]

    def test_role_metadata_frozen(self):
        r = _role(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_permission_rule_conditions_frozen(self):
        p = _permission_rule(conditions={"ip": "10.0.0.0/8"})
        assert isinstance(p.conditions, MappingProxyType)

    def test_delegation_metadata_frozen(self):
        d = _delegation(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_violation_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_snapshot_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_audit_metadata_frozen(self):
        a = _audit(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_role_permissions_tuple(self):
        r = _role(permissions=["read", "write"])
        assert isinstance(r.permissions, tuple)
        assert r.permissions == ("read", "write")

    def test_evaluation_matching_rule_ids_tuple(self):
        e = _evaluation(matching_rule_ids=["rule-001", "rule-002"])
        assert isinstance(e.matching_rule_ids, tuple)
        assert e.matching_rule_ids == ("rule-001", "rule-002")

    def test_evaluation_matching_role_ids_tuple(self):
        e = _evaluation(matching_role_ids=["role-001"])
        assert isinstance(e.matching_role_ids, tuple)
        assert e.matching_role_ids == ("role-001",)

    def test_nested_metadata_frozen(self):
        r = _identity(metadata={"nested": {"inner": 1}})
        assert isinstance(r.metadata["nested"], MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["nested"]["new"] = 2  # type: ignore[index]

    def test_list_to_tuple_in_metadata(self):
        r = _identity(metadata={"tags": [1, 2, 3]})
        assert isinstance(r.metadata["tags"], tuple)
        assert r.metadata["tags"] == (1, 2, 3)

    def test_empty_metadata_is_mapping_proxy(self):
        r = _identity()
        assert isinstance(r.metadata, MappingProxyType)

    def test_empty_conditions_is_mapping_proxy(self):
        p = _permission_rule()
        assert isinstance(p.conditions, MappingProxyType)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_identity_defaults(self):
        r = _identity()
        assert r.tenant_id == "tenant-001"
        assert r.enabled is True
        assert r.metadata == {}

    def test_role_defaults(self):
        r = _role()
        assert r.permissions == ()
        assert r.description == ""
        assert r.metadata == {}

    def test_permission_rule_defaults(self):
        p = _permission_rule()
        assert p.effect is PermissionEffect.DENY
        assert p.scope_kind is AuthContextKind.TENANT
        assert p.scope_ref_id == "scope-001"
        assert p.conditions == {}

    def test_role_binding_defaults(self):
        b = _role_binding()
        assert b.scope_kind is AuthContextKind.TENANT
        assert b.scope_ref_id == "scope-001"

    def test_delegation_defaults(self):
        d = _delegation()
        assert d.scope_kind is AuthContextKind.WORKSPACE
        assert d.scope_ref_id == "scope-001"
        assert d.status is DelegationStatus.ACTIVE
        assert d.expires_at == ""
        assert d.revoked_at == ""
        assert d.metadata == {}

    def test_access_request_defaults(self):
        r = _access_request()
        assert r.scope_kind is AuthContextKind.TENANT
        assert r.scope_ref_id == ""

    def test_evaluation_defaults(self):
        e = _evaluation()
        assert e.decision is AccessDecision.DENIED
        assert e.matching_rule_ids == ()
        assert e.matching_role_ids == ()
        assert e.reason == ""

    def test_violation_defaults(self):
        v = _violation()
        assert v.scope_kind is AuthContextKind.TENANT
        assert v.scope_ref_id == "scope-001"
        assert v.reason == ""
        assert v.metadata == {}

    def test_snapshot_defaults(self):
        s = _snapshot()
        assert s.total_identities == 0
        assert s.total_roles == 0
        assert s.total_bindings == 0
        assert s.total_rules == 0
        assert s.active_delegations == 0
        assert s.total_violations == 0
        assert s.total_evaluations == 0
        assert s.metadata == {}

    def test_audit_defaults(self):
        a = _audit()
        assert a.decision is AccessDecision.DENIED
        assert a.scope_kind is AuthContextKind.TENANT
        assert a.scope_ref_id == "scope-001"
        assert a.metadata == {}


# ---------------------------------------------------------------------------
# Edge-case boundaries
# ---------------------------------------------------------------------------


class TestEdgeCaseBoundaries:
    def test_all_identity_kind_values(self):
        for kind in IdentityKind:
            r = _identity(kind=kind)
            assert r.kind is kind

    def test_all_role_kind_values(self):
        for kind in RoleKind:
            r = _role(kind=kind)
            assert r.kind is kind

    def test_all_permission_effect_values(self):
        for effect in PermissionEffect:
            p = _permission_rule(effect=effect)
            assert p.effect is effect

    def test_all_access_decision_values(self):
        for decision in AccessDecision:
            e = _evaluation(decision=decision)
            assert e.decision is decision

    def test_all_delegation_status_values(self):
        for status in DelegationStatus:
            d = _delegation(status=status)
            assert d.status is status

    def test_all_auth_context_kind_values(self):
        for kind in AuthContextKind:
            b = _role_binding(scope_kind=kind)
            assert b.scope_kind is kind

    def test_whitespace_only_id_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _identity(identity_id="\t\n ")

    def test_snapshot_zero_counts_accepted(self):
        s = _snapshot(
            total_identities=0,
            total_roles=0,
            total_bindings=0,
            total_rules=0,
            active_delegations=0,
            total_violations=0,
            total_evaluations=0,
        )
        assert s.total_identities == 0
        assert s.total_evaluations == 0

    def test_large_snapshot_counts(self):
        s = _snapshot(total_identities=999999, total_evaluations=999999)
        assert s.total_identities == 999999
        assert s.total_evaluations == 999999


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


class TestToDictSerialization:
    def test_identity_to_dict_preserves_enums(self):
        r = _identity(kind=IdentityKind.SERVICE, metadata={"k": "v"})
        d = r.to_dict()
        assert d["identity_id"] == "id-001"
        assert d["name"] == "alice"
        assert d["kind"] is IdentityKind.SERVICE
        assert d["metadata"] == {"k": "v"}
        assert isinstance(d["metadata"], dict)

    def test_role_to_dict_preserves_enums(self):
        r = _role(kind=RoleKind.AUDITOR, permissions=("read", "audit"))
        d = r.to_dict()
        assert d["kind"] is RoleKind.AUDITOR
        assert d["permissions"] == ["read", "audit"]
        assert isinstance(d["permissions"], list)

    def test_permission_rule_to_dict(self):
        p = _permission_rule(
            effect=PermissionEffect.REQUIRE_APPROVAL,
            scope_kind=AuthContextKind.ENVIRONMENT,
            conditions={"mfa": True},
        )
        d = p.to_dict()
        assert d["effect"] is PermissionEffect.REQUIRE_APPROVAL
        assert d["scope_kind"] is AuthContextKind.ENVIRONMENT
        assert d["conditions"] == {"mfa": True}
        assert isinstance(d["conditions"], dict)

    def test_role_binding_to_dict(self):
        b = _role_binding(scope_kind=AuthContextKind.WORKSPACE)
        d = b.to_dict()
        assert d["binding_id"] == "bind-001"
        assert d["scope_kind"] is AuthContextKind.WORKSPACE

    def test_delegation_to_dict(self):
        dl = _delegation(
            status=DelegationStatus.EXPIRED,
            scope_kind=AuthContextKind.GLOBAL,
            metadata={"reason": "timeout"},
        )
        d = dl.to_dict()
        assert d["status"] is DelegationStatus.EXPIRED
        assert d["scope_kind"] is AuthContextKind.GLOBAL
        assert d["metadata"] == {"reason": "timeout"}
        assert isinstance(d["metadata"], dict)

    def test_access_request_to_dict(self):
        r = _access_request(scope_kind=AuthContextKind.ENVIRONMENT)
        d = r.to_dict()
        assert d["request_id"] == "req-001"
        assert d["scope_kind"] is AuthContextKind.ENVIRONMENT

    def test_evaluation_to_dict(self):
        e = _evaluation(
            decision=AccessDecision.REQUIRES_APPROVAL,
            matching_rule_ids=("rule-001",),
            matching_role_ids=("role-001", "role-002"),
        )
        d = e.to_dict()
        assert d["decision"] is AccessDecision.REQUIRES_APPROVAL
        assert d["matching_rule_ids"] == ["rule-001"]
        assert isinstance(d["matching_rule_ids"], list)
        assert d["matching_role_ids"] == ["role-001", "role-002"]
        assert isinstance(d["matching_role_ids"], list)

    def test_violation_to_dict(self):
        v = _violation(
            scope_kind=AuthContextKind.WORKSPACE,
            metadata={"severity": "high"},
        )
        d = v.to_dict()
        assert d["scope_kind"] is AuthContextKind.WORKSPACE
        assert d["metadata"] == {"severity": "high"}
        assert isinstance(d["metadata"], dict)

    def test_snapshot_to_dict(self):
        s = _snapshot(total_identities=50, total_evaluations=1000)
        d = s.to_dict()
        assert d["total_identities"] == 50
        assert d["total_evaluations"] == 1000

    def test_audit_to_dict(self):
        a = _audit(
            decision=AccessDecision.DENIED,
            scope_kind=AuthContextKind.GLOBAL,
            metadata={"alert": True},
        )
        d = a.to_dict()
        assert d["decision"] is AccessDecision.DENIED
        assert d["scope_kind"] is AuthContextKind.GLOBAL
        assert d["metadata"] == {"alert": True}
        assert isinstance(d["metadata"], dict)

    def test_to_dict_round_trip_preserves_enums(self):
        r = _identity()
        d = r.to_dict()
        assert d["kind"] is IdentityKind.HUMAN


# ---------------------------------------------------------------------------
# Additional coverage: cross-cutting concerns
# ---------------------------------------------------------------------------


class TestAdditionalCoverage:
    # More whitespace variants for require_non_empty_text
    def test_permission_rule_whitespace_rule_id(self):
        with pytest.raises(ValueError, match="rule_id"):
            _permission_rule(rule_id="  \t")

    def test_delegation_whitespace_delegation_id(self):
        with pytest.raises(ValueError, match="delegation_id"):
            _delegation(delegation_id="  \n ")

    def test_access_request_whitespace_request_id(self):
        with pytest.raises(ValueError, match="request_id"):
            _access_request(request_id="   ")

    def test_snapshot_whitespace_snapshot_id(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="\t")

    def test_audit_whitespace_audit_id(self):
        with pytest.raises(ValueError, match="audit_id"):
            _audit(audit_id="  ")

    # Verify delegation expires_at accepts valid datetime
    def test_delegation_expires_at_valid_datetime(self):
        d = _delegation(expires_at=TS2)
        assert d.expires_at == TS2

    # Verify delegation revoked_at accepts valid datetime
    def test_delegation_revoked_at_valid_datetime(self):
        d = _delegation(revoked_at=TS2)
        assert d.revoked_at == TS2

    # Bool rejected for non_neg_int fields
    def test_snapshot_total_roles_bool_rejected(self):
        with pytest.raises(ValueError, match="total_roles"):
            _snapshot(total_roles=False)

    def test_snapshot_total_bindings_bool_rejected(self):
        with pytest.raises(ValueError, match="total_bindings"):
            _snapshot(total_bindings=True)

    # Additional enum cycling through auth context kinds on different records
    def test_all_auth_context_kind_on_permission_rule(self):
        for kind in AuthContextKind:
            p = _permission_rule(scope_kind=kind)
            assert p.scope_kind is kind

    def test_all_auth_context_kind_on_delegation(self):
        for kind in AuthContextKind:
            d = _delegation(scope_kind=kind)
            assert d.scope_kind is kind

    def test_all_auth_context_kind_on_violation(self):
        for kind in AuthContextKind:
            v = _violation(scope_kind=kind)
            assert v.scope_kind is kind

    def test_all_auth_context_kind_on_audit(self):
        for kind in AuthContextKind:
            a = _audit(scope_kind=kind)
            assert a.scope_kind is kind

    # Nested frozen metadata on different records
    def test_delegation_nested_metadata_frozen(self):
        d = _delegation(metadata={"nested": {"inner": 1}})
        assert isinstance(d.metadata["nested"], MappingProxyType)

    def test_violation_nested_metadata_frozen(self):
        v = _violation(metadata={"nested": {"a": "b"}})
        assert isinstance(v.metadata["nested"], MappingProxyType)

    def test_audit_nested_metadata_frozen(self):
        a = _audit(metadata={"nested": {"x": 1}})
        assert isinstance(a.metadata["nested"], MappingProxyType)

    def test_snapshot_nested_metadata_frozen(self):
        s = _snapshot(metadata={"nested": {"y": 2}})
        assert isinstance(s.metadata["nested"], MappingProxyType)

    # Empty tuple fields
    def test_role_empty_permissions_tuple(self):
        r = _role(permissions=[])
        assert r.permissions == ()
        assert isinstance(r.permissions, tuple)

    def test_evaluation_empty_matching_rule_ids_tuple(self):
        e = _evaluation(matching_rule_ids=[])
        assert e.matching_rule_ids == ()
        assert isinstance(e.matching_rule_ids, tuple)

    def test_evaluation_empty_matching_role_ids_tuple(self):
        e = _evaluation(matching_role_ids=[])
        assert e.matching_role_ids == ()
        assert isinstance(e.matching_role_ids, tuple)
