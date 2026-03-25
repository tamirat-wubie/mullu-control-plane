"""Tests for geospatial runtime contracts (Phase 117).

Covers: GeoFeature, TerritoryRecord, RouteRecord, DepotRecord, SiteRecord,
        GeoDecision, GeoAssessment, GeoViolation, GeoSnapshot,
        GeoClosureReport, and all related enums.
"""

import json
import math

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.geospatial_runtime import (
    DepotRecord,
    DistanceUnit,
    GeoAssessment,
    GeoClosureReport,
    GeoDecision,
    GeoFeature,
    GeoFeatureKind,
    GeoRiskLevel,
    GeoSnapshot,
    GeoStatus,
    GeoViolation,
    RouteRecord,
    RouteStatus,
    SiteRecord,
    TerritoryDisposition,
    TerritoryRecord,
)


TS = "2025-06-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feature(**kw):
    defaults = dict(
        feature_id="f-001", tenant_id="t-1", kind=GeoFeatureKind.POINT,
        display_name="HQ", latitude=40.7128, longitude=-74.0060,
        status=GeoStatus.ACTIVE, created_at=TS,
    )
    defaults.update(kw)
    return GeoFeature(**defaults)


def _territory(**kw):
    defaults = dict(
        territory_id="ter-001", tenant_id="t-1", display_name="Zone A",
        disposition=TerritoryDisposition.UNASSIGNED, assigned_ref="",
        feature_count=0, created_at=TS,
    )
    defaults.update(kw)
    return TerritoryRecord(**defaults)


def _route(**kw):
    defaults = dict(
        route_id="rt-001", tenant_id="t-1", display_name="Route A-B",
        origin_ref="f-001", destination_ref="f-002", distance=1000.0,
        unit=DistanceUnit.METERS, status=RouteStatus.OPEN, created_at=TS,
    )
    defaults.update(kw)
    return RouteRecord(**defaults)


def _depot(**kw):
    defaults = dict(
        depot_id="dep-001", tenant_id="t-1", display_name="Depot A",
        feature_ref="f-001", capacity=100, current_load=50, created_at=TS,
    )
    defaults.update(kw)
    return DepotRecord(**defaults)


def _site(**kw):
    defaults = dict(
        site_id="site-001", tenant_id="t-1", display_name="Site A",
        feature_ref="f-001", territory_ref="ter-001", created_at=TS,
    )
    defaults.update(kw)
    return SiteRecord(**defaults)


def _geo_decision(**kw):
    defaults = dict(
        decision_id="dec-001", tenant_id="t-1", feature_ref="f-001",
        disposition="restrict", reason="Safety concern", decided_at=TS,
    )
    defaults.update(kw)
    return GeoDecision(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="a-001", tenant_id="t-1", total_features=10,
        total_territories=3, total_routes=5, coverage_rate=0.8,
        assessed_at=TS,
    )
    defaults.update(kw)
    return GeoAssessment(**defaults)


def _geo_violation(**kw):
    defaults = dict(
        violation_id="viol-001", tenant_id="t-1", operation="overloaded_depot",
        reason="Depot overloaded", detected_at=TS,
    )
    defaults.update(kw)
    return GeoViolation(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-001", tenant_id="t-1", total_features=10,
        total_territories=3, total_routes=5, total_depots=2,
        total_sites=4, total_violations=1, captured_at=TS,
    )
    defaults.update(kw)
    return GeoSnapshot(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="cr-001", tenant_id="t-1", total_features=10,
        total_territories=3, total_routes=5, total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return GeoClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================

class TestGeoStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in GeoStatus) == {"active", "deprecated", "restricted", "closed"}
    def test_member_count(self):
        assert len(GeoStatus) == 4

class TestGeoFeatureKindEnum:
    def test_all_values(self):
        assert set(e.value for e in GeoFeatureKind) == {
            "point", "route", "region", "depot", "site", "zone",
        }
    def test_member_count(self):
        assert len(GeoFeatureKind) == 6

class TestTerritoryDispositionEnum:
    def test_all_values(self):
        assert set(e.value for e in TerritoryDisposition) == {
            "assigned", "unassigned", "contested", "restricted",
        }

class TestRouteStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in RouteStatus) == {"open", "blocked", "degraded", "unknown"}

