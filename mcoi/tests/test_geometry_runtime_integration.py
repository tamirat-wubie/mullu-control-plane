"""Focused tests for geometry runtime integration bounded contracts."""

from __future__ import annotations

from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.geometry_runtime import GeometryRuntimeEngine
from mcoi_runtime.core.geometry_runtime_integration import GeometryRuntimeIntegration
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


def _make_integration() -> tuple[GeometryRuntimeIntegration, GeometryRuntimeEngine, EventSpineEngine, MemoryMeshEngine]:
    spine = EventSpineEngine()
    engine = GeometryRuntimeEngine(spine)
    memory = MemoryMeshEngine()
    integration = GeometryRuntimeIntegration(engine, spine, memory)
    return integration, engine, spine, memory


class TestGeometryRuntimeIntegrationBoundedTitles:
    def test_attach_geometry_state_to_memory_mesh_uses_bounded_title(self):
        integration, _, _, memory = _make_integration()
        integration.geometry_from_asset_layout("t1", "asset-1")
        record = integration.attach_geometry_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert record.title == "Geometry state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"
        assert memory.memory_count == 1

    def test_attach_geometry_state_to_graph_preserves_scope_and_counts(self):
        integration, _, _, _ = _make_integration()
        integration.geometry_from_asset_layout("t1", "asset-1")
        graph = integration.attach_geometry_state_to_graph("scope-2")
        assert graph["scope_ref_id"] == "scope-2"
        assert graph["total_points"] == 1
        assert graph["total_shapes"] == 1
        assert graph["total_regions"] == 1
