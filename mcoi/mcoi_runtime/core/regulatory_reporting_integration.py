"""Purpose: regulatory reporting runtime integration bridge.
Governance scope: composing regulatory reporting runtime with evidence assembly
    from assurance, case closures, remediations, records, and control history;
    memory mesh and operational graph attachment.
Dependencies: regulatory_reporting engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every package creation emits events.
  - Reporting state is attached to memory mesh.
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
from .regulatory_reporting import RegulatoryReportingEngine


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


class RegulatoryReportingIntegration:
    """Integration bridge for regulatory reporting with platform layers."""

    def __init__(
        self,
        reporting_engine: RegulatoryReportingEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(reporting_engine, RegulatoryReportingEngine):
            raise RuntimeCoreInvariantError(
                "reporting_engine must be a RegulatoryReportingEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._reporting = reporting_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Package assembly helpers
    # ------------------------------------------------------------------

    def package_from_assurance(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        assurance_evidence_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Assemble a package from assurance evidence."""
        pkg = self._reporting.assemble_evidence_package(
            package_id, tenant_id, requirement_id, assurance_evidence_ids,
        )
        _emit(self._events, "package_from_assurance", {
            "package_id": package_id, "requirement_id": requirement_id,
        }, package_id)
        return {
            "package_id": pkg.package_id,
            "tenant_id": pkg.tenant_id,
            "completeness": pkg.completeness.value,
            "total_evidence_items": pkg.total_evidence_items,
            "source_type": "assurance",
        }

    def package_from_case_closure(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        case_evidence_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Assemble a package from case closure evidence."""
        pkg = self._reporting.assemble_evidence_package(
            package_id, tenant_id, requirement_id, case_evidence_ids,
        )
        _emit(self._events, "package_from_case_closure", {
            "package_id": package_id, "requirement_id": requirement_id,
        }, package_id)
        return {
            "package_id": pkg.package_id,
            "tenant_id": pkg.tenant_id,
            "completeness": pkg.completeness.value,
            "total_evidence_items": pkg.total_evidence_items,
            "source_type": "case_closure",
        }

    def package_from_remediation(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        remediation_evidence_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Assemble a package from remediation evidence."""
        pkg = self._reporting.assemble_evidence_package(
            package_id, tenant_id, requirement_id, remediation_evidence_ids,
        )
        _emit(self._events, "package_from_remediation", {
            "package_id": package_id, "requirement_id": requirement_id,
        }, package_id)
        return {
            "package_id": pkg.package_id,
            "tenant_id": pkg.tenant_id,
            "completeness": pkg.completeness.value,
            "total_evidence_items": pkg.total_evidence_items,
            "source_type": "remediation",
        }

    def package_from_records(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        record_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Assemble a package from preserved records."""
        pkg = self._reporting.assemble_evidence_package(
            package_id, tenant_id, requirement_id, record_ids,
        )
        _emit(self._events, "package_from_records", {
            "package_id": package_id, "requirement_id": requirement_id,
        }, package_id)
        return {
            "package_id": pkg.package_id,
            "tenant_id": pkg.tenant_id,
            "completeness": pkg.completeness.value,
            "total_evidence_items": pkg.total_evidence_items,
            "source_type": "records",
        }

    def package_from_control_history(
        self,
        package_id: str,
        tenant_id: str,
        requirement_id: str,
        control_evidence_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Assemble a package from control history evidence."""
        pkg = self._reporting.assemble_evidence_package(
            package_id, tenant_id, requirement_id, control_evidence_ids,
        )
        _emit(self._events, "package_from_control_history", {
            "package_id": package_id, "requirement_id": requirement_id,
        }, package_id)
        return {
            "package_id": pkg.package_id,
            "tenant_id": pkg.tenant_id,
            "completeness": pkg.completeness.value,
            "total_evidence_items": pkg.total_evidence_items,
            "source_type": "control_history",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_reporting_package_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist regulatory reporting state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_requirements": self._reporting.requirement_count,
            "total_windows": self._reporting.window_count,
            "total_packages": self._reporting.package_count,
            "total_submissions": self._reporting.submission_count,
            "total_reviews": self._reporting.review_count,
            "total_auditor_requests": self._reporting.auditor_request_count,
            "total_auditor_responses": self._reporting.auditor_response_count,
            "total_violations": self._reporting.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-rrep", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Regulatory reporting state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("regulatory", "reporting", "submission"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "reporting_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_reporting_package_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return regulatory reporting state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_requirements": self._reporting.requirement_count,
            "total_windows": self._reporting.window_count,
            "total_packages": self._reporting.package_count,
            "total_submissions": self._reporting.submission_count,
            "total_reviews": self._reporting.review_count,
            "total_auditor_requests": self._reporting.auditor_request_count,
            "total_auditor_responses": self._reporting.auditor_response_count,
            "total_violations": self._reporting.violation_count,
        }
