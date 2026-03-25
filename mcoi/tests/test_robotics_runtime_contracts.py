"""Tests for robotics runtime contracts (Phase 118).

Covers: ControlTask, ActuatorRecord, SensorRecord, SafetyInterlock,
        ControlSequence, WorkcellRecord, RoboticsDecision,
        RoboticsAssessment, RoboticsSnapshot, RoboticsClosureReport,
        and all related enums.
"""

import json
import math

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.robotics_runtime import (
    ActuatorRecord,
    ActuatorStatus,
    ControlMode,
    ControlSequence,
    ControlTask,
    RoboticsAssessment,
    RoboticsClosureReport,
    RoboticsDecision,
    RoboticsRiskLevel,
    RoboticsSnapshot,
    SafetyInterlock,
    SafetyInterlockStatus,
    SensorRecord,
    SensorStatus,
    TaskExecutionStatus,
    WorkcellRecord,
)


TS = "2025-06-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kw):
    defaults = dict(
        task_id="task-001", tenant_id="t-1", display_name="Pick Task",
        target_ref="cell-001", mode=ControlMode.MANUAL,
        status=TaskExecutionStatus.QUEUED, sequence_count=0, created_at=TS,
    )
    defaults.update(kw)
    return ControlTask(**defaults)


def _actuator(**kw):
    defaults = dict(
        actuator_id="act-001", tenant_id="t-1", display_name="Arm A",
        cell_ref="cell-001", status=ActuatorStatus.IDLE, created_at=TS,
    )
    defaults.update(kw)
    return ActuatorRecord(**defaults)


def _sensor(**kw):
    defaults = dict(
        sensor_id="sen-001", tenant_id="t-1", display_name="Proximity",
        cell_ref="cell-001", status=SensorStatus.ONLINE, reading_count=0,
        created_at=TS,
    )
    defaults.update(kw)
    return SensorRecord(**defaults)


def _interlock(**kw):
    defaults = dict(
        interlock_id="il-001", tenant_id="t-1", cell_ref="cell-001",
        status=SafetyInterlockStatus.ARMED, reason="Safety boundary",
        created_at=TS,
    )
    defaults.update(kw)
    return SafetyInterlock(**defaults)


def _sequence(**kw):
    defaults = dict(
        sequence_id="seq-001", tenant_id="t-1", task_ref="task-001",
        step_count=5, completed_steps=2, created_at=TS,
    )
    defaults.update(kw)
    return ControlSequence(**defaults)


def _workcell(**kw):
    defaults = dict(
        cell_id="cell-001", tenant_id="t-1", display_name="Cell A",
        actuator_count=3, sensor_count=2, created_at=TS,
    )
    defaults.update(kw)
    return WorkcellRecord(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="dec-001", tenant_id="t-1", task_ref="task-001",
        disposition="continue", reason="All clear", decided_at=TS,
    )
    defaults.update(kw)
    return RoboticsDecision(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="a-001", tenant_id="t-1", total_cells=3,
        total_tasks=10, total_faults=1, availability_rate=0.9,
        assessed_at=TS,
    )
    defaults.update(kw)
    return RoboticsAssessment(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-001", tenant_id="t-1", total_cells=3,
        total_actuators=9, total_sensors=6, total_tasks=10,
        total_interlocks=3, total_violations=1, captured_at=TS,
    )
    defaults.update(kw)
    return RoboticsSnapshot(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="cr-001", tenant_id="t-1", total_cells=3,
        total_tasks=10, total_faults=1, total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return RoboticsClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================

class TestControlModeEnum:
    def test_all_values(self):
        assert set(e.value for e in ControlMode) == {
            "manual", "semi_auto", "automatic", "emergency_stop",
        }
    def test_member_count(self):
        assert len(ControlMode) == 4

class TestActuatorStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in ActuatorStatus) == {
            "idle", "active", "faulted", "locked", "maintenance",
        }
    def test_member_count(self):
        assert len(ActuatorStatus) == 5

class TestSensorStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in SensorStatus) == {
            "online", "degraded", "offline", "calibrating",
        }
    def test_member_count(self):
        assert len(SensorStatus) == 4

class TestTaskExecutionStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in TaskExecutionStatus) == {
            "queued", "running", "completed", "aborted", "faulted",
        }
    def test_member_count(self):
        assert len(TaskExecutionStatus) == 5

class TestSafetyInterlockStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in SafetyInterlockStatus) == {
            "armed", "triggered", "bypassed", "cleared",
        }
    def test_member_count(self):
        assert len(SafetyInterlockStatus) == 4

class TestRoboticsRiskLevelEnum:
    def test_all_values(self):
        assert set(e.value for e in RoboticsRiskLevel) == {"low", "medium", "high", "critical"}


# ===================================================================
# ControlTask
# ===================================================================

class TestControlTask:
    def test_happy_path(self):
        t = _task()
        assert t.task_id == "task-001"
        assert t.mode == ControlMode.MANUAL
        assert t.status == TaskExecutionStatus.QUEUED

    def test_frozen(self):
        t = _task()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(t, "task_id", "x")

    def test_to_dict_preserves_enum(self):
        t = _task()
        data = t.to_dict()
        assert data["mode"] is ControlMode.MANUAL
        assert data["status"] is TaskExecutionStatus.QUEUED

    def test_to_json_dict_serializes_enum(self):
        t = _task()
        data = t.to_json_dict()
        assert data["mode"] == "manual"
        assert data["status"] == "queued"

    def test_to_json_roundtrip(self):
        t = _task()
        parsed = json.loads(t.to_json())
        assert parsed["task_id"] == "task-001"

    def test_metadata_frozen(self):
        t = _task(metadata={"k": "v"})
        with pytest.raises(TypeError):
            t.metadata["k2"] = "v2"

    @pytest.mark.parametrize("field,val", [
        ("task_id", ""), ("tenant_id", "  "), ("display_name", ""),
        ("target_ref", ""),
    ])
    def test_empty_text_rejected(self, field, val):
        with pytest.raises(ValueError):
            _task(**{field: val})

    def test_invalid_mode(self):
        with pytest.raises(ValueError):
            _task(mode="not_a_mode")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _task(status="not_a_status")

    def test_negative_sequence_count(self):
        with pytest.raises(ValueError):
            _task(sequence_count=-1)

    def test_bool_sequence_count(self):
        with pytest.raises(ValueError):
            _task(sequence_count=True)

    def test_bad_created_at(self):
        with pytest.raises(ValueError):
            _task(created_at="not-a-date")

    @pytest.mark.parametrize("mode", list(ControlMode))
    def test_all_modes_accepted(self, mode):
        t = _task(mode=mode)
        assert t.mode is mode

    @pytest.mark.parametrize("status", list(TaskExecutionStatus))
    def test_all_statuses_accepted(self, status):
        t = _task(status=status)
        assert t.status is status

    def test_equal_tasks(self):
        assert _task() == _task()

    def test_unequal_tasks(self):
        assert _task() != _task(task_id="task-002")


# ===================================================================
# ActuatorRecord
# ===================================================================

