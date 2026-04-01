"""Phase 5 — RBAC Guard Tests.

Tests: RBAC guard evaluation, identity resolution, permission checking,
    default permission seeding, guard chain integration.
"""

import pytest
from mcoi_runtime.core.governance_guard import (
    GovernanceGuardChain,
    create_rbac_guard,
)
from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.contracts.access_runtime import (
    AccessDecision,
    AuthContextKind,
    IdentityKind,
    PermissionEffect,
    RoleKind,
)
from mcoi_runtime.core.rbac_defaults import seed_default_permissions


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


def _engine() -> AccessRuntimeEngine:
    spine = EventSpineEngine(clock=_clock)
    return AccessRuntimeEngine(spine)


def _engine_with_identity(identity_id: str = "user1", role_id: str = "admin") -> AccessRuntimeEngine:
    """Create engine with a registered identity and role."""
    engine = _engine()
    engine.register_identity(identity_id, "Test User", kind=IdentityKind.HUMAN, tenant_id="t1")
    engine.register_role(role_id, "Admin", kind=RoleKind.ADMIN, permissions=["*:*"])
    engine.bind_role(f"bind-{identity_id}", identity_id, role_id, scope_kind=AuthContextKind.GLOBAL)
    return engine


# ═══ RBAC Guard — No Identity ═══


class TestRBACGuardNoIdentity:
    def test_allows_without_identity_when_not_required(self):
        engine = _engine()
        guard = create_rbac_guard(engine)
        result = guard.check({"endpoint": "/api/v1/test", "method": "GET"})
        assert result.allowed

    def test_blocks_without_identity_when_required(self):
        engine = _engine()
        guard = create_rbac_guard(engine, require_identity=True)
        result = guard.check({"endpoint": "/api/v1/test", "method": "GET"})
        assert not result.allowed
        assert "no authenticated identity" in result.reason


# ═══ RBAC Guard — Identity Resolution ═══


class TestRBACGuardIdentityResolution:
    def test_resolves_from_jwt_subject(self):
        engine = _engine_with_identity("jwt-user")
        guard = create_rbac_guard(engine)
        ctx = {
            "authenticated_subject": "jwt-user",
            "endpoint": "/api/v1/llm/complete",
            "method": "POST",
        }
        result = guard.check(ctx)
        assert result.allowed
        assert ctx.get("rbac_identity_id") == "jwt-user"

    def test_resolves_from_api_key_id(self):
        engine = _engine_with_identity("key-user")
        guard = create_rbac_guard(engine)
        ctx = {
            "authenticated_key_id": "key-user",
            "endpoint": "/api/v1/tenant/budget",
            "method": "GET",
        }
        result = guard.check(ctx)
        assert result.allowed
        assert ctx.get("rbac_identity_id") == "key-user"

    def test_prefers_jwt_subject_over_key_id(self):
        engine = _engine_with_identity("jwt-user")
        guard = create_rbac_guard(engine)
        ctx = {
            "authenticated_subject": "jwt-user",
            "authenticated_key_id": "key-user",
            "endpoint": "/api/v1/test",
            "method": "GET",
        }
        guard.check(ctx)
        assert ctx.get("rbac_identity_id") == "jwt-user"


# ═══ RBAC Guard — Permission Evaluation ═══


