"""Purpose: comprehensive tests for the process simulation runtime.
Governance scope: validate contracts (enums, frozen dataclasses, field constraints),
    engine lifecycle (models, parameters, scenarios, runs, results, envelopes,
    violations, assessments, snapshots, closure reports), and integration bridge.
Dependencies: pytest, mcoi_runtime process_simulation_runtime contracts/engine/integration.
Invariants:
  - All dataclasses are frozen and reject mutation.
  - Enum fields reject non-enum values.
  - Required text fields reject empty strings.
  - Datetime fields reject non-ISO-8601 strings.
  - Numeric fields respect their range constraints.
  - Float fields reject bool, inf, nan but allow negative.
  - Terminal run states block further transitions.
  - Violation detection is idempotent.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.process_simulation_runtime import (
    ConstraintEnvelope,
    PhysicalConstraintStatus,
    PhysicalParameter,
    ProcessAssessment,
    ProcessClosureReport,
    ProcessModel,
    ProcessModelKind,
    ProcessRiskLevel,
    ProcessSimulationStatus,
    ProcessSnapshot,
    ProcessViolation,
    SimulationDisposition,
    SimulationOutcomeKind,
    SimulationResult,
    SimulationRun,
    SimulationScenario,
)
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.process_simulation_runtime import ProcessSimulationRuntimeEngine
from mcoi_runtime.core.process_simulation_runtime_integration import (
    ProcessSimulationRuntimeIntegration,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DT = "2026-01-01T00:00:00+00:00"
DT2 = "2026-01-01T01:00:00+00:00"


def _make_engine() -> tuple[ProcessSimulationRuntimeEngine, EventSpineEngine, FixedClock]:
    clock = FixedClock(DT)
    es = EventSpineEngine()
    engine = ProcessSimulationRuntimeEngine(es, clock=clock)
    return engine, es, clock


def _make_integration() -> tuple[
    ProcessSimulationRuntimeIntegration,
    ProcessSimulationRuntimeEngine,
    EventSpineEngine,
    MemoryMeshEngine,
]:
    clock = FixedClock(DT)
    es = EventSpineEngine()
    engine = ProcessSimulationRuntimeEngine(es, clock=clock)
    mem = MemoryMeshEngine()
    integration = ProcessSimulationRuntimeIntegration(engine, es, mem)
    return integration, engine, es, mem


# ===================================================================
# Contract enum tests
# ===================================================================


class TestProcessSimulationStatusEnum:
    def test_member_count(self):
        assert len(ProcessSimulationStatus) == 5

    def test_members(self):
        assert ProcessSimulationStatus.CONFIGURED.value == "configured"
        assert ProcessSimulationStatus.RUNNING.value == "running"
        assert ProcessSimulationStatus.COMPLETED.value == "completed"
        assert ProcessSimulationStatus.FAILED.value == "failed"
        assert ProcessSimulationStatus.CANCELLED.value == "cancelled"


class TestProcessModelKindEnum:
    def test_member_count(self):
        assert len(ProcessModelKind) == 6

    def test_members(self):
        assert ProcessModelKind.THROUGHPUT.value == "throughput"
        assert ProcessModelKind.THERMAL.value == "thermal"
        assert ProcessModelKind.FLOW.value == "flow"
        assert ProcessModelKind.TIMING.value == "timing"
        assert ProcessModelKind.YIELD.value == "yield"
        assert ProcessModelKind.DEGRADATION.value == "degradation"


class TestSimulationDispositionEnum:
    def test_member_count(self):
        assert len(SimulationDisposition) == 5

    def test_members(self):
        assert SimulationDisposition.NOMINAL.value == "nominal"
        assert SimulationDisposition.STRESSED.value == "stressed"
        assert SimulationDisposition.DEGRADED.value == "degraded"
        assert SimulationDisposition.FAILURE.value == "failure"
        assert SimulationDisposition.RECOVERY.value == "recovery"


class TestPhysicalConstraintStatusEnum:
    def test_member_count(self):
        assert len(PhysicalConstraintStatus) == 4

    def test_members(self):
        assert PhysicalConstraintStatus.WITHIN_ENVELOPE.value == "within_envelope"
        assert PhysicalConstraintStatus.WARNING.value == "warning"
        assert PhysicalConstraintStatus.BREACH.value == "breach"
        assert PhysicalConstraintStatus.CRITICAL.value == "critical"


class TestProcessRiskLevelEnum:
    def test_member_count(self):
        assert len(ProcessRiskLevel) == 4

    def test_members(self):
        assert ProcessRiskLevel.LOW.value == "low"
        assert ProcessRiskLevel.MEDIUM.value == "medium"
        assert ProcessRiskLevel.HIGH.value == "high"
        assert ProcessRiskLevel.CRITICAL.value == "critical"


class TestSimulationOutcomeKindEnum:
    def test_member_count(self):
        assert len(SimulationOutcomeKind) == 4

    def test_members(self):
        assert SimulationOutcomeKind.PASS.value == "pass"
        assert SimulationOutcomeKind.MARGINAL.value == "marginal"
        assert SimulationOutcomeKind.FAIL.value == "fail"
        assert SimulationOutcomeKind.UNSAFE.value == "unsafe"


# ===================================================================
# Contract dataclass tests
# ===================================================================


class TestProcessModelContract:
    def test_valid_construction(self):
        m = ProcessModel(
            model_id="m1", tenant_id="t1", display_name="Test Model",
            kind=ProcessModelKind.THERMAL, parameter_count=3, created_at=DT,
        )
        assert m.model_id == "m1"
        assert m.kind == ProcessModelKind.THERMAL
        assert m.parameter_count == 3

    def test_frozen(self):
        m = ProcessModel(
            model_id="m1", tenant_id="t1", display_name="X",
            kind=ProcessModelKind.FLOW, parameter_count=0, created_at=DT,
        )
        with pytest.raises(AttributeError):
            m.model_id = "other"

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError):
            ProcessModel(
                model_id="", tenant_id="t1", display_name="X",
                kind=ProcessModelKind.FLOW, parameter_count=0, created_at=DT,
            )

    def test_negative_parameter_count_rejected(self):
        with pytest.raises(ValueError):
            ProcessModel(
                model_id="m1", tenant_id="t1", display_name="X",
                kind=ProcessModelKind.FLOW, parameter_count=-1, created_at=DT,
            )

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            ProcessModel(
                model_id="m1", tenant_id="t1", display_name="X",
                kind=ProcessModelKind.FLOW, parameter_count=0, created_at="not-a-date",
            )

    def test_to_dict(self):
        m = ProcessModel(
            model_id="m1", tenant_id="t1", display_name="X",
            kind=ProcessModelKind.FLOW, parameter_count=0, created_at=DT,
        )
        d = m.to_dict()
        assert d["model_id"] == "m1"
        assert d["kind"] == ProcessModelKind.FLOW

    def test_to_json(self):
        m = ProcessModel(
            model_id="m1", tenant_id="t1", display_name="X",
            kind=ProcessModelKind.FLOW, parameter_count=0, created_at=DT,
        )
        j = m.to_json()
        assert '"m1"' in j

    def test_metadata_frozen(self):
        m = ProcessModel(
            model_id="m1", tenant_id="t1", display_name="X",
            kind=ProcessModelKind.FLOW, parameter_count=0, created_at=DT,
            metadata={"a": 1},
        )
        assert isinstance(m.metadata, MappingProxyType)


class TestPhysicalParameterContract:
    def test_valid_construction(self):
        p = PhysicalParameter(
            parameter_id="p1", tenant_id="t1", model_ref="m1",
            name="temperature", value=100.5, unit="C", created_at=DT,
        )
        assert p.value == 100.5
        assert p.unit == "C"

    def test_negative_value_allowed(self):
        p = PhysicalParameter(
            parameter_id="p1", tenant_id="t1", model_ref="m1",
            name="delta", value=-42.5, unit="K", created_at=DT,
        )
        assert p.value == -42.5

    def test_bool_value_rejected(self):
        with pytest.raises(ValueError):
            PhysicalParameter(
                parameter_id="p1", tenant_id="t1", model_ref="m1",
                name="x", value=True, unit="m", created_at=DT,
            )

    def test_inf_value_rejected(self):
        with pytest.raises(ValueError):
            PhysicalParameter(
                parameter_id="p1", tenant_id="t1", model_ref="m1",
                name="x", value=float("inf"), unit="m", created_at=DT,
            )

    def test_nan_value_rejected(self):
        with pytest.raises(ValueError):
            PhysicalParameter(
                parameter_id="p1", tenant_id="t1", model_ref="m1",
                name="x", value=float("nan"), unit="m", created_at=DT,
            )

    def test_frozen(self):
        p = PhysicalParameter(
            parameter_id="p1", tenant_id="t1", model_ref="m1",
            name="x", value=1.0, unit="m", created_at=DT,
        )
        with pytest.raises(AttributeError):
            p.value = 2.0


class TestSimulationScenarioContract:
    def test_valid_construction(self):
        s = SimulationScenario(
            scenario_id="s1", tenant_id="t1", model_ref="m1",
            disposition=SimulationDisposition.STRESSED, description="test", created_at=DT,
        )
        assert s.disposition == SimulationDisposition.STRESSED

    def test_frozen(self):
        s = SimulationScenario(
            scenario_id="s1", tenant_id="t1", model_ref="m1",
            disposition=SimulationDisposition.NOMINAL, description="x", created_at=DT,
        )
        with pytest.raises(AttributeError):
            s.scenario_id = "other"


class TestSimulationRunContract:
    def test_valid_construction(self):
        r = SimulationRun(
            run_id="r1", tenant_id="t1", scenario_ref="s1",
            status=ProcessSimulationStatus.RUNNING, duration_ms=0.0, created_at=DT,
        )
        assert r.status == ProcessSimulationStatus.RUNNING

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError):
            SimulationRun(
                run_id="r1", tenant_id="t1", scenario_ref="s1",
                status=ProcessSimulationStatus.RUNNING, duration_ms=-1.0, created_at=DT,
            )

    def test_frozen(self):
        r = SimulationRun(
            run_id="r1", tenant_id="t1", scenario_ref="s1",
            status=ProcessSimulationStatus.RUNNING, duration_ms=0.0, created_at=DT,
        )
        with pytest.raises(AttributeError):
            r.status = ProcessSimulationStatus.COMPLETED


class TestSimulationResultContract:
    def test_valid_construction(self):
        sr = SimulationResult(
            result_id="sr1", tenant_id="t1", run_ref="r1",
            outcome=SimulationOutcomeKind.PASS,
            expected_value=1.0, actual_value=1.1, deviation=0.1, created_at=DT,
        )
        assert sr.deviation == 0.1

    def test_negative_deviation_allowed(self):
        sr = SimulationResult(
            result_id="sr1", tenant_id="t1", run_ref="r1",
            outcome=SimulationOutcomeKind.FAIL,
            expected_value=10.0, actual_value=5.0, deviation=-5.0, created_at=DT,
        )
        assert sr.deviation == -5.0

    def test_bool_expected_rejected(self):
        with pytest.raises(ValueError):
            SimulationResult(
                result_id="sr1", tenant_id="t1", run_ref="r1",
                outcome=SimulationOutcomeKind.PASS,
                expected_value=True, actual_value=1.0, deviation=0.0, created_at=DT,
            )


class TestConstraintEnvelopeContract:
    def test_valid_construction(self):
        ce = ConstraintEnvelope(
            envelope_id="ce1", tenant_id="t1", parameter_ref="p1",
            min_value=0.0, max_value=100.0, target_value=50.0,
            status=PhysicalConstraintStatus.WITHIN_ENVELOPE, created_at=DT,
        )
        assert ce.status == PhysicalConstraintStatus.WITHIN_ENVELOPE

    def test_negative_min_allowed(self):
        ce = ConstraintEnvelope(
            envelope_id="ce1", tenant_id="t1", parameter_ref="p1",
            min_value=-50.0, max_value=50.0, target_value=0.0,
            status=PhysicalConstraintStatus.WITHIN_ENVELOPE, created_at=DT,
        )
        assert ce.min_value == -50.0


class TestProcessAssessmentContract:
    def test_valid_construction(self):
        pa = ProcessAssessment(
            assessment_id="a1", tenant_id="t1",
            total_models=5, total_runs=10, total_violations=2,
            safety_score=0.8, assessed_at=DT,
        )
        assert pa.safety_score == 0.8

    def test_safety_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            ProcessAssessment(
                assessment_id="a1", tenant_id="t1",
                total_models=0, total_runs=0, total_violations=0,
                safety_score=1.5, assessed_at=DT,
            )

    def test_safety_score_negative_rejected(self):
        with pytest.raises(ValueError):
            ProcessAssessment(
                assessment_id="a1", tenant_id="t1",
                total_models=0, total_runs=0, total_violations=0,
                safety_score=-0.1, assessed_at=DT,
            )


class TestProcessViolationContract:
    def test_valid_construction(self):
        pv = ProcessViolation(
            violation_id="v1", tenant_id="t1",
            operation="breach", reason="over temp", detected_at=DT,
        )
        assert pv.operation == "breach"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            ProcessViolation(
                violation_id="v1", tenant_id="t1",
                operation="breach", reason="", detected_at=DT,
            )


class TestProcessSnapshotContract:
    def test_valid_construction(self):
        ps = ProcessSnapshot(
            snapshot_id="s1", tenant_id="t1",
            total_models=1, total_parameters=2, total_scenarios=3,
            total_runs=4, total_envelopes=5, total_violations=0, captured_at=DT,
        )
        assert ps.total_envelopes == 5


class TestProcessClosureReportContract:
    def test_valid_construction(self):
        cr = ProcessClosureReport(
            report_id="cr1", tenant_id="t1",
            total_models=1, total_runs=2, total_results=3,
            total_violations=0, created_at=DT,
        )
        assert cr.total_results == 3


# ===================================================================
# Engine tests
# ===================================================================


class TestEngineConstruction:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ProcessSimulationRuntimeEngine("not-an-engine")

    def test_initial_counts_are_zero(self):
        engine, _, _ = _make_engine()
        assert engine.model_count == 0
        assert engine.parameter_count == 0
        assert engine.scenario_count == 0
        assert engine.run_count == 0
        assert engine.result_count == 0
        assert engine.envelope_count == 0
        assert engine.violation_count == 0


class TestProcessModelEngine:
    def test_register_model(self):
        engine, _, _ = _make_engine()
        m = engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        assert m.model_id == "m1"
        assert m.kind == ProcessModelKind.THERMAL
        assert engine.model_count == 1

    def test_duplicate_model_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_process_model("m1", "t1", "Test2", ProcessModelKind.FLOW)

    def test_get_model(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        m = engine.get_model("m1")
        assert m.display_name == "Test"

    def test_get_unknown_model_raises(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_model("nonexistent")


class TestPhysicalParameterEngine:
    def test_register_parameter(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        p = engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.5, "C")
        assert p.value == 100.5
        assert engine.parameter_count == 1

    def test_parameter_increments_model_count(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_physical_parameter("p2", "t1", "m1", "pressure", 50.0, "Pa")
        m = engine.get_model("m1")
        assert m.parameter_count == 2

    def test_parameter_requires_model(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown model"):
            engine.register_physical_parameter("p1", "t1", "nonexistent", "x", 1.0, "m")

    def test_duplicate_parameter_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_physical_parameter("p1", "t1", "m1", "press", 50.0, "Pa")


class TestConstraintEnvelopeEngine:
    def test_register_within_envelope(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        env = engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 200.0, 100.0)
        assert env.status == PhysicalConstraintStatus.WITHIN_ENVELOPE
        assert engine.envelope_count == 1

    def test_register_warning_near_boundary(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        # span=100, 10% threshold=10, target=5 is within 10 of min(0)
        env = engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 5.0)
        assert env.status == PhysicalConstraintStatus.WARNING

    def test_register_breach_outside(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        # target outside [0, 100]
        env = engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 110.0)
        assert env.status == PhysicalConstraintStatus.BREACH

    def test_register_critical_way_outside(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        # span=100, 50% threshold=50, target=200 > max+50=150
        env = engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 200.0)
        assert env.status == PhysicalConstraintStatus.CRITICAL

    def test_requires_parameter(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown parameter"):
            engine.register_constraint_envelope("e1", "t1", "nonexistent", 0.0, 100.0, 50.0)

    def test_duplicate_envelope_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 200.0, 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 200.0, 100.0)


class TestSimulationScenarioEngine:
    def test_register_scenario(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        s = engine.register_simulation_scenario("s1", "t1", "m1")
        assert s.disposition == SimulationDisposition.NOMINAL
        assert engine.scenario_count == 1

    def test_register_with_disposition(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        s = engine.register_simulation_scenario(
            "s1", "t1", "m1", disposition=SimulationDisposition.STRESSED,
        )
        assert s.disposition == SimulationDisposition.STRESSED

    def test_requires_model(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown model"):
            engine.register_simulation_scenario("s1", "t1", "nonexistent")

    def test_duplicate_scenario_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_simulation_scenario("s1", "t1", "m1")


class TestSimulationRunEngine:
    def test_run_simulation(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        r = engine.run_simulation("r1", "t1", "s1")
        assert r.status == ProcessSimulationStatus.RUNNING
        assert r.duration_ms == 0.0
        assert engine.run_count == 1

    def test_complete_simulation(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        r = engine.complete_simulation("r1", 150.5)
        assert r.status == ProcessSimulationStatus.COMPLETED
        assert r.duration_ms == 150.5

    def test_fail_simulation(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        r = engine.fail_simulation("r1")
        assert r.status == ProcessSimulationStatus.FAILED

    def test_terminal_guard_complete(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.complete_simulation("r1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_simulation("r1", 200.0)

    def test_terminal_guard_fail_after_complete(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.complete_simulation("r1", 100.0)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_simulation("r1")

    def test_terminal_guard_complete_after_fail(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.fail_simulation("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_simulation("r1", 100.0)

    def test_requires_scenario(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown scenario"):
            engine.run_simulation("r1", "t1", "nonexistent")

    def test_duplicate_run_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.run_simulation("r1", "t1", "s1")


class TestSimulationResultEngine:
    def test_record_result(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        sr = engine.record_simulation_result(
            "sr1", "t1", "r1", SimulationOutcomeKind.PASS, 10.0, 10.5,
        )
        assert sr.deviation == pytest.approx(0.5)
        assert engine.result_count == 1

    def test_auto_deviation(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        sr = engine.record_simulation_result(
            "sr1", "t1", "r1", SimulationOutcomeKind.FAIL, 100.0, 50.0,
        )
        assert sr.deviation == pytest.approx(-50.0)

    def test_requires_run(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown run"):
            engine.record_simulation_result(
                "sr1", "t1", "nonexistent", SimulationOutcomeKind.PASS, 1.0, 1.0,
            )

    def test_duplicate_result_rejected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0)


class TestCompareActualToModel:
    def test_within_envelope(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 200.0, 100.0)
        status = engine.compare_actual_to_model("p1", 100.0)
        assert status == PhysicalConstraintStatus.WITHIN_ENVELOPE

    def test_warning_near_boundary(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        # actual=2 is within 10% of min(0), threshold=10
        status = engine.compare_actual_to_model("p1", 2.0)
        assert status == PhysicalConstraintStatus.WARNING

    def test_breach_outside(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        status = engine.compare_actual_to_model("p1", 110.0)
        assert status == PhysicalConstraintStatus.BREACH

    def test_critical_way_outside(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        # span=100, 50% threshold=50, actual=200 > max+50=150
        status = engine.compare_actual_to_model("p1", 200.0)
        assert status == PhysicalConstraintStatus.CRITICAL

    def test_no_envelope_raises(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        with pytest.raises(RuntimeCoreInvariantError, match="No envelope"):
            engine.compare_actual_to_model("p1", 100.0)

    def test_unknown_parameter_raises(self):
        engine, _, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown parameter"):
            engine.compare_actual_to_model("nonexistent", 100.0)


class TestProcessAssessmentEngine:
    def test_no_results_gives_perfect_score(self):
        engine, _, _ = _make_engine()
        a = engine.assess_process_state("a1", "t1")
        assert a.safety_score == 1.0
        assert a.total_models == 0

    def test_all_passes(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0)
        a = engine.assess_process_state("a1", "t1")
        assert a.safety_score == 1.0

    def test_mixed_results(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0)
        engine.run_simulation("r2", "t1", "s1")
        engine.record_simulation_result("sr2", "t1", "r2", SimulationOutcomeKind.FAIL, 1.0, 5.0)
        a = engine.assess_process_state("a1", "t1")
        assert a.safety_score == pytest.approx(0.5)

    def test_tenant_isolation(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.FAIL, 1.0, 5.0)
        # t2 has no results
        a = engine.assess_process_state("a2", "t2")
        assert a.safety_score == 1.0
        assert a.total_models == 0


class TestSimulateFailureMode:
    def test_creates_failure_scenario(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        s = engine.simulate_failure_mode("sf1", "t1", "m1")
        assert s.disposition == SimulationDisposition.FAILURE
        assert engine.scenario_count == 1


class TestProcessSnapshotEngine:
    def test_snapshot(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 100.0, "C")
        engine.register_simulation_scenario("s1", "t1", "m1")
        snap = engine.process_snapshot("snap1", "t1")
        assert snap.total_models == 1
        assert snap.total_parameters == 1
        assert snap.total_scenarios == 1
        assert snap.total_runs == 0
        assert snap.total_envelopes == 0
        assert snap.total_violations == 0


class TestProcessClosureReportEngine:
    def test_closure_report(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result("sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0)
        cr = engine.process_closure_report("cr1", "t1")
        assert cr.total_models == 1
        assert cr.total_runs == 1
        assert cr.total_results == 1
        assert cr.total_violations == 0


class TestViolationDetection:
    def test_envelope_breach_detected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        # Register parameter with value outside future envelope
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 150.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        violations = engine.detect_process_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "envelope_breach"

    def test_failed_run_no_result_detected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.fail_simulation("r1")
        violations = engine.detect_process_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "failed_run_no_result"

    def test_unsafe_outcome_detected(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.record_simulation_result(
            "sr1", "t1", "r1", SimulationOutcomeKind.UNSAFE, 1.0, 99.0,
        )
        violations = engine.detect_process_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "unsafe_outcome"

    def test_idempotent(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.fail_simulation("r1")
        v1 = engine.detect_process_violations("t1")
        v2 = engine.detect_process_violations("t1")
        assert len(v1) == 1
        assert len(v2) == 0  # already detected
        assert engine.violation_count == 1

    def test_no_violations_when_clean(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 50.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.complete_simulation("r1", 100.0)
        engine.record_simulation_result(
            "sr1", "t1", "r1", SimulationOutcomeKind.PASS, 1.0, 1.0,
        )
        violations = engine.detect_process_violations("t1")
        assert len(violations) == 0

    def test_multiple_violations(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        # Envelope breach
        engine.register_physical_parameter("p1", "t1", "m1", "temp", 150.0, "C")
        engine.register_constraint_envelope("e1", "t1", "p1", 0.0, 100.0, 50.0)
        # Failed run no result
        engine.register_simulation_scenario("s1", "t1", "m1")
        engine.run_simulation("r1", "t1", "s1")
        engine.fail_simulation("r1")
        # Unsafe outcome
        engine.run_simulation("r2", "t1", "s1")
        engine.record_simulation_result(
            "sr1", "t1", "r2", SimulationOutcomeKind.UNSAFE, 1.0, 99.0,
        )
        violations = engine.detect_process_violations("t1")
        assert len(violations) == 3
        ops = {v.operation for v in violations}
        assert ops == {"envelope_breach", "failed_run_no_result", "unsafe_outcome"}


class TestEngineStateHash:
    def test_state_hash_is_64_chars(self):
        engine, _, _ = _make_engine()
        h = engine.state_hash()
        assert len(h) == 64

    def test_state_hash_changes_after_mutation(self):
        engine, _, _ = _make_engine()
        h1 = engine.state_hash()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_deterministic(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


class TestEngineSnapshot:
    def test_snapshot_structure(self):
        engine, _, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        snap = engine.snapshot()
        assert "models" in snap
        assert "parameters" in snap
        assert "scenarios" in snap
        assert "runs" in snap
        assert "results" in snap
        assert "envelopes" in snap
        assert "violations" in snap
        assert "_state_hash" in snap
        assert "m1" in snap["models"]

    def test_collections_returns_all(self):
        engine, _, _ = _make_engine()
        cols = engine._collections()
        assert len(cols) == 7


class TestEventsEmitted:
    def test_model_emits_event(self):
        engine, es, _ = _make_engine()
        before = es.event_count
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        assert es.event_count > before

    def test_run_lifecycle_emits_events(self):
        engine, es, _ = _make_engine()
        engine.register_process_model("m1", "t1", "Test", ProcessModelKind.THERMAL)
        engine.register_simulation_scenario("s1", "t1", "m1")
        before = es.event_count
        engine.run_simulation("r1", "t1", "s1")
        engine.complete_simulation("r1", 100.0)
        assert es.event_count >= before + 2


# ===================================================================
# Integration bridge tests
# ===================================================================


class TestIntegrationConstruction:
    def test_requires_simulation_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ProcessSimulationRuntimeIntegration("not-an-engine", es, mem)

    def test_requires_event_spine(self):
        es = EventSpineEngine()
        engine = ProcessSimulationRuntimeEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            ProcessSimulationRuntimeIntegration(engine, "not-es", mem)

    def test_requires_memory_engine(self):
        es = EventSpineEngine()
        engine = ProcessSimulationRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            ProcessSimulationRuntimeIntegration(engine, es, "not-mem")


class TestIntegrationSourceMethods:
    def test_simulation_from_factory_runtime(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_factory_runtime("t1", "factory-001")
        assert result["source_type"] == "factory_runtime"
        assert result["tenant_id"] == "t1"
        assert engine.model_count == 1
        assert engine.scenario_count == 1
        assert engine.run_count == 1

    def test_simulation_from_digital_twin(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_digital_twin("t1", "twin-001")
        assert result["source_type"] == "digital_twin"
        assert result["kind"] == "thermal"

    def test_simulation_from_asset_runtime(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_asset_runtime("t1", "asset-001")
        assert result["source_type"] == "asset_runtime"
        assert result["kind"] == "degradation"

    def test_simulation_from_quality_events(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_quality_events("t1", "quality-001")
        assert result["source_type"] == "quality_events"
        assert result["kind"] == "yield"

    def test_simulation_from_continuity_runtime(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_continuity_runtime("t1", "cont-001")
        assert result["source_type"] == "continuity_runtime"
        assert result["kind"] == "flow"

    def test_simulation_from_forecasting_runtime(self):
        integration, engine, _, _ = _make_integration()
        result = integration.simulation_from_forecasting_runtime("t1", "forecast-001")
        assert result["source_type"] == "forecasting_runtime"
        assert result["kind"] == "timing"

    def test_multiple_sources_create_distinct_models(self):
        integration, engine, _, _ = _make_integration()
        integration.simulation_from_factory_runtime("t1", "f1")
        integration.simulation_from_digital_twin("t1", "t1")
        integration.simulation_from_asset_runtime("t1", "a1")
        assert engine.model_count == 3
        assert engine.scenario_count == 3
        assert engine.run_count == 3


class TestIntegrationMemoryMesh:
    def test_attach_to_memory_mesh(self):
        integration, engine, _, mem = _make_integration()
        integration.simulation_from_factory_runtime("t1", "f1")
        record = integration.attach_process_state_to_memory_mesh("scope-1")
        assert record.memory_id
        assert record.tags == ("process_simulation", "physics", "engineering")
        assert mem.memory_count >= 1

    def test_memory_content_has_counts(self):
        integration, engine, _, _ = _make_integration()
        integration.simulation_from_factory_runtime("t1", "f1")
        record = integration.attach_process_state_to_memory_mesh("scope-1")
        content = dict(record.content)
        assert "total_models" in content
        assert content["total_models"] == 1


class TestIntegrationGraph:
    def test_attach_to_graph(self):
        integration, engine, _, _ = _make_integration()
        integration.simulation_from_factory_runtime("t1", "f1")
        graph = integration.attach_process_state_to_graph("scope-1")
        assert graph["scope_ref_id"] == "scope-1"
        assert graph["total_models"] == 1
        assert graph["total_runs"] == 1

    def test_graph_reflects_current_state(self):
        integration, engine, _, _ = _make_integration()
        integration.simulation_from_factory_runtime("t1", "f1")
        integration.simulation_from_digital_twin("t1", "t1")
        graph = integration.attach_process_state_to_graph("scope-1")
        assert graph["total_models"] == 2
        assert graph["total_scenarios"] == 2
