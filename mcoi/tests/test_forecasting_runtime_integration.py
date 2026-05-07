"""Tests for ForecastingRuntimeIntegration bridge.

Covers constructor validation, all six forecast-from-* methods,
memory mesh attachment, graph attachment, event emission, and
duplicate-ID rejection.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.forecasting_runtime_integration import ForecastingRuntimeIntegration
from mcoi_runtime.core.forecasting_runtime import ForecastingRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.forecasting_runtime import (
    DemandSignalKind,
    ForecastConfidenceBand,
    ForecastHorizon,
    ForecastStatus,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def forecasting_engine(event_spine: EventSpineEngine) -> ForecastingRuntimeEngine:
    return ForecastingRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    forecasting_engine: ForecastingRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> ForecastingRuntimeIntegration:
    return ForecastingRuntimeIntegration(forecasting_engine, event_spine, memory_engine)


# ===================================================================
# Constructor validation (3 guards)
# ===================================================================


class TestConstructorValidation:
    """Constructor rejects wrong types for each of the three arguments."""

    def test_invalid_forecasting_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="forecasting_engine"):
            ForecastingRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_invalid_event_spine(
        self, forecasting_engine: ForecastingRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ForecastingRuntimeIntegration(forecasting_engine, "not-a-spine", memory_engine)

    def test_invalid_memory_engine(
        self, forecasting_engine: ForecastingRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ForecastingRuntimeIntegration(forecasting_engine, event_spine, "not-a-mesh")


# ===================================================================
# forecast_from_portfolio
# ===================================================================


class TestForecastFromPortfolio:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p1", "fc-p1", "tenant-1", "portfolio-A"
        )
        assert isinstance(result, dict)

    def test_correct_keys(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p2", "fc-p2", "tenant-1", "portfolio-B"
        )
        expected_keys = {
            "forecast_id", "tenant_id", "portfolio_ref",
            "status", "confidence_band", "signal_count", "source_type",
        }
        assert set(result.keys()) == expected_keys

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p3", "fc-p3", "tenant-1", "portfolio-C"
        )
        assert result["source_type"] == "portfolio"

    def test_forecast_id_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p4", "fc-p4", "tenant-1", "portfolio-D"
        )
        assert result["forecast_id"] == "fc-p4"

    def test_tenant_id_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p5", "fc-p5", "tenant-X", "portfolio-E"
        )
        assert result["tenant_id"] == "tenant-X"

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p6", "fc-p6", "tenant-1", "portfolio-F"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_medium_default(
        self, integration: ForecastingRuntimeIntegration
    ) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p7", "fc-p7", "tenant-1", "portfolio-G", confidence=0.5
        )
        assert result["confidence_band"] == ForecastConfidenceBand.MEDIUM.value

    def test_confidence_band_high(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p8", "fc-p8", "tenant-1", "portfolio-H", confidence=0.9
        )
        assert result["confidence_band"] == ForecastConfidenceBand.HIGH.value

    def test_signal_registered_in_engine(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_portfolio(
            "sig-p9", "fc-p9", "tenant-1", "portfolio-I"
        )
        sig = forecasting_engine.get_signal("sig-p9")
        assert sig.kind == DemandSignalKind.CAPACITY_USAGE

    def test_forecast_built_in_engine(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_portfolio(
            "sig-p10", "fc-p10", "tenant-1", "portfolio-J"
        )
        fc = forecasting_engine.get_forecast("fc-p10")
        assert fc.status == ForecastStatus.ACTIVE

    def test_status_is_active(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_portfolio(
            "sig-p11", "fc-p11", "tenant-1", "portfolio-K"
        )
        assert result["status"] == ForecastStatus.ACTIVE.value


# ===================================================================
# forecast_from_service_requests
# ===================================================================


class TestForecastFromServiceRequests:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_service_requests(
            "sig-sr1", "fc-sr1", "tenant-1", "svc-A"
        )
        assert isinstance(result, dict)

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_service_requests(
            "sig-sr2", "fc-sr2", "tenant-1", "svc-B"
        )
        assert result["source_type"] == "service_requests"

    def test_signal_kind_request_volume(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_service_requests(
            "sig-sr3", "fc-sr3", "tenant-1", "svc-C"
        )
        sig = forecasting_engine.get_signal("sig-sr3")
        assert sig.kind == DemandSignalKind.REQUEST_VOLUME

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_service_requests(
            "sig-sr4", "fc-sr4", "tenant-1", "svc-D"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_service_requests(
            "sig-sr5", "fc-sr5", "tenant-1", "svc-E", confidence=0.85
        )
        assert result["confidence_band"] == ForecastConfidenceBand.HIGH.value

    def test_has_service_ref_key(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_service_requests(
            "sig-sr6", "fc-sr6", "tenant-1", "svc-F"
        )
        assert result["service_ref"] == "svc-F"


# ===================================================================
# forecast_from_availability
# ===================================================================


class TestForecastFromAvailability:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_availability(
            "sig-av1", "fc-av1", "tenant-1", "avail-A"
        )
        assert isinstance(result, dict)

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_availability(
            "sig-av2", "fc-av2", "tenant-1", "avail-B"
        )
        assert result["source_type"] == "availability"

    def test_signal_kind_capacity_usage(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_availability(
            "sig-av3", "fc-av3", "tenant-1", "avail-C"
        )
        sig = forecasting_engine.get_signal("sig-av3")
        assert sig.kind == DemandSignalKind.CAPACITY_USAGE

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_availability(
            "sig-av4", "fc-av4", "tenant-1", "avail-D"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_low(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_availability(
            "sig-av5", "fc-av5", "tenant-1", "avail-E", confidence=0.35
        )
        assert result["confidence_band"] == ForecastConfidenceBand.LOW.value

    def test_has_availability_ref_key(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_availability(
            "sig-av6", "fc-av6", "tenant-1", "avail-F"
        )
        assert result["availability_ref"] == "avail-F"


# ===================================================================
# forecast_from_financials
# ===================================================================


class TestForecastFromFinancials:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_financials(
            "sig-fn1", "fc-fn1", "tenant-1", "budget-A"
        )
        assert isinstance(result, dict)

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_financials(
            "sig-fn2", "fc-fn2", "tenant-1", "budget-B"
        )
        assert result["source_type"] == "financials"

    def test_signal_kind_budget_burn(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_financials(
            "sig-fn3", "fc-fn3", "tenant-1", "budget-C"
        )
        sig = forecasting_engine.get_signal("sig-fn3")
        assert sig.kind == DemandSignalKind.BUDGET_BURN

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_financials(
            "sig-fn4", "fc-fn4", "tenant-1", "budget-D"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_financials(
            "sig-fn5", "fc-fn5", "tenant-1", "budget-E", confidence=0.5
        )
        assert result["confidence_band"] == ForecastConfidenceBand.MEDIUM.value

    def test_has_budget_ref_key(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_financials(
            "sig-fn6", "fc-fn6", "tenant-1", "budget-F"
        )
        assert result["budget_ref"] == "budget-F"


# ===================================================================
# forecast_from_assets
# ===================================================================


class TestForecastFromAssets:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_assets(
            "sig-as1", "fc-as1", "tenant-1", "asset-A"
        )
        assert isinstance(result, dict)

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_assets(
            "sig-as2", "fc-as2", "tenant-1", "asset-B"
        )
        assert result["source_type"] == "assets"

    def test_signal_kind_asset_utilization(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_assets(
            "sig-as3", "fc-as3", "tenant-1", "asset-C"
        )
        sig = forecasting_engine.get_signal("sig-as3")
        assert sig.kind == DemandSignalKind.ASSET_UTILIZATION

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_assets(
            "sig-as4", "fc-as4", "tenant-1", "asset-D"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_assets(
            "sig-as5", "fc-as5", "tenant-1", "asset-E", confidence=0.8
        )
        assert result["confidence_band"] == ForecastConfidenceBand.HIGH.value

    def test_has_asset_ref_key(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_assets(
            "sig-as6", "fc-as6", "tenant-1", "asset-F"
        )
        assert result["asset_ref"] == "asset-F"


# ===================================================================
# forecast_from_continuity
# ===================================================================


class TestForecastFromContinuity:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_continuity(
            "sig-ct1", "fc-ct1", "tenant-1", "cont-A"
        )
        assert isinstance(result, dict)

    def test_source_type(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_continuity(
            "sig-ct2", "fc-ct2", "tenant-1", "cont-B"
        )
        assert result["source_type"] == "continuity"

    def test_signal_kind_incident_rate(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_continuity(
            "sig-ct3", "fc-ct3", "tenant-1", "cont-C"
        )
        sig = forecasting_engine.get_signal("sig-ct3")
        assert sig.kind == DemandSignalKind.INCIDENT_RATE

    def test_signal_count_gte_1(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_continuity(
            "sig-ct4", "fc-ct4", "tenant-1", "cont-D"
        )
        assert result["signal_count"] >= 1

    def test_confidence_band_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_continuity(
            "sig-ct5", "fc-ct5", "tenant-1", "cont-E", confidence=0.6
        )
        assert result["confidence_band"] == ForecastConfidenceBand.MEDIUM.value

    def test_has_continuity_ref_key(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.forecast_from_continuity(
            "sig-ct6", "fc-ct6", "tenant-1", "cont-F"
        )
        assert result["continuity_ref"] == "cont-F"


# ===================================================================
# attach_forecast_to_memory_mesh
# ===================================================================


class TestAttachForecastToMemoryMesh:
    def test_returns_memory_record(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_title_is_bounded(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-title")
        assert mem.title == "Forecasting state"
        assert "scope-title" not in mem.title
        assert mem.scope_ref_id == "scope-title"

    def test_correct_tags(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-2")
        assert set(mem.tags) == {"forecasting", "demand", "allocation"}

    def test_content_has_total_signals(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-3")
        assert "total_signals" in mem.content

    def test_content_has_total_forecasts(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-4")
        assert "total_forecasts" in mem.content

    def test_content_has_total_scenarios(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-5")
        assert "total_scenarios" in mem.content

    def test_content_has_total_projections(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-6")
        assert "total_projections" in mem.content

    def test_content_has_total_recommendations(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-7")
        assert "total_recommendations" in mem.content

    def test_content_has_total_capacity_forecasts(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-8")
        assert "total_capacity_forecasts" in mem.content

    def test_content_has_total_budget_forecasts(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-9")
        assert "total_budget_forecasts" in mem.content

    def test_content_has_total_risk_forecasts(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-10")
        assert "total_risk_forecasts" in mem.content

    def test_content_has_total_violations(self, integration: ForecastingRuntimeIntegration) -> None:
        mem = integration.attach_forecast_to_memory_mesh("scope-11")
        assert "total_violations" in mem.content

    def test_content_counts_reflect_engine(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        # Create a signal + forecast first
        integration.forecast_from_portfolio(
            "sig-mm1", "fc-mm1", "tenant-1", "portfolio-mm"
        )
        mem = integration.attach_forecast_to_memory_mesh("scope-counts")
        assert mem.content["total_signals"] == forecasting_engine.signal_count
        assert mem.content["total_forecasts"] == forecasting_engine.forecast_count


# ===================================================================
# attach_forecast_to_graph
# ===================================================================


class TestAttachForecastToGraph:
    def test_returns_dict(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.attach_forecast_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_all_keys_present(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.attach_forecast_to_graph("scope-g2")
        expected_keys = {
            "scope_ref_id",
            "total_signals",
            "total_forecasts",
            "total_scenarios",
            "total_projections",
            "total_recommendations",
            "total_capacity_forecasts",
            "total_budget_forecasts",
            "total_risk_forecasts",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_values_match_engine_counts(
        self,
        integration: ForecastingRuntimeIntegration,
        forecasting_engine: ForecastingRuntimeEngine,
    ) -> None:
        integration.forecast_from_assets(
            "sig-g1", "fc-g1", "tenant-1", "asset-g"
        )
        result = integration.attach_forecast_to_graph("scope-g3")
        assert result["total_signals"] == forecasting_engine.signal_count
        assert result["total_forecasts"] == forecasting_engine.forecast_count
        assert result["total_scenarios"] == forecasting_engine.scenario_count
        assert result["total_projections"] == forecasting_engine.projection_count
        assert result["total_recommendations"] == forecasting_engine.recommendation_count
        assert result["total_capacity_forecasts"] == forecasting_engine.capacity_forecast_count
        assert result["total_budget_forecasts"] == forecasting_engine.budget_forecast_count
        assert result["total_risk_forecasts"] == forecasting_engine.risk_forecast_count
        assert result["total_violations"] == forecasting_engine.violation_count

    def test_scope_ref_id_matches(self, integration: ForecastingRuntimeIntegration) -> None:
        result = integration.attach_forecast_to_graph("my-scope")
        assert result["scope_ref_id"] == "my-scope"


# ===================================================================
# Events emitted
# ===================================================================


class TestEventsEmitted:
    def test_portfolio_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_portfolio(
            "sig-ev1", "fc-ev1", "tenant-1", "portfolio-ev"
        )
        assert event_spine.event_count > before

    def test_service_requests_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_service_requests(
            "sig-ev2", "fc-ev2", "tenant-1", "svc-ev"
        )
        assert event_spine.event_count > before

    def test_availability_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_availability(
            "sig-ev3", "fc-ev3", "tenant-1", "avail-ev"
        )
        assert event_spine.event_count > before

    def test_financials_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_financials(
            "sig-ev4", "fc-ev4", "tenant-1", "budget-ev"
        )
        assert event_spine.event_count > before

    def test_assets_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_assets(
            "sig-ev5", "fc-ev5", "tenant-1", "asset-ev"
        )
        assert event_spine.event_count > before

    def test_continuity_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.forecast_from_continuity(
            "sig-ev6", "fc-ev6", "tenant-1", "cont-ev"
        )
        assert event_spine.event_count > before

    def test_memory_mesh_attach_emits_event(
        self, integration: ForecastingRuntimeIntegration, event_spine: EventSpineEngine
    ) -> None:
        before = event_spine.event_count
        integration.attach_forecast_to_memory_mesh("scope-ev1")
        assert event_spine.event_count > before


# ===================================================================
# Duplicate ID rejection
# ===================================================================


class TestDuplicateIdRejection:
    def test_duplicate_signal_id_raises(
        self, integration: ForecastingRuntimeIntegration
    ) -> None:
        integration.forecast_from_portfolio(
            "sig-dup1", "fc-dup1", "tenant-1", "portfolio-dup"
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate signal_id"):
            integration.forecast_from_portfolio(
                "sig-dup1", "fc-dup1b", "tenant-1", "portfolio-dup2"
            )

    def test_duplicate_forecast_id_raises(
        self, integration: ForecastingRuntimeIntegration
    ) -> None:
        integration.forecast_from_portfolio(
            "sig-dup2", "fc-dup2", "tenant-1", "portfolio-dup3"
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            integration.forecast_from_service_requests(
                "sig-dup3", "fc-dup2", "tenant-1", "svc-dup"
            )

    def test_duplicate_signal_id_across_methods(
        self, integration: ForecastingRuntimeIntegration
    ) -> None:
        integration.forecast_from_assets(
            "sig-cross1", "fc-cross1", "tenant-1", "asset-cross"
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate signal_id"):
            integration.forecast_from_continuity(
                "sig-cross1", "fc-cross2", "tenant-1", "cont-cross"
            )
