"""Tests for IndustryPackIntegration bridge.

Governance scope: comprehensive coverage for bridge methods, memory mesh
attachment, and graph attachment.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.industry_pack import IndustryPackEngine
from mcoi_runtime.core.industry_pack_integration import IndustryPackIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def pack_engine(spine: EventSpineEngine) -> IndustryPackEngine:
    return IndustryPackEngine(spine)


@pytest.fixture()
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(pack_engine: IndustryPackEngine, spine: EventSpineEngine, memory: MemoryMeshEngine) -> IndustryPackIntegration:
    return IndustryPackIntegration(pack_engine, spine, memory)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_rejects_bad_pack_engine(self, spine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            IndustryPackIntegration("bad", spine, memory)

    def test_rejects_bad_event_spine(self, pack_engine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            IndustryPackIntegration(pack_engine, "bad", memory)

    def test_rejects_bad_memory_engine(self, pack_engine, spine):
        with pytest.raises(RuntimeCoreInvariantError):
            IndustryPackIntegration(pack_engine, spine, "bad")


# ---------------------------------------------------------------------------
# Bridge methods
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_pack_from_regulated_operations(self, bridge: IndustryPackIntegration, pack_engine: IndustryPackEngine):
        result = bridge.pack_from_regulated_operations("t1", "reg-1")
        assert result["pack_id"] == "reg-1"
        assert result["domain"] == "regulated_ops"
        assert result["capability_count"] == 10
        assert result["source_type"] == "regulated_operations"
        assert pack_engine.pack_count == 1

    def test_pack_from_research_operations(self, bridge: IndustryPackIntegration, pack_engine: IndustryPackEngine):
        result = bridge.pack_from_research_operations("t1", "res-1")
        assert result["pack_id"] == "res-1"
        assert result["domain"] == "research_lab"
        assert result["source_type"] == "research_operations"
        assert result["capability_count"] >= 5
        assert pack_engine.pack_count == 1

    def test_pack_from_factory_operations(self, bridge: IndustryPackIntegration, pack_engine: IndustryPackEngine):
        result = bridge.pack_from_factory_operations("t1", "fac-1")
        assert result["pack_id"] == "fac-1"
        assert result["domain"] == "factory_quality"
        assert result["source_type"] == "factory_operations"
        assert result["capability_count"] >= 5

    def test_pack_from_financial_control(self, bridge: IndustryPackIntegration, pack_engine: IndustryPackEngine):
        result = bridge.pack_from_financial_control("t1", "fin-1")
        assert result["pack_id"] == "fin-1"
        assert result["domain"] == "financial_control"
        assert result["source_type"] == "financial_control"
        assert result["capability_count"] >= 5

    def test_pack_from_enterprise_service(self, bridge: IndustryPackIntegration, pack_engine: IndustryPackEngine):
        result = bridge.pack_from_enterprise_service("t1", "ent-1")
        assert result["pack_id"] == "ent-1"
        assert result["domain"] == "enterprise_service"
        assert result["source_type"] == "enterprise_service"
        assert result["capability_count"] >= 5


# ---------------------------------------------------------------------------
# Memory mesh
# ---------------------------------------------------------------------------


class TestMemoryMesh:
    def test_attach_pack_state_to_memory_mesh(self, bridge: IndustryPackIntegration, memory: MemoryMeshEngine):
        bridge.pack_from_regulated_operations("t1", "reg-1")
        record = bridge.attach_pack_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert "industry_pack" in record.tags
        assert "deployment" in record.tags
        assert "operations" in record.tags
        assert memory.memory_count >= 1


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


class TestGraph:
    def test_attach_pack_state_to_graph(self, bridge: IndustryPackIntegration):
        bridge.pack_from_regulated_operations("t1", "reg-1")
        result = bridge.attach_pack_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_packs"] == 1
        assert result["total_capabilities"] == 10
