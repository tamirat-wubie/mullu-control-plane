"""Purpose: remediation runtime integration bridge.
Governance scope: composing remediation runtime with cases, findings,
    control failures, fault campaigns, campaigns, portfolios; memory mesh
    and operational graph attachment.
Dependencies: remediation_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every remediation creation emits events.
  - Remediation audit state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.remediation_runtime import (
    RemediationPriority,
    RemediationType,
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
from .remediation_runtime import RemediationRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-rmint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class RemediationRuntimeIntegration:
    """Integration bridge for remediation runtime with platform layers."""

    def __init__(
        self,
        remediation_engine: RemediationRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(remediation_engine, RemediationRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "remediation_engine must be a RemediationRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._remediation = remediation_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Remediation creation helpers
    # ------------------------------------------------------------------

    def _create_remediation(
        self,
        remediation_id: str,
        tenant_id: str,
        title: str,
        source_type: str,
        source_id: str,
        remediation_type: RemediationType,
        priority: RemediationPriority,
        action_name: str,
        case_id: str = "",
        finding_id: str = "",
    ) -> dict[str, Any]:
        rec = self._remediation.create_remediation(
            remediation_id, tenant_id, title,
            case_id=case_id,
            finding_id=finding_id,
            remediation_type=remediation_type,
            priority=priority,
        )
        _emit(self._events, action_name, {
            "remediation_id": remediation_id,
            "source_type": source_type,
            "source_id": source_id,
        }, remediation_id)
        return {
            "remediation_id": rec.remediation_id,
            "tenant_id": rec.tenant_id,
            "type": rec.remediation_type.value,
            "priority": rec.priority.value,
            "source_type": source_type,
            "source_id": source_id,
        }

    def remediation_from_case(
        self,
        remediation_id: str,
        tenant_id: str,
        case_id: str,
        title: str = "Case remediation",
    ) -> dict[str, Any]:
        """Create a remediation from a case decision."""
        return self._create_remediation(
            remediation_id, tenant_id, title,
            "case", case_id,
            RemediationType.CORRECTIVE, RemediationPriority.MEDIUM,
            "remediation_from_case",
            case_id=case_id,
        )

    def remediation_from_finding(
        self,
        remediation_id: str,
        tenant_id: str,
        finding_id: str,
        case_id: str = "",
        title: str = "Finding remediation",
        priority: RemediationPriority = RemediationPriority.HIGH,
    ) -> dict[str, Any]:
        """Create a remediation from a case finding."""
        return self._create_remediation(
            remediation_id, tenant_id, title,
            "finding", finding_id,
            RemediationType.CORRECTIVE, priority,
            "remediation_from_finding",
            case_id=case_id,
            finding_id=finding_id,
        )

    def remediation_from_control_failure(
        self,
        remediation_id: str,
        tenant_id: str,
        control_id: str,
        title: str = "Control failure remediation",
    ) -> dict[str, Any]:
        """Create a remediation from a compliance control failure."""
        return self._create_remediation(
            remediation_id, tenant_id, title,
            "control_failure", control_id,
            RemediationType.CORRECTIVE, RemediationPriority.HIGH,
            "remediation_from_control_failure",
        )

    def remediation_from_fault_campaign(
        self,
        remediation_id: str,
        tenant_id: str,
        fault_campaign_id: str,
        title: str = "Fault campaign remediation",
    ) -> dict[str, Any]:
        """Create a remediation from a fault campaign result."""
        return self._create_remediation(
            remediation_id, tenant_id, title,
            "fault_campaign", fault_campaign_id,
            RemediationType.PREVENTIVE, RemediationPriority.MEDIUM,
            "remediation_from_fault_campaign",
        )

    # ------------------------------------------------------------------
    # Cross-domain attachment helpers
    # ------------------------------------------------------------------

    def attach_remediation_to_campaigns(
        self,
        remediation_id: str,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Link a remediation to a campaign for tracking."""
        rem = self._remediation.get_remediation(remediation_id)
        _emit(self._events, "remediation_attached_to_campaign", {
            "remediation_id": remediation_id,
            "campaign_id": campaign_id,
        }, remediation_id)
        return {
            "remediation_id": rem.remediation_id,
            "campaign_id": campaign_id,
            "status": rem.status.value,
        }

    def attach_remediation_to_portfolio(
        self,
        remediation_id: str,
        portfolio_id: str,
    ) -> dict[str, Any]:
        """Link a remediation to a portfolio for executive visibility."""
        rem = self._remediation.get_remediation(remediation_id)
        _emit(self._events, "remediation_attached_to_portfolio", {
            "remediation_id": remediation_id,
            "portfolio_id": portfolio_id,
        }, remediation_id)
        return {
            "remediation_id": rem.remediation_id,
            "portfolio_id": portfolio_id,
            "status": rem.status.value,
            "priority": rem.priority.value,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_remediation_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist remediation state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_remediations": self._remediation.remediation_count,
            "open_remediations": self._remediation.open_remediation_count,
            "total_corrective": self._remediation.corrective_count,
            "total_preventive": self._remediation.preventive_count,
            "total_verifications": self._remediation.verification_count,
            "total_reopens": self._remediation.reopen_count,
            "total_decisions": self._remediation.decision_count,
            "total_violations": self._remediation.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-rmed", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Remediation state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("remediation", "corrective", "preventive"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "remediation_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_remediation_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return remediation state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_remediations": self._remediation.remediation_count,
            "open_remediations": self._remediation.open_remediation_count,
            "total_corrective": self._remediation.corrective_count,
            "total_preventive": self._remediation.preventive_count,
            "total_verifications": self._remediation.verification_count,
            "total_reopens": self._remediation.reopen_count,
            "total_decisions": self._remediation.decision_count,
            "total_violations": self._remediation.violation_count,
        }
