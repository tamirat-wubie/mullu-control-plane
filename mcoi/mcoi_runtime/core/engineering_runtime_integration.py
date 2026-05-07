"""Purpose: engineering runtime integration bridge.
Governance scope: composing engineering runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create engineering
    quantities from various platform surface sources.
Dependencies: engineering_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every engineering operation emits events.
  - Engineering state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.engineering_runtime import (
    EngineeringDomain,
    ReliabilityGrade,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .engineering_runtime import EngineeringRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-engint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class EngineeringRuntimeIntegration:
    """Integration bridge for engineering runtime with platform layers."""

    def __init__(
        self,
        engineering_engine: EngineeringRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(engineering_engine, EngineeringRuntimeEngine):
            raise RuntimeCoreInvariantError("engineering_engine must be an EngineeringRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._engineering = engineering_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic quantity and tolerance IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        quantity_id = stable_identifier("qty-engrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        tolerance_id = stable_identifier("tol-engrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return quantity_id, tolerance_id

    def _engineering_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.MECHANICAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register an engineering quantity for a given source."""
        if not quantity_id:
            quantity_id, _ = self._next_ids(tenant_id, source_type)
        else:
            self._bridge_seq += 1

        qty = self._engineering.register_quantity(
            quantity_id=quantity_id,
            tenant_id=tenant_id,
            display_name=display_name or f"{domain.value}_{source_type}",
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

        _emit(self._events, f"engineering_from_{source_type}", {
            "tenant_id": tenant_id,
            "quantity_id": quantity_id,
            "ref": ref,
        }, quantity_id)

        return {
            "quantity_id": quantity_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "domain": qty.domain.value,
            "value": qty.value,
            "unit_label": qty.unit_label,
            "tolerance": qty.tolerance,
        }

    # ------------------------------------------------------------------
    # Surface-specific engineering methods
    # ------------------------------------------------------------------

    def engineering_for_assets(
        self,
        tenant_id: str,
        asset_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.MECHANICAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for assets source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=asset_ref,
            source_type="assets",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    def engineering_for_continuity(
        self,
        tenant_id: str,
        continuity_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.ELECTRICAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for continuity source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=continuity_ref,
            source_type="continuity",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    def engineering_for_factory(
        self,
        tenant_id: str,
        factory_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.PROCESS,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for factory source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=factory_ref,
            source_type="factory",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    def engineering_for_service_capacity(
        self,
        tenant_id: str,
        service_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.ELECTRICAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for service capacity source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=service_ref,
            source_type="service_capacity",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    def engineering_for_procurement(
        self,
        tenant_id: str,
        procurement_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.STRUCTURAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for procurement source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=procurement_ref,
            source_type="procurement",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    def engineering_for_quality(
        self,
        tenant_id: str,
        quality_ref: str,
        quantity_id: str = "",
        display_name: str = "",
        value: float = 0.0,
        unit_label: str = "unit",
        domain: EngineeringDomain = EngineeringDomain.CHEMICAL,
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        """Register engineering quantity for quality source."""
        return self._engineering_for_source(
            tenant_id=tenant_id,
            ref=quality_ref,
            source_type="quality",
            quantity_id=quantity_id,
            display_name=display_name,
            value=value,
            unit_label=unit_label,
            domain=domain,
            tolerance=tolerance,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_engineering_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist engineering state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-engrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_quantities": self._engineering.quantity_count,
            "total_tolerances": self._engineering.tolerance_count,
            "total_targets": self._engineering.target_count,
            "total_margins": self._engineering.margin_count,
            "total_envelopes": self._engineering.envelope_count,
            "total_windows": self._engineering.window_count,
            "total_curves": self._engineering.curve_count,
            "total_violations": self._engineering.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Engineering state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("engineering", "quantities", "systems"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "engineering_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_engineering_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return engineering state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_quantities": self._engineering.quantity_count,
            "total_tolerances": self._engineering.tolerance_count,
            "total_targets": self._engineering.target_count,
            "total_margins": self._engineering.margin_count,
            "total_envelopes": self._engineering.envelope_count,
            "total_windows": self._engineering.window_count,
            "total_curves": self._engineering.curve_count,
            "total_violations": self._engineering.violation_count,
        }
