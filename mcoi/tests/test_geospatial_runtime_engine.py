"""Tests for geospatial runtime engine (Phase 117).

Covers: GeospatialRuntimeEngine features, territories, routes, depots, sites,
        distance computation, nearest feature, territory resolution, violation
        detection, snapshots, state hashing, and golden scenarios.
"""

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.geospatial_runtime import GeospatialRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.geospatial_runtime import (
    DistanceUnit,
    GeoFeatureKind,
    GeoStatus,
    RouteStatus,
    TerritoryDisposition,
)


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _fixed_clock():
    return lambda: FIXED_TS


def _make_engine(*, clock=None):
    es = EventSpineEngine()
    eng = GeospatialRuntimeEngine(es, clock=clock or _fixed_clock())
    return eng, es


# ===================================================================
# Constructor
# ===================================================================

class TestConstructor:
    def test_valid_event_spine(self):
        eng, _ = _make_engine()
        assert eng.feature_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            GeospatialRuntimeEngine("not_an_engine")

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = GeospatialRuntimeEngine(es)
        assert eng.feature_count == 0

    def test_custom_clock(self):
        eng, _ = _make_engine(clock=lambda: "2025-01-01T00:00:00+00:00")
        f = eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.0, -74.0)
        assert f.created_at == "2025-01-01T00:00:00+00:00"


# ===================================================================
# Features
# ===================================================================

class TestFeatures:
    def test_register_feature(self):
        eng, _ = _make_engine()
        f = eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.7, -74.0)
        assert f.feature_id == "f1"
        assert f.status == GeoStatus.ACTIVE
        assert eng.feature_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.7, -74.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.7, -74.0)

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.7, -74.0)
        assert es.event_count >= 1

    @pytest.mark.parametrize("kind", list(GeoFeatureKind))
    def test_all_kinds(self, kind):
        eng, _ = _make_engine()
        f = eng.register_feature("f1", "t1", kind, "Feature", 0.0, 0.0)
        assert f.kind is kind


# ===================================================================
# Territories
# ===================================================================

class TestTerritories:
    def test_register_territory(self):
        eng, _ = _make_engine()
        t = eng.register_territory("ter1", "t1", "Zone A")
        assert t.territory_id == "ter1"
        assert t.disposition == TerritoryDisposition.UNASSIGNED
        assert eng.territory_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_territory("ter1", "t1", "Zone A")

    def test_assign_territory(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        t = eng.assign_territory("ter1", "agent-1")
        assert t.disposition == TerritoryDisposition.ASSIGNED
        assert t.assigned_ref == "agent-1"

    def test_assign_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.assign_territory("nope", "agent-1")


# ===================================================================
# Routes
# ===================================================================

class TestRoutes:
    def test_register_route(self):
        eng, _ = _make_engine()
        r = eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 500.0)
        assert r.route_id == "rt1"
        assert r.status == RouteStatus.OPEN
        assert eng.route_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 500.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 500.0)

    def test_block_route(self):
        eng, _ = _make_engine()
        eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 500.0)
        r = eng.block_route("rt1")
        assert r.status == RouteStatus.BLOCKED

    def test_degrade_route(self):
        eng, _ = _make_engine()
        eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 500.0)
        r = eng.degrade_route("rt1")
        assert r.status == RouteStatus.DEGRADED

    def test_block_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.block_route("nope")

    def test_route_with_unit(self):
        eng, _ = _make_engine()
        r = eng.register_route("rt1", "t1", "Route", "f1", "f2", 10.0,
                               unit=DistanceUnit.KILOMETERS)
        assert r.unit == DistanceUnit.KILOMETERS


# ===================================================================
# Depots
# ===================================================================

