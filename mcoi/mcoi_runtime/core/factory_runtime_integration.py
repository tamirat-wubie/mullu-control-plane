"""Purpose: factory runtime integration bridge.
Governance scope: composing factory runtime with procurement, asset,
    workforce, continuity, service, and financial scopes; memory mesh
    and operational graph attachment.
Dependencies: factory_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every factory creation emits events.
  - Factory state is attached to memory mesh.
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
from .factory_runtime import FactoryRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class FactoryRuntimeIntegration:
    """Integration bridge for factory runtime with platform layers."""

    def __init__(
        self,
        factory_engine: FactoryRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(factory_engine, FactoryRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "factory_engine must be a FactoryRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._factory = factory_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Bridge helpers (each registers a plant + creates a work order)
    # ------------------------------------------------------------------

    def _bridge(
        self,
        source_type: str,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        source_ref: str,
    ) -> dict[str, Any]:
        plant = self._factory.register_plant(plant_id, tenant_id, display_name)
        order = self._factory.create_work_order(
            order_id, tenant_id, plant_id, product_ref, quantity,
        )
        _emit(self._events, f"factory_from_{source_type}", {
            "plant_id": plant_id, "order_id": order_id, "source_ref": source_ref,
        }, plant_id)
        return {
            "plant_id": plant.plant_id,
            "tenant_id": plant.tenant_id,
            "display_name": plant.display_name,
            "order_id": order.order_id,
            "product_ref": order.product_ref,
            "quantity": order.quantity,
            "status": order.status.value,
            "source_type": source_type,
        }

    def factory_from_procurement(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        procurement_ref: str = "procurement",
    ) -> dict[str, Any]:
        """Create factory plant and order from a procurement source."""
        return self._bridge(
            "procurement", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, procurement_ref,
        )

    def factory_from_asset_deployment(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        asset_ref: str = "asset_deployment",
    ) -> dict[str, Any]:
        """Create factory plant and order from an asset deployment."""
        return self._bridge(
            "asset_deployment", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, asset_ref,
        )

    def factory_from_workforce_assignment(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        workforce_ref: str = "workforce_assignment",
    ) -> dict[str, Any]:
        """Create factory plant and order from a workforce assignment."""
        return self._bridge(
            "workforce_assignment", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, workforce_ref,
        )

    def factory_from_continuity_event(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        continuity_ref: str = "continuity_event",
    ) -> dict[str, Any]:
        """Create factory plant and order from a continuity event."""
        return self._bridge(
            "continuity_event", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, continuity_ref,
        )

    def factory_from_service_request(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        service_ref: str = "service_request",
    ) -> dict[str, Any]:
        """Create factory plant and order from a service request."""
        return self._bridge(
            "service_request", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, service_ref,
        )

    def factory_from_financial_budget(
        self,
        plant_id: str,
        tenant_id: str,
        display_name: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        *,
        budget_ref: str = "financial_budget",
    ) -> dict[str, Any]:
        """Create factory plant and order from a financial budget."""
        return self._bridge(
            "financial_budget", plant_id, tenant_id, display_name,
            order_id, product_ref, quantity, budget_ref,
        )

    # ------------------------------------------------------------------
    # Cross-domain: factory + engineering tolerance check
    # ------------------------------------------------------------------

    def factory_with_engineering_check(
        self,
        tenant_id: str,
        plant_id: str,
        order_id: str,
        product_ref: str,
        quantity: int,
        engineering_ref: str = "",
        description: str = "engineering-checked order",
    ) -> dict[str, Any]:
        """Create a factory work order that references an engineering tolerance check."""
        display_name = f"eng-checked-{plant_id}"
        plant = self._factory.register_plant(plant_id, tenant_id, display_name)
        order = self._factory.create_work_order(
            order_id, tenant_id, plant_id, product_ref, quantity,
        )
        _emit(self._events, "factory_with_engineering_check", {
            "plant_id": plant_id, "order_id": order_id,
            "engineering_ref": engineering_ref, "description": description,
        }, plant_id)
        return {
            "plant_id": plant.plant_id,
            "tenant_id": plant.tenant_id,
            "display_name": plant.display_name,
            "order_id": order.order_id,
            "product_ref": order.product_ref,
            "quantity": order.quantity,
            "status": order.status.value,
            "engineering_ref": engineering_ref,
            "source_type": "engineering_check",
            "description": description,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_factory_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist factory state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_plants": self._factory.plant_count,
            "total_lines": self._factory.line_count,
            "total_orders": self._factory.order_count,
            "total_batches": self._factory.batch_count,
            "total_checks": self._factory.check_count,
            "total_downtime_events": self._factory.downtime_count,
            "total_violations": self._factory.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-fac", {
                "scope": scope_ref_id,
                "seq": str(self._memory.memory_count),
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Factory state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("factory", "production", "quality"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "factory_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_factory_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return factory state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_plants": self._factory.plant_count,
            "total_lines": self._factory.line_count,
            "total_orders": self._factory.order_count,
            "total_batches": self._factory.batch_count,
            "total_checks": self._factory.check_count,
            "total_downtime_events": self._factory.downtime_count,
            "total_violations": self._factory.violation_count,
        }
