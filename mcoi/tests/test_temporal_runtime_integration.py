"""Purpose: integration tests for TemporalRuntimeIntegration.
Governance scope: runtime-integration tests only.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_runtime_integration import TemporalRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> TemporalRuntimeEngine:
    return TemporalRuntimeEngine(spine)


@pytest.fixture()
def integration(
    engine: TemporalRuntimeEngine,
    spine: EventSpineEngine,
    memory: MemoryMeshEngine,
) -> TemporalRuntimeIntegration:
    return TemporalRuntimeIntegration(engine, spine, memory)


class TestConstructor:
    def test_valid_construction(self, integration: TemporalRuntimeIntegration) -> None:
        assert integration is not None

    def test_bad_engine_raises(self, spine: EventSpineEngine, memory: MemoryMeshEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            TemporalRuntimeIntegration(None, spine, memory)  # type: ignore[arg-type]


class TestCrossDomainMethods:
    def test_temporal_from_contracts_sla(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_contracts_sla("e-1", "t-1", "ct-1", NOW)
        assert result["source_type"] == "contracts_sla"
        assert result["event_id"] == "e-1"

    def test_temporal_from_remediation(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_remediation("e-2", "t-1", "rem-1", NOW)
        assert result["source_type"] == "remediation"

    def test_temporal_from_continuity(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_continuity("e-3", "t-1", "cont-1", NOW)
        assert result["source_type"] == "continuity"

    def test_temporal_from_records_legal_hold(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_records_legal_hold("e-4", "t-1", "hold-1", NOW)
        assert result["source_type"] == "records_legal_hold"

    def test_temporal_from_executive_reporting(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_executive_reporting("e-5", "t-1", "rp-1", NOW)
        assert result["source_type"] == "executive_reporting"

    def test_temporal_from_research_studies(self, integration: TemporalRuntimeIntegration) -> None:
        result = integration.temporal_from_research_studies("e-6", "t-1", "study-1", NOW)
        assert result["source_type"] == "research_studies"


class TestMemoryMeshAndGraph:
    def test_attach_to_memory_mesh(self, integration: TemporalRuntimeIntegration) -> None:
        integration.temporal_from_contracts_sla("e-1", "t-1", "ct-1", NOW)
        mem = integration.attach_temporal_to_memory_mesh("scope-1")
        assert mem.memory_id
        assert "temporal" in mem.tags

    def test_attach_to_graph(self, integration: TemporalRuntimeIntegration) -> None:
        integration.temporal_from_contracts_sla("e-1", "t-1", "ct-1", NOW)
        graph = integration.attach_temporal_to_graph("scope-1")
        assert graph["total_events"] == 1
