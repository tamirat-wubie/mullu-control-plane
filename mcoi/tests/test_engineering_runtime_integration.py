"""Comprehensive tests for the EngineeringRuntimeIntegration bridge.

Tests cover: construction validation, surface-specific engineering methods,
memory mesh attachment, graph attachment, and bridge sequencing.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.engineering_runtime import (
    EngineeringDomain,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.engineering_runtime import EngineeringRuntimeEngine
from mcoi_runtime.core.engineering_runtime_integration import EngineeringRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


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
def eng_engine(es, clock):
    return EngineeringRuntimeEngine(es, clock=clock)


@pytest.fixture()
def mem_engine():
    return MemoryMeshEngine()


@pytest.fixture()
def integration(eng_engine, es, mem_engine):
    return EngineeringRuntimeIntegration(eng_engine, es, mem_engine)


# ===================================================================
# Construction Tests
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, eng_engine, es, mem_engine):
        integ = EngineeringRuntimeIntegration(eng_engine, es, mem_engine)
        assert integ is not None

    def test_invalid_engineering_engine(self, es, mem_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            EngineeringRuntimeIntegration("bad", es, mem_engine)

    def test_invalid_event_spine(self, eng_engine, mem_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            EngineeringRuntimeIntegration(eng_engine, "bad", mem_engine)

    def test_invalid_memory_engine(self, eng_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            EngineeringRuntimeIntegration(eng_engine, es, "bad")


# ===================================================================
# Surface Method Tests
# ===================================================================


class TestSurfaceMethods:
    def test_engineering_for_assets(self, integration):
        result = integration.engineering_for_assets(
            tenant_id="t-1", asset_ref="asset-1",
            display_name="Pump Pressure", value=42.0, unit_label="psi",
            domain=EngineeringDomain.MECHANICAL, tolerance=0.5,
        )
        assert result["source_type"] == "assets"
        assert result["value"] == 42.0

    def test_engineering_for_continuity(self, integration):
        result = integration.engineering_for_continuity(
            tenant_id="t-1", continuity_ref="cont-1",
            display_name="Voltage", value=220.0, unit_label="V",
        )
        assert result["source_type"] == "continuity"

    def test_engineering_for_factory(self, integration):
        result = integration.engineering_for_factory(
            tenant_id="t-1", factory_ref="fac-1",
            display_name="Flow Rate", value=100.0, unit_label="L/min",
        )
        assert result["source_type"] == "factory"

    def test_engineering_for_service_capacity(self, integration):
        result = integration.engineering_for_service_capacity(
            tenant_id="t-1", service_ref="svc-1",
            display_name="Bandwidth", value=1000.0, unit_label="Mbps",
        )
        assert result["source_type"] == "service_capacity"

    def test_engineering_for_procurement(self, integration):
        result = integration.engineering_for_procurement(
            tenant_id="t-1", procurement_ref="proc-1",
            display_name="Tensile Strength", value=500.0, unit_label="MPa",
        )
        assert result["source_type"] == "procurement"

    def test_engineering_for_quality(self, integration):
        result = integration.engineering_for_quality(
            tenant_id="t-1", quality_ref="qual-1",
            display_name="pH Level", value=7.0, unit_label="pH",
        )
        assert result["source_type"] == "quality"

    def test_custom_quantity_id(self, integration):
        result = integration.engineering_for_assets(
            tenant_id="t-1", asset_ref="asset-1",
            quantity_id="custom-q-1",
            display_name="Custom", value=1.0, unit_label="unit",
        )
        assert result["quantity_id"] == "custom-q-1"


# ===================================================================
# Memory Mesh Attachment Tests
# ===================================================================


class TestMemoryMeshAttachment:
    def test_attach_engineering_state_to_memory_mesh(self, integration, eng_engine):
        eng_engine.register_quantity(
            "q-1", "t-1", "Temp", 50.0, "C",
            EngineeringDomain.THERMAL, 1.0,
        )
        record = integration.attach_engineering_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert "engineering" in record.tags
        assert "quantities" in record.tags
        assert "systems" in record.tags


# ===================================================================
# Graph Attachment Tests
# ===================================================================


class TestGraphAttachment:
    def test_attach_engineering_state_to_graph(self, integration, eng_engine):
        eng_engine.register_quantity(
            "q-1", "t-1", "Temp", 50.0, "C",
            EngineeringDomain.THERMAL, 1.0,
        )
        result = integration.attach_engineering_state_to_graph("scope-1")
        assert result["total_quantities"] == 1
        assert result["scope_ref_id"] == "scope-1"
