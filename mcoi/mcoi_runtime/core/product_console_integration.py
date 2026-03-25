"""Purpose: product console integration bridge.
Governance scope: composing product console with customer runtime, marketplace,
    service catalog, workforce, billing/settlement, constitutional governance;
    memory mesh and graph attachment.
Dependencies: product_console engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every console action emits events.
  - Console state is attached to memory mesh.
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
from ..contracts.product_console import (
    ConsoleRole,
    SurfaceDisposition,
    ViewMode,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .product_console import ProductConsoleEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-consoleint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProductConsoleIntegration:
    """Integration bridge for product console with platform layers."""

    def __init__(
        self,
        console_engine: ProductConsoleEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(console_engine, ProductConsoleEngine):
            raise RuntimeCoreInvariantError(
                "console_engine must be a ProductConsoleEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._console = console_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Console from platform layers
    # ------------------------------------------------------------------

    def console_from_customer_runtime(
        self,
        tenant_id: str,
        customer_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Customer Admin Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.CUSTOMER_ADMIN,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="customer_runtime",
        )
        _emit(self._events, "console_from_customer_runtime", {
            "surface_id": surface_id, "customer_ref": customer_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "role": ConsoleRole.CUSTOMER_ADMIN.value,
            "display_name": display_name,
            "target_runtime": "customer_runtime",
            "source_type": "customer_runtime",
        }

    def console_from_marketplace_runtime(
        self,
        tenant_id: str,
        marketplace_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Partner Admin Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.PARTNER_ADMIN,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="marketplace_runtime",
        )
        _emit(self._events, "console_from_marketplace_runtime", {
            "surface_id": surface_id, "marketplace_ref": marketplace_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "marketplace_ref": marketplace_ref,
            "role": ConsoleRole.PARTNER_ADMIN.value,
            "display_name": display_name,
            "target_runtime": "marketplace_runtime",
            "source_type": "marketplace_runtime",
        }

    def console_from_service_catalog(
        self,
        tenant_id: str,
        service_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Operations Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.OPERATIONS_MANAGER,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="service_catalog",
        )
        _emit(self._events, "console_from_service_catalog", {
            "surface_id": surface_id, "service_ref": service_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "service_ref": service_ref,
            "role": ConsoleRole.OPERATIONS_MANAGER.value,
            "display_name": display_name,
            "target_runtime": "service_catalog",
            "source_type": "service_catalog",
        }

    def console_from_workforce_runtime(
        self,
        tenant_id: str,
        workforce_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Workspace Admin Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.WORKSPACE_ADMIN,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="workforce_runtime",
        )
        _emit(self._events, "console_from_workforce_runtime", {
            "surface_id": surface_id, "workforce_ref": workforce_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "workforce_ref": workforce_ref,
            "role": ConsoleRole.WORKSPACE_ADMIN.value,
            "display_name": display_name,
            "target_runtime": "workforce_runtime",
            "source_type": "workforce_runtime",
        }

    def console_from_billing_and_settlement(
        self,
        tenant_id: str,
        billing_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Tenant Admin Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.TENANT_ADMIN,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="billing_settlement",
        )
        _emit(self._events, "console_from_billing_and_settlement", {
            "surface_id": surface_id, "billing_ref": billing_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "billing_ref": billing_ref,
            "role": ConsoleRole.TENANT_ADMIN.value,
            "display_name": display_name,
            "target_runtime": "billing_settlement",
            "source_type": "billing_settlement",
        }

    def console_from_constitutional_governance(
        self,
        tenant_id: str,
        governance_ref: str,
        surface_id: str,
        panel_id: str,
        display_name: str = "Compliance Viewer Console",
    ) -> dict[str, Any]:
        surface = self._console.register_surface(
            surface_id=surface_id,
            tenant_id=tenant_id,
            display_name=display_name,
            role=ConsoleRole.COMPLIANCE_VIEWER,
            disposition=SurfaceDisposition.VISIBLE,
        )
        panel = self._console.register_panel(
            panel_id=panel_id,
            tenant_id=tenant_id,
            surface_ref=surface_id,
            display_name=f"{display_name} - Panel",
            target_runtime="constitutional_governance",
        )
        _emit(self._events, "console_from_constitutional_governance", {
            "surface_id": surface_id, "governance_ref": governance_ref, "tenant_id": tenant_id,
        }, surface_id)
        return {
            "surface_id": surface.surface_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "governance_ref": governance_ref,
            "role": ConsoleRole.COMPLIANCE_VIEWER.value,
            "display_name": display_name,
            "target_runtime": "constitutional_governance",
            "source_type": "constitutional_governance",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_console_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-console", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "surfaces": self._console.surface_count,
            "nodes": self._console.node_count,
            "panels": self._console.panel_count,
            "sessions": self._console.session_count,
            "actions": self._console.action_count,
            "decisions": self._console.decision_count,
            "violations": self._console.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Product console state",
            content=content,
            tags=("product_console", "admin", "multi_tenant"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_console_to_memory", {"memory_id": mid, "scope_ref_id": scope_ref_id}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_console_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "surfaces": self._console.surface_count,
            "nodes": self._console.node_count,
            "panels": self._console.panel_count,
            "sessions": self._console.session_count,
            "actions": self._console.action_count,
            "decisions": self._console.decision_count,
            "violations": self._console.violation_count,
        }
