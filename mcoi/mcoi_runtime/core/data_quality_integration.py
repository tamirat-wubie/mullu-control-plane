"""Purpose: data quality integration bridge.
Governance scope: composing data quality engine with artifact ingestion,
    records runtime, knowledge query, reporting, research, and memory mesh;
    memory mesh and operational graph attachment.
Dependencies: data_quality engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every quality record creation emits events.
  - Quality state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.data_quality import (
    DataQualityStatus,
    TrustScore,
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
from .data_quality import DataQualityEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dqi", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_SEQ = {"n": 0}


def _next_seq() -> int:
    _SEQ["n"] += 1
    return _SEQ["n"]


class DataQualityIntegration:
    """Integration bridge for data quality with platform layers."""

    def __init__(
        self,
        dq_engine: DataQualityEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(dq_engine, DataQualityEngine):
            raise RuntimeCoreInvariantError(
                "dq_engine must be a DataQualityEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._dq = dq_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Quality record creation from various sources
    # ------------------------------------------------------------------

    def _create_quality_from_source(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        source_type: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        rec = self._dq.register_quality_record(
            record_id, tenant_id, source_ref,
            status=status, error_count=error_count,
        )
        _emit(self._events, f"quality_from_{source_type}", {
            "record_id": record_id, "source_type": source_type,
            "source_ref": source_ref,
        }, record_id)
        return {
            "record_id": rec.record_id,
            "tenant_id": rec.tenant_id,
            "source_type": source_type,
            "source_ref": rec.source_ref,
            "status": rec.status.value,
            "trust_score": rec.trust_score.value,
            "error_count": rec.error_count,
        }

    def quality_from_artifact_ingestion(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from artifact ingestion."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "artifact_ingestion",
            error_count=error_count, status=status,
        )

    def quality_from_records_runtime(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from records runtime."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "records_runtime",
            error_count=error_count, status=status,
        )

    def quality_from_knowledge_query(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from knowledge query."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "knowledge_query",
            error_count=error_count, status=status,
        )

    def quality_from_reporting(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from reporting."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "reporting",
            error_count=error_count, status=status,
        )

    def quality_from_research(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from research."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "research",
            error_count=error_count, status=status,
        )

    def quality_from_memory_mesh(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        *,
        error_count: int = 0,
        status: DataQualityStatus = DataQualityStatus.CLEAN,
    ) -> dict[str, Any]:
        """Create a quality record from memory mesh."""
        return self._create_quality_from_source(
            record_id, tenant_id, source_ref,
            "memory_mesh",
            error_count=error_count, status=status,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_data_quality_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist data quality state to memory mesh."""
        now = _now_iso()
        seq = _next_seq()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_records": self._dq.record_count,
            "total_schemas": self._dq.schema_count,
            "total_drifts": self._dq.drift_count,
            "total_duplicates": self._dq.duplicate_count,
            "total_lineages": self._dq.lineage_count,
            "total_violations": self._dq.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-dq", {"id": scope_ref_id, "seq": seq}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Data quality state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("data_quality", "schema_evolution", "lineage"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "data_quality_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_data_quality_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return data quality state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_records": self._dq.record_count,
            "total_schemas": self._dq.schema_count,
            "total_drifts": self._dq.drift_count,
            "total_duplicates": self._dq.duplicate_count,
            "total_lineages": self._dq.lineage_count,
            "total_reconciliations": self._dq.reconciliation_count,
            "total_policies": self._dq.policy_count,
            "total_violations": self._dq.violation_count,
        }
