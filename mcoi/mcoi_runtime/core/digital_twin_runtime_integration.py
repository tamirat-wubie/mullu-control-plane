"""Purpose: digital twin runtime integration bridge.
Governance scope: composing digital twin runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create twin bindings
    from various platform runtime sources.
Dependencies: digital_twin_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every twin operation emits events.
  - Twin state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.digital_twin_runtime import (
    TwinObjectKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .digital_twin_runtime import DigitalTwinRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-dtint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class DigitalTwinRuntimeIntegration:
    """Integration bridge for digital twin runtime with platform layers."""

    def __init__(
        self,
        twin_engine: DigitalTwinRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(twin_engine, DigitalTwinRuntimeEngine):
            raise RuntimeCoreInvariantError("twin_engine must be a DigitalTwinRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._twin = twin_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic model and object IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        model_id = stable_identifier("mdl-dtrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        object_id = stable_identifier("obj-dtrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return model_id, object_id

    def _twin_from_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        model_id: str,
        object_id: str,
        kind: TwinObjectKind = TwinObjectKind.MACHINE,
    ) -> dict[str, Any]:
        """Register a twin model and object for a given source."""
        if not model_id or not object_id:
            model_id, object_id = self._next_ids(tenant_id, source_type)
        else:
            self._bridge_seq += 1

        model = self._twin.register_twin_model(
            model_id=model_id,
            tenant_id=tenant_id,
            display_name=f"{source_type}_{ref}",
        )
        obj = self._twin.register_twin_object(
            object_id=object_id,
            tenant_id=tenant_id,
            model_ref=model_id,
            kind=kind,
            display_name=f"{kind.value}_{source_type}",
        )

        _emit(self._events, f"twin_from_{source_type}", {
            "tenant_id": tenant_id,
            "model_id": model_id,
            "object_id": object_id,
            "ref": ref,
        }, model_id)

        return {
            "model_id": model_id,
            "object_id": object_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "kind": obj.kind.value,
            "status": model.status.value,
            "state": obj.state.value,
        }

    # ------------------------------------------------------------------
    # Source-specific twin methods
    # ------------------------------------------------------------------

    def twin_from_factory_runtime(
        self,
        tenant_id: str,
        factory_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from factory runtime."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=factory_ref,
            source_type="factory_runtime",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.LINE,
        )

    def twin_from_asset_runtime(
        self,
        tenant_id: str,
        asset_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from asset runtime."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=asset_ref,
            source_type="asset_runtime",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.MACHINE,
        )

    def twin_from_geometry_runtime(
        self,
        tenant_id: str,
        geometry_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from geometry runtime."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=geometry_ref,
            source_type="geometry_runtime",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.SITE,
        )

    def twin_from_observability(
        self,
        tenant_id: str,
        trace_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from observability."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=trace_ref,
            source_type="observability",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.SENSOR,
        )

    def twin_from_continuity_runtime(
        self,
        tenant_id: str,
        continuity_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from continuity runtime."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=continuity_ref,
            source_type="continuity_runtime",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.STATION,
        )

    def twin_from_workforce_runtime(
        self,
        tenant_id: str,
        workforce_ref: str,
        model_id: str = "",
        object_id: str = "",
    ) -> dict[str, Any]:
        """Register twin model and object from workforce runtime."""
        return self._twin_from_source(
            tenant_id=tenant_id,
            ref=workforce_ref,
            source_type="workforce_runtime",
            model_id=model_id,
            object_id=object_id,
            kind=TwinObjectKind.COMPONENT,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_twin_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist twin state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-dtrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_models": self._twin.model_count,
            "total_objects": self._twin.object_count,
            "total_assemblies": self._twin.assembly_count,
            "total_states": self._twin.state_count,
            "total_bindings": self._twin.binding_count,
            "total_syncs": self._twin.sync_count,
            "total_violations": self._twin.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Digital twin state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("digital_twin", "physical", "topology"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "twin_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_twin_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return twin state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_models": self._twin.model_count,
            "total_objects": self._twin.object_count,
            "total_assemblies": self._twin.assembly_count,
            "total_states": self._twin.state_count,
            "total_bindings": self._twin.binding_count,
            "total_syncs": self._twin.sync_count,
            "total_violations": self._twin.violation_count,
        }
