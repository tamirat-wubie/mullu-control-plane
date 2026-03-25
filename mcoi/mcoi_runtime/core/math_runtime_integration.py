"""Purpose: math runtime integration bridge.
Governance scope: composing math runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create optimization
    setups from various platform surface sources.
Dependencies: math_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every math operation emits events.
  - Math state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.math_runtime import (
    ObjectiveDirection,
    OptimizationStatus,
    SolverDisposition,
    UnitDimension,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .math_runtime import MathRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-maint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MathRuntimeIntegration:
    """Integration bridge for math runtime with platform layers."""

    def __init__(
        self,
        math_engine: MathRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(math_engine, MathRuntimeEngine):
            raise RuntimeCoreInvariantError("math_engine must be a MathRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._math = math_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str, str]:
        """Generate deterministic objective, request, and result IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        objective_id = stable_identifier("obj-math", {"tenant": tenant_id, "source": source_type, "seq": seq})
        request_id = stable_identifier("req-math", {"tenant": tenant_id, "source": source_type, "seq": seq})
        result_id = stable_identifier("res-math", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return objective_id, request_id, result_id

    def _optimize_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register an objective and submit a solver request for a given source."""
        objective_id, request_id, result_id = self._next_ids(tenant_id, source_type)

        objective = self._math.register_objective(
            objective_id=objective_id,
            tenant_id=tenant_id,
            display_name=f"{source_type}_{ref}",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

        request = self._math.submit_solver_request(
            request_id=request_id,
            tenant_id=tenant_id,
            objective_ref=objective_id,
        )

        _emit(self._events, f"optimize_from_{source_type}", {
            "tenant_id": tenant_id,
            "objective_id": objective_id,
            "request_id": request_id,
            "ref": ref,
        }, objective_id)

        return {
            "objective_id": objective_id,
            "request_id": request_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "direction": objective.direction.value,
            "target_value": objective.target_value,
            "weight": objective.weight,
            "status": request.status.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific optimization methods
    # ------------------------------------------------------------------

    def optimize_for_portfolio(
        self,
        tenant_id: str,
        portfolio_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for portfolio source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=portfolio_ref,
            source_type="portfolio",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    def optimize_for_workforce(
        self,
        tenant_id: str,
        workforce_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for workforce source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=workforce_ref,
            source_type="workforce",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    def optimize_for_forecasting(
        self,
        tenant_id: str,
        forecast_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for forecasting source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=forecast_ref,
            source_type="forecasting",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    def optimize_for_marketplace(
        self,
        tenant_id: str,
        marketplace_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for marketplace source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=marketplace_ref,
            source_type="marketplace",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    def optimize_for_factory(
        self,
        tenant_id: str,
        factory_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for factory source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=factory_ref,
            source_type="factory",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    def optimize_for_self_tuning(
        self,
        tenant_id: str,
        tuning_ref: str,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_value: float = 0.0,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        """Register optimization objective for self-tuning source."""
        return self._optimize_for_source(
            tenant_id=tenant_id,
            ref=tuning_ref,
            source_type="self_tuning",
            direction=direction,
            target_value=target_value,
            weight=weight,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_math_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist math state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-math", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_quantities": self._math.quantity_count,
            "total_conversions": self._math.conversion_count,
            "total_objectives": self._math.objective_count,
            "total_constraints": self._math.constraint_count,
            "total_requests": self._math.request_count,
            "total_results": self._math.result_count,
            "total_intervals": self._math.interval_count,
            "total_traces": self._math.trace_count,
            "total_violations": self._math.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Math state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("math", "optimization", "units"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "math_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_math_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return math state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_quantities": self._math.quantity_count,
            "total_conversions": self._math.conversion_count,
            "total_objectives": self._math.objective_count,
            "total_constraints": self._math.constraint_count,
            "total_requests": self._math.request_count,
            "total_results": self._math.result_count,
            "total_intervals": self._math.interval_count,
            "total_traces": self._math.trace_count,
            "total_violations": self._math.violation_count,
        }
