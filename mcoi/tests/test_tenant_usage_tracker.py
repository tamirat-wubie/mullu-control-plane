"""Tenant Usage Tracker Tests."""

import math

import pytest
from mcoi_runtime.core.tenant_usage_tracker import TenantUsageTracker


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

    @pytest.mark.parametrize(
        ("kwargs", "field_name"),
        [
            ({"tokens_in": -1}, "tokens_in"),
            ({"tokens_in": 1.5}, "tokens_in"),
            ({"tokens_in": True}, "tokens_in"),
            ({"tokens_out": math.inf}, "tokens_out"),
            ({"tokens_out": "7"}, "tokens_out"),
            ({"cost": -0.01}, "cost"),
            ({"cost": math.nan}, "cost"),
            ({"cost": False}, "cost"),
        ],
    )
    def test_record_llm_rejects_invalid_usage_values_without_mutating_state(self, kwargs, field_name):
        t = TenantUsageTracker()
        with pytest.raises(ValueError, match=field_name):
            t.record_llm("t1", **kwargs)
        assert t.get("t1") is None
        assert t.summary()["tenants"] == 0

    def test_record_llm_normalizes_integral_numeric_values(self):
        t = TenantUsageTracker()
        t.record_llm(" t1 ", tokens_in=100.0, tokens_out=50, cost=1)
        usage = t.get("t1")
        assert usage.llm_calls == 1
        assert usage.llm_tokens_input == 100
        assert usage.llm_tokens_output == 50
        assert usage.llm_cost == 1.0

    @pytest.mark.parametrize("tenant_id", ["", "   ", 12, "t" * 257])
    def test_recording_rejects_invalid_tenant_identity(self, tenant_id):
        t = TenantUsageTracker()
        with pytest.raises(ValueError, match="tenant_id"):
            t.record_message(tenant_id)
        assert t.tenant_count == 0
        assert t.summary()["total_messages"] == 0

    @pytest.mark.parametrize(
        ("method_name", "kwargs", "field_name"),
        [
            ("record_message", {"error": 1}, "error"),
            ("record_message", {"error": "true"}, "error"),
            ("record_skill", {"success": 1}, "success"),
            ("record_skill", {"success": "false"}, "success"),
        ],
    )
    def test_boolean_flags_must_be_explicit_booleans(self, method_name, kwargs, field_name):
        t = TenantUsageTracker()
        method = getattr(t, method_name)
        with pytest.raises(ValueError, match=field_name):
            method("t1", **kwargs)
        assert t.get("t1") is None
        assert t.summary()["tenants"] == 0


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

    @pytest.mark.parametrize("limit", [-1, 1.5, True, math.inf])
    def test_top_tenant_limits_reject_invalid_values(self, limit):
        t = TenantUsageTracker()
        t.record_llm("t1", cost=1.0)
        with pytest.raises(ValueError, match="limit"):
            t.top_by_cost(limit=limit)
        with pytest.raises(ValueError, match="limit"):
            t.top_by_volume(limit=limit)
        assert t.tenant_count == 1

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
