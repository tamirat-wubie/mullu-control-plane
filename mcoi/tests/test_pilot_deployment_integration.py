"""Tests for PilotDeploymentIntegration bridge.

Governance scope: comprehensive coverage for bridge methods, memory mesh
attachment, and graph attachment.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.pilot_deployment import PilotDeploymentEngine
from mcoi_runtime.core.pilot_deployment_integration import PilotDeploymentIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
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
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture()
def pilot_engine(spine: EventSpineEngine, clock: FixedClock) -> PilotDeploymentEngine:
    return PilotDeploymentEngine(spine, clock=clock)


@pytest.fixture()
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(pilot_engine: PilotDeploymentEngine, spine: EventSpineEngine, memory: MemoryMeshEngine) -> PilotDeploymentIntegration:
    return PilotDeploymentIntegration(pilot_engine, spine, memory)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_rejects_bad_pilot_engine(self, spine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            PilotDeploymentIntegration("bad", spine, memory)

    def test_rejects_bad_event_spine(self, pilot_engine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            PilotDeploymentIntegration(pilot_engine, "bad", memory)

    def test_rejects_bad_memory_engine(self, pilot_engine, spine):
        with pytest.raises(RuntimeCoreInvariantError):
            PilotDeploymentIntegration(pilot_engine, spine, "bad")


# ---------------------------------------------------------------------------
# Deploy bridge methods
# ---------------------------------------------------------------------------


class TestDeployMethods:
    def test_deploy_regulated_ops_pilot(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        result = bridge.deploy_regulated_ops_pilot("t1", "b-reg", "p-reg")
        assert result["tenant_id"] == "t1"
        assert result["bootstrap_id"] == "b-reg"
        assert result["pilot_id"] == "p-reg"
        assert result["bootstrap_status"] == "pending"
        assert result["pilot_phase"] == "setup"
        assert result["source_type"] == "regulated_ops_pilot"
        assert pilot_engine.bootstrap_count == 1
        assert pilot_engine.pilot_count == 1

    def test_deploy_research_pilot(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        result = bridge.deploy_research_pilot("t1", "b-res", "p-res")
        assert result["source_type"] == "research_pilot"
        assert pilot_engine.bootstrap_count == 1

    def test_deploy_factory_pilot(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        result = bridge.deploy_factory_pilot("t1", "b-fac", "p-fac")
        assert result["source_type"] == "factory_pilot"
        assert pilot_engine.bootstrap_count == 1

    def test_deploy_enterprise_service_pilot(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        result = bridge.deploy_enterprise_service_pilot("t1", "b-ent", "p-ent")
        assert result["source_type"] == "enterprise_service_pilot"
        assert pilot_engine.bootstrap_count == 1

    def test_deploy_financial_control_pilot(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        result = bridge.deploy_financial_control_pilot("t1", "b-fin", "p-fin")
        assert result["source_type"] == "financial_control_pilot"
        assert pilot_engine.bootstrap_count == 1

    def test_all_five_deploy_types(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        bridge.deploy_regulated_ops_pilot("t1", "b1", "p1")
        bridge.deploy_research_pilot("t2", "b2", "p2")
        bridge.deploy_factory_pilot("t3", "b3", "p3")
        bridge.deploy_enterprise_service_pilot("t4", "b4", "p4")
        bridge.deploy_financial_control_pilot("t5", "b5", "p5")
        assert pilot_engine.bootstrap_count == 5
        assert pilot_engine.pilot_count == 5


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_attach_to_memory_mesh(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine, memory: MemoryMeshEngine):
        bridge.deploy_regulated_ops_pilot("t1", "b1", "p1")
        mem = bridge.attach_pilot_state_to_memory_mesh("t1")
        assert isinstance(mem, MemoryRecord)
        assert mem.title == "Pilot deployment state"
        assert "t1" not in mem.title
        assert mem.scope_ref_id == "t1"
        assert mem.tags == ("pilot", "deployment", "bootstrap")
        assert memory.memory_count >= 1

    def test_memory_content_counts(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        bridge.deploy_regulated_ops_pilot("t1", "b1", "p1")
        pilot_engine.activate_connector("a1", "t1", "http", "https://x.com")
        mem = bridge.attach_pilot_state_to_memory_mesh("t1")
        content = mem.content
        assert content["total_bootstraps"] == 1
        assert content["total_connectors"] == 1
        assert content["total_pilots"] == 1


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_attach_to_graph(self, bridge: PilotDeploymentIntegration, pilot_engine: PilotDeploymentEngine):
        bridge.deploy_regulated_ops_pilot("t1", "b1", "p1")
        graph = bridge.attach_pilot_state_to_graph("t1")
        assert graph["scope_ref_id"] == "t1"
        assert graph["total_bootstraps"] == 1
        assert graph["total_pilots"] == 1

    def test_graph_empty_state(self, bridge: PilotDeploymentIntegration):
        graph = bridge.attach_pilot_state_to_graph("t1")
        assert graph["total_bootstraps"] == 0
        assert graph["total_violations"] == 0
