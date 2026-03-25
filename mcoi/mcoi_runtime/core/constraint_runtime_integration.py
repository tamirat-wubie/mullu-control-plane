"""Purpose: constraint runtime integration bridge.
Governance scope: composing constraint runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to solve constraints from
    various platform surface sources.
Dependencies: constraint_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every constraint operation emits events.
  - Constraint state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentStrategy,
    ConstraintKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .constraint_runtime import ConstraintRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-csint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ConstraintRuntimeIntegration:
    """Integration bridge for constraint runtime with platform layers."""

    def __init__(
        self,
        constraint_engine: ConstraintRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(constraint_engine, ConstraintRuntimeEngine):
            raise RuntimeCoreInvariantError("constraint_engine must be a ConstraintRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._constraint = constraint_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str, str]:
        """Generate deterministic problem, constraint, and solution IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        problem_id = stable_identifier("prb-csrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        constraint_id = stable_identifier("cst-csrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        solution_id = stable_identifier("sol-csrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return problem_id, constraint_id, solution_id

    def _solve_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        algorithm: AlgorithmKind = AlgorithmKind.CONSTRAINT_SAT,
        constraint_kind: ConstraintKind = ConstraintKind.EQUALITY,
        expression: str = "default",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Create a problem, add a constraint, start, solve, and return result."""
        problem_id, constraint_id, solution_id = self._next_ids(tenant_id, source_type)

        self._constraint.add_constraint(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            kind=constraint_kind,
            expression=expression,
        )

        self._constraint.create_problem(
            problem_id=problem_id,
            tenant_id=tenant_id,
            algorithm=algorithm,
            constraint_count=1,
            variable_count=1,
        )

        self._constraint.start_problem(problem_id)

        solution = self._constraint.solve_problem(
            solution_id=solution_id,
            tenant_id=tenant_id,
            problem_ref=problem_id,
            objective_value=objective_value,
        )

        _emit(self._events, f"solved_for_{source_type}", {
            "tenant_id": tenant_id,
            "problem_id": problem_id,
            "solution_id": solution_id,
            "ref": ref,
        }, solution_id)

        return {
            "problem_id": problem_id,
            "constraint_id": constraint_id,
            "solution_id": solution_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "status": solution.status.value,
            "objective_value": solution.objective_value,
        }

    # ------------------------------------------------------------------
    # Surface-specific solve methods
    # ------------------------------------------------------------------

    def solve_for_orchestration(
        self,
        tenant_id: str,
        plan_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.SCHEDULING,
        expression: str = "orchestration_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for orchestration planning."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=plan_ref,
            source_type="orchestration",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    def solve_for_service_routing(
        self,
        tenant_id: str,
        service_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.ROUTING,
        expression: str = "service_routing_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for service routing."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=service_ref,
            source_type="service_routing",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    def solve_for_workforce_assignment(
        self,
        tenant_id: str,
        workforce_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.MATCHING,
        expression: str = "workforce_assignment_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for workforce assignment."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=workforce_ref,
            source_type="workforce_assignment",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    def solve_for_release_planning(
        self,
        tenant_id: str,
        release_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.SCHEDULING,
        expression: str = "release_planning_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for release planning."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=release_ref,
            source_type="release_planning",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    def solve_for_factory_scheduling(
        self,
        tenant_id: str,
        factory_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.SCHEDULING,
        expression: str = "factory_scheduling_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for factory scheduling."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=factory_ref,
            source_type="factory_scheduling",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    def solve_for_continuity_recovery(
        self,
        tenant_id: str,
        continuity_ref: str,
        algorithm: AlgorithmKind = AlgorithmKind.GRAPH_SEARCH,
        expression: str = "continuity_recovery_constraint",
        objective_value: float = 0.0,
    ) -> dict[str, Any]:
        """Solve constraints for continuity/recovery planning."""
        return self._solve_for_source(
            tenant_id=tenant_id,
            ref=continuity_ref,
            source_type="continuity_recovery",
            algorithm=algorithm,
            expression=expression,
            objective_value=objective_value,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_constraint_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist constraint state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-csrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_constraints": self._constraint.constraint_count,
            "total_problems": self._constraint.problem_count,
            "total_solutions": self._constraint.solution_count,
            "total_nodes": self._constraint.node_count,
            "total_edges": self._constraint.edge_count,
            "total_slots": self._constraint.slot_count,
            "total_assignments": self._constraint.assignment_count,
            "total_dependencies": self._constraint.dependency_count,
            "total_violations": self._constraint.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Constraint state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("constraint", "algorithm", "solver"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "constraint_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_constraint_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return constraint state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_constraints": self._constraint.constraint_count,
            "total_problems": self._constraint.problem_count,
            "total_solutions": self._constraint.solution_count,
            "total_nodes": self._constraint.node_count,
            "total_edges": self._constraint.edge_count,
            "total_slots": self._constraint.slot_count,
            "total_assignments": self._constraint.assignment_count,
            "total_dependencies": self._constraint.dependency_count,
            "total_violations": self._constraint.violation_count,
        }
