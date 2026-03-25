"""Purpose: research runtime integration bridge.
Governance scope: composing research runtime with artifact ingestion,
    knowledge queries, case reviews, assurance, reporting, LLM generation;
    memory mesh and operational graph attachment.
Dependencies: research_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every research creation emits events.
  - Research state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
from .research_runtime import ResearchRuntimeEngine


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


class ResearchRuntimeIntegration:
    """Integration bridge for research runtime with platform layers."""

    def __init__(
        self,
        research_engine: ResearchRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(research_engine, ResearchRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "research_engine must be a ResearchRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._research = research_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _bridge_research(
        self,
        tenant_id: str,
        title: str,
        description: str,
        statement: str,
        source_type: str,
        ref_field_name: str,
        ref_field_value: str,
        action_name: str,
    ) -> dict[str, Any]:
        """Register a question + hypothesis from a bridge source."""
        self._bridge_seq += 1
        q_id = stable_identifier("rq", {
            "tenant": tenant_id, "src": source_type, "seq": str(self._bridge_seq),
        })
        h_id = stable_identifier("rh", {
            "tenant": tenant_id, "src": source_type, "seq": str(self._bridge_seq),
        })

        q = self._research.register_question(q_id, tenant_id, title, description)
        h = self._research.register_hypothesis(h_id, tenant_id, q_id, statement)
        # Re-read question after hypothesis registration incremented its count
        q_updated = self._research.get_question(q_id)

        _emit(self._events, action_name, {
            "question_id": q_id,
            "hypothesis_id": h_id,
            ref_field_name: ref_field_value,
            "source_type": source_type,
        }, q_id)

        return {
            "question_id": q_updated.question_id,
            "hypothesis_id": h.hypothesis_id,
            "tenant_id": tenant_id,
            ref_field_name: ref_field_value,
            "status": q_updated.status.value,
            "hypothesis_count": q_updated.hypothesis_count,
            "confidence": h.confidence,
            "source_type": source_type,
        }

    # ------------------------------------------------------------------
    # Bridge methods
    # ------------------------------------------------------------------

    def research_from_artifact_ingestion(
        self,
        tenant_id: str,
        artifact_id: str,
        title: str = "Artifact-driven research",
        description: str = "Research question from artifact ingestion",
        statement: str = "Artifact content supports hypothesis",
    ) -> dict[str, Any]:
        """Create research from an artifact ingestion event."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "artifact_ingestion", "artifact_id", artifact_id,
            "research_from_artifact_ingestion",
        )

    def research_from_knowledge_query(
        self,
        tenant_id: str,
        query_id: str,
        title: str = "Knowledge-query research",
        description: str = "Research question from knowledge query",
        statement: str = "Knowledge query supports hypothesis",
    ) -> dict[str, Any]:
        """Create research from a knowledge query."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "knowledge_query", "query_id", query_id,
            "research_from_knowledge_query",
        )

    def research_from_case_review(
        self,
        tenant_id: str,
        case_id: str,
        title: str = "Case-review research",
        description: str = "Research question from case review",
        statement: str = "Case review supports hypothesis",
    ) -> dict[str, Any]:
        """Create research from a case review."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "case_review", "case_id", case_id,
            "research_from_case_review",
        )

    def research_from_assurance(
        self,
        tenant_id: str,
        assurance_id: str,
        title: str = "Assurance-driven research",
        description: str = "Research question from assurance check",
        statement: str = "Assurance check supports hypothesis",
    ) -> dict[str, Any]:
        """Create research from an assurance event."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "assurance", "assurance_id", assurance_id,
            "research_from_assurance",
        )

    def research_from_reporting(
        self,
        tenant_id: str,
        report_id: str,
        title: str = "Reporting-driven research",
        description: str = "Research question from reporting",
        statement: str = "Report findings support hypothesis",
    ) -> dict[str, Any]:
        """Create research from a reporting event."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "reporting", "report_id", report_id,
            "research_from_reporting",
        )

    def research_from_llm_generation(
        self,
        tenant_id: str,
        generation_id: str,
        title: str = "LLM-generation research",
        description: str = "Research question from LLM generation",
        statement: str = "LLM generation supports hypothesis",
    ) -> dict[str, Any]:
        """Create research from an LLM generation event."""
        return self._bridge_research(
            tenant_id, title, description, statement,
            "llm_generation", "generation_id", generation_id,
            "research_from_llm_generation",
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_research_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist research state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_questions": self._research.question_count,
            "total_hypotheses": self._research.hypothesis_count,
            "total_studies": self._research.study_count,
            "total_experiments": self._research.experiment_count,
            "total_literature": self._research.literature_count,
            "total_syntheses": self._research.synthesis_count,
            "total_reviews": self._research.review_count,
            "total_violations": self._research.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-res", {
                "scope": scope_ref_id,
                "seq": str(self._memory.memory_count),
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Research state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("research", "evidence", "synthesis"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "research_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_research_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return research state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_questions": self._research.question_count,
            "total_hypotheses": self._research.hypothesis_count,
            "total_studies": self._research.study_count,
            "total_experiments": self._research.experiment_count,
            "total_literature": self._research.literature_count,
            "total_syntheses": self._research.synthesis_count,
            "total_reviews": self._research.review_count,
            "total_violations": self._research.violation_count,
        }
