"""Tests for geospatial runtime integration bridge (Phase 117).

Covers: GeospatialRuntimeIntegration cross-domain creation, memory mesh
        attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.geospatial_runtime import GeospatialRuntimeEngine
from mcoi_runtime.core.geospatial_runtime_integration import GeospatialRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.contracts.geospatial_runtime import GeoFeatureKind


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_integration():
    es = EventSpineEngine()
    eng = GeospatialRuntimeEngine(es, clock=lambda: FIXED_TS)
    mem = MemoryMeshEngine()
    integ = GeospatialRuntimeIntegration(eng, es, mem)
    return integ, eng, es, mem


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_geo_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            GeospatialRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        eng = GeospatialRuntimeEngine(es, clock=lambda: FIXED_TS)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            GeospatialRuntimeIntegration(eng, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        eng = GeospatialRuntimeEngine(es, clock=lambda: FIXED_TS)
        with pytest.raises(RuntimeCoreInvariantError):
            GeospatialRuntimeIntegration(eng, es, "bad")


# ===================================================================
# Cross-domain geo creation
# ===================================================================

class TestGeoFromServiceTerritory:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        assert result["feature_id"] == "f1"
        assert result["source_type"] == "service_territory"
        assert eng.feature_count == 1

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        assert es.event_count > before

    def test_duplicate_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        with pytest.raises(RuntimeCoreInvariantError):
            integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        result = integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        assert result["tenant_id"] == "t1"
        assert result["latitude"] == 40.7
        assert result["longitude"] == -74.0
        assert result["status"] == "active"


class TestGeoFromContinuitySite:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_continuity_site("f1", "t1", "DR Site", 34.0, -118.2)
        assert result["source_type"] == "continuity_site"
        assert eng.feature_count == 1


class TestGeoFromFactoryLocation:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_factory_location("f1", "t1", "Factory", 51.5, -0.12)
        assert result["source_type"] == "factory_location"


class TestGeoFromAssetPlacement:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_asset_placement("f1", "t1", "Asset", 35.6, 139.6)
        assert result["source_type"] == "asset_placement"


class TestGeoFromLogistics:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_logistics("f1", "t1", "Logistics Hub", 48.8, 2.3)
        assert result["source_type"] == "logistics"


class TestGeoFromWorkforceField:
    def test_creates_feature(self):
        integ, eng, _, _ = _make_integration()
        result = integ.geo_from_workforce_field("f1", "t1", "Field Office", -33.8, 151.2)
        assert result["source_type"] == "workforce_field"


# ===================================================================
# Memory mesh attachment
# ===================================================================

class TestMemoryMeshAttachment:
    def test_attach_to_memory(self):
        integ, eng, _, mem = _make_integration()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        record = integ.attach_geo_state_to_memory_mesh("scope-1")
        assert record.memory_id
        assert mem.memory_count >= 1

    def test_memory_title_is_bounded(self):
        integ, eng, _, _ = _make_integration()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        record = integ.attach_geo_state_to_memory_mesh("scope-1")
        assert record.title == "Geospatial state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"

    def test_emits_event(self):
        integ, eng, es, _ = _make_integration()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        before = es.event_count
        integ.attach_geo_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# Graph attachment
# ===================================================================

class TestGraphAttachment:
    def test_attach_to_graph(self):
        integ, eng, _, _ = _make_integration()
        eng.register_feature("f1", "t1", GeoFeatureKind.POINT, "HQ", 0.0, 0.0)
        result = integ.attach_geo_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_features"] == 1

    def test_graph_reflects_violations(self):
        integ, eng, _, _ = _make_integration()
        eng.register_territory("ter1", "t1", "Zone A")
        eng.detect_geo_violations()
        result = integ.attach_geo_state_to_graph("scope-1")
        assert result["total_violations"] > 0


# ===================================================================
# End-to-end integration
# ===================================================================

class TestEndToEnd:
    def test_full_workflow(self):
        integ, eng, es, mem = _make_integration()
        integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        eng.register_territory("ter1", "t1", "Zone A")
        eng.assign_territory("ter1", "agent-1")
        integ.attach_geo_state_to_memory_mesh("scope-1")
        assert mem.memory_count >= 1
        graph = integ.attach_geo_state_to_graph("scope-1")
        assert graph["total_features"] == 1
        assert es.event_count >= 3

    def test_multiple_sources(self):
        integ, eng, _, _ = _make_integration()
        integ.geo_from_service_territory("f1", "t1", "HQ", 40.7, -74.0)
        integ.geo_from_factory_location("f2", "t1", "Factory", 51.5, -0.12)
        integ.geo_from_logistics("f3", "t1", "Hub", 48.8, 2.3)
        assert eng.feature_count == 3
