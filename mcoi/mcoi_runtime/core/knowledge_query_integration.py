"""Purpose: knowledge query runtime integration bridge.
Governance scope: composing knowledge query runtime with case reviews,
    regulatory packages, remediation verification, assurance decisions,
    executive control, service requests; memory mesh and graph attachment.
Dependencies: knowledge_query engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every query action emits events.
  - Query state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.knowledge_query import (
    EvidenceKind,
    QueryScope,
    RankingStrategy,
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
from .knowledge_query import KnowledgeQueryEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-kqint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class KnowledgeQueryIntegration:
    """Integration bridge for knowledge query runtime with platform layers."""

    def __init__(
        self,
        query_engine: KnowledgeQueryEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(query_engine, KnowledgeQueryEngine):
            raise RuntimeCoreInvariantError(
                "query_engine must be a KnowledgeQueryEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._query = query_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Query creation helpers
    # ------------------------------------------------------------------

    def query_for_case_review(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        case_ref: str,
        *,
        search_text: str = "",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Execute a query for case review evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.TENANT,
            scope_ref_id=case_ref,
            search_text=search_text or case_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.RELEVANCE,
        )
        _emit(self._events, "query_for_case_review", {
            "query_id": query_id, "case_ref": case_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "case_ref": case_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "case_review",
        }

    def query_for_regulatory_package(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        submission_ref: str,
        *,
        search_text: str = "",
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Execute a query for regulatory package evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.TENANT,
            scope_ref_id=submission_ref,
            search_text=search_text or submission_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.CONFIDENCE,
        )
        _emit(self._events, "query_for_regulatory_package", {
            "query_id": query_id, "submission_ref": submission_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "submission_ref": submission_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "regulatory_package",
        }

    def query_for_remediation_verification(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        remediation_ref: str,
        *,
        search_text: str = "",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Execute a query for remediation verification evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.TENANT,
            scope_ref_id=remediation_ref,
            search_text=search_text or remediation_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.RECENCY,
        )
        _emit(self._events, "query_for_remediation_verification", {
            "query_id": query_id, "remediation_ref": remediation_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "remediation_ref": remediation_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "remediation_verification",
        }

    def query_for_assurance_decision(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        assurance_ref: str,
        *,
        search_text: str = "",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Execute a query for assurance decision evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.TENANT,
            scope_ref_id=assurance_ref,
            search_text=search_text or assurance_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.CONFIDENCE,
        )
        _emit(self._events, "query_for_assurance_decision", {
            "query_id": query_id, "assurance_ref": assurance_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "assurance_ref": assurance_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "assurance_decision",
        }

    def query_for_executive_control(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        directive_ref: str,
        *,
        search_text: str = "",
        max_results: int = 25,
    ) -> dict[str, Any]:
        """Execute a query for executive control evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.PROGRAM,
            scope_ref_id=directive_ref,
            search_text=search_text or directive_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.SEVERITY,
        )
        _emit(self._events, "query_for_executive_control", {
            "query_id": query_id, "directive_ref": directive_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "directive_ref": directive_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "executive_control",
        }

    def query_for_service_request(
        self,
        query_id: str,
        execution_id: str,
        tenant_id: str,
        service_ref: str,
        *,
        search_text: str = "",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Execute a query for service request evidence."""
        self._query.register_query(
            query_id, tenant_id,
            scope=QueryScope.SERVICE,
            scope_ref_id=service_ref,
            search_text=search_text or service_ref,
            max_results=max_results,
        )
        exec_rec = self._query.execute_query(
            execution_id, query_id,
            ranking_strategy=RankingStrategy.RECENCY,
        )
        _emit(self._events, "query_for_service_request", {
            "query_id": query_id, "service_ref": service_ref,
        }, query_id)
        return {
            "query_id": query_id,
            "execution_id": execution_id,
            "tenant_id": tenant_id,
            "service_ref": service_ref,
            "total_matches": exec_rec.total_matches,
            "total_results": exec_rec.total_results,
            "status": exec_rec.status.value,
            "source_type": "service_request",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_query_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist query state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_queries": self._query.query_count,
            "total_filters": self._query.filter_count,
            "total_references": self._query.reference_count,
            "total_matches": self._query.match_count,
            "total_results": self._query.result_count,
            "total_executions": self._query.execution_count,
            "total_bundles": self._query.bundle_count,
            "total_violations": self._query.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-kqry", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Knowledge query state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("knowledge_query", "evidence", "retrieval"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "query_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_query_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return query state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_queries": self._query.query_count,
            "total_filters": self._query.filter_count,
            "total_references": self._query.reference_count,
            "total_matches": self._query.match_count,
            "total_results": self._query.result_count,
            "total_executions": self._query.execution_count,
            "total_bundles": self._query.bundle_count,
            "total_violations": self._query.violation_count,
        }
