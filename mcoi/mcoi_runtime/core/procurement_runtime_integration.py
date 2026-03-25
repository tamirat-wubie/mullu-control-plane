"""Purpose: procurement runtime integration bridge.
Governance scope: composing procurement runtime with budgets, contracts,
    connectors, assets, and fault histories; memory mesh and operational
    graph attachment.
Dependencies: procurement_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every procurement creation emits events.
  - Procurement state is attached to memory mesh.
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
from .procurement_runtime import ProcurementRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProcurementRuntimeIntegration:
    """Integration bridge for procurement runtime with platform layers."""

    def __init__(
        self,
        procurement_engine: ProcurementRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(procurement_engine, ProcurementRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "procurement_engine must be a ProcurementRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._procurement = procurement_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Procurement creation helpers
    # ------------------------------------------------------------------

    def procurement_from_budget_need(
        self,
        request_id: str,
        vendor_id: str,
        tenant_id: str,
        budget_ref: str,
        amount: float,
        *,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a procurement request from a budget need."""
        req = self._procurement.create_request(
            request_id, vendor_id, tenant_id, amount,
            currency=currency,
            description=f"Budget need: {budget_ref}",
        )
        _emit(self._events, "procurement_from_budget_need", {
            "request_id": request_id, "budget_ref": budget_ref,
            "amount": amount,
        }, request_id)
        return {
            "request_id": req.request_id,
            "vendor_id": req.vendor_id,
            "tenant_id": req.tenant_id,
            "budget_ref": budget_ref,
            "estimated_amount": req.estimated_amount,
            "status": req.status.value,
            "source_type": "budget_need",
        }

    def procurement_from_contract_renewal(
        self,
        renewal_id: str,
        vendor_id: str,
        contract_ref: str,
        opens_at: str,
        closes_at: str,
    ) -> dict[str, Any]:
        """Schedule a procurement renewal from a contract renewal."""
        ren = self._procurement.schedule_renewal(
            renewal_id, vendor_id, contract_ref, opens_at, closes_at,
        )
        _emit(self._events, "procurement_from_contract_renewal", {
            "renewal_id": renewal_id, "contract_ref": contract_ref,
        }, renewal_id)
        return {
            "renewal_id": ren.renewal_id,
            "vendor_id": ren.vendor_id,
            "contract_ref": ren.contract_ref,
            "disposition": ren.disposition.value,
            "source_type": "contract_renewal",
        }

    def procurement_from_connector_requirement(
        self,
        request_id: str,
        vendor_id: str,
        tenant_id: str,
        connector_ref: str,
        amount: float,
        *,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a procurement request from a connector requirement."""
        req = self._procurement.create_request(
            request_id, vendor_id, tenant_id, amount,
            currency=currency,
            description=f"Connector requirement: {connector_ref}",
        )
        _emit(self._events, "procurement_from_connector_requirement", {
            "request_id": request_id, "connector_ref": connector_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "vendor_id": req.vendor_id,
            "tenant_id": req.tenant_id,
            "connector_ref": connector_ref,
            "estimated_amount": req.estimated_amount,
            "status": req.status.value,
            "source_type": "connector_requirement",
        }

    def procurement_from_asset_need(
        self,
        request_id: str,
        vendor_id: str,
        tenant_id: str,
        asset_ref: str,
        amount: float,
        *,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a procurement request from an asset need."""
        req = self._procurement.create_request(
            request_id, vendor_id, tenant_id, amount,
            currency=currency,
            description=f"Asset need: {asset_ref}",
        )
        _emit(self._events, "procurement_from_asset_need", {
            "request_id": request_id, "asset_ref": asset_ref,
        }, request_id)
        return {
            "request_id": req.request_id,
            "vendor_id": req.vendor_id,
            "tenant_id": req.tenant_id,
            "asset_ref": asset_ref,
            "estimated_amount": req.estimated_amount,
            "status": req.status.value,
            "source_type": "asset_need",
        }

    def vendor_risk_from_faults(
        self,
        assessment_id: str,
        vendor_id: str,
        performance_score: float,
        fault_count: int,
        *,
        assessed_by: str = "fault_engine",
    ) -> dict[str, Any]:
        """Assess vendor risk from fault history."""
        a = self._procurement.assess_vendor(
            assessment_id, vendor_id, performance_score, fault_count,
            assessed_by=assessed_by,
        )
        _emit(self._events, "vendor_risk_from_faults", {
            "assessment_id": assessment_id, "vendor_id": vendor_id,
            "risk_level": a.risk_level.value,
        }, vendor_id)
        return {
            "assessment_id": a.assessment_id,
            "vendor_id": a.vendor_id,
            "risk_level": a.risk_level.value,
            "performance_score": a.performance_score,
            "fault_count": a.fault_count,
            "source_type": "fault_history",
        }

    def bind_po_to_financial_runtime(
        self,
        po_id: str,
        invoice_ref: str,
    ) -> dict[str, Any]:
        """Bind a PO to a financial runtime invoice reference."""
        po = self._procurement.get_po(po_id)
        _emit(self._events, "po_bound_to_financial", {
            "po_id": po_id, "invoice_ref": invoice_ref,
        }, po_id)
        return {
            "po_id": po.po_id,
            "vendor_id": po.vendor_id,
            "amount": po.amount,
            "invoice_ref": invoice_ref,
            "status": po.status.value,
            "binding_type": "financial",
        }

    def bind_vendor_to_contract_runtime(
        self,
        commitment_id: str,
        vendor_id: str,
        contract_ref: str,
        *,
        description: str = "",
        target_value: str = "",
    ) -> dict[str, Any]:
        """Bind a vendor to a contract runtime commitment."""
        c = self._procurement.register_commitment(
            commitment_id, vendor_id, contract_ref,
            description=description, target_value=target_value,
        )
        _emit(self._events, "vendor_bound_to_contract", {
            "commitment_id": commitment_id, "vendor_id": vendor_id,
            "contract_ref": contract_ref,
        }, commitment_id)
        return {
            "commitment_id": c.commitment_id,
            "vendor_id": c.vendor_id,
            "contract_ref": c.contract_ref,
            "binding_type": "contract",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_procurement_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist procurement state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_vendors": self._procurement.vendor_count,
            "total_requests": self._procurement.request_count,
            "total_purchase_orders": self._procurement.po_count,
            "total_assessments": self._procurement.assessment_count,
            "total_commitments": self._procurement.commitment_count,
            "total_renewals": self._procurement.renewal_count,
            "total_violations": self._procurement.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-proc", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Procurement state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("procurement", "vendor", "purchasing"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "procurement_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_procurement_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return procurement state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_vendors": self._procurement.vendor_count,
            "total_requests": self._procurement.request_count,
            "total_purchase_orders": self._procurement.po_count,
            "total_assessments": self._procurement.assessment_count,
            "total_commitments": self._procurement.commitment_count,
            "total_renewals": self._procurement.renewal_count,
            "total_violations": self._procurement.violation_count,
        }
