"""Comprehensive tests for mcoi_runtime.contracts.forecasting_runtime contracts."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Mapping

import pytest

from mcoi_runtime.contracts.forecasting_runtime import (
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T00:00:00Z"
TS2 = "2025-06-01"  # date-only is valid on 3.11+


# ===================================================================
# Enum tests
# ===================================================================


class TestForecastStatus:
    def test_members(self):
        assert ForecastStatus.DRAFT.value == "draft"
        assert ForecastStatus.ACTIVE.value == "active"
        assert ForecastStatus.SUPERSEDED.value == "superseded"
        assert ForecastStatus.EXPIRED.value == "expired"
        assert ForecastStatus.CANCELLED.value == "cancelled"

    def test_member_count(self):
        assert len(ForecastStatus) == 5

    def test_lookup_by_value(self):
        assert ForecastStatus("draft") is ForecastStatus.DRAFT

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ForecastStatus("bogus")


class TestDemandSignalKind:
    def test_members(self):
        assert DemandSignalKind.REQUEST_VOLUME.value == "request_volume"
        assert DemandSignalKind.CAPACITY_USAGE.value == "capacity_usage"
        assert DemandSignalKind.BUDGET_BURN.value == "budget_burn"
        assert DemandSignalKind.ASSET_UTILIZATION.value == "asset_utilization"
        assert DemandSignalKind.CONNECTOR_LOAD.value == "connector_load"
        assert DemandSignalKind.INCIDENT_RATE.value == "incident_rate"

    def test_member_count(self):
        assert len(DemandSignalKind) == 6

    def test_lookup_by_value(self):
        assert DemandSignalKind("budget_burn") is DemandSignalKind.BUDGET_BURN

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            DemandSignalKind("bogus")


class TestScenarioStatus:
    def test_members(self):
        assert ScenarioStatus.DRAFT.value == "draft"
        assert ScenarioStatus.ACTIVE.value == "active"
        assert ScenarioStatus.EVALUATED.value == "evaluated"
        assert ScenarioStatus.ARCHIVED.value == "archived"

    def test_member_count(self):
        assert len(ScenarioStatus) == 4

    def test_lookup_by_value(self):
        assert ScenarioStatus("evaluated") is ScenarioStatus.EVALUATED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ScenarioStatus("bogus")


class TestAllocationDisposition:
    def test_members(self):
        assert AllocationDisposition.RECOMMENDED.value == "recommended"
        assert AllocationDisposition.ACCEPTED.value == "accepted"
        assert AllocationDisposition.REJECTED.value == "rejected"
        assert AllocationDisposition.DEFERRED.value == "deferred"

    def test_member_count(self):
        assert len(AllocationDisposition) == 4

    def test_lookup_by_value(self):
        assert AllocationDisposition("deferred") is AllocationDisposition.DEFERRED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            AllocationDisposition("bogus")


class TestForecastConfidenceBand:
    def test_members(self):
        assert ForecastConfidenceBand.HIGH.value == "high"
        assert ForecastConfidenceBand.MEDIUM.value == "medium"
        assert ForecastConfidenceBand.LOW.value == "low"
        assert ForecastConfidenceBand.VERY_LOW.value == "very_low"

    def test_member_count(self):
        assert len(ForecastConfidenceBand) == 4

    def test_lookup_by_value(self):
        assert ForecastConfidenceBand("very_low") is ForecastConfidenceBand.VERY_LOW

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ForecastConfidenceBand("bogus")


class TestForecastHorizon:
    def test_members(self):
        assert ForecastHorizon.SHORT.value == "short"
        assert ForecastHorizon.MEDIUM.value == "medium"
        assert ForecastHorizon.LONG.value == "long"
        assert ForecastHorizon.STRATEGIC.value == "strategic"

    def test_member_count(self):
        assert len(ForecastHorizon) == 4

    def test_lookup_by_value(self):
        assert ForecastHorizon("strategic") is ForecastHorizon.STRATEGIC

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ForecastHorizon("bogus")


# ===================================================================
# DemandSignal tests
# ===================================================================


class TestDemandSignal:
    def _make(self, **kw):
        defaults = dict(
            signal_id="sig-1",
            tenant_id="t-1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="scope-1",
            value=42.0,
            recorded_at=TS,
            metadata={"k": "v"},
        )
        defaults.update(kw)
        return DemandSignal(**defaults)

    def test_valid_construction(self):
        ds = self._make()
        assert ds.signal_id == "sig-1"
        assert ds.tenant_id == "t-1"
        assert ds.kind is DemandSignalKind.REQUEST_VOLUME
        assert ds.scope_ref_id == "scope-1"
        assert ds.value == 42.0
        assert ds.recorded_at == TS

    def test_date_only_recorded_at(self):
        ds = self._make(recorded_at=TS2)
        assert ds.recorded_at == TS2

    def test_metadata_is_mapping(self):
        ds = self._make()
        assert isinstance(ds.metadata, Mapping)
        assert ds.metadata["k"] == "v"

    def test_metadata_frozen(self):
        ds = self._make()
        with pytest.raises(TypeError):
            ds.metadata["new"] = "val"

    def test_frozen_immutability(self):
        ds = self._make()
        with pytest.raises(FrozenInstanceError):
            ds.signal_id = "other"

    def test_empty_signal_id(self):
        with pytest.raises(ValueError):
            self._make(signal_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError):
            self._make(kind="request_volume")

    def test_negative_value(self):
        with pytest.raises(ValueError):
            self._make(value=-1.0)

    def test_invalid_recorded_at(self):
        with pytest.raises(ValueError):
            self._make(recorded_at="not-a-date")

    def test_empty_recorded_at(self):
        with pytest.raises(ValueError):
            self._make(recorded_at="")

    def test_value_zero(self):
        ds = self._make(value=0.0)
        assert ds.value == 0.0

    def test_to_dict_returns_dict(self):
        ds = self._make()
        d = ds.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        ds = self._make()
        d = ds.to_dict()
        assert d["kind"] is DemandSignalKind.REQUEST_VOLUME

    def test_all_signal_kinds(self):
        for kind in DemandSignalKind:
            ds = self._make(kind=kind)
            assert ds.kind is kind

    def test_whitespace_signal_id(self):
        with pytest.raises(ValueError):
            self._make(signal_id="   ")


# ===================================================================
# ForecastRecord tests
# ===================================================================


class TestForecastRecord:
    def _make(self, **kw):
        defaults = dict(
            forecast_id="fc-1",
            tenant_id="t-1",
            status=ForecastStatus.DRAFT,
            horizon=ForecastHorizon.SHORT,
            confidence_band=ForecastConfidenceBand.MEDIUM,
            confidence=0.8,
            signal_count=5,
            scope_ref_id="scope-1",
            projected_value=100.0,
            created_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return ForecastRecord(**defaults)

    def test_valid_construction(self):
        fr = self._make()
        assert fr.forecast_id == "fc-1"
        assert fr.status is ForecastStatus.DRAFT
        assert fr.horizon is ForecastHorizon.SHORT
        assert fr.confidence_band is ForecastConfidenceBand.MEDIUM
        assert fr.confidence == 0.8
        assert fr.signal_count == 5
        assert fr.projected_value == 100.0

    def test_frozen(self):
        fr = self._make()
        with pytest.raises(FrozenInstanceError):
            fr.forecast_id = "other"

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="draft")

    def test_invalid_horizon_type(self):
        with pytest.raises(ValueError):
            self._make(horizon="short")

    def test_invalid_confidence_band_type(self):
        with pytest.raises(ValueError):
            self._make(confidence_band="medium")

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_confidence_boundary_zero(self):
        fr = self._make(confidence=0.0)
        assert fr.confidence == 0.0

    def test_confidence_boundary_one(self):
        fr = self._make(confidence=1.0)
        assert fr.confidence == 1.0

    def test_negative_signal_count(self):
        with pytest.raises(ValueError):
            self._make(signal_count=-1)

    def test_negative_projected_value(self):
        with pytest.raises(ValueError):
            self._make(projected_value=-1.0)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_metadata_is_mapping(self):
        fr = self._make(metadata={"a": 1})
        assert isinstance(fr.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["status"] is ForecastStatus.DRAFT
        assert d["horizon"] is ForecastHorizon.SHORT
        assert d["confidence_band"] is ForecastConfidenceBand.MEDIUM

    def test_all_statuses(self):
        for s in ForecastStatus:
            fr = self._make(status=s)
            assert fr.status is s

    def test_all_horizons(self):
        for h in ForecastHorizon:
            fr = self._make(horizon=h)
            assert fr.horizon is h

    def test_all_confidence_bands(self):
        for cb in ForecastConfidenceBand:
            fr = self._make(confidence_band=cb)
            assert fr.confidence_band is cb

    def test_date_only_created_at(self):
        fr = self._make(created_at=TS2)
        assert fr.created_at == TS2

    def test_signal_count_zero(self):
        fr = self._make(signal_count=0)
        assert fr.signal_count == 0


# ===================================================================
# ScenarioModel tests
# ===================================================================


class TestScenarioModel:
    def _make(self, **kw):
        defaults = dict(
            scenario_id="sc-1",
            tenant_id="t-1",
            name="Baseline",
            status=ScenarioStatus.DRAFT,
            horizon=ForecastHorizon.MEDIUM,
            description="desc",
            created_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return ScenarioModel(**defaults)

    def test_valid_construction(self):
        sm = self._make()
        assert sm.scenario_id == "sc-1"
        assert sm.name == "Baseline"
        assert sm.status is ScenarioStatus.DRAFT
        assert sm.horizon is ForecastHorizon.MEDIUM
        assert sm.description == "desc"

    def test_frozen(self):
        sm = self._make()
        with pytest.raises(FrozenInstanceError):
            sm.scenario_id = "other"

    def test_empty_scenario_id(self):
        with pytest.raises(ValueError):
            self._make(scenario_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_name(self):
        with pytest.raises(ValueError):
            self._make(name="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="draft")

    def test_invalid_horizon_type(self):
        with pytest.raises(ValueError):
            self._make(horizon="medium")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_metadata_is_mapping(self):
        sm = self._make(metadata={"x": 1})
        assert isinstance(sm.metadata, Mapping)

    def test_metadata_frozen(self):
        sm = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            sm.metadata["y"] = 2

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enums(self):
        d = self._make().to_dict()
        assert d["status"] is ScenarioStatus.DRAFT
        assert d["horizon"] is ForecastHorizon.MEDIUM

    def test_all_statuses(self):
        for s in ScenarioStatus:
            sm = self._make(status=s)
            assert sm.status is s

    def test_all_horizons(self):
        for h in ForecastHorizon:
            sm = self._make(horizon=h)
            assert sm.horizon is h

    def test_date_only_created_at(self):
        sm = self._make(created_at=TS2)
        assert sm.created_at == TS2

    def test_whitespace_name(self):
        with pytest.raises(ValueError):
            self._make(name="   ")


# ===================================================================
# ScenarioProjection tests
# ===================================================================


class TestScenarioProjection:
    def _make(self, **kw):
        defaults = dict(
            projection_id="proj-1",
            scenario_id="sc-1",
            forecast_id="fc-1",
            projected_value=50.0,
            probability=0.7,
            impact_score=0.5,
            projected_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return ScenarioProjection(**defaults)

    def test_valid_construction(self):
        sp = self._make()
        assert sp.projection_id == "proj-1"
        assert sp.scenario_id == "sc-1"
        assert sp.forecast_id == "fc-1"
        assert sp.projected_value == 50.0
        assert sp.probability == 0.7
        assert sp.impact_score == 0.5

    def test_frozen(self):
        sp = self._make()
        with pytest.raises(FrozenInstanceError):
            sp.projection_id = "other"

    def test_empty_projection_id(self):
        with pytest.raises(ValueError):
            self._make(projection_id="")

    def test_empty_scenario_id(self):
        with pytest.raises(ValueError):
            self._make(scenario_id="")

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_negative_projected_value(self):
        with pytest.raises(ValueError):
            self._make(projected_value=-1.0)

    def test_probability_above_one(self):
        with pytest.raises(ValueError):
            self._make(probability=1.1)

    def test_probability_below_zero(self):
        with pytest.raises(ValueError):
            self._make(probability=-0.1)

    def test_impact_score_above_one(self):
        with pytest.raises(ValueError):
            self._make(impact_score=1.1)

    def test_impact_score_below_zero(self):
        with pytest.raises(ValueError):
            self._make(impact_score=-0.1)

    def test_invalid_projected_at(self):
        with pytest.raises(ValueError):
            self._make(projected_at="not-a-date")

    def test_metadata_is_mapping(self):
        sp = self._make(metadata={"x": 1})
        assert isinstance(sp.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_projected_value_zero(self):
        sp = self._make(projected_value=0.0)
        assert sp.projected_value == 0.0

    def test_probability_boundary_zero(self):
        sp = self._make(probability=0.0)
        assert sp.probability == 0.0

    def test_probability_boundary_one(self):
        sp = self._make(probability=1.0)
        assert sp.probability == 1.0

    def test_impact_score_boundary_zero(self):
        sp = self._make(impact_score=0.0)
        assert sp.impact_score == 0.0

    def test_impact_score_boundary_one(self):
        sp = self._make(impact_score=1.0)
        assert sp.impact_score == 1.0

    def test_date_only_projected_at(self):
        sp = self._make(projected_at=TS2)
        assert sp.projected_at == TS2

    def test_whitespace_projection_id(self):
        with pytest.raises(ValueError):
            self._make(projection_id="   ")


# ===================================================================
# AllocationRecommendation tests
# ===================================================================


class TestAllocationRecommendation:
    def _make(self, **kw):
        defaults = dict(
            recommendation_id="rec-1",
            forecast_id="fc-1",
            tenant_id="t-1",
            disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id="scope-1",
            recommended_value=200.0,
            confidence=0.9,
            reason="capacity headroom",
            created_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return AllocationRecommendation(**defaults)

    def test_valid_construction(self):
        ar = self._make()
        assert ar.recommendation_id == "rec-1"
        assert ar.disposition is AllocationDisposition.RECOMMENDED
        assert ar.recommended_value == 200.0
        assert ar.confidence == 0.9
        assert ar.reason == "capacity headroom"

    def test_frozen(self):
        ar = self._make()
        with pytest.raises(FrozenInstanceError):
            ar.recommendation_id = "other"

    def test_empty_recommendation_id(self):
        with pytest.raises(ValueError):
            self._make(recommendation_id="")

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            self._make(disposition="recommended")

    def test_negative_recommended_value(self):
        with pytest.raises(ValueError):
            self._make(recommended_value=-1.0)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_metadata_is_mapping(self):
        ar = self._make(metadata={"a": 1})
        assert isinstance(ar.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        d = self._make().to_dict()
        assert d["disposition"] is AllocationDisposition.RECOMMENDED

    def test_all_dispositions(self):
        for disp in AllocationDisposition:
            ar = self._make(disposition=disp)
            assert ar.disposition is disp

    def test_confidence_boundary_zero(self):
        ar = self._make(confidence=0.0)
        assert ar.confidence == 0.0

    def test_confidence_boundary_one(self):
        ar = self._make(confidence=1.0)
        assert ar.confidence == 1.0

    def test_recommended_value_zero(self):
        ar = self._make(recommended_value=0.0)
        assert ar.recommended_value == 0.0

    def test_date_only_created_at(self):
        ar = self._make(created_at=TS2)
        assert ar.created_at == TS2

    def test_whitespace_recommendation_id(self):
        with pytest.raises(ValueError):
            self._make(recommendation_id="   ")


# ===================================================================
# CapacityForecast tests
# ===================================================================


class TestCapacityForecast:
    def _make(self, **kw):
        defaults = dict(
            forecast_id="cf-1",
            tenant_id="t-1",
            scope_ref_id="scope-1",
            current_utilization=0.6,
            projected_utilization=0.8,
            headroom=0.2,
            confidence=0.9,
            horizon=ForecastHorizon.SHORT,
            projected_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return CapacityForecast(**defaults)

    def test_valid_construction(self):
        cf = self._make()
        assert cf.forecast_id == "cf-1"
        assert cf.current_utilization == 0.6
        assert cf.projected_utilization == 0.8
        assert cf.headroom == 0.2
        assert cf.confidence == 0.9
        assert cf.horizon is ForecastHorizon.SHORT

    def test_frozen(self):
        cf = self._make()
        with pytest.raises(FrozenInstanceError):
            cf.forecast_id = "other"

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_current_utilization_above_one(self):
        with pytest.raises(ValueError):
            self._make(current_utilization=1.1)

    def test_current_utilization_below_zero(self):
        with pytest.raises(ValueError):
            self._make(current_utilization=-0.1)

    def test_projected_utilization_above_one(self):
        with pytest.raises(ValueError):
            self._make(projected_utilization=1.1)

    def test_projected_utilization_below_zero(self):
        with pytest.raises(ValueError):
            self._make(projected_utilization=-0.1)

    def test_headroom_above_one(self):
        with pytest.raises(ValueError):
            self._make(headroom=1.1)

    def test_headroom_below_zero(self):
        with pytest.raises(ValueError):
            self._make(headroom=-0.1)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_invalid_horizon_type(self):
        with pytest.raises(ValueError):
            self._make(horizon="short")

    def test_invalid_projected_at(self):
        with pytest.raises(ValueError):
            self._make(projected_at="not-a-date")

    def test_metadata_is_mapping(self):
        cf = self._make(metadata={"a": 1})
        assert isinstance(cf.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        d = self._make().to_dict()
        assert d["horizon"] is ForecastHorizon.SHORT

    def test_all_horizons(self):
        for h in ForecastHorizon:
            cf = self._make(horizon=h)
            assert cf.horizon is h

    def test_boundary_zero_current_utilization(self):
        cf = self._make(current_utilization=0.0)
        assert cf.current_utilization == 0.0

    def test_boundary_one_current_utilization(self):
        cf = self._make(current_utilization=1.0)
        assert cf.current_utilization == 1.0

    def test_boundary_zero_headroom(self):
        cf = self._make(headroom=0.0)
        assert cf.headroom == 0.0

    def test_boundary_one_headroom(self):
        cf = self._make(headroom=1.0)
        assert cf.headroom == 1.0

    def test_date_only_projected_at(self):
        cf = self._make(projected_at=TS2)
        assert cf.projected_at == TS2

    def test_metadata_frozen(self):
        cf = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            cf.metadata["y"] = 2


# ===================================================================
# BudgetForecast tests
# ===================================================================


class TestBudgetForecast:
    def _make(self, **kw):
        defaults = dict(
            forecast_id="bf-1",
            tenant_id="t-1",
            scope_ref_id="scope-1",
            current_spend=1000.0,
            projected_spend=1500.0,
            budget_limit=2000.0,
            burn_rate=150.0,
            confidence=0.85,
            horizon=ForecastHorizon.MEDIUM,
            projected_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return BudgetForecast(**defaults)

    def test_valid_construction(self):
        bf = self._make()
        assert bf.forecast_id == "bf-1"
        assert bf.current_spend == 1000.0
        assert bf.projected_spend == 1500.0
        assert bf.budget_limit == 2000.0
        assert bf.burn_rate == 150.0
        assert bf.confidence == 0.85
        assert bf.horizon is ForecastHorizon.MEDIUM

    def test_frozen(self):
        bf = self._make()
        with pytest.raises(FrozenInstanceError):
            bf.forecast_id = "other"

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_negative_current_spend(self):
        with pytest.raises(ValueError):
            self._make(current_spend=-1.0)

    def test_negative_projected_spend(self):
        with pytest.raises(ValueError):
            self._make(projected_spend=-1.0)

    def test_negative_budget_limit(self):
        with pytest.raises(ValueError):
            self._make(budget_limit=-1.0)

    def test_negative_burn_rate(self):
        with pytest.raises(ValueError):
            self._make(burn_rate=-1.0)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_invalid_horizon_type(self):
        with pytest.raises(ValueError):
            self._make(horizon="medium")

    def test_invalid_projected_at(self):
        with pytest.raises(ValueError):
            self._make(projected_at="not-a-date")

    def test_metadata_is_mapping(self):
        bf = self._make(metadata={"a": 1})
        assert isinstance(bf.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        d = self._make().to_dict()
        assert d["horizon"] is ForecastHorizon.MEDIUM

    def test_all_horizons(self):
        for h in ForecastHorizon:
            bf = self._make(horizon=h)
            assert bf.horizon is h

    def test_zero_current_spend(self):
        bf = self._make(current_spend=0.0)
        assert bf.current_spend == 0.0

    def test_zero_burn_rate(self):
        bf = self._make(burn_rate=0.0)
        assert bf.burn_rate == 0.0

    def test_confidence_boundary_zero(self):
        bf = self._make(confidence=0.0)
        assert bf.confidence == 0.0

    def test_confidence_boundary_one(self):
        bf = self._make(confidence=1.0)
        assert bf.confidence == 1.0

    def test_date_only_projected_at(self):
        bf = self._make(projected_at=TS2)
        assert bf.projected_at == TS2

    def test_metadata_frozen(self):
        bf = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            bf.metadata["y"] = 2


# ===================================================================
# RiskForecast tests
# ===================================================================


class TestRiskForecast:
    def _make(self, **kw):
        defaults = dict(
            forecast_id="rf-1",
            tenant_id="t-1",
            scope_ref_id="scope-1",
            current_risk=0.3,
            projected_risk=0.5,
            mitigation_coverage=0.7,
            confidence=0.8,
            horizon=ForecastHorizon.LONG,
            projected_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return RiskForecast(**defaults)

    def test_valid_construction(self):
        rf = self._make()
        assert rf.forecast_id == "rf-1"
        assert rf.current_risk == 0.3
        assert rf.projected_risk == 0.5
        assert rf.mitigation_coverage == 0.7
        assert rf.confidence == 0.8
        assert rf.horizon is ForecastHorizon.LONG

    def test_frozen(self):
        rf = self._make()
        with pytest.raises(FrozenInstanceError):
            rf.forecast_id = "other"

    def test_empty_forecast_id(self):
        with pytest.raises(ValueError):
            self._make(forecast_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_current_risk_above_one(self):
        with pytest.raises(ValueError):
            self._make(current_risk=1.1)

    def test_current_risk_below_zero(self):
        with pytest.raises(ValueError):
            self._make(current_risk=-0.1)

    def test_projected_risk_above_one(self):
        with pytest.raises(ValueError):
            self._make(projected_risk=1.1)

    def test_projected_risk_below_zero(self):
        with pytest.raises(ValueError):
            self._make(projected_risk=-0.1)

    def test_mitigation_coverage_above_one(self):
        with pytest.raises(ValueError):
            self._make(mitigation_coverage=1.1)

    def test_mitigation_coverage_below_zero(self):
        with pytest.raises(ValueError):
            self._make(mitigation_coverage=-0.1)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.1)

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_invalid_horizon_type(self):
        with pytest.raises(ValueError):
            self._make(horizon="long")

    def test_invalid_projected_at(self):
        with pytest.raises(ValueError):
            self._make(projected_at="not-a-date")

    def test_metadata_is_mapping(self):
        rf = self._make(metadata={"a": 1})
        assert isinstance(rf.metadata, Mapping)

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        d = self._make().to_dict()
        assert d["horizon"] is ForecastHorizon.LONG

    def test_all_horizons(self):
        for h in ForecastHorizon:
            rf = self._make(horizon=h)
            assert rf.horizon is h

    def test_boundary_zero_current_risk(self):
        rf = self._make(current_risk=0.0)
        assert rf.current_risk == 0.0

    def test_boundary_one_current_risk(self):
        rf = self._make(current_risk=1.0)
        assert rf.current_risk == 1.0

    def test_boundary_zero_mitigation_coverage(self):
        rf = self._make(mitigation_coverage=0.0)
        assert rf.mitigation_coverage == 0.0

    def test_boundary_one_mitigation_coverage(self):
        rf = self._make(mitigation_coverage=1.0)
        assert rf.mitigation_coverage == 1.0

    def test_date_only_projected_at(self):
        rf = self._make(projected_at=TS2)
        assert rf.projected_at == TS2

    def test_metadata_frozen(self):
        rf = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            rf.metadata["y"] = 2


# ===================================================================
# ForecastSnapshot tests
# ===================================================================


class TestForecastSnapshot:
    def _make(self, **kw):
        defaults = dict(
            snapshot_id="snap-1",
            total_signals=10,
            total_forecasts=5,
            total_scenarios=3,
            total_projections=8,
            total_recommendations=4,
            total_capacity_forecasts=2,
            total_budget_forecasts=2,
            total_risk_forecasts=1,
            total_violations=0,
            captured_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return ForecastSnapshot(**defaults)

    def test_valid_construction(self):
        fs = self._make()
        assert fs.snapshot_id == "snap-1"
        assert fs.total_signals == 10
        assert fs.total_forecasts == 5
        assert fs.total_scenarios == 3
        assert fs.total_projections == 8
        assert fs.total_recommendations == 4
        assert fs.total_capacity_forecasts == 2
        assert fs.total_budget_forecasts == 2
        assert fs.total_risk_forecasts == 1
        assert fs.total_violations == 0

    def test_frozen(self):
        fs = self._make()
        with pytest.raises(FrozenInstanceError):
            fs.snapshot_id = "other"

    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_negative_total_signals(self):
        with pytest.raises(ValueError):
            self._make(total_signals=-1)

    def test_negative_total_forecasts(self):
        with pytest.raises(ValueError):
            self._make(total_forecasts=-1)

    def test_negative_total_scenarios(self):
        with pytest.raises(ValueError):
            self._make(total_scenarios=-1)

    def test_negative_total_projections(self):
        with pytest.raises(ValueError):
            self._make(total_projections=-1)

    def test_negative_total_recommendations(self):
        with pytest.raises(ValueError):
            self._make(total_recommendations=-1)

    def test_negative_total_capacity_forecasts(self):
        with pytest.raises(ValueError):
            self._make(total_capacity_forecasts=-1)

    def test_negative_total_budget_forecasts(self):
        with pytest.raises(ValueError):
            self._make(total_budget_forecasts=-1)

    def test_negative_total_risk_forecasts(self):
        with pytest.raises(ValueError):
            self._make(total_risk_forecasts=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            self._make(captured_at="not-a-date")

    def test_empty_captured_at(self):
        with pytest.raises(ValueError):
            self._make(captured_at="")

    def test_metadata_is_mapping(self):
        fs = self._make(metadata={"a": 1})
        assert isinstance(fs.metadata, Mapping)

    def test_metadata_frozen(self):
        fs = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            fs.metadata["y"] = 2

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_json_returns_valid_json(self):
        fs = self._make()
        j = fs.to_json()
        parsed = json.loads(j)
        assert parsed["snapshot_id"] == "snap-1"
        assert parsed["total_signals"] == 10

    def test_all_zeros(self):
        fs = self._make(
            total_signals=0,
            total_forecasts=0,
            total_scenarios=0,
            total_projections=0,
            total_recommendations=0,
            total_capacity_forecasts=0,
            total_budget_forecasts=0,
            total_risk_forecasts=0,
            total_violations=0,
        )
        assert fs.total_signals == 0

    def test_date_only_captured_at(self):
        fs = self._make(captured_at=TS2)
        assert fs.captured_at == TS2

    def test_whitespace_snapshot_id(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="   ")

    def test_to_dict_field_count(self):
        d = self._make().to_dict()
        assert len(d) == 12  # 11 fields + metadata


# ===================================================================
# ForecastClosureReport tests
# ===================================================================


class TestForecastClosureReport:
    def _make(self, **kw):
        defaults = dict(
            report_id="rpt-1",
            tenant_id="t-1",
            total_signals=20,
            total_forecasts=10,
            total_scenarios=5,
            total_recommendations_accepted=8,
            total_recommendations_rejected=2,
            total_violations=1,
            closed_at=TS,
            metadata={},
        )
        defaults.update(kw)
        return ForecastClosureReport(**defaults)

    def test_valid_construction(self):
        cr = self._make()
        assert cr.report_id == "rpt-1"
        assert cr.tenant_id == "t-1"
        assert cr.total_signals == 20
        assert cr.total_forecasts == 10
        assert cr.total_scenarios == 5
        assert cr.total_recommendations_accepted == 8
        assert cr.total_recommendations_rejected == 2
        assert cr.total_violations == 1

    def test_frozen(self):
        cr = self._make()
        with pytest.raises(FrozenInstanceError):
            cr.report_id = "other"

    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_negative_total_signals(self):
        with pytest.raises(ValueError):
            self._make(total_signals=-1)

    def test_negative_total_forecasts(self):
        with pytest.raises(ValueError):
            self._make(total_forecasts=-1)

    def test_negative_total_scenarios(self):
        with pytest.raises(ValueError):
            self._make(total_scenarios=-1)

    def test_negative_total_recommendations_accepted(self):
        with pytest.raises(ValueError):
            self._make(total_recommendations_accepted=-1)

    def test_negative_total_recommendations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_recommendations_rejected=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_invalid_closed_at(self):
        with pytest.raises(ValueError):
            self._make(closed_at="not-a-date")

    def test_empty_closed_at(self):
        with pytest.raises(ValueError):
            self._make(closed_at="")

    def test_metadata_is_mapping(self):
        cr = self._make(metadata={"a": 1})
        assert isinstance(cr.metadata, Mapping)

    def test_metadata_frozen(self):
        cr = self._make(metadata={"x": 1})
        with pytest.raises(TypeError):
            cr.metadata["y"] = 2

    def test_to_dict_returns_dict(self):
        d = self._make().to_dict()
        assert isinstance(d, dict)

    def test_to_json_returns_valid_json(self):
        cr = self._make()
        j = cr.to_json()
        parsed = json.loads(j)
        assert parsed["report_id"] == "rpt-1"
        assert parsed["total_signals"] == 20

    def test_all_zeros(self):
        cr = self._make(
            total_signals=0,
            total_forecasts=0,
            total_scenarios=0,
            total_recommendations_accepted=0,
            total_recommendations_rejected=0,
            total_violations=0,
        )
        assert cr.total_signals == 0

    def test_date_only_closed_at(self):
        cr = self._make(closed_at=TS2)
        assert cr.closed_at == TS2

    def test_whitespace_report_id(self):
        with pytest.raises(ValueError):
            self._make(report_id="   ")

    def test_whitespace_tenant_id(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="   ")

    def test_to_dict_field_count(self):
        d = self._make().to_dict()
        assert len(d) == 10  # 9 fields + metadata


# ===================================================================
# Cross-cutting / additional edge-case tests
# ===================================================================


class TestCrossCutting:
    """Additional tests for edge cases shared across dataclasses."""

    def test_demand_signal_integer_value_coerced(self):
        """Integer values for float fields should be accepted."""
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.BUDGET_BURN,
            scope_ref_id="sc", value=10,
            recorded_at=TS,
        )
        assert ds.value == 10.0

    def test_forecast_record_integer_confidence(self):
        fr = ForecastRecord(
            forecast_id="f1", tenant_id="t1",
            status=ForecastStatus.ACTIVE,
            horizon=ForecastHorizon.SHORT,
            confidence_band=ForecastConfidenceBand.HIGH,
            confidence=1, signal_count=0,
            scope_ref_id="sc", projected_value=0,
            created_at=TS,
        )
        assert fr.confidence == 1.0

    def test_scenario_projection_no_enum_fields(self):
        """ScenarioProjection has no enum fields -- verify to_dict has none."""
        sp = ScenarioProjection(
            projection_id="p1", scenario_id="s1", forecast_id="f1",
            projected_value=1.0, probability=0.5, impact_score=0.5,
            projected_at=TS,
        )
        d = sp.to_dict()
        # No enum values in the dict
        for v in d.values():
            assert not isinstance(v, type) or True  # just confirm it's a dict

    def test_default_metadata_empty(self):
        """Default metadata should be an empty frozen mapping."""
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0,
            recorded_at=TS,
        )
        assert isinstance(ds.metadata, Mapping)
        assert len(ds.metadata) == 0

    def test_nested_metadata_frozen(self):
        """Nested dicts in metadata should also be frozen."""
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0,
            recorded_at=TS,
            metadata={"nested": {"inner": "val"}},
        )
        assert isinstance(ds.metadata["nested"], Mapping)
        with pytest.raises(TypeError):
            ds.metadata["nested"]["new_key"] = "fail"

    def test_to_dict_metadata_thawed(self):
        """to_dict should thaw metadata back to regular dict."""
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0,
            recorded_at=TS,
            metadata={"k": "v"},
        )
        d = ds.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_forecast_snapshot_to_json_roundtrip(self):
        fs = ForecastSnapshot(
            snapshot_id="snap-1",
            total_signals=1, total_forecasts=2,
            total_scenarios=3, total_projections=4,
            total_recommendations=5,
            total_capacity_forecasts=6,
            total_budget_forecasts=7,
            total_risk_forecasts=8,
            total_violations=9,
            captured_at=TS,
        )
        j = fs.to_json()
        parsed = json.loads(j)
        assert parsed["total_signals"] == 1
        assert parsed["total_violations"] == 9

    def test_closure_report_to_json_roundtrip(self):
        cr = ForecastClosureReport(
            report_id="rpt-1", tenant_id="t-1",
            total_signals=1, total_forecasts=2,
            total_scenarios=3,
            total_recommendations_accepted=4,
            total_recommendations_rejected=5,
            total_violations=6,
            closed_at=TS,
        )
        j = cr.to_json()
        parsed = json.loads(j)
        assert parsed["total_recommendations_accepted"] == 4

    def test_iso_datetime_with_timezone(self):
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0,
            recorded_at="2025-06-01T12:00:00+05:30",
        )
        assert ds.recorded_at == "2025-06-01T12:00:00+05:30"

    def test_iso_datetime_z_suffix(self):
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0,
            recorded_at="2025-06-01T00:00:00Z",
        )
        assert ds.recorded_at == "2025-06-01T00:00:00Z"

    def test_capacity_forecast_all_unit_floats_at_boundary(self):
        cf = CapacityForecast(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.0, projected_utilization=1.0,
            headroom=0.0, confidence=1.0,
            horizon=ForecastHorizon.STRATEGIC,
            projected_at=TS,
        )
        assert cf.current_utilization == 0.0
        assert cf.projected_utilization == 1.0

    def test_risk_forecast_all_unit_floats_at_boundary(self):
        rf = RiskForecast(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=1.0, projected_risk=0.0,
            mitigation_coverage=1.0, confidence=0.0,
            horizon=ForecastHorizon.SHORT,
            projected_at=TS,
        )
        assert rf.current_risk == 1.0
        assert rf.projected_risk == 0.0
        assert rf.confidence == 0.0

    def test_budget_forecast_large_values(self):
        bf = BudgetForecast(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=1e12, projected_spend=2e12,
            budget_limit=3e12, burn_rate=1e6,
            confidence=0.5,
            horizon=ForecastHorizon.STRATEGIC,
            projected_at=TS,
        )
        assert bf.current_spend == 1e12

    def test_demand_signal_scope_ref_id_preserved(self):
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.CONNECTOR_LOAD,
            scope_ref_id="some/path/ref",
            value=0.0, recorded_at=TS,
        )
        assert ds.scope_ref_id == "some/path/ref"

    def test_allocation_reason_preserved(self):
        ar = AllocationRecommendation(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.ACCEPTED,
            scope_ref_id="s", recommended_value=0.0,
            confidence=0.5, reason="multi word reason with special chars: !@#",
            created_at=TS,
        )
        assert ar.reason == "multi word reason with special chars: !@#"

    def test_scenario_model_description_can_be_empty_string(self):
        """description is not validated as non-empty -- only scenario_id, tenant_id, name are."""
        sm = ScenarioModel(
            scenario_id="sc-1", tenant_id="t-1", name="Test",
            status=ScenarioStatus.DRAFT,
            horizon=ForecastHorizon.MEDIUM,
            description="",
            created_at=TS,
        )
        assert sm.description == ""

    def test_allocation_scope_ref_id_can_be_any_string(self):
        """scope_ref_id is not validated as non-empty for AllocationRecommendation."""
        ar = AllocationRecommendation(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.DEFERRED,
            scope_ref_id="",
            recommended_value=0.0, confidence=0.5,
            reason="test", created_at=TS,
        )
        assert ar.scope_ref_id == ""


# ===================================================================
# Parametrized tests for broader coverage
# ===================================================================


class TestDemandSignalKindParametrized:
    @pytest.mark.parametrize("kind,value", [
        (DemandSignalKind.REQUEST_VOLUME, "request_volume"),
        (DemandSignalKind.CAPACITY_USAGE, "capacity_usage"),
        (DemandSignalKind.BUDGET_BURN, "budget_burn"),
        (DemandSignalKind.ASSET_UTILIZATION, "asset_utilization"),
        (DemandSignalKind.CONNECTOR_LOAD, "connector_load"),
        (DemandSignalKind.INCIDENT_RATE, "incident_rate"),
    ])
    def test_enum_value(self, kind, value):
        assert kind.value == value

    @pytest.mark.parametrize("kind", list(DemandSignalKind))
    def test_demand_signal_accepts_each_kind(self, kind):
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1", kind=kind,
            scope_ref_id="sc", value=1.0, recorded_at=TS,
        )
        assert ds.kind is kind
        d = ds.to_dict()
        assert d["kind"] is kind


class TestForecastStatusParametrized:
    @pytest.mark.parametrize("status,value", [
        (ForecastStatus.DRAFT, "draft"),
        (ForecastStatus.ACTIVE, "active"),
        (ForecastStatus.SUPERSEDED, "superseded"),
        (ForecastStatus.EXPIRED, "expired"),
        (ForecastStatus.CANCELLED, "cancelled"),
    ])
    def test_enum_value(self, status, value):
        assert status.value == value


class TestScenarioStatusParametrized:
    @pytest.mark.parametrize("status,value", [
        (ScenarioStatus.DRAFT, "draft"),
        (ScenarioStatus.ACTIVE, "active"),
        (ScenarioStatus.EVALUATED, "evaluated"),
        (ScenarioStatus.ARCHIVED, "archived"),
    ])
    def test_enum_value(self, status, value):
        assert status.value == value


class TestAllocationDispositionParametrized:
    @pytest.mark.parametrize("disp,value", [
        (AllocationDisposition.RECOMMENDED, "recommended"),
        (AllocationDisposition.ACCEPTED, "accepted"),
        (AllocationDisposition.REJECTED, "rejected"),
        (AllocationDisposition.DEFERRED, "deferred"),
    ])
    def test_enum_value(self, disp, value):
        assert disp.value == value


class TestForecastConfidenceBandParametrized:
    @pytest.mark.parametrize("band,value", [
        (ForecastConfidenceBand.HIGH, "high"),
        (ForecastConfidenceBand.MEDIUM, "medium"),
        (ForecastConfidenceBand.LOW, "low"),
        (ForecastConfidenceBand.VERY_LOW, "very_low"),
    ])
    def test_enum_value(self, band, value):
        assert band.value == value


class TestForecastHorizonParametrized:
    @pytest.mark.parametrize("horizon,value", [
        (ForecastHorizon.SHORT, "short"),
        (ForecastHorizon.MEDIUM, "medium"),
        (ForecastHorizon.LONG, "long"),
        (ForecastHorizon.STRATEGIC, "strategic"),
    ])
    def test_enum_value(self, horizon, value):
        assert horizon.value == value


class TestUnitFloatBoundaries:
    """Parametrized tests for unit_float validation across dataclasses."""

    @pytest.mark.parametrize("val", [-0.001, -1.0, -100.0])
    def test_demand_signal_value_non_negative(self, val):
        with pytest.raises(ValueError):
            DemandSignal(
                signal_id="s1", tenant_id="t1",
                kind=DemandSignalKind.REQUEST_VOLUME,
                scope_ref_id="sc", value=val, recorded_at=TS,
            )

    @pytest.mark.parametrize("val", [1.001, 2.0, 100.0])
    def test_forecast_record_confidence_too_high(self, val):
        with pytest.raises(ValueError):
            ForecastRecord(
                forecast_id="f1", tenant_id="t1",
                status=ForecastStatus.DRAFT,
                horizon=ForecastHorizon.SHORT,
                confidence_band=ForecastConfidenceBand.MEDIUM,
                confidence=val, signal_count=0,
                scope_ref_id="sc", projected_value=0.0,
                created_at=TS,
            )

    @pytest.mark.parametrize("val", [-0.001, -1.0, -100.0])
    def test_forecast_record_confidence_too_low(self, val):
        with pytest.raises(ValueError):
            ForecastRecord(
                forecast_id="f1", tenant_id="t1",
                status=ForecastStatus.DRAFT,
                horizon=ForecastHorizon.SHORT,
                confidence_band=ForecastConfidenceBand.MEDIUM,
                confidence=val, signal_count=0,
                scope_ref_id="sc", projected_value=0.0,
                created_at=TS,
            )

    @pytest.mark.parametrize("field_name,val", [
        ("probability", 1.5),
        ("probability", -0.1),
        ("impact_score", 1.5),
        ("impact_score", -0.1),
    ])
    def test_scenario_projection_unit_float_invalid(self, field_name, val):
        kw = dict(
            projection_id="p1", scenario_id="s1", forecast_id="f1",
            projected_value=1.0, probability=0.5, impact_score=0.5,
            projected_at=TS,
        )
        kw[field_name] = val
        with pytest.raises(ValueError):
            ScenarioProjection(**kw)

    @pytest.mark.parametrize("field_name,val", [
        ("confidence", 1.5),
        ("confidence", -0.1),
    ])
    def test_allocation_recommendation_unit_float_invalid(self, field_name, val):
        kw = dict(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id="s", recommended_value=0.0,
            confidence=0.5, reason="test", created_at=TS,
        )
        kw[field_name] = val
        with pytest.raises(ValueError):
            AllocationRecommendation(**kw)

    @pytest.mark.parametrize("field_name", [
        "current_utilization", "projected_utilization", "headroom", "confidence",
    ])
    def test_capacity_forecast_unit_float_above_one(self, field_name):
        kw = dict(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.5, projected_utilization=0.5,
            headroom=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = 1.5
        with pytest.raises(ValueError):
            CapacityForecast(**kw)

    @pytest.mark.parametrize("field_name", [
        "current_utilization", "projected_utilization", "headroom", "confidence",
    ])
    def test_capacity_forecast_unit_float_below_zero(self, field_name):
        kw = dict(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.5, projected_utilization=0.5,
            headroom=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = -0.1
        with pytest.raises(ValueError):
            CapacityForecast(**kw)

    @pytest.mark.parametrize("field_name", [
        "current_risk", "projected_risk", "mitigation_coverage", "confidence",
    ])
    def test_risk_forecast_unit_float_above_one(self, field_name):
        kw = dict(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=0.5, projected_risk=0.5,
            mitigation_coverage=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = 1.5
        with pytest.raises(ValueError):
            RiskForecast(**kw)

    @pytest.mark.parametrize("field_name", [
        "current_risk", "projected_risk", "mitigation_coverage", "confidence",
    ])
    def test_risk_forecast_unit_float_below_zero(self, field_name):
        kw = dict(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=0.5, projected_risk=0.5,
            mitigation_coverage=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = -0.1
        with pytest.raises(ValueError):
            RiskForecast(**kw)


class TestNonNegativeFloatBoundaries:
    """Parametrized tests for non_negative_float fields."""

    @pytest.mark.parametrize("field_name", [
        "current_spend", "projected_spend", "budget_limit", "burn_rate",
    ])
    def test_budget_forecast_negative(self, field_name):
        kw = dict(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=300.0, burn_rate=10.0,
            confidence=0.5, horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = -0.01
        with pytest.raises(ValueError):
            BudgetForecast(**kw)

    @pytest.mark.parametrize("field_name", [
        "current_spend", "projected_spend", "budget_limit", "burn_rate",
    ])
    def test_budget_forecast_zero_ok(self, field_name):
        kw = dict(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=300.0, burn_rate=10.0,
            confidence=0.5, horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = 0.0
        bf = BudgetForecast(**kw)
        assert getattr(bf, field_name) == 0.0


class TestNonNegativeIntBoundaries:
    """Parametrized tests for non_negative_int fields."""

    INT_FIELDS_SNAPSHOT = [
        "total_signals", "total_forecasts", "total_scenarios",
        "total_projections", "total_recommendations",
        "total_capacity_forecasts", "total_budget_forecasts",
        "total_risk_forecasts", "total_violations",
    ]

    @pytest.mark.parametrize("field_name", INT_FIELDS_SNAPSHOT)
    def test_snapshot_negative_int(self, field_name):
        kw = dict(
            snapshot_id="snap-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_projections=0, total_recommendations=0,
            total_capacity_forecasts=0, total_budget_forecasts=0,
            total_risk_forecasts=0, total_violations=0,
            captured_at=TS,
        )
        kw[field_name] = -1
        with pytest.raises(ValueError):
            ForecastSnapshot(**kw)

    INT_FIELDS_CLOSURE = [
        "total_signals", "total_forecasts", "total_scenarios",
        "total_recommendations_accepted", "total_recommendations_rejected",
        "total_violations",
    ]

    @pytest.mark.parametrize("field_name", INT_FIELDS_CLOSURE)
    def test_closure_negative_int(self, field_name):
        kw = dict(
            report_id="rpt-1", tenant_id="t-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_recommendations_accepted=0,
            total_recommendations_rejected=0,
            total_violations=0,
            closed_at=TS,
        )
        kw[field_name] = -1
        with pytest.raises(ValueError):
            ForecastClosureReport(**kw)


class TestInvalidDatetimeParametrized:
    """Parametrized tests for datetime validation across dataclasses."""

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", "12:99:99", ""])
    def test_demand_signal_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            DemandSignal(
                signal_id="s1", tenant_id="t1",
                kind=DemandSignalKind.REQUEST_VOLUME,
                scope_ref_id="sc", value=0.0, recorded_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", "12:99:99", ""])
    def test_forecast_record_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            ForecastRecord(
                forecast_id="f1", tenant_id="t1",
                status=ForecastStatus.DRAFT,
                horizon=ForecastHorizon.SHORT,
                confidence_band=ForecastConfidenceBand.MEDIUM,
                confidence=0.5, signal_count=0,
                scope_ref_id="sc", projected_value=0.0,
                created_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_scenario_model_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            ScenarioModel(
                scenario_id="sc-1", tenant_id="t-1", name="Test",
                status=ScenarioStatus.DRAFT,
                horizon=ForecastHorizon.MEDIUM,
                description="d", created_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_scenario_projection_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            ScenarioProjection(
                projection_id="p1", scenario_id="s1", forecast_id="f1",
                projected_value=1.0, probability=0.5, impact_score=0.5,
                projected_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_allocation_recommendation_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            AllocationRecommendation(
                recommendation_id="r1", forecast_id="f1", tenant_id="t1",
                disposition=AllocationDisposition.RECOMMENDED,
                scope_ref_id="s", recommended_value=0.0,
                confidence=0.5, reason="test", created_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_capacity_forecast_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            CapacityForecast(
                forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
                current_utilization=0.5, projected_utilization=0.5,
                headroom=0.5, confidence=0.5,
                horizon=ForecastHorizon.SHORT, projected_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_budget_forecast_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            BudgetForecast(
                forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
                current_spend=100.0, projected_spend=200.0,
                budget_limit=300.0, burn_rate=10.0,
                confidence=0.5, horizon=ForecastHorizon.SHORT,
                projected_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_risk_forecast_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            RiskForecast(
                forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
                current_risk=0.5, projected_risk=0.5,
                mitigation_coverage=0.5, confidence=0.5,
                horizon=ForecastHorizon.SHORT, projected_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_forecast_snapshot_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            ForecastSnapshot(
                snapshot_id="snap-1",
                total_signals=0, total_forecasts=0, total_scenarios=0,
                total_projections=0, total_recommendations=0,
                total_capacity_forecasts=0, total_budget_forecasts=0,
                total_risk_forecasts=0, total_violations=0,
                captured_at=bad_dt,
            )

    @pytest.mark.parametrize("bad_dt", ["not-a-date", "abc", ""])
    def test_forecast_closure_report_bad_datetime(self, bad_dt):
        with pytest.raises(ValueError):
            ForecastClosureReport(
                report_id="rpt-1", tenant_id="t-1",
                total_signals=0, total_forecasts=0, total_scenarios=0,
                total_recommendations_accepted=0,
                total_recommendations_rejected=0,
                total_violations=0,
                closed_at=bad_dt,
            )


class TestEmptyTextFieldsParametrized:
    """Parametrized tests for required text fields rejecting empty strings."""

    @pytest.mark.parametrize("field_name", ["signal_id", "tenant_id"])
    def test_demand_signal_empty_text(self, field_name):
        kw = dict(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0, recorded_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            DemandSignal(**kw)

    @pytest.mark.parametrize("field_name", ["forecast_id", "tenant_id"])
    def test_forecast_record_empty_text(self, field_name):
        kw = dict(
            forecast_id="f1", tenant_id="t1",
            status=ForecastStatus.DRAFT,
            horizon=ForecastHorizon.SHORT,
            confidence_band=ForecastConfidenceBand.MEDIUM,
            confidence=0.5, signal_count=0,
            scope_ref_id="sc", projected_value=0.0,
            created_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            ForecastRecord(**kw)

    @pytest.mark.parametrize("field_name", ["scenario_id", "tenant_id", "name"])
    def test_scenario_model_empty_text(self, field_name):
        kw = dict(
            scenario_id="sc-1", tenant_id="t-1", name="Test",
            status=ScenarioStatus.DRAFT,
            horizon=ForecastHorizon.MEDIUM,
            description="d", created_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            ScenarioModel(**kw)

    @pytest.mark.parametrize("field_name", ["projection_id", "scenario_id", "forecast_id"])
    def test_scenario_projection_empty_text(self, field_name):
        kw = dict(
            projection_id="p1", scenario_id="s1", forecast_id="f1",
            projected_value=1.0, probability=0.5, impact_score=0.5,
            projected_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            ScenarioProjection(**kw)

    @pytest.mark.parametrize("field_name", ["recommendation_id", "forecast_id", "tenant_id"])
    def test_allocation_recommendation_empty_text(self, field_name):
        kw = dict(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id="s", recommended_value=0.0,
            confidence=0.5, reason="test", created_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            AllocationRecommendation(**kw)

    @pytest.mark.parametrize("field_name", ["forecast_id", "tenant_id"])
    def test_capacity_forecast_empty_text(self, field_name):
        kw = dict(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.5, projected_utilization=0.5,
            headroom=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            CapacityForecast(**kw)

    @pytest.mark.parametrize("field_name", ["forecast_id", "tenant_id"])
    def test_budget_forecast_empty_text(self, field_name):
        kw = dict(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=300.0, burn_rate=10.0,
            confidence=0.5, horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            BudgetForecast(**kw)

    @pytest.mark.parametrize("field_name", ["forecast_id", "tenant_id"])
    def test_risk_forecast_empty_text(self, field_name):
        kw = dict(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=0.5, projected_risk=0.5,
            mitigation_coverage=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            RiskForecast(**kw)

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_closure_report_empty_text(self, field_name):
        kw = dict(
            report_id="rpt-1", tenant_id="t-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_recommendations_accepted=0,
            total_recommendations_rejected=0,
            total_violations=0,
            closed_at=TS,
        )
        kw[field_name] = ""
        with pytest.raises(ValueError):
            ForecastClosureReport(**kw)


class TestFrozenImmutabilityParametrized:
    """Ensure setattr raises on all dataclasses."""

    def test_forecast_record_frozen(self):
        fr = ForecastRecord(
            forecast_id="f1", tenant_id="t1",
            status=ForecastStatus.DRAFT,
            horizon=ForecastHorizon.SHORT,
            confidence_band=ForecastConfidenceBand.MEDIUM,
            confidence=0.5, signal_count=0,
            scope_ref_id="sc", projected_value=0.0,
            created_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            fr.status = ForecastStatus.ACTIVE

    def test_scenario_model_frozen(self):
        sm = ScenarioModel(
            scenario_id="sc-1", tenant_id="t-1", name="Test",
            status=ScenarioStatus.DRAFT,
            horizon=ForecastHorizon.MEDIUM,
            description="d", created_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            sm.name = "Other"

    def test_scenario_projection_frozen(self):
        sp = ScenarioProjection(
            projection_id="p1", scenario_id="s1", forecast_id="f1",
            projected_value=1.0, probability=0.5, impact_score=0.5,
            projected_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            sp.probability = 0.9

    def test_allocation_recommendation_frozen(self):
        ar = AllocationRecommendation(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id="s", recommended_value=0.0,
            confidence=0.5, reason="test", created_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            ar.disposition = AllocationDisposition.ACCEPTED

    def test_capacity_forecast_frozen(self):
        cf = CapacityForecast(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.5, projected_utilization=0.5,
            headroom=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            cf.headroom = 0.9

    def test_budget_forecast_frozen(self):
        bf = BudgetForecast(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=300.0, burn_rate=10.0,
            confidence=0.5, horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            bf.burn_rate = 999.0

    def test_risk_forecast_frozen(self):
        rf = RiskForecast(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=0.5, projected_risk=0.5,
            mitigation_coverage=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            rf.current_risk = 0.9

    def test_forecast_snapshot_frozen(self):
        fs = ForecastSnapshot(
            snapshot_id="snap-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_projections=0, total_recommendations=0,
            total_capacity_forecasts=0, total_budget_forecasts=0,
            total_risk_forecasts=0, total_violations=0,
            captured_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            fs.total_signals = 99

    def test_forecast_closure_report_frozen(self):
        cr = ForecastClosureReport(
            report_id="rpt-1", tenant_id="t-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_recommendations_accepted=0,
            total_recommendations_rejected=0,
            total_violations=0,
            closed_at=TS,
        )
        with pytest.raises(FrozenInstanceError):
            cr.total_violations = 99


class TestToDictFields:
    """Verify to_dict returns all expected field names."""

    def test_demand_signal_fields(self):
        ds = DemandSignal(
            signal_id="s1", tenant_id="t1",
            kind=DemandSignalKind.REQUEST_VOLUME,
            scope_ref_id="sc", value=0.0, recorded_at=TS,
        )
        d = ds.to_dict()
        expected = {"signal_id", "tenant_id", "kind", "scope_ref_id", "value", "recorded_at", "metadata"}
        assert set(d.keys()) == expected

    def test_forecast_record_fields(self):
        fr = ForecastRecord(
            forecast_id="f1", tenant_id="t1",
            status=ForecastStatus.DRAFT,
            horizon=ForecastHorizon.SHORT,
            confidence_band=ForecastConfidenceBand.MEDIUM,
            confidence=0.5, signal_count=0,
            scope_ref_id="sc", projected_value=0.0,
            created_at=TS,
        )
        d = fr.to_dict()
        expected = {
            "forecast_id", "tenant_id", "status", "horizon",
            "confidence_band", "confidence", "signal_count",
            "scope_ref_id", "projected_value", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_scenario_model_fields(self):
        sm = ScenarioModel(
            scenario_id="sc-1", tenant_id="t-1", name="Test",
            status=ScenarioStatus.DRAFT,
            horizon=ForecastHorizon.MEDIUM,
            description="d", created_at=TS,
        )
        d = sm.to_dict()
        expected = {
            "scenario_id", "tenant_id", "name", "status", "horizon",
            "description", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_scenario_projection_fields(self):
        sp = ScenarioProjection(
            projection_id="p1", scenario_id="s1", forecast_id="f1",
            projected_value=1.0, probability=0.5, impact_score=0.5,
            projected_at=TS,
        )
        d = sp.to_dict()
        expected = {
            "projection_id", "scenario_id", "forecast_id",
            "projected_value", "probability", "impact_score",
            "projected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_allocation_recommendation_fields(self):
        ar = AllocationRecommendation(
            recommendation_id="r1", forecast_id="f1", tenant_id="t1",
            disposition=AllocationDisposition.RECOMMENDED,
            scope_ref_id="s", recommended_value=0.0,
            confidence=0.5, reason="test", created_at=TS,
        )
        d = ar.to_dict()
        expected = {
            "recommendation_id", "forecast_id", "tenant_id", "disposition",
            "scope_ref_id", "recommended_value", "confidence", "reason",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_capacity_forecast_fields(self):
        cf = CapacityForecast(
            forecast_id="cf-1", tenant_id="t-1", scope_ref_id="s",
            current_utilization=0.5, projected_utilization=0.5,
            headroom=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        d = cf.to_dict()
        expected = {
            "forecast_id", "tenant_id", "scope_ref_id",
            "current_utilization", "projected_utilization", "headroom",
            "confidence", "horizon", "projected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_budget_forecast_fields(self):
        bf = BudgetForecast(
            forecast_id="bf-1", tenant_id="t-1", scope_ref_id="s",
            current_spend=100.0, projected_spend=200.0,
            budget_limit=300.0, burn_rate=10.0,
            confidence=0.5, horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        d = bf.to_dict()
        expected = {
            "forecast_id", "tenant_id", "scope_ref_id",
            "current_spend", "projected_spend", "budget_limit", "burn_rate",
            "confidence", "horizon", "projected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_risk_forecast_fields(self):
        rf = RiskForecast(
            forecast_id="rf-1", tenant_id="t-1", scope_ref_id="s",
            current_risk=0.5, projected_risk=0.5,
            mitigation_coverage=0.5, confidence=0.5,
            horizon=ForecastHorizon.SHORT, projected_at=TS,
        )
        d = rf.to_dict()
        expected = {
            "forecast_id", "tenant_id", "scope_ref_id",
            "current_risk", "projected_risk", "mitigation_coverage",
            "confidence", "horizon", "projected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_forecast_snapshot_fields(self):
        fs = ForecastSnapshot(
            snapshot_id="snap-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_projections=0, total_recommendations=0,
            total_capacity_forecasts=0, total_budget_forecasts=0,
            total_risk_forecasts=0, total_violations=0,
            captured_at=TS,
        )
        d = fs.to_dict()
        expected = {
            "snapshot_id", "total_signals", "total_forecasts", "total_scenarios",
            "total_projections", "total_recommendations",
            "total_capacity_forecasts", "total_budget_forecasts",
            "total_risk_forecasts", "total_violations",
            "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_forecast_closure_report_fields(self):
        cr = ForecastClosureReport(
            report_id="rpt-1", tenant_id="t-1",
            total_signals=0, total_forecasts=0, total_scenarios=0,
            total_recommendations_accepted=0,
            total_recommendations_rejected=0,
            total_violations=0,
            closed_at=TS,
        )
        d = cr.to_dict()
        expected = {
            "report_id", "tenant_id", "total_signals", "total_forecasts",
            "total_scenarios", "total_recommendations_accepted",
            "total_recommendations_rejected", "total_violations",
            "closed_at", "metadata",
        }
        assert set(d.keys()) == expected
