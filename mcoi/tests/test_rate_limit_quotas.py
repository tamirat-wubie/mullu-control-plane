"""Rate Limit Quotas Tests."""

import pytest
from mcoi_runtime.core.rate_limit_quotas import (
    ENTERPRISE_PLAN, FREE_PLAN, PRO_PLAN,
    QuotaManager, QuotaPlan,
)
from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig


class TestPredefinedPlans:
    def test_free_plan(self):
        assert FREE_PLAN.default_config.max_tokens == 10
        assert FREE_PLAN.max_llm_calls_per_day == 50

    def test_pro_plan(self):
        assert PRO_PLAN.default_config.max_tokens > FREE_PLAN.default_config.max_tokens

    def test_enterprise_plan(self):
        assert ENTERPRISE_PLAN.max_llm_calls_per_day == 0  # Unlimited


class TestQuotaManager:
    def test_default_is_free(self):
        qm = QuotaManager()
        config = qm.get_config("unknown-tenant")
        assert config.max_tokens == FREE_PLAN.default_config.max_tokens

    def test_assign_plan(self):
        qm = QuotaManager()
        assert qm.assign_plan("t1", "pro") is True
        config = qm.get_config("t1")
        assert config.max_tokens == PRO_PLAN.default_config.max_tokens

    def test_assign_invalid_plan(self):
        qm = QuotaManager()
        assert qm.assign_plan("t1", "nonexistent") is False

    def test_custom_override(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "free")
        custom = RateLimitConfig(max_tokens=999, refill_rate=99.0)
        qm.set_custom("t1", custom)
        assert qm.get_config("t1").max_tokens == 999

    def test_plan_assignment_clears_custom(self):
        qm = QuotaManager()
        qm.set_custom("t1", RateLimitConfig(max_tokens=999))
        qm.assign_plan("t1", "pro")
        assert qm.get_config("t1").max_tokens == PRO_PLAN.default_config.max_tokens

    def test_identity_config(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "pro")
        ic = qm.get_identity_config("t1")
        assert ic is not None
        assert ic.max_tokens == PRO_PLAN.identity_config.max_tokens

    def test_custom_identity_config(self):
        qm = QuotaManager()
        custom_id = RateLimitConfig(max_tokens=50)
        qm.set_custom("t1", RateLimitConfig(max_tokens=100), identity_config=custom_id)
        assert qm.get_identity_config("t1").max_tokens == 50

    def test_list_tenants(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "free")
        qm.assign_plan("t2", "pro")
        tenants = qm.list_tenants()
        assert tenants == {"t1": "free", "t2": "pro"}

    def test_remove_tenant(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "pro")
        assert qm.remove_tenant("t1") is True
        assert qm.remove_tenant("t1") is False

    def test_get_plan(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "enterprise")
        plan = qm.get_plan("t1")
        assert plan.name == "enterprise"

    def test_summary(self):
        qm = QuotaManager()
        qm.assign_plan("t1", "pro")
        s = qm.summary()
        assert s["tenant_plans"] == 1
        assert "pro" in s["available_plans"]