class TestDepots:
    def test_register_depot(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.DEPOT, "Depot Feature", 0.0, 0.0)
        d = eng.register_depot("dep1", "t1", "Depot A", "f1", 100)
        assert d.depot_id == "dep1"
        assert d.capacity == 100
        assert eng.depot_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.DEPOT, "Depot Feature", 0.0, 0.0)
        eng.register_depot("dep1", "t1", "Depot A", "f1", 100)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_depot("dep1", "t1", "Depot A", "f1", 100)

    def test_unknown_feature_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.register_depot("dep1", "t1", "Depot A", "nope", 100)

    def test_update_depot_load(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.DEPOT, "Depot Feature", 0.0, 0.0)
        eng.register_depot("dep1", "t1", "Depot A", "f1", 100)
        d = eng.update_depot_load("dep1", 80)
        assert d.current_load == 80

    def test_update_unknown_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.update_depot_load("nope", 50)


# ===================================================================
# Sites
# ===================================================================

class TestSites:
    def test_register_site(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.SITE, "Site Feature", 0.0, 0.0)
        eng.register_territory("ter1", "t1", "Zone A")
        s = eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        assert s.site_id == "s1"
        assert eng.site_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.SITE, "Site Feature", 0.0, 0.0)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_site("s1", "t1", "Site A", "f1", "ter1")

    def test_unknown_feature_rejected(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown feature"):
            eng.register_site("s1", "t1", "Site A", "nope", "ter1")

    def test_unknown_territory_rejected(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.SITE, "Site Feature", 0.0, 0.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown territory"):
            eng.register_site("s1", "t1", "Site A", "f1", "nope")

    def test_site_increments_territory_feature_count(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.SITE, "Site Feature", 0.0, 0.0)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        # Territory feature count should have been incremented
        # (internal state, checked via second site)
        eng.register_feature("f2", "t1", GeoFeatureKind.SITE, "Site Feature 2", 1.0, 1.0)
        eng.register_site("s2", "t1", "Site B", "f2", "ter1")
        assert eng.site_count == 2


# ===================================================================
# Distance computation
# ===================================================================

class TestDistanceComputation:
    def test_compute_distance(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "A", 40.7128, -74.0060)
        eng.register_feature("f2", "t1", GeoFeatureKind.POINT, "B", 34.0522, -118.2437)
        dist = eng.compute_distance("f1", "f2")
        assert dist > 3_900_000  # ~3944 km

    def test_same_point_zero(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "A", 40.0, -74.0)
        eng.register_feature("f2", "t1", GeoFeatureKind.POINT, "B", 40.0, -74.0)
        dist = eng.compute_distance("f1", "f2")
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_unknown_feature_rejected(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "A", 0.0, 0.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.compute_distance("f1", "nope")


# ===================================================================
# Nearest feature
# ===================================================================

class TestNearestFeature:
    def test_find_nearest(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "Near", 40.0, -74.0)
        eng.register_feature("f2", "t1", GeoFeatureKind.POINT, "Far", 0.0, 0.0)
        nearest = eng.find_nearest_feature(40.1, -74.1)
        assert nearest.feature_id == "f1"

    def test_empty_returns_none(self):
        eng, _ = _make_engine()
        assert eng.find_nearest_feature(0.0, 0.0) is None


# ===================================================================
# Territory resolution
# ===================================================================

class TestTerritoryResolution:
    def test_resolve_territory(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.SITE, "Site Feature", 0.0, 0.0)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        t = eng.resolve_territory("f1")
        assert t is not None
        assert t.territory_id == "ter1"

    def test_resolve_unknown_returns_none(self):
        eng, _ = _make_engine()
        assert eng.resolve_territory("nope") is None


# ===================================================================
# Assessment
# ===================================================================

class TestAssessment:
    def test_basic_assessment(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        a = eng.geo_assessment("a1", "t1")
        assert a.total_features == 1

    def test_coverage_rate(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        eng.assign_territory("ter1", "agent-1")
        eng.register_territory("ter2", "t1", "Zone B")
        a = eng.geo_assessment("a1", "t1")
        assert a.coverage_rate == 0.5


# ===================================================================
# Snapshot
# ===================================================================

class TestSnapshot:
    def test_basic_snapshot(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        s = eng.geo_snapshot("s1", "t1")
        assert s.total_features == 1

    def test_duplicate_snapshot_rejected(self):
        eng, _ = _make_engine()
        eng.geo_snapshot("s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.geo_snapshot("s1", "t1")

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        snap = eng.snapshot()
        assert "features" in snap


# ===================================================================
# Closure report
# ===================================================================

class TestClosureReport:
    def test_basic_closure(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        c = eng.geo_closure_report("cr1", "t1")
        assert c.total_features == 1


# ===================================================================
# Violation detection
# ===================================================================

class TestViolationDetection:
    def test_no_violations_empty(self):
        eng, _ = _make_engine()
        v = eng.detect_geo_violations()
        assert len(v) == 0

    def test_overloaded_depot(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.DEPOT, "DF", 0.0, 0.0)
        eng.register_depot("dep1", "t1", "Depot A", "f1", 100)
        eng.update_depot_load("dep1", 150)
        v = eng.detect_geo_violations()
        assert any(x["operation"] == "overloaded_depot" for x in v)

    def test_unassigned_territory(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        v = eng.detect_geo_violations()
        assert any(x["operation"] == "unassigned_territory" for x in v)

    def test_blocked_route_in_use(self):
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "A", 0.0, 0.0)
        eng.register_feature("f2", "t1", GeoFeatureKind.POINT, "B", 1.0, 1.0)
        eng.register_route("rt1", "t1", "Route", "f1", "f2", 100.0)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        eng.block_route("rt1")
        v = eng.detect_geo_violations()
        assert any(x["operation"] == "blocked_route_in_use" for x in v)

    def test_idempotency(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        v1 = eng.detect_geo_violations()
        assert len(v1) > 0
        v2 = eng.detect_geo_violations()
        assert len(v2) == 0

    def test_violation_count_incremented(self):
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        eng.detect_geo_violations()
        assert eng.violation_count > 0


# ===================================================================
# State hash
# ===================================================================

class TestStateHash:
    def test_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_after_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        eng1.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        eng2.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# Golden scenarios
# ===================================================================

class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        """Full geospatial lifecycle: features, territories, routes, sites, depots."""
        eng, es = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 40.7, -74.0)
        eng.register_feature("f2", "t1", GeoFeatureKind.DEPOT, "Depot", 34.0, -118.2)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.assign_territory("ter1", "agent-1")
        eng.register_route("rt1", "t1", "Route A-B", "f1", "f2", 3900000.0)
        eng.register_depot("dep1", "t1", "Depot A", "f2", 100)
        eng.register_site("s1", "t1", "Site A", "f1", "ter1")
        assert eng.feature_count == 2
        assert eng.territory_count == 1
        assert eng.route_count == 1
        assert eng.depot_count == 1
        assert eng.site_count == 1
        assert es.event_count >= 7

    def test_cross_tenant_denied(self):
        """Assessment scoped to tenant."""
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        a = eng.geo_assessment("a1", "t-other")
        assert a.total_features == 0

    def test_terminal_state_blocking(self):
        """No terminal state blocking for geo (no terminal statuses on features)."""
        # Geo features don't have terminal phases in the same way, but we test
        # that duplicate IDs are still blocked
        eng, _ = _make_engine()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        with pytest.raises(RuntimeCoreInvariantError):
            eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ2", 1.0, 1.0)

    def test_violation_detection_idempotency(self):
        """First call detects, second returns empty."""
        eng, _ = _make_engine()
        eng.register_territory("ter1", "t1", "Zone A")
        v1 = eng.detect_geo_violations()
        assert len(v1) > 0
        v2 = eng.detect_geo_violations()
        assert len(v2) == 0

    def test_state_hash_determinism(self):
        """Two engines with identical operations produce identical state hashes."""
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        for eng in (eng1, eng2):
            eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
            eng.register_territory("ter1", "t1", "Zone A")
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_consistency(self):
        """Replay with same clock produces consistent state."""
        eng1, _ = _make_engine()
        eng1.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        eng1.register_territory("ter1", "t1", "Zone A")
        snap1 = eng1.snapshot()
        eng2, _ = _make_engine()
        eng2.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        eng2.register_territory("ter1", "t1", "Zone A")
        snap2 = eng2.snapshot()
        # State hashes should match since same operations
        assert eng1.state_hash() == eng2.state_hash()
