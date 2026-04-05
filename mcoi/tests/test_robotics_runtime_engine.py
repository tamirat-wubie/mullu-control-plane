"""Tests for robotics runtime engine (Phase 118).

Covers: RoboticsRuntimeEngine workcells, actuators, sensors, tasks, interlocks,
        sequences, emergency stop, violation detection, snapshots, state hashing,
        and golden scenarios.
"""

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.robotics_runtime import RoboticsRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.robotics_runtime import (
    ActuatorStatus,
    ControlMode,
    SafetyInterlockStatus,
    SensorStatus,
    TaskExecutionStatus,
)


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _fixed_clock():
    return lambda: FIXED_TS


def _make_engine(*, clock=None):
    es = EventSpineEngine()
    eng = RoboticsRuntimeEngine(es, clock=clock or _fixed_clock())
    return eng, es


# ===================================================================
# Constructor
# ===================================================================

class TestConstructor:
    def test_valid_event_spine(self):
        eng, _ = _make_engine()
        assert eng.cell_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            RoboticsRuntimeEngine("not_an_engine")

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = RoboticsRuntimeEngine(es)
        assert eng.cell_count == 0

    def test_custom_clock(self):
        eng, _ = _make_engine(clock=lambda: "2025-01-01T00:00:00+00:00")
        c = eng.register_workcell("c1", "t1", "Cell A")
        assert c.created_at == "2025-01-01T00:00:00+00:00"


# ===================================================================
# Workcells
# ===================================================================

class TestWorkcells:
    def test_register_workcell(self):
        eng, _ = _make_engine()
        c = eng.register_workcell("c1", "t1", "Cell A")
        assert c.cell_id == "c1"
        assert c.actuator_count == 0
        assert c.sensor_count == 0
        assert eng.cell_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_workcell("c1", "t1", "Cell A")

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        assert es.event_count >= 1


# ===================================================================
# Actuators
# ===================================================================

