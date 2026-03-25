"""Purpose: memory consolidation integration bridge.
Governance scope: composing memory consolidation engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create memory candidates
    from various platform surface sources.
Dependencies: memory_consolidation engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every consolidation operation emits events.
  - Consolidation state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.memory_consolidation import (
    MemoryImportance,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .memory_consolidation import MemoryConsolidationEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mcint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MemoryConsolidationIntegration:
    """Integration bridge for memory consolidation with platform layers."""

    def __init__(
        self,
        consolidation_engine: MemoryConsolidationEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(consolidation_engine, MemoryConsolidationEngine):
            raise RuntimeCoreInvariantError("consolidation_engine must be a MemoryConsolidationEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._consolidation = consolidation_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_candidate_id(self, tenant_id: str, source_type: str) -> str:
        """Generate deterministic candidate ID from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        return stable_identifier("cand-mcrt", {"tenant": tenant_id, "source": source_type, "seq": seq})

    def _consolidate_from_source(
        self,
        tenant_id: str,
        ref: str,
        content_summary: str,
        source_type: str,
    ) -> dict[str, Any]:
        """Register a memory candidate from a specific source."""
        candidate_id = self._next_candidate_id(tenant_id, source_type)
        candidate = self._consolidation.register_memory_candidate(
            candidate_id=candidate_id,
            tenant_id=tenant_id,
            source_ref=ref,
            content_summary=content_summary,
            importance=MemoryImportance.MEDIUM,
            occurrence_count=1,
        )

        _emit(self._events, f"consolidation_from_{source_type}", {
            "tenant_id": tenant_id,
            "candidate_id": candidate_id,
            "ref": ref,
            "source_type": source_type,
        }, candidate_id)

        return {
            "candidate_id": candidate_id,
            "tenant_id": tenant_id,
            "source_ref": ref,
            "source_type": source_type,
            "content_summary": content_summary,
            "importance": candidate.importance.value,
            "status": candidate.status.value,
            "occurrence_count": candidate.occurrence_count,
        }

    # ------------------------------------------------------------------
    # Surface-specific consolidation methods
    # ------------------------------------------------------------------

    def consolidate_from_copilot_sessions(
        self,
        tenant_id: str,
        session_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from copilot sessions."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=session_ref,
            content_summary=content_summary,
            source_type="copilot_sessions",
        )

    def consolidate_from_multimodal_sessions(
        self,
        tenant_id: str,
        session_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from multimodal sessions."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=session_ref,
            content_summary=content_summary,
            source_type="multimodal_sessions",
        )

    def consolidate_from_operator_actions(
        self,
        tenant_id: str,
        action_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from operator actions."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=action_ref,
            content_summary=content_summary,
            source_type="operator_actions",
        )

    def consolidate_from_research_runs(
        self,
        tenant_id: str,
        research_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from research runs."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=research_ref,
            content_summary=content_summary,
            source_type="research_runs",
        )

    def consolidate_from_customer_history(
        self,
        tenant_id: str,
        customer_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from customer history."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=customer_ref,
            content_summary=content_summary,
            source_type="customer_history",
        )

    def consolidate_from_executive_patterns(
        self,
        tenant_id: str,
        executive_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Register memory candidate from executive patterns."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=executive_ref,
            content_summary=content_summary,
            source_type="executive_patterns",
        )

    # ------------------------------------------------------------------
    # Persona-aware consolidation
    # ------------------------------------------------------------------

    def consolidate_from_persona_decisions(
        self,
        tenant_id: str,
        persona_ref: str,
        content_summary: str,
    ) -> dict[str, Any]:
        """Consolidate persona behavior patterns into long-term memory."""
        return self._consolidate_from_source(
            tenant_id=tenant_id,
            ref=persona_ref,
            content_summary=content_summary,
            source_type="persona_decisions",
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_consolidation_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist consolidation state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-mcrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_candidates": self._consolidation.candidate_count,
            "total_decisions": self._consolidation.decision_count,
            "total_rules": self._consolidation.rule_count,
            "total_profiles": self._consolidation.profile_count,
            "total_conflicts": self._consolidation.conflict_count,
            "total_batches": self._consolidation.batch_count,
            "total_violations": self._consolidation.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Memory consolidation state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("memory_consolidation", "personalization", "retention"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "consolidation_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_consolidation_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return consolidation state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_candidates": self._consolidation.candidate_count,
            "total_decisions": self._consolidation.decision_count,
            "total_rules": self._consolidation.rule_count,
            "total_profiles": self._consolidation.profile_count,
            "total_conflicts": self._consolidation.conflict_count,
            "total_batches": self._consolidation.batch_count,
            "total_violations": self._consolidation.violation_count,
        }
