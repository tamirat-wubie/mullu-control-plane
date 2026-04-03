"""Tests for executive reporting / KPI / outcome analytics contracts.

Covers all 5 enums and 10 dataclasses in
``mcoi_runtime.contracts.executive_reporting``.
"""

from __future__ import annotations

import dataclasses

import pytest

from mcoi_runtime.contracts.executive_reporting import (
    CostEffectivenessReport,
    EfficiencyReport,
    ExecutiveDashboardSnapshot,
    KPIDefinition,
    KPIKind,
    KPIValue,
    MetricWindow,
    OutcomeReport,
    ReliabilityReport,
    ReportingDecision,
    ReportStatus,
    RollupRecord,
    RollupScope,
    TrendDirection,
    TrendSnapshot,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DT = "2025-01-01T00:00:00+00:00"
DT2 = "2025-06-15T12:30:00+00:00"
BAD_DT = "not-a-datetime"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _kpi_def(**overrides) -> KPIDefinition:
    defaults = dict(
        kpi_id="kpi-1",
        name="Campaign Completion",
        kind=KPIKind.CAMPAIGN_COMPLETION_RATE,
        description="Tracks campaign completion",
        unit="percent",
        window=MetricWindow.DAILY,
        target_value=0.95,
        warning_threshold=0.8,
        critical_threshold=0.6,
        higher_is_better=True,
        scope=RollupScope.GLOBAL,
        scope_ref_id="ref-1",
        tags=("ops", "kpi"),
        created_at=DT,
        metadata={"owner": "platform"},
    )
    defaults.update(overrides)
    return KPIDefinition(**defaults)


def _kpi_val(**overrides) -> KPIValue:
    defaults = dict(
        value_id="val-1",
        kpi_id="kpi-1",
        value=0.92,
        window=MetricWindow.DAILY,
        period_start=DT,
        period_end=DT2,
        scope=RollupScope.GLOBAL,
        scope_ref_id="ref-1",
        sample_count=100,
        recorded_at=DT,
    )
    defaults.update(overrides)
    return KPIValue(**defaults)


def _trend(**overrides) -> TrendSnapshot:
    defaults = dict(
        trend_id="trend-1",
        kpi_id="kpi-1",
        direction=TrendDirection.IMPROVING,
        current_value=0.95,
        previous_value=0.90,
        change_pct=5.5,
        data_points=30,
        window=MetricWindow.WEEKLY,
        scope=RollupScope.PORTFOLIO,
        scope_ref_id="port-1",
        computed_at=DT,
    )
    defaults.update(overrides)
    return TrendSnapshot(**defaults)


def _rollup(**overrides) -> RollupRecord:
    defaults = dict(
        rollup_id="roll-1",
        kpi_id="kpi-1",
        scope=RollupScope.CAMPAIGN,
        scope_ref_id="camp-1",
        window=MetricWindow.MONTHLY,
        period_start=DT,
        period_end=DT2,
        total=500.0,
        count=10,
        average=50.0,
        minimum=20.0,
        maximum=80.0,
        computed_at=DT,
    )
    defaults.update(overrides)
    return RollupRecord(**defaults)


def _outcome(**overrides) -> OutcomeReport:
    defaults = dict(
        report_id="out-1",
        title="Q1 Outcomes",
        scope=RollupScope.PORTFOLIO,
        scope_ref_id="port-1",
        status=ReportStatus.FINAL,
        total_campaigns=10,
        completed_campaigns=7,
        failed_campaigns=1,
        blocked_campaigns=1,
        completion_rate=0.7,
        avg_duration_seconds=3600.0,
        escalation_count=2,
        overdue_count=1,
        period_start=DT,
        period_end=DT2,
        generated_at=DT,
        metadata={"version": "1"},
    )
    defaults.update(overrides)
    return OutcomeReport(**defaults)


def _efficiency(**overrides) -> EfficiencyReport:
    defaults = dict(
        report_id="eff-1",
        title="Team Efficiency Q1",
        scope=RollupScope.TEAM,
        scope_ref_id="team-1",
        status=ReportStatus.FINAL,
        total_actions=200,
        successful_actions=180,
        failed_actions=10,
        success_rate=0.9,
        avg_latency_seconds=1.5,
        waiting_on_human_seconds=300.0,
        utilization=0.75,
        period_start=DT,
        period_end=DT2,
        generated_at=DT,
        metadata={"dept": "eng"},
    )
    defaults.update(overrides)
    return EfficiencyReport(**defaults)


def _cost_eff(**overrides) -> CostEffectivenessReport:
    defaults = dict(
        report_id="cost-1",
        title="Cost Report Q1",
        scope=RollupScope.GLOBAL,
        scope_ref_id="global-1",
        status=ReportStatus.FINAL,
        total_spend=5000.0,
        budget_limit=10000.0,
        burn_rate=0.5,
        completed_campaigns=8,
        cost_per_completion=625.0,
        currency="USD",
        roi_estimate=2.5,
        period_start=DT,
        period_end=DT2,
        generated_at=DT,
        metadata={"fiscal": "2025"},
    )
    defaults.update(overrides)
    return CostEffectivenessReport(**defaults)


def _reliability(**overrides) -> ReliabilityReport:
    defaults = dict(
        report_id="rel-1",
        title="Reliability Q1",
        scope=RollupScope.CONNECTOR,
        scope_ref_id="conn-1",
        status=ReportStatus.FINAL,
        total_operations=1000,
        successful_operations=990,
        failed_operations=10,
        success_rate=0.99,
        fault_drill_count=5,
        fault_drill_pass_count=4,
        fault_drill_success_rate=0.8,
        recovery_count=3,
        mean_time_to_recovery_seconds=120.0,
        period_start=DT,
        period_end=DT2,
        generated_at=DT,
        metadata={"sla": "99.9"},
    )
    defaults.update(overrides)
    return ReliabilityReport(**defaults)


def _dashboard(**overrides) -> ExecutiveDashboardSnapshot:
    defaults = dict(
        snapshot_id="snap-1",
        title="Executive Dashboard",
        status=ReportStatus.FINAL,
        total_kpis=20,
        kpis_on_target=15,
        kpis_warning=3,
        kpis_critical=1,
        active_campaigns=12,
        blocked_campaigns=2,
        active_budgets=5,
        total_spend=25000.0,
        budget_utilization=0.6,
        connector_health_pct=0.95,
        overall_trend=TrendDirection.IMPROVING,
        period_start=DT,
        period_end=DT2,
        generated_at=DT,
        metadata={"quarter": "Q1"},
    )
    defaults.update(overrides)
    return ExecutiveDashboardSnapshot(**defaults)


def _reporting_dec(**overrides) -> ReportingDecision:
    defaults = dict(
        decision_id="dec-1",
        report_type="outcome",
        scope=RollupScope.PORTFOLIO,
        scope_ref_id="port-1",
        window=MetricWindow.MONTHLY,
        include_trends=True,
        include_breakdowns=False,
        reason="Scheduled quarterly review",
        decided_at=DT,
    )
    defaults.update(overrides)
    return ReportingDecision(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestKPIKind:
    def test_member_count(self):
        assert len(KPIKind) == 10

    def test_values(self):
        expected = {
            "campaign_completion_rate",
            "waiting_on_human_delay",
            "escalation_frequency",
            "connector_success_rate",
            "budget_burn_vs_completion",
            "overdue_obligation_rate",
            "cost_per_closure",
            "portfolio_blocked_count",
            "fault_drill_success_rate",
            "custom",
        }
        assert {m.value for m in KPIKind} == expected

    def test_unique_values(self):
        vals = [m.value for m in KPIKind]
        assert len(vals) == len(set(vals))


class TestMetricWindow:
    def test_member_count(self):
        assert len(MetricWindow) == 7

    def test_values(self):
        expected = {"hourly", "daily", "weekly", "monthly", "quarterly", "yearly", "all_time"}
        assert {m.value for m in MetricWindow} == expected

    def test_unique_values(self):
        vals = [m.value for m in MetricWindow]
        assert len(vals) == len(set(vals))


class TestTrendDirection:
    def test_member_count(self):
        assert len(TrendDirection) == 4

    def test_values(self):
        expected = {"improving", "stable", "degrading", "insufficient_data"}
        assert {m.value for m in TrendDirection} == expected

    def test_unique_values(self):
        vals = [m.value for m in TrendDirection]
        assert len(vals) == len(set(vals))


class TestRollupScope:
    def test_member_count(self):
        assert len(RollupScope) == 8

    def test_values(self):
        expected = {
            "global", "portfolio", "campaign", "team",
            "function", "connector", "domain_pack", "channel",
        }
        assert {m.value for m in RollupScope} == expected

    def test_unique_values(self):
        vals = [m.value for m in RollupScope]
        assert len(vals) == len(set(vals))


class TestReportStatus:
    def test_member_count(self):
        assert len(ReportStatus) == 4

    def test_values(self):
        expected = {"draft", "final", "superseded", "archived"}
        assert {m.value for m in ReportStatus} == expected

    def test_unique_values(self):
        vals = [m.value for m in ReportStatus]
        assert len(vals) == len(set(vals))


# ===================================================================
# KPIDefinition tests
# ===================================================================


class TestKPIDefinition:
    def test_valid_construction(self):
        obj = _kpi_def()
        assert obj.kpi_id == "kpi-1"
        assert obj.name == "Campaign Completion"
        assert obj.kind is KPIKind.CAMPAIGN_COMPLETION_RATE
        assert obj.window is MetricWindow.DAILY
        assert obj.scope is RollupScope.GLOBAL
        assert obj.higher_is_better is True
        assert obj.tags == ("ops", "kpi")

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_def(kpi_id="")

    def test_name_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_def(name="")

    def test_frozen_immutability(self):
        obj = _kpi_def()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.kpi_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _kpi_def().to_dict()
        assert d["kind"] is KPIKind.CAMPAIGN_COMPLETION_RATE
        assert d["window"] is MetricWindow.DAILY
        assert d["scope"] is RollupScope.GLOBAL

    def test_to_dict_all_keys(self):
        d = _kpi_def().to_dict()
        expected_keys = {
            "kpi_id", "name", "kind", "description", "unit", "window",
            "target_value", "warning_threshold", "critical_threshold",
            "higher_is_better", "scope", "scope_ref_id", "tags",
            "created_at", "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_bad_created_at(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_def(created_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _kpi_def()
        with pytest.raises(TypeError):
            obj.metadata["new_key"] = "fail"  # type: ignore[index]

    def test_tags_preserved(self):
        obj = _kpi_def(tags=("a", "b", "c"))
        assert obj.tags == ("a", "b", "c")

    def test_all_kpi_kinds(self):
        for k in KPIKind:
            obj = _kpi_def(kind=k)
            assert obj.kind is k

    def test_all_metric_windows(self):
        for w in MetricWindow:
            obj = _kpi_def(window=w)
            assert obj.window is w

    def test_all_rollup_scopes(self):
        for s in RollupScope:
            obj = _kpi_def(scope=s)
            assert obj.scope is s

    def test_higher_is_better_false(self):
        obj = _kpi_def(higher_is_better=False)
        assert obj.higher_is_better is False

    def test_whitespace_only_id_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_def(kpi_id="   ")


# ===================================================================
# KPIValue tests
# ===================================================================


class TestKPIValue:
    def test_valid_construction(self):
        obj = _kpi_val()
        assert obj.value_id == "val-1"
        assert obj.kpi_id == "kpi-1"
        assert obj.value == 0.92
        assert obj.sample_count == 100

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(value_id="")

    def test_kpi_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(kpi_id="")

    def test_frozen_immutability(self):
        obj = _kpi_val()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.value_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _kpi_val().to_dict()
        assert d["window"] is MetricWindow.DAILY
        assert d["scope"] is RollupScope.GLOBAL

    def test_to_dict_all_keys(self):
        d = _kpi_val().to_dict()
        expected_keys = {
            "value_id", "kpi_id", "value", "window", "period_start",
            "period_end", "scope", "scope_ref_id", "sample_count",
            "recorded_at",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_sample_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(sample_count=-1)

    def test_period_start_after_end_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(period_start=DT2, period_end=DT)

    def test_period_start_equals_end_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(period_start=DT, period_end=DT)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(period_start=BAD_DT)

    def test_bad_period_end(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(period_end=BAD_DT)

    def test_bad_recorded_at(self):
        with pytest.raises((ValueError, TypeError)):
            _kpi_val(recorded_at=BAD_DT)

    def test_zero_sample_count_ok(self):
        obj = _kpi_val(sample_count=0)
        assert obj.sample_count == 0


# ===================================================================
# TrendSnapshot tests
# ===================================================================


class TestTrendSnapshot:
    def test_valid_construction(self):
        obj = _trend()
        assert obj.trend_id == "trend-1"
        assert obj.direction is TrendDirection.IMPROVING
        assert obj.change_pct == 5.5
        assert obj.data_points == 30

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _trend(trend_id="")

    def test_kpi_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _trend(kpi_id="")

    def test_frozen_immutability(self):
        obj = _trend()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.trend_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _trend().to_dict()
        assert d["direction"] is TrendDirection.IMPROVING
        assert d["window"] is MetricWindow.WEEKLY
        assert d["scope"] is RollupScope.PORTFOLIO

    def test_to_dict_all_keys(self):
        d = _trend().to_dict()
        expected_keys = {
            "trend_id", "kpi_id", "direction", "current_value",
            "previous_value", "change_pct", "data_points", "window",
            "scope", "scope_ref_id", "computed_at",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_data_points_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _trend(data_points=-1)

    def test_zero_data_points_ok(self):
        obj = _trend(data_points=0)
        assert obj.data_points == 0

    def test_bad_computed_at(self):
        with pytest.raises((ValueError, TypeError)):
            _trend(computed_at=BAD_DT)

    def test_all_trend_directions(self):
        for d in TrendDirection:
            obj = _trend(direction=d)
            assert obj.direction is d

    def test_negative_change_pct_ok(self):
        obj = _trend(change_pct=-10.5)
        assert obj.change_pct == -10.5


# ===================================================================
# RollupRecord tests
# ===================================================================


class TestRollupRecord:
    def test_valid_construction(self):
        obj = _rollup()
        assert obj.rollup_id == "roll-1"
        assert obj.scope is RollupScope.CAMPAIGN
        assert obj.count == 10
        assert obj.average == 50.0

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(rollup_id="")

    def test_kpi_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(kpi_id="")

    def test_frozen_immutability(self):
        obj = _rollup()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.rollup_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _rollup().to_dict()
        assert d["scope"] is RollupScope.CAMPAIGN
        assert d["window"] is MetricWindow.MONTHLY

    def test_to_dict_all_keys(self):
        d = _rollup().to_dict()
        expected_keys = {
            "rollup_id", "kpi_id", "scope", "scope_ref_id", "window",
            "period_start", "period_end", "total", "count", "average",
            "minimum", "maximum", "computed_at",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(count=-1)

    def test_zero_count_ok(self):
        obj = _rollup(count=0)
        assert obj.count == 0

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(period_start=BAD_DT)

    def test_bad_period_end(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(period_end=BAD_DT)

    def test_bad_computed_at(self):
        with pytest.raises((ValueError, TypeError)):
            _rollup(computed_at=BAD_DT)


# ===================================================================
# OutcomeReport tests
# ===================================================================


class TestOutcomeReport:
    def test_valid_construction(self):
        obj = _outcome()
        assert obj.report_id == "out-1"
        assert obj.title == "Q1 Outcomes"
        assert obj.status is ReportStatus.FINAL
        assert obj.total_campaigns == 10
        assert obj.completion_rate == 0.7

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(report_id="")

    def test_title_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(title="")

    def test_frozen_immutability(self):
        obj = _outcome()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.report_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _outcome().to_dict()
        assert d["scope"] is RollupScope.PORTFOLIO
        assert d["status"] is ReportStatus.FINAL

    def test_to_dict_all_keys(self):
        d = _outcome().to_dict()
        expected_keys = {
            "report_id", "title", "scope", "scope_ref_id", "status",
            "total_campaigns", "completed_campaigns", "failed_campaigns",
            "blocked_campaigns", "completion_rate", "avg_duration_seconds",
            "escalation_count", "overdue_count", "period_start",
            "period_end", "generated_at", "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_total_campaigns_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(total_campaigns=-1)

    def test_negative_completed_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(completed_campaigns=-1)

    def test_negative_failed_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(failed_campaigns=-1)

    def test_negative_blocked_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(blocked_campaigns=-1)

    def test_sum_exceeds_total_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(
                total_campaigns=5,
                completed_campaigns=3,
                failed_campaigns=2,
                blocked_campaigns=2,
            )

    def test_sum_equals_total_ok(self):
        obj = _outcome(
            total_campaigns=10,
            completed_campaigns=5,
            failed_campaigns=3,
            blocked_campaigns=2,
        )
        assert obj.total_campaigns == 10

    def test_completion_rate_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(completion_rate=1.1)

    def test_completion_rate_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(completion_rate=-0.1)

    def test_negative_avg_duration_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(avg_duration_seconds=-1.0)

    def test_negative_escalation_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(escalation_count=-1)

    def test_negative_overdue_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(overdue_count=-1)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(period_start=BAD_DT)

    def test_bad_generated_at(self):
        with pytest.raises((ValueError, TypeError)):
            _outcome(generated_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _outcome()
        with pytest.raises(TypeError):
            obj.metadata["x"] = "fail"  # type: ignore[index]

    def test_all_report_statuses(self):
        for s in ReportStatus:
            obj = _outcome(status=s)
            assert obj.status is s


# ===================================================================
# EfficiencyReport tests
# ===================================================================


class TestEfficiencyReport:
    def test_valid_construction(self):
        obj = _efficiency()
        assert obj.report_id == "eff-1"
        assert obj.total_actions == 200
        assert obj.success_rate == 0.9
        assert obj.utilization == 0.75

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(report_id="")

    def test_title_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(title="")

    def test_frozen_immutability(self):
        obj = _efficiency()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.report_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _efficiency().to_dict()
        assert d["scope"] is RollupScope.TEAM
        assert d["status"] is ReportStatus.FINAL

    def test_to_dict_all_keys(self):
        d = _efficiency().to_dict()
        expected_keys = {
            "report_id", "title", "scope", "scope_ref_id", "status",
            "total_actions", "successful_actions", "failed_actions",
            "success_rate", "avg_latency_seconds", "waiting_on_human_seconds",
            "utilization", "period_start", "period_end", "generated_at",
            "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_total_actions_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(total_actions=-1)

    def test_negative_successful_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(successful_actions=-1)

    def test_negative_failed_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(failed_actions=-1)

    def test_sum_exceeds_total_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(
                total_actions=10,
                successful_actions=8,
                failed_actions=5,
            )

    def test_sum_equals_total_ok(self):
        obj = _efficiency(
            total_actions=10,
            successful_actions=7,
            failed_actions=3,
        )
        assert obj.total_actions == 10

    def test_success_rate_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(success_rate=1.1)

    def test_success_rate_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(success_rate=-0.1)

    def test_negative_avg_latency_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(avg_latency_seconds=-1.0)

    def test_negative_waiting_on_human_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(waiting_on_human_seconds=-1.0)

    def test_utilization_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(utilization=1.1)

    def test_utilization_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(utilization=-0.1)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(period_start=BAD_DT)

    def test_bad_generated_at(self):
        with pytest.raises((ValueError, TypeError)):
            _efficiency(generated_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _efficiency()
        with pytest.raises(TypeError):
            obj.metadata["x"] = "fail"  # type: ignore[index]


# ===================================================================
# CostEffectivenessReport tests
# ===================================================================


class TestCostEffectivenessReport:
    def test_valid_construction(self):
        obj = _cost_eff()
        assert obj.report_id == "cost-1"
        assert obj.total_spend == 5000.0
        assert obj.burn_rate == 0.5
        assert obj.currency == "USD"
        assert obj.roi_estimate == 2.5

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(report_id="")

    def test_title_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(title="")

    def test_frozen_immutability(self):
        obj = _cost_eff()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.report_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _cost_eff().to_dict()
        assert d["scope"] is RollupScope.GLOBAL
        assert d["status"] is ReportStatus.FINAL

    def test_to_dict_all_keys(self):
        d = _cost_eff().to_dict()
        expected_keys = {
            "report_id", "title", "scope", "scope_ref_id", "status",
            "total_spend", "budget_limit", "burn_rate", "completed_campaigns",
            "cost_per_completion", "currency", "roi_estimate",
            "period_start", "period_end", "generated_at", "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_total_spend_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(total_spend=-1.0)

    def test_negative_budget_limit_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(budget_limit=-1.0)

    def test_burn_rate_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(burn_rate=1.1)

    def test_burn_rate_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(burn_rate=-0.1)

    def test_negative_completed_campaigns_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(completed_campaigns=-1)

    def test_negative_cost_per_completion_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(cost_per_completion=-1.0)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(period_start=BAD_DT)

    def test_bad_generated_at(self):
        with pytest.raises((ValueError, TypeError)):
            _cost_eff(generated_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _cost_eff()
        with pytest.raises(TypeError):
            obj.metadata["x"] = "fail"  # type: ignore[index]

    def test_zero_spend_ok(self):
        obj = _cost_eff(total_spend=0.0)
        assert obj.total_spend == 0.0

    def test_zero_burn_rate_ok(self):
        obj = _cost_eff(burn_rate=0.0)
        assert obj.burn_rate == 0.0

    def test_roi_can_be_negative(self):
        obj = _cost_eff(roi_estimate=-1.5)
        assert obj.roi_estimate == -1.5


# ===================================================================
# ReliabilityReport tests
# ===================================================================


class TestReliabilityReport:
    def test_valid_construction(self):
        obj = _reliability()
        assert obj.report_id == "rel-1"
        assert obj.total_operations == 1000
        assert obj.success_rate == 0.99
        assert obj.fault_drill_success_rate == 0.8

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(report_id="")

    def test_title_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(title="")

    def test_frozen_immutability(self):
        obj = _reliability()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.report_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _reliability().to_dict()
        assert d["scope"] is RollupScope.CONNECTOR
        assert d["status"] is ReportStatus.FINAL

    def test_to_dict_all_keys(self):
        d = _reliability().to_dict()
        expected_keys = {
            "report_id", "title", "scope", "scope_ref_id", "status",
            "total_operations", "successful_operations", "failed_operations",
            "success_rate", "fault_drill_count", "fault_drill_pass_count",
            "fault_drill_success_rate", "recovery_count",
            "mean_time_to_recovery_seconds", "period_start", "period_end",
            "generated_at", "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_negative_total_operations_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(total_operations=-1)

    def test_negative_successful_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(successful_operations=-1)

    def test_negative_failed_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(failed_operations=-1)

    def test_ops_sum_exceeds_total_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(
                total_operations=10,
                successful_operations=8,
                failed_operations=5,
            )

    def test_ops_sum_equals_total_ok(self):
        obj = _reliability(
            total_operations=10,
            successful_operations=7,
            failed_operations=3,
        )
        assert obj.total_operations == 10

    def test_pass_count_exceeds_drill_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(
                fault_drill_count=3,
                fault_drill_pass_count=5,
            )

    def test_pass_count_equals_drill_count_ok(self):
        obj = _reliability(
            fault_drill_count=5,
            fault_drill_pass_count=5,
        )
        assert obj.fault_drill_pass_count == 5

    def test_success_rate_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(success_rate=1.1)

    def test_success_rate_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(success_rate=-0.1)

    def test_drill_success_rate_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(fault_drill_success_rate=1.1)

    def test_drill_success_rate_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(fault_drill_success_rate=-0.1)

    def test_negative_recovery_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(recovery_count=-1)

    def test_negative_mttr_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(mean_time_to_recovery_seconds=-1.0)

    def test_negative_drill_count_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(fault_drill_count=-1)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(period_start=BAD_DT)

    def test_bad_generated_at(self):
        with pytest.raises((ValueError, TypeError)):
            _reliability(generated_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _reliability()
        with pytest.raises(TypeError):
            obj.metadata["x"] = "fail"  # type: ignore[index]


# ===================================================================
# ExecutiveDashboardSnapshot tests
# ===================================================================


class TestExecutiveDashboardSnapshot:
    def test_valid_construction(self):
        obj = _dashboard()
        assert obj.snapshot_id == "snap-1"
        assert obj.title == "Executive Dashboard"
        assert obj.total_kpis == 20
        assert obj.overall_trend is TrendDirection.IMPROVING

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(snapshot_id="")

    def test_title_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(title="")

    def test_frozen_immutability(self):
        obj = _dashboard()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.snapshot_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _dashboard().to_dict()
        assert d["status"] is ReportStatus.FINAL
        assert d["overall_trend"] is TrendDirection.IMPROVING

    def test_to_dict_all_keys(self):
        d = _dashboard().to_dict()
        expected_keys = {
            "snapshot_id", "title", "status", "total_kpis", "kpis_on_target",
            "kpis_warning", "kpis_critical", "active_campaigns",
            "blocked_campaigns", "active_budgets", "total_spend",
            "budget_utilization", "connector_health_pct", "overall_trend",
            "period_start", "period_end", "generated_at", "metadata",
        }
        assert expected_keys <= set(d.keys())

    def test_kpi_status_exceeds_total_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(
                total_kpis=5,
                kpis_on_target=3,
                kpis_warning=2,
                kpis_critical=2,
            )

    def test_kpi_status_equals_total_ok(self):
        obj = _dashboard(
            total_kpis=10,
            kpis_on_target=5,
            kpis_warning=3,
            kpis_critical=2,
        )
        assert obj.total_kpis == 10

    def test_negative_total_kpis_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(total_kpis=-1)

    def test_negative_kpis_on_target_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(kpis_on_target=-1)

    def test_negative_kpis_warning_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(kpis_warning=-1)

    def test_negative_kpis_critical_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(kpis_critical=-1)

    def test_negative_active_campaigns_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(active_campaigns=-1)

    def test_negative_blocked_campaigns_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(blocked_campaigns=-1)

    def test_negative_active_budgets_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(active_budgets=-1)

    def test_negative_total_spend_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(total_spend=-1.0)

    def test_budget_utilization_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(budget_utilization=1.1)

    def test_budget_utilization_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(budget_utilization=-0.1)

    def test_connector_health_above_one_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(connector_health_pct=1.1)

    def test_connector_health_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(connector_health_pct=-0.1)

    def test_bad_period_start(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(period_start=BAD_DT)

    def test_bad_generated_at(self):
        with pytest.raises((ValueError, TypeError)):
            _dashboard(generated_at=BAD_DT)

    def test_metadata_frozen(self):
        obj = _dashboard()
        with pytest.raises(TypeError):
            obj.metadata["x"] = "fail"  # type: ignore[index]

    def test_all_trend_directions(self):
        for t in TrendDirection:
            obj = _dashboard(overall_trend=t)
            assert obj.overall_trend is t

    def test_all_report_statuses(self):
        for s in ReportStatus:
            obj = _dashboard(status=s)
            assert obj.status is s

    def test_zero_spend_ok(self):
        obj = _dashboard(total_spend=0.0)
        assert obj.total_spend == 0.0


@pytest.mark.parametrize(
    "factory",
    (_rollup, _outcome, _efficiency, _cost_eff, _reliability, _dashboard),
)
def test_period_models_require_start_before_end(factory):
    with pytest.raises((ValueError, TypeError), match="must be before"):
        factory(period_start=DT2, period_end=DT)


# ===================================================================
# ReportingDecision tests
# ===================================================================


class TestReportingDecision:
    def test_valid_construction(self):
        obj = _reporting_dec()
        assert obj.decision_id == "dec-1"
        assert obj.report_type == "outcome"
        assert obj.scope is RollupScope.PORTFOLIO
        assert obj.window is MetricWindow.MONTHLY
        assert obj.include_trends is True
        assert obj.include_breakdowns is False

    def test_id_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reporting_dec(decision_id="")

    def test_report_type_empty_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reporting_dec(report_type="")

    def test_frozen_immutability(self):
        obj = _reporting_dec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.decision_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        d = _reporting_dec().to_dict()
        assert d["scope"] is RollupScope.PORTFOLIO
        assert d["window"] is MetricWindow.MONTHLY

    def test_to_dict_all_keys(self):
        d = _reporting_dec().to_dict()
        expected_keys = {
            "decision_id", "report_type", "scope", "scope_ref_id",
            "window", "include_trends", "include_breakdowns", "reason",
            "decided_at",
        }
        assert expected_keys <= set(d.keys())

    def test_bad_decided_at(self):
        with pytest.raises((ValueError, TypeError)):
            _reporting_dec(decided_at=BAD_DT)

    def test_include_trends_false(self):
        obj = _reporting_dec(include_trends=False)
        assert obj.include_trends is False

    def test_include_breakdowns_true(self):
        obj = _reporting_dec(include_breakdowns=True)
        assert obj.include_breakdowns is True

    def test_all_rollup_scopes(self):
        for s in RollupScope:
            obj = _reporting_dec(scope=s)
            assert obj.scope is s

    def test_all_metric_windows(self):
        for w in MetricWindow:
            obj = _reporting_dec(window=w)
            assert obj.window is w

    def test_whitespace_only_id_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reporting_dec(decision_id="   ")

    def test_whitespace_only_report_type_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _reporting_dec(report_type="   ")
