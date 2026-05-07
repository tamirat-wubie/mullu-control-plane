"""Purpose: executive control tower integration bridge.
Governance scope: composing executive control engine with reporting,
    financials, portfolio, fault campaigns, autonomous improvement,
    memory mesh, and operational graph.
Dependencies: executive_control engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every control operation emits events.
  - Control state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.executive_control import (
    ControlTowerHealth,
    DirectiveStatus,
    DirectiveType,
    InterventionSeverity,
    ObjectiveStatus,
    PriorityLevel,
    ScenarioStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .executive_control import ExecutiveControlEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-ecint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExecutiveControlIntegration:
    """Integration bridge for executive control with platform layers."""

    def __init__(
        self,
        control_engine: ExecutiveControlEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(control_engine, ExecutiveControlEngine):
            raise RuntimeCoreInvariantError("control_engine must be an ExecutiveControlEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._control = control_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Control from reporting — degrading KPIs trigger directives
    # ------------------------------------------------------------------

    def control_from_reporting(
        self,
        objective_id: str,
        current_value: float,
        *,
        auto_directive: bool = True,
    ) -> dict[str, Any]:
        """Update objective KPI from reporting data; optionally issue directive if off-track."""
        obj = self._control.update_objective_kpi(objective_id, current_value)
        health = self._control.check_objective_health(objective_id)

        directive_id = None
        if auto_directive and not health["on_track"]:
            directive_id = f"dir-rpt-{objective_id}"
            try:
                self._control.issue_directive(
                    directive_id,
                    "KPI degraded",
                    DirectiveType.ESCALATE,
                    objective_id=objective_id,
                    reason="objective gap exceeds tolerance",
                    parameters={"gap_pct": health["gap_pct"], "current_value": current_value},
                )
            except RuntimeCoreInvariantError:
                directive_id = None  # Already issued

        _emit(self._events, "control_from_reporting", {
            "objective_id": objective_id,
            "current_value": current_value,
            "on_track": health["on_track"],
            "directive_id": directive_id,
        }, objective_id)
        return {
            "objective_id": objective_id,
            "current_value": current_value,
            "target_value": health["target_value"],
            "gap_pct": health["gap_pct"],
            "on_track": health["on_track"],
            "directive_issued": directive_id is not None,
            "directive_id": directive_id,
        }

    # ------------------------------------------------------------------
    # Control from financials — budget reallocation
    # ------------------------------------------------------------------

    def control_from_financials(
        self,
        directive_id: str,
        title: str,
        *,
        objective_id: str = "",
        target_scope_ref_id: str = "",
        budget_delta: float = 0.0,
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue a budget reallocation directive from financial data."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.BUDGET_REALLOCATION,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            parameters={"budget_delta": budget_delta},
        )
        _emit(self._events, "control_from_financials", {
            "directive_id": directive_id,
            "budget_delta": budget_delta,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "source": "financials",
            "directive_type": DirectiveType.BUDGET_REALLOCATION.value,
            "budget_delta": budget_delta,
            "target_scope_ref_id": target_scope_ref_id,
        }

    # ------------------------------------------------------------------
    # Control from portfolio — reprioritization
    # ------------------------------------------------------------------

    def control_from_portfolio(
        self,
        directive_id: str,
        title: str,
        *,
        objective_id: str = "",
        target_scope_ref_id: str = "",
        from_priority: PriorityLevel = PriorityLevel.P3_LOW,
        to_priority: PriorityLevel = PriorityLevel.P1_HIGH,
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue a priority shift directive from portfolio analysis."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.PRIORITY_SHIFT,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            parameters={"from_priority": from_priority.value, "to_priority": to_priority.value},
        )
        shift = self._control.shift_priority(
            f"{directive_id}-shift", directive_id,
            target_scope_ref_id, from_priority, to_priority,
            reason=reason,
        )
        _emit(self._events, "control_from_portfolio", {
            "directive_id": directive_id,
            "from": from_priority.value,
            "to": to_priority.value,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "source": "portfolio",
            "directive_type": DirectiveType.PRIORITY_SHIFT.value,
            "shift_id": shift.shift_id,
            "from_priority": from_priority.value,
            "to_priority": to_priority.value,
            "target_scope_ref_id": target_scope_ref_id,
        }

    # ------------------------------------------------------------------
    # Control from faults — escalation
    # ------------------------------------------------------------------

    def control_from_faults(
        self,
        directive_id: str,
        title: str,
        *,
        objective_id: str = "",
        target_scope_ref_id: str = "",
        severity: InterventionSeverity = InterventionSeverity.HIGH,
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue an escalation directive from fault campaign results."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.ESCALATE,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            parameters={"severity": severity.value},
        )
        intervention = self._control.intervene(
            f"{directive_id}-int", directive_id,
            "escalate_from_faults",
            severity=severity,
            target_engine="fault_campaign",
            target_ref_id=target_scope_ref_id,
            reason=reason,
        )
        _emit(self._events, "control_from_faults", {
            "directive_id": directive_id,
            "severity": severity.value,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "source": "faults",
            "directive_type": DirectiveType.ESCALATE.value,
            "intervention_id": intervention.intervention_id,
            "severity": severity.value,
        }

    # ------------------------------------------------------------------
    # Control from autonomous improvement — halt unsafe loops
    # ------------------------------------------------------------------

    def control_from_autonomous_improvement(
        self,
        directive_id: str,
        title: str,
        *,
        objective_id: str = "",
        target_scope_ref_id: str = "",
        reason: str = "",
        severity: InterventionSeverity = InterventionSeverity.HIGH,
    ) -> dict[str, Any]:
        """Halt autonomous improvement loops via executive intervention."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.HALT_AUTONOMOUS,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
        )
        intervention = self._control.intervene(
            f"{directive_id}-int", directive_id,
            "halt_autonomous_improvement",
            severity=severity,
            target_engine="autonomous_improvement",
            target_ref_id=target_scope_ref_id,
            reason=reason,
        )
        _emit(self._events, "control_from_autonomous_improvement", {
            "directive_id": directive_id,
            "intervention_id": intervention.intervention_id,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "source": "autonomous_improvement",
            "directive_type": DirectiveType.HALT_AUTONOMOUS.value,
            "intervention_id": intervention.intervention_id,
            "severity": severity.value,
        }

    # ------------------------------------------------------------------
    # Issue shifts
    # ------------------------------------------------------------------

    def issue_priority_shift(
        self,
        directive_id: str,
        title: str,
        target_scope_ref_id: str,
        from_priority: PriorityLevel,
        to_priority: PriorityLevel,
        *,
        objective_id: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue a standalone priority shift directive."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.PRIORITY_SHIFT,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
        )
        shift = self._control.shift_priority(
            f"{directive_id}-shift", directive_id,
            target_scope_ref_id, from_priority, to_priority,
            reason=reason,
        )
        self._control.execute_directive(directive_id)
        _emit(self._events, "priority_shift_issued", {
            "directive_id": directive_id,
            "shift_id": shift.shift_id,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "shift_id": shift.shift_id,
            "from_priority": from_priority.value,
            "to_priority": to_priority.value,
        }

    def issue_budget_shift(
        self,
        directive_id: str,
        title: str,
        target_scope_ref_id: str,
        budget_delta: float,
        *,
        objective_id: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue a budget reallocation directive and execute it."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.BUDGET_REALLOCATION,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            parameters={"budget_delta": budget_delta},
        )
        self._control.execute_directive(directive_id)
        _emit(self._events, "budget_shift_issued", {
            "directive_id": directive_id,
            "budget_delta": budget_delta,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "budget_delta": budget_delta,
            "target_scope_ref_id": target_scope_ref_id,
        }

    def issue_capacity_shift(
        self,
        directive_id: str,
        title: str,
        target_scope_ref_id: str,
        capacity_delta: float,
        *,
        objective_id: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Issue a capacity shift directive and execute it."""
        d = self._control.issue_directive(
            directive_id, title, DirectiveType.CAPACITY_SHIFT,
            objective_id=objective_id,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            parameters={"capacity_delta": capacity_delta},
        )
        self._control.execute_directive(directive_id)
        _emit(self._events, "capacity_shift_issued", {
            "directive_id": directive_id,
            "capacity_delta": capacity_delta,
        }, directive_id)
        return {
            "directive_id": directive_id,
            "capacity_delta": capacity_delta,
            "target_scope_ref_id": target_scope_ref_id,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_control_decisions_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist control tower state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_objectives": self._control.objective_count,
            "total_directives": self._control.directive_count,
            "total_scenarios": self._control.scenario_count,
            "total_interventions": self._control.intervention_count,
            "total_decisions": self._control.decision_count,
            "total_priority_shifts": self._control.priority_shift_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-ectl", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Control tower state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("executive", "control", "strategic"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "control_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_control_decisions_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return control tower state suitable for operational graph consumption."""
        shifts = self._control.get_priority_shifts()
        return {
            "scope_ref_id": scope_ref_id,
            "total_objectives": self._control.objective_count,
            "total_directives": self._control.directive_count,
            "total_scenarios": self._control.scenario_count,
            "total_interventions": self._control.intervention_count,
            "total_decisions": self._control.decision_count,
            "total_priority_shifts": self._control.priority_shift_count,
            "priority_shifts": [
                {"shift_id": s.shift_id, "from": s.from_priority.value, "to": s.to_priority.value, "target": s.target_scope_ref_id}
                for s in shifts
            ],
        }
