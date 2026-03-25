"""Purpose: forecasting runtime integration bridge.
Governance scope: composing forecasting runtime with portfolios, service
    requests, availability, financials, assets, and continuity plans;
    memory mesh and operational graph attachment.
Dependencies: forecasting_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every forecasting action emits events.
  - Forecast state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.forecasting_runtime import (
    DemandSignalKind,
    ForecastHorizon,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .forecasting_runtime import ForecastingRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ForecastingRuntimeIntegration:
    """Integration bridge for forecasting runtime with platform layers."""

    def __init__(
        self,
        forecasting_engine: ForecastingRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(forecasting_engine, ForecastingRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "forecasting_engine must be a ForecastingRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._forecasting = forecasting_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Forecast creation helpers
    # ------------------------------------------------------------------

    def forecast_from_portfolio(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        portfolio_ref: str,
        *,
        projected_value: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.MEDIUM,
    ) -> dict[str, Any]:
        """Create a forecast from portfolio demand signals."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.CAPACITY_USAGE,
            scope_ref_id=portfolio_ref,
            value=projected_value,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=portfolio_ref,
            confidence=confidence, projected_value=projected_value,
        )
        _emit(self._events, "forecast_from_portfolio", {
            "forecast_id": forecast_id, "portfolio_ref": portfolio_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "portfolio_ref": portfolio_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "portfolio",
        }

    def forecast_from_service_requests(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        service_ref: str,
        *,
        request_volume: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> dict[str, Any]:
        """Create a forecast from service request volume."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id=service_ref,
            value=request_volume,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=service_ref,
            confidence=confidence, projected_value=request_volume,
        )
        _emit(self._events, "forecast_from_service_requests", {
            "forecast_id": forecast_id, "service_ref": service_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "service_ref": service_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "service_requests",
        }

    def forecast_from_availability(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        availability_ref: str,
        *,
        utilization: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> dict[str, Any]:
        """Create a forecast from availability/utilization data."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.CAPACITY_USAGE,
            scope_ref_id=availability_ref,
            value=utilization,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=availability_ref,
            confidence=confidence, projected_value=utilization,
        )
        _emit(self._events, "forecast_from_availability", {
            "forecast_id": forecast_id, "availability_ref": availability_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "availability_ref": availability_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "availability",
        }

    def forecast_from_financials(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        budget_ref: str,
        *,
        spend_value: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.MEDIUM,
    ) -> dict[str, Any]:
        """Create a forecast from financial/budget burn data."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.BUDGET_BURN,
            scope_ref_id=budget_ref,
            value=spend_value,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=budget_ref,
            confidence=confidence, projected_value=spend_value,
        )
        _emit(self._events, "forecast_from_financials", {
            "forecast_id": forecast_id, "budget_ref": budget_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "budget_ref": budget_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "financials",
        }

    def forecast_from_assets(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        asset_ref: str,
        *,
        utilization: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> dict[str, Any]:
        """Create a forecast from asset utilization data."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.ASSET_UTILIZATION,
            scope_ref_id=asset_ref,
            value=utilization,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=asset_ref,
            confidence=confidence, projected_value=utilization,
        )
        _emit(self._events, "forecast_from_assets", {
            "forecast_id": forecast_id, "asset_ref": asset_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "asset_ref": asset_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "assets",
        }

    def forecast_from_continuity(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        continuity_ref: str,
        *,
        incident_rate: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.MEDIUM,
    ) -> dict[str, Any]:
        """Create a forecast from continuity/incident data."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.INCIDENT_RATE,
            scope_ref_id=continuity_ref,
            value=incident_rate,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=continuity_ref,
            confidence=confidence, projected_value=incident_rate,
        )
        _emit(self._events, "forecast_from_continuity", {
            "forecast_id": forecast_id, "continuity_ref": continuity_ref,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "continuity_ref": continuity_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "continuity",
        }

    # ------------------------------------------------------------------
    # Cross-domain: forecasting + math optimization
    # ------------------------------------------------------------------

    def forecast_with_optimization(
        self,
        signal_id: str,
        forecast_id: str,
        tenant_id: str,
        forecast_ref: str,
        objective_ref: str,
        *,
        projected_value: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.MEDIUM,
        description: str = "optimized forecast",
    ) -> dict[str, Any]:
        """Create a forecast that references a math optimization objective."""
        self._forecasting.register_signal(
            signal_id, tenant_id,
            kind=DemandSignalKind.CAPACITY_USAGE,
            scope_ref_id=forecast_ref,
            value=projected_value,
        )
        fc = self._forecasting.build_forecast(
            forecast_id, tenant_id,
            horizon=horizon, scope_ref_id=forecast_ref,
            confidence=confidence, projected_value=projected_value,
        )
        _emit(self._events, "forecast_with_optimization", {
            "forecast_id": forecast_id, "forecast_ref": forecast_ref,
            "objective_ref": objective_ref, "description": description,
        }, forecast_id)
        return {
            "forecast_id": fc.forecast_id,
            "tenant_id": fc.tenant_id,
            "forecast_ref": forecast_ref,
            "objective_ref": objective_ref,
            "status": fc.status.value,
            "confidence_band": fc.confidence_band.value,
            "signal_count": fc.signal_count,
            "source_type": "math_optimization",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_forecast_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist forecasting state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_signals": self._forecasting.signal_count,
            "total_forecasts": self._forecasting.forecast_count,
            "total_scenarios": self._forecasting.scenario_count,
            "total_projections": self._forecasting.projection_count,
            "total_recommendations": self._forecasting.recommendation_count,
            "total_capacity_forecasts": self._forecasting.capacity_forecast_count,
            "total_budget_forecasts": self._forecasting.budget_forecast_count,
            "total_risk_forecasts": self._forecasting.risk_forecast_count,
            "total_violations": self._forecasting.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-fcast", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Forecasting state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("forecasting", "demand", "allocation"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "forecast_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_forecast_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return forecasting state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_signals": self._forecasting.signal_count,
            "total_forecasts": self._forecasting.forecast_count,
            "total_scenarios": self._forecasting.scenario_count,
            "total_projections": self._forecasting.projection_count,
            "total_recommendations": self._forecasting.recommendation_count,
            "total_capacity_forecasts": self._forecasting.capacity_forecast_count,
            "total_budget_forecasts": self._forecasting.budget_forecast_count,
            "total_risk_forecasts": self._forecasting.risk_forecast_count,
            "total_violations": self._forecasting.violation_count,
        }
