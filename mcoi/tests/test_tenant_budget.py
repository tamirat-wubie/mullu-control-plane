"""Phase 201A — Multi-tenant budget isolation tests."""

import pytest
from mcoi_runtime.governance.guards.budget import (
    TenantBudgetManager,
    TenantBudgetPolicy,
    TenantBudgetReport,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestTenantBudgetPolicy:
    def test_defaults(self):
        policy = TenantBudgetPolicy(tenant_id="t1")
        assert policy.max_cost == 10.0
        assert policy.max_calls == 1000
        assert policy.auto_create is True
        assert policy.enabled is True

    def test_custom(self):
        policy = TenantBudgetPolicy(tenant_id="t1", max_cost=50.0, auto_create=False)
        assert policy.max_cost == 50.0
        assert policy.auto_create is False


class TestTenantBudgetManager:
    def test_ensure_budget_auto_create(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        budget = mgr.ensure_budget("tenant-1")
        assert budget.tenant_id == "tenant-1"
        assert budget.spent == 0.0

    def test_ensure_budget_reuses(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        b1 = mgr.ensure_budget("t1")
        b2 = mgr.ensure_budget("t1")
        assert b1 is b2

    def test_no_auto_create_raises(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.set_policy(TenantBudgetPolicy(tenant_id="t1", auto_create=False))
        with pytest.raises(ValueError, match="^no budget available and auto_create is disabled$") as exc_info:
            mgr.ensure_budget("t1")
        assert "t1" not in str(exc_info.value)

    def test_record_spend(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        updated = mgr.record_spend("t1", 1.50)
        assert updated.spent == 1.50
        assert updated.calls_made == 1

    def test_spend_accumulates(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 1.0)
        mgr.record_spend("t1", 2.0)
        budget = mgr.get_budget("t1")
        assert budget.spent == 3.0
        assert budget.calls_made == 2

    def test_exhausted_budget_raises(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.set_policy(TenantBudgetPolicy(tenant_id="t1", max_cost=1.0))
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 1.0)
        with pytest.raises(ValueError, match="^budget exhausted$") as exc_info:
            mgr.record_spend("t1", 0.01)
        assert "t1" not in str(exc_info.value)

    def test_isolation_between_tenants(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.ensure_budget("t2")
        mgr.record_spend("t1", 5.0)
        b2 = mgr.get_budget("t2")
        assert b2.spent == 0.0  # t2 unaffected by t1

    def test_report(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.set_policy(TenantBudgetPolicy(tenant_id="t1", max_cost=100.0))
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 25.0)
        report = mgr.report("t1")
        assert report.spent == 25.0
        assert report.remaining == 75.0
        assert report.utilization_pct == 25.0
        assert report.exhausted is False

    def test_report_no_budget(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        report = mgr.report("nonexistent")
        assert report.spent == 0.0
        assert report.exhausted is False

    def test_all_reports(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.ensure_budget("t2")
        reports = mgr.all_reports()
        assert len(reports) == 2

    def test_total_spent(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.ensure_budget("t2")
        mgr.record_spend("t1", 3.0)
        mgr.record_spend("t2", 2.0)
        assert mgr.total_spent() == 5.0

    def test_reset_budget(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        mgr.record_spend("t1", 5.0)
        reset = mgr.reset_budget("t1")
        assert reset.spent == 0.0
        assert reset.calls_made == 0

    def test_disable_tenant(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        mgr.ensure_budget("t1")
        assert mgr.is_enabled("t1") is True
        mgr.disable_tenant("t1")
        assert mgr.is_enabled("t1") is False

    def test_tenant_count(self):
        mgr = TenantBudgetManager(clock=FIXED_CLOCK)
        assert mgr.tenant_count() == 0
        mgr.ensure_budget("t1")
        mgr.ensure_budget("t2")
        assert mgr.tenant_count() == 2

    def test_custom_default_policy(self):
        default = TenantBudgetPolicy(tenant_id="__default__", max_cost=50.0, max_calls=500)
        mgr = TenantBudgetManager(clock=FIXED_CLOCK, default_policy=default)
        budget = mgr.ensure_budget("new-tenant")
        assert budget.max_cost == 50.0
        assert budget.max_calls == 500
