"""Purpose: geometry runtime integration bridge.
Governance scope: composing geometry runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create geometry bindings
    from various platform surface sources.
Dependencies: geometry_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every geometry operation emits events.
  - Geometry state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.geometry_runtime import (
    GeometryKind,
    RegionDisposition,
    RoutingDisposition,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .geometry_runtime import GeometryRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-geoint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class GeometryRuntimeIntegration:
    """Integration bridge for geometry runtime with platform layers."""

    def __init__(
        self,
        geometry_engine: GeometryRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(geometry_engine, GeometryRuntimeEngine):
            raise RuntimeCoreInvariantError("geometry_engine must be a GeometryRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._geometry = geometry_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str, str]:
        """Generate deterministic point, shape, and region IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        point_id = stable_identifier("pt-geort", {"tenant": tenant_id, "source": source_type, "seq": seq})
        shape_id = stable_identifier("sh-geort", {"tenant": tenant_id, "source": source_type, "seq": seq})
        region_id = stable_identifier("rg-geort", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return point_id, shape_id, region_id

    def _geometry_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register a point, shape, and region for a given source."""
        point_id, shape_id, region_id = self._next_ids(tenant_id, source_type)

        point = self._geometry.register_point(
            point_id=point_id,
            tenant_id=tenant_id,
            label=label or f"{source_type}_{ref}",
            x=x,
            y=y,
        )
        shape = self._geometry.register_shape(
            shape_id=shape_id,
            tenant_id=tenant_id,
            kind=GeometryKind.BOX,
            label=label or f"{source_type}_{ref}",
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
        )
        region = self._geometry.register_region(
            region_id=region_id,
            tenant_id=tenant_id,
            display_name=label or f"{source_type}_{ref}",
            disposition=disposition,
        )

        _emit(self._events, f"geometry_from_{source_type}", {
            "tenant_id": tenant_id,
            "point_id": point_id,
            "shape_id": shape_id,
            "region_id": region_id,
            "ref": ref,
        }, point_id)

        return {
            "point_id": point_id,
            "shape_id": shape_id,
            "region_id": region_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "disposition": disposition.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific geometry methods
    # ------------------------------------------------------------------

    def geometry_from_asset_layout(
        self,
        tenant_id: str,
        asset_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from an asset layout."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=asset_ref,
            source_type="asset_layout",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    def geometry_from_factory_line(
        self,
        tenant_id: str,
        line_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from a factory line."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=line_ref,
            source_type="factory_line",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    def geometry_from_service_territory(
        self,
        tenant_id: str,
        territory_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from a service territory."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=territory_ref,
            source_type="service_territory",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    def geometry_from_facility_map(
        self,
        tenant_id: str,
        facility_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from a facility map."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=facility_ref,
            source_type="facility_map",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    def geometry_from_inventory_zone(
        self,
        tenant_id: str,
        zone_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from an inventory zone."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=zone_ref,
            source_type="inventory_zone",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    def geometry_from_continuity_site(
        self,
        tenant_id: str,
        site_ref: str,
        label: str = "",
        x: float = 0.0,
        y: float = 0.0,
        x_min: float = 0.0,
        y_min: float = 0.0,
        x_max: float = 10.0,
        y_max: float = 10.0,
        disposition: RegionDisposition = RegionDisposition.VALID,
    ) -> dict[str, Any]:
        """Register geometry from a continuity site."""
        return self._geometry_for_source(
            tenant_id=tenant_id,
            ref=site_ref,
            source_type="continuity_site",
            label=label,
            x=x, y=y,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            disposition=disposition,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_geometry_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist geometry state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-geort", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_points": self._geometry.point_count,
            "total_shapes": self._geometry.shape_count,
            "total_regions": self._geometry.region_count,
            "total_paths": self._geometry.path_count,
            "total_constraints": self._geometry.constraint_count,
            "total_decisions": self._geometry.decision_count,
            "total_violations": self._geometry.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Geometry state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("geometry", "spatial", "placement"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "geometry_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_geometry_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return geometry state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_points": self._geometry.point_count,
            "total_shapes": self._geometry.shape_count,
            "total_regions": self._geometry.region_count,
            "total_paths": self._geometry.path_count,
            "total_constraints": self._geometry.constraint_count,
            "total_decisions": self._geometry.decision_count,
            "total_violations": self._geometry.violation_count,
        }