class TestActuatorRecord:
    def test_happy_path(self):
        a = _actuator()
        assert a.actuator_id == "act-001"
        assert a.status == ActuatorStatus.IDLE

    def test_frozen(self):
        a = _actuator()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "actuator_id", "x")

    @pytest.mark.parametrize("status", list(ActuatorStatus))
    def test_all_statuses(self, status):
        a = _actuator(status=status)
        assert a.status is status

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _actuator(status="bad")

    @pytest.mark.parametrize("field", ["actuator_id", "tenant_id", "display_name", "cell_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _actuator(**{field: ""})

    def test_to_dict(self):
        data = _actuator().to_dict()
        assert data["status"] is ActuatorStatus.IDLE


# ===================================================================
# SensorRecord
# ===================================================================

class TestSensorRecord:
    def test_happy_path(self):
        s = _sensor()
        assert s.sensor_id == "sen-001"
        assert s.status == SensorStatus.ONLINE

    def test_frozen(self):
        s = _sensor()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "sensor_id", "x")

    @pytest.mark.parametrize("status", list(SensorStatus))
    def test_all_statuses(self, status):
        s = _sensor(status=status)
        assert s.status is status

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _sensor(status="bad")

    def test_negative_reading_count(self):
        with pytest.raises(ValueError):
            _sensor(reading_count=-1)

    @pytest.mark.parametrize("field", ["sensor_id", "tenant_id", "display_name", "cell_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _sensor(**{field: ""})


# ===================================================================
# SafetyInterlock
# ===================================================================

class TestSafetyInterlock:
    def test_happy_path(self):
        il = _interlock()
        assert il.interlock_id == "il-001"
        assert il.status == SafetyInterlockStatus.ARMED

    def test_frozen(self):
        il = _interlock()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(il, "interlock_id", "x")

    @pytest.mark.parametrize("status", list(SafetyInterlockStatus))
    def test_all_statuses(self, status):
        il = _interlock(status=status)
        assert il.status is status

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _interlock(status="bad")

    @pytest.mark.parametrize("field", ["interlock_id", "tenant_id", "cell_ref", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _interlock(**{field: ""})


# ===================================================================
# ControlSequence
# ===================================================================

class TestControlSequence:
    def test_happy_path(self):
        s = _sequence()
        assert s.sequence_id == "seq-001"
        assert s.step_count == 5
        assert s.completed_steps == 2

    def test_frozen(self):
        s = _sequence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "sequence_id", "x")

    def test_negative_step_count(self):
        with pytest.raises(ValueError):
            _sequence(step_count=-1)

    def test_negative_completed_steps(self):
        with pytest.raises(ValueError):
            _sequence(completed_steps=-1)

    @pytest.mark.parametrize("field", ["sequence_id", "tenant_id", "task_ref"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _sequence(**{field: ""})


# ===================================================================
# WorkcellRecord
# ===================================================================

class TestWorkcellRecord:
    def test_happy_path(self):
        w = _workcell()
        assert w.cell_id == "cell-001"
        assert w.actuator_count == 3
        assert w.sensor_count == 2

    def test_frozen(self):
        w = _workcell()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(w, "cell_id", "x")

    def test_negative_actuator_count(self):
        with pytest.raises(ValueError):
            _workcell(actuator_count=-1)

    def test_negative_sensor_count(self):
        with pytest.raises(ValueError):
            _workcell(sensor_count=-1)

    @pytest.mark.parametrize("field", ["cell_id", "tenant_id", "display_name"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _workcell(**{field: ""})


# ===================================================================
# RoboticsDecision
# ===================================================================

class TestRoboticsDecision:
    def test_happy_path(self):
        d = _decision()
        assert d.decision_id == "dec-001"

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    @pytest.mark.parametrize("field", ["decision_id", "tenant_id", "task_ref", "disposition", "reason"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _decision(**{field: ""})


# ===================================================================
# RoboticsAssessment
# ===================================================================

class TestRoboticsAssessment:
    def test_happy_path(self):
        a = _assessment()
        assert a.assessment_id == "a-001"
        assert a.availability_rate == 0.9

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")

    def test_availability_rate_bounds(self):
        _assessment(availability_rate=0.0)
        _assessment(availability_rate=1.0)

    def test_availability_rate_over_rejected(self):
        with pytest.raises(ValueError):
            _assessment(availability_rate=1.1)

    def test_availability_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(availability_rate=-0.1)

    def test_negative_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_cells=-1)


# ===================================================================
# RoboticsSnapshot
# ===================================================================

class TestRoboticsSnapshot:
    def test_happy_path(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")

    @pytest.mark.parametrize("field", [
        "total_cells", "total_actuators", "total_sensors",
        "total_tasks", "total_interlocks", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})


# ===================================================================
# RoboticsClosureReport
# ===================================================================

class TestRoboticsClosureReport:
    def test_happy_path(self):
        c = _closure()
        assert c.report_id == "cr-001"

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "report_id", "x")

    @pytest.mark.parametrize("field", [
        "total_cells", "total_tasks", "total_faults", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    def test_to_json(self):
        parsed = json.loads(_closure().to_json())
        assert parsed["report_id"] == "cr-001"
