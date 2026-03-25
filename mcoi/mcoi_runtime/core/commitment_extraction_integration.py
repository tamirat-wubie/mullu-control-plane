"""Purpose: bridge between commitment extraction and domain engines.
Governance scope: commitment extraction with event emission, obligation
    creation, memory recording, and retrieval for domain contexts.
Dependencies: CommitmentExtractionEngine, EventSpineEngine, MemoryMeshEngine,
    ObligationRuntimeEngine, core invariants.
Invariants:
  - Accepted commitments can produce obligations and memory records.
  - Rejected/ambiguous commitments still emit events (for audit trail).
  - Obligation creation is explicit — only for ACCEPTED/PROPOSED disposition.
  - Memory records track extraction lineage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.commitment_extraction import (
    CommitmentCandidate,
    CommitmentDisposition,
    CommitmentExtractionResult,
    CommitmentSourceType,
    CommitmentType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRetrievalResult,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from ..contracts.obligation import ObligationDeadline, ObligationOwner, ObligationTrigger
from .commitment_extraction import CommitmentExtractionEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .memory_mesh_integration import MemoryMeshIntegration
from .obligation_runtime import ObligationRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommitmentExtractionIntegration:
    """Bridge connecting commitment extraction to event spine,
    obligation runtime, and memory mesh.
    """

    def __init__(
        self,
        extraction_engine: CommitmentExtractionEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
        obligation_runtime: ObligationRuntimeEngine,
    ) -> None:
        if not isinstance(extraction_engine, CommitmentExtractionEngine):
            raise RuntimeCoreInvariantError("extraction_engine must be a CommitmentExtractionEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        if not isinstance(obligation_runtime, ObligationRuntimeEngine):
            raise RuntimeCoreInvariantError("obligation_runtime must be an ObligationRuntimeEngine")
        self._extraction = extraction_engine
        self._events = event_spine
        self._memory_engine = memory_engine
        self._memory = MemoryMeshIntegration(memory_engine)
        self._obligations = obligation_runtime

    # ------------------------------------------------------------------
    # Extract and emit events
    # ------------------------------------------------------------------

    def extract_and_emit_events(
        self,
        text: str,
        source_type: CommitmentSourceType,
        source_ref_id: str,
    ) -> dict[str, Any]:
        """Extract commitments and emit events for each candidate."""
        result = self._extraction.extract_from_text(text, source_type, source_ref_id)

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-extr", {"rid": result.result_id}),
            event_type=EventType.CUSTOM,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=source_ref_id,
            payload={
                "action": "commitments_extracted",
                "source_type": source_type.value,
                "source_ref_id": source_ref_id,
                "candidate_count": len(result.candidates),
                "approval_count": len(result.approvals),
                "deadline_count": len(result.deadlines),
                "owner_count": len(result.owners),
                "escalation_count": len(result.escalations),
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"result": result, "event": event}

    # ------------------------------------------------------------------
    # Extract and create obligations
    # ------------------------------------------------------------------

    def extract_and_create_obligations(
        self,
        text: str,
        source_type: CommitmentSourceType,
        source_ref_id: str,
        *,
        default_owner_id: str = "unassigned",
        default_owner_type: str = "system",
        default_owner_name: str = "Unassigned",
        default_deadline_days: int = 7,
    ) -> dict[str, Any]:
        """Extract commitments, emit events, and create obligations for
        actionable candidates (PROPOSED or ACCEPTED disposition).
        """
        emit_result = self.extract_and_emit_events(text, source_type, source_ref_id)
        result: CommitmentExtractionResult = emit_result["result"]

        obligations = []
        promotions = []
        for candidate in result.candidates:
            if candidate.disposition in (
                CommitmentDisposition.REJECTED,
                CommitmentDisposition.AMBIGUOUS,
                CommitmentDisposition.BLOCKED,
            ):
                continue

            # Determine owner
            owner_id = candidate.proposed_owner_id or default_owner_id
            owner = ObligationOwner(
                owner_id=owner_id,
                owner_type=default_owner_type,
                display_name=candidate.proposed_owner_id or default_owner_name,
            )

            # Determine deadline
            now = _now_iso()
            deadline_id = stable_identifier("dl-commit", {"cid": candidate.commitment_id})
            due_at = candidate.proposed_due_at if candidate.proposed_due_at else now
            deadline = ObligationDeadline(
                deadline_id=deadline_id,
                due_at=due_at if _is_datetime(due_at) else now,
            )

            # Create obligation
            obl_id = stable_identifier("obl-commit", {
                "cid": candidate.commitment_id,
                "src": source_ref_id,
            })

            try:
                obl = self._obligations.create_obligation(
                    obligation_id=obl_id,
                    trigger=ObligationTrigger.CUSTOM,
                    trigger_ref_id=source_ref_id,
                    owner=owner,
                    deadline=deadline,
                    description=candidate.normalized_text,
                    correlation_id=source_ref_id,
                    metadata={
                        "source": "commitment_extraction",
                        "commitment_id": candidate.commitment_id,
                        "commitment_type": candidate.commitment_type.value,
                        "confidence": candidate.confidence,
                    },
                )
                obligations.append(obl)

                # Promote
                promo = self._extraction.promote_commitment(
                    candidate.commitment_id, obl_id,
                )
                promotions.append(promo)
            except RuntimeCoreInvariantError:
                # Duplicate obligation (idempotency) — skip
                continue

        emit_result["obligations"] = obligations
        emit_result["promotions"] = promotions
        return emit_result

    # ------------------------------------------------------------------
    # Extract and remember
    # ------------------------------------------------------------------

    def extract_and_remember(
        self,
        text: str,
        source_type: CommitmentSourceType,
        source_ref_id: str,
        *,
        tags: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Extract commitments, emit events, and create memory record."""
        emit_result = self.extract_and_emit_events(text, source_type, source_ref_id)
        result: CommitmentExtractionResult = emit_result["result"]

        mem = self._memory.remember_event(
            event_id=emit_result["event"].event_id,
            event_type="commitments_extracted",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=source_ref_id,
            content={
                "source_type": source_type.value,
                "source_ref_id": source_ref_id,
                "candidate_count": len(result.candidates),
                "candidates": [
                    {
                        "type": c.commitment_type.value,
                        "disposition": c.disposition.value,
                        "text": c.normalized_text,
                    }
                    for c in result.candidates
                ],
            },
            tags=("commitment_extraction",) + tags,
            confidence=0.8,
            trust_level=MemoryTrustLevel.OBSERVED,
        )
        emit_result["memory"] = mem
        return emit_result

    # ------------------------------------------------------------------
    # Source-specific extraction wrappers
    # ------------------------------------------------------------------

    def extract_from_communication_surface(
        self,
        message_id: str,
        text: str,
        *,
        create_obligations: bool = False,
        **obligation_kw: Any,
    ) -> dict[str, Any]:
        """Extract from an inbound/outbound message."""
        if create_obligations:
            return self.extract_and_create_obligations(
                text, CommitmentSourceType.MESSAGE, message_id, **obligation_kw,
            )
        return self.extract_and_emit_events(text, CommitmentSourceType.MESSAGE, message_id)

    def extract_from_artifact_ingestion(
        self,
        artifact_id: str,
        text: str,
        *,
        create_obligations: bool = False,
        **obligation_kw: Any,
    ) -> dict[str, Any]:
        """Extract from an ingested artifact's text content."""
        if create_obligations:
            return self.extract_and_create_obligations(
                text, CommitmentSourceType.ARTIFACT, artifact_id, **obligation_kw,
            )
        return self.extract_and_emit_events(text, CommitmentSourceType.ARTIFACT, artifact_id)

    def extract_from_operator_note(
        self,
        note_id: str,
        text: str,
        *,
        create_obligations: bool = False,
        **obligation_kw: Any,
    ) -> dict[str, Any]:
        """Extract from an operator note."""
        if create_obligations:
            return self.extract_and_create_obligations(
                text, CommitmentSourceType.OPERATOR_NOTE, note_id, **obligation_kw,
            )
        return self.extract_and_emit_events(text, CommitmentSourceType.OPERATOR_NOTE, note_id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_commitments_for_goal(
        self,
        goal_id: str,
        *,
        max_results: int = 50,
    ) -> MemoryRetrievalResult:
        """Retrieve commitment-related memories for a goal."""
        return self._memory.retrieve_for_goal(goal_id, max_results=max_results)

    def retrieve_commitments_for_recovery(
        self,
        *,
        max_results: int = 100,
    ) -> MemoryRetrievalResult:
        """Retrieve commitment-related memories for recovery context."""
        return self._memory.retrieve_for_recovery(max_results=max_results)


def _is_datetime(text: str) -> bool:
    """Check if text looks like a datetime string."""
    try:
        datetime.fromisoformat(text)
        return True
    except (ValueError, TypeError):
        return False
