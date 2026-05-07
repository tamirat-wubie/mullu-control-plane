"""Purpose: program runtime integration bridge.
Governance scope: composing program runtime with executive control,
    campaign outcomes, financials, reporting, optimization, memory mesh,
    and operational graph.
Dependencies: program_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every program operation emits events.
  - Program state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.program_runtime import (
    AttainmentLevel,
    DependencyKind,
    InitiativeStatus,
    MilestoneStatus,
    ObjectiveType,
    ProgramStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .program_runtime import ProgramRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProgramRuntimeIntegration:
    """Integration bridge for program runtime with platform layers."""

    def __init__(
        self,
        program_engine: ProgramRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(program_engine, ProgramRuntimeEngine):
            raise RuntimeCoreInvariantError("program_engine must be a ProgramRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._program = program_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Create program from executive objective
    # ------------------------------------------------------------------

    def program_from_executive_objective(
        self,
        program_id: str,
        objective_id: str,
        title: str,
        *,
        target_value: float = 0.0,
        unit: str = "",
        initiative_specs: list[dict[str, Any]] | None = None,
        owner: str = "",
    ) -> dict[str, Any]:
        """Create a program + objective + initiatives from an executive objective."""
        obj = self._program.register_objective(
            objective_id, title,
            target_value=target_value,
            unit=unit,
            owner=owner,
        )
        prog = self._program.register_program(
            program_id, title,
            objective_ids=[objective_id],
            owner=owner,
        )
        initiative_ids = []
        for spec in (initiative_specs or []):
            ini_id = spec.get("initiative_id", f"{program_id}-ini-{len(initiative_ids)}")
            ini_title = spec.get("title", f"Initiative {len(initiative_ids) + 1}")
            self._program.register_initiative(
                ini_id, program_id, ini_title,
                objective_id=objective_id,
                priority=spec.get("priority", 0),
                owner=spec.get("owner", ""),
            )
            initiative_ids.append(ini_id)

        _emit(self._events, "program_from_executive", {
            "program_id": program_id,
            "objective_id": objective_id,
            "initiative_count": len(initiative_ids),
        }, program_id)
        return {
            "program_id": program_id,
            "objective_id": objective_id,
            "initiative_ids": initiative_ids,
            "title": title,
            "target_value": target_value,
        }

    # ------------------------------------------------------------------
    # Bind campaign / portfolio to initiative
    # ------------------------------------------------------------------

    def bind_campaign_to_initiative(
        self,
        binding_id: str,
        initiative_id: str,
        campaign_ref_id: str,
        *,
        objective_id: str = "",
        weight: float = 1.0,
    ) -> dict[str, Any]:
        binding = self._program.bind_campaign(
            binding_id, initiative_id, campaign_ref_id,
            objective_id=objective_id,
            weight=weight,
        )
        _emit(self._events, "campaign_bound_to_initiative", {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "campaign_ref_id": campaign_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "campaign_ref_id": campaign_ref_id,
            "weight": weight,
        }

    def bind_portfolio_to_program(
        self,
        binding_id: str,
        initiative_id: str,
        portfolio_ref_id: str,
        *,
        objective_id: str = "",
        weight: float = 1.0,
    ) -> dict[str, Any]:
        binding = self._program.bind_portfolio(
            binding_id, initiative_id, portfolio_ref_id,
            objective_id=objective_id,
            weight=weight,
        )
        _emit(self._events, "portfolio_bound_to_program", {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "portfolio_ref_id": portfolio_ref_id,
        }, binding_id)
        return {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "portfolio_ref_id": portfolio_ref_id,
            "weight": weight,
        }

    # ------------------------------------------------------------------
    # Update from campaign outcomes
    # ------------------------------------------------------------------

    def update_from_campaign_outcomes(
        self,
        initiative_id: str,
        campaign_progress_pct: float,
    ) -> dict[str, Any]:
        """Update initiative progress from campaign outcome data."""
        ini = self._program.update_initiative_progress(initiative_id, campaign_progress_pct)
        _emit(self._events, "update_from_campaign_outcomes", {
            "initiative_id": initiative_id,
            "progress_pct": campaign_progress_pct,
        }, initiative_id)
        return {
            "initiative_id": initiative_id,
            "progress_pct": campaign_progress_pct,
            "status": ini.status.value,
        }

    # ------------------------------------------------------------------
    # Update from financials
    # ------------------------------------------------------------------

    def update_from_financials(
        self,
        objective_id: str,
        current_value: float,
    ) -> dict[str, Any]:
        """Update objective value from financial data."""
        obj = self._program.update_objective_value(objective_id, current_value)
        _emit(self._events, "update_from_financials", {
            "objective_id": objective_id,
            "current_value": current_value,
            "attainment": obj.attainment.value,
        }, objective_id)
        return {
            "objective_id": objective_id,
            "current_value": current_value,
            "attainment": obj.attainment.value,
        }

    # ------------------------------------------------------------------
    # Update from reporting
    # ------------------------------------------------------------------

    def update_from_reporting(
        self,
        objective_id: str,
        current_value: float,
    ) -> dict[str, Any]:
        """Update objective value from reporting/KPI data."""
        obj = self._program.update_objective_value(objective_id, current_value)
        _emit(self._events, "update_from_reporting", {
            "objective_id": objective_id,
            "current_value": current_value,
            "attainment": obj.attainment.value,
        }, objective_id)
        return {
            "objective_id": objective_id,
            "current_value": current_value,
            "attainment": obj.attainment.value,
        }

    # ------------------------------------------------------------------
    # Update from optimization
    # ------------------------------------------------------------------

    def update_from_optimization(
        self,
        initiative_id: str,
        optimized_progress_pct: float,
    ) -> dict[str, Any]:
        """Update initiative progress from optimization recommendation outcomes."""
        ini = self._program.update_initiative_progress(initiative_id, optimized_progress_pct)
        _emit(self._events, "update_from_optimization", {
            "initiative_id": initiative_id,
            "progress_pct": optimized_progress_pct,
        }, initiative_id)
        return {
            "initiative_id": initiative_id,
            "progress_pct": optimized_progress_pct,
            "status": ini.status.value,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_program_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist program state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_objectives": self._program.objective_count,
            "total_programs": self._program.program_count,
            "total_initiatives": self._program.initiative_count,
            "total_milestones": self._program.milestone_count,
            "total_bindings": self._program.binding_count,
            "total_dependencies": self._program.dependency_count,
            "total_decisions": self._program.decision_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-prog", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Program state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("program", "initiative", "okr"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "program_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_program_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return program state suitable for operational graph consumption."""
        blocked = self._program.blocked_initiatives()
        return {
            "scope_ref_id": scope_ref_id,
            "total_objectives": self._program.objective_count,
            "total_programs": self._program.program_count,
            "total_initiatives": self._program.initiative_count,
            "total_milestones": self._program.milestone_count,
            "total_bindings": self._program.binding_count,
            "blocked_initiatives": [i.initiative_id for i in blocked],
        }
