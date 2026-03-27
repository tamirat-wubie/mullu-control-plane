"""Tests for Phase 229C — Tenant Quota Enforcement Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.tenant_quota import TenantQuotaEngine, QuotaDecision


class TestTenantQuotaEngine:
    def test_no_quota_configured(self):
        engine = TenantQuotaEngine()
        result = engine.check_and_consume("t1", "api_calls")
        assert result.decision == QuotaDecision.NO_QUOTA

    def test_allowed(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "api_calls", limit=100)
        result = engine.check_and_consume("t1", "api_calls")
        assert result.decision == QuotaDecision.ALLOWED
        assert result.remaining == 99

    def test_consume_up_to_limit(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=3, grace_percent=0.0)
        for _ in range(3):
            r = engine.check_and_consume("t1", "calls")
            assert r.decision == QuotaDecision.ALLOWED
        r = engine.check_and_consume("t1", "calls")
        assert r.decision == QuotaDecision.DENIED

    def test_grace_period(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=10, grace_percent=20.0)
        # Consume 10
        for _ in range(10):
            engine.check_and_consume("t1", "calls")
        # 11th should be grace (limit=10, hard_limit=12)
        r = engine.check_and_consume("t1", "calls")
        assert r.decision == QuotaDecision.GRACE

    def test_hard_limit_exceeded(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=10, grace_percent=10.0)
        # hard_limit = 11, consume 11
        for _ in range(11):
            engine.check_and_consume("t1", "calls")
        r = engine.check_and_consume("t1", "calls")
        assert r.decision == QuotaDecision.DENIED

    def test_reset_interval(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=2, reset_interval=0.01)
        engine.check_and_consume("t1", "calls")
        engine.check_and_consume("t1", "calls")
        import time
        time.sleep(0.02)
        r = engine.check_and_consume("t1", "calls")
        assert r.decision == QuotaDecision.ALLOWED  # reset

    def test_multi_tenant_isolation(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=1, grace_percent=0.0)
        engine.set_quota("t2", "calls", limit=1, grace_percent=0.0)
        engine.check_and_consume("t1", "calls")
        r = engine.check_and_consume("t2", "calls")
        assert r.decision == QuotaDecision.ALLOWED  # t2 has its own quota

    def test_get_usage(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "api_calls", limit=100)
        engine.check_and_consume("t1", "api_calls", amount=5)
        usage = engine.get_usage("t1")
        assert usage["api_calls"]["current"] == 5
        assert usage["api_calls"]["total_allowed"] == 5

    def test_consume_amount(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "tokens", limit=1000)
        r = engine.check_and_consume("t1", "tokens", amount=500)
        assert r.decision == QuotaDecision.ALLOWED
        assert r.remaining == 500

    def test_summary(self):
        engine = TenantQuotaEngine()
        engine.set_quota("t1", "calls", limit=10)
        engine.check_and_consume("t1", "calls")
        s = engine.summary()
        assert s["tenants_with_quotas"] == 1
        assert s["total_checks"] == 1
