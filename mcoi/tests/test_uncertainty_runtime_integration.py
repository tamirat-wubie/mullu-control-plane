"""Purpose: integration tests for UncertaintyRuntimeIntegration.
Governance scope: runtime-integration tests only.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.uncertainty_runtime import UncertaintyRuntimeEngine
from mcoi_runtime.core.uncertainty_runtime_integration import UncertaintyRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> UncertaintyRuntimeEngine:
    return UncertaintyRuntimeEngine(spine)


@pytest.fixture()
def integration(
    engine: UncertaintyRuntimeEngine,
    spine: EventSpineEngine,
    memory: MemoryMeshEngine,
) -> UncertaintyRuntimeIntegration:
    return UncertaintyRuntimeIntegration(engine, spine, memory)


class TestConstructor:
    def test_valid_construction(self, integration: UncertaintyRuntimeIntegration) -> None:
        assert integration is not None

    def test_bad_engine_raises(self, spine: EventSpineEngine, memory: MemoryMeshEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            UncertaintyRuntimeIntegration(None, spine, memory)  # type: ignore[arg-type]


class TestCrossDomainMethods:
    def test_uncertainty_from_forecasting(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_forecasting("b-1", "t-1", "fc-1")
        assert result["source_type"] == "forecasting"
        assert result["belief_id"] == "b-1"

    def test_uncertainty_from_research(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_research("b-2", "t-1", "r-1")
        assert result["source_type"] == "research"

    def test_uncertainty_from_copilot(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_copilot("b-3", "t-1", "cp-1")
        assert result["source_type"] == "copilot"

    def test_uncertainty_from_executive_reporting(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_executive_reporting("b-4", "t-1", "rp-1")
        assert result["source_type"] == "executive_reporting"

    def test_uncertainty_from_assurance(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_assurance("b-5", "t-1", "as-1")
        assert result["source_type"] == "assurance"

    def test_uncertainty_from_policy_simulation(self, integration: UncertaintyRuntimeIntegration) -> None:
        result = integration.uncertainty_from_policy_simulation("b-6", "t-1", "ps-1")
        assert result["source_type"] == "policy_simulation"


class TestMemoryMeshAndGraph:
    def test_attach_to_memory_mesh(self, integration: UncertaintyRuntimeIntegration) -> None:
        integration.uncertainty_from_forecasting("b-1", "t-1", "fc-1")
        mem = integration.attach_uncertainty_to_memory_mesh("scope-1")
        assert mem.memory_id
        assert mem.title == "Uncertainty state"
        assert "scope-1" not in mem.title
        assert mem.scope_ref_id == "scope-1"
        assert "uncertainty" in mem.tags

    def test_attach_to_graph(self, integration: UncertaintyRuntimeIntegration) -> None:
        integration.uncertainty_from_forecasting("b-1", "t-1", "fc-1")
        graph = integration.attach_uncertainty_to_graph("scope-1")
        assert graph["total_beliefs"] == 1
