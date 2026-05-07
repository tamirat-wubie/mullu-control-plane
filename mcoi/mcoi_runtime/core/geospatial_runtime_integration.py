"""Purpose: geospatial runtime integration bridge.
Governance scope: composing geospatial runtime with service, continuity,
    factory, asset, logistics, and workforce scopes; memory mesh and
    operational graph attachment.
Dependencies: geospatial_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every geo creation emits events.
  - Geo state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.geospatial_runtime import GeoFeatureKind
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .geospatial_runtime import GeospatialRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-gint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class GeospatialRuntimeIntegration:
    """Integration bridge for geospatial runtime with platform layers."""

    def __init__(
        self,
        geo_engine: GeospatialRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(geo_engine, GeospatialRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "geo_engine must be a GeospatialRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._geo = geo_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Bridge helpers
    # ------------------------------------------------------------------

    def _bridge(
        self,
        source_type: str,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        source_ref: str,
    ) -> dict[str, Any]:
        feat = self._geo.register_feature(
            feature_id, tenant_id, GeoFeatureKind.POINT,
            display_name, latitude, longitude,
        )
        _emit(self._events, f"geo_from_{source_type}", {
            "feature_id": feature_id, "source_ref": source_ref,
        }, feature_id)
        return {
            "feature_id": feat.feature_id,
            "tenant_id": feat.tenant_id,
            "display_name": feat.display_name,
            "latitude": feat.latitude,
            "longitude": feat.longitude,
            "status": feat.status.value,
            "source_type": source_type,
        }

    def geo_from_service_territory(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        service_ref: str = "service_territory",
    ) -> dict[str, Any]:
        """Create geo feature from a service territory source."""
        return self._bridge(
            "service_territory", feature_id, tenant_id, display_name,
            latitude, longitude, service_ref,
        )

    def geo_from_continuity_site(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        continuity_ref: str = "continuity_site",
    ) -> dict[str, Any]:
        """Create geo feature from a continuity site source."""
        return self._bridge(
            "continuity_site", feature_id, tenant_id, display_name,
            latitude, longitude, continuity_ref,
        )

    def geo_from_factory_location(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        factory_ref: str = "factory_location",
    ) -> dict[str, Any]:
        """Create geo feature from a factory location source."""
        return self._bridge(
            "factory_location", feature_id, tenant_id, display_name,
            latitude, longitude, factory_ref,
        )

    def geo_from_asset_placement(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        asset_ref: str = "asset_placement",
    ) -> dict[str, Any]:
        """Create geo feature from an asset placement source."""
        return self._bridge(
            "asset_placement", feature_id, tenant_id, display_name,
            latitude, longitude, asset_ref,
        )

    def geo_from_logistics(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        logistics_ref: str = "logistics",
    ) -> dict[str, Any]:
        """Create geo feature from a logistics source."""
        return self._bridge(
            "logistics", feature_id, tenant_id, display_name,
            latitude, longitude, logistics_ref,
        )

    def geo_from_workforce_field(
        self,
        feature_id: str,
        tenant_id: str,
        display_name: str,
        latitude: float,
        longitude: float,
        *,
        workforce_ref: str = "workforce_field",
    ) -> dict[str, Any]:
        """Create geo feature from a workforce field source."""
        return self._bridge(
            "workforce_field", feature_id, tenant_id, display_name,
            latitude, longitude, workforce_ref,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_geo_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist geospatial state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_features": self._geo.feature_count,
            "total_territories": self._geo.territory_count,
            "total_routes": self._geo.route_count,
            "total_depots": self._geo.depot_count,
            "total_sites": self._geo.site_count,
            "total_violations": self._geo.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-geo", {
                "scope": scope_ref_id,
                "seq": str(self._memory.memory_count),
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Geospatial state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("geospatial", "spatial", "territory"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "geo_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_geo_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return geospatial state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_features": self._geo.feature_count,
            "total_territories": self._geo.territory_count,
            "total_routes": self._geo.route_count,
            "total_depots": self._geo.depot_count,
            "total_sites": self._geo.site_count,
            "total_violations": self._geo.violation_count,
        }
