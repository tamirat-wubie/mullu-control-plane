"""Purpose: assurance runtime integration bridge.
Governance scope: composing assurance runtime with control tests, case closures,
    remediations, program health, connector stability, records, memory, events;
    memory mesh and operational graph attachment.
Dependencies: assurance_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every assurance creation emits events.
  - Assurance audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.assurance_runtime import (
    AssuranceLevel,
    AssuranceScope,
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
from .assurance_runtime import AssuranceRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-aint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AssuranceRuntimeIntegration:
    """Integration bridge for assurance runtime with platform layers."""

    def __init__(
        self,
        assurance_engine: AssuranceRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(assurance_engine, AssuranceRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "assurance_engine must be an AssuranceRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._assurance = assurance_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Attestation/certification creation helpers
    # ------------------------------------------------------------------

    def assurance_from_control_tests(
        self,
        attestation_id: str,
        tenant_id: str,
        control_id: str,
        title: str = "Control test attestation",
    ) -> dict[str, Any]:
        """Create an attestation from control test results."""
        att = self._assurance.register_attestation(
            attestation_id, tenant_id, control_id,
            scope=AssuranceScope.CONTROL,
        )
        _emit(self._events, "assurance_from_control_tests", {
            "attestation_id": attestation_id, "control_id": control_id,
        }, attestation_id)
        return {
            "attestation_id": att.attestation_id,
            "tenant_id": att.tenant_id,
            "scope": att.scope.value,
            "scope_ref_id": control_id,
            "source_type": "control_test",
        }

    def assurance_from_case_closure(
        self,
        attestation_id: str,
        tenant_id: str,
        case_id: str,
        title: str = "Case closure attestation",
    ) -> dict[str, Any]:
        """Create an attestation from a closed case."""
        att = self._assurance.register_attestation(
            attestation_id, tenant_id, case_id,
            scope=AssuranceScope.CONTROL,
        )
        _emit(self._events, "assurance_from_case_closure", {
            "attestation_id": attestation_id, "case_id": case_id,
        }, attestation_id)
        return {
            "attestation_id": att.attestation_id,
            "tenant_id": att.tenant_id,
            "scope": att.scope.value,
            "scope_ref_id": case_id,
            "source_type": "case_closure",
        }

    def assurance_from_remediation(
        self,
        attestation_id: str,
        tenant_id: str,
        remediation_id: str,
        title: str = "Remediation attestation",
    ) -> dict[str, Any]:
        """Create an attestation from a completed remediation."""
        att = self._assurance.register_attestation(
            attestation_id, tenant_id, remediation_id,
            scope=AssuranceScope.CONTROL,
        )
        _emit(self._events, "assurance_from_remediation", {
            "attestation_id": attestation_id, "remediation_id": remediation_id,
        }, attestation_id)
        return {
            "attestation_id": att.attestation_id,
            "tenant_id": att.tenant_id,
            "scope": att.scope.value,
            "scope_ref_id": remediation_id,
            "source_type": "remediation",
        }

    def assurance_from_program_health(
        self,
        certification_id: str,
        tenant_id: str,
        program_id: str,
        title: str = "Program health certification",
    ) -> dict[str, Any]:
        """Create a certification from program health metrics."""
        cert = self._assurance.register_certification(
            certification_id, tenant_id, program_id,
            scope=AssuranceScope.PROGRAM,
        )
        _emit(self._events, "assurance_from_program_health", {
            "certification_id": certification_id, "program_id": program_id,
        }, certification_id)
        return {
            "certification_id": cert.certification_id,
            "tenant_id": cert.tenant_id,
            "scope": cert.scope.value,
            "scope_ref_id": program_id,
            "source_type": "program_health",
        }

    def assurance_from_connector_stability(
        self,
        certification_id: str,
        tenant_id: str,
        connector_id: str,
        title: str = "Connector stability certification",
    ) -> dict[str, Any]:
        """Create a certification from connector stability metrics."""
        cert = self._assurance.register_certification(
            certification_id, tenant_id, connector_id,
            scope=AssuranceScope.CONNECTOR,
        )
        _emit(self._events, "assurance_from_connector_stability", {
            "certification_id": certification_id, "connector_id": connector_id,
        }, certification_id)
        return {
            "certification_id": cert.certification_id,
            "tenant_id": cert.tenant_id,
            "scope": cert.scope.value,
            "scope_ref_id": connector_id,
            "source_type": "connector_stability",
        }

    # ------------------------------------------------------------------
    # Evidence binding helpers
    # ------------------------------------------------------------------

    def bind_record_evidence(
        self,
        binding_id: str,
        target_id: str,
        target_type: str,
        record_id: str,
    ) -> dict[str, Any]:
        """Bind a preserved record as evidence."""
        b = self._assurance.bind_evidence(
            binding_id, target_id, target_type, "record", record_id,
        )
        _emit(self._events, "record_evidence_bound", {
            "binding_id": binding_id, "target_id": target_id, "record_id": record_id,
        }, target_id)
        return {
            "binding_id": b.binding_id,
            "target_id": b.target_id,
            "source_type": "record",
            "source_id": record_id,
        }

    def bind_memory_evidence(
        self,
        binding_id: str,
        target_id: str,
        target_type: str,
        memory_id: str,
    ) -> dict[str, Any]:
        """Bind a memory record as evidence."""
        b = self._assurance.bind_evidence(
            binding_id, target_id, target_type, "memory", memory_id,
        )
        _emit(self._events, "memory_evidence_bound", {
            "binding_id": binding_id, "target_id": target_id, "memory_id": memory_id,
        }, target_id)
        return {
            "binding_id": b.binding_id,
            "target_id": b.target_id,
            "source_type": "memory",
            "source_id": memory_id,
        }

    def bind_event_evidence(
        self,
        binding_id: str,
        target_id: str,
        target_type: str,
        event_id: str,
    ) -> dict[str, Any]:
        """Bind an event as evidence."""
        b = self._assurance.bind_evidence(
            binding_id, target_id, target_type, "event", event_id,
        )
        _emit(self._events, "event_evidence_bound", {
            "binding_id": binding_id, "target_id": target_id, "event_id": event_id,
        }, target_id)
        return {
            "binding_id": b.binding_id,
            "target_id": b.target_id,
            "source_type": "event",
            "source_id": event_id,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_assurance_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist assurance state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_attestations": self._assurance.attestation_count,
            "granted_attestations": self._assurance.granted_attestation_count,
            "total_certifications": self._assurance.certification_count,
            "active_certifications": self._assurance.active_certification_count,
            "total_assessments": self._assurance.assessment_count,
            "total_evidence_bindings": self._assurance.binding_count,
            "total_violations": self._assurance.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-asur", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Assurance state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("assurance", "attestation", "certification"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "assurance_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_assurance_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return assurance state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_attestations": self._assurance.attestation_count,
            "granted_attestations": self._assurance.granted_attestation_count,
            "total_certifications": self._assurance.certification_count,
            "active_certifications": self._assurance.active_certification_count,
            "total_assessments": self._assurance.assessment_count,
            "total_evidence_bindings": self._assurance.binding_count,
            "total_violations": self._assurance.violation_count,
        }
