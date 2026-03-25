"""Comprehensive tests for DigitalTwinRuntimeIntegration.

Tests cover: construction, source-specific twin methods, memory mesh attachment,
graph attachment, multi-tenant, event emission, and end-to-end workflows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.digital_twin_runtime import (
    TwinObjectKind,
    TwinStatus,
    TwinStateDisposition,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.digital_twin_runtime import DigitalTwinRuntimeEngine
from mcoi_runtime.core.digital_twin_runtime_integration import DigitalTwinRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def mem():
    return MemoryMeshEngine()


@pytest.fixture()
def twin_engine(es, clock):
    return DigitalTwinRuntimeEngine(es, clock=clock)


@pytest.fixture()
def integration(twin_engine, es, mem):
    return DigitalTwinRuntimeIntegration(twin_engine, es, mem)


# ===================================================================
# Construction Tests
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, twin_engine, es, mem):
        integ = DigitalTwinRuntimeIntegration(twin_engine, es, mem)
        assert integ is not None

    def test_invalid_twin_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeIntegration("not_engine", es, mem)

    def test_invalid_event_spine_rejected(self, twin_engine, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeIntegration(twin_engine, "not_es", mem)

    def test_invalid_memory_engine_rejected(self, twin_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeIntegration(twin_engine, es, "not_mem")

    def test_none_twin_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeIntegration(None, es, mem)


# ===================================================================
# Source-specific twin methods
# ===================================================================


class TestTwinFromSources:
    def test_twin_from_factory_runtime(self, integration, twin_engine):
        result = integration.twin_from_factory_runtime("t-1", "factory-ref-1")
        assert result["source_type"] == "factory_runtime"
        assert result["tenant_id"] == "t-1"
        assert twin_engine.model_count == 1
        assert twin_engine.object_count == 1

    def test_twin_from_asset_runtime(self, integration, twin_engine):
        result = integration.twin_from_asset_runtime("t-1", "asset-ref-1")
        assert result["source_type"] == "asset_runtime"
        assert twin_engine.model_count == 1

    def test_twin_from_geometry_runtime(self, integration, twin_engine):
        result = integration.twin_from_geometry_runtime("t-1", "geo-ref-1")
        assert result["source_type"] == "geometry_runtime"
        assert result["kind"] == "site"

    def test_twin_from_observability(self, integration, twin_engine):
        result = integration.twin_from_observability("t-1", "trace-ref-1")
        assert result["source_type"] == "observability"
        assert result["kind"] == "sensor"

    def test_twin_from_continuity_runtime(self, integration, twin_engine):
        result = integration.twin_from_continuity_runtime("t-1", "cont-ref-1")
        assert result["source_type"] == "continuity_runtime"
        assert result["kind"] == "station"

    def test_twin_from_workforce_runtime(self, integration, twin_engine):
        result = integration.twin_from_workforce_runtime("t-1", "wf-ref-1")
        assert result["source_type"] == "workforce_runtime"
        assert result["kind"] == "component"

    def test_twin_with_explicit_ids(self, integration, twin_engine):
        result = integration.twin_from_factory_runtime(
            "t-1", "factory-ref-1",
            model_id="custom-model", object_id="custom-obj",
        )
        assert result["model_id"] == "custom-model"
        assert result["object_id"] == "custom-obj"
        assert twin_engine.model_count == 1

    def test_multiple_sources(self, integration, twin_engine):
        integration.twin_from_factory_runtime("t-1", "f-1")
        integration.twin_from_asset_runtime("t-1", "a-1")
        integration.twin_from_geometry_runtime("t-1", "g-1")
        assert twin_engine.model_count == 3
        assert twin_engine.object_count == 3


# ===================================================================
# Memory Mesh Attachment Tests
# ===================================================================


class TestMemoryMeshAttachment:
    def test_attach_to_memory_mesh(self, integration, mem):
        integration.twin_from_factory_runtime("t-1", "f-1")
        record = integration.attach_twin_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert mem.memory_count == 1

    def test_memory_tags(self, integration, mem):
        integration.twin_from_factory_runtime("t-1", "f-1")
        record = integration.attach_twin_state_to_memory_mesh("scope-1")
        assert "digital_twin" in record.tags
        assert "physical" in record.tags
        assert "topology" in record.tags

    def test_memory_content_has_counts(self, integration, mem):
        integration.twin_from_factory_runtime("t-1", "f-1")
        record = integration.attach_twin_state_to_memory_mesh("scope-1")
        content = dict(record.content)
        assert content["total_models"] == 1
        assert content["total_objects"] == 1


# ===================================================================
# Graph Attachment Tests
# ===================================================================


class TestGraphAttachment:
    def test_attach_to_graph(self, integration):
        integration.twin_from_factory_runtime("t-1", "f-1")
        result = integration.attach_twin_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_models"] == 1
        assert result["total_objects"] == 1

    def test_graph_state_empty(self, integration):
        result = integration.attach_twin_state_to_graph("scope-1")
        assert result["total_models"] == 0
        assert result["total_objects"] == 0


# ===================================================================
# Multi-tenant Tests
# ===================================================================


class TestMultiTenant:
    def test_different_tenants(self, integration, twin_engine):
        integration.twin_from_factory_runtime("t-1", "f-1")
        integration.twin_from_factory_runtime("t-2", "f-2")
        assert twin_engine.model_count == 2
        assert twin_engine.object_count == 2


# ===================================================================
# Event Emission Tests
# ===================================================================


class TestEventEmission:
    def test_events_emitted_on_twin_creation(self, es, integration):
        before = es.event_count
        integration.twin_from_factory_runtime("t-1", "f-1")
        assert es.event_count > before

    def test_events_emitted_on_memory_attachment(self, es, integration):
        integration.twin_from_factory_runtime("t-1", "f-1")
        before = es.event_count
        integration.attach_twin_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# End-to-End Workflow Tests
# ===================================================================


class TestEndToEnd:
    def test_full_workflow(self, integration, twin_engine, mem):
        # Create twins from multiple sources
        r1 = integration.twin_from_factory_runtime("t-1", "f-1")
        r2 = integration.twin_from_asset_runtime("t-1", "a-1")
        r3 = integration.twin_from_observability("t-1", "trace-1")

        assert twin_engine.model_count == 3
        assert twin_engine.object_count == 3

        # Attach to memory
        record = integration.attach_twin_state_to_memory_mesh("scope-1")
        assert mem.memory_count == 1

        # Get graph state
        graph = integration.attach_twin_state_to_graph("scope-1")
        assert graph["total_models"] == 3
        assert graph["total_objects"] == 3

    def test_all_six_sources(self, integration, twin_engine):
        integration.twin_from_factory_runtime("t-1", "f-1")
        integration.twin_from_asset_runtime("t-1", "a-1")
        integration.twin_from_geometry_runtime("t-1", "g-1")
        integration.twin_from_observability("t-1", "o-1")
        integration.twin_from_continuity_runtime("t-1", "c-1")
        integration.twin_from_workforce_runtime("t-1", "w-1")
        assert twin_engine.model_count == 6
        assert twin_engine.object_count == 6
