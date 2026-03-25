"""Purpose: bridge between artifact ingestion and domain engines.
Governance scope: artifact ingestion with event emission, memory recording,
    obligation extraction, and structured retrieval for domain contexts.
Dependencies: ArtifactIngestionEngine, EventSpineEngine, MemoryMeshEngine,
    MemoryMeshIntegration, ObligationRuntimeEngine, core invariants.
Invariants:
  - Every accepted artifact can produce an event and a memory record.
  - Rejected artifacts still emit events (for audit trail).
  - Obligation extraction is explicit — not automatic.
  - Retrieval methods return memory results, not raw records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.artifact_ingestion import (
    ArtifactDescriptor,
    ArtifactFormat,
    ArtifactIngestionRecord,
    ArtifactParseStatus,
    ArtifactSemanticType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryRetrievalResult,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from ..contracts.obligation import ObligationDeadline, ObligationOwner, ObligationTrigger
from .artifact_ingestion import ArtifactIngestionEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .memory_mesh_integration import MemoryMeshIntegration
from .obligation_runtime import ObligationRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactIngestionIntegration:
    """Bridge connecting artifact ingestion to event spine, memory mesh,
    obligation runtime, and other domain engines.
    """

    def __init__(
        self,
        artifact_engine: ArtifactIngestionEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
        obligation_runtime: ObligationRuntimeEngine,
    ) -> None:
        if not isinstance(artifact_engine, ArtifactIngestionEngine):
            raise RuntimeCoreInvariantError("artifact_engine must be an ArtifactIngestionEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        if not isinstance(obligation_runtime, ObligationRuntimeEngine):
            raise RuntimeCoreInvariantError("obligation_runtime must be an ObligationRuntimeEngine")
        self._artifacts = artifact_engine
        self._events = event_spine
        self._memory_engine = memory_engine
        self._memory = MemoryMeshIntegration(memory_engine)
        self._obligations = obligation_runtime

    # ------------------------------------------------------------------
    # Ingest + emit event
    # ------------------------------------------------------------------

    def ingest_and_emit_event(
        self,
        descriptor: ArtifactDescriptor,
        content: bytes,
    ) -> dict[str, Any]:
        """Ingest artifact and emit event. Returns dict with record and event."""
        record = self._artifacts.ingest(descriptor, content)

        now = _now_iso()
        event_type = (
            EventType.WORLD_STATE_CHANGED
            if record.status == ArtifactParseStatus.ACCEPTED
            else EventType.CUSTOM
        )
        event = EventRecord(
            event_id=stable_identifier("evt-art", {"aid": descriptor.artifact_id}),
            event_type=event_type,
            source=EventSource.EXTERNAL,
            correlation_id=descriptor.artifact_id,
            payload={
                "artifact_id": descriptor.artifact_id,
                "filename": descriptor.filename,
                "format": record.parse_result.format_detected.value,
                "status": record.status.value,
                "reason": record.parse_result.reason,
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"record": record, "event": event}

    # ------------------------------------------------------------------
    # Ingest + remember
    # ------------------------------------------------------------------

    def ingest_and_remember(
        self,
        descriptor: ArtifactDescriptor,
        content: bytes,
        *,
        tags: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Ingest artifact, emit event, and create memory record.

        Returns dict with record, event, and memory.
        """
        result = self.ingest_and_emit_event(descriptor, content)
        record: ArtifactIngestionRecord = result["record"]

        # Create memory record
        mem = self._memory.remember_event(
            event_id=result["event"].event_id,
            event_type="artifact_ingested",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=descriptor.artifact_id,
            content={
                "artifact_id": descriptor.artifact_id,
                "filename": descriptor.filename,
                "format": record.parse_result.format_detected.value,
                "status": record.status.value,
                "size_bytes": descriptor.size_bytes,
                "semantic_type": (
                    record.semantic_mapping.semantic_type.value
                    if record.semantic_mapping else "unknown"
                ),
            },
            tags=("artifact",) + tags,
            confidence=0.8 if record.status == ArtifactParseStatus.ACCEPTED else 0.3,
            trust_level=(
                MemoryTrustLevel.VERIFIED
                if record.status == ArtifactParseStatus.ACCEPTED
                else MemoryTrustLevel.UNVERIFIED
            ),
        )
        result["memory"] = mem
        return result

    # ------------------------------------------------------------------
    # Ingest + extract obligations
    # ------------------------------------------------------------------

    def ingest_and_extract_obligations(
        self,
        descriptor: ArtifactDescriptor,
        content: bytes,
        obligations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ingest artifact and extract obligations from its content.

        Each obligation dict must have: description, owner_id, owner_type,
        display_name, deadline_id, due_at.

        Returns dict with record, event, memory, obligations.
        """
        result = self.ingest_and_remember(descriptor, content, tags=("obligation_source",))
        record: ArtifactIngestionRecord = result["record"]

        if record.status != ArtifactParseStatus.ACCEPTED:
            result["obligations"] = ()
            return result

        created = []
        for idx, obl_spec in enumerate(obligations):
            owner = ObligationOwner(
                owner_id=obl_spec["owner_id"],
                owner_type=obl_spec["owner_type"],
                display_name=obl_spec["display_name"],
            )
            deadline = ObligationDeadline(
                deadline_id=obl_spec["deadline_id"],
                due_at=obl_spec["due_at"],
            )
            obl_id = stable_identifier("obl-art", {
                "aid": descriptor.artifact_id,
                "idx": idx,
                "dl": obl_spec["deadline_id"],
            })
            obl = self._obligations.create_obligation(
                obligation_id=obl_id,
                trigger=ObligationTrigger.CUSTOM,
                trigger_ref_id=descriptor.artifact_id,
                owner=owner,
                deadline=deadline,
                description=obl_spec["description"],
                correlation_id=descriptor.artifact_id,
                metadata={"source": "artifact_extraction", "artifact_id": descriptor.artifact_id},
            )
            created.append(obl)

        result["obligations"] = tuple(created)
        return result

    # ------------------------------------------------------------------
    # Retrieval for domain contexts
    # ------------------------------------------------------------------

    def retrieve_artifacts_for_goal(
        self,
        goal_id: str,
        *,
        max_results: int = 50,
    ) -> MemoryRetrievalResult:
        """Retrieve artifact-related memories for a goal."""
        return self._memory.retrieve_for_goal(goal_id, max_results=max_results)

    def retrieve_artifacts_for_workflow(
        self,
        workflow_id: str,
        *,
        max_results: int = 50,
    ) -> MemoryRetrievalResult:
        """Retrieve artifact-related memories for a workflow."""
        return self._memory.retrieve_for_workflow(workflow_id, max_results=max_results)

    def retrieve_artifacts_for_recovery(
        self,
        *,
        max_results: int = 100,
    ) -> MemoryRetrievalResult:
        """Retrieve artifact-related memories for recovery context."""
        return self._memory.retrieve_for_recovery(max_results=max_results)

    def retrieve_artifacts_for_supervisor_tick(
        self,
        tick_number: int,
        *,
        max_results: int = 20,
    ) -> MemoryRetrievalResult:
        """Retrieve artifact-related memories for supervisor tick context."""
        return self._memory.retrieve_for_supervisor_tick(tick_number, max_results=max_results)
