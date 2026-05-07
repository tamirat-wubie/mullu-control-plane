"""Purpose: geospatial / spatial runtime engine.
Governance scope: registering features, territories, routes, depots, sites;
    computing distances (haversine); finding nearest features; resolving
    territories; detecting geo-violations; producing immutable snapshots.
Dependencies: geospatial_runtime contracts, event_spine, core invariants.
Invariants:
  - Every mutation emits an event.
  - All returns are immutable.
  - Violation detection is idempotent.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Optional

from ..contracts.geospatial_runtime import (
    DepotRecord,
    DistanceUnit,
    GeoAssessment,
    GeoClosureReport,
    GeoDecision,
    GeoFeature,
    GeoFeatureKind,
    GeoRiskLevel,
    GeoSnapshot,
    GeoStatus,
    GeoViolation,
    RouteRecord,
    RouteStatus,
    SiteRecord,
    TerritoryDisposition,
    TerritoryRecord,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-geo", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_EARTH_RADIUS_METERS = 6_371_000.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in meters between two lat/lon pairs."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c


class GeospatialRuntimeEngine:
    """Geospatial / spatial runtime engine."""

    def __init__(
        self,
        event_spine: EventSpineEngine,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _now_iso
        self._features: dict[str, GeoFeature] = {}
        self._territories: dict[str, TerritoryRecord] = {}
        self._routes: dict[str, RouteRecord] = {}
        self._depots: dict[str, DepotRecord] = {}
        self._sites: dict[str, SiteRecord] = {}
        self._decisions: dict[str, GeoDecision] = {}
        self._violations: dict[str, dict[str, Any]] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def feature_count(self) -> int:
        return len(self._features)

    @property
    def territory_count(self) -> int:
        return len(self._territories)

    @property
    def route_count(self) -> int:
        return len(self._routes)

    @property
    def depot_count(self) -> int:
        return len(self._depots)

    @property
    def site_count(self) -> int:
        return len(self._sites)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Features
    # ------------------------------------------------------------------

    def register_feature(
        self,
        feature_id: str,
        tenant_id: str,
        kind: GeoFeatureKind,
        display_name: str,
        latitude: float,
        longitude: float,
    ) -> GeoFeature:
        """Register a geospatial feature."""
        if feature_id in self._features:
            raise RuntimeCoreInvariantError("Duplicate feature_id")
        now = self._clock()
        feat = GeoFeature(
            feature_id=feature_id,
            tenant_id=tenant_id,
            kind=kind,
            display_name=display_name,
            latitude=latitude,
            longitude=longitude,
            status=GeoStatus.ACTIVE,
            created_at=now,
        )
        self._features[feature_id] = feat
        _emit(self._events, "feature_registered", {
            "feature_id": feature_id, "tenant_id": tenant_id,
        }, feature_id)
        return feat

    # ------------------------------------------------------------------
    # Territories
    # ------------------------------------------------------------------

    def register_territory(
        self,
        territory_id: str,
        tenant_id: str,
        display_name: str,
    ) -> TerritoryRecord:
        """Register a territory (initially UNASSIGNED)."""
        if territory_id in self._territories:
            raise RuntimeCoreInvariantError("Duplicate territory_id")
        now = self._clock()
        terr = TerritoryRecord(
            territory_id=territory_id,
            tenant_id=tenant_id,
            display_name=display_name,
            disposition=TerritoryDisposition.UNASSIGNED,
            assigned_ref="",
            feature_count=0,
            created_at=now,
        )
        self._territories[territory_id] = terr
        _emit(self._events, "territory_registered", {
            "territory_id": territory_id, "tenant_id": tenant_id,
        }, territory_id)
        return terr

    def assign_territory(
        self,
        territory_id: str,
        assigned_ref: str,
    ) -> TerritoryRecord:
        """Assign a territory to a reference."""
        old = self._territories.get(territory_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown territory_id")
        updated = TerritoryRecord(
            territory_id=old.territory_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            disposition=TerritoryDisposition.ASSIGNED,
            assigned_ref=assigned_ref,
            feature_count=old.feature_count,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._territories[territory_id] = updated
        _emit(self._events, "territory_assigned", {
            "territory_id": territory_id, "assigned_ref": assigned_ref,
        }, territory_id)
        return updated

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def register_route(
        self,
        route_id: str,
        tenant_id: str,
        display_name: str,
        origin_ref: str,
        destination_ref: str,
        distance: float,
        unit: DistanceUnit = DistanceUnit.METERS,
    ) -> RouteRecord:
        """Register a route between two references."""
        if route_id in self._routes:
            raise RuntimeCoreInvariantError("Duplicate route_id")
        now = self._clock()
        route = RouteRecord(
            route_id=route_id,
            tenant_id=tenant_id,
            display_name=display_name,
            origin_ref=origin_ref,
            destination_ref=destination_ref,
            distance=distance,
            unit=unit,
            status=RouteStatus.OPEN,
            created_at=now,
        )
        self._routes[route_id] = route
        _emit(self._events, "route_registered", {
            "route_id": route_id, "tenant_id": tenant_id,
        }, route_id)
        return route

    def _transition_route(self, route_id: str, new_status: RouteStatus) -> RouteRecord:
        old = self._routes.get(route_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown route_id")
        updated = RouteRecord(
            route_id=old.route_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            origin_ref=old.origin_ref,
            destination_ref=old.destination_ref,
            distance=old.distance,
            unit=old.unit,
            status=new_status,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._routes[route_id] = updated
        _emit(self._events, f"route_{new_status.value}", {
            "route_id": route_id,
        }, route_id)
        return updated

    def block_route(self, route_id: str) -> RouteRecord:
        """Block a route."""
        return self._transition_route(route_id, RouteStatus.BLOCKED)

    def degrade_route(self, route_id: str) -> RouteRecord:
        """Degrade a route."""
        return self._transition_route(route_id, RouteStatus.DEGRADED)

    # ------------------------------------------------------------------
    # Depots
    # ------------------------------------------------------------------

    def register_depot(
        self,
        depot_id: str,
        tenant_id: str,
        display_name: str,
        feature_ref: str,
        capacity: int,
    ) -> DepotRecord:
        """Register a depot linked to a feature."""
        if depot_id in self._depots:
            raise RuntimeCoreInvariantError("Duplicate depot_id")
        if feature_ref not in self._features:
            raise RuntimeCoreInvariantError("Unknown feature_ref")
        now = self._clock()
        depot = DepotRecord(
            depot_id=depot_id,
            tenant_id=tenant_id,
            display_name=display_name,
            feature_ref=feature_ref,
            capacity=capacity,
            current_load=0,
            created_at=now,
        )
        self._depots[depot_id] = depot
        _emit(self._events, "depot_registered", {
            "depot_id": depot_id, "tenant_id": tenant_id,
        }, depot_id)
        return depot

    def update_depot_load(self, depot_id: str, current_load: int) -> DepotRecord:
        """Update the current load of a depot."""
        old = self._depots.get(depot_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown depot_id")
        updated = DepotRecord(
            depot_id=old.depot_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            feature_ref=old.feature_ref,
            capacity=old.capacity,
            current_load=current_load,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._depots[depot_id] = updated
        _emit(self._events, "depot_load_updated", {
            "depot_id": depot_id, "current_load": current_load,
        }, depot_id)
        return updated

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def register_site(
        self,
        site_id: str,
        tenant_id: str,
        display_name: str,
        feature_ref: str,
        territory_ref: str,
    ) -> SiteRecord:
        """Register a site linked to a feature and territory."""
        if site_id in self._sites:
            raise RuntimeCoreInvariantError("Duplicate site_id")
        if feature_ref not in self._features:
            raise RuntimeCoreInvariantError("Unknown feature_ref")
        if territory_ref not in self._territories:
            raise RuntimeCoreInvariantError("Unknown territory_ref")
        now = self._clock()
        # Increment territory feature count
        terr = self._territories[territory_ref]
        updated_terr = TerritoryRecord(
            territory_id=terr.territory_id,
            tenant_id=terr.tenant_id,
            display_name=terr.display_name,
            disposition=terr.disposition,
            assigned_ref=terr.assigned_ref,
            feature_count=terr.feature_count + 1,
            created_at=terr.created_at,
            metadata=terr.metadata,
        )
        self._territories[territory_ref] = updated_terr
        site = SiteRecord(
            site_id=site_id,
            tenant_id=tenant_id,
            display_name=display_name,
            feature_ref=feature_ref,
            territory_ref=territory_ref,
            created_at=now,
        )
        self._sites[site_id] = site
        _emit(self._events, "site_registered", {
            "site_id": site_id, "tenant_id": tenant_id,
        }, site_id)
        return site

    # ------------------------------------------------------------------
    # Distance computation
    # ------------------------------------------------------------------

    def compute_distance(self, feature_a_id: str, feature_b_id: str) -> float:
        """Compute haversine distance (meters) between two features."""
        a = self._features.get(feature_a_id)
        if a is None:
            raise RuntimeCoreInvariantError("Unknown feature_id")
        b = self._features.get(feature_b_id)
        if b is None:
            raise RuntimeCoreInvariantError("Unknown feature_id")
        return _haversine(a.latitude, a.longitude, b.latitude, b.longitude)

    def find_nearest_feature(self, latitude: float, longitude: float) -> GeoFeature | None:
        """Return the closest feature to the given lat/lon, or None if empty."""
        if not self._features:
            return None
        best: GeoFeature | None = None
        best_dist = float("inf")
        for feat in self._features.values():
            d = _haversine(latitude, longitude, feat.latitude, feat.longitude)
            if d < best_dist:
                best_dist = d
                best = feat
        return best

    def resolve_territory(self, feature_id: str) -> TerritoryRecord | None:
        """Return the territory that contains a site referencing the given feature."""
        for site in self._sites.values():
            if site.feature_ref == feature_id:
                return self._territories.get(site.territory_ref)
        return None

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def geo_assessment(self, assessment_id: str, tenant_id: str) -> GeoAssessment:
        """Produce a tenant-scoped geospatial assessment."""
        now = self._clock()
        t_feat = sum(1 for f in self._features.values() if f.tenant_id == tenant_id)
        t_terr = sum(1 for t in self._territories.values() if t.tenant_id == tenant_id)
        t_routes = sum(1 for r in self._routes.values() if r.tenant_id == tenant_id)
        assigned = sum(
            1 for t in self._territories.values()
            if t.tenant_id == tenant_id and t.disposition == TerritoryDisposition.ASSIGNED
        )
        rate = assigned / t_terr if t_terr else 0.0
        assessment = GeoAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_features=t_feat,
            total_territories=t_terr,
            total_routes=t_routes,
            coverage_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "geo_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def geo_snapshot(self, snapshot_id: str, tenant_id: str) -> GeoSnapshot:
        """Capture a tenant-scoped point-in-time geospatial snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._clock()
        snap = GeoSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_features=self.feature_count,
            total_territories=self.territory_count,
            total_routes=self.route_count,
            total_depots=self.depot_count,
            total_sites=self.site_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "geo_snapshot_captured", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def geo_closure_report(self, report_id: str, tenant_id: str) -> GeoClosureReport:
        """Produce a tenant-scoped geospatial closure report."""
        now = self._clock()
        report = GeoClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_features=sum(1 for f in self._features.values() if f.tenant_id == tenant_id),
            total_territories=sum(1 for t in self._territories.values() if t.tenant_id == tenant_id),
            total_routes=sum(1 for r in self._routes.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )
        _emit(self._events, "geo_closure_report", {"report_id": report_id}, report_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_geo_violations(self) -> tuple[dict[str, Any], ...]:
        """Detect geospatial violations (idempotent).

        Rules:
        - overloaded_depot: depot where current_load > capacity
        - blocked_route_in_use: route is BLOCKED but referenced by a site
        - unassigned_territory: territory still UNASSIGNED
        """
        now = self._clock()
        new_violations: list[dict[str, Any]] = []

        # Rule: overloaded depot
        for depot in self._depots.values():
            if depot.current_load > depot.capacity:
                vid = stable_identifier("viol-geo", {
                    "depot": depot.depot_id, "op": "overloaded_depot",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": depot.tenant_id,
                        "operation": "overloaded_depot",
                        "reason": "depot load exceeds capacity",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Rule: blocked route in use (referenced by origin/dest of any other route or site feature)
        blocked_features: set[str] = set()
        for route in self._routes.values():
            if route.status == RouteStatus.BLOCKED:
                blocked_features.add(route.origin_ref)
                blocked_features.add(route.destination_ref)
        # Check if any site references a feature that is origin/dest of a blocked route
        for route in self._routes.values():
            if route.status == RouteStatus.BLOCKED:
                vid = stable_identifier("viol-geo", {
                    "route": route.route_id, "op": "blocked_route_in_use",
                })
                # Only flag if there are sites referencing origin or dest features
                has_sites = any(
                    s.feature_ref in (route.origin_ref, route.destination_ref)
                    for s in self._sites.values()
                )
                if has_sites and vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": route.tenant_id,
                        "operation": "blocked_route_in_use",
                        "reason": "blocked route endpoints remain in use",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Rule: unassigned territory
        for terr in self._territories.values():
            if terr.disposition == TerritoryDisposition.UNASSIGNED:
                vid = stable_identifier("viol-geo", {
                    "territory": terr.territory_id, "op": "unassigned_territory",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": terr.tenant_id,
                        "operation": "unassigned_territory",
                        "reason": "territory is unassigned",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "geo_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "features": self._features,
            "territories": self._territories,
            "routes": self._routes,
            "depots": self._depots,
            "sites": self._sites,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v for v in collection
                ]
            else:
                result[name] = collection
        return result

    def state_hash(self) -> str:
        """Compute a SHA-256 hash of the current engine state."""
        parts = sorted([
            f"decisions={self.decision_count}",
            f"depots={self.depot_count}",
            f"features={self.feature_count}",
            f"routes={self.route_count}",
            f"sites={self.site_count}",
            f"territories={self.territory_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
