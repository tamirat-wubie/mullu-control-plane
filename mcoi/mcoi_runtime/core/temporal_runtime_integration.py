"""Purpose: temporal runtime integration bridge.
Governance scope: composing temporal runtime with contracts/SLA, remediation,
    continuity, records/legal hold, executive reporting, and research studies;
    memory mesh and operational graph attachment.
Dependencies: temporal_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every temporal action emits events.
  - Temporal state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.temporal_runtime import (
    TemporalRelation,
    TemporalStatus,
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
from .temporal_runtime import TemporalRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-tint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class TemporalRuntimeIntegration:
    """Integration bridge for temporal runtime with platform layers."""

    def __init__(
        self,
        temporal_engine: TemporalRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(temporal_engine, TemporalRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "temporal_engine must be a TemporalRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._temporal = temporal_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Cross-domain temporal event creation helpers
    # ------------------------------------------------------------------

    def temporal_from_contracts_sla(
        self,
        event_id: str,
        tenant_id: str,
        contract_ref: str,
        occurred_at: str,
        *,
        label: str = "SLA deadline event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from a contract/SLA deadline."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_contracts_sla", {
            "event_id": event_id, "contract_ref": contract_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "contract_ref": contract_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "contracts_sla",
        }

    def temporal_from_remediation(
        self,
        event_id: str,
        tenant_id: str,
        remediation_ref: str,
        occurred_at: str,
        *,
        label: str = "Remediation milestone event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from a remediation milestone."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_remediation", {
            "event_id": event_id, "remediation_ref": remediation_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "remediation_ref": remediation_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "remediation",
        }

    def temporal_from_continuity(
        self,
        event_id: str,
        tenant_id: str,
        continuity_ref: str,
        occurred_at: str,
        *,
        label: str = "Continuity event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from a continuity plan."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_continuity", {
            "event_id": event_id, "continuity_ref": continuity_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "continuity_ref": continuity_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "continuity",
        }

    def temporal_from_records_legal_hold(
        self,
        event_id: str,
        tenant_id: str,
        hold_ref: str,
        occurred_at: str,
        *,
        label: str = "Legal hold event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from a records/legal hold action."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_records_legal_hold", {
            "event_id": event_id, "hold_ref": hold_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "hold_ref": hold_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "records_legal_hold",
        }

    def temporal_from_executive_reporting(
        self,
        event_id: str,
        tenant_id: str,
        report_ref: str,
        occurred_at: str,
        *,
        label: str = "Executive reporting event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from executive reporting."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_executive_reporting", {
            "event_id": event_id, "report_ref": report_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "report_ref": report_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "executive_reporting",
        }

    def temporal_from_research_studies(
        self,
        event_id: str,
        tenant_id: str,
        study_ref: str,
        occurred_at: str,
        *,
        label: str = "Research study event",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Create a temporal event from a research study."""
        te = self._temporal.register_temporal_event(
            event_id, tenant_id, label, occurred_at,
            duration_ms=duration_ms,
        )
        _emit(self._events, "temporal_from_research_studies", {
            "event_id": event_id, "study_ref": study_ref,
        }, event_id)
        return {
            "event_id": te.event_id,
            "tenant_id": te.tenant_id,
            "study_ref": study_ref,
            "label": te.label,
            "occurred_at": te.occurred_at,
            "source_type": "research_studies",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_temporal_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist temporal state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_events": self._temporal.event_count,
            "total_intervals": self._temporal.interval_count,
            "total_constraints": self._temporal.constraint_count,
            "total_sequences": self._temporal.sequence_count,
            "total_persistence": self._temporal.persistence_count,
            "total_decisions": self._temporal.decision_count,
            "total_violations": self._temporal.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-temp", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Temporal state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("temporal", "reasoning", "constraints"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "temporal_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_temporal_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return temporal state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_events": self._temporal.event_count,
            "total_intervals": self._temporal.interval_count,
            "total_constraints": self._temporal.constraint_count,
            "total_sequences": self._temporal.sequence_count,
            "total_persistence": self._temporal.persistence_count,
            "total_decisions": self._temporal.decision_count,
            "total_violations": self._temporal.violation_count,
        }
