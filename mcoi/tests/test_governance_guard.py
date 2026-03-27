"""Phase 207B — Governance guards tests."""

import pytest
from mcoi_runtime.core.governance_guard import (
    GovernanceGuard, GovernanceGuardChain, GuardResult,
    create_rate_limit_guard, create_budget_guard, create_tenant_guard,
)
from mcoi_runtime.core.rate_limiter import RateLimiter, RateLimitConfig
from mcoi_runtime.core.tenant_budget import TenantBudgetManager

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

    def test_budget_guard_allows(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is True  # No budget = allowed (auto-create)

    def test_budget_guard_denies_exhausted(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        from mcoi_runtime.core.tenant_budget import TenantBudgetPolicy
        mgr.set_policy(TenantBudgetPolicy(tenant_id="t1", max_cost=0.01))
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 0.01)
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is False

    def test_budget_guard_denies_disabled(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.disable_tenant("t1")
        guard = create_budget_guard(mgr)
        result = guard.check({"tenant_id": "t1"})
        assert result.allowed is False

    def test_tenant_guard_allows(self):
        guard = create_tenant_guard()
        result = guard.check({"tenant_id": "valid-tenant"})
        assert result.allowed is True

    def test_tenant_guard_rejects_long_id(self):
        guard = create_tenant_guard()
        result = guard.check({"tenant_id": "x" * 200})
        assert result.allowed is False
