"""Purpose: workforce runtime integration bridge.
Governance scope: composing workforce runtime with campaigns, case reviews,
    service requests, remediation, regulatory review, human workflow;
    memory mesh and graph attachment.
Dependencies: workforce_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every assignment action emits events.
  - Workforce state is attached to memory mesh.
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
from .workforce_runtime import WorkforceRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-wkfint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class WorkforceRuntimeIntegration:
    """Integration bridge for workforce runtime with platform layers."""

    def __init__(
        self,
        workforce_engine: WorkforceRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(workforce_engine, WorkforceRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "workforce_engine must be a WorkforceRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._workforce = workforce_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Assignment from platform layers
    # ------------------------------------------------------------------

    def assignment_from_campaign(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        campaign_ref: str,
        role_ref: str,
        priority: int = 1,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=campaign_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="campaign",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_campaign", {
            "request_id": request_id, "campaign_ref": campaign_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "campaign_ref": campaign_ref,
            "source_type": "campaign",
        }

    def assignment_from_case_review(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        case_ref: str,
        role_ref: str,
        priority: int = 2,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=case_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="case_review",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_case_review", {
            "request_id": request_id, "case_ref": case_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "case_ref": case_ref,
            "source_type": "case_review",
        }

    def assignment_from_service_request(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        service_ref: str,
        role_ref: str,
        priority: int = 1,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=service_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="service_request",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_service_request", {
            "request_id": request_id, "service_ref": service_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "service_ref": service_ref,
            "source_type": "service_request",
        }

    def assignment_from_remediation(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        remediation_ref: str,
        role_ref: str,
        priority: int = 3,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=remediation_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="remediation",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_remediation", {
            "request_id": request_id, "remediation_ref": remediation_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "remediation_ref": remediation_ref,
            "source_type": "remediation",
        }

    def assignment_from_regulatory_review(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        regulatory_ref: str,
        role_ref: str,
        priority: int = 3,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=regulatory_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="regulatory_review",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_regulatory_review", {
            "request_id": request_id, "regulatory_ref": regulatory_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "regulatory_ref": regulatory_ref,
            "source_type": "regulatory_review",
        }

    def assignment_from_human_workflow(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        workflow_ref: str,
        role_ref: str,
        priority: int = 2,
    ) -> dict[str, Any]:
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=workflow_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="human_workflow",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_from_human_workflow", {
            "request_id": request_id, "workflow_ref": workflow_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "workflow_ref": workflow_ref,
            "source_type": "human_workflow",
        }

    # ------------------------------------------------------------------
    # Cross-domain: workforce + constraint solver
    # ------------------------------------------------------------------

    def assignment_with_constraint_solving(
        self,
        request_id: str,
        decision_id: str,
        tenant_id: str,
        worker_ref: str,
        task_ref: str,
        constraint_ref: str = "",
        role_ref: str = "constraint_solver",
        priority: int = 2,
        description: str = "constraint-optimized assignment",
    ) -> dict[str, Any]:
        """Create a workforce assignment that references a constraint solver solution."""
        req = self._workforce.request_assignment(
            request_id=request_id,
            tenant_id=tenant_id,
            scope_ref_id=task_ref,
            role_ref=role_ref,
            priority=priority,
            source_type="constraint_solving",
        )
        dec = self._workforce.assign_to_lowest_load(
            decision_id=decision_id,
            request_id=request_id,
        )
        _emit(self._events, "assignment_with_constraint_solving", {
            "request_id": request_id, "worker_ref": worker_ref,
            "task_ref": task_ref, "constraint_ref": constraint_ref,
            "description": description,
        }, request_id)
        return {
            "request_id": req.request_id,
            "decision_id": dec.decision_id,
            "worker_id": dec.worker_id,
            "disposition": dec.disposition.value,
            "tenant_id": tenant_id,
            "worker_ref": worker_ref,
            "task_ref": task_ref,
            "constraint_ref": constraint_ref,
            "source_type": "constraint_solving",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_workforce_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-wkf", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "workers": self._workforce.worker_count,
            "role_capacities": self._workforce.role_capacity_count,
            "team_capacities": self._workforce.team_capacity_count,
            "requests": self._workforce.request_count,
            "decisions": self._workforce.decision_count,
            "gaps": self._workforce.gap_count,
            "violations": self._workforce.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Workforce runtime state",
            content=content,
            tags=("workforce", "capacity", "assignment"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_workforce_to_memory", {"memory_id": mid, "scope_ref_id": scope_ref_id}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_workforce_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "workers": self._workforce.worker_count,
            "role_capacities": self._workforce.role_capacity_count,
            "team_capacities": self._workforce.team_capacity_count,
            "requests": self._workforce.request_count,
            "decisions": self._workforce.decision_count,
            "gaps": self._workforce.gap_count,
            "violations": self._workforce.violation_count,
        }
