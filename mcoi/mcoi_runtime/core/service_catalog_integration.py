"""Purpose: service catalog runtime integration bridge.
Governance scope: composing service catalog runtime with campaigns,
    programs, assets, procurement, budgets, availability, contracts,
    and SLAs; memory mesh and operational graph attachment.
Dependencies: service_catalog engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every request creation emits events.
  - Request state is attached to memory mesh.
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
from ..contracts.service_catalog import CatalogItemKind, RequestPriority
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .service_catalog import ServiceCatalogEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-sint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ServiceCatalogIntegration:
    """Integration bridge for service catalog runtime with platform layers."""

    def __init__(
        self,
        catalog_engine: ServiceCatalogEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(catalog_engine, ServiceCatalogEngine):
            raise RuntimeCoreInvariantError(
                "catalog_engine must be a ServiceCatalogEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._catalog = catalog_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Request creation helpers
    # ------------------------------------------------------------------

    def request_from_campaign_need(
        self,
        request_id: str,
        item_id: str,
        tenant_id: str,
        requester_ref: str,
        campaign_ref: str,
        *,
        priority: RequestPriority = RequestPriority.MEDIUM,
    ) -> dict[str, Any]:
        """Create a service request from a campaign need."""
        req = self._catalog.submit_request(
            request_id, item_id, tenant_id, requester_ref,
            priority=priority,
            description=f"Campaign need: {campaign_ref}",
        )
        _emit(self._events, "request_from_campaign_need", {
            "request_id": request_id, "campaign_ref": campaign_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "tenant_id": req.tenant_id,
            "campaign_ref": campaign_ref,
            "priority": req.priority.value,
            "status": req.status.value,
            "source_type": "campaign_need",
        }

    def request_from_program_need(
        self,
        request_id: str,
        item_id: str,
        tenant_id: str,
        requester_ref: str,
        program_ref: str,
        *,
        priority: RequestPriority = RequestPriority.MEDIUM,
    ) -> dict[str, Any]:
        """Create a service request from a program need."""
        req = self._catalog.submit_request(
            request_id, item_id, tenant_id, requester_ref,
            priority=priority,
            description=f"Program need: {program_ref}",
        )
        _emit(self._events, "request_from_program_need", {
            "request_id": request_id, "program_ref": program_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "tenant_id": req.tenant_id,
            "program_ref": program_ref,
            "priority": req.priority.value,
            "status": req.status.value,
            "source_type": "program_need",
        }

    def request_from_asset_gap(
        self,
        request_id: str,
        item_id: str,
        tenant_id: str,
        requester_ref: str,
        asset_ref: str,
        *,
        priority: RequestPriority = RequestPriority.HIGH,
    ) -> dict[str, Any]:
        """Create a service request from an asset gap."""
        req = self._catalog.submit_request(
            request_id, item_id, tenant_id, requester_ref,
            priority=priority,
            description=f"Asset gap: {asset_ref}",
        )
        _emit(self._events, "request_from_asset_gap", {
            "request_id": request_id, "asset_ref": asset_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "tenant_id": req.tenant_id,
            "asset_ref": asset_ref,
            "priority": req.priority.value,
            "status": req.status.value,
            "source_type": "asset_gap",
        }

    def request_from_procurement_need(
        self,
        request_id: str,
        item_id: str,
        tenant_id: str,
        requester_ref: str,
        procurement_ref: str,
        *,
        priority: RequestPriority = RequestPriority.MEDIUM,
        estimated_cost: float = 0.0,
    ) -> dict[str, Any]:
        """Create a service request from a procurement need."""
        req = self._catalog.submit_request(
            request_id, item_id, tenant_id, requester_ref,
            priority=priority, estimated_cost=estimated_cost,
            description=f"Procurement need: {procurement_ref}",
        )
        _emit(self._events, "request_from_procurement_need", {
            "request_id": request_id, "procurement_ref": procurement_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "tenant_id": req.tenant_id,
            "procurement_ref": procurement_ref,
            "estimated_cost": req.estimated_cost,
            "priority": req.priority.value,
            "status": req.status.value,
            "source_type": "procurement_need",
        }

    # ------------------------------------------------------------------
    # Binding helpers
    # ------------------------------------------------------------------

    def bind_request_to_budget(
        self,
        request_id: str,
        budget_ref: str,
    ) -> dict[str, Any]:
        """Bind a request to a budget reference."""
        req = self._catalog.get_request(request_id)
        _emit(self._events, "request_bound_to_budget", {
            "request_id": request_id, "budget_ref": budget_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "budget_ref": budget_ref,
            "estimated_cost": req.estimated_cost,
            "status": req.status.value,
            "binding_type": "budget",
        }

    def bind_request_to_availability(
        self,
        request_id: str,
        availability_ref: str,
    ) -> dict[str, Any]:
        """Bind a request to an availability window."""
        req = self._catalog.get_request(request_id)
        _emit(self._events, "request_bound_to_availability", {
            "request_id": request_id, "availability_ref": availability_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "availability_ref": availability_ref,
            "status": req.status.value,
            "binding_type": "availability",
        }

    def bind_request_to_contract_sla(
        self,
        request_id: str,
        contract_ref: str,
        sla_ref: str,
    ) -> dict[str, Any]:
        """Bind a request to a contract SLA."""
        req = self._catalog.get_request(request_id)
        _emit(self._events, "request_bound_to_contract_sla", {
            "request_id": request_id, "contract_ref": contract_ref,
            "sla_ref": sla_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "contract_ref": contract_ref,
            "sla_ref": sla_ref,
            "status": req.status.value,
            "binding_type": "contract_sla",
        }

    def bind_request_to_work_campaign(
        self,
        request_id: str,
        campaign_ref: str,
    ) -> dict[str, Any]:
        """Bind a request to a work campaign."""
        req = self._catalog.get_request(request_id)
        _emit(self._events, "request_bound_to_work_campaign", {
            "request_id": request_id, "campaign_ref": campaign_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "campaign_ref": campaign_ref,
            "status": req.status.value,
            "binding_type": "work_campaign",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_request_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist request state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_catalog_items": self._catalog.catalog_count,
            "total_requests": self._catalog.request_count,
            "total_assignments": self._catalog.assignment_count,
            "total_entitlements": self._catalog.entitlement_count,
            "total_tasks": self._catalog.task_count,
            "total_decisions": self._catalog.decision_count,
            "total_violations": self._catalog.violation_count,
            "total_assessments": self._catalog.assessment_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-scat", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Service catalog state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("service_catalog", "request", "fulfillment"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "request_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_request_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return request state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_catalog_items": self._catalog.catalog_count,
            "total_requests": self._catalog.request_count,
            "total_assignments": self._catalog.assignment_count,
            "total_entitlements": self._catalog.entitlement_count,
            "total_tasks": self._catalog.task_count,
            "total_decisions": self._catalog.decision_count,
            "total_violations": self._catalog.violation_count,
            "total_assessments": self._catalog.assessment_count,
        }
