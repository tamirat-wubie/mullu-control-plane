"""Purpose: case runtime integration bridge.
Governance scope: composing case runtime with records, fault campaigns,
    control failures, program risks, memory, artifacts, events; memory mesh
    and operational graph attachment.
Dependencies: case_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every case creation emits events.
  - Case audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.case_runtime import (
    CaseKind,
    CaseSeverity,
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
from .case_runtime import CaseRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CaseRuntimeIntegration:
    """Integration bridge for case runtime with platform layers."""

    def __init__(
        self,
        case_engine: CaseRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(case_engine, CaseRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "case_engine must be a CaseRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._cases = case_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Case creation helpers
    # ------------------------------------------------------------------

    def _open_case(
        self,
        case_id: str,
        tenant_id: str,
        title: str,
        source_type: str,
        source_id: str,
        kind: CaseKind,
        severity: CaseSeverity,
        action_name: str,
    ) -> dict[str, Any]:
        case = self._cases.open_case(
            case_id, tenant_id, title,
            kind=kind,
            severity=severity,
        )
        # Auto-add the source as initial evidence
        ev_id = stable_identifier("ev", {"case": case_id, "src": source_id})
        self._cases.add_evidence(
            ev_id, case_id, source_type, source_id,
            title="Case evidence",
        )
        _emit(self._events, action_name, {
            "case_id": case_id, "source_type": source_type,
            "source_id": source_id,
        }, case_id)
        return {
            "case_id": case.case_id,
            "tenant_id": case.tenant_id,
            "kind": case.kind.value,
            "severity": case.severity.value,
            "source_type": source_type,
            "source_id": source_id,
            "evidence_id": ev_id,
        }

    def case_from_record(
        self,
        case_id: str,
        tenant_id: str,
        record_id: str,
        title: str = "Record investigation",
    ) -> dict[str, Any]:
        """Open a case from a preserved record."""
        return self._open_case(
            case_id, tenant_id, title,
            "record", record_id,
            CaseKind.AUDIT, CaseSeverity.MEDIUM,
            "case_from_record",
        )

    def case_from_fault_campaign(
        self,
        case_id: str,
        tenant_id: str,
        fault_campaign_id: str,
        title: str = "Fault campaign investigation",
    ) -> dict[str, Any]:
        """Open a case from a fault campaign result."""
        return self._open_case(
            case_id, tenant_id, title,
            "fault_campaign", fault_campaign_id,
            CaseKind.FAULT_ANALYSIS, CaseSeverity.HIGH,
            "case_from_fault_campaign",
        )

    def case_from_control_failure(
        self,
        case_id: str,
        tenant_id: str,
        control_id: str,
        title: str = "Control failure investigation",
    ) -> dict[str, Any]:
        """Open a case from a compliance control failure."""
        return self._open_case(
            case_id, tenant_id, title,
            "control_failure", control_id,
            CaseKind.COMPLIANCE, CaseSeverity.HIGH,
            "case_from_control_failure",
        )

    def case_from_program_risk(
        self,
        case_id: str,
        tenant_id: str,
        program_id: str,
        title: str = "Program risk investigation",
    ) -> dict[str, Any]:
        """Open a case from a program risk signal."""
        return self._open_case(
            case_id, tenant_id, title,
            "program_risk", program_id,
            CaseKind.OPERATIONAL, CaseSeverity.MEDIUM,
            "case_from_program_risk",
        )

    # ------------------------------------------------------------------
    # Evidence attachment helpers
    # ------------------------------------------------------------------

    def attach_memory_as_evidence(
        self,
        evidence_id: str,
        case_id: str,
        memory_id: str,
        *,
        title: str = "Memory evidence",
    ) -> dict[str, Any]:
        """Attach a memory record as evidence to a case."""
        item = self._cases.add_evidence(
            evidence_id, case_id, "memory", memory_id,
            title=title,
        )
        _emit(self._events, "memory_attached_as_evidence", {
            "evidence_id": evidence_id, "case_id": case_id,
            "memory_id": memory_id,
        }, case_id)
        return {
            "evidence_id": item.evidence_id,
            "case_id": item.case_id,
            "source_type": "memory",
            "source_id": memory_id,
        }

    def attach_artifact_as_evidence(
        self,
        evidence_id: str,
        case_id: str,
        artifact_id: str,
        *,
        title: str = "Artifact evidence",
    ) -> dict[str, Any]:
        """Attach an artifact as evidence to a case."""
        item = self._cases.add_evidence(
            evidence_id, case_id, "artifact", artifact_id,
            title=title,
        )
        _emit(self._events, "artifact_attached_as_evidence", {
            "evidence_id": evidence_id, "case_id": case_id,
            "artifact_id": artifact_id,
        }, case_id)
        return {
            "evidence_id": item.evidence_id,
            "case_id": item.case_id,
            "source_type": "artifact",
            "source_id": artifact_id,
        }

    def attach_event_as_evidence(
        self,
        evidence_id: str,
        case_id: str,
        event_id: str,
        *,
        title: str = "Event evidence",
    ) -> dict[str, Any]:
        """Attach an event as evidence to a case."""
        item = self._cases.add_evidence(
            evidence_id, case_id, "event", event_id,
            title=title,
        )
        _emit(self._events, "event_attached_as_evidence", {
            "evidence_id": evidence_id, "case_id": case_id,
            "event_id": event_id,
        }, case_id)
        return {
            "evidence_id": item.evidence_id,
            "case_id": item.case_id,
            "source_type": "event",
            "source_id": event_id,
        }

    def attach_record_as_evidence(
        self,
        evidence_id: str,
        case_id: str,
        record_id: str,
        *,
        title: str = "Record evidence",
    ) -> dict[str, Any]:
        """Attach a preserved record as evidence to a case."""
        item = self._cases.add_evidence(
            evidence_id, case_id, "record", record_id,
            title=title,
        )
        _emit(self._events, "record_attached_as_evidence", {
            "evidence_id": evidence_id, "case_id": case_id,
            "record_id": record_id,
        }, case_id)
        return {
            "evidence_id": item.evidence_id,
            "case_id": item.case_id,
            "source_type": "record",
            "source_id": record_id,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_case_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist case state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_cases": self._cases.case_count,
            "open_cases": self._cases.open_case_count,
            "total_evidence": self._cases.evidence_count,
            "total_reviews": self._cases.review_count,
            "total_findings": self._cases.finding_count,
            "total_decisions": self._cases.decision_count,
            "total_violations": self._cases.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-case", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Case state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("case", "investigation", "evidence"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "case_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_case_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return case state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_cases": self._cases.case_count,
            "open_cases": self._cases.open_case_count,
            "total_evidence": self._cases.evidence_count,
            "total_reviews": self._cases.review_count,
            "total_findings": self._cases.finding_count,
            "total_decisions": self._cases.decision_count,
            "total_violations": self._cases.violation_count,
        }
