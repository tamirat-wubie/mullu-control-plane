"""Purpose: comprehensive tests for the ForecastingRuntimeEngine.
Governance scope: runtime-core tests only.
Dependencies: forecasting_runtime engine, event_spine, contracts, invariants.
Invariants: every mutation emits events, terminal guards hold, confidence bands
    are auto-derived, low-confidence blocks allocation, violations are idempotent.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.forecasting_runtime import ForecastingRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.forecasting_runtime import (
    AllocationDisposition,
    AllocationRecommendation,
    BudgetForecast,
    CapacityForecast,
    DemandSignal,
    DemandSignalKind,
    ForecastConfidenceBand,
    ForecastHorizon,
    ForecastRecord,
    ForecastSnapshot,
    ForecastStatus,
    RiskForecast,
    ScenarioModel,
    ScenarioProjection,
    ScenarioStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> ForecastingRuntimeEngine:
    return ForecastingRuntimeEngine(spine)


@pytest.fixture()
def engine_with_signal(engine: ForecastingRuntimeEngine) -> ForecastingRuntimeEngine:
    engine.register_signal("sig-1", "tenant-a", value=10.0)
    return engine


@pytest.fixture()
def engine_with_forecast(engine_with_signal: ForecastingRuntimeEngine) -> ForecastingRuntimeEngine:
    engine_with_signal.build_forecast("fc-1", "tenant-a", confidence=0.7)
    return engine_with_signal


@pytest.fixture()
def engine_with_scenario(engine_with_forecast: ForecastingRuntimeEngine) -> ForecastingRuntimeEngine:
    engine_with_forecast.build_scenario("sc-1", "tenant-a", "Test Scenario")
    return engine_with_forecast


# ===================================================================
# SECTION 1: Constructor validation
# ===================================================================


class TestConstructorValidation:
    def test_valid_event_spine_accepted(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        assert eng.signal_count == 0

    def test_none_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine(None)  # type: ignore[arg-type]

    def test_string_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine("not-an-engine")  # type: ignore[arg-type]

    def test_int_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine(42)  # type: ignore[arg-type]

    def test_dict_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine({})  # type: ignore[arg-type]

    def test_list_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine([])  # type: ignore[arg-type]

    def test_object_raises(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ForecastingRuntimeEngine(object())  # type: ignore[arg-type]


# ===================================================================
# SECTION 2: Initial property values
# ===================================================================


class TestInitialProperties:
    def test_signal_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.signal_count == 0

    def test_forecast_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.forecast_count == 0

    def test_scenario_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.scenario_count == 0

    def test_projection_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.projection_count == 0

    def test_recommendation_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.recommendation_count == 0

    def test_capacity_forecast_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.capacity_forecast_count == 0

    def test_budget_forecast_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.budget_forecast_count == 0

    def test_risk_forecast_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.risk_forecast_count == 0

    def test_violation_count_zero(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.violation_count == 0


# ===================================================================
# SECTION 3: Demand signals
# ===================================================================


class TestRegisterSignal:
    def test_returns_demand_signal(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert isinstance(s, DemandSignal)

    def test_signal_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.signal_id == "sig-1"

    def test_tenant_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.tenant_id == "tenant-a"

    def test_default_kind_is_request_volume(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.kind == DemandSignalKind.REQUEST_VOLUME

    def test_custom_kind(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a", kind=DemandSignalKind.CAPACITY_USAGE)
        assert s.kind == DemandSignalKind.CAPACITY_USAGE

    def test_default_scope_ref_id(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.scope_ref_id == ""

    def test_custom_scope_ref_id(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a", scope_ref_id="scope-x")
        assert s.scope_ref_id == "scope-x"

    def test_default_value(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.value == 0.0

    def test_custom_value(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a", value=42.5)
        assert s.value == 42.5

    def test_recorded_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert s.recorded_at != ""

    def test_increments_signal_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        assert engine.signal_count == 1

    def test_multiple_signals_increment(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-a")
        engine.register_signal("sig-3", "tenant-b")
        assert engine.signal_count == 3

    def test_duplicate_signal_id_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate signal_id"):
            engine.register_signal("sig-1", "tenant-a")

    def test_duplicate_does_not_increment(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        try:
            engine.register_signal("sig-1", "tenant-a")
        except RuntimeCoreInvariantError:
            pass
        assert engine.signal_count == 1

    def test_all_signal_kinds(self, engine: ForecastingRuntimeEngine) -> None:
        for i, kind in enumerate(DemandSignalKind):
            s = engine.register_signal(f"sig-{i}", "tenant-a", kind=kind)
            assert s.kind == kind

    def test_signal_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        with pytest.raises(AttributeError):
            s.value = 999.0  # type: ignore[misc]


class TestGetSignal:
    def test_retrieves_registered_signal(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", value=5.0)
        s = engine.get_signal("sig-1")
        assert s.signal_id == "sig-1"
        assert s.value == 5.0

    def test_unknown_signal_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown signal_id"):
            engine.get_signal("no-such-signal")

    def test_get_after_multiple_registers(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", value=1.0)
        engine.register_signal("sig-2", "tenant-b", value=2.0)
        assert engine.get_signal("sig-1").value == 1.0
        assert engine.get_signal("sig-2").value == 2.0


class TestSignalsForTenant:
    def test_empty_for_unknown_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        result = engine.signals_for_tenant("unknown")
        assert result == ()

    def test_returns_tuple(self, engine: ForecastingRuntimeEngine) -> None:
        result = engine.signals_for_tenant("tenant-a")
        assert isinstance(result, tuple)

    def test_filters_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-b")
        engine.register_signal("sig-3", "tenant-a")
        result = engine.signals_for_tenant("tenant-a")
        assert len(result) == 2
        ids = {s.signal_id for s in result}
        assert ids == {"sig-1", "sig-3"}

    def test_returns_empty_tuple_when_no_match(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        result = engine.signals_for_tenant("tenant-b")
        assert result == ()


# ===================================================================
# SECTION 4: Forecasts
# ===================================================================


class TestBuildForecast:
    def test_returns_forecast_record(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert isinstance(fc, ForecastRecord)

    def test_forecast_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.forecast_id == "fc-1"

    def test_tenant_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.tenant_id == "tenant-a"

    def test_status_is_active(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.status == ForecastStatus.ACTIVE

    def test_default_horizon_is_short(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.horizon == ForecastHorizon.SHORT

    def test_custom_horizon(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", horizon=ForecastHorizon.LONG)
        assert fc.horizon == ForecastHorizon.LONG

    def test_default_confidence(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.confidence == 0.5

    def test_custom_confidence(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.9)
        assert fc.confidence == 0.9

    def test_default_projected_value(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.projected_value == 0.0

    def test_custom_projected_value(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", projected_value=100.0)
        assert fc.projected_value == 100.0

    def test_created_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.created_at != ""

    def test_increments_forecast_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        assert engine.forecast_count == 1

    def test_duplicate_forecast_id_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate forecast_id"):
            engine.build_forecast("fc-1", "tenant-a")

    def test_forecast_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        with pytest.raises(AttributeError):
            fc.status = ForecastStatus.EXPIRED  # type: ignore[misc]

    def test_all_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            fc = engine.build_forecast(f"fc-{i}", "tenant-a", horizon=h)
            assert fc.horizon == h


class TestSignalAutoCounting:
    def test_zero_signals_counted_when_none(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.signal_count == 0

    def test_counts_matching_tenant_signals(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-a")
        engine.register_signal("sig-3", "tenant-b")
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert fc.signal_count == 2

    def test_counts_only_matching_scope(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", scope_ref_id="scope-x")
        engine.register_signal("sig-2", "tenant-a", scope_ref_id="scope-y")
        engine.register_signal("sig-3", "tenant-a", scope_ref_id="scope-x")
        fc = engine.build_forecast("fc-1", "tenant-a", scope_ref_id="scope-x")
        assert fc.signal_count == 2

    def test_empty_scope_counts_all_tenant_signals(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", scope_ref_id="scope-x")
        engine.register_signal("sig-2", "tenant-a", scope_ref_id="scope-y")
        fc = engine.build_forecast("fc-1", "tenant-a", scope_ref_id="")
        assert fc.signal_count == 2

    def test_signal_count_only_includes_current_signals(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        fc1 = engine.build_forecast("fc-1", "tenant-a")
        assert fc1.signal_count == 1
        engine.register_signal("sig-2", "tenant-a")
        fc2 = engine.build_forecast("fc-2", "tenant-a")
        assert fc2.signal_count == 2


class TestConfidenceBandDerivation:
    def test_very_low_at_0(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.0)
        assert fc.confidence_band == ForecastConfidenceBand.VERY_LOW

    def test_very_low_at_0_1(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.1)
        assert fc.confidence_band == ForecastConfidenceBand.VERY_LOW

    def test_very_low_at_0_29(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.29)
        assert fc.confidence_band == ForecastConfidenceBand.VERY_LOW

    def test_low_at_0_3(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.3)
        assert fc.confidence_band == ForecastConfidenceBand.LOW

    def test_low_at_0_4(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.4)
        assert fc.confidence_band == ForecastConfidenceBand.LOW

    def test_low_at_0_49(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.49)
        assert fc.confidence_band == ForecastConfidenceBand.LOW

    def test_medium_at_0_5(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.5)
        assert fc.confidence_band == ForecastConfidenceBand.MEDIUM

    def test_medium_at_0_6(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.6)
        assert fc.confidence_band == ForecastConfidenceBand.MEDIUM

    def test_medium_at_0_79(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.79)
        assert fc.confidence_band == ForecastConfidenceBand.MEDIUM

    def test_high_at_0_8(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.8)
        assert fc.confidence_band == ForecastConfidenceBand.HIGH

    def test_high_at_0_9(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.9)
        assert fc.confidence_band == ForecastConfidenceBand.HIGH

    def test_high_at_1_0(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=1.0)
        assert fc.confidence_band == ForecastConfidenceBand.HIGH


class TestGetForecast:
    def test_retrieves_built_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        fc = engine.get_forecast("fc-1")
        assert fc.forecast_id == "fc-1"

    def test_unknown_forecast_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown forecast_id"):
            engine.get_forecast("no-such-forecast")


class TestSupersedeForecast:
    def test_active_to_superseded(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        fc = engine_with_forecast.supersede_forecast("fc-1")
        assert fc.status == ForecastStatus.SUPERSEDED

    def test_preserves_fields(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        original = engine_with_forecast.get_forecast("fc-1")
        superseded = engine_with_forecast.supersede_forecast("fc-1")
        assert superseded.tenant_id == original.tenant_id
        assert superseded.confidence == original.confidence
        assert superseded.horizon == original.horizon

    def test_expired_cannot_be_superseded(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")

    def test_cancelled_cannot_be_superseded(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")

    def test_unknown_forecast_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.supersede_forecast("no-such")


class TestExpireForecast:
    def test_active_to_expired(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        fc = engine_with_forecast.expire_forecast("fc-1")
        assert fc.status == ForecastStatus.EXPIRED

    def test_expired_cannot_be_expired_again(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_forecast.expire_forecast("fc-1")

    def test_cancelled_cannot_be_expired(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_forecast.expire_forecast("fc-1")

    def test_superseded_can_be_expired(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.supersede_forecast("fc-1")
        fc = engine_with_forecast.expire_forecast("fc-1")
        assert fc.status == ForecastStatus.EXPIRED


class TestCancelForecast:
    def test_active_to_cancelled(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        fc = engine_with_forecast.cancel_forecast("fc-1")
        assert fc.status == ForecastStatus.CANCELLED

    def test_cancelled_cannot_be_cancelled_again(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_forecast.cancel_forecast("fc-1")

    def test_expired_cannot_be_cancelled(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_forecast.cancel_forecast("fc-1")

    def test_superseded_can_be_cancelled(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.supersede_forecast("fc-1")
        fc = engine_with_forecast.cancel_forecast("fc-1")
        assert fc.status == ForecastStatus.CANCELLED


class TestForecastsForTenant:
    def test_empty_for_unknown_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.forecasts_for_tenant("unknown") == ()

    def test_returns_tuple(self, engine: ForecastingRuntimeEngine) -> None:
        assert isinstance(engine.forecasts_for_tenant("tenant-a"), tuple)

    def test_filters_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.build_forecast("fc-2", "tenant-b")
        engine.build_forecast("fc-3", "tenant-a")
        result = engine.forecasts_for_tenant("tenant-a")
        assert len(result) == 2
        ids = {f.forecast_id for f in result}
        assert ids == {"fc-1", "fc-3"}


class TestTerminalStateGuards:
    """Cross-cutting terminal state guard tests."""

    def test_expire_then_supersede(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")

    def test_expire_then_cancel(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.cancel_forecast("fc-1")

    def test_cancel_then_supersede(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")

    def test_cancel_then_expire(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.expire_forecast("fc-1")


# ===================================================================
# SECTION 5: Scenarios
# ===================================================================


class TestBuildScenario:
    def test_returns_scenario_model(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "My Scenario")
        assert isinstance(sc, ScenarioModel)

    def test_scenario_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "My Scenario")
        assert sc.scenario_id == "sc-1"

    def test_name_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "Growth Plan")
        assert sc.name == "Growth Plan"

    def test_status_is_active(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S")
        assert sc.status == ScenarioStatus.ACTIVE

    def test_default_horizon_is_medium(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S")
        assert sc.horizon == ForecastHorizon.MEDIUM

    def test_custom_horizon(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S", horizon=ForecastHorizon.STRATEGIC)
        assert sc.horizon == ForecastHorizon.STRATEGIC

    def test_default_description(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S")
        assert sc.description == ""

    def test_custom_description(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S", description="A test scenario")
        assert sc.description == "A test scenario"

    def test_increments_scenario_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        assert engine.scenario_count == 1

    def test_duplicate_scenario_id_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate scenario_id"):
            engine.build_scenario("sc-1", "tenant-a", "S")

    def test_scenario_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S")
        with pytest.raises(AttributeError):
            sc.name = "changed"  # type: ignore[misc]


class TestGetScenario:
    def test_retrieves_built_scenario(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        sc = engine.get_scenario("sc-1")
        assert sc.scenario_id == "sc-1"

    def test_unknown_scenario_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown scenario_id"):
            engine.get_scenario("no-such")


class TestEvaluateScenario:
    def test_active_to_evaluated(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        sc = engine.evaluate_scenario("sc-1")
        assert sc.status == ScenarioStatus.EVALUATED

    def test_preserves_fields(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "My Name", description="Desc")
        sc = engine.evaluate_scenario("sc-1")
        assert sc.name == "My Name"
        assert sc.description == "Desc"
        assert sc.tenant_id == "tenant-a"

    def test_archived_cannot_be_evaluated(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.archive_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="archived"):
            engine.evaluate_scenario("sc-1")

    def test_evaluated_can_be_evaluated_again(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.evaluate_scenario("sc-1")
        sc = engine.evaluate_scenario("sc-1")
        assert sc.status == ScenarioStatus.EVALUATED


class TestArchiveScenario:
    def test_active_to_archived(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        sc = engine.archive_scenario("sc-1")
        assert sc.status == ScenarioStatus.ARCHIVED

    def test_evaluated_to_archived(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.evaluate_scenario("sc-1")
        sc = engine.archive_scenario("sc-1")
        assert sc.status == ScenarioStatus.ARCHIVED

    def test_already_archived_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.archive_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already archived"):
            engine.archive_scenario("sc-1")


class TestScenariosForTenant:
    def test_empty_for_unknown_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.scenarios_for_tenant("unknown") == ()

    def test_filters_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S1")
        engine.build_scenario("sc-2", "tenant-b", "S2")
        engine.build_scenario("sc-3", "tenant-a", "S3")
        result = engine.scenarios_for_tenant("tenant-a")
        assert len(result) == 2


# ===================================================================
# SECTION 6: Projections
# ===================================================================


class TestProjectScenario:
    def test_returns_scenario_projection(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert isinstance(proj, ScenarioProjection)

    def test_projection_id_preserved(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.projection_id == "proj-1"

    def test_scenario_id_preserved(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.scenario_id == "sc-1"

    def test_forecast_id_preserved(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.forecast_id == "fc-1"

    def test_default_projected_value(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.projected_value == 0.0

    def test_custom_projected_value(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1", projected_value=50.0)
        assert proj.projected_value == 50.0

    def test_default_probability(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.probability == 0.5

    def test_custom_probability(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1", probability=0.8)
        assert proj.probability == 0.8

    def test_default_impact_score(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.impact_score == 0.5

    def test_custom_impact_score(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1", impact_score=0.9)
        assert proj.impact_score == 0.9

    def test_projected_at_populated(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert proj.projected_at != ""

    def test_increments_projection_count(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        assert engine_with_scenario.projection_count == 1

    def test_duplicate_projection_id_raises(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate projection_id"):
            engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")

    def test_unknown_scenario_raises(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown scenario_id"):
            engine_with_forecast.project_scenario("proj-1", "no-such", "fc-1")

    def test_unknown_forecast_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown forecast_id"):
            engine.project_scenario("proj-1", "sc-1", "no-such")

    def test_both_unknown_raises_scenario_first(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown scenario_id"):
            engine.project_scenario("proj-1", "no-sc", "no-fc")

    def test_projection_is_frozen(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        proj = engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        with pytest.raises(AttributeError):
            proj.probability = 0.99  # type: ignore[misc]


class TestProjectionsForScenario:
    def test_empty_for_unknown_scenario(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.projections_for_scenario("unknown") == ()

    def test_filters_by_scenario(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        eng = engine_with_scenario
        eng.build_scenario("sc-2", "tenant-a", "S2")
        eng.project_scenario("proj-1", "sc-1", "fc-1")
        eng.project_scenario("proj-2", "sc-2", "fc-1")
        eng.project_scenario("proj-3", "sc-1", "fc-1")
        result = eng.projections_for_scenario("sc-1")
        assert len(result) == 2

    def test_returns_tuple(self, engine: ForecastingRuntimeEngine) -> None:
        assert isinstance(engine.projections_for_scenario("x"), tuple)


# ===================================================================
# SECTION 7: Capacity / Budget / Risk forecasts
# ===================================================================


class TestProjectCapacity:
    def test_returns_capacity_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        assert isinstance(cf, CapacityForecast)

    def test_forecast_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        assert cf.forecast_id == "cf-1"

    def test_tenant_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        assert cf.tenant_id == "tenant-a"

    def test_default_values(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        assert cf.current_utilization == 0.0
        assert cf.projected_utilization == 0.0
        assert cf.headroom == 1.0
        assert cf.confidence == 0.5
        assert cf.horizon == ForecastHorizon.SHORT

    def test_custom_utilization(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity(
            "cf-1", "tenant-a",
            current_utilization=0.7, projected_utilization=0.95,
        )
        assert cf.current_utilization == 0.7
        assert cf.projected_utilization == 0.95

    def test_custom_headroom(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a", headroom=0.5)
        assert cf.headroom == 0.5

    def test_custom_confidence(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a", confidence=0.9)
        assert cf.confidence == 0.9

    def test_custom_horizon(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a", horizon=ForecastHorizon.LONG)
        assert cf.horizon == ForecastHorizon.LONG

    def test_increments_capacity_forecast_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a")
        assert engine.capacity_forecast_count == 1

    def test_duplicate_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate capacity"):
            engine.project_capacity("cf-1", "tenant-a")

    def test_capacity_forecast_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        with pytest.raises(AttributeError):
            cf.projected_utilization = 0.99  # type: ignore[misc]

    def test_scope_ref_id(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a", scope_ref_id="scope-x")
        assert cf.scope_ref_id == "scope-x"


class TestProjectBudget:
    def test_returns_budget_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget("bf-1", "tenant-a")
        assert isinstance(bf, BudgetForecast)

    def test_default_values(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget("bf-1", "tenant-a")
        assert bf.current_spend == 0.0
        assert bf.projected_spend == 0.0
        assert bf.budget_limit == 0.0
        assert bf.burn_rate == 0.0

    def test_custom_spend_and_limit(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget(
            "bf-1", "tenant-a",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=150.0, burn_rate=10.0,
        )
        assert bf.current_spend == 100.0
        assert bf.projected_spend == 200.0
        assert bf.budget_limit == 150.0
        assert bf.burn_rate == 10.0

    def test_increments_budget_forecast_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-a")
        assert engine.budget_forecast_count == 1

    def test_duplicate_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate budget"):
            engine.project_budget("bf-1", "tenant-a")

    def test_budget_forecast_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget("bf-1", "tenant-a")
        with pytest.raises(AttributeError):
            bf.projected_spend = 999.0  # type: ignore[misc]

    def test_custom_confidence_and_horizon(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget(
            "bf-1", "tenant-a",
            confidence=0.8, horizon=ForecastHorizon.STRATEGIC,
        )
        assert bf.confidence == 0.8
        assert bf.horizon == ForecastHorizon.STRATEGIC


class TestProjectRisk:
    def test_returns_risk_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk("rf-1", "tenant-a")
        assert isinstance(rf, RiskForecast)

    def test_default_values(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk("rf-1", "tenant-a")
        assert rf.current_risk == 0.0
        assert rf.projected_risk == 0.0
        assert rf.mitigation_coverage == 0.0

    def test_custom_risk_values(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk(
            "rf-1", "tenant-a",
            current_risk=0.3, projected_risk=0.7, mitigation_coverage=0.5,
        )
        assert rf.current_risk == 0.3
        assert rf.projected_risk == 0.7
        assert rf.mitigation_coverage == 0.5

    def test_increments_risk_forecast_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_risk("rf-1", "tenant-a")
        assert engine.risk_forecast_count == 1

    def test_duplicate_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_risk("rf-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate risk"):
            engine.project_risk("rf-1", "tenant-a")

    def test_risk_forecast_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk("rf-1", "tenant-a")
        with pytest.raises(AttributeError):
            rf.projected_risk = 0.99  # type: ignore[misc]

    def test_scope_ref_id(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk("rf-1", "tenant-a", scope_ref_id="scope-y")
        assert rf.scope_ref_id == "scope-y"

    def test_custom_confidence_and_horizon(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk(
            "rf-1", "tenant-a",
            confidence=0.6, horizon=ForecastHorizon.MEDIUM,
        )
        assert rf.confidence == 0.6
        assert rf.horizon == ForecastHorizon.MEDIUM


# ===================================================================
# SECTION 8: Allocation recommendations
# ===================================================================


class TestRecommendAllocation:
    def test_returns_allocation_recommendation(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert isinstance(rec, AllocationRecommendation)

    def test_recommendation_id_preserved(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.recommendation_id == "rec-1"

    def test_forecast_id_preserved(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.forecast_id == "fc-1"

    def test_tenant_id_preserved(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.tenant_id == "tenant-a"

    def test_disposition_is_recommended(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.disposition == AllocationDisposition.RECOMMENDED

    def test_default_recommended_value(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.recommended_value == 0.0

    def test_custom_recommended_value(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation(
            "rec-1", "fc-1", "tenant-a", recommended_value=50.0,
        )
        assert rec.recommended_value == 50.0

    def test_default_reason(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert rec.reason == ""

    def test_custom_reason(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation(
            "rec-1", "fc-1", "tenant-a", reason="High demand expected",
        )
        assert rec.reason == "High demand expected"

    def test_inherits_forecast_confidence(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        fc = engine_with_forecast.get_forecast("fc-1")
        assert rec.confidence == fc.confidence

    def test_increments_recommendation_count(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert engine_with_forecast.recommendation_count == 1

    def test_duplicate_recommendation_id_raises(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate recommendation_id"):
            engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")

    def test_unknown_forecast_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown forecast_id"):
            engine.recommend_allocation("rec-1", "no-such", "tenant-a")

    def test_scope_ref_id(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation(
            "rec-1", "fc-1", "tenant-a", scope_ref_id="scope-z",
        )
        assert rec.scope_ref_id == "scope-z"

    def test_recommendation_is_frozen(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        with pytest.raises(AttributeError):
            rec.disposition = AllocationDisposition.ACCEPTED  # type: ignore[misc]


class TestVeryLowConfidenceBlocking:
    def test_very_low_confidence_blocks_allocation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-low", "tenant-a", confidence=0.1)
        with pytest.raises(RuntimeCoreInvariantError, match="VERY_LOW"):
            engine.recommend_allocation("rec-1", "fc-low", "tenant-a")

    def test_zero_confidence_blocks_allocation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-low", "tenant-a", confidence=0.0)
        with pytest.raises(RuntimeCoreInvariantError, match="VERY_LOW"):
            engine.recommend_allocation("rec-1", "fc-low", "tenant-a")

    def test_0_29_confidence_blocks(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-low", "tenant-a", confidence=0.29)
        with pytest.raises(RuntimeCoreInvariantError, match="VERY_LOW"):
            engine.recommend_allocation("rec-1", "fc-low", "tenant-a")

    def test_0_3_confidence_allowed(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-ok", "tenant-a", confidence=0.3)
        rec = engine.recommend_allocation("rec-1", "fc-ok", "tenant-a")
        assert rec.disposition == AllocationDisposition.RECOMMENDED

    def test_medium_confidence_allowed(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-ok", "tenant-a", confidence=0.5)
        rec = engine.recommend_allocation("rec-1", "fc-ok", "tenant-a")
        assert rec.disposition == AllocationDisposition.RECOMMENDED

    def test_high_confidence_allowed(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-ok", "tenant-a", confidence=0.9)
        rec = engine.recommend_allocation("rec-1", "fc-ok", "tenant-a")
        assert rec.disposition == AllocationDisposition.RECOMMENDED


class TestAcceptRecommendation:
    def test_recommended_to_accepted(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        rec = engine_with_forecast.accept_recommendation("rec-1")
        assert rec.disposition == AllocationDisposition.ACCEPTED

    def test_preserves_fields(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation(
            "rec-1", "fc-1", "tenant-a", recommended_value=42.0, reason="test",
        )
        rec = engine_with_forecast.accept_recommendation("rec-1")
        assert rec.recommendation_id == "rec-1"
        assert rec.forecast_id == "fc-1"
        assert rec.tenant_id == "tenant-a"
        assert rec.recommended_value == 42.0
        assert rec.reason == "test"

    def test_unknown_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown recommendation_id"):
            engine.accept_recommendation("no-such")

    def test_accepted_cannot_accept_again(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError, match="RECOMMENDED"):
            engine_with_forecast.accept_recommendation("rec-1")

    def test_rejected_cannot_accept(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.accept_recommendation("rec-1")

    def test_deferred_cannot_accept(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.accept_recommendation("rec-1")


class TestRejectRecommendation:
    def test_recommended_to_rejected(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        rec = engine_with_forecast.reject_recommendation("rec-1")
        assert rec.disposition == AllocationDisposition.REJECTED

    def test_unknown_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown recommendation_id"):
            engine.reject_recommendation("no-such")

    def test_accepted_cannot_reject(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")

    def test_rejected_cannot_reject_again(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")

    def test_deferred_cannot_reject(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")


class TestDeferRecommendation:
    def test_recommended_to_deferred(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        rec = engine_with_forecast.defer_recommendation("rec-1")
        assert rec.disposition == AllocationDisposition.DEFERRED

    def test_unknown_raises(self, engine: ForecastingRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown recommendation_id"):
            engine.defer_recommendation("no-such")

    def test_accepted_cannot_defer(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")

    def test_rejected_cannot_defer(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")

    def test_deferred_cannot_defer_again(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")


class TestRecommendationsForForecast:
    def test_empty_for_unknown(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.recommendations_for_forecast("unknown") == ()

    def test_filters_by_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        engine.build_forecast("fc-2", "tenant-a", confidence=0.7)
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine.recommend_allocation("rec-2", "fc-2", "tenant-a")
        engine.recommend_allocation("rec-3", "fc-1", "tenant-a")
        result = engine.recommendations_for_forecast("fc-1")
        assert len(result) == 2

    def test_returns_tuple(self, engine: ForecastingRuntimeEngine) -> None:
        assert isinstance(engine.recommendations_for_forecast("x"), tuple)


# ===================================================================
# SECTION 9: Violation detection
# ===================================================================


class TestDetectForecastViolations:
    def test_no_violations_returns_empty(self, engine: ForecastingRuntimeEngine) -> None:
        result = engine.detect_forecast_violations()
        assert result == ()

    def test_no_signals_violation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        assert len(violations) == 1
        assert violations[0]["operation"] == "no_signals"
        assert violations[0]["forecast_id"] == "fc-1"

    def test_no_signals_violation_is_dict(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        assert isinstance(violations[0], dict)

    def test_no_signals_violation_has_required_keys(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        v = violations[0]
        assert "violation_id" in v
        assert "forecast_id" in v
        assert "tenant_id" in v
        assert "operation" in v
        assert "reason" in v
        assert "detected_at" in v

    def test_no_signals_not_triggered_with_signals(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        no_signal_violations = [v for v in violations if v["operation"] == "no_signals"]
        assert len(no_signal_violations) == 0

    def test_budget_breach_violation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=200.0, budget_limit=100.0,
        )
        violations = engine.detect_forecast_violations()
        budget_violations = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_violations) == 1
        assert budget_violations[0]["forecast_id"] == "bf-1"

    def test_budget_breach_not_triggered_when_under_limit(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=50.0, budget_limit=100.0,
        )
        violations = engine.detect_forecast_violations()
        budget_violations = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_violations) == 0

    def test_budget_breach_not_triggered_when_limit_is_zero(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=200.0, budget_limit=0.0,
        )
        violations = engine.detect_forecast_violations()
        budget_violations = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_violations) == 0

    def test_capacity_pressure_violation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity(
            "cf-1", "tenant-a",
            projected_utilization=0.95,
        )
        violations = engine.detect_forecast_violations()
        cap_violations = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_violations) == 1
        assert cap_violations[0]["forecast_id"] == "cf-1"

    def test_capacity_pressure_not_triggered_at_0_9(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity(
            "cf-1", "tenant-a",
            projected_utilization=0.9,
        )
        violations = engine.detect_forecast_violations()
        cap_violations = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_violations) == 0

    def test_capacity_pressure_not_triggered_at_0_89(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity(
            "cf-1", "tenant-a",
            projected_utilization=0.89,
        )
        violations = engine.detect_forecast_violations()
        cap_violations = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_violations) == 0

    def test_capacity_pressure_triggered_at_0_91(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity(
            "cf-1", "tenant-a",
            projected_utilization=0.91,
        )
        violations = engine.detect_forecast_violations()
        cap_violations = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_violations) == 1

    def test_multiple_violations_detected(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.project_budget("bf-1", "tenant-a", projected_spend=200.0, budget_limit=100.0)
        engine.project_capacity("cf-1", "tenant-a", projected_utilization=0.95)
        violations = engine.detect_forecast_violations()
        assert len(violations) == 3
        ops = {v["operation"] for v in violations}
        assert ops == {"no_signals", "budget_breach", "capacity_pressure"}

    def test_increments_violation_count(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.detect_forecast_violations()
        assert engine.violation_count == 1

    def test_returns_tuple(self, engine: ForecastingRuntimeEngine) -> None:
        assert isinstance(engine.detect_forecast_violations(), tuple)


class TestViolationIdempotency:
    def test_second_scan_returns_empty(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        first = engine.detect_forecast_violations()
        assert len(first) == 1
        second = engine.detect_forecast_violations()
        assert second == ()

    def test_violation_count_stable_after_second_scan(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.detect_forecast_violations()
        count_after_first = engine.violation_count
        engine.detect_forecast_violations()
        assert engine.violation_count == count_after_first

    def test_budget_idempotency(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-a", projected_spend=200.0, budget_limit=100.0)
        first = engine.detect_forecast_violations()
        assert len(first) == 1
        second = engine.detect_forecast_violations()
        assert second == ()

    def test_capacity_idempotency(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a", projected_utilization=0.95)
        first = engine.detect_forecast_violations()
        assert len(first) == 1
        second = engine.detect_forecast_violations()
        assert second == ()

    def test_new_violations_detected_after_new_data(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        first = engine.detect_forecast_violations()
        assert len(first) == 1
        engine.build_forecast("fc-2", "tenant-a")
        second = engine.detect_forecast_violations()
        assert len(second) == 1
        assert second[0]["forecast_id"] == "fc-2"

    def test_third_scan_still_empty_for_old(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.detect_forecast_violations()
        engine.detect_forecast_violations()
        third = engine.detect_forecast_violations()
        assert third == ()


class TestNoSignalViolationForNonActive:
    def test_expired_forecast_not_flagged(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a")
        engine.expire_forecast("fc-1")
        violations = engine.detect_forecast_violations()
        no_signal_viols = [v for v in violations if v["operation"] == "no_signals"]
        assert len(no_signal_viols) == 0

    def test_cancelled_forecast_not_flagged(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a")
        engine.cancel_forecast("fc-1")
        violations = engine.detect_forecast_violations()
        no_signal_viols = [v for v in violations if v["operation"] == "no_signals"]
        assert len(no_signal_viols) == 0


# ===================================================================
# SECTION 10: Snapshots
# ===================================================================


class TestForecastSnapshot:
    def test_returns_forecast_snapshot(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        assert isinstance(snap, ForecastSnapshot)

    def test_snapshot_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"

    def test_captured_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        assert snap.captured_at != ""

    def test_empty_engine_snapshot(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        assert snap.total_signals == 0
        assert snap.total_forecasts == 0
        assert snap.total_scenarios == 0
        assert snap.total_projections == 0
        assert snap.total_recommendations == 0
        assert snap.total_capacity_forecasts == 0
        assert snap.total_budget_forecasts == 0
        assert snap.total_risk_forecasts == 0
        assert snap.total_violations == 0

    def test_snapshot_captures_all_counts(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.project_scenario("proj-1", "sc-1", "fc-1")
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine.project_capacity("cf-1", "tenant-a")
        engine.project_budget("bf-1", "tenant-a")
        engine.project_risk("rf-1", "tenant-a")
        snap = engine.forecast_snapshot("snap-1")
        assert snap.total_signals == 1
        assert snap.total_forecasts == 1
        assert snap.total_scenarios == 1
        assert snap.total_projections == 1
        assert snap.total_recommendations == 1
        assert snap.total_capacity_forecasts == 1
        assert snap.total_budget_forecasts == 1
        assert snap.total_risk_forecasts == 1

    def test_snapshot_captures_violations(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.detect_forecast_violations()
        snap = engine.forecast_snapshot("snap-1")
        assert snap.total_violations == 1

    def test_duplicate_snapshot_id_raises(self, engine: ForecastingRuntimeEngine) -> None:
        engine.forecast_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.forecast_snapshot("snap-1")

    def test_snapshot_is_frozen(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_signals = 999  # type: ignore[misc]

    def test_multiple_snapshots_allowed(self, engine: ForecastingRuntimeEngine) -> None:
        snap1 = engine.forecast_snapshot("snap-1")
        engine.register_signal("sig-1", "tenant-a")
        snap2 = engine.forecast_snapshot("snap-2")
        assert snap1.total_signals == 0
        assert snap2.total_signals == 1


# ===================================================================
# SECTION 11: State hash
# ===================================================================


class TestStateHash:
    def test_returns_string(self, engine: ForecastingRuntimeEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_is_16_char_hex(self, engine: ForecastingRuntimeEngine) -> None:
        h = engine.state_hash()
        assert len(h) == 64
        int(h, 16)  # raises ValueError if not valid hex

    def test_deterministic(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_signal(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.register_signal("sig-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.build_forecast("fc-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_scenario(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.build_scenario("sc-1", "tenant-a", "S")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_capacity(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.project_capacity("cf-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_budget(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.project_budget("bf-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_risk(self, engine: ForecastingRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.project_risk("rf-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        h1 = engine.state_hash()
        engine.detect_forecast_violations()
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_recommendation(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        h1 = engine.state_hash()
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_projection(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        h1 = engine_with_scenario.state_hash()
        engine_with_scenario.project_scenario("proj-1", "sc-1", "fc-1")
        h2 = engine_with_scenario.state_hash()
        assert h1 != h2

    def test_is_method_not_property(self, engine: ForecastingRuntimeEngine) -> None:
        assert callable(engine.state_hash)
        assert not isinstance(
            type(engine).__dict__.get("state_hash"), property,
        )


# ===================================================================
# SECTION 12: Events emitted
# ===================================================================


class TestEventsEmitted:
    def test_signal_registration_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.register_signal("sig-1", "tenant-a")
        assert spine.event_count > initial

    def test_build_forecast_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.build_forecast("fc-1", "tenant-a")
        assert spine.event_count > initial

    def test_supersede_forecast_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a")
        initial = spine.event_count
        eng.supersede_forecast("fc-1")
        assert spine.event_count > initial

    def test_expire_forecast_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a")
        initial = spine.event_count
        eng.expire_forecast("fc-1")
        assert spine.event_count > initial

    def test_cancel_forecast_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a")
        initial = spine.event_count
        eng.cancel_forecast("fc-1")
        assert spine.event_count > initial

    def test_build_scenario_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.build_scenario("sc-1", "tenant-a", "S")
        assert spine.event_count > initial

    def test_evaluate_scenario_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        initial = spine.event_count
        engine.evaluate_scenario("sc-1")
        assert spine.event_count > initial

    def test_archive_scenario_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        initial = spine.event_count
        engine.archive_scenario("sc-1")
        assert spine.event_count > initial

    def test_project_scenario_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a")
        eng.build_scenario("sc-1", "tenant-a", "S")
        initial = spine.event_count
        eng.project_scenario("proj-1", "sc-1", "fc-1")
        assert spine.event_count > initial

    def test_project_capacity_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.project_capacity("cf-1", "tenant-a")
        assert spine.event_count > initial

    def test_project_budget_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.project_budget("bf-1", "tenant-a")
        assert spine.event_count > initial

    def test_project_risk_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.project_risk("rf-1", "tenant-a")
        assert spine.event_count > initial

    def test_recommend_allocation_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a", confidence=0.7)
        initial = spine.event_count
        eng.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert spine.event_count > initial

    def test_accept_recommendation_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a", confidence=0.7)
        eng.recommend_allocation("rec-1", "fc-1", "tenant-a")
        initial = spine.event_count
        eng.accept_recommendation("rec-1")
        assert spine.event_count > initial

    def test_reject_recommendation_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a", confidence=0.7)
        eng.recommend_allocation("rec-1", "fc-1", "tenant-a")
        initial = spine.event_count
        eng.reject_recommendation("rec-1")
        assert spine.event_count > initial

    def test_defer_recommendation_emits_event(self, spine: EventSpineEngine) -> None:
        eng = ForecastingRuntimeEngine(spine)
        eng.register_signal("sig-1", "tenant-a")
        eng.build_forecast("fc-1", "tenant-a", confidence=0.7)
        eng.recommend_allocation("rec-1", "fc-1", "tenant-a")
        initial = spine.event_count
        eng.defer_recommendation("rec-1")
        assert spine.event_count > initial

    def test_violation_detection_emits_event_when_found(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        initial = spine.event_count
        engine.detect_forecast_violations()
        assert spine.event_count > initial

    def test_snapshot_emits_event(self, spine: EventSpineEngine, engine: ForecastingRuntimeEngine) -> None:
        initial = spine.event_count
        engine.forecast_snapshot("snap-1")
        assert spine.event_count > initial


# ===================================================================
# SECTION 13: Golden scenarios
# ===================================================================


class TestGoldenScenario1RequestVolumeForecasting:
    """Register signals, build forecast, recommend allocation, accept."""

    def test_full_flow(self, engine: ForecastingRuntimeEngine) -> None:
        # Register demand signals
        s1 = engine.register_signal("sig-1", "tenant-a", kind=DemandSignalKind.REQUEST_VOLUME, value=100.0)
        s2 = engine.register_signal("sig-2", "tenant-a", kind=DemandSignalKind.REQUEST_VOLUME, value=120.0)
        s3 = engine.register_signal("sig-3", "tenant-a", kind=DemandSignalKind.REQUEST_VOLUME, value=80.0)
        assert engine.signal_count == 3

        # Build forecast
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.8, projected_value=300.0)
        assert fc.status == ForecastStatus.ACTIVE
        assert fc.signal_count == 3
        assert fc.confidence_band == ForecastConfidenceBand.HIGH
        assert fc.projected_value == 300.0

        # Recommend allocation
        rec = engine.recommend_allocation(
            "rec-1", "fc-1", "tenant-a",
            recommended_value=350.0, reason="High demand trend",
        )
        assert rec.disposition == AllocationDisposition.RECOMMENDED
        assert rec.confidence == 0.8

        # Accept
        accepted = engine.accept_recommendation("rec-1")
        assert accepted.disposition == AllocationDisposition.ACCEPTED
        assert accepted.recommended_value == 350.0

    def test_counts_consistent(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", value=100.0)
        engine.register_signal("sig-2", "tenant-a", value=120.0)
        engine.build_forecast("fc-1", "tenant-a", confidence=0.8)
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine.accept_recommendation("rec-1")
        assert engine.signal_count == 2
        assert engine.forecast_count == 1
        assert engine.recommendation_count == 1


class TestGoldenScenario2CapacityPressureDetection:
    """Project capacity at 0.95, detect violation."""

    def test_full_flow(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity(
            "cf-1", "tenant-a",
            current_utilization=0.7, projected_utilization=0.95,
            headroom=0.05, confidence=0.9,
        )
        assert cf.projected_utilization == 0.95

        violations = engine.detect_forecast_violations()
        assert len(violations) == 1
        assert violations[0]["operation"] == "capacity_pressure"
        assert violations[0]["forecast_id"] == "cf-1"
        assert engine.violation_count == 1

    def test_threshold_boundary(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-at-90", "tenant-a", projected_utilization=0.9)
        violations = engine.detect_forecast_violations()
        cap_viols = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_viols) == 0

    def test_above_threshold(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-above", "tenant-a", projected_utilization=0.91)
        violations = engine.detect_forecast_violations()
        cap_viols = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_viols) == 1


class TestGoldenScenario3BudgetBreachDetection:
    """Project budget with projected > limit, detect violation."""

    def test_full_flow(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget(
            "bf-1", "tenant-a",
            current_spend=80.0, projected_spend=200.0,
            budget_limit=150.0, burn_rate=10.0,
        )
        assert bf.projected_spend == 200.0
        assert bf.budget_limit == 150.0

        violations = engine.detect_forecast_violations()
        budget_viols = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_viols) == 1
        assert budget_viols[0]["forecast_id"] == "bf-1"

    def test_equal_spend_and_limit_no_breach(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=100.0, budget_limit=100.0,
        )
        violations = engine.detect_forecast_violations()
        budget_viols = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_viols) == 0

    def test_under_limit_no_breach(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=50.0, budget_limit=100.0,
        )
        violations = engine.detect_forecast_violations()
        budget_viols = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_viols) == 0


class TestGoldenScenario4ScenarioPlanning:
    """Build scenario, project, evaluate, archive."""

    def test_full_flow(self, engine: ForecastingRuntimeEngine) -> None:
        # Setup
        engine.register_signal("sig-1", "tenant-a", value=50.0)
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.7)

        # Build scenario
        sc = engine.build_scenario("sc-1", "tenant-a", "Growth Plan", description="Q4 growth")
        assert sc.status == ScenarioStatus.ACTIVE

        # Project
        proj = engine.project_scenario(
            "proj-1", "sc-1", "fc-1",
            projected_value=75.0, probability=0.7, impact_score=0.8,
        )
        assert proj.scenario_id == "sc-1"
        assert proj.forecast_id == "fc-1"

        # Evaluate
        evaluated = engine.evaluate_scenario("sc-1")
        assert evaluated.status == ScenarioStatus.EVALUATED

        # Archive
        archived = engine.archive_scenario("sc-1")
        assert archived.status == ScenarioStatus.ARCHIVED

        # Verify archived cannot be evaluated or archived again
        with pytest.raises(RuntimeCoreInvariantError):
            engine.evaluate_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.archive_scenario("sc-1")

    def test_projections_persist(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a")
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.project_scenario("proj-1", "sc-1", "fc-1")
        engine.project_scenario("proj-2", "sc-1", "fc-1")
        engine.evaluate_scenario("sc-1")
        engine.archive_scenario("sc-1")
        projs = engine.projections_for_scenario("sc-1")
        assert len(projs) == 2


class TestGoldenScenario5LowConfidenceBlocking:
    """Build forecast with confidence 0.1, try recommend, blocked."""

    def test_full_flow(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a", value=10.0)
        fc = engine.build_forecast("fc-low", "tenant-a", confidence=0.1)
        assert fc.confidence_band == ForecastConfidenceBand.VERY_LOW

        with pytest.raises(RuntimeCoreInvariantError, match="VERY_LOW"):
            engine.recommend_allocation("rec-1", "fc-low", "tenant-a")

        # Verify no recommendation was created
        assert engine.recommendation_count == 0

    def test_low_confidence_boundary(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-boundary", "tenant-a", confidence=0.3)
        rec = engine.recommend_allocation("rec-1", "fc-boundary", "tenant-a")
        assert rec.disposition == AllocationDisposition.RECOMMENDED


class TestGoldenScenario6FullLifecycle:
    """Signals, forecast, scenario, projection, capacity/budget/risk, recs, violations, snapshot."""

    def test_full_lifecycle(self, engine: ForecastingRuntimeEngine) -> None:
        # Step 1: Register signals
        engine.register_signal("sig-1", "tenant-a", kind=DemandSignalKind.REQUEST_VOLUME, value=100.0)
        engine.register_signal("sig-2", "tenant-a", kind=DemandSignalKind.CAPACITY_USAGE, value=80.0)
        engine.register_signal("sig-3", "tenant-a", kind=DemandSignalKind.BUDGET_BURN, value=50.0)
        assert engine.signal_count == 3

        # Step 2: Build forecast
        fc = engine.build_forecast("fc-1", "tenant-a", confidence=0.85, projected_value=230.0)
        assert fc.signal_count == 3
        assert fc.confidence_band == ForecastConfidenceBand.HIGH

        # Step 3: Build scenario
        sc = engine.build_scenario("sc-1", "tenant-a", "Growth Scenario", horizon=ForecastHorizon.LONG)
        assert sc.status == ScenarioStatus.ACTIVE

        # Step 4: Create projection
        proj = engine.project_scenario(
            "proj-1", "sc-1", "fc-1",
            projected_value=250.0, probability=0.75, impact_score=0.9,
        )
        assert proj.projected_value == 250.0

        # Step 5: Project capacity (pressure)
        engine.project_capacity(
            "cf-1", "tenant-a",
            projected_utilization=0.95, headroom=0.05, confidence=0.9,
        )

        # Step 6: Project budget (breach)
        engine.project_budget(
            "bf-1", "tenant-a",
            projected_spend=200.0, budget_limit=150.0, burn_rate=15.0,
        )

        # Step 7: Project risk
        engine.project_risk(
            "rf-1", "tenant-a",
            current_risk=0.4, projected_risk=0.6, mitigation_coverage=0.3,
        )

        # Step 8: Recommend allocation
        rec = engine.recommend_allocation(
            "rec-1", "fc-1", "tenant-a",
            recommended_value=300.0, reason="Scaling needed",
        )
        assert rec.confidence == 0.85

        # Step 9: Accept recommendation
        accepted = engine.accept_recommendation("rec-1")
        assert accepted.disposition == AllocationDisposition.ACCEPTED

        # Step 10: Detect violations
        violations = engine.detect_forecast_violations()
        assert len(violations) >= 2  # capacity_pressure + budget_breach
        ops = {v["operation"] for v in violations}
        assert "capacity_pressure" in ops
        assert "budget_breach" in ops

        # Step 11: Snapshot
        snap = engine.forecast_snapshot("snap-final")
        assert snap.total_signals == 3
        assert snap.total_forecasts == 1
        assert snap.total_scenarios == 1
        assert snap.total_projections == 1
        assert snap.total_recommendations == 1
        assert snap.total_capacity_forecasts == 1
        assert snap.total_budget_forecasts == 1
        assert snap.total_risk_forecasts == 1
        assert snap.total_violations >= 2

        # Step 12: Evaluate and archive scenario
        engine.evaluate_scenario("sc-1")
        engine.archive_scenario("sc-1")
        assert engine.get_scenario("sc-1").status == ScenarioStatus.ARCHIVED

    def test_state_hash_evolves(self, engine: ForecastingRuntimeEngine) -> None:
        hashes = [engine.state_hash()]

        engine.register_signal("sig-1", "tenant-a")
        hashes.append(engine.state_hash())

        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        hashes.append(engine.state_hash())

        engine.build_scenario("sc-1", "tenant-a", "S")
        hashes.append(engine.state_hash())

        engine.project_scenario("proj-1", "sc-1", "fc-1")
        hashes.append(engine.state_hash())

        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        hashes.append(engine.state_hash())

        # All hashes should be unique
        assert len(set(hashes)) == len(hashes)


# ===================================================================
# SECTION 14: Edge cases and cross-cutting concerns
# ===================================================================


class TestMultipleTenants:
    def test_signals_isolated_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-b")
        assert len(engine.signals_for_tenant("tenant-a")) == 1
        assert len(engine.signals_for_tenant("tenant-b")) == 1

    def test_forecasts_isolated_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        engine.build_forecast("fc-2", "tenant-b")
        assert len(engine.forecasts_for_tenant("tenant-a")) == 1
        assert len(engine.forecasts_for_tenant("tenant-b")) == 1

    def test_scenarios_isolated_by_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S1")
        engine.build_scenario("sc-2", "tenant-b", "S2")
        assert len(engine.scenarios_for_tenant("tenant-a")) == 1
        assert len(engine.scenarios_for_tenant("tenant-b")) == 1

    def test_signal_count_per_tenant_in_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-a")
        engine.register_signal("sig-3", "tenant-b")
        fc_a = engine.build_forecast("fc-a", "tenant-a")
        fc_b = engine.build_forecast("fc-b", "tenant-b")
        assert fc_a.signal_count == 2
        assert fc_b.signal_count == 1


class TestMultipleRecommendationsPerForecast:
    def test_multiple_recs(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a", recommended_value=10.0)
        engine.recommend_allocation("rec-2", "fc-1", "tenant-a", recommended_value=20.0)
        engine.recommend_allocation("rec-3", "fc-1", "tenant-a", recommended_value=30.0)
        recs = engine.recommendations_for_forecast("fc-1")
        assert len(recs) == 3
        assert engine.recommendation_count == 3

    def test_different_dispositions(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine.recommend_allocation("rec-2", "fc-1", "tenant-a")
        engine.recommend_allocation("rec-3", "fc-1", "tenant-a")
        engine.accept_recommendation("rec-1")
        engine.reject_recommendation("rec-2")
        engine.defer_recommendation("rec-3")
        recs = engine.recommendations_for_forecast("fc-1")
        dispositions = {r.disposition for r in recs}
        assert dispositions == {
            AllocationDisposition.ACCEPTED,
            AllocationDisposition.REJECTED,
            AllocationDisposition.DEFERRED,
        }


class TestMultipleProjectionsPerScenario:
    def test_multiple_projections(self, engine_with_scenario: ForecastingRuntimeEngine) -> None:
        eng = engine_with_scenario
        eng.build_forecast("fc-2", "tenant-a", confidence=0.6)
        eng.project_scenario("proj-1", "sc-1", "fc-1", projected_value=10.0)
        eng.project_scenario("proj-2", "sc-1", "fc-2", projected_value=20.0)
        projs = eng.projections_for_scenario("sc-1")
        assert len(projs) == 2
        values = {p.projected_value for p in projs}
        assert values == {10.0, 20.0}


class TestMultipleViolationTypes:
    def test_all_three_types_simultaneously(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-no-signal", "tenant-a")
        engine.project_budget("bf-breach", "tenant-a", projected_spend=200.0, budget_limit=100.0)
        engine.project_capacity("cf-pressure", "tenant-a", projected_utilization=0.95)
        violations = engine.detect_forecast_violations()
        ops = {v["operation"] for v in violations}
        assert len(ops) == 3
        assert "no_signals" in ops
        assert "budget_breach" in ops
        assert "capacity_pressure" in ops


class TestForecastSupersedeThenRebuild:
    def test_supersede_then_build_new(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.5)
        engine.supersede_forecast("fc-1")
        fc2 = engine.build_forecast("fc-2", "tenant-a", confidence=0.9)
        assert fc2.status == ForecastStatus.ACTIVE
        assert engine.forecast_count == 2
        old = engine.get_forecast("fc-1")
        assert old.status == ForecastStatus.SUPERSEDED


class TestPropertyCountsAccuracy:
    def test_all_counts_after_operations(self, engine: ForecastingRuntimeEngine) -> None:
        engine.register_signal("sig-1", "tenant-a")
        engine.register_signal("sig-2", "tenant-a")
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        engine.build_forecast("fc-2", "tenant-a", confidence=0.6)
        engine.build_scenario("sc-1", "tenant-a", "S1")
        engine.build_scenario("sc-2", "tenant-a", "S2")
        engine.build_scenario("sc-3", "tenant-a", "S3")
        engine.project_scenario("proj-1", "sc-1", "fc-1")
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine.recommend_allocation("rec-2", "fc-2", "tenant-a")
        engine.project_capacity("cf-1", "tenant-a")
        engine.project_budget("bf-1", "tenant-a")
        engine.project_risk("rf-1", "tenant-a")
        engine.project_risk("rf-2", "tenant-a")
        assert engine.signal_count == 2
        assert engine.forecast_count == 2
        assert engine.scenario_count == 3
        assert engine.projection_count == 1
        assert engine.recommendation_count == 2
        assert engine.capacity_forecast_count == 1
        assert engine.budget_forecast_count == 1
        assert engine.risk_forecast_count == 2


class TestSignalKindVariety:
    def test_all_demand_signal_kinds(self, engine: ForecastingRuntimeEngine) -> None:
        for i, kind in enumerate(DemandSignalKind):
            s = engine.register_signal(f"sig-{i}", "tenant-a", kind=kind, value=float(i))
            assert s.kind == kind
            assert s.value == float(i)
        assert engine.signal_count == len(DemandSignalKind)


class TestHorizonVariety:
    def test_all_forecast_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            fc = engine.build_forecast(f"fc-{i}", "tenant-a", horizon=h)
            assert fc.horizon == h

    def test_all_scenario_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            sc = engine.build_scenario(f"sc-{i}", "tenant-a", f"S-{i}", horizon=h)
            assert sc.horizon == h

    def test_all_capacity_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            cf = engine.project_capacity(f"cf-{i}", "tenant-a", horizon=h)
            assert cf.horizon == h

    def test_all_budget_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            bf = engine.project_budget(f"bf-{i}", "tenant-a", horizon=h)
            assert bf.horizon == h

    def test_all_risk_horizons(self, engine: ForecastingRuntimeEngine) -> None:
        for i, h in enumerate(ForecastHorizon):
            rf = engine.project_risk(f"rf-{i}", "tenant-a", horizon=h)
            assert rf.horizon == h


class TestScenarioLifecycleTransitions:
    def test_active_to_evaluated(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        sc = engine.evaluate_scenario("sc-1")
        assert sc.status == ScenarioStatus.EVALUATED

    def test_active_to_archived(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        sc = engine.archive_scenario("sc-1")
        assert sc.status == ScenarioStatus.ARCHIVED

    def test_evaluated_to_archived(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.evaluate_scenario("sc-1")
        sc = engine.archive_scenario("sc-1")
        assert sc.status == ScenarioStatus.ARCHIVED

    def test_evaluated_to_evaluated_again(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.evaluate_scenario("sc-1")
        sc = engine.evaluate_scenario("sc-1")
        assert sc.status == ScenarioStatus.EVALUATED

    def test_archived_to_evaluated_blocked(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.archive_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.evaluate_scenario("sc-1")

    def test_archived_to_archived_blocked(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_scenario("sc-1", "tenant-a", "S")
        engine.archive_scenario("sc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.archive_scenario("sc-1")


class TestRecommendationStateTransitions:
    def test_recommended_to_accepted(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        r = engine_with_forecast.accept_recommendation("rec-1")
        assert r.disposition == AllocationDisposition.ACCEPTED

    def test_recommended_to_rejected(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        r = engine_with_forecast.reject_recommendation("rec-1")
        assert r.disposition == AllocationDisposition.REJECTED

    def test_recommended_to_deferred(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        r = engine_with_forecast.defer_recommendation("rec-1")
        assert r.disposition == AllocationDisposition.DEFERRED

    def test_accepted_is_terminal_for_accept(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.accept_recommendation("rec-1")

    def test_accepted_is_terminal_for_reject(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")

    def test_accepted_is_terminal_for_defer(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.accept_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")

    def test_rejected_is_terminal_for_accept(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.accept_recommendation("rec-1")

    def test_rejected_is_terminal_for_reject(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")

    def test_rejected_is_terminal_for_defer(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.reject_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")

    def test_deferred_is_terminal_for_accept(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.accept_recommendation("rec-1")

    def test_deferred_is_terminal_for_reject(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.reject_recommendation("rec-1")

    def test_deferred_is_terminal_for_defer(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        engine_with_forecast.defer_recommendation("rec-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.defer_recommendation("rec-1")


class TestForecastStatusTransitions:
    def test_active_to_superseded(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        r = engine_with_forecast.supersede_forecast("fc-1")
        assert r.status == ForecastStatus.SUPERSEDED

    def test_active_to_expired(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        r = engine_with_forecast.expire_forecast("fc-1")
        assert r.status == ForecastStatus.EXPIRED

    def test_active_to_cancelled(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        r = engine_with_forecast.cancel_forecast("fc-1")
        assert r.status == ForecastStatus.CANCELLED

    def test_superseded_to_expired(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.supersede_forecast("fc-1")
        r = engine_with_forecast.expire_forecast("fc-1")
        assert r.status == ForecastStatus.EXPIRED

    def test_superseded_to_cancelled(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.supersede_forecast("fc-1")
        r = engine_with_forecast.cancel_forecast("fc-1")
        assert r.status == ForecastStatus.CANCELLED

    def test_expired_to_expired_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.expire_forecast("fc-1")

    def test_expired_to_cancelled_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.cancel_forecast("fc-1")

    def test_expired_to_superseded_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.expire_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")

    def test_cancelled_to_expired_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.expire_forecast("fc-1")

    def test_cancelled_to_cancelled_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.cancel_forecast("fc-1")

    def test_cancelled_to_superseded_blocked(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        engine_with_forecast.cancel_forecast("fc-1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_forecast.supersede_forecast("fc-1")


class TestSnapshotMultipleCaptures:
    def test_progressive_snapshots(self, engine: ForecastingRuntimeEngine) -> None:
        snap1 = engine.forecast_snapshot("snap-1")
        assert snap1.total_signals == 0

        engine.register_signal("sig-1", "tenant-a")
        snap2 = engine.forecast_snapshot("snap-2")
        assert snap2.total_signals == 1

        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        snap3 = engine.forecast_snapshot("snap-3")
        assert snap3.total_forecasts == 1

        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        snap4 = engine.forecast_snapshot("snap-4")
        assert snap4.total_recommendations == 1


class TestBudgetForecastScopeRef:
    def test_scope_ref_id_preserved(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget("bf-1", "tenant-a", scope_ref_id="dept-finance")
        assert bf.scope_ref_id == "dept-finance"


class TestCapacityForecastProjectedAt:
    def test_projected_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        cf = engine.project_capacity("cf-1", "tenant-a")
        assert cf.projected_at != ""


class TestBudgetForecastProjectedAt:
    def test_projected_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        bf = engine.project_budget("bf-1", "tenant-a")
        assert bf.projected_at != ""


class TestRiskForecastProjectedAt:
    def test_projected_at_populated(self, engine: ForecastingRuntimeEngine) -> None:
        rf = engine.project_risk("rf-1", "tenant-a")
        assert rf.projected_at != ""


class TestEmptyTenantQueries:
    def test_signals_for_nonexistent_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.signals_for_tenant("ghost") == ()

    def test_forecasts_for_nonexistent_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.forecasts_for_tenant("ghost") == ()

    def test_scenarios_for_nonexistent_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.scenarios_for_tenant("ghost") == ()

    def test_projections_for_nonexistent_scenario(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.projections_for_scenario("ghost") == ()

    def test_recommendations_for_nonexistent_forecast(self, engine: ForecastingRuntimeEngine) -> None:
        assert engine.recommendations_for_forecast("ghost") == ()


class TestViolationDetectionEdgeCases:
    def test_no_active_forecast_no_violation(self, engine: ForecastingRuntimeEngine) -> None:
        violations = engine.detect_forecast_violations()
        assert violations == ()

    def test_budget_at_exact_limit_no_breach(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-a", projected_spend=100.0, budget_limit=100.0)
        violations = engine.detect_forecast_violations()
        budget_viols = [v for v in violations if v["operation"] == "budget_breach"]
        assert len(budget_viols) == 0

    def test_capacity_at_exactly_0_9_no_pressure(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a", projected_utilization=0.9)
        violations = engine.detect_forecast_violations()
        cap_viols = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_viols) == 0

    def test_capacity_at_1_0_triggers_pressure(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a", projected_utilization=1.0)
        violations = engine.detect_forecast_violations()
        cap_viols = [v for v in violations if v["operation"] == "capacity_pressure"]
        assert len(cap_viols) == 1


# ===================================================================
# SECTION 15: Additional coverage for 350+ target
# ===================================================================


class TestStateHashDeterminism:
    def test_same_state_same_hash_across_engines(self, spine: EventSpineEngine) -> None:
        eng1 = ForecastingRuntimeEngine(spine)
        eng2 = ForecastingRuntimeEngine(EventSpineEngine())
        assert eng1.state_hash() == eng2.state_hash()

    def test_hash_differs_after_each_entity_type(self, engine: ForecastingRuntimeEngine) -> None:
        hashes = set()
        hashes.add(engine.state_hash())
        engine.register_signal("sig-1", "tenant-a")
        hashes.add(engine.state_hash())
        engine.build_forecast("fc-1", "tenant-a", confidence=0.7)
        hashes.add(engine.state_hash())
        engine.build_scenario("sc-1", "tenant-a", "S")
        hashes.add(engine.state_hash())
        engine.project_scenario("proj-1", "sc-1", "fc-1")
        hashes.add(engine.state_hash())
        engine.recommend_allocation("rec-1", "fc-1", "tenant-a")
        hashes.add(engine.state_hash())
        engine.project_capacity("cf-1", "tenant-a")
        hashes.add(engine.state_hash())
        engine.project_budget("bf-1", "tenant-a")
        hashes.add(engine.state_hash())
        engine.project_risk("rf-1", "tenant-a")
        hashes.add(engine.state_hash())
        assert len(hashes) == 9


class TestForecastCreatedAtTimestamp:
    def test_created_at_is_iso_format(self, engine: ForecastingRuntimeEngine) -> None:
        fc = engine.build_forecast("fc-1", "tenant-a")
        assert "T" in fc.created_at

    def test_signal_recorded_at_is_iso_format(self, engine: ForecastingRuntimeEngine) -> None:
        s = engine.register_signal("sig-1", "tenant-a")
        assert "T" in s.recorded_at


class TestScenarioCreatedAtTimestamp:
    def test_created_at_is_iso_format(self, engine: ForecastingRuntimeEngine) -> None:
        sc = engine.build_scenario("sc-1", "tenant-a", "S")
        assert "T" in sc.created_at


class TestRecommendationCreatedAtTimestamp:
    def test_created_at_is_iso_format(self, engine_with_forecast: ForecastingRuntimeEngine) -> None:
        rec = engine_with_forecast.recommend_allocation("rec-1", "fc-1", "tenant-a")
        assert "T" in rec.created_at


class TestSnapshotCapturedAtTimestamp:
    def test_captured_at_is_iso_format(self, engine: ForecastingRuntimeEngine) -> None:
        snap = engine.forecast_snapshot("snap-1")
        assert "T" in snap.captured_at


class TestViolationDetectedAtTimestamp:
    def test_detected_at_present(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        assert "T" in violations[0]["detected_at"]


class TestViolationTenantId:
    def test_no_signals_includes_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-1", "tenant-a")
        violations = engine.detect_forecast_violations()
        assert violations[0]["tenant_id"] == "tenant-a"

    def test_budget_breach_includes_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-b", projected_spend=200.0, budget_limit=100.0)
        violations = engine.detect_forecast_violations()
        budget_v = [v for v in violations if v["operation"] == "budget_breach"][0]
        assert budget_v["tenant_id"] == "tenant-b"

    def test_capacity_pressure_includes_tenant(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-c", projected_utilization=0.95)
        violations = engine.detect_forecast_violations()
        cap_v = [v for v in violations if v["operation"] == "capacity_pressure"][0]
        assert cap_v["tenant_id"] == "tenant-c"


class TestViolationReasonText:
    def test_no_signals_reason_includes_forecast_id(self, engine: ForecastingRuntimeEngine) -> None:
        engine.build_forecast("fc-xyz", "tenant-a")
        violations = engine.detect_forecast_violations()
        assert "fc-xyz" in violations[0]["reason"]

    def test_budget_reason_includes_amounts(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_budget("bf-1", "tenant-a", projected_spend=200.0, budget_limit=100.0)
        violations = engine.detect_forecast_violations()
        budget_v = [v for v in violations if v["operation"] == "budget_breach"][0]
        assert "200.0" in budget_v["reason"]
        assert "100.0" in budget_v["reason"]

    def test_capacity_reason_includes_utilization(self, engine: ForecastingRuntimeEngine) -> None:
        engine.project_capacity("cf-1", "tenant-a", projected_utilization=0.95)
        violations = engine.detect_forecast_violations()
        cap_v = [v for v in violations if v["operation"] == "capacity_pressure"][0]
        assert "0.95" in cap_v["reason"]
