"""Tests for experiment runtime integration bridge (Phase 114).

Covers: ExperimentRuntimeIntegration cross-domain creation, memory mesh
        attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.experiment_runtime import ExperimentRuntimeEngine
from mcoi_runtime.core.experiment_runtime_integration import ExperimentRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_integration():
    es = EventSpineEngine()
    clk = FixedClock(FIXED_TS)
    eng = ExperimentRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = ExperimentRuntimeIntegration(eng, es, mem)
    return integ, eng, es, mem


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_experiment_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExperimentRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        eng = ExperimentRuntimeEngine(es, clock=FixedClock(FIXED_TS))
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ExperimentRuntimeIntegration(eng, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        eng = ExperimentRuntimeEngine(es, clock=FixedClock(FIXED_TS))
        with pytest.raises(RuntimeCoreInvariantError):
            ExperimentRuntimeIntegration(eng, es, "bad")


# ===================================================================
# Cross-domain experiment creation
# ===================================================================

class TestExperimentFromResearch:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")
        assert result["design_id"] == "d1"
        assert result["source_type"] == "research"
        assert eng.design_count == 1

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")
        assert es.event_count > before

    def test_duplicate_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")
        with pytest.raises(RuntimeCoreInvariantError):
            integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        result = integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")
        assert result["tenant_id"] == "t1"
        assert result["hypothesis_ref"] == "h1"
        assert result["research_ref"] == "res1"
        assert result["phase"] == "design"


class TestExperimentFromSelfTuning:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_self_tuning("d1", "t1", "h1", "tune1", "Tuning Experiment")
        assert result["source_type"] == "self_tuning"
        assert result["tuning_ref"] == "tune1"
        assert eng.design_count == 1


class TestExperimentFromPolicySimulation:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_policy_simulation("d1", "t1", "h1", "pol1", "Policy Exp")
        assert result["source_type"] == "policy_simulation"
        assert result["policy_sim_ref"] == "pol1"


class TestExperimentFromQualityEvents:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_quality_events("d1", "t1", "h1", "q1", "Quality Exp")
        assert result["source_type"] == "quality_events"
        assert result["quality_ref"] == "q1"


class TestExperimentFromProcessSimulation:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_process_simulation("d1", "t1", "h1", "ps1", "Process Exp")
        assert result["source_type"] == "process_simulation"
        assert result["process_sim_ref"] == "ps1"


class TestExperimentFromForecasting:
    def test_creates_design(self):
        integ, eng, _, _ = _make_integration()
        result = integ.experiment_from_forecasting("d1", "t1", "h1", "fc1", "Forecast Exp")
        assert result["source_type"] == "forecasting"
        assert result["forecast_ref"] == "fc1"


# ===================================================================
# Memory mesh attachment
# ===================================================================

class TestMemoryMeshAttachment:
    def test_attach_to_memory(self):
        integ, eng, _, mem = _make_integration()
        eng.register_design("d1", "t1", "h1", "Design 1")
        record = integ.attach_experiment_to_memory_mesh("scope-1")
        assert record.memory_id
        assert mem.memory_count >= 1

    def test_memory_content(self):
        integ, eng, _, _ = _make_integration()
        eng.register_design("d1", "t1", "h1", "Design 1")
        record = integ.attach_experiment_to_memory_mesh("scope-1")
        assert record.title.startswith("Experiment state:")

    def test_emits_event(self):
        integ, eng, es, _ = _make_integration()
        eng.register_design("d1", "t1", "h1", "Design 1")
        before = es.event_count
        integ.attach_experiment_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# Graph attachment
# ===================================================================

class TestGraphAttachment:
    def test_attach_to_graph(self):
        integ, eng, _, _ = _make_integration()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.add_variable("v1", "t1", "d1", "Temp")
        result = integ.attach_experiment_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_designs"] == 1
        assert result["total_variables"] == 1

    def test_graph_reflects_violations(self):
        integ, eng, _, _ = _make_integration()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.detect_experiment_violations()
        result = integ.attach_experiment_to_graph("scope-1")
        assert result["total_violations"] > 0


# ===================================================================
# End-to-end integration
# ===================================================================

class TestEndToEnd:
    def test_full_workflow(self):
        integ, eng, es, mem = _make_integration()
        # Create from research
        integ.experiment_from_research("d1", "t1", "h1", "res1", "Design 1")
        # Add variable and group
        eng.add_variable("v1", "t1", "d1", "Temp")
        eng.add_control_group("g1", "t1", "d1", "Control A")
        # Run experiment
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        eng.complete_experiment("d1")
        # Attach to memory
        integ.attach_experiment_to_memory_mesh("scope-1")
        assert mem.memory_count >= 1
        # Check graph
        graph = integ.attach_experiment_to_graph("scope-1")
        assert graph["total_designs"] == 1
        assert es.event_count >= 5

    def test_multiple_sources(self):
        integ, eng, _, _ = _make_integration()
        integ.experiment_from_research("d1", "t1", "h1", "res1", "From Research")
        integ.experiment_from_self_tuning("d2", "t1", "h2", "tune1", "From Tuning")
        integ.experiment_from_forecasting("d3", "t1", "h3", "fc1", "From Forecast")
        assert eng.design_count == 3
