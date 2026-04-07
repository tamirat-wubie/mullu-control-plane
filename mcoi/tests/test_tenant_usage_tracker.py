"""Tenant Usage Tracker Tests."""

import pytest
from mcoi_runtime.core.tenant_usage_tracker import TenantUsage, TenantUsageTracker


class TestRecording:
    def test_record_llm(self):
        t = TenantUsageTracker()
        t.record_llm("t1", tokens_in=100, tokens_out=50, cost=0.01)
        u = t.get("t1")
        assert u.llm_calls == 1
        assert u.llm_tokens_input == 100
        assert u.llm_cost == 0.01

    def test_record_message(self):
        t = TenantUsageTracker()
        t.record_message("t1")
        t.record_message("t1", error=True)
        u = t.get("t1")
        assert u.gateway_messages == 2
        assert u.gateway_errors == 1

    def test_record_skill(self):
        t = TenantUsageTracker()
        t.record_skill("t1", success=True)
        t.record_skill("t1", success=False)
        u = t.get("t1")
        assert u.skill_executions == 2
        assert u.skill_errors == 1

    def test_record_session(self):
        t = TenantUsageTracker()
        t.record_session("t1")
        assert t.get("t1").sessions_created == 1

    def test_record_rate_denial(self):
        t = TenantUsageTracker()
        t.record_rate_denial("t1")
        assert t.get("t1").rate_limit_denials == 1

    def test_get_missing(self):
        t = TenantUsageTracker()
        assert t.get("nonexistent") is None

    def test_accumulates(self):
        t = TenantUsageTracker()
        for _ in range(5):
            t.record_llm("t1", cost=0.1)
        assert t.get("t1").llm_calls == 5
        assert t.get("t1").llm_cost == pytest.approx(0.5)


class TestTopTenants:
    def test_top_by_cost(self):
        t = TenantUsageTracker()
        t.record_llm("t1", cost=1.0)
        t.record_llm("t2", cost=5.0)
        t.record_llm("t3", cost=2.0)
        top = t.top_by_cost(limit=2)
        assert top[0].tenant_id == "t2"
        assert len(top) == 2

    def test_top_by_volume(self):
        t = TenantUsageTracker()
        for _ in range(10):
            t.record_message("t1")
        for _ in range(5):
            t.record_message("t2")
        top = t.top_by_volume(limit=1)
        assert top[0].tenant_id == "t1"

    def test_with_errors(self):
        t = TenantUsageTracker()
        t.record_message("t1")
        t.record_message("t2", error=True)
        errs = t.with_errors()
        assert len(errs) == 1
        assert errs[0].tenant_id == "t2"


class TestReset:
    def test_reset(self):
        t = TenantUsageTracker()
        t.record_llm("t1", cost=1.0)
        assert t.reset("t1") is True
        assert t.get("t1").llm_calls == 0

    def test_reset_nonexistent(self):
        t = TenantUsageTracker()
        assert t.reset("nonexistent") is False


class TestSummary:
    def test_summary(self):
        t = TenantUsageTracker()
        t.record_llm("t1", cost=0.5)
        t.record_message("t2")
        s = t.summary()
        assert s["tenants"] == 2
        assert s["total_cost"] == 0.5
        assert s["total_calls"] == 1

    def test_to_dict(self):
        t = TenantUsageTracker()
        t.record_llm("t1", tokens_in=100, tokens_out=50, cost=0.01)
        d = t.get("t1").to_dict()
        assert d["llm_tokens"] == 150
        assert d["llm_cost"] == 0.01