class TestRBACGuardPermissions:
    def test_admin_allowed_everywhere(self):
        engine = _engine_with_identity("admin1", "admin")
        guard = create_rbac_guard(engine)
        for endpoint in ["/api/v1/llm/complete", "/api/v1/tenant/budget", "/api/v1/ops/benchmarks"]:
            ctx = {"authenticated_subject": "admin1", "endpoint": endpoint, "method": "POST"}
            result = guard.check(ctx)
            assert result.allowed, f"Admin should be allowed on {endpoint}"

    def test_viewer_read_only(self):
        engine = _engine()
        engine.register_identity("viewer1", "Viewer", kind=IdentityKind.HUMAN, tenant_id="t1")
        engine.register_role("viewer", "Viewer", kind=RoleKind.VIEWER, permissions=["llm:GET", "tenant:GET"])
        engine.bind_role("bind-v1", "viewer1", "viewer", scope_kind=AuthContextKind.TENANT, scope_ref_id="t1")
        engine.add_permission_rule("rule-read", "llm", "GET", effect=PermissionEffect.ALLOW, scope_kind=AuthContextKind.TENANT)

        guard = create_rbac_guard(engine)
        # GET should work
        ctx = {"authenticated_subject": "viewer1", "endpoint": "/api/v1/llm/models", "method": "GET", "tenant_id": "t1"}
        assert guard.check(ctx).allowed

    def test_unknown_identity_denied(self):
        engine = _engine()
        guard = create_rbac_guard(engine, require_identity=True)
        ctx = {"authenticated_subject": "unknown-user", "endpoint": "/api/v1/test", "method": "GET"}
        result = guard.check(ctx)
        assert not result.allowed
        assert "denied" in result.reason

    def test_disabled_identity_denied(self):
        engine = _engine()
        engine.register_identity("disabled1", "Disabled", kind=IdentityKind.HUMAN, tenant_id="t1")
        engine.disable_identity("disabled1")
        guard = create_rbac_guard(engine, require_identity=True)
        ctx = {"authenticated_subject": "disabled1", "endpoint": "/api/v1/test", "method": "GET"}
        result = guard.check(ctx)
        assert not result.allowed
        assert "denied" in result.reason


# ═══ RBAC Guard — Resource Type Extraction ═══


class TestRBACGuardResourceType:
    def test_extracts_resource_from_endpoint(self):
        engine = _engine_with_identity("user1")
        guard = create_rbac_guard(engine)
        ctx = {"authenticated_subject": "user1", "endpoint": "/api/v1/llm/complete", "method": "POST"}
        guard.check(ctx)
        assert ctx.get("rbac_resource_type") == "llm"

    def test_extracts_tenant_resource(self):
        engine = _engine_with_identity("user1")
        guard = create_rbac_guard(engine)
        ctx = {"authenticated_subject": "user1", "endpoint": "/api/v1/tenant/budget", "method": "GET"}
        guard.check(ctx)
        assert ctx.get("rbac_resource_type") == "tenant"

    def test_fallback_resource_type(self):
        engine = _engine_with_identity("user1")
        guard = create_rbac_guard(engine)
        ctx = {"authenticated_subject": "user1", "endpoint": "/short", "method": "GET"}
        guard.check(ctx)
        assert ctx.get("rbac_resource_type") == "api"


# ═══ RBAC Guard in Chain ═══


class TestRBACGuardInChain:
    def test_rbac_in_guard_chain(self):
        engine = _engine_with_identity("user1")
        guard = create_rbac_guard(engine)
        chain = GovernanceGuardChain()
        chain.add(guard)
        ctx = {"authenticated_subject": "user1", "endpoint": "/api/v1/test", "method": "GET"}
        result = chain.evaluate(ctx)
        assert result.allowed

    def test_rbac_blocks_in_chain(self):
        engine = _engine()
        engine.register_identity("blocked1", "Blocked", kind=IdentityKind.HUMAN, tenant_id="t1")
        engine.disable_identity("blocked1")
        guard = create_rbac_guard(engine, require_identity=True)
        chain = GovernanceGuardChain()
        chain.add(guard)
        ctx = {"authenticated_subject": "blocked1", "endpoint": "/api/v1/test", "method": "GET"}
        result = chain.evaluate(ctx)
        assert not result.allowed
        assert result.blocking_guard == "rbac"


# ═══ Default Permission Seeding ═══


class TestDefaultPermissionSeeding:
    def test_seed_creates_rules(self):
        engine = _engine()
        count = seed_default_permissions(engine)
        assert count >= 8

    def test_seed_creates_roles(self):
        engine = _engine()
        seed_default_permissions(engine)
        assert engine.role_count >= 5  # admin, operator, developer, viewer, auditor

    def test_seed_idempotent(self):
        engine = _engine()
        count1 = seed_default_permissions(engine)
        count2 = seed_default_permissions(engine)
        # Second call should skip all (already exist)
        assert count2 == 0

    def test_admin_role_has_wildcard(self):
        engine = _engine()
        seed_default_permissions(engine)
        roles = {r.role_id: r for r in engine._roles.values()}
        assert "admin" in roles
        assert "*:*" in roles["admin"].permissions
