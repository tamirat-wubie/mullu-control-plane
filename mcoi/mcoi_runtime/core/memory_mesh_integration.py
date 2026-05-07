"""Purpose: bridge between domain engines and the memory mesh.
Governance scope: structured remember/retrieve operations that translate
    domain events into durable memory records and query for them.
Dependencies: MemoryMeshEngine, memory_mesh contracts, core invariants.
Invariants:
  - Every remember_* method produces a fully-typed MemoryRecord and adds it.
  - Every retrieve_for_* method builds a MemoryRetrievalQuery and returns results.
  - Bridge never mutates engine state outside of MemoryMeshEngine calls.
  - IDs are deterministic via stable_identifier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryRetrievalQuery,
    MemoryRetrievalResult,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryMeshIntegration:
    """Bridge that translates domain engine outputs into memory mesh records.

    Provides typed remember_* methods for ingesting domain events and
    retrieve_for_* methods for querying memories by domain context.
    """

    def __init__(self, engine: MemoryMeshEngine) -> None:
        if not isinstance(engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("engine must be a MemoryMeshEngine")
        self._engine = engine

    # ------------------------------------------------------------------
    # remember_* methods
    # ------------------------------------------------------------------

    def remember_event(
        self,
        event_id: str,
        event_type: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.7,
        trust_level: MemoryTrustLevel = MemoryTrustLevel.OBSERVED,
    ) -> MemoryRecord:
        """Create a memory record from an event."""
        now = _now_iso()
        mid = stable_identifier("mem-evt", {"event_id": event_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.OBSERVATION,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=trust_level,
            title="Event",
            content=dict(content),
            source_ids=(event_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_obligation(
        self,
        obligation_id: str,
        state: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.8,
    ) -> MemoryRecord:
        """Create a memory record from an obligation state change."""
        now = _now_iso()
        mid = stable_identifier("mem-obl", {"obligation_id": obligation_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.DECISION,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Obligation state",
            content=dict(content),
            source_ids=(obligation_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_job(
        self,
        job_id: str,
        job_state: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.8,
    ) -> MemoryRecord:
        """Create a memory record from a job state transition."""
        now = _now_iso()
        mid = stable_identifier("mem-job", {"job_id": job_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.EPISODIC,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.OBSERVED,
            title="Job state",
            content=dict(content),
            source_ids=(job_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_workflow(
        self,
        workflow_id: str,
        stage: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.8,
    ) -> MemoryRecord:
        """Create a memory record from a workflow stage transition."""
        now = _now_iso()
        mid = stable_identifier("mem-wfl", {"workflow_id": workflow_id, "stage": stage, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.PROCEDURAL,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Workflow stage",
            content=dict(content),
            source_ids=(workflow_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_simulation(
        self,
        simulation_id: str,
        verdict: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.6,
    ) -> MemoryRecord:
        """Create a memory record from a simulation outcome."""
        now = _now_iso()
        mid = stable_identifier("mem-sim", {"simulation_id": simulation_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.OUTCOME,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.DERIVED,
            title="Simulation outcome",
            content=dict(content),
            source_ids=(simulation_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_utility(
        self,
        decision_id: str,
        chosen_option: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.7,
    ) -> MemoryRecord:
        """Create a memory record from a utility decision."""
        now = _now_iso()
        mid = stable_identifier("mem-utl", {"decision_id": decision_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.DECISION,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Utility decision",
            content=dict(content),
            source_ids=(decision_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_meta_snapshot(
        self,
        snapshot_id: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.9,
    ) -> MemoryRecord:
        """Create a memory record from a meta-reasoning snapshot."""
        now = _now_iso()
        mid = stable_identifier("mem-meta", {"snapshot_id": snapshot_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.STRATEGIC,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.OBSERVED,
            title="Meta snapshot",
            content=dict(content),
            source_ids=(snapshot_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_operator_override(
        self,
        override_id: str,
        action: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 1.0,
    ) -> MemoryRecord:
        """Create a memory record from an operator override action."""
        now = _now_iso()
        mid = stable_identifier("mem-opr", {"override_id": override_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.COMMUNICATION,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.OPERATOR_CONFIRMED,
            title="Operator override",
            content=dict(content),
            source_ids=(override_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    def remember_benchmark(
        self,
        run_id: str,
        category: str,
        scope: MemoryScope,
        scope_ref_id: str,
        content: Mapping[str, Any],
        *,
        tags: tuple[str, ...] = (),
        confidence: float = 0.8,
    ) -> MemoryRecord:
        """Create a memory record from a benchmark run."""
        now = _now_iso()
        mid = stable_identifier("mem-bench", {"run_id": run_id, "seq": str(self._engine.memory_count)})
        record = MemoryRecord(
            memory_id=mid,
            memory_type=MemoryType.ARTIFACT,
            scope=scope,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Benchmark",
            content=dict(content),
            source_ids=(run_id,),
            tags=tags,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        return self._engine.add_memory(record)

    # ------------------------------------------------------------------
    # retrieve_for_* methods
    # ------------------------------------------------------------------

    def retrieve_for_goal(
        self,
        goal_id: str,
        *,
        max_results: int = 50,
        trust_floor: float = 0.3,
    ) -> MemoryRetrievalResult:
        """Retrieve memories relevant to a goal."""
        query = MemoryRetrievalQuery(
            query_id=stable_identifier("qry-goal", {"goal_id": goal_id}),
            scope=MemoryScope.GOAL,
            scope_ref_id=goal_id,
            trust_floor=trust_floor,
            max_results=max_results,
        )
        return self._engine.retrieve(query)

    def retrieve_for_workflow(
        self,
        workflow_id: str,
        *,
        max_results: int = 50,
        trust_floor: float = 0.3,
    ) -> MemoryRetrievalResult:
        """Retrieve memories relevant to a workflow."""
        query = MemoryRetrievalQuery(
            query_id=stable_identifier("qry-wfl", {"workflow_id": workflow_id}),
            scope=MemoryScope.WORKFLOW,
            scope_ref_id=workflow_id,
            trust_floor=trust_floor,
            max_results=max_results,
        )
        return self._engine.retrieve(query)

    def retrieve_for_recovery(
        self,
        *,
        max_results: int = 100,
        trust_floor: float = 0.5,
    ) -> MemoryRetrievalResult:
        """Retrieve incident and outcome memories for recovery context."""
        query = MemoryRetrievalQuery(
            query_id=stable_identifier("qry-recovery", {"purpose": "recovery"}),
            memory_types=(MemoryType.INCIDENT, MemoryType.OUTCOME),
            trust_floor=trust_floor,
            max_results=max_results,
        )
        return self._engine.retrieve(query)

    def retrieve_for_provider_routing(
        self,
        provider_id: str,
        *,
        max_results: int = 50,
        trust_floor: float = 0.4,
    ) -> MemoryRetrievalResult:
        """Retrieve memories relevant to provider routing decisions."""
        query = MemoryRetrievalQuery(
            query_id=stable_identifier("qry-provider", {"provider_id": provider_id}),
            scope=MemoryScope.PROVIDER,
            scope_ref_id=provider_id,
            trust_floor=trust_floor,
            max_results=max_results,
        )
        return self._engine.retrieve(query)

    def retrieve_for_supervisor_tick(
        self,
        tick_number: int,
        *,
        max_results: int = 20,
        trust_floor: float = 0.5,
    ) -> MemoryRetrievalResult:
        """Retrieve strategic and incident memories for supervisor tick context."""
        query = MemoryRetrievalQuery(
            query_id=stable_identifier("qry-tick", {"tick": tick_number}),
            memory_types=(MemoryType.STRATEGIC, MemoryType.INCIDENT, MemoryType.DECISION),
            trust_floor=trust_floor,
            max_results=max_results,
        )
        return self._engine.retrieve(query)
