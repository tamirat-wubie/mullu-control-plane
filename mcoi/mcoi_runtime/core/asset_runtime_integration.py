"""Purpose: asset runtime integration bridge.
Governance scope: composing asset runtime with procurement, connectors,
    environments, campaigns, programs, vendors, and contracts; memory mesh
    and operational graph attachment.
Dependencies: asset_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every asset creation emits events.
  - Asset state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.asset_runtime import AssetKind, OwnershipType
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
from .asset_runtime import AssetRuntimeEngine


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


def _require_human_actor(field_name: str, value: str, missing_message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(missing_message)
    normalized = value.strip()
    if normalized == "system":
        raise RuntimeCoreInvariantError(f"{field_name} must exclude system")
    return normalized


class AssetRuntimeIntegration:
    """Integration bridge for asset runtime with platform layers."""

    def __init__(
        self,
        asset_engine: AssetRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(asset_engine, AssetRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "asset_engine must be an AssetRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._assets = asset_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Asset creation helpers
    # ------------------------------------------------------------------

    def asset_from_purchase_order(
        self,
        asset_id: str,
        name: str,
        tenant_id: str,
        po_ref: str,
        *,
        kind: AssetKind = AssetKind.HARDWARE,
        ownership: OwnershipType = OwnershipType.OWNED,
        vendor_ref: str = "",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an asset from a purchase order."""
        a = self._assets.register_asset(
            asset_id, name, tenant_id,
            kind=kind, ownership=ownership,
            vendor_ref=vendor_ref, value=value,
        )
        _emit(self._events, "asset_from_purchase_order", {
            "asset_id": asset_id, "po_ref": po_ref,
        }, asset_id)
        return {
            "asset_id": a.asset_id,
            "name": a.name,
            "tenant_id": a.tenant_id,
            "po_ref": po_ref,
            "kind": a.kind.value,
            "status": a.status.value,
            "value": a.value,
            "source_type": "purchase_order",
        }

    def asset_from_connector_dependency(
        self,
        asset_id: str,
        name: str,
        tenant_id: str,
        connector_ref: str,
        *,
        kind: AssetKind = AssetKind.SOFTWARE,
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an asset from a connector dependency."""
        a = self._assets.register_asset(
            asset_id, name, tenant_id,
            kind=kind, value=value,
        )
        _emit(self._events, "asset_from_connector_dependency", {
            "asset_id": asset_id, "connector_ref": connector_ref,
        }, asset_id)
        return {
            "asset_id": a.asset_id,
            "name": a.name,
            "tenant_id": a.tenant_id,
            "connector_ref": connector_ref,
            "kind": a.kind.value,
            "status": a.status.value,
            "source_type": "connector_dependency",
        }

    def asset_from_environment(
        self,
        asset_id: str,
        name: str,
        tenant_id: str,
        environment_ref: str,
        *,
        kind: AssetKind = AssetKind.INFRASTRUCTURE,
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an asset from an environment provisioning."""
        a = self._assets.register_asset(
            asset_id, name, tenant_id,
            kind=kind, value=value,
        )
        _emit(self._events, "asset_from_environment", {
            "asset_id": asset_id, "environment_ref": environment_ref,
        }, asset_id)
        return {
            "asset_id": a.asset_id,
            "name": a.name,
            "tenant_id": a.tenant_id,
            "environment_ref": environment_ref,
            "kind": a.kind.value,
            "status": a.status.value,
            "source_type": "environment",
        }

    # ------------------------------------------------------------------
    # Binding helpers
    # ------------------------------------------------------------------

    def bind_asset_to_campaign(
        self,
        assignment_id: str,
        asset_id: str,
        campaign_ref: str,
        *,
        bound_by: str = "",
    ) -> dict[str, Any]:
        """Bind an asset to a campaign."""
        normalized_bound_by = _require_human_actor(
            "bound_by", bound_by, "bound_by required for asset binding"
        )
        aa = self._assets.assign_asset(
            assignment_id, asset_id, campaign_ref, "campaign",
            assigned_by=normalized_bound_by,
        )
        _emit(self._events, "asset_bound_to_campaign", {
            "assignment_id": assignment_id, "asset_id": asset_id,
            "campaign_ref": campaign_ref,
            "bound_by": normalized_bound_by,
        }, assignment_id)
        return {
            "assignment_id": aa.assignment_id,
            "asset_id": aa.asset_id,
            "campaign_ref": campaign_ref,
            "scope_ref_type": aa.scope_ref_type,
            "bound_by": aa.assigned_by,
            "binding_type": "campaign",
        }

    def bind_asset_to_program(
        self,
        assignment_id: str,
        asset_id: str,
        program_ref: str,
        *,
        bound_by: str = "",
    ) -> dict[str, Any]:
        """Bind an asset to a program."""
        normalized_bound_by = _require_human_actor(
            "bound_by", bound_by, "bound_by required for asset binding"
        )
        aa = self._assets.assign_asset(
            assignment_id, asset_id, program_ref, "program",
            assigned_by=normalized_bound_by,
        )
        _emit(self._events, "asset_bound_to_program", {
            "assignment_id": assignment_id, "asset_id": asset_id,
            "program_ref": program_ref,
            "bound_by": normalized_bound_by,
        }, assignment_id)
        return {
            "assignment_id": aa.assignment_id,
            "asset_id": aa.asset_id,
            "program_ref": program_ref,
            "scope_ref_type": aa.scope_ref_type,
            "bound_by": aa.assigned_by,
            "binding_type": "program",
        }

    def bind_asset_to_vendor(
        self,
        assignment_id: str,
        asset_id: str,
        vendor_ref: str,
        *,
        bound_by: str = "",
    ) -> dict[str, Any]:
        """Bind an asset to a vendor."""
        normalized_bound_by = _require_human_actor(
            "bound_by", bound_by, "bound_by required for asset binding"
        )
        aa = self._assets.assign_asset(
            assignment_id, asset_id, vendor_ref, "vendor",
            assigned_by=normalized_bound_by,
        )
        _emit(self._events, "asset_bound_to_vendor", {
            "assignment_id": assignment_id, "asset_id": asset_id,
            "vendor_ref": vendor_ref,
            "bound_by": normalized_bound_by,
        }, assignment_id)
        return {
            "assignment_id": aa.assignment_id,
            "asset_id": aa.asset_id,
            "vendor_ref": vendor_ref,
            "scope_ref_type": aa.scope_ref_type,
            "bound_by": aa.assigned_by,
            "binding_type": "vendor",
        }

    def bind_asset_to_contract(
        self,
        assignment_id: str,
        asset_id: str,
        contract_ref: str,
        *,
        bound_by: str = "",
    ) -> dict[str, Any]:
        """Bind an asset to a contract."""
        normalized_bound_by = _require_human_actor(
            "bound_by", bound_by, "bound_by required for asset binding"
        )
        aa = self._assets.assign_asset(
            assignment_id, asset_id, contract_ref, "contract",
            assigned_by=normalized_bound_by,
        )
        _emit(self._events, "asset_bound_to_contract", {
            "assignment_id": assignment_id, "asset_id": asset_id,
            "contract_ref": contract_ref,
            "bound_by": normalized_bound_by,
        }, assignment_id)
        return {
            "assignment_id": aa.assignment_id,
            "asset_id": aa.asset_id,
            "contract_ref": contract_ref,
            "scope_ref_type": aa.scope_ref_type,
            "bound_by": aa.assigned_by,
            "binding_type": "contract",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_asset_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist asset state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_assets": self._assets.asset_count,
            "total_config_items": self._assets.config_item_count,
            "total_inventory": self._assets.inventory_count,
            "total_assignments": self._assets.assignment_count,
            "total_dependencies": self._assets.dependency_count,
            "total_lifecycle_events": self._assets.lifecycle_event_count,
            "total_assessments": self._assets.assessment_count,
            "total_violations": self._assets.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-asst", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Asset state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("asset", "configuration", "inventory"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "asset_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_asset_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return asset state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_assets": self._assets.asset_count,
            "total_config_items": self._assets.config_item_count,
            "total_inventory": self._assets.inventory_count,
            "total_assignments": self._assets.assignment_count,
            "total_dependencies": self._assets.dependency_count,
            "total_lifecycle_events": self._assets.lifecycle_event_count,
            "total_assessments": self._assets.assessment_count,
            "total_violations": self._assets.violation_count,
        }