class TestActuators:
    def test_register_actuator(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        a = eng.register_actuator("a1", "t1", "Arm A", "c1")
        assert a.actuator_id == "a1"
        assert a.status == ActuatorStatus.IDLE
        assert eng.actuator_count == 1

    def test_actuator_increments_cell_count(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_actuator("a1", "t1", "Arm A", "c1")
        # Internal cell actuator_count should be 1 now
        eng.register_actuator("a2", "t1", "Arm B", "c1")
        assert eng.actuator_count == 2

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_actuator("a1", "t1", "Arm A", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_actuator("a1", "t1", "Arm A", "c1")

    def test_unknown_cell_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.register_actuator("a1", "t1", "Arm A", "nope")


# ===================================================================
# Sensors
# ===================================================================

class TestSensors:
    def test_register_sensor(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        s = eng.register_sensor("s1", "t1", "Proximity", "c1")
        assert s.sensor_id == "s1"
        assert s.status == SensorStatus.ONLINE
        assert eng.sensor_count == 1

    def test_sensor_increments_cell_count(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_sensor("s1", "t1", "Proximity", "c1")
        eng.register_sensor("s2", "t1", "Temperature", "c1")
        assert eng.sensor_count == 2

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_sensor("s1", "t1", "Proximity", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_sensor("s1", "t1", "Proximity", "c1")

    def test_unknown_cell_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.register_sensor("s1", "t1", "Proximity", "nope")


# ===================================================================
# Control Tasks
# ===================================================================

class TestControlTasks:
    def test_create_task(self):
        eng, _ = _make_engine()
        t = eng.create_control_task("t1", "t1", "Pick Task", "c1")
        assert t.task_id == "t1"
        assert t.status == TaskExecutionStatus.QUEUED
        assert eng.task_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.create_control_task("t1", "t1", "Pick Task", "c1")

    def test_start_task(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        t = eng.start_task("t1")
        assert t.status == TaskExecutionStatus.RUNNING

    def test_start_non_queued_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="QUEUED"):
            eng.start_task("t1")

    def test_complete_task(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        t = eng.complete_task("t1")
        assert t.status == TaskExecutionStatus.COMPLETED

    def test_complete_non_running_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING"):
            eng.complete_task("t1")

    def test_abort_task(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        t = eng.abort_task("t1")
        assert t.status == TaskExecutionStatus.ABORTED

    def test_fault_task(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        t = eng.fault_task("t1")
        assert t.status == TaskExecutionStatus.FAULTED

    def test_terminal_blocks_further_transitions(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        eng.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.abort_task("t1")

    def test_abort_terminal_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.abort_task("t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.fault_task("t1")

    def test_unknown_task_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.start_task("nope")

    def test_task_with_mode(self):
        eng, _ = _make_engine()
        t = eng.create_control_task("t1", "t1", "Auto Task", "c1",
                                    mode=ControlMode.AUTOMATIC)
        assert t.mode == ControlMode.AUTOMATIC

    def test_full_lifecycle(self):
        eng, es = _make_engine()
        t = eng.create_control_task("t1", "t1", "Pick Task", "c1")
        assert t.status == TaskExecutionStatus.QUEUED
        t = eng.start_task("t1")
        assert t.status == TaskExecutionStatus.RUNNING
        t = eng.complete_task("t1")
        assert t.status == TaskExecutionStatus.COMPLETED
        assert es.event_count >= 3


# ===================================================================
# Safety Interlocks
# ===================================================================

class TestSafetyInterlocks:
    def test_arm_interlock(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        il = eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        assert il.interlock_id == "il1"
        assert il.status == SafetyInterlockStatus.ARMED
        assert eng.interlock_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.arm_interlock("il1", "t1", "c1", "Safety boundary")

    def test_unknown_cell_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.arm_interlock("il1", "t1", "nope", "Safety boundary")

    def test_trigger_interlock(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        il = eng.trigger_interlock("il1")
        assert il.status == SafetyInterlockStatus.TRIGGERED

    def test_trigger_emergency_stops_tasks(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        eng.trigger_interlock("il1")
        # Task should be emergency stopped (ABORTED with EMERGENCY_STOP mode)
        t = eng._get_task("t1")
        assert t.status == TaskExecutionStatus.ABORTED
        assert t.mode == ControlMode.EMERGENCY_STOP

    def test_bypass_interlock(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        il = eng.bypass_interlock("il1")
        assert il.status == SafetyInterlockStatus.BYPASSED

    def test_clear_interlock(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        il = eng.clear_interlock("il1")
        assert il.status == SafetyInterlockStatus.CLEARED

    def test_unknown_interlock_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.trigger_interlock("nope")


# ===================================================================
# Control Sequences
# ===================================================================

class TestControlSequences:
    def test_create_sequence(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        seq = eng.create_control_sequence("seq1", "t1", "t1", 5)
        assert seq.sequence_id == "seq1"
        assert seq.step_count == 5
        assert seq.completed_steps == 0
        assert eng.sequence_count == 1

    def test_sequence_increments_task_count(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.create_control_sequence("seq1", "t1", "t1", 5)
        t = eng._get_task("t1")
        assert t.sequence_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.create_control_sequence("seq1", "t1", "t1", 5)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.create_control_sequence("seq1", "t1", "t1", 5)

    def test_unknown_task_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.create_control_sequence("seq1", "t1", "nope", 5)

    def test_advance_sequence(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.create_control_sequence("seq1", "t1", "t1", 3)
        seq = eng.advance_sequence("seq1")
        assert seq.completed_steps == 1

    def test_advance_fully_completed_rejected(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.create_control_sequence("seq1", "t1", "t1", 2)
        eng.advance_sequence("seq1")
        eng.advance_sequence("seq1")
        with pytest.raises(RuntimeCoreInvariantError, match="fully completed"):
            eng.advance_sequence("seq1")

    def test_unknown_sequence_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.advance_sequence("nope")


# ===================================================================
# Assessment
# ===================================================================

class TestAssessment:
    def test_basic_assessment(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        a = eng.robotics_assessment("a1", "t1")
        assert a.total_cells == 1

    def test_availability_rate(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_actuator("a1", "t1", "Arm A", "c1")
        eng.register_actuator("a2", "t1", "Arm B", "c1")
        a = eng.robotics_assessment("a1", "t1")
        assert a.availability_rate == 1.0

    def test_no_actuators_zero_rate(self):
        eng, _ = _make_engine()
        a = eng.robotics_assessment("a1", "t1")
        assert a.availability_rate == 0.0


# ===================================================================
# Snapshot
# ===================================================================

class TestSnapshot:
    def test_basic_snapshot(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        s = eng.robotics_snapshot("s1", "t1")
        assert s.total_cells == 1

    def test_duplicate_snapshot_rejected(self):
        eng, _ = _make_engine()
        eng.robotics_snapshot("s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.robotics_snapshot("s1", "t1")

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        snap = eng.snapshot()
        assert "cells" in snap


# ===================================================================
# Closure report
# ===================================================================

class TestClosureReport:
    def test_basic_closure(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        c = eng.robotics_closure_report("cr1", "t1")
        assert c.total_cells == 1


# ===================================================================
# Violation detection
# ===================================================================

class TestViolationDetection:
    def test_no_violations_empty(self):
        eng, _ = _make_engine()
        v = eng.detect_robotics_violations()
        assert len(v) == 0

    def test_bypassed_interlock(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.arm_interlock("il1", "t1", "c1", "Safety boundary")
        eng.bypass_interlock("il1")
        v = eng.detect_robotics_violations()
        assert any(x["operation"] == "bypassed_interlock" for x in v)

    def test_task_without_sequence(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        v = eng.detect_robotics_violations()
        assert any(x["operation"] == "task_without_sequence" for x in v)

    def test_faulted_actuator_in_active_cell(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_actuator("a1", "t1", "Arm A", "c1")
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        # Manually set actuator to faulted by replacing
        from mcoi_runtime.contracts.robotics_runtime import ActuatorRecord
        old = eng._actuators["a1"]
        faulted = ActuatorRecord(
            actuator_id=old.actuator_id, tenant_id=old.tenant_id,
            display_name=old.display_name, cell_ref=old.cell_ref,
            status=ActuatorStatus.FAULTED, created_at=old.created_at,
        )
        eng._actuators["a1"] = faulted
        v = eng.detect_robotics_violations()
        assert any(x["operation"] == "faulted_actuator_in_active_cell" for x in v)

    def test_idempotency(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        v1 = eng.detect_robotics_violations()
        assert len(v1) > 0
        v2 = eng.detect_robotics_violations()
        assert len(v2) == 0

    def test_violation_count_incremented(self):
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.detect_robotics_violations()
        assert eng.violation_count > 0


# ===================================================================
# State hash
# ===================================================================

class TestStateHash:
    def test_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_after_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_workcell("c1", "t1", "Cell A")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        eng1.register_workcell("c1", "t1", "Cell A")
        eng2.register_workcell("c1", "t1", "Cell A")
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# Golden scenarios
# ===================================================================

class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        """Full robotics lifecycle: cell, actuator, sensor, task, sequence."""
        eng, es = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.register_actuator("a1", "t1", "Arm A", "c1")
        eng.register_sensor("s1", "t1", "Proximity", "c1")
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.create_control_sequence("seq1", "t1", "t1", 3)
        eng.start_task("t1")
        eng.advance_sequence("seq1")
        eng.advance_sequence("seq1")
        eng.advance_sequence("seq1")
        eng.complete_task("t1")
        t = eng._get_task("t1")
        assert t.status == TaskExecutionStatus.COMPLETED
        assert es.event_count >= 9

    def test_cross_tenant_denied(self):
        """Assessment scoped to tenant."""
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        a = eng.robotics_assessment("a1", "t-other")
        assert a.total_cells == 0

    def test_terminal_state_blocking(self):
        """COMPLETED blocks further transitions."""
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        eng.start_task("t1")
        eng.complete_task("t1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.abort_task("t1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.fault_task("t1")

    def test_violation_detection_idempotency(self):
        """First call detects, second returns empty."""
        eng, _ = _make_engine()
        eng.create_control_task("t1", "t1", "Pick Task", "c1")
        v1 = eng.detect_robotics_violations()
        assert len(v1) > 0
        v2 = eng.detect_robotics_violations()
        assert len(v2) == 0

    def test_state_hash_determinism(self):
        """Two engines with identical operations produce identical state hashes."""
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        for eng in (eng1, eng2):
            eng.register_workcell("c1", "t1", "Cell A")
            eng.register_actuator("a1", "t1", "Arm A", "c1")
            eng.create_control_task("t1", "t1", "Pick Task", "c1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_consistency(self):
        """Replay with same clock produces consistent state."""
        eng1, _ = _make_engine()
        eng1.register_workcell("c1", "t1", "Cell A")
        eng1.register_actuator("a1", "t1", "Arm A", "c1")
        eng1.create_control_task("t1", "t1", "Pick Task", "c1")
        eng1.start_task("t1")
        eng2, _ = _make_engine()
        eng2.register_workcell("c1", "t1", "Cell A")
        eng2.register_actuator("a1", "t1", "Arm A", "c1")
        eng2.create_control_task("t1", "t1", "Pick Task", "c1")
        eng2.start_task("t1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_interlock_emergency_stop(self):
        """Triggering an interlock emergency-stops all tasks in cell."""
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.create_control_task("t1", "t1", "Task A", "c1")
        eng.create_control_task("t2", "t1", "Task B", "c1")
        eng.start_task("t1")
        eng.start_task("t2")
        eng.arm_interlock("il1", "t1", "c1", "Emergency")
        eng.trigger_interlock("il1")
        assert eng._get_task("t1").status == TaskExecutionStatus.ABORTED
        assert eng._get_task("t2").status == TaskExecutionStatus.ABORTED


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids_or_statuses(self):
        eng, _ = _make_engine()
        eng.register_workcell("cell-secret", "t1", "Cell A")

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            eng.register_workcell("cell-secret", "t1", "Cell A")
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "Duplicate cell_id"
        assert "cell-secret" not in duplicate_message
        assert "cell_id" in duplicate_message

        eng.create_control_task("task-secret", "t1", "Task A", "c1")
        eng.start_task("task-secret")
        eng.complete_task("task-secret")
        with pytest.raises(RuntimeCoreInvariantError) as terminal_exc:
            eng.abort_task("task-secret")
        terminal_message = str(terminal_exc.value)
        assert terminal_message == "Cannot transition task in terminal status"
        assert "completed" not in terminal_message
        assert "task-secret" not in terminal_message

    def test_violation_reasons_are_bounded(self):
        eng, _ = _make_engine()
        eng.register_workcell("c1", "t1", "Cell A")
        eng.create_control_task("task-no-seq", "t1", "Task A", "c1")
        eng.arm_interlock("il-secret", "t1", "c1", "Safety")
        eng.bypass_interlock("il-secret")

        violations = {v["operation"]: v["reason"] for v in eng.detect_robotics_violations()}
        assert violations["task_without_sequence"] == "Task has no sequences"
        assert "task-no-seq" not in violations["task_without_sequence"]
        assert "sequences" in violations["task_without_sequence"]

        assert violations["bypassed_interlock"] == "Interlock bypassed"
        assert "il-secret" not in violations["bypassed_interlock"]
        assert "bypassed" in violations["bypassed_interlock"]
