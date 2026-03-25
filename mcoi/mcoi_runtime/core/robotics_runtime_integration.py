"""Purpose: robotics runtime integration bridge.
Governance scope: composing robotics runtime with factory, digital twin,
    asset, continuity, workforce, and process simulation scopes; memory mesh
    and operational graph attachment.
Dependencies: robotics_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every robotics creation emits events.
  - Robotics state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.robotics_runtime import ControlMode
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .robotics_runtime import RoboticsRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class RoboticsRuntimeIntegration:
    """Integration bridge for robotics runtime with platform layers."""

    def __init__(
        self,
        robotics_engine: RoboticsRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(robotics_engine, RoboticsRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "robotics_engine must be a RoboticsRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._robotics = robotics_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Bridge helpers
    # ------------------------------------------------------------------

    def _bridge(
        self,
        source_type: str,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        source_ref: str,
    ) -> dict[str, Any]:
        cell = self._robotics.register_workcell(cell_id, tenant_id, display_name)
        task = self._robotics.create_control_task(
            task_id, tenant_id, task_name, target_ref,
        )
        _emit(self._events, f"robotics_from_{source_type}", {
            "cell_id": cell_id, "task_id": task_id, "source_ref": source_ref,
        }, cell_id)
        return {
            "cell_id": cell.cell_id,
            "tenant_id": cell.tenant_id,
            "display_name": cell.display_name,
            "task_id": task.task_id,
            "task_name": task.display_name,
            "target_ref": task.target_ref,
            "status": task.status.value,
            "source_type": source_type,
        }

    def robotics_from_factory(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        factory_ref: str = "factory",
    ) -> dict[str, Any]:
        """Create workcell and task from a factory source."""
        return self._bridge(
            "factory", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, factory_ref,
        )

    def robotics_from_digital_twin(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        twin_ref: str = "digital_twin",
    ) -> dict[str, Any]:
        """Create workcell and task from a digital twin source."""
        return self._bridge(
            "digital_twin", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, twin_ref,
        )

    def robotics_from_asset(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        asset_ref: str = "asset",
    ) -> dict[str, Any]:
        """Create workcell and task from an asset source."""
        return self._bridge(
            "asset", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, asset_ref,
        )

    def robotics_from_continuity(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        continuity_ref: str = "continuity",
    ) -> dict[str, Any]:
        """Create workcell and task from a continuity source."""
        return self._bridge(
            "continuity", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, continuity_ref,
        )

    def robotics_from_workforce(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        workforce_ref: str = "workforce",
    ) -> dict[str, Any]:
        """Create workcell and task from a workforce source."""
        return self._bridge(
            "workforce", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, workforce_ref,
        )

    def robotics_from_process_simulation(
        self,
        cell_id: str,
        tenant_id: str,
        display_name: str,
        task_id: str,
        task_name: str,
        target_ref: str,
        *,
        simulation_ref: str = "process_simulation",
    ) -> dict[str, Any]:
        """Create workcell and task from a process simulation source."""
        return self._bridge(
            "process_simulation", cell_id, tenant_id, display_name,
            task_id, task_name, target_ref, simulation_ref,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_robotics_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist robotics state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_cells": self._robotics.cell_count,
            "total_actuators": self._robotics.actuator_count,
            "total_sensors": self._robotics.sensor_count,
            "total_tasks": self._robotics.task_count,
            "total_interlocks": self._robotics.interlock_count,
            "total_violations": self._robotics.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-rob", {
                "scope": scope_ref_id,
                "seq": str(self._memory.memory_count),
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Robotics state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("robotics", "control", "automation"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "robotics_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_robotics_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return robotics state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_cells": self._robotics.cell_count,
            "total_actuators": self._robotics.actuator_count,
            "total_sensors": self._robotics.sensor_count,
            "total_tasks": self._robotics.task_count,
            "total_interlocks": self._robotics.interlock_count,
            "total_violations": self._robotics.violation_count,
        }
