"""Purpose: data governance integration bridge.
Governance scope: composing data governance with artifact ingestion,
    communication, memory mesh, connector, campaign, and program reporting;
    memory mesh and operational graph attachment.
Dependencies: data_governance engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every governance decision emits events.
  - Governance audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.data_governance import (
    GovernanceDecision,
    ResidencyRegion,
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
from .data_governance import DataGovernanceEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class DataGovernanceIntegration:
    """Integration bridge for data governance with platform layers."""

    def __init__(
        self,
        governance_engine: DataGovernanceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(governance_engine, DataGovernanceEngine):
            raise RuntimeCoreInvariantError(
                "governance_engine must be a DataGovernanceEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._governance = governance_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Governance helpers
    # ------------------------------------------------------------------

    def govern_artifact_ingestion(
        self,
        data_id: str,
    ) -> dict[str, Any]:
        """Govern whether an artifact may be ingested."""
        dec = self._governance.evaluate_artifact_storage(data_id)
        _emit(self._events, "artifact_ingestion_governed", {
            "data_id": data_id, "decision": dec.decision.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "artifact_ingestion",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    def govern_communication_payload(
        self,
        data_id: str,
    ) -> dict[str, Any]:
        """Govern whether a communication payload may be sent."""
        dec = self._governance.evaluate_handling(data_id, "communication")
        _emit(self._events, "communication_payload_governed", {
            "data_id": data_id, "decision": dec.decision.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "communication",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    def govern_memory_write(
        self,
        data_id: str,
    ) -> dict[str, Any]:
        """Govern whether data may be written to memory mesh."""
        dec = self._governance.evaluate_memory_storage(data_id)
        _emit(self._events, "memory_write_governed", {
            "data_id": data_id, "decision": dec.decision.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "memory_storage",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    def govern_connector_payload(
        self,
        data_id: str,
        connector_region: ResidencyRegion = ResidencyRegion.GLOBAL,
    ) -> dict[str, Any]:
        """Govern whether data may be sent to a connector."""
        dec = self._governance.evaluate_connector_transfer(data_id, connector_region)
        _emit(self._events, "connector_payload_governed", {
            "data_id": data_id, "decision": dec.decision.value,
            "region": connector_region.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "connector_transfer",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    def govern_campaign_artifact_step(
        self,
        data_id: str,
    ) -> dict[str, Any]:
        """Govern whether data may be used in a campaign artifact step."""
        dec = self._governance.evaluate_handling(data_id, "campaign_artifact")
        _emit(self._events, "campaign_artifact_governed", {
            "data_id": data_id, "decision": dec.decision.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "campaign_artifact",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    def govern_program_reporting_output(
        self,
        data_id: str,
    ) -> dict[str, Any]:
        """Govern whether data may be included in program reporting output."""
        dec = self._governance.evaluate_handling(data_id, "program_reporting")
        _emit(self._events, "program_reporting_governed", {
            "data_id": data_id, "decision": dec.decision.value,
        }, data_id)
        return {
            "data_id": data_id,
            "operation": "program_reporting",
            "decision": dec.decision.value,
            "disposition": dec.disposition.value,
            "redaction_level": dec.redaction_level.value,
            "reason": dec.reason,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_data_governance_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist data governance state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_records": self._governance.record_count,
            "total_policies": self._governance.policy_count,
            "total_residency_constraints": self._governance.residency_constraint_count,
            "total_privacy_rules": self._governance.privacy_rule_count,
            "total_redaction_rules": self._governance.redaction_rule_count,
            "total_retention_rules": self._governance.retention_rule_count,
            "total_decisions": self._governance.decision_count,
            "total_violations": self._governance.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-dgov", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Data governance state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("data", "governance", "privacy"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "data_governance_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_data_governance_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return data governance state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_records": self._governance.record_count,
            "total_policies": self._governance.policy_count,
            "total_residency_constraints": self._governance.residency_constraint_count,
            "total_privacy_rules": self._governance.privacy_rule_count,
            "total_redaction_rules": self._governance.redaction_rule_count,
            "total_retention_rules": self._governance.retention_rule_count,
            "total_decisions": self._governance.decision_count,
            "total_violations": self._governance.violation_count,
        }
