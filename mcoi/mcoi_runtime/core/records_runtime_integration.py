"""Purpose: records runtime integration bridge.
Governance scope: composing records runtime with campaigns, programs,
    control tests, changes, approvals, connector activity, and fault
    campaigns; memory mesh and operational graph attachment.
Dependencies: records_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every record creation emits events.
  - Records audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.records_runtime import (
    EvidenceGrade,
    RecordAuthority,
    RecordKind,
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
from .records_runtime import RecordsRuntimeEngine


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


class RecordsRuntimeIntegration:
    """Integration bridge for records runtime with platform layers."""

    def __init__(
        self,
        records_engine: RecordsRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(records_engine, RecordsRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "records_engine must be a RecordsRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._records = records_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Record creation helpers
    # ------------------------------------------------------------------

    def _create_record(
        self,
        record_id: str,
        tenant_id: str,
        title: str,
        source_type: str,
        source_id: str,
        kind: RecordKind,
        evidence_grade: EvidenceGrade,
        authority: RecordAuthority,
        action_name: str,
    ) -> dict[str, Any]:
        rec = self._records.register_record(
            record_id, tenant_id, title,
            kind=kind,
            source_type=source_type,
            source_id=source_id,
            authority=authority,
            evidence_grade=evidence_grade,
        )
        self._records.add_link(
            stable_identifier("lnk", {"rec": record_id, "src": source_id}),
            record_id, source_type, source_id, "source",
        )
        _emit(self._events, action_name, {
            "record_id": record_id, "source_type": source_type,
            "source_id": source_id,
        }, record_id)
        return {
            "record_id": rec.record_id,
            "tenant_id": rec.tenant_id,
            "kind": rec.kind.value,
            "source_type": source_type,
            "source_id": source_id,
            "evidence_grade": rec.evidence_grade.value,
        }

    def record_from_campaign(
        self,
        record_id: str,
        tenant_id: str,
        campaign_id: str,
        title: str = "Campaign record",
    ) -> dict[str, Any]:
        """Create a record from a campaign."""
        return self._create_record(
            record_id, tenant_id, title,
            "campaign", campaign_id,
            RecordKind.OPERATIONAL, EvidenceGrade.PRIMARY,
            RecordAuthority.SYSTEM, "record_from_campaign",
        )

    def record_from_program(
        self,
        record_id: str,
        tenant_id: str,
        program_id: str,
        title: str = "Program record",
    ) -> dict[str, Any]:
        """Create a record from a program."""
        return self._create_record(
            record_id, tenant_id, title,
            "program", program_id,
            RecordKind.OPERATIONAL, EvidenceGrade.PRIMARY,
            RecordAuthority.SYSTEM, "record_from_program",
        )

    def record_from_control_test(
        self,
        record_id: str,
        tenant_id: str,
        test_id: str,
        title: str = "Control test record",
    ) -> dict[str, Any]:
        """Create a record from a compliance control test."""
        return self._create_record(
            record_id, tenant_id, title,
            "control_test", test_id,
            RecordKind.COMPLIANCE, EvidenceGrade.PRIMARY,
            RecordAuthority.COMPLIANCE, "record_from_control_test",
        )

    def record_from_change(
        self,
        record_id: str,
        tenant_id: str,
        change_id: str,
        title: str = "Change record",
    ) -> dict[str, Any]:
        """Create a record from a change execution."""
        return self._create_record(
            record_id, tenant_id, title,
            "change", change_id,
            RecordKind.AUDIT, EvidenceGrade.PRIMARY,
            RecordAuthority.OPERATOR, "record_from_change",
        )

    def record_from_approval(
        self,
        record_id: str,
        tenant_id: str,
        approval_id: str,
        title: str = "Approval record",
    ) -> dict[str, Any]:
        """Create a record from an approval decision."""
        return self._create_record(
            record_id, tenant_id, title,
            "approval", approval_id,
            RecordKind.AUDIT, EvidenceGrade.PRIMARY,
            RecordAuthority.OPERATOR, "record_from_approval",
        )

    def record_from_connector_activity(
        self,
        record_id: str,
        tenant_id: str,
        connector_id: str,
        title: str = "Connector activity record",
    ) -> dict[str, Any]:
        """Create a record from connector activity."""
        return self._create_record(
            record_id, tenant_id, title,
            "connector", connector_id,
            RecordKind.OPERATIONAL, EvidenceGrade.SECONDARY,
            RecordAuthority.SYSTEM, "record_from_connector_activity",
        )

    def record_from_fault_campaign(
        self,
        record_id: str,
        tenant_id: str,
        fault_campaign_id: str,
        title: str = "Fault campaign record",
    ) -> dict[str, Any]:
        """Create a preserved assurance record from a fault campaign."""
        return self._create_record(
            record_id, tenant_id, title,
            "fault_campaign", fault_campaign_id,
            RecordKind.EVIDENCE, EvidenceGrade.PRIMARY,
            RecordAuthority.COMPLIANCE, "record_from_fault_campaign",
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_records_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist records state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_records": self._records.record_count,
            "total_schedules": self._records.schedule_count,
            "total_holds": self._records.hold_count,
            "active_holds": self._records.active_hold_count,
            "total_links": self._records.link_count,
            "total_disposals": self._records.disposal_count,
            "total_violations": self._records.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-rrec", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Records state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("records", "retention", "legal_hold"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "records_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_records_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return records state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_records": self._records.record_count,
            "total_schedules": self._records.schedule_count,
            "total_holds": self._records.hold_count,
            "active_holds": self._records.active_hold_count,
            "total_links": self._records.link_count,
            "total_disposals": self._records.disposal_count,
            "total_violations": self._records.violation_count,
        }
