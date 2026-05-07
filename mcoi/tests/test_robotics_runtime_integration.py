"""Tests for robotics runtime integration bridge (Phase 118).

Covers: RoboticsRuntimeIntegration cross-domain creation, memory mesh
        attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.robotics_runtime import RoboticsRuntimeEngine
from mcoi_runtime.core.robotics_runtime_integration import RoboticsRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.contracts.robotics_runtime import TaskExecutionStatus


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_integration():
    es = EventSpineEngine()
    eng = RoboticsRuntimeEngine(es, clock=lambda: FIXED_TS)
    mem = MemoryMeshEngine()
    integ = RoboticsRuntimeIntegration(eng, es, mem)
    return integ, eng, es, mem


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_robotics_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RoboticsRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        eng = RoboticsRuntimeEngine(es, clock=lambda: FIXED_TS)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RoboticsRuntimeIntegration(eng, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        eng = RoboticsRuntimeEngine(es, clock=lambda: FIXED_TS)
        with pytest.raises(RuntimeCoreInvariantError):
            RoboticsRuntimeIntegration(eng, es, "bad")


# ===================================================================
# Cross-domain robotics creation
# ===================================================================

class TestRoboticsFromFactory:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_factory(
            "c1", "t1", "Cell A", "t1-task", "Pick Task", "c1",
        )
        assert result["cell_id"] == "c1"
        assert result["task_id"] == "t1-task"
        assert result["source_type"] == "factory"
        assert eng.cell_count == 1
        assert eng.task_count == 1

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.robotics_from_factory("c1", "t1", "Cell A", "t1-task", "Pick", "c1")
        assert es.event_count > before

    def test_duplicate_cell_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.robotics_from_factory("c1", "t1", "Cell A", "t1-task", "Pick", "c1")
        with pytest.raises(RuntimeCoreInvariantError):
            integ.robotics_from_factory("c1", "t1", "Cell B", "t2-task", "Place", "c1")

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        result = integ.robotics_from_factory(
            "c1", "t1", "Cell A", "t1-task", "Pick Task", "c1",
        )
        assert result["tenant_id"] == "t1"
        assert result["display_name"] == "Cell A"
        assert result["task_name"] == "Pick Task"
        assert result["target_ref"] == "c1"
        assert result["status"] == "queued"


class TestRoboticsFromDigitalTwin:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_digital_twin(
            "c1", "t1", "Cell A", "t1-task", "Pick", "c1",
        )
        assert result["source_type"] == "digital_twin"
        assert eng.cell_count == 1


class TestRoboticsFromAsset:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_asset(
            "c1", "t1", "Cell A", "t1-task", "Pick", "c1",
        )
        assert result["source_type"] == "asset"


class TestRoboticsFromContinuity:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_continuity(
            "c1", "t1", "Cell A", "t1-task", "Pick", "c1",
        )
        assert result["source_type"] == "continuity"


class TestRoboticsFromWorkforce:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_workforce(
            "c1", "t1", "Cell A", "t1-task", "Pick", "c1",
        )
        assert result["source_type"] == "workforce"


class TestRoboticsFromProcessSimulation:
    def test_creates_cell_and_task(self):
        integ, eng, _, _ = _make_integration()
        result = integ.robotics_from_process_simulation(
            "c1", "t1", "Cell A", "t1-task", "Pick", "c1",
        )
        assert result["source_type"] == "process_simulation"


# ===================================================================
# Memory mesh attachment
# ===================================================================

class TestMemoryMeshAttachment:
    def test_attach_to_memory(self):
        integ, eng, _, mem = _make_integration()
        eng.register_workcell("c1", "t1", "Cell A")
        record = integ.attach_robotics_state_to_memory_mesh("scope-1")
        assert record.memory_id
        assert record.title == "Robotics state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"
        assert mem.memory_count >= 1

    def test_memory_content(self):
        integ, eng, _, _ = _make_integration()
        eng.register_workcell("c1", "t1", "Cell A")
        record = integ.attach_robotics_state_to_memory_mesh("scope-1")
        assert record.title == "Robotics state"

    def test_emits_event(self):
        integ, eng, es, _ = _make_integration()
        eng.register_workcell("c1", "t1", "Cell A")
        before = es.event_count
        integ.attach_robotics_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# Graph attachment
# ===================================================================

class TestGraphAttachment:
    def test_attach_to_graph(self):
        integ, eng, _, _ = _make_integration()
        eng.register_workcell("c1", "t1", "Cell A")
        result = integ.attach_robotics_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_cells"] == 1

    def test_graph_reflects_violations(self):
        integ, eng, _, _ = _make_integration()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.detect_robotics_violations()
        result = integ.attach_robotics_state_to_graph("scope-1")
        assert result["total_violations"] > 0


# ===================================================================
# End-to-end integration
# ===================================================================

class TestEndToEnd:
    def test_full_workflow(self):
        integ, eng, es, mem = _make_integration()
        integ.robotics_from_factory("c1", "t1", "Cell A", "t1-task", "Pick", "c1")
        eng.start_task("t1-task")
        eng.complete_task("t1-task")
        integ.attach_robotics_state_to_memory_mesh("scope-1")
        assert mem.memory_count >= 1
        graph = integ.attach_robotics_state_to_graph("scope-1")
        assert graph["total_cells"] == 1
        assert graph["total_tasks"] == 1
        assert es.event_count >= 4

    def test_multiple_sources(self):
        integ, eng, _, _ = _make_integration()
        integ.robotics_from_factory("c1", "t1", "Cell A", "t1", "Pick", "c1")
        integ.robotics_from_digital_twin("c2", "t1", "Cell B", "t2", "Place", "c2")
        integ.robotics_from_asset("c3", "t1", "Cell C", "t3", "Weld", "c3")
        assert eng.cell_count == 3
        assert eng.task_count == 3
