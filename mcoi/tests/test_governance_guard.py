"""Phase 207B — Governance guards tests."""

import pytest
from mcoi_runtime.governance.guards.chain import (
    GovernanceGuard, GovernanceGuardChain, GuardResult,
    create_rate_limit_guard, create_budget_guard, create_tenant_guard, create_api_key_guard,
)
from mcoi_runtime.governance.auth.api_key import APIKeyManager
from mcoi_runtime.governance.guards.rate_limit import RateLimiter, RateLimitConfig
from mcoi_runtime.governance.guards.budget import TenantBudgetManager

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestGovernanceGuard:
    def test_allow(self):
        guard = GovernanceGuard("test", lambda ctx: GuardResult(allowed=True, guard_name="test"))
        result = guard.check({})
        assert result.allowed is True

    def test_deny(self):
        guard = GovernanceGuard("test", lambda ctx: GuardResult(allowed=False, guard_name="test", reason="nope"))
        result = guard.check({})
        assert result.allowed is False
        assert result.reason == "nope"

    def test_exception_handled(self):
        guard = GovernanceGuard("broken", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
        result = guard.check({})
        assert result.allowed is False
        assert "guard error" in result.reason


class TestGovernanceGuardChain:
    def test_all_pass(self):
        chain = GovernanceGuardChain()
        chain.add(GovernanceGuard("a", lambda ctx: GuardResult(allowed=True, guard_name="a")))
        chain.add(GovernanceGuard("b", lambda ctx: GuardResult(allowed=True, guard_name="b")))
        result = chain.evaluate({})
        assert result.allowed is True
        assert len(result.results) == 2

    def test_first_fails(self):
        chain = GovernanceGuardChain()
        chain.add(GovernanceGuard("a", lambda ctx: GuardResult(allowed=False, guard_name="a", reason="blocked")))
        chain.add(GovernanceGuard("b", lambda ctx: GuardResult(allowed=True, guard_name="b")))
        result = chain.evaluate({})
        assert result.allowed is False
        assert result.blocking_guard == "a"
        assert len(result.results) == 1  # b never ran

    def test_second_fails(self):
        chain = GovernanceGuardChain()
        chain.add(GovernanceGuard("a", lambda ctx: GuardResult(allowed=True, guard_name="a")))
        chain.add(GovernanceGuard("b", lambda ctx: GuardResult(allowed=False, guard_name="b", reason="denied")))
        result = chain.evaluate({})
        assert result.allowed is False
        assert result.blocking_guard == "b"
        assert len(result.results) == 2

    def test_guard_names(self):
        chain = GovernanceGuardChain()
        chain.add(GovernanceGuard("rate", lambda ctx: GuardResult(allowed=True, guard_name="rate")))
        chain.add(GovernanceGuard("budget", lambda ctx: GuardResult(allowed=True, guard_name="budget")))
        assert chain.guard_names() == ["rate", "budget"]


class TestBuiltInGuards:
    def test_rate_limit_guard_allows(self):
        limiter = RateLimiter(default_config=RateLimitConfig(max_tokens=100))
        guard = create_rate_limit_guard(limiter)
        result = guard.check({"tenant_id": "t1", "endpoint": "/api"})
        assert result.allowed is True

    def test_rate_limit_guard_denies(self):
        limiter = RateLimiter(default_config=RateLimitConfig(max_tokens=1, refill_rate=0.001))
        guard = create_rate_limit_guard(limiter)
        guard.check({"tenant_id": "t1", "endpoint": "/api"})
        result = guard.check({"tenant_id": "t1", "endpoint": "/api"})
        assert result.allowed is False
        assert result.reason == "rate limited"
        assert "retry" not in result.reason

    def test_budget_guard_allows(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is True  # No budget = allowed (auto-create)

    def test_budget_guard_denies_exhausted(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        from mcoi_runtime.governance.guards.budget import TenantBudgetPolicy
        mgr.set_policy(TenantBudgetPolicy(tenant_id="t1", max_cost=0.01))
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 0.01)
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is False
        assert result.reason == "budget exhausted"
        assert "t1" not in result.reason

    def test_budget_guard_denies_disabled(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.disable_tenant("t1")
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is False
        assert result.reason == "tenant disabled"
        assert "t1" not in result.reason

    def test_tenant_guard_allows(self):
        guard = create_tenant_guard()
        result = guard.check({"tenant_id": "valid-tenant"})
        assert result.allowed is True

    def test_tenant_guard_rejects_long_id(self):
        guard = create_tenant_guard()
        result = guard.check({"tenant_id": "x" * 200})
        assert result.allowed is False

    def test_api_key_guard_allows_missing_header_when_optional(self):
        mgr = APIKeyManager()
        guard = create_api_key_guard(mgr, require_auth=False)
        result = guard.check({})
        assert result.allowed is True

    def test_api_key_guard_rejects_missing_header_when_required(self):
        mgr = APIKeyManager()
        guard = create_api_key_guard(mgr, require_auth=True)
        result = guard.check({})
        assert result.allowed is False
        assert "missing Authorization" in result.reason

    def test_api_key_guard_rejects_blank_bearer_when_required(self):
        mgr = APIKeyManager()
        guard = create_api_key_guard(mgr, require_auth=True)
        result = guard.check({"authorization": "Bearer   "})
        assert result.allowed is False
        assert "missing bearer token" in result.reason

    def test_api_key_guard_propagates_tenant_from_key(self):
        mgr = APIKeyManager()
        raw_key, _ = mgr.create_key("tenant-123", frozenset({"read"}))
        guard = create_api_key_guard(mgr, require_auth=True)
        # Without spoofed tenant — key tenant propagates
        ctx = {"authorization": f"Bearer {raw_key}", "tenant_id": ""}
        result = guard.check(ctx)
        assert result.allowed is True
        assert ctx["tenant_id"] == "tenant-123"

    def test_api_key_guard_rejects_spoofed_tenant(self):
        mgr = APIKeyManager()
        raw_key, _ = mgr.create_key("tenant-123", frozenset({"read"}))
        guard = create_api_key_guard(mgr, require_auth=True)
        ctx = {"authorization": f"Bearer {raw_key}", "tenant_id": "spoofed"}
        result = guard.check(ctx)
        assert result.allowed is False
        assert result.reason == "tenant mismatch"
        assert "tenant-123" not in result.reason
        assert "spoofed" not in result.reason

    def test_api_key_guard_rejects_jwt_like_token_without_passthrough(self):
        mgr = APIKeyManager()
        guard = create_api_key_guard(mgr, require_auth=True)
        result = guard.check({"authorization": "Bearer a.b.c"})
        assert result.allowed is False
        assert result.guard_name == "api_key"

    def test_api_key_guard_allows_jwt_like_token_with_passthrough(self):
        mgr = APIKeyManager()
        guard = create_api_key_guard(
            mgr,
            require_auth=True,
            allow_jwt_passthrough=True,
        )
        ctx = {"authorization": "Bearer a.b.c", "tenant_id": ""}
        result = guard.check(ctx)
        assert result.allowed is True
        assert "authenticated_key_id" not in ctx
