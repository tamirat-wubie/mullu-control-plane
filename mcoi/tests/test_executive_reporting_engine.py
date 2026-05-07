"""Purpose: comprehensive tests for the executive-reporting engine.
Governance scope: KPI registration, metric recording, rollup computation,
    trend analysis, report generation, dashboard snapshots, status evaluation.
Dependencies: executive_reporting engine + contracts, event_spine, invariants.
Invariants:
  - No duplicate KPI or value IDs.
  - Trends are deterministic given metric history.
  - All returns are immutable.
  - Every mutation emits an event.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.executive_reporting import ExecutiveReportingEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.executive_reporting import (
    KPIKind,
    MetricWindow,
    RollupScope,
    TrendDirection,
    ReportStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DT = "2025-01-01T00:00:00+00:00"
DT2 = "2025-01-02T00:00:00+00:00"
DT3 = "2025-01-03T00:00:00+00:00"
DT4 = "2025-01-04T00:00:00+00:00"
DT_END = "2025-06-15T12:30:00+00:00"


def _engine():
    es = EventSpineEngine()
    return es, ExecutiveReportingEngine(es)


# ===================================================================
# TestInit
# ===================================================================

class TestInit:
    """Tests for __init__ validation."""

    def test_accepts_event_spine_engine(self):
        es = EventSpineEngine()
        eng = ExecutiveReportingEngine(es)
        assert eng.kpi_count == 0

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingEngine(None)

    def test_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingEngine("not-an-engine")

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingEngine({})

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExecutiveReportingEngine(42)

    def test_initial_counts_zero(self):
        _, eng = _engine()
        assert eng.kpi_count == 0
        assert eng.metric_count == 0
        assert eng.report_count == 0


# ===================================================================
# TestRegisterKPI
# ===================================================================

class TestRegisterKPI:
    """Tests for register_kpi."""

    def test_basic_registration(self):
        _, eng = _engine()
        kpi = eng.register_kpi("kpi-1", "Completion Rate", KPIKind.CAMPAIGN_COMPLETION_RATE)
        assert kpi.kpi_id == "kpi-1"
        assert kpi.name == "Completion Rate"
        assert kpi.kind == KPIKind.CAMPAIGN_COMPLETION_RATE

    def test_kpi_count_increments(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert eng.kpi_count == 1
        eng.register_kpi("k2", "K2", KPIKind.CUSTOM)
        assert eng.kpi_count == 2

    def test_duplicate_kpi_id_raises(self):
        _, eng = _engine()
        eng.register_kpi("kpi-dup", "First", KPIKind.CUSTOM)
        with pytest.raises(RuntimeCoreInvariantError, match="^KPI already exists$") as excinfo:
            eng.register_kpi("kpi-dup", "Second", KPIKind.CUSTOM)
        assert "kpi-dup" not in str(excinfo.value)

    def test_default_window(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert kpi.window == MetricWindow.DAILY

    def test_custom_window(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, window=MetricWindow.WEEKLY)
        assert kpi.window == MetricWindow.WEEKLY

    def test_all_windows(self):
        _, eng = _engine()
        for i, w in enumerate(MetricWindow):
            kpi = eng.register_kpi(f"k-{i}", f"K{i}", KPIKind.CUSTOM, window=w)
            assert kpi.window == w

    def test_default_scope(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert kpi.scope == RollupScope.GLOBAL

    def test_custom_scope(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, scope=RollupScope.TEAM)
        assert kpi.scope == RollupScope.TEAM

    def test_higher_is_better_default_true(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert kpi.higher_is_better is True

    def test_higher_is_better_false(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=False)
        assert kpi.higher_is_better is False

    def test_description(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, description="A test KPI")
        assert kpi.description == "A test KPI"

    def test_unit(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, unit="%")
        assert kpi.unit == "%"

    def test_target_value(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, target_value=95.0)
        assert kpi.target_value == 95.0

    def test_thresholds(self):
        _, eng = _engine()
        kpi = eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            warning_threshold=80.0,
            critical_threshold=60.0,
        )
        assert kpi.warning_threshold == 80.0
        assert kpi.critical_threshold == 60.0

    def test_tags(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, tags=("a", "b"))
        assert kpi.tags == ("a", "b")

    def test_metadata(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, metadata={"team": "alpha"})
        assert kpi.metadata["team"] == "alpha"

    def test_scope_ref_id_defaults_to_kpi_id(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert kpi.scope_ref_id == "k1"

    def test_scope_ref_id_explicit(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM, scope_ref_id="team-alpha")
        assert kpi.scope_ref_id == "team-alpha"

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        after = len(es.list_events())
        assert after == before + 1

    def test_all_kpi_kinds(self):
        _, eng = _engine()
        for i, kind in enumerate(KPIKind):
            kpi = eng.register_kpi(f"k-{i}", f"K{i}", kind)
            assert kpi.kind == kind


# ===================================================================
# TestGetKPI
# ===================================================================

class TestGetKPI:
    """Tests for get_kpi."""

    def test_returns_registered_kpi(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        result = eng.get_kpi("k1")
        assert result is not None
        assert result.kpi_id == "k1"

    def test_returns_none_for_unknown(self):
        _, eng = _engine()
        assert eng.get_kpi("nonexistent") is None

    def test_returns_none_on_empty_engine(self):
        _, eng = _engine()
        assert eng.get_kpi("any") is None


# ===================================================================
# TestRecordMetric
# ===================================================================

class TestRecordMetric:
    """Tests for record_metric."""

    def test_basic_recording(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 42.0, DT, DT2)
        assert val.value_id == "v1"
        assert val.kpi_id == "k1"
        assert val.value == 42.0

    def test_metric_count_increments(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert eng.metric_count == 1
        eng.record_metric("v2", "k1", 2.0, DT2, DT3)
        assert eng.metric_count == 2

    def test_duplicate_value_id_raises(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 1.0, DT, DT2)
        with pytest.raises(RuntimeCoreInvariantError, match="^metric value already exists$") as excinfo:
            eng.record_metric("v1", "k1", 2.0, DT2, DT3)
        assert "v1" not in str(excinfo.value)

    def test_unknown_kpi_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^KPI not found$") as excinfo:
            eng.record_metric("v1", "unknown-kpi", 1.0, DT, DT2)
        assert "unknown-kpi" not in str(excinfo.value)

    def test_default_window(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert val.window == MetricWindow.DAILY

    def test_custom_window(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2, window=MetricWindow.MONTHLY)
        assert val.window == MetricWindow.MONTHLY

    def test_default_scope(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert val.scope == RollupScope.GLOBAL

    def test_custom_scope(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2, scope=RollupScope.TEAM)
        assert val.scope == RollupScope.TEAM

    def test_scope_ref_id_defaults_to_kpi_id(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert val.scope_ref_id == "k1"

    def test_scope_ref_id_explicit(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2, scope_ref_id="team-a")
        assert val.scope_ref_id == "team-a"

    def test_sample_count_default(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert val.sample_count == 1

    def test_sample_count_custom(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 1.0, DT, DT2, sample_count=100)
        assert val.sample_count == 100

    def test_emits_event(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        before = len(es.list_events())
        eng.record_metric("v1", "k1", 1.0, DT, DT2)
        after = len(es.list_events())
        assert after == before + 1

    def test_negative_value_allowed(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", -5.0, DT, DT2)
        assert val.value == -5.0

    def test_zero_value_allowed(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 0.0, DT, DT2)
        assert val.value == 0.0


# ===================================================================
# TestGetValues
# ===================================================================

class TestGetValues:
    """Tests for get_values."""

    def test_empty_when_no_values(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert eng.get_values("k1") == ()

    def test_returns_recorded_values(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        vals = eng.get_values("k1")
        assert len(vals) == 2
        assert vals[0].value == 10.0
        assert vals[1].value == 20.0

    def test_returns_tuple(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        result = eng.get_values("k1")
        assert isinstance(result, tuple)

    def test_empty_for_unknown_kpi(self):
        _, eng = _engine()
        assert eng.get_values("nonexistent") == ()


# ===================================================================
# TestRollup
# ===================================================================

class TestRollup:
    """Tests for rollup computation."""

    def test_basic_rollup(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        r = eng.rollup("k1", DT, DT3)
        assert r.total == 30.0
        assert r.count == 2
        assert r.average == 15.0
        assert r.minimum == 10.0
        assert r.maximum == 20.0

    def test_rollup_unknown_kpi_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^KPI not found$") as excinfo:
            eng.rollup("nonexistent", DT, DT2)
        assert "nonexistent" not in str(excinfo.value)

    def test_rollup_no_values(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        r = eng.rollup("k1", DT, DT2)
        assert r.total == 0.0
        assert r.count == 0
        assert r.average == 0.0
        assert r.minimum == 0.0
        assert r.maximum == 0.0

    def test_rollup_single_value(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 42.0, DT, DT2)
        r = eng.rollup("k1", DT, DT2)
        assert r.total == 42.0
        assert r.count == 1
        assert r.average == 42.0
        assert r.minimum == 42.0
        assert r.maximum == 42.0

    def test_rollup_filters_by_scope_ref_id(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2, scope_ref_id="team-a")
        eng.record_metric("v2", "k1", 20.0, DT2, DT3, scope_ref_id="team-b")
        eng.record_metric("v3", "k1", 30.0, DT3, DT4, scope_ref_id="team-a")

        r_a = eng.rollup("k1", DT, DT4, scope_ref_id="team-a")
        assert r_a.count == 2
        assert r_a.total == 40.0

        r_b = eng.rollup("k1", DT, DT4, scope_ref_id="team-b")
        assert r_b.count == 1
        assert r_b.total == 20.0

    def test_rollup_emits_event(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        before = len(es.list_events())
        eng.rollup("k1", DT, DT2)
        after = len(es.list_events())
        assert after == before + 1

    def test_rollup_kpi_id_matches(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 5.0, DT, DT2)
        r = eng.rollup("k1", DT, DT2)
        assert r.kpi_id == "k1"

    def test_rollup_scope_ref_id_defaults(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 5.0, DT, DT2)
        r = eng.rollup("k1", DT, DT2)
        assert r.scope_ref_id == "k1"

    def test_get_rollups(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 5.0, DT, DT2)
        eng.rollup("k1", DT, DT2)
        rollups = eng.get_rollups("k1")
        assert len(rollups) == 1

    def test_get_rollups_empty(self):
        _, eng = _engine()
        assert eng.get_rollups("nonexistent") == ()


# ===================================================================
# TestComputeTrend
# ===================================================================

class TestComputeTrend:
    """Tests for compute_trend."""

    def test_insufficient_data_no_values(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.INSUFFICIENT_DATA
        assert t.data_points == 0

    def test_insufficient_data_one_value(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.INSUFFICIENT_DATA
        assert t.data_points == 1
        assert t.current_value == 10.0

    def test_improving_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=True)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.IMPROVING
        assert t.current_value == 20.0
        assert t.previous_value == 10.0

    def test_degrading_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=True)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 50.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.DEGRADING

    def test_improving_lower_is_better(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=False)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 50.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.IMPROVING

    def test_degrading_lower_is_better(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=False)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.DEGRADING

    def test_stable_when_change_under_5pct(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 104.0, DT2, DT3)  # 4% change
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.STABLE

    def test_stable_exact_boundary(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 104.99, DT2, DT3)  # <5% change
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.STABLE

    def test_change_pct_computed(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 150.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert abs(t.change_pct - 0.5) < 0.001

    def test_unknown_kpi_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^KPI not found$") as excinfo:
            eng.compute_trend("nonexistent")
        assert "nonexistent" not in str(excinfo.value)

    def test_emits_event_when_sufficient_data(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        before = len(es.list_events())
        eng.compute_trend("k1")
        after = len(es.list_events())
        assert after == before + 1

    def test_get_trends(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        eng.compute_trend("k1")
        trends = eng.get_trends("k1")
        assert len(trends) == 1

    def test_get_trends_empty(self):
        _, eng = _engine()
        assert eng.get_trends("nonexistent") == ()

    def test_uses_last_two_values_by_period_end(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 100.0, DT2, DT3)
        eng.record_metric("v3", "k1", 110.0, DT3, DT4)
        t = eng.compute_trend("k1")
        assert t.previous_value == 100.0
        assert t.current_value == 110.0
        assert t.data_points == 3

    def test_trend_with_scope_ref_filter(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2, scope_ref_id="team-a")
        eng.record_metric("v2", "k1", 20.0, DT2, DT3, scope_ref_id="team-a")
        eng.record_metric("v3", "k1", 100.0, DT, DT2, scope_ref_id="team-b")
        t = eng.compute_trend("k1", scope_ref_id="team-a")
        assert t.current_value == 20.0
        assert t.previous_value == 10.0

    def test_trend_scope_ref_insufficient_data(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2, scope_ref_id="team-a")
        eng.record_metric("v2", "k1", 20.0, DT2, DT3, scope_ref_id="team-b")
        t = eng.compute_trend("k1", scope_ref_id="team-a")
        assert t.direction == TrendDirection.INSUFFICIENT_DATA

    def test_change_from_zero_positive(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 0.0, DT, DT2)
        eng.record_metric("v2", "k1", 10.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.change_pct == 1.0

    def test_change_from_zero_to_zero(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 0.0, DT, DT2)
        eng.record_metric("v2", "k1", 0.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.change_pct == 0.0


# ===================================================================
# TestBuildOutcomeReport
# ===================================================================

class TestBuildOutcomeReport:
    """Tests for build_outcome_report."""

    def test_basic_outcome_report(self):
        _, eng = _engine()
        r = eng.build_outcome_report(
            "rpt-1", "Q1 Outcomes",
            scope=RollupScope.GLOBAL,
            total_campaigns=10,
            completed_campaigns=8,
            failed_campaigns=1,
            blocked_campaigns=1,
            avg_duration_seconds=3600.0,
            escalation_count=2,
            overdue_count=1,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.report_id == "rpt-1"
        assert r.title == "Q1 Outcomes"
        assert r.completion_rate == 0.8

    def test_completion_rate_zero_campaigns(self):
        _, eng = _engine()
        r = eng.build_outcome_report(
            "rpt-1", "Empty",
            total_campaigns=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.completion_rate == 0.0

    def test_completion_rate_all_completed(self):
        _, eng = _engine()
        r = eng.build_outcome_report(
            "rpt-1", "Perfect",
            total_campaigns=5,
            completed_campaigns=5,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.completion_rate == 1.0

    def test_report_count_increments(self):
        _, eng = _engine()
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        assert eng.report_count == 1

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        after = len(es.list_events())
        assert after == before + 1

    def test_metadata(self):
        _, eng = _engine()
        r = eng.build_outcome_report(
            "rpt-1", "M",
            period_start=DT,
            period_end=DT_END,
            metadata={"region": "us-east"},
        )
        assert r.metadata["region"] == "us-east"

    def test_scope_ref_defaults_to_report_id(self):
        _, eng = _engine()
        r = eng.build_outcome_report("rpt-1", "R1", period_start=DT, period_end=DT_END)
        assert r.scope_ref_id == "rpt-1"


# ===================================================================
# TestBuildEfficiencyReport
# ===================================================================

class TestBuildEfficiencyReport:
    """Tests for build_efficiency_report."""

    def test_basic_efficiency_report(self):
        _, eng = _engine()
        r = eng.build_efficiency_report(
            "eff-1", "Team Efficiency",
            total_actions=100,
            successful_actions=90,
            failed_actions=10,
            avg_latency_seconds=0.5,
            waiting_on_human_seconds=3600.0,
            utilization=0.85,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 0.9
        assert r.waiting_on_human_seconds == 3600.0
        assert r.utilization == 0.85

    def test_success_rate_zero_actions(self):
        _, eng = _engine()
        r = eng.build_efficiency_report(
            "eff-1", "Empty",
            total_actions=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 0.0

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.build_efficiency_report("eff-1", "E", period_start=DT, period_end=DT_END)
        after = len(es.list_events())
        assert after == before + 1

    def test_scope(self):
        _, eng = _engine()
        r = eng.build_efficiency_report(
            "eff-1", "E",
            scope=RollupScope.TEAM,
            scope_ref_id="team-beta",
            period_start=DT,
            period_end=DT_END,
        )
        assert r.scope == RollupScope.TEAM
        assert r.scope_ref_id == "team-beta"


# ===================================================================
# TestBuildCostEffectivenessReport
# ===================================================================

class TestBuildCostEffectivenessReport:
    """Tests for build_cost_effectiveness_report."""

    def test_basic_cost_report(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "Budget Analysis",
            total_spend=5000.0,
            budget_limit=10000.0,
            completed_campaigns=10,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.burn_rate == 0.5
        assert r.cost_per_completion == 500.0
        assert r.roi_estimate == 10 / 5000.0

    def test_burn_rate_zero_limit(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "No Budget",
            total_spend=1000.0,
            budget_limit=0.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.burn_rate == 0.0

    def test_cost_per_completion_zero_campaigns(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "No Completions",
            total_spend=1000.0,
            budget_limit=2000.0,
            completed_campaigns=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.cost_per_completion == 0.0

    def test_roi_zero_spend(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "No Spend",
            total_spend=0.0,
            budget_limit=10000.0,
            completed_campaigns=5,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.roi_estimate == 0.0

    def test_currency_default(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "Curr",
            period_start=DT,
            period_end=DT_END,
        )
        assert r.currency == "USD"

    def test_currency_custom(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "Curr",
            currency="EUR",
            period_start=DT,
            period_end=DT_END,
        )
        assert r.currency == "EUR"

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.build_cost_effectiveness_report("cost-1", "C", period_start=DT, period_end=DT_END)
        after = len(es.list_events())
        assert after == before + 1

    def test_burn_rate_capped_at_one(self):
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "cost-1", "Over budget",
            total_spend=15000.0,
            budget_limit=10000.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.burn_rate == 1.0


# ===================================================================
# TestBuildReliabilityReport
# ===================================================================

class TestBuildReliabilityReport:
    """Tests for build_reliability_report."""

    def test_basic_reliability_report(self):
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-1", "System Reliability",
            total_operations=1000,
            successful_operations=950,
            failed_operations=50,
            fault_drill_count=10,
            fault_drill_pass_count=8,
            recovery_count=5,
            mean_time_to_recovery_seconds=120.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 0.95
        assert r.fault_drill_success_rate == 0.8
        assert r.recovery_count == 5
        assert r.mean_time_to_recovery_seconds == 120.0

    def test_success_rate_zero_operations(self):
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-1", "Empty",
            total_operations=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 0.0

    def test_drill_rate_zero_drills(self):
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-1", "No drills",
            total_operations=100,
            successful_operations=100,
            fault_drill_count=0,
            fault_drill_pass_count=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.fault_drill_success_rate == 0.0

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.build_reliability_report("rel-1", "R", period_start=DT, period_end=DT_END)
        after = len(es.list_events())
        assert after == before + 1

    def test_scope_and_ref(self):
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-1", "R",
            scope=RollupScope.CONNECTOR,
            scope_ref_id="conn-123",
            period_start=DT,
            period_end=DT_END,
        )
        assert r.scope == RollupScope.CONNECTOR
        assert r.scope_ref_id == "conn-123"


# ===================================================================
# TestBuildDashboardSnapshot
# ===================================================================

class TestBuildDashboardSnapshot:
    """Tests for build_dashboard_snapshot."""

    def test_basic_snapshot(self):
        _, eng = _engine()
        snap = eng.build_dashboard_snapshot(
            "snap-1", "Daily Dashboard",
            active_campaigns=5,
            blocked_campaigns=1,
            active_budgets=3,
            total_spend=25000.0,
            budget_utilization=0.6,
            connector_health_pct=0.95,
            overall_trend=TrendDirection.IMPROVING,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.snapshot_id == "snap-1"
        assert snap.active_campaigns == 5
        assert snap.blocked_campaigns == 1

    def test_kpi_status_counting(self):
        _, eng = _engine()
        statuses = {
            "kpi-1": "on_target",
            "kpi-2": "on_target",
            "kpi-3": "warning",
            "kpi-4": "critical",
        }
        snap = eng.build_dashboard_snapshot(
            "snap-1", "Dashboard",
            kpi_statuses=statuses,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.total_kpis == 4
        assert snap.kpis_on_target == 2
        assert snap.kpis_warning == 1
        assert snap.kpis_critical == 1

    def test_no_kpi_statuses(self):
        _, eng = _engine()
        snap = eng.build_dashboard_snapshot(
            "snap-1", "Dashboard",
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.total_kpis == 0
        assert snap.kpis_on_target == 0

    def test_emits_event(self):
        es, eng = _engine()
        before = len(es.list_events())
        eng.build_dashboard_snapshot("snap-1", "D", period_start=DT, period_end=DT_END)
        after = len(es.list_events())
        assert after == before + 1

    def test_overall_trend(self):
        _, eng = _engine()
        snap = eng.build_dashboard_snapshot(
            "snap-1", "D",
            overall_trend=TrendDirection.DEGRADING,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.overall_trend == TrendDirection.DEGRADING

    def test_metadata(self):
        _, eng = _engine()
        snap = eng.build_dashboard_snapshot(
            "snap-1", "D",
            period_start=DT,
            period_end=DT_END,
            metadata={"generated_by": "cron"},
        )
        assert snap.metadata["generated_by"] == "cron"

    def test_all_kpis_on_target(self):
        _, eng = _engine()
        statuses = {"k1": "on_target", "k2": "on_target", "k3": "on_target"}
        snap = eng.build_dashboard_snapshot(
            "snap-1", "D",
            kpi_statuses=statuses,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.kpis_on_target == 3
        assert snap.kpis_warning == 0
        assert snap.kpis_critical == 0

    def test_all_kpis_critical(self):
        _, eng = _engine()
        statuses = {"k1": "critical", "k2": "critical"}
        snap = eng.build_dashboard_snapshot(
            "snap-1", "D",
            kpi_statuses=statuses,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.kpis_critical == 2
        assert snap.kpis_on_target == 0


# ===================================================================
# TestEvaluateKPIStatus
# ===================================================================

class TestEvaluateKPIStatus:
    """Tests for evaluate_kpi_status."""

    def test_insufficient_data_no_values(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert eng.evaluate_kpi_status("k1") == "insufficient_data"

    def test_on_target_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 90.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "on_target"

    def test_warning_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 65.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "warning"

    def test_critical_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 40.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "critical"

    def test_on_target_lower_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=False,
            warning_threshold=70.0,
            critical_threshold=90.0,
        )
        eng.record_metric("v1", "k1", 50.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "on_target"

    def test_warning_lower_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=False,
            warning_threshold=70.0,
            critical_threshold=90.0,
        )
        eng.record_metric("v1", "k1", 75.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "warning"

    def test_critical_lower_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=False,
            warning_threshold=70.0,
            critical_threshold=90.0,
        )
        eng.record_metric("v1", "k1", 95.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "critical"

    def test_unknown_kpi_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^KPI not found$") as excinfo:
            eng.evaluate_kpi_status("nonexistent")
        assert "nonexistent" not in str(excinfo.value)

    def test_uses_latest_value(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 40.0, DT, DT2)  # critical
        eng.record_metric("v2", "k1", 90.0, DT2, DT3)  # on_target (latest by period_end)
        assert eng.evaluate_kpi_status("k1") == "on_target"

    def test_on_target_when_thresholds_zero(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "on_target"

    def test_exactly_at_warning_threshold_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 70.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "warning"

    def test_exactly_at_critical_threshold_higher_is_better(self):
        _, eng = _engine()
        eng.register_kpi(
            "k1", "K1", KPIKind.CUSTOM,
            higher_is_better=True,
            warning_threshold=70.0,
            critical_threshold=50.0,
        )
        eng.record_metric("v1", "k1", 50.0, DT, DT2)
        assert eng.evaluate_kpi_status("k1") == "critical"


# ===================================================================
# TestProperties
# ===================================================================

class TestProperties:
    """Tests for kpi_count, metric_count, report_count."""

    def test_kpi_count(self):
        _, eng = _engine()
        assert eng.kpi_count == 0
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert eng.kpi_count == 1

    def test_metric_count(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        assert eng.metric_count == 0
        eng.record_metric("v1", "k1", 1.0, DT, DT2)
        assert eng.metric_count == 1

    def test_report_count_includes_all_types(self):
        _, eng = _engine()
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        eng.build_efficiency_report("r2", "R2", period_start=DT, period_end=DT_END)
        eng.build_cost_effectiveness_report("r3", "R3", period_start=DT, period_end=DT_END)
        eng.build_reliability_report("r4", "R4", period_start=DT, period_end=DT_END)
        eng.build_dashboard_snapshot("s1", "S1", period_start=DT, period_end=DT_END)
        assert eng.report_count == 5


# ===================================================================
# TestGetReports
# ===================================================================

class TestGetReports:
    """Tests for get_reports."""

    def test_empty(self):
        _, eng = _engine()
        assert eng.get_reports() == ()

    def test_returns_all_reports(self):
        _, eng = _engine()
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        eng.build_efficiency_report("r2", "R2", period_start=DT, period_end=DT_END)
        assert len(eng.get_reports()) == 2

    def test_returns_tuple(self):
        _, eng = _engine()
        assert isinstance(eng.get_reports(), tuple)


# ===================================================================
# TestStateHash
# ===================================================================

class TestStateHash:
    """Tests for state_hash."""

    def test_returns_16_hex_chars(self):
        _, eng = _engine()
        h = eng.state_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_changes_after_kpi_registration(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_recording_metric(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        h1 = eng.state_hash()
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_deterministic(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_changes_after_rollup(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 1.0, DT, DT2)
        h1 = eng.state_hash()
        eng.rollup("k1", DT, DT2)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_report(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        h2 = eng.state_hash()
        assert h1 != h2


# ===================================================================
# TestEventEmission
# ===================================================================

class TestEventEmission:
    """Tests that every mutation emits events."""

    def test_register_kpi_emits(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        events = es.list_events()
        assert len(events) >= 1

    def test_record_metric_emits(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        count_before = len(es.list_events())
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        assert len(es.list_events()) > count_before

    def test_rollup_emits(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        count_before = len(es.list_events())
        eng.rollup("k1", DT, DT2)
        assert len(es.list_events()) > count_before

    def test_compute_trend_with_data_emits(self):
        es, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        count_before = len(es.list_events())
        eng.compute_trend("k1")
        assert len(es.list_events()) > count_before

    def test_outcome_report_emits(self):
        es, eng = _engine()
        count_before = len(es.list_events())
        eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        assert len(es.list_events()) > count_before

    def test_efficiency_report_emits(self):
        es, eng = _engine()
        count_before = len(es.list_events())
        eng.build_efficiency_report("r1", "R1", period_start=DT, period_end=DT_END)
        assert len(es.list_events()) > count_before

    def test_cost_effectiveness_report_emits(self):
        es, eng = _engine()
        count_before = len(es.list_events())
        eng.build_cost_effectiveness_report("r1", "R1", period_start=DT, period_end=DT_END)
        assert len(es.list_events()) > count_before

    def test_reliability_report_emits(self):
        es, eng = _engine()
        count_before = len(es.list_events())
        eng.build_reliability_report("r1", "R1", period_start=DT, period_end=DT_END)
        assert len(es.list_events()) > count_before

    def test_dashboard_snapshot_emits(self):
        es, eng = _engine()
        count_before = len(es.list_events())
        eng.build_dashboard_snapshot("s1", "S1", period_start=DT, period_end=DT_END)
        assert len(es.list_events()) > count_before


# ===================================================================
# TestGoldenScenarios
# ===================================================================

class TestGoldenScenarios:
    """Eight golden end-to-end scenarios."""

    def test_campaign_outcome_rollup_by_team(self):
        """Register KPI, record metrics for two teams, rollup each with scope_ref_id filter."""
        _, eng = _engine()
        eng.register_kpi(
            "completion-rate", "Campaign Completion Rate",
            KPIKind.CAMPAIGN_COMPLETION_RATE,
            scope=RollupScope.TEAM,
        )

        # Team Alpha: 3 metrics
        eng.record_metric("v-a1", "completion-rate", 0.80, DT, DT2, scope_ref_id="team-alpha")
        eng.record_metric("v-a2", "completion-rate", 0.85, DT2, DT3, scope_ref_id="team-alpha")
        eng.record_metric("v-a3", "completion-rate", 0.90, DT3, DT4, scope_ref_id="team-alpha")

        # Team Beta: 2 metrics
        eng.record_metric("v-b1", "completion-rate", 0.70, DT, DT2, scope_ref_id="team-beta")
        eng.record_metric("v-b2", "completion-rate", 0.60, DT2, DT3, scope_ref_id="team-beta")

        # Rollup per team
        r_alpha = eng.rollup(
            "completion-rate", DT, DT4,
            scope=RollupScope.TEAM,
            scope_ref_id="team-alpha",
        )
        assert r_alpha.count == 3
        assert abs(r_alpha.total - 2.55) < 0.001
        assert abs(r_alpha.average - 0.85) < 0.001
        assert r_alpha.minimum == 0.80
        assert r_alpha.maximum == 0.90

        r_beta = eng.rollup(
            "completion-rate", DT, DT4,
            scope=RollupScope.TEAM,
            scope_ref_id="team-beta",
        )
        assert r_beta.count == 2
        assert abs(r_beta.total - 1.30) < 0.001
        assert abs(r_beta.average - 0.65) < 0.001
        assert r_beta.minimum == 0.60
        assert r_beta.maximum == 0.70

    def test_budget_burn_plus_completion(self):
        """Build cost-effectiveness report, verify burn_rate and cost_per_completion."""
        _, eng = _engine()
        r = eng.build_cost_effectiveness_report(
            "budget-rpt-1", "Q1 Budget vs Completion",
            scope=RollupScope.PORTFOLIO,
            scope_ref_id="portfolio-main",
            total_spend=7500.0,
            budget_limit=10000.0,
            completed_campaigns=15,
            currency="USD",
            period_start=DT,
            period_end=DT_END,
        )
        assert r.burn_rate == 0.75
        assert r.cost_per_completion == 500.0
        assert r.roi_estimate == 15 / 7500.0
        assert r.scope == RollupScope.PORTFOLIO
        assert r.scope_ref_id == "portfolio-main"
        assert r.currency == "USD"

    def test_connector_failures_degrade_trend(self):
        """Register KPI higher_is_better=True, record decreasing values, trend shows DEGRADING."""
        _, eng = _engine()
        eng.register_kpi(
            "conn-success", "Connector Success Rate",
            KPIKind.CONNECTOR_SUCCESS_RATE,
            higher_is_better=True,
        )
        eng.record_metric("cv1", "conn-success", 0.95, DT, DT2)
        eng.record_metric("cv2", "conn-success", 0.70, DT2, DT3)  # dropped significantly

        t = eng.compute_trend("conn-success")
        assert t.direction == TrendDirection.DEGRADING
        assert t.current_value == 0.70
        assert t.previous_value == 0.95
        assert t.change_pct < 0

    def test_waiting_on_human_increases_delay(self):
        """Build efficiency report with high waiting_on_human_seconds."""
        _, eng = _engine()
        r = eng.build_efficiency_report(
            "eff-human-wait", "Human Wait Analysis",
            scope=RollupScope.FUNCTION,
            scope_ref_id="approvals-fn",
            total_actions=200,
            successful_actions=180,
            failed_actions=20,
            avg_latency_seconds=2.5,
            waiting_on_human_seconds=86400.0,  # 24 hours
            utilization=0.65,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.waiting_on_human_seconds == 86400.0
        assert r.success_rate == 0.9
        assert r.utilization == 0.65
        assert r.scope == RollupScope.FUNCTION
        assert r.scope_ref_id == "approvals-fn"

    def test_portfolio_blocked_in_snapshot(self):
        """Build dashboard with blocked_campaigns > 0."""
        _, eng = _engine()
        statuses = {
            "kpi-a": "on_target",
            "kpi-b": "warning",
            "kpi-c": "critical",
        }
        snap = eng.build_dashboard_snapshot(
            "snap-blocked", "Portfolio Dashboard",
            kpi_statuses=statuses,
            active_campaigns=12,
            blocked_campaigns=3,
            active_budgets=5,
            total_spend=50000.0,
            budget_utilization=0.7,
            connector_health_pct=0.88,
            overall_trend=TrendDirection.DEGRADING,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.blocked_campaigns == 3
        assert snap.active_campaigns == 12
        assert snap.total_kpis == 3
        assert snap.kpis_on_target == 1
        assert snap.kpis_warning == 1
        assert snap.kpis_critical == 1
        assert snap.overall_trend == TrendDirection.DEGRADING

    def test_fault_drill_feeds_reliability(self):
        """Build reliability report with drill data, verify drill_success_rate."""
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-drills", "Fault Drill Report",
            scope=RollupScope.CONNECTOR,
            scope_ref_id="payment-gateway",
            total_operations=5000,
            successful_operations=4900,
            failed_operations=100,
            fault_drill_count=20,
            fault_drill_pass_count=17,
            recovery_count=15,
            mean_time_to_recovery_seconds=45.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.fault_drill_success_rate == 0.85
        assert r.success_rate == 0.98
        assert r.recovery_count == 15
        assert r.mean_time_to_recovery_seconds == 45.0
        assert r.scope == RollupScope.CONNECTOR
        assert r.scope_ref_id == "payment-gateway"

    def test_replay_preserves_state(self):
        """State hash changes after recording metrics."""
        _, eng = _engine()
        h_initial = eng.state_hash()

        eng.register_kpi("kpi-replay", "Replay KPI", KPIKind.CUSTOM)
        h_after_kpi = eng.state_hash()
        assert h_initial != h_after_kpi

        eng.record_metric("rv1", "kpi-replay", 10.0, DT, DT2)
        h_after_metric1 = eng.state_hash()
        assert h_after_kpi != h_after_metric1

        eng.record_metric("rv2", "kpi-replay", 20.0, DT2, DT3)
        h_after_metric2 = eng.state_hash()
        assert h_after_metric1 != h_after_metric2

        # Hash is deterministic at each point
        assert eng.state_hash() == h_after_metric2

    def test_domain_pack_kpi_rollup(self):
        """Register KPI with scope=DOMAIN_PACK, record metrics with different
        scope_ref_ids, rollup filters by scope_ref_id."""
        _, eng = _engine()
        eng.register_kpi(
            "dp-throughput", "Domain Pack Throughput",
            KPIKind.CUSTOM,
            scope=RollupScope.DOMAIN_PACK,
            unit="ops/sec",
        )

        # Domain pack A
        eng.record_metric("dp-a1", "dp-throughput", 100.0, DT, DT2, scope_ref_id="dp-finance")
        eng.record_metric("dp-a2", "dp-throughput", 120.0, DT2, DT3, scope_ref_id="dp-finance")

        # Domain pack B
        eng.record_metric("dp-b1", "dp-throughput", 200.0, DT, DT2, scope_ref_id="dp-healthcare")
        eng.record_metric("dp-b2", "dp-throughput", 250.0, DT2, DT3, scope_ref_id="dp-healthcare")
        eng.record_metric("dp-b3", "dp-throughput", 230.0, DT3, DT4, scope_ref_id="dp-healthcare")

        r_finance = eng.rollup(
            "dp-throughput", DT, DT4,
            scope=RollupScope.DOMAIN_PACK,
            scope_ref_id="dp-finance",
        )
        assert r_finance.count == 2
        assert r_finance.total == 220.0
        assert r_finance.average == 110.0

        r_health = eng.rollup(
            "dp-throughput", DT, DT4,
            scope=RollupScope.DOMAIN_PACK,
            scope_ref_id="dp-healthcare",
        )
        assert r_health.count == 3
        assert r_health.total == 680.0
        assert abs(r_health.average - 680.0 / 3) < 0.001
        assert r_health.minimum == 200.0
        assert r_health.maximum == 250.0

        # Global rollup (no filter) includes all
        r_all = eng.rollup("dp-throughput", DT, DT4, scope=RollupScope.DOMAIN_PACK)
        assert r_all.count == 5
        assert r_all.total == 900.0


# ===================================================================
# TestEdgeCases
# ===================================================================

class TestEdgeCases:
    """Edge cases and additional coverage."""

    def test_many_metrics_for_one_kpi(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        for i in range(20):
            eng.record_metric(
                f"v{i}", "k1", float(i),
                f"2025-01-{i+1:02d}T00:00:00+00:00",
                f"2025-01-{i+2:02d}T00:00:00+00:00",
            )
        assert eng.metric_count == 20
        vals = eng.get_values("k1")
        assert len(vals) == 20

    def test_multiple_kpis_independent(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.register_kpi("k2", "K2", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k2", 20.0, DT, DT2)
        assert eng.get_values("k1")[0].value == 10.0
        assert eng.get_values("k2")[0].value == 20.0

    def test_rollup_with_window_param(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 5.0, DT, DT2)
        r = eng.rollup("k1", DT, DT2, window=MetricWindow.WEEKLY)
        assert r.window == MetricWindow.WEEKLY

    def test_trend_with_window_param(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        t = eng.compute_trend("k1", window=MetricWindow.MONTHLY)
        assert t.window == MetricWindow.MONTHLY

    def test_large_negative_trend(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM, higher_is_better=True)
        eng.record_metric("v1", "k1", 100.0, DT, DT2)
        eng.record_metric("v2", "k1", 1.0, DT2, DT3)
        t = eng.compute_trend("k1")
        assert t.direction == TrendDirection.DEGRADING
        assert t.change_pct < -0.5

    def test_outcome_report_escalation_and_overdue(self):
        _, eng = _engine()
        r = eng.build_outcome_report(
            "rpt-esc", "Escalation Heavy",
            total_campaigns=20,
            completed_campaigns=10,
            failed_campaigns=5,
            blocked_campaigns=5,
            escalation_count=15,
            overdue_count=8,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.escalation_count == 15
        assert r.overdue_count == 8
        assert r.completion_rate == 0.5

    def test_efficiency_report_full_utilization(self):
        _, eng = _engine()
        r = eng.build_efficiency_report(
            "eff-full", "Full Utilization",
            total_actions=100,
            successful_actions=100,
            utilization=1.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 1.0
        assert r.utilization == 1.0

    def test_reliability_all_operations_successful(self):
        _, eng = _engine()
        r = eng.build_reliability_report(
            "rel-perfect", "Perfect Reliability",
            total_operations=500,
            successful_operations=500,
            failed_operations=0,
            period_start=DT,
            period_end=DT_END,
        )
        assert r.success_rate == 1.0

    def test_dashboard_with_zero_spend(self):
        _, eng = _engine()
        snap = eng.build_dashboard_snapshot(
            "snap-zero", "Zero Spend",
            total_spend=0.0,
            budget_utilization=0.0,
            period_start=DT,
            period_end=DT_END,
        )
        assert snap.total_spend == 0.0
        assert snap.budget_utilization == 0.0

    def test_multiple_rollups_same_kpi(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.rollup("k1", DT, DT2)
        eng.rollup("k1", DT, DT2)
        rollups = eng.get_rollups("k1")
        assert len(rollups) == 2

    def test_multiple_trends_same_kpi(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        eng.record_metric("v2", "k1", 20.0, DT2, DT3)
        eng.compute_trend("k1")
        eng.compute_trend("k1")
        trends = eng.get_trends("k1")
        assert len(trends) == 2

    def test_kpi_frozen(self):
        _, eng = _engine()
        kpi = eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        with pytest.raises(AttributeError):
            kpi.name = "modified"

    def test_value_frozen(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        val = eng.record_metric("v1", "k1", 10.0, DT, DT2)
        with pytest.raises(AttributeError):
            val.value = 99.0

    def test_rollup_record_frozen(self):
        _, eng = _engine()
        eng.register_kpi("k1", "K1", KPIKind.CUSTOM)
        eng.record_metric("v1", "k1", 10.0, DT, DT2)
        r = eng.rollup("k1", DT, DT2)
        with pytest.raises(AttributeError):
            r.total = 999.0

    def test_outcome_report_frozen(self):
        _, eng = _engine()
        r = eng.build_outcome_report("r1", "R1", period_start=DT, period_end=DT_END)
        with pytest.raises(AttributeError):
            r.title = "modified"
