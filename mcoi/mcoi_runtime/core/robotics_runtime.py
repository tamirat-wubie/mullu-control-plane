"""Purpose: robotics / control runtime engine.
Governance scope: registering workcells, actuators, sensors; managing control
    tasks and sequences; arming/triggering/bypassing/clearing interlocks;
    detecting robotics violations; producing immutable snapshots.
Dependencies: robotics_runtime contracts, event_spine, core invariants.
Invariants:
  - Terminal tasks cannot transition.
  - Trigger interlock auto emergency-stops all tasks in cell.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable

from ..contracts.robotics_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rob", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_TASK_TERMINAL = frozenset({
    TaskExecutionStatus.COMPLETED,
    TaskExecutionStatus.ABORTED,
    TaskExecutionStatus.FAULTED,
})


class RoboticsRuntimeEngine:
    """Robotics / control runtime engine."""

    def __init__(
        self,
        event_spine: EventSpineEngine,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _now_iso
        self._cells: dict[str, WorkcellRecord] = {}
        self._actuators: dict[str, ActuatorRecord] = {}
        self._sensors: dict[str, SensorRecord] = {}
        self._tasks: dict[str, ControlTask] = {}
        self._interlocks: dict[str, SafetyInterlock] = {}
        self._sequences: dict[str, ControlSequence] = {}
        self._decisions: dict[str, RoboticsDecision] = {}
        self._violations: dict[str, dict[str, Any]] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def cell_count(self) -> int:
        return len(self._cells)

    @property
    def actuator_count(self) -> int:
        return len(self._actuators)

    @property
    def sensor_count(self) -> int:
        return len(self._sensors)

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def interlock_count(self) -> int:
        return len(self._interlocks)

    @property
    def sequence_count(self) -> int:
        return len(self._sequences)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Workcells
    # ------------------------------------------------------------------

    def register_workcell(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
    ) -> WorkcellRecord:
        """Register a workcell."""
        if cell_id in self._cells:
            raise RuntimeCoreInvariantError("Duplicate cell_id")
        now = self._clock()
        cell = WorkcellRecord(
            cell_id=cell_id,
            tenant_id=tenant_id,
            display_name=display_name,
            actuator_count=0,
            sensor_count=0,
            created_at=now,
        )
        self._cells[cell_id] = cell
        _emit(self._events, "workcell_registered", {
            "cell_id": cell_id, "tenant_id": tenant_id,
        }, cell_id)
        return cell

    def _update_cell(self, cell_id: str, *, delta_actuators: int = 0, delta_sensors: int = 0) -> WorkcellRecord:
        old = self._cells[cell_id]
        updated = WorkcellRecord(
            cell_id=old.cell_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            actuator_count=old.actuator_count + delta_actuators,
            sensor_count=old.sensor_count + delta_sensors,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._cells[cell_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Actuators
    # ------------------------------------------------------------------

    def register_actuator(
        self,
        actuator_id: str,
        tenant_id: str,
        display_name: str,
        cell_ref: str,
    ) -> ActuatorRecord:
        """Register an actuator (increments cell actuator_count)."""
        if actuator_id in self._actuators:
            raise RuntimeCoreInvariantError("Duplicate actuator_id")
        if cell_ref not in self._cells:
            raise RuntimeCoreInvariantError("Unknown cell_ref")
        now = self._clock()
        act = ActuatorRecord(
            actuator_id=actuator_id,
            tenant_id=tenant_id,
            display_name=display_name,
            cell_ref=cell_ref,
            status=ActuatorStatus.IDLE,
            created_at=now,
        )
        self._actuators[actuator_id] = act
        self._update_cell(cell_ref, delta_actuators=1)
        _emit(self._events, "actuator_registered", {
            "actuator_id": actuator_id, "cell_ref": cell_ref,
        }, actuator_id)
        return act

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    def register_sensor(
        self,
        sensor_id: str,
        tenant_id: str,
        display_name: str,
        cell_ref: str,
    ) -> SensorRecord:
        """Register a sensor (increments cell sensor_count)."""
        if sensor_id in self._sensors:
            raise RuntimeCoreInvariantError("Duplicate sensor_id")
        if cell_ref not in self._cells:
            raise RuntimeCoreInvariantError("Unknown cell_ref")
        now = self._clock()
        sen = SensorRecord(
            sensor_id=sensor_id,
            tenant_id=tenant_id,
            display_name=display_name,
            cell_ref=cell_ref,
            status=SensorStatus.ONLINE,
            reading_count=0,
            created_at=now,
        )
        self._sensors[sensor_id] = sen
        self._update_cell(cell_ref, delta_sensors=1)
        _emit(self._events, "sensor_registered", {
            "sensor_id": sensor_id, "cell_ref": cell_ref,
        }, sensor_id)
        return sen

    # ------------------------------------------------------------------
    # Control Tasks
    # ------------------------------------------------------------------

    def create_control_task(
        self,
        task_id: str,
        tenant_id: str,
        display_name: str,
        target_ref: str,
        mode: ControlMode = ControlMode.MANUAL,
    ) -> ControlTask:
        """Create a control task (QUEUED)."""
        if task_id in self._tasks:
            raise RuntimeCoreInvariantError("Duplicate task_id")
        now = self._clock()
        task = ControlTask(
            task_id=task_id,
            tenant_id=tenant_id,
            display_name=display_name,
            target_ref=target_ref,
            mode=mode,
            status=TaskExecutionStatus.QUEUED,
            sequence_count=0,
            created_at=now,
        )
        self._tasks[task_id] = task
        _emit(self._events, "control_task_created", {
            "task_id": task_id, "tenant_id": tenant_id,
        }, task_id)
        return task

    def _get_task(self, task_id: str) -> ControlTask:
        t = self._tasks.get(task_id)
        if t is None:
            raise RuntimeCoreInvariantError("Unknown task_id")
        return t

    def _guard_terminal(self, task: ControlTask) -> None:
        if task.status in _TASK_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot transition task in terminal status")

    def _transition_task(self, task_id: str, new_status: TaskExecutionStatus) -> ControlTask:
        old = self._get_task(task_id)
        self._guard_terminal(old)
        updated = ControlTask(
            task_id=old.task_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            target_ref=old.target_ref,
            mode=old.mode,
            status=new_status,
            sequence_count=old.sequence_count,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, f"task_{new_status.value}", {
            "task_id": task_id,
        }, task_id)
        return updated

    def start_task(self, task_id: str) -> ControlTask:
        """Start a QUEUED task (transition to RUNNING)."""
        old = self._get_task(task_id)
        if old.status != TaskExecutionStatus.QUEUED:
            raise RuntimeCoreInvariantError("Can only start QUEUED tasks")
        return self._transition_task(task_id, TaskExecutionStatus.RUNNING)

    def complete_task(self, task_id: str) -> ControlTask:
        """Complete a RUNNING task."""
        old = self._get_task(task_id)
        if old.status != TaskExecutionStatus.RUNNING:
            raise RuntimeCoreInvariantError("Can only complete RUNNING tasks")
        return self._transition_task(task_id, TaskExecutionStatus.COMPLETED)

    def abort_task(self, task_id: str) -> ControlTask:
        """Abort a non-terminal task."""
        return self._transition_task(task_id, TaskExecutionStatus.ABORTED)

    def fault_task(self, task_id: str) -> ControlTask:
        """Fault a non-terminal task."""
        return self._transition_task(task_id, TaskExecutionStatus.FAULTED)

    def _emergency_stop_task(self, task_id: str) -> ControlTask:
        """Force a task to ABORTED (for emergency stop via interlock)."""
        old = self._get_task(task_id)
        if old.status in _TASK_TERMINAL:
            return old  # already terminal, no-op
        updated = ControlTask(
            task_id=old.task_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            target_ref=old.target_ref,
            mode=ControlMode.EMERGENCY_STOP,
            status=TaskExecutionStatus.ABORTED,
            sequence_count=old.sequence_count,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._tasks[task_id] = updated
        _emit(self._events, "task_emergency_stopped", {
            "task_id": task_id,
        }, task_id)
        return updated

    # ------------------------------------------------------------------
    # Safety Interlocks
    # ------------------------------------------------------------------

    def arm_interlock(
        self,
        interlock_id: str,
        tenant_id: str,
        cell_ref: str,
        reason: str,
    ) -> SafetyInterlock:
        """Arm a safety interlock (ARMED)."""
        if interlock_id in self._interlocks:
            raise RuntimeCoreInvariantError("Duplicate interlock_id")
        if cell_ref not in self._cells:
            raise RuntimeCoreInvariantError("Unknown cell_ref")
        now = self._clock()
        il = SafetyInterlock(
            interlock_id=interlock_id,
            tenant_id=tenant_id,
            cell_ref=cell_ref,
            status=SafetyInterlockStatus.ARMED,
            reason=reason,
            created_at=now,
        )
        self._interlocks[interlock_id] = il
        _emit(self._events, "interlock_armed", {
            "interlock_id": interlock_id, "cell_ref": cell_ref,
        }, interlock_id)
        return il

    def _transition_interlock(
        self, interlock_id: str, new_status: SafetyInterlockStatus,
    ) -> SafetyInterlock:
        old = self._interlocks.get(interlock_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown interlock_id")
        updated = SafetyInterlock(
            interlock_id=old.interlock_id,
            tenant_id=old.tenant_id,
            cell_ref=old.cell_ref,
            status=new_status,
            reason=old.reason,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._interlocks[interlock_id] = updated
        _emit(self._events, f"interlock_{new_status.value}", {
            "interlock_id": interlock_id,
        }, interlock_id)
        return updated

    def trigger_interlock(self, interlock_id: str) -> SafetyInterlock:
        """Trigger an interlock (TRIGGERED). Auto emergency-stops all tasks in cell."""
        il = self._transition_interlock(interlock_id, SafetyInterlockStatus.TRIGGERED)
        # Auto emergency-stop all tasks targeting this cell
        for task in list(self._tasks.values()):
            if task.target_ref == il.cell_ref and task.status not in _TASK_TERMINAL:
                self._emergency_stop_task(task.task_id)
        return il

    def bypass_interlock(self, interlock_id: str) -> SafetyInterlock:
        """Bypass an interlock (BYPASSED)."""
        return self._transition_interlock(interlock_id, SafetyInterlockStatus.BYPASSED)

    def clear_interlock(self, interlock_id: str) -> SafetyInterlock:
        """Clear an interlock (CLEARED)."""
        return self._transition_interlock(interlock_id, SafetyInterlockStatus.CLEARED)

    # ------------------------------------------------------------------
    # Control Sequences
    # ------------------------------------------------------------------

    def create_control_sequence(
        self,
        sequence_id: str,
        tenant_id: str,
        task_ref: str,
        step_count: int,
    ) -> ControlSequence:
        """Create a control sequence linked to a task."""
        if sequence_id in self._sequences:
            raise RuntimeCoreInvariantError("Duplicate sequence_id")
        self._get_task(task_ref)  # ensure task exists
        now = self._clock()
        seq = ControlSequence(
            sequence_id=sequence_id,
            tenant_id=tenant_id,
            task_ref=task_ref,
            step_count=step_count,
            completed_steps=0,
            created_at=now,
        )
        self._sequences[sequence_id] = seq
        # Increment task sequence_count
        task = self._tasks[task_ref]
        updated_task = ControlTask(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            display_name=task.display_name,
            target_ref=task.target_ref,
            mode=task.mode,
            status=task.status,
            sequence_count=task.sequence_count + 1,
            created_at=task.created_at,
            metadata=task.metadata,
        )
        self._tasks[task_ref] = updated_task
        _emit(self._events, "control_sequence_created", {
            "sequence_id": sequence_id, "task_ref": task_ref,
        }, sequence_id)
        return seq

    def advance_sequence(self, sequence_id: str) -> ControlSequence:
        """Advance a control sequence by one step."""
        old = self._sequences.get(sequence_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown sequence_id")
        if old.completed_steps >= old.step_count:
            raise RuntimeCoreInvariantError("Sequence already fully completed")
        updated = ControlSequence(
            sequence_id=old.sequence_id,
            tenant_id=old.tenant_id,
            task_ref=old.task_ref,
            step_count=old.step_count,
            completed_steps=old.completed_steps + 1,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._sequences[sequence_id] = updated
        _emit(self._events, "sequence_advanced", {
            "sequence_id": sequence_id, "completed_steps": updated.completed_steps,
        }, sequence_id)
        return updated

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def robotics_assessment(self, assessment_id: str, tenant_id: str) -> RoboticsAssessment:
        """Produce a tenant-scoped robotics assessment."""
        now = self._clock()
        t_cells = sum(1 for c in self._cells.values() if c.tenant_id == tenant_id)
        t_tasks = sum(1 for t in self._tasks.values() if t.tenant_id == tenant_id)
        t_actuators = sum(1 for a in self._actuators.values() if a.tenant_id == tenant_id)
        faulted = sum(
            1 for a in self._actuators.values()
            if a.tenant_id == tenant_id and a.status == ActuatorStatus.FAULTED
        )
        rate = (t_actuators - faulted) / t_actuators if t_actuators else 0.0
        assessment = RoboticsAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_cells=t_cells,
            total_tasks=t_tasks,
            total_faults=faulted,
            availability_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "robotics_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def robotics_snapshot(self, snapshot_id: str, tenant_id: str) -> RoboticsSnapshot:
        """Capture a tenant-scoped point-in-time robotics snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._clock()
        snap = RoboticsSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_cells=self.cell_count,
            total_actuators=self.actuator_count,
            total_sensors=self.sensor_count,
            total_tasks=self.task_count,
            total_interlocks=self.interlock_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "robotics_snapshot_captured", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def robotics_closure_report(self, report_id: str, tenant_id: str) -> RoboticsClosureReport:
        """Produce a tenant-scoped robotics closure report."""
        now = self._clock()
        faulted = sum(
            1 for a in self._actuators.values()
            if a.tenant_id == tenant_id and a.status == ActuatorStatus.FAULTED
        )
        report = RoboticsClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_cells=sum(1 for c in self._cells.values() if c.tenant_id == tenant_id),
            total_tasks=sum(1 for t in self._tasks.values() if t.tenant_id == tenant_id),
            total_faults=faulted,
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )
        _emit(self._events, "robotics_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_robotics_violations(self) -> tuple[dict[str, Any], ...]:
        """Detect robotics violations (idempotent).

        Rules:
        - faulted_actuator_in_active_cell: actuator is FAULTED in a cell with active tasks
        - bypassed_interlock: interlock is BYPASSED
        - task_without_sequence: task has 0 sequences
        """
        now = self._clock()
        new_violations: list[dict[str, Any]] = []

        # Rule: faulted actuator in active cell
        active_cells: set[str] = set()
        for task in self._tasks.values():
            if task.status == TaskExecutionStatus.RUNNING:
                active_cells.add(task.target_ref)
        for act in self._actuators.values():
            if act.status == ActuatorStatus.FAULTED and act.cell_ref in active_cells:
                vid = stable_identifier("viol-rob", {
                    "actuator": act.actuator_id, "op": "faulted_actuator_in_active_cell",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": act.tenant_id,
                        "operation": "faulted_actuator_in_active_cell",
                        "reason": "Faulted actuator in active cell",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Rule: bypassed interlock
        for il in self._interlocks.values():
            if il.status == SafetyInterlockStatus.BYPASSED:
                vid = stable_identifier("viol-rob", {
                    "interlock": il.interlock_id, "op": "bypassed_interlock",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": il.tenant_id,
                        "operation": "bypassed_interlock",
                        "reason": "Interlock bypassed",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Rule: task without sequence
        for task in self._tasks.values():
            if task.sequence_count == 0:
                vid = stable_identifier("viol-rob", {
                    "task": task.task_id, "op": "task_without_sequence",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": task.tenant_id,
                        "operation": "task_without_sequence",
                        "reason": "Task has no sequences",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "robotics_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "cells": self._cells,
            "actuators": self._actuators,
            "sensors": self._sensors,
            "tasks": self._tasks,
            "interlocks": self._interlocks,
            "sequences": self._sequences,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v for v in collection
                ]
            else:
                result[name] = collection
        return result

    def state_hash(self) -> str:
        """Compute a SHA-256 hash of the current engine state."""
        parts = sorted([
            f"actuators={self.actuator_count}",
            f"cells={self.cell_count}",
            f"interlocks={self.interlock_count}",
            f"sensors={self.sensor_count}",
            f"sequences={self.sequence_count}",
            f"tasks={self.task_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