class TestDistanceUnitEnum:
    def test_all_values(self):
        assert set(e.value for e in DistanceUnit) == {
            "meters", "kilometers", "miles", "nautical_miles",
        }

class TestGeoRiskLevelEnum:
    def test_all_values(self):
        assert set(e.value for e in GeoRiskLevel) == {"low", "medium", "high", "critical"}


# ===================================================================
# GeoFeature
# ===================================================================

class TestGeoFeature:
    def test_happy_path(self):
        f = _feature()
        assert f.feature_id == "f-001"
        assert f.kind == GeoFeatureKind.POINT
        assert f.latitude == 40.7128
        assert f.longitude == -74.0060

    def test_frozen(self):
        f = _feature()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(f, "feature_id", "x")

    def test_to_dict_preserves_enum(self):
        f = _feature()
        data = f.to_dict()
        assert data["kind"] is GeoFeatureKind.POINT
        assert data["status"] is GeoStatus.ACTIVE

    def test_to_json_dict_serializes_enum(self):
        f = _feature()
        data = f.to_json_dict()
        assert data["kind"] == "point"
        assert data["status"] == "active"

    def test_to_json_roundtrip(self):
        f = _feature()
        parsed = json.loads(f.to_json())
        assert parsed["feature_id"] == "f-001"

    def test_metadata_frozen(self):
        f = _feature(metadata={"k": "v"})
        with pytest.raises(TypeError):
            f.metadata["k2"] = "v2"

    @pytest.mark.parametrize("field,val", [
        ("feature_id", ""), ("tenant_id", "  "), ("display_name", ""),
    ])
    def test_empty_text_rejected(self, field, val):
        with pytest.raises(ValueError):
            _feature(**{field: val})

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            _feature(kind="not_a_kind")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _feature(status="not_a_status")

    def test_bool_latitude_rejected(self):
        with pytest.raises(ValueError):
            _feature(latitude=True)

    def test_inf_latitude_rejected(self):
        with pytest.raises(ValueError):
            _feature(latitude=float("inf"))

    def test_nan_latitude_rejected(self):
        with pytest.raises(ValueError):
            _feature(latitude=float("nan"))

    def test_bool_longitude_rejected(self):
        with pytest.raises(ValueError):
            _feature(longitude=True)

    def test_inf_longitude_rejected(self):
        with pytest.raises(ValueError):
            _feature(longitude=float("inf"))

    def test_negative_latitude_accepted(self):
        f = _feature(latitude=-33.8688)
        assert f.latitude == -33.8688

    def test_negative_longitude_accepted(self):
        f = _feature(longitude=-118.2437)
        assert f.longitude == -118.2437

    @pytest.mark.parametrize("kind", list(GeoFeatureKind))
    def test_all_kinds_accepted(self, kind):
        f = _feature(kind=kind)
        assert f.kind is kind

    @pytest.mark.parametrize("status", list(GeoStatus))
    def test_all_statuses_accepted(self, status):
        f = _feature(status=status)
        assert f.status is status

    def test_bad_created_at(self):
        with pytest.raises(ValueError):
            _feature(created_at="not-a-date")

    def test_equal_features(self):
        assert _feature() == _feature()

    def test_unequal_features(self):
        assert _feature() != _feature(feature_id="f-002")


# ===================================================================
# TerritoryRecord
# ===================================================================

