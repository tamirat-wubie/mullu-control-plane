"""Comprehensive tests for mcoi.mcoi_runtime.core.executive_reporting_integration."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.executive_reporting import ExecutiveReportingEngine
from mcoi_runtime.core.executive_reporting_integration import (
    ExecutiveReportingIntegration,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.executive_reporting import (
    KPIKind,
    RollupScope,
    TrendDirection,
)

DT = "2025-01-01T00:00:00+00:00"
DT2 = "2025-06-15T12:30:00+00:00"


def _setup():
    es = EventSpineEngine()
    re = ExecutiveReportingEngine(es)
    mm = MemoryMeshEngine()
    ri = ExecutiveReportingIntegration(re, es, mm)
    return ri, re, es, mm


# ===================================================================
# 1. TestConstructorValidation
# ===================================================================


class TestConstructorValidation:
    """Wrong types for all 3 constructor params."""

    def test_reject_wrong_reporting_engine_none(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(None, es, mm)

    def test_reject_wrong_reporting_engine_string(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration("bad", es, mm)

    def test_reject_wrong_reporting_engine_int(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(42, es, mm)

    def test_reject_wrong_reporting_engine_dict(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration({}, es, mm)

    def test_reject_wrong_event_spine_none(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, None, mm)

    def test_reject_wrong_event_spine_string(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, "bad", mm)

    def test_reject_wrong_event_spine_int(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, 123, mm)

    def test_reject_wrong_memory_engine_none(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, es, None)

    def test_reject_wrong_memory_engine_string(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, es, "bad")

    def test_reject_wrong_memory_engine_list(self):
        es = EventSpineEngine()
        re = ExecutiveReportingEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingIntegration(re, es, [])

    def test_valid_construction(self):
        ri, re, es, mm = _setup()
        assert ri is not None


# ===================================================================
# 2. TestReportFromCampaigns
# ===================================================================


class TestReportFromCampaigns:
    """All return keys, completion_rate correct, emits events."""

    def test_return_keys_present(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c1", "Campaign Report",
            total_campaigns=10, completed_campaigns=7,
            failed_campaigns=2, blocked_campaigns=1,
            avg_duration_seconds=120.0, escalation_count=3,
            overdue_count=1, period_start=DT, period_end=DT2,
        )
        expected_keys = {
            "report_id", "report_type", "scope", "completion_rate",
            "total_campaigns", "completed_campaigns", "failed_campaigns",
            "blocked_campaigns", "escalation_count", "overdue_count",
        }
        assert expected_keys == set(result.keys())

    def test_report_id_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c2", "T", total_campaigns=5, completed_campaigns=5,
            period_start=DT, period_end=DT2,
        )
        assert result["report_id"] == "rpt-c2"

    def test_report_type_is_outcome(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c3", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "outcome"

    def test_scope_default_is_campaign(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c4", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "campaign"

    def test_scope_override_global(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c5", "T", scope=RollupScope.GLOBAL,
            total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "global"

    def test_scope_override_portfolio(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c5b", "T", scope=RollupScope.PORTFOLIO,
            total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "portfolio"

    def test_completion_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c6", "T", total_campaigns=10, completed_campaigns=7,
            period_start=DT, period_end=DT2,
        )
        assert result["completion_rate"] == pytest.approx(0.7)

    def test_completion_rate_zero_when_no_campaigns(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c7", "T", total_campaigns=0, completed_campaigns=0,
            period_start=DT, period_end=DT2,
        )
        assert result["completion_rate"] == 0.0

    def test_completion_rate_full(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c8", "T", total_campaigns=5, completed_campaigns=5,
            period_start=DT, period_end=DT2,
        )
        assert result["completion_rate"] == pytest.approx(1.0)

    def test_total_campaigns_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c9", "T", total_campaigns=42, completed_campaigns=10,
            period_start=DT, period_end=DT2,
        )
        assert result["total_campaigns"] == 42

    def test_completed_campaigns_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c10", "T", total_campaigns=10, completed_campaigns=3,
            period_start=DT, period_end=DT2,
        )
        assert result["completed_campaigns"] == 3

    def test_failed_campaigns_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c11", "T", total_campaigns=10, failed_campaigns=4,
            period_start=DT, period_end=DT2,
        )
        assert result["failed_campaigns"] == 4

    def test_blocked_campaigns_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c12", "T", total_campaigns=10, blocked_campaigns=2,
            period_start=DT, period_end=DT2,
        )
        assert result["blocked_campaigns"] == 2

    def test_escalation_count_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c13", "T", total_campaigns=10, escalation_count=5,
            period_start=DT, period_end=DT2,
        )
        assert result["escalation_count"] == 5

    def test_overdue_count_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c14", "T", total_campaigns=10, overdue_count=3,
            period_start=DT, period_end=DT2,
        )
        assert result["overdue_count"] == 3

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_campaigns(
            "rpt-c15", "T", total_campaigns=10, completed_campaigns=5,
            period_start=DT, period_end=DT2,
        )
        # integration emits 1, engine build_outcome_report emits 1 => at least 2
        assert es.event_count > initial

    def test_return_is_dict(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-c16", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result, dict)


# ===================================================================
# 3. TestReportFromPortfolio
# ===================================================================


class TestReportFromPortfolio:
    """Scope is 'portfolio', blocked count."""

    def test_scope_is_portfolio(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p1", "Portfolio Report",
            total_campaigns=5, completed_campaigns=3,
            blocked_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "portfolio"

    def test_report_type_is_outcome(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p2", "T", total_campaigns=5, completed_campaigns=3,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "outcome"

    def test_blocked_campaigns_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p3", "T", total_campaigns=10, completed_campaigns=5,
            blocked_campaigns=4, period_start=DT, period_end=DT2,
        )
        assert result["blocked_campaigns"] == 4

    def test_completion_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p4", "T", total_campaigns=10, completed_campaigns=8,
            period_start=DT, period_end=DT2,
        )
        assert result["completion_rate"] == pytest.approx(0.8)

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p5", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        expected = {"report_id", "report_type", "scope", "completion_rate", "blocked_campaigns"}
        assert expected == set(result.keys())

    def test_report_id_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p6", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["report_id"] == "rpt-p6"

    def test_zero_blocked(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-p7", "T", total_campaigns=5, completed_campaigns=5,
            blocked_campaigns=0, period_start=DT, period_end=DT2,
        )
        assert result["blocked_campaigns"] == 0

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_portfolio(
            "rpt-p8", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 4. TestReportFromAvailability
# ===================================================================


class TestReportFromAvailability:
    """Scope is 'team', waiting_on_human echoed."""

    def test_scope_is_team(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a1", "Availability Report",
            total_actions=100, successful_actions=90, failed_actions=10,
            waiting_on_human_seconds=300.0, avg_latency_seconds=1.5,
            utilization=0.85, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "team"

    def test_report_type_is_efficiency(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a2", "T", total_actions=10, successful_actions=8,
            failed_actions=2, utilization=0.5,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "efficiency"

    def test_waiting_on_human_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a3", "T", total_actions=10, successful_actions=10,
            waiting_on_human_seconds=999.5, utilization=0.5,
            period_start=DT, period_end=DT2,
        )
        assert result["waiting_on_human_seconds"] == 999.5

    def test_waiting_on_human_zero(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a3b", "T", total_actions=10, successful_actions=10,
            waiting_on_human_seconds=0.0, utilization=0.5,
            period_start=DT, period_end=DT2,
        )
        assert result["waiting_on_human_seconds"] == 0.0

    def test_success_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a4", "T", total_actions=100, successful_actions=75,
            failed_actions=25, utilization=0.5,
            period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == pytest.approx(0.75)

    def test_success_rate_zero_when_no_actions(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a5", "T", total_actions=0, successful_actions=0,
            period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == 0.0

    def test_utilization_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a6", "T", total_actions=10, successful_actions=10,
            utilization=0.92, period_start=DT, period_end=DT2,
        )
        assert result["utilization"] == 0.92

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a7", "T", total_actions=10, successful_actions=10,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        expected = {
            "report_id", "report_type", "scope", "success_rate",
            "waiting_on_human_seconds", "utilization",
        }
        assert expected == set(result.keys())

    def test_report_id_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-a8", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        assert result["report_id"] == "rpt-a8"

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_availability(
            "rpt-a9", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 5. TestReportFromFinancials
# ===================================================================


class TestReportFromFinancials:
    """burn_rate, cost_per_completion, roi computed."""

    def test_report_type_is_cost_effectiveness(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f1", "Financial Report",
            total_spend=5000.0, budget_limit=10000.0,
            completed_campaigns=10, period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "cost_effectiveness"

    def test_scope_is_global(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f2", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "global"

    def test_burn_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f3", "T", total_spend=5000.0, budget_limit=10000.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["burn_rate"] == pytest.approx(0.5)

    def test_burn_rate_zero_when_no_budget(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f4", "T", total_spend=0.0, budget_limit=0.0,
            completed_campaigns=0, period_start=DT, period_end=DT2,
        )
        assert result["burn_rate"] == 0.0

    def test_burn_rate_capped_at_one(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f4b", "T", total_spend=20000.0, budget_limit=10000.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["burn_rate"] <= 1.0

    def test_cost_per_completion_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f5", "T", total_spend=1000.0, budget_limit=2000.0,
            completed_campaigns=5, period_start=DT, period_end=DT2,
        )
        assert result["cost_per_completion"] == pytest.approx(200.0)

    def test_cost_per_completion_zero_when_no_completions(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f6", "T", total_spend=1000.0, budget_limit=2000.0,
            completed_campaigns=0, period_start=DT, period_end=DT2,
        )
        assert result["cost_per_completion"] == 0.0

    def test_roi_estimate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f7", "T", total_spend=1000.0, budget_limit=2000.0,
            completed_campaigns=10, period_start=DT, period_end=DT2,
        )
        assert result["roi_estimate"] == pytest.approx(10 / 1000.0)

    def test_roi_zero_when_no_spend(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f8", "T", total_spend=0.0, budget_limit=1000.0,
            completed_campaigns=0, period_start=DT, period_end=DT2,
        )
        assert result["roi_estimate"] == 0.0

    def test_total_spend_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f9", "T", total_spend=7777.0, budget_limit=10000.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["total_spend"] == 7777.0

    def test_budget_limit_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f10", "T", total_spend=100.0, budget_limit=9999.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["budget_limit"] == 9999.0

    def test_currency_default_usd(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f11", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["currency"] == "USD"

    def test_currency_custom(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f12", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, currency="EUR",
            period_start=DT, period_end=DT2,
        )
        assert result["currency"] == "EUR"

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-f13", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        expected = {
            "report_id", "report_type", "scope", "total_spend",
            "budget_limit", "burn_rate", "cost_per_completion",
            "roi_estimate", "currency",
        }
        assert expected == set(result.keys())

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_financials(
            "rpt-f14", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 6. TestReportFromConnectors
# ===================================================================


class TestReportFromConnectors:
    """Scope is 'connector', success_rate."""

    def test_scope_is_connector(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn1", "Connector Report",
            total_operations=100, successful_operations=95,
            failed_operations=5, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "connector"

    def test_report_type_is_reliability(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn2", "T", total_operations=10, successful_operations=10,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "reliability"

    def test_success_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn3", "T", total_operations=100, successful_operations=80,
            failed_operations=20, period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == pytest.approx(0.8)

    def test_success_rate_zero(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn4", "T", total_operations=0, successful_operations=0,
            period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == 0.0

    def test_success_rate_full(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn5", "T", total_operations=50, successful_operations=50,
            period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == pytest.approx(1.0)

    def test_total_operations_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn6", "T", total_operations=200, successful_operations=180,
            failed_operations=20, period_start=DT, period_end=DT2,
        )
        assert result["total_operations"] == 200

    def test_failed_operations_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn7", "T", total_operations=100, successful_operations=90,
            failed_operations=10, period_start=DT, period_end=DT2,
        )
        assert result["failed_operations"] == 10

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn8", "T", total_operations=10, successful_operations=10,
            period_start=DT, period_end=DT2,
        )
        expected = {
            "report_id", "report_type", "scope", "success_rate",
            "total_operations", "failed_operations",
        }
        assert expected == set(result.keys())

    def test_report_id_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-cn9", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert result["report_id"] == "rpt-cn9"

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_connectors(
            "rpt-cn10", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 7. TestReportFromFaults
# ===================================================================


class TestReportFromFaults:
    """fault_drill_success_rate, recovery data."""

    def test_scope_is_global(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft1", "Fault Report",
            total_operations=100, successful_operations=90,
            failed_operations=10, fault_drill_count=20,
            fault_drill_pass_count=18, recovery_count=5,
            mean_time_to_recovery_seconds=30.0,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "global"

    def test_report_type_is_reliability(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft2", "T", total_operations=10, successful_operations=10,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "reliability"

    def test_fault_drill_success_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft3", "T", total_operations=100, successful_operations=100,
            fault_drill_count=10, fault_drill_pass_count=8,
            period_start=DT, period_end=DT2,
        )
        assert result["fault_drill_success_rate"] == pytest.approx(0.8)

    def test_fault_drill_success_rate_zero_when_no_drills(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft4", "T", total_operations=10, successful_operations=10,
            fault_drill_count=0, fault_drill_pass_count=0,
            period_start=DT, period_end=DT2,
        )
        assert result["fault_drill_success_rate"] == 0.0

    def test_fault_drill_success_rate_full(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft5", "T", total_operations=10, successful_operations=10,
            fault_drill_count=5, fault_drill_pass_count=5,
            period_start=DT, period_end=DT2,
        )
        assert result["fault_drill_success_rate"] == pytest.approx(1.0)

    def test_recovery_count_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft6", "T", total_operations=10, successful_operations=10,
            recovery_count=7, period_start=DT, period_end=DT2,
        )
        assert result["recovery_count"] == 7

    def test_mean_time_to_recovery_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft7", "T", total_operations=10, successful_operations=10,
            mean_time_to_recovery_seconds=42.5,
            period_start=DT, period_end=DT2,
        )
        assert result["mean_time_to_recovery_seconds"] == 42.5

    def test_success_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft8", "T", total_operations=50, successful_operations=45,
            failed_operations=5, period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == pytest.approx(0.9)

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-ft9", "T", total_operations=10, successful_operations=10,
            period_start=DT, period_end=DT2,
        )
        expected = {
            "report_id", "report_type", "scope", "success_rate",
            "fault_drill_success_rate", "recovery_count",
            "mean_time_to_recovery_seconds",
        }
        assert expected == set(result.keys())

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_faults(
            "rpt-ft10", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 8. TestReportFromBenchmarks
# ===================================================================


class TestReportFromBenchmarks:
    """Scope is 'global', latency echoed."""

    def test_scope_is_global(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b1", "Benchmark Report",
            total_actions=100, successful_actions=95, failed_actions=5,
            avg_latency_seconds=0.5, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == "global"

    def test_report_type_is_efficiency(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b2", "T", total_actions=10, successful_actions=10,
            period_start=DT, period_end=DT2,
        )
        assert result["report_type"] == "efficiency"

    def test_avg_latency_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b3", "T", total_actions=10, successful_actions=10,
            avg_latency_seconds=1.234, period_start=DT, period_end=DT2,
        )
        assert result["avg_latency_seconds"] == 1.234

    def test_avg_latency_zero(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b4", "T", total_actions=10, successful_actions=10,
            avg_latency_seconds=0.0, period_start=DT, period_end=DT2,
        )
        assert result["avg_latency_seconds"] == 0.0

    def test_success_rate_computed(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b5", "T", total_actions=200, successful_actions=180,
            failed_actions=20, period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == pytest.approx(0.9)

    def test_success_rate_zero_no_actions(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b6", "T", total_actions=0, successful_actions=0,
            period_start=DT, period_end=DT2,
        )
        assert result["success_rate"] == 0.0

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b7", "T", total_actions=10, successful_actions=10,
            period_start=DT, period_end=DT2,
        )
        expected = {
            "report_id", "report_type", "scope", "success_rate",
            "avg_latency_seconds",
        }
        assert expected == set(result.keys())

    def test_report_id_echoed(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-b8", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        assert result["report_id"] == "rpt-b8"

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.report_from_benchmarks(
            "rpt-b9", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        assert es.event_count > initial


# ===================================================================
# 9. TestAttachToMemoryMesh
# ===================================================================


class TestAttachToMemoryMesh:
    """Deterministic ID, duplicate raises."""

    def test_returns_memory_record(self):
        ri, re, es, mm = _setup()
        ri.report_from_campaigns(
            "rpt-mm1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        mem = ri.attach_reports_to_memory_mesh("scope-1")
        assert mem is not None
        assert mem.memory_id != ""

    def test_deterministic_id(self):
        ri1, re1, es1, mm1 = _setup()
        ri2, re2, es2, mm2 = _setup()
        mem1 = ri1.attach_reports_to_memory_mesh("scope-det")
        mem2 = ri2.attach_reports_to_memory_mesh("scope-det")
        assert mem1.memory_id == mem2.memory_id

    def test_different_scope_different_id(self):
        ri, re, es, mm = _setup()
        mem1 = ri.attach_reports_to_memory_mesh("scope-a")
        mem2 = ri.attach_reports_to_memory_mesh("scope-b")
        assert mem1.memory_id != mem2.memory_id

    def test_duplicate_raises(self):
        ri, re, es, mm = _setup()
        ri.attach_reports_to_memory_mesh("scope-dup")
        with pytest.raises(RuntimeCoreInvariantError):
            ri.attach_reports_to_memory_mesh("scope-dup")

    def test_memory_stored_in_mesh(self):
        ri, re, es, mm = _setup()
        mem = ri.attach_reports_to_memory_mesh("scope-store")
        found = mm.get_memory(mem.memory_id)
        assert found is not None
        assert found.memory_id == mem.memory_id

    def test_memory_content_has_scope_ref_id(self):
        ri, re, es, mm = _setup()
        mem = ri.attach_reports_to_memory_mesh("scope-content")
        assert mem.content["scope_ref_id"] == "scope-content"

    def test_memory_content_has_total_kpis(self):
        ri, re, es, mm = _setup()
        mem = ri.attach_reports_to_memory_mesh("scope-kpi")
        assert "total_kpis" in mem.content

    def test_memory_content_has_total_reports(self):
        ri, re, es, mm = _setup()
        ri.report_from_campaigns(
            "rpt-mc1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        mem = ri.attach_reports_to_memory_mesh("scope-rptcount")
        assert mem.content["total_reports"] >= 1

    def test_emits_event(self):
        ri, re, es, mm = _setup()
        initial = es.event_count
        ri.attach_reports_to_memory_mesh("scope-evt")
        assert es.event_count > initial

    def test_memory_title_is_bounded(self):
        ri, re, es, mm = _setup()
        mem = ri.attach_reports_to_memory_mesh("my-scope-id")
        assert mem.title == "Reporting state"
        assert "my-scope-id" not in mem.title
        assert mem.scope_ref_id == "my-scope-id"


# ===================================================================
# 10. TestAttachToGraph
# ===================================================================


class TestAttachToGraph:
    """All keys, counts reflect generated reports."""

    def test_return_keys(self):
        ri, *_ = _setup()
        result = ri.attach_reports_to_graph("scope-g1")
        expected = {
            "scope_ref_id", "total_kpis", "total_metrics", "total_reports",
            "outcome_reports", "efficiency_reports",
            "cost_effectiveness_reports", "reliability_reports",
            "dashboard_snapshots",
        }
        assert expected == set(result.keys())

    def test_scope_ref_id_echoed(self):
        ri, *_ = _setup()
        result = ri.attach_reports_to_graph("my-scope")
        assert result["scope_ref_id"] == "my-scope"

    def test_no_reports_all_zero(self):
        ri, *_ = _setup()
        result = ri.attach_reports_to_graph("scope-g2")
        assert result["total_reports"] == 0
        assert result["outcome_reports"] == 0
        assert result["efficiency_reports"] == 0
        assert result["cost_effectiveness_reports"] == 0
        assert result["reliability_reports"] == 0
        assert result["dashboard_snapshots"] == 0

    def test_outcome_count_after_campaign(self):
        ri, *_ = _setup()
        ri.report_from_campaigns(
            "rpt-gc1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g3")
        assert result["outcome_reports"] == 1

    def test_outcome_count_after_portfolio(self):
        ri, *_ = _setup()
        ri.report_from_portfolio(
            "rpt-gp1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g4")
        assert result["outcome_reports"] == 1

    def test_efficiency_count_after_availability(self):
        ri, *_ = _setup()
        ri.report_from_availability(
            "rpt-ga1", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g5")
        assert result["efficiency_reports"] == 1

    def test_efficiency_count_after_benchmark(self):
        ri, *_ = _setup()
        ri.report_from_benchmarks(
            "rpt-gb1", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g6")
        assert result["efficiency_reports"] == 1

    def test_cost_effectiveness_count_after_financials(self):
        ri, *_ = _setup()
        ri.report_from_financials(
            "rpt-gf1", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g7")
        assert result["cost_effectiveness_reports"] == 1

    def test_reliability_count_after_connectors(self):
        ri, *_ = _setup()
        ri.report_from_connectors(
            "rpt-gcn1", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g8")
        assert result["reliability_reports"] == 1

    def test_reliability_count_after_faults(self):
        ri, *_ = _setup()
        ri.report_from_faults(
            "rpt-gft1", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g9")
        assert result["reliability_reports"] == 1

    def test_multiple_reports_counted(self):
        ri, *_ = _setup()
        ri.report_from_campaigns(
            "rpt-gm1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        ri.report_from_campaigns(
            "rpt-gm2", "T", total_campaigns=2, completed_campaigns=2,
            period_start=DT, period_end=DT2,
        )
        ri.report_from_financials(
            "rpt-gm3", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g10")
        assert result["total_reports"] == 3
        assert result["outcome_reports"] == 2
        assert result["cost_effectiveness_reports"] == 1

    def test_total_kpis_zero_initially(self):
        ri, *_ = _setup()
        result = ri.attach_reports_to_graph("scope-g11")
        assert result["total_kpis"] == 0

    def test_total_metrics_zero_initially(self):
        ri, *_ = _setup()
        result = ri.attach_reports_to_graph("scope-g12")
        assert result["total_metrics"] == 0

    def test_dashboard_snapshots_zero_no_dashboards(self):
        ri, *_ = _setup()
        ri.report_from_campaigns(
            "rpt-gd1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        result = ri.attach_reports_to_graph("scope-g13")
        assert result["dashboard_snapshots"] == 0


# ===================================================================
# 11. TestEventEmission
# ===================================================================


class TestEventEmission:
    """Every bridge method emits events."""

    def _count_new_events(self, es, fn):
        before = es.event_count
        fn()
        return es.event_count - before

    def test_campaign_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_campaigns(
            "rpt-ev1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 2  # engine + integration

    def test_portfolio_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_portfolio(
            "rpt-ev2", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_availability_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_availability(
            "rpt-ev3", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_financials_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_financials(
            "rpt-ev4", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_connectors_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_connectors(
            "rpt-ev5", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_faults_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_faults(
            "rpt-ev6", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_benchmarks_report_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_benchmarks(
            "rpt-ev7", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 2

    def test_attach_memory_emits(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.attach_reports_to_memory_mesh("scope-ev1"))
        assert count >= 1

    def test_campaign_emits_at_least_one_integration_event(self):
        ri, re, es, mm = _setup()
        count = self._count_new_events(es, lambda: ri.report_from_campaigns(
            "rpt-ev8", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        ))
        assert count >= 1


# ===================================================================
# 12. TestReturnValueSerialization
# ===================================================================


class TestReturnValueSerialization:
    """All scope/report_type fields are strings not enums."""

    def test_campaign_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-s1", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)
        assert not isinstance(result["scope"], RollupScope)

    def test_campaign_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-s2", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_campaign_scope_global_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-s2b", "T", scope=RollupScope.GLOBAL,
            total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)
        assert result["scope"] == "global"

    def test_campaign_scope_team_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-s2c", "T", scope=RollupScope.TEAM,
            total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)
        assert result["scope"] == "team"

    def test_portfolio_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-s3", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)
        assert not isinstance(result["scope"], RollupScope)

    def test_portfolio_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-s4", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_availability_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-s5", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)

    def test_availability_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-s6", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_financials_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-s7", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)

    def test_financials_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-s8", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_connectors_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-s9", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)

    def test_connectors_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-s10", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_faults_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-s11", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)

    def test_faults_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-s12", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_benchmarks_scope_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-s13", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["scope"], str)

    def test_benchmarks_report_type_is_str(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-s14", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        assert isinstance(result["report_type"], str)

    def test_campaign_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_campaigns(
            "rpt-s15", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.CAMPAIGN.value

    def test_portfolio_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_portfolio(
            "rpt-s16", "T", total_campaigns=1, completed_campaigns=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.PORTFOLIO.value

    def test_availability_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_availability(
            "rpt-s17", "T", total_actions=1, successful_actions=1,
            utilization=0.5, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.TEAM.value

    def test_financials_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_financials(
            "rpt-s18", "T", total_spend=100.0, budget_limit=200.0,
            completed_campaigns=1, period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.GLOBAL.value

    def test_connectors_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_connectors(
            "rpt-s19", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.CONNECTOR.value

    def test_faults_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_faults(
            "rpt-s20", "T", total_operations=1, successful_operations=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.GLOBAL.value

    def test_benchmarks_scope_value_matches_enum_value(self):
        ri, *_ = _setup()
        result = ri.report_from_benchmarks(
            "rpt-s21", "T", total_actions=1, successful_actions=1,
            period_start=DT, period_end=DT2,
        )
        assert result["scope"] == RollupScope.GLOBAL.value
