"""Purpose: forecasting / demand / scenario allocation runtime engine.
Governance scope: ingesting demand signals, building forecasts, scenario
    projections, allocation recommendations, capacity/budget/risk forecasts,
    detecting violations, producing immutable snapshots.
Dependencies: forecasting_runtime contracts, event_spine, core invariants.
Invariants:
  - Forecasts must reference ingested signals.
  - Low-confidence forecasts block aggressive allocation.
  - Terminal forecasts cannot be re-opened.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.forecasting_runtime import (
    AllocationDisposition,
    AllocationRecommendation,
    BudgetForecast,
    CapacityForecast,
    DemandSignal,
    DemandSignalKind,
    ForecastClosureReport,
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fcast", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


def _confidence_band(confidence: float) -> ForecastConfidenceBand:
    """Derive confidence band from numeric confidence."""
    if confidence >= 0.8:
        return ForecastConfidenceBand.HIGH
    if confidence >= 0.5:
        return ForecastConfidenceBand.MEDIUM
    if confidence >= 0.3:
        return ForecastConfidenceBand.LOW
    return ForecastConfidenceBand.VERY_LOW


_FORECAST_TERMINAL = frozenset({ForecastStatus.EXPIRED, ForecastStatus.CANCELLED})


class ForecastingRuntimeEngine:
    """Forecasting, demand, and scenario allocation engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._signals: dict[str, DemandSignal] = {}
        self._forecasts: dict[str, ForecastRecord] = {}
        self._scenarios: dict[str, ScenarioModel] = {}
        self._projections: dict[str, ScenarioProjection] = {}
        self._recommendations: dict[str, AllocationRecommendation] = {}
        self._capacity_forecasts: dict[str, CapacityForecast] = {}
        self._budget_forecasts: dict[str, BudgetForecast] = {}
        self._risk_forecasts: dict[str, RiskForecast] = {}
        self._violations: dict[str, Any] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def signal_count(self) -> int:
        return len(self._signals)

    @property
    def forecast_count(self) -> int:
        return len(self._forecasts)

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def projection_count(self) -> int:
        return len(self._projections)

    @property
    def recommendation_count(self) -> int:
        return len(self._recommendations)

    @property
    def capacity_forecast_count(self) -> int:
        return len(self._capacity_forecasts)

    @property
    def budget_forecast_count(self) -> int:
        return len(self._budget_forecasts)

    @property
    def risk_forecast_count(self) -> int:
        return len(self._risk_forecasts)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Demand signals
    # ------------------------------------------------------------------

    def register_signal(
        self,
        signal_id: str,
        tenant_id: str,
        *,
        kind: DemandSignalKind = DemandSignalKind.REQUEST_VOLUME,
        scope_ref_id: str = "",
        value: float = 0.0,
    ) -> DemandSignal:
        """Ingest a demand signal."""
        if signal_id in self._signals:
            raise RuntimeCoreInvariantError("Duplicate signal_id")
        now = _now_iso()
        signal = DemandSignal(
            signal_id=signal_id, tenant_id=tenant_id,
            kind=kind, scope_ref_id=scope_ref_id,
            value=value, recorded_at=now,
        )
        self._signals[signal_id] = signal
        _emit(self._events, "signal_registered", {
            "signal_id": signal_id, "kind": kind.value, "value": value,
        }, signal_id)
        return signal

    def get_signal(self, signal_id: str) -> DemandSignal:
        """Get a signal by ID."""
        s = self._signals.get(signal_id)
        if s is None:
            raise RuntimeCoreInvariantError("Unknown signal_id")
        return s

    def signals_for_tenant(self, tenant_id: str) -> tuple[DemandSignal, ...]:
        """Return all signals for a tenant."""
        return tuple(s for s in self._signals.values() if s.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Forecasts
    # ------------------------------------------------------------------

    def build_forecast(
        self,
        forecast_id: str,
        tenant_id: str,
        *,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
        scope_ref_id: str = "",
        confidence: float = 0.5,
        projected_value: float = 0.0,
    ) -> ForecastRecord:
        """Build a forecast from demand signals."""
        if forecast_id in self._forecasts:
            raise RuntimeCoreInvariantError("Duplicate forecast_id")
        # Count signals for this tenant/scope
        signal_count = sum(
            1 for s in self._signals.values()
            if s.tenant_id == tenant_id
            and (not scope_ref_id or s.scope_ref_id == scope_ref_id)
        )
        now = _now_iso()
        band = _confidence_band(confidence)
        forecast = ForecastRecord(
            forecast_id=forecast_id, tenant_id=tenant_id,
            status=ForecastStatus.ACTIVE, horizon=horizon,
            confidence_band=band, confidence=confidence,
            signal_count=signal_count, scope_ref_id=scope_ref_id,
            projected_value=projected_value, created_at=now,
        )
        self._forecasts[forecast_id] = forecast
        _emit(self._events, "forecast_built", {
            "forecast_id": forecast_id, "confidence": confidence,
            "signal_count": signal_count,
        }, forecast_id)
        return forecast

    def get_forecast(self, forecast_id: str) -> ForecastRecord:
        """Get a forecast by ID."""
        f = self._forecasts.get(forecast_id)
        if f is None:
            raise RuntimeCoreInvariantError("Unknown forecast_id")
        return f

    def supersede_forecast(self, forecast_id: str) -> ForecastRecord:
        """Mark a forecast as superseded."""
        old = self.get_forecast(forecast_id)
        if old.status in _FORECAST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot supersede terminal forecast")
        updated = ForecastRecord(
            forecast_id=old.forecast_id, tenant_id=old.tenant_id,
            status=ForecastStatus.SUPERSEDED, horizon=old.horizon,
            confidence_band=old.confidence_band, confidence=old.confidence,
            signal_count=old.signal_count, scope_ref_id=old.scope_ref_id,
            projected_value=old.projected_value, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._forecasts[forecast_id] = updated
        _emit(self._events, "forecast_superseded", {"forecast_id": forecast_id}, forecast_id)
        return updated

    def expire_forecast(self, forecast_id: str) -> ForecastRecord:
        """Expire a forecast."""
        old = self.get_forecast(forecast_id)
        if old.status in _FORECAST_TERMINAL:
            raise RuntimeCoreInvariantError("Forecast already in terminal status")
        updated = ForecastRecord(
            forecast_id=old.forecast_id, tenant_id=old.tenant_id,
            status=ForecastStatus.EXPIRED, horizon=old.horizon,
            confidence_band=old.confidence_band, confidence=old.confidence,
            signal_count=old.signal_count, scope_ref_id=old.scope_ref_id,
            projected_value=old.projected_value, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._forecasts[forecast_id] = updated
        _emit(self._events, "forecast_expired", {"forecast_id": forecast_id}, forecast_id)
        return updated

    def cancel_forecast(self, forecast_id: str) -> ForecastRecord:
        """Cancel a forecast."""
        old = self.get_forecast(forecast_id)
        if old.status in _FORECAST_TERMINAL:
            raise RuntimeCoreInvariantError("Forecast already in terminal status")
        updated = ForecastRecord(
            forecast_id=old.forecast_id, tenant_id=old.tenant_id,
            status=ForecastStatus.CANCELLED, horizon=old.horizon,
            confidence_band=old.confidence_band, confidence=old.confidence,
            signal_count=old.signal_count, scope_ref_id=old.scope_ref_id,
            projected_value=old.projected_value, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._forecasts[forecast_id] = updated
        _emit(self._events, "forecast_cancelled", {"forecast_id": forecast_id}, forecast_id)
        return updated

    def forecasts_for_tenant(self, tenant_id: str) -> tuple[ForecastRecord, ...]:
        """Return all forecasts for a tenant."""
        return tuple(f for f in self._forecasts.values() if f.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def build_scenario(
        self,
        scenario_id: str,
        tenant_id: str,
        name: str,
        *,
        horizon: ForecastHorizon = ForecastHorizon.MEDIUM,
        description: str = "",
    ) -> ScenarioModel:
        """Build a scenario model."""
        if scenario_id in self._scenarios:
            raise RuntimeCoreInvariantError("Duplicate scenario_id")
        now = _now_iso()
        scenario = ScenarioModel(
            scenario_id=scenario_id, tenant_id=tenant_id, name=name,
            status=ScenarioStatus.ACTIVE, horizon=horizon,
            description=description, created_at=now,
        )
        self._scenarios[scenario_id] = scenario
        _emit(self._events, "scenario_built", {
            "scenario_id": scenario_id, "name": name,
        }, scenario_id)
        return scenario

    def get_scenario(self, scenario_id: str) -> ScenarioModel:
        """Get a scenario by ID."""
        s = self._scenarios.get(scenario_id)
        if s is None:
            raise RuntimeCoreInvariantError("Unknown scenario_id")
        return s

    def evaluate_scenario(self, scenario_id: str) -> ScenarioModel:
        """Mark a scenario as evaluated."""
        old = self.get_scenario(scenario_id)
        if old.status == ScenarioStatus.ARCHIVED:
            raise RuntimeCoreInvariantError("Cannot evaluate archived scenario")
        updated = ScenarioModel(
            scenario_id=old.scenario_id, tenant_id=old.tenant_id,
            name=old.name, status=ScenarioStatus.EVALUATED,
            horizon=old.horizon, description=old.description,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._scenarios[scenario_id] = updated
        _emit(self._events, "scenario_evaluated", {"scenario_id": scenario_id}, scenario_id)
        return updated

    def archive_scenario(self, scenario_id: str) -> ScenarioModel:
        """Archive a scenario."""
        old = self.get_scenario(scenario_id)
        if old.status == ScenarioStatus.ARCHIVED:
            raise RuntimeCoreInvariantError("Scenario already archived")
        updated = ScenarioModel(
            scenario_id=old.scenario_id, tenant_id=old.tenant_id,
            name=old.name, status=ScenarioStatus.ARCHIVED,
            horizon=old.horizon, description=old.description,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._scenarios[scenario_id] = updated
        _emit(self._events, "scenario_archived", {"scenario_id": scenario_id}, scenario_id)
        return updated

    def scenarios_for_tenant(self, tenant_id: str) -> tuple[ScenarioModel, ...]:
        """Return all scenarios for a tenant."""
        return tuple(s for s in self._scenarios.values() if s.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Projections
    # ------------------------------------------------------------------

    def project_scenario(
        self,
        projection_id: str,
        scenario_id: str,
        forecast_id: str,
        *,
        projected_value: float = 0.0,
        probability: float = 0.5,
        impact_score: float = 0.5,
    ) -> ScenarioProjection:
        """Create a projection from a scenario and forecast."""
        if projection_id in self._projections:
            raise RuntimeCoreInvariantError("Duplicate projection_id")
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError("Unknown scenario_id")
        if forecast_id not in self._forecasts:
            raise RuntimeCoreInvariantError("Unknown forecast_id")
        now = _now_iso()
        proj = ScenarioProjection(
            projection_id=projection_id, scenario_id=scenario_id,
            forecast_id=forecast_id, projected_value=projected_value,
            probability=probability, impact_score=impact_score,
            projected_at=now,
        )
        self._projections[projection_id] = proj
        _emit(self._events, "scenario_projected", {
            "projection_id": projection_id, "scenario_id": scenario_id,
        }, projection_id)
        return proj

    def projections_for_scenario(self, scenario_id: str) -> tuple[ScenarioProjection, ...]:
        """Return all projections for a scenario."""
        return tuple(p for p in self._projections.values() if p.scenario_id == scenario_id)

    # ------------------------------------------------------------------
    # Capacity / Budget / Risk forecasts
    # ------------------------------------------------------------------

    def project_capacity(
        self,
        forecast_id: str,
        tenant_id: str,
        *,
        scope_ref_id: str = "",
        current_utilization: float = 0.0,
        projected_utilization: float = 0.0,
        headroom: float = 1.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> CapacityForecast:
        """Project capacity pressure."""
        if forecast_id in self._capacity_forecasts:
            raise RuntimeCoreInvariantError("Duplicate capacity forecast_id")
        now = _now_iso()
        cf = CapacityForecast(
            forecast_id=forecast_id, tenant_id=tenant_id,
            scope_ref_id=scope_ref_id,
            current_utilization=current_utilization,
            projected_utilization=projected_utilization,
            headroom=headroom, confidence=confidence,
            horizon=horizon, projected_at=now,
        )
        self._capacity_forecasts[forecast_id] = cf
        _emit(self._events, "capacity_projected", {
            "forecast_id": forecast_id,
            "projected_utilization": projected_utilization,
        }, forecast_id)
        return cf

    def project_budget(
        self,
        forecast_id: str,
        tenant_id: str,
        *,
        scope_ref_id: str = "",
        current_spend: float = 0.0,
        projected_spend: float = 0.0,
        budget_limit: float = 0.0,
        burn_rate: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> BudgetForecast:
        """Project budget burn."""
        if forecast_id in self._budget_forecasts:
            raise RuntimeCoreInvariantError("Duplicate budget forecast_id")
        now = _now_iso()
        bf = BudgetForecast(
            forecast_id=forecast_id, tenant_id=tenant_id,
            scope_ref_id=scope_ref_id,
            current_spend=current_spend, projected_spend=projected_spend,
            budget_limit=budget_limit, burn_rate=burn_rate,
            confidence=confidence, horizon=horizon,
            projected_at=now,
        )
        self._budget_forecasts[forecast_id] = bf
        _emit(self._events, "budget_projected", {
            "forecast_id": forecast_id,
            "projected_spend": projected_spend,
        }, forecast_id)
        return bf

    def project_risk(
        self,
        forecast_id: str,
        tenant_id: str,
        *,
        scope_ref_id: str = "",
        current_risk: float = 0.0,
        projected_risk: float = 0.0,
        mitigation_coverage: float = 0.0,
        confidence: float = 0.5,
        horizon: ForecastHorizon = ForecastHorizon.SHORT,
    ) -> RiskForecast:
        """Project risk pressure."""
        if forecast_id in self._risk_forecasts:
            raise RuntimeCoreInvariantError("Duplicate risk forecast_id")
        now = _now_iso()
        rf = RiskForecast(
            forecast_id=forecast_id, tenant_id=tenant_id,
            scope_ref_id=scope_ref_id,
            current_risk=current_risk, projected_risk=projected_risk,
            mitigation_coverage=mitigation_coverage,
            confidence=confidence, horizon=horizon,
            projected_at=now,
        )
        self._risk_forecasts[forecast_id] = rf
        _emit(self._events, "risk_projected", {
            "forecast_id": forecast_id,
            "projected_risk": projected_risk,
        }, forecast_id)
        return rf

    # ------------------------------------------------------------------
    # Allocation recommendations
    # ------------------------------------------------------------------

    def recommend_allocation(
        self,
        recommendation_id: str,
        forecast_id: str,
        tenant_id: str,
        *,
        scope_ref_id: str = "",
        recommended_value: float = 0.0,
        reason: str = "",
    ) -> AllocationRecommendation:
        """Recommend a resource allocation based on a forecast."""
        if recommendation_id in self._recommendations:
            raise RuntimeCoreInvariantError("Duplicate recommendation_id")
        forecast = self.get_forecast(forecast_id)
        # Low confidence blocks aggressive allocation
        if forecast.confidence_band == ForecastConfidenceBand.VERY_LOW:
            raise RuntimeCoreInvariantError(
                "Cannot recommend allocation from VERY_LOW confidence forecast"
            )
        now = _now_iso()
        rec = AllocationRecommendation(
            recommendation_id=recommendation_id, forecast_id=forecast_id,
            tenant_id=tenant_id, disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id=scope_ref_id, recommended_value=recommended_value,
            confidence=forecast.confidence, reason=reason,
            created_at=now,
        )
        self._recommendations[recommendation_id] = rec
        _emit(self._events, "allocation_recommended", {
            "recommendation_id": recommendation_id,
            "forecast_id": forecast_id,
        }, recommendation_id)
        return rec

    def accept_recommendation(self, recommendation_id: str) -> AllocationRecommendation:
        """Accept an allocation recommendation."""
        old = self._recommendations.get(recommendation_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown recommendation_id")
        if old.disposition != AllocationDisposition.RECOMMENDED:
            raise RuntimeCoreInvariantError("Can only accept RECOMMENDED")
        updated = AllocationRecommendation(
            recommendation_id=old.recommendation_id, forecast_id=old.forecast_id,
            tenant_id=old.tenant_id, disposition=AllocationDisposition.ACCEPTED,
            scope_ref_id=old.scope_ref_id, recommended_value=old.recommended_value,
            confidence=old.confidence, reason=old.reason,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._recommendations[recommendation_id] = updated
        _emit(self._events, "recommendation_accepted", {
            "recommendation_id": recommendation_id,
        }, recommendation_id)
        return updated

    def reject_recommendation(self, recommendation_id: str) -> AllocationRecommendation:
        """Reject an allocation recommendation."""
        old = self._recommendations.get(recommendation_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown recommendation_id")
        if old.disposition != AllocationDisposition.RECOMMENDED:
            raise RuntimeCoreInvariantError("Can only reject RECOMMENDED")
        updated = AllocationRecommendation(
            recommendation_id=old.recommendation_id, forecast_id=old.forecast_id,
            tenant_id=old.tenant_id, disposition=AllocationDisposition.REJECTED,
            scope_ref_id=old.scope_ref_id, recommended_value=old.recommended_value,
            confidence=old.confidence, reason=old.reason,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._recommendations[recommendation_id] = updated
        _emit(self._events, "recommendation_rejected", {
            "recommendation_id": recommendation_id,
        }, recommendation_id)
        return updated

    def defer_recommendation(self, recommendation_id: str) -> AllocationRecommendation:
        """Defer an allocation recommendation."""
        old = self._recommendations.get(recommendation_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown recommendation_id")
        if old.disposition != AllocationDisposition.RECOMMENDED:
            raise RuntimeCoreInvariantError("Can only defer RECOMMENDED")
        updated = AllocationRecommendation(
            recommendation_id=old.recommendation_id, forecast_id=old.forecast_id,
            tenant_id=old.tenant_id, disposition=AllocationDisposition.DEFERRED,
            scope_ref_id=old.scope_ref_id, recommended_value=old.recommended_value,
            confidence=old.confidence, reason=old.reason,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._recommendations[recommendation_id] = updated
        _emit(self._events, "recommendation_deferred", {
            "recommendation_id": recommendation_id,
        }, recommendation_id)
        return updated

    def recommendations_for_forecast(self, forecast_id: str) -> tuple[AllocationRecommendation, ...]:
        """Return all recommendations for a forecast."""
        return tuple(r for r in self._recommendations.values() if r.forecast_id == forecast_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_forecast_violations(self) -> tuple:
        """Detect forecasting violations."""
        from ..contracts.forecasting_runtime import ForecastSnapshot as _  # noqa: F401 — ensure import
        now = _now_iso()
        new_violations: list = []

        # Active forecasts with zero signals
        for fc in self._forecasts.values():
            if fc.status == ForecastStatus.ACTIVE and fc.signal_count == 0:
                vid = stable_identifier("viol-fcast", {
                    "forecast": fc.forecast_id, "op": "no_signals",
                })
                if vid not in self._violations:
                    from ..contracts.forecasting_runtime import ForecastSnapshot  # noqa: F811
                    v = {
                        "violation_id": vid,
                        "forecast_id": fc.forecast_id,
                        "tenant_id": fc.tenant_id,
                        "operation": "no_signals",
                        "reason": "active forecast has no demand signals",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Budget forecasts where projected_spend > budget_limit
        for bf in self._budget_forecasts.values():
            if bf.budget_limit > 0 and bf.projected_spend > bf.budget_limit:
                vid = stable_identifier("viol-fcast", {
                    "budget": bf.forecast_id, "op": "budget_breach",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "forecast_id": bf.forecast_id,
                        "tenant_id": bf.tenant_id,
                        "operation": "budget_breach",
                        "reason": "budget forecast exceeds budget limit",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Capacity forecasts with projected_utilization > 0.9 (near capacity)
        for cf in self._capacity_forecasts.values():
            if cf.projected_utilization > 0.9:
                vid = stable_identifier("viol-fcast", {
                    "capacity": cf.forecast_id, "op": "capacity_pressure",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "forecast_id": cf.forecast_id,
                        "tenant_id": cf.tenant_id,
                        "operation": "capacity_pressure",
                        "reason": "capacity forecast exceeds utilization threshold",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "forecast_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def forecast_snapshot(self, snapshot_id: str) -> ForecastSnapshot:
        """Capture a point-in-time forecast snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        snap = ForecastSnapshot(
            snapshot_id=snapshot_id,
            total_signals=self.signal_count,
            total_forecasts=self.forecast_count,
            total_scenarios=self.scenario_count,
            total_projections=self.projection_count,
            total_recommendations=self.recommendation_count,
            total_capacity_forecasts=self.capacity_forecast_count,
            total_budget_forecasts=self.budget_forecast_count,
            total_risk_forecasts=self.risk_forecast_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "forecast_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"signals={self.signal_count}",
            f"forecasts={self.forecast_count}",
            f"scenarios={self.scenario_count}",
            f"projections={self.projection_count}",
            f"recommendations={self.recommendation_count}",
            f"capacity={self.capacity_forecast_count}",
            f"budget={self.budget_forecast_count}",
            f"risk={self.risk_forecast_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