class TestTerritoryRecord:
    def test_happy_path(self):
        t = _territory()
        assert t.territory_id == "ter-001"
        assert t.disposition == TerritoryDisposition.UNASSIGNED

    def test_frozen(self):
        t = _territory()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(t, "territory_id", "x")

    @pytest.mark.parametrize("disp", list(TerritoryDisposition))
    def test_all_dispositions(self, disp):
        t = _territory(disposition=disp)
        assert t.disposition is disp

    def test_invalid_disposition(self):
        with pytest.raises(ValueError):
            _territory(disposition="bad")

    @pytest.mark.parametrize("field", ["territory_id", "tenant_id", "display_name"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _territory(**{field: ""})

    def test_negative_feature_count(self):
        with pytest.raises(ValueError):
            _territory(feature_count=-1)

    def test_bool_feature_count(self):
        with pytest.raises(ValueError):
            _territory(feature_count=True)

    def test_to_dict(self):
        data = _territory().to_dict()
        assert data["disposition"] is TerritoryDisposition.UNASSIGNED


# ===================================================================
# RouteRecord
# ===================================================================

class TestRouteRecord:
    def test_happy_path(self):
        r = _route()
        assert r.route_id == "rt-001"
        assert r.distance == 1000.0
        assert r.unit == DistanceUnit.METERS

    def test_frozen(self):
        r = _route()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "route_id", "x")

    @pytest.mark.parametrize("unit", list(DistanceUnit))
    def test_all_units(self, unit):
        r = _route(unit=unit)
        assert r.unit is unit

    @pytest.mark.parametrize("status", list(RouteStatus))
    def test_all_statuses(self, status):
        r = _route(status=status)
        assert r.status is status

    def test_invalid_unit(self):
        with pytest.raises(ValueError):
            _route(unit="bad")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _route(status="bad")

    def test_negative_distance_rejected(self):
        with pytest.raises(ValueError):
            _route(distance=-1.0)

    def test_zero_distance(self):
        r = _route(distance=0.0)
        assert r.distance == 0.0

    @pytest.mark.parametrize("field", ["route_id", "tenant_id", "display_name", "origin_ref", "destination_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _route(**{field: ""})

    def test_to_dict(self):
        data = _route().to_dict()
        assert data["unit"] is DistanceUnit.METERS
        assert data["status"] is RouteStatus.OPEN


# ===================================================================
# DepotRecord
# ===================================================================

class TestDepotRecord:
    def test_happy_path(self):
        d = _depot()
        assert d.depot_id == "dep-001"
        assert d.capacity == 100
        assert d.current_load == 50

    def test_frozen(self):
        d = _depot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "depot_id", "x")

    @pytest.mark.parametrize("field", ["depot_id", "tenant_id", "display_name", "feature_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _depot(**{field: ""})

    def test_negative_capacity(self):
        with pytest.raises(ValueError):
            _depot(capacity=-1)

    def test_negative_load(self):
        with pytest.raises(ValueError):
            _depot(current_load=-1)

    def test_zero_values(self):
        d = _depot(capacity=0, current_load=0)
        assert d.capacity == 0
        assert d.current_load == 0


# ===================================================================
# SiteRecord
# ===================================================================

class TestSiteRecord:
    def test_happy_path(self):
        s = _site()
        assert s.site_id == "site-001"

    def test_frozen(self):
        s = _site()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "site_id", "x")

    @pytest.mark.parametrize("field", ["site_id", "tenant_id", "display_name", "feature_ref", "territory_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _site(**{field: ""})


# ===================================================================
# GeoDecision
# ===================================================================

class TestGeoDecision:
    def test_happy_path(self):
        d = _geo_decision()
        assert d.decision_id == "dec-001"

    def test_frozen(self):
        d = _geo_decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    @pytest.mark.parametrize("field", ["decision_id", "tenant_id", "feature_ref", "disposition", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _geo_decision(**{field: ""})


# ===================================================================
# GeoAssessment
# ===================================================================

class TestGeoAssessment:
    def test_happy_path(self):
        a = _assessment()
        assert a.assessment_id == "a-001"
        assert a.coverage_rate == 0.8

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")

    def test_coverage_rate_bounds(self):
        _assessment(coverage_rate=0.0)
        _assessment(coverage_rate=1.0)

    def test_coverage_rate_over_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_rate=1.1)

    def test_coverage_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(coverage_rate=-0.1)

    def test_negative_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_features=-1)


# ===================================================================
# GeoViolation
# ===================================================================

class TestGeoViolation:
    def test_happy_path(self):
        v = _geo_violation()
        assert v.violation_id == "viol-001"

    def test_frozen(self):
        v = _geo_violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "operation", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _geo_violation(**{field: ""})


# ===================================================================
# GeoSnapshot
# ===================================================================

class TestGeoSnapshot:
    def test_happy_path(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_features == 10

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")

    @pytest.mark.parametrize("field", [
        "total_features", "total_territories", "total_routes",
        "total_depots", "total_sites", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})


# ===================================================================
# GeoClosureReport
# ===================================================================

class TestGeoClosureReport:
    def test_happy_path(self):
        c = _closure()
        assert c.report_id == "cr-001"

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "report_id", "x")

    @pytest.mark.parametrize("field", [
        "total_features", "total_territories", "total_routes", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    def test_to_json(self):
        parsed = json.loads(_closure().to_json())
        assert parsed["report_id"] == "cr-001"
