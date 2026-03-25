"""Purpose: forecasting / demand / scenario allocation runtime contracts.
Governance scope: typed descriptors for demand signals, forecasts, scenarios,
    scenario projections, allocation recommendations, capacity/budget/risk
    forecasts, forecast snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every forecast references ingested demand signals.
  - Low-confidence forecasts block aggressive allocation.
  - Completed forecasts cannot be re-opened.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ForecastStatus(Enum):
    """Status of a forecast."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DemandSignalKind(Enum):
    """Kind of demand signal."""
    REQUEST_VOLUME = "request_volume"
    CAPACITY_USAGE = "capacity_usage"
    BUDGET_BURN = "budget_burn"
    ASSET_UTILIZATION = "asset_utilization"
    CONNECTOR_LOAD = "connector_load"
    INCIDENT_RATE = "incident_rate"


class ScenarioStatus(Enum):
    """Status of a scenario model."""
    DRAFT = "draft"
    ACTIVE = "active"
    EVALUATED = "evaluated"
    ARCHIVED = "archived"


class AllocationDisposition(Enum):
    """Disposition of an allocation recommendation."""
    RECOMMENDED = "recommended"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ForecastConfidenceBand(Enum):
    """Confidence band for a forecast."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ForecastHorizon(Enum):
    """Time horizon for a forecast."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    STRATEGIC = "strategic"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DemandSignal(ContractRecord):
    """A demand signal ingested for forecasting."""

    signal_id: str = ""
    tenant_id: str = ""
    kind: DemandSignalKind = DemandSignalKind.REQUEST_VOLUME
    scope_ref_id: str = ""
    value: float = 0.0
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", require_non_empty_text(self.signal_id, "signal_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, DemandSignalKind):
            raise ValueError("kind must be a DemandSignalKind")
        object.__setattr__(self, "value", require_non_negative_float(self.value, "value"))
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ForecastRecord(ContractRecord):
    """A forecast built from demand signals."""

    forecast_id: str = ""
    tenant_id: str = ""
    status: ForecastStatus = ForecastStatus.DRAFT
    horizon: ForecastHorizon = ForecastHorizon.SHORT
    confidence_band: ForecastConfidenceBand = ForecastConfidenceBand.MEDIUM
    confidence: float = 0.0
    signal_count: int = 0
    scope_ref_id: str = ""
    projected_value: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, ForecastStatus):
            raise ValueError("status must be a ForecastStatus")
        if not isinstance(self.horizon, ForecastHorizon):
            raise ValueError("horizon must be a ForecastHorizon")
        if not isinstance(self.confidence_band, ForecastConfidenceBand):
            raise ValueError("confidence_band must be a ForecastConfidenceBand")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "signal_count", require_non_negative_int(self.signal_count, "signal_count"))
        object.__setattr__(self, "projected_value", require_non_negative_float(self.projected_value, "projected_value"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ScenarioModel(ContractRecord):
    """A scenario model for what-if analysis."""

    scenario_id: str = ""
    tenant_id: str = ""
    name: str = ""
    status: ScenarioStatus = ScenarioStatus.DRAFT
    horizon: ForecastHorizon = ForecastHorizon.MEDIUM
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.status, ScenarioStatus):
            raise ValueError("status must be a ScenarioStatus")
        if not isinstance(self.horizon, ForecastHorizon):
            raise ValueError("horizon must be a ForecastHorizon")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ScenarioProjection(ContractRecord):
    """A projection result from a scenario model."""

    projection_id: str = ""
    scenario_id: str = ""
    forecast_id: str = ""
    projected_value: float = 0.0
    probability: float = 0.0
    impact_score: float = 0.0
    projected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", require_non_empty_text(self.projection_id, "projection_id"))
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "projected_value", require_non_negative_float(self.projected_value, "projected_value"))
        object.__setattr__(self, "probability", require_unit_float(self.probability, "probability"))
        object.__setattr__(self, "impact_score", require_unit_float(self.impact_score, "impact_score"))
        require_datetime_text(self.projected_at, "projected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AllocationRecommendation(ContractRecord):
    """A recommendation for resource allocation."""

    recommendation_id: str = ""
    forecast_id: str = ""
    tenant_id: str = ""
    disposition: AllocationDisposition = AllocationDisposition.RECOMMENDED
    scope_ref_id: str = ""
    recommended_value: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", require_non_empty_text(self.recommendation_id, "recommendation_id"))
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.disposition, AllocationDisposition):
            raise ValueError("disposition must be an AllocationDisposition")
        object.__setattr__(self, "recommended_value", require_non_negative_float(self.recommended_value, "recommended_value"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CapacityForecast(ContractRecord):
    """A capacity pressure forecast."""

    forecast_id: str = ""
    tenant_id: str = ""
    scope_ref_id: str = ""
    current_utilization: float = 0.0
    projected_utilization: float = 0.0
    headroom: float = 0.0
    confidence: float = 0.0
    horizon: ForecastHorizon = ForecastHorizon.SHORT
    projected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "current_utilization", require_unit_float(self.current_utilization, "current_utilization"))
        object.__setattr__(self, "projected_utilization", require_unit_float(self.projected_utilization, "projected_utilization"))
        object.__setattr__(self, "headroom", require_unit_float(self.headroom, "headroom"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.horizon, ForecastHorizon):
            raise ValueError("horizon must be a ForecastHorizon")
        require_datetime_text(self.projected_at, "projected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BudgetForecast(ContractRecord):
    """A budget burn forecast."""

    forecast_id: str = ""
    tenant_id: str = ""
    scope_ref_id: str = ""
    current_spend: float = 0.0
    projected_spend: float = 0.0
    budget_limit: float = 0.0
    burn_rate: float = 0.0
    confidence: float = 0.0
    horizon: ForecastHorizon = ForecastHorizon.SHORT
    projected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "current_spend", require_non_negative_float(self.current_spend, "current_spend"))
        object.__setattr__(self, "projected_spend", require_non_negative_float(self.projected_spend, "projected_spend"))
        object.__setattr__(self, "budget_limit", require_non_negative_float(self.budget_limit, "budget_limit"))
        object.__setattr__(self, "burn_rate", require_non_negative_float(self.burn_rate, "burn_rate"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.horizon, ForecastHorizon):
            raise ValueError("horizon must be a ForecastHorizon")
        require_datetime_text(self.projected_at, "projected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RiskForecast(ContractRecord):
    """A risk pressure forecast."""

    forecast_id: str = ""
    tenant_id: str = ""
    scope_ref_id: str = ""
    current_risk: float = 0.0
    projected_risk: float = 0.0
    mitigation_coverage: float = 0.0
    confidence: float = 0.0
    horizon: ForecastHorizon = ForecastHorizon.SHORT
    projected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "forecast_id", require_non_empty_text(self.forecast_id, "forecast_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "current_risk", require_unit_float(self.current_risk, "current_risk"))
        object.__setattr__(self, "projected_risk", require_unit_float(self.projected_risk, "projected_risk"))
        object.__setattr__(self, "mitigation_coverage", require_unit_float(self.mitigation_coverage, "mitigation_coverage"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.horizon, ForecastHorizon):
            raise ValueError("horizon must be a ForecastHorizon")
        require_datetime_text(self.projected_at, "projected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ForecastSnapshot(ContractRecord):
    """Point-in-time forecasting state snapshot."""

    snapshot_id: str = ""
    total_signals: int = 0
    total_forecasts: int = 0
    total_scenarios: int = 0
    total_projections: int = 0
    total_recommendations: int = 0
    total_capacity_forecasts: int = 0
    total_budget_forecasts: int = 0
    total_risk_forecasts: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "total_forecasts", require_non_negative_int(self.total_forecasts, "total_forecasts"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_projections", require_non_negative_int(self.total_projections, "total_projections"))
        object.__setattr__(self, "total_recommendations", require_non_negative_int(self.total_recommendations, "total_recommendations"))
        object.__setattr__(self, "total_capacity_forecasts", require_non_negative_int(self.total_capacity_forecasts, "total_capacity_forecasts"))
        object.__setattr__(self, "total_budget_forecasts", require_non_negative_int(self.total_budget_forecasts, "total_budget_forecasts"))
        object.__setattr__(self, "total_risk_forecasts", require_non_negative_int(self.total_risk_forecasts, "total_risk_forecasts"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ForecastClosureReport(ContractRecord):
    """Summary report for forecasting lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_signals: int = 0
    total_forecasts: int = 0
    total_scenarios: int = 0
    total_recommendations_accepted: int = 0
    total_recommendations_rejected: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_signals", require_non_negative_int(self.total_signals, "total_signals"))
        object.__setattr__(self, "total_forecasts", require_non_negative_int(self.total_forecasts, "total_forecasts"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_recommendations_accepted", require_non_negative_int(self.total_recommendations_accepted, "total_recommendations_accepted"))
        object.__setattr__(self, "total_recommendations_rejected", require_non_negative_int(self.total_recommendations_rejected, "total_recommendations_rejected"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
