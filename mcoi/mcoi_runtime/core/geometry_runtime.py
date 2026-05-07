"""Purpose: geometry / spatial runtime engine.
Governance scope: managing geometry points, shapes, spatial regions, paths,
    constraints, decisions, violations, assessments, snapshots, and closure
    reports.
Dependencies: geometry_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
  - Violation detection is idempotent.
"""

from __future__ import annotations

import math
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.geometry_runtime import (
    GeometryKind,
    GeometryPoint,
    GeometryShape,
    RegionDisposition,
    RoutingDisposition,
    SpatialAssessment,
    SpatialClosureReport,
    SpatialConstraint,
    SpatialDecision,
    SpatialRegion,
    SpatialRelation,
    SpatialPath,
    SpatialSnapshot,
    SpatialViolation,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-geort", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class GeometryRuntimeEngine:
    """Engine for governed geometry / spatial runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._points: dict[str, GeometryPoint] = {}
        self._shapes: dict[str, GeometryShape] = {}
        self._regions: dict[str, SpatialRegion] = {}
        self._paths: dict[str, SpatialPath] = {}
        self._constraints: dict[str, SpatialConstraint] = {}
        self._decisions: dict[str, SpatialDecision] = {}
        self._violations: dict[str, SpatialViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def point_count(self) -> int:
        return len(self._points)

    @property
    def shape_count(self) -> int:
        return len(self._shapes)

    @property
    def region_count(self) -> int:
        return len(self._regions)

    @property
    def path_count(self) -> int:
        return len(self._paths)

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Points
    # ------------------------------------------------------------------

    def register_point(
        self,
        point_id: str,
        tenant_id: str,
        label: str,
        x: float,
        y: float,
        z: float = 0.0,
    ) -> GeometryPoint:
        """Register a new geometry point. Duplicate point_id raises."""
        if point_id in self._points:
            raise RuntimeCoreInvariantError("Duplicate point_id")
        now = self._now()
        point = GeometryPoint(
            point_id=point_id,
            tenant_id=tenant_id,
            label=label,
            x=x,
            y=y,
            z=z,
            created_at=now,
        )
        self._points[point_id] = point
        _emit(self._events, "point_registered", {
            "point_id": point_id, "label": label,
        }, point_id, self._now())
        return point

    def get_point(self, point_id: str) -> GeometryPoint:
        p = self._points.get(point_id)
        if p is None:
            raise RuntimeCoreInvariantError("Unknown point_id")
        return p

    def points_for_tenant(self, tenant_id: str) -> tuple[GeometryPoint, ...]:
        return tuple(p for p in self._points.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Shapes
    # ------------------------------------------------------------------

    def register_shape(
        self,
        shape_id: str,
        tenant_id: str,
        kind: GeometryKind,
        label: str,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
    ) -> GeometryShape:
        """Register a new shape. Auto-computes area for BOX/POLYGON."""
        if shape_id in self._shapes:
            raise RuntimeCoreInvariantError("Duplicate shape_id")
        if kind in (GeometryKind.BOX, GeometryKind.POLYGON):
            area = abs((x_max - x_min) * (y_max - y_min))
        else:
            area = 0.0
        now = self._now()
        shape = GeometryShape(
            shape_id=shape_id,
            tenant_id=tenant_id,
            kind=kind,
            label=label,
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
            area=area,
            created_at=now,
        )
        self._shapes[shape_id] = shape
        _emit(self._events, "shape_registered", {
            "shape_id": shape_id, "kind": kind.value,
        }, shape_id, self._now())
        return shape

    def get_shape(self, shape_id: str) -> GeometryShape:
        s = self._shapes.get(shape_id)
        if s is None:
            raise RuntimeCoreInvariantError("Unknown shape_id")
        return s

    def shapes_for_tenant(self, tenant_id: str) -> tuple[GeometryShape, ...]:
        return tuple(s for s in self._shapes.values() if s.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Regions
    # ------------------------------------------------------------------

    def register_region(
        self,
        region_id: str,
        tenant_id: str,
        display_name: str,
        disposition: RegionDisposition = RegionDisposition.VALID,
        parent_ref: str = "root",
    ) -> SpatialRegion:
        """Register a new spatial region."""
        if region_id in self._regions:
            raise RuntimeCoreInvariantError("Duplicate region_id")
        now = self._now()
        region = SpatialRegion(
            region_id=region_id,
            tenant_id=tenant_id,
            display_name=display_name,
            disposition=disposition,
            parent_ref=parent_ref,
            created_at=now,
        )
        self._regions[region_id] = region
        _emit(self._events, "region_registered", {
            "region_id": region_id, "disposition": disposition.value,
        }, region_id, self._now())
        return region

    def get_region(self, region_id: str) -> SpatialRegion:
        r = self._regions.get(region_id)
        if r is None:
            raise RuntimeCoreInvariantError("Unknown region_id")
        return r

    def regions_for_tenant(self, tenant_id: str) -> tuple[SpatialRegion, ...]:
        return tuple(r for r in self._regions.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def register_path(
        self,
        path_id: str,
        tenant_id: str,
        display_name: str,
        node_count: int,
        total_distance: float,
        routing: RoutingDisposition = RoutingDisposition.ROUTABLE,
    ) -> SpatialPath:
        """Register a new spatial path."""
        if path_id in self._paths:
            raise RuntimeCoreInvariantError("Duplicate path_id")
        now = self._now()
        path = SpatialPath(
            path_id=path_id,
            tenant_id=tenant_id,
            display_name=display_name,
            node_count=node_count,
            total_distance=total_distance,
            routing=routing,
            created_at=now,
        )
        self._paths[path_id] = path
        _emit(self._events, "path_registered", {
            "path_id": path_id, "routing": routing.value,
        }, path_id, self._now())
        return path

    def get_path(self, path_id: str) -> SpatialPath:
        p = self._paths.get(path_id)
        if p is None:
            raise RuntimeCoreInvariantError("Unknown path_id")
        return p

    def paths_for_tenant(self, tenant_id: str) -> tuple[SpatialPath, ...]:
        return tuple(p for p in self._paths.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def register_constraint(
        self,
        constraint_id: str,
        tenant_id: str,
        kind: str,
        target_a_ref: str,
        target_b_ref: str,
        threshold: float = 0.0,
    ) -> SpatialConstraint:
        """Register a new spatial constraint."""
        if constraint_id in self._constraints:
            raise RuntimeCoreInvariantError("Duplicate constraint_id")
        now = self._now()
        constraint = SpatialConstraint(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            kind=kind,
            target_a_ref=target_a_ref,
            target_b_ref=target_b_ref,
            threshold=threshold,
            created_at=now,
        )
        self._constraints[constraint_id] = constraint
        _emit(self._events, "constraint_registered", {
            "constraint_id": constraint_id, "kind": kind,
        }, constraint_id, self._now())
        return constraint

    # ------------------------------------------------------------------
    # Spatial computations
    # ------------------------------------------------------------------

    def compute_distance(self, point_a_id: str, point_b_id: str) -> float:
        """Compute Euclidean distance between two points."""
        a = self.get_point(point_a_id)
        b = self.get_point(point_b_id)
        return math.sqrt(
            (b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2
        )

    def compute_relation(self, shape_a_id: str, shape_b_id: str) -> SpatialRelation:
        """Compute spatial relation between two shapes using bounding boxes."""
        a = self.get_shape(shape_a_id)
        b = self.get_shape(shape_b_id)

        # Check if A contains B
        a_contains_b = (
            a.x_min <= b.x_min and a.y_min <= b.y_min
            and a.x_max >= b.x_max and a.y_max >= b.y_max
        )
        # Check if B contains A
        b_contains_a = (
            b.x_min <= a.x_min and b.y_min <= a.y_min
            and b.x_max >= a.x_max and b.y_max >= a.y_max
        )

        if a_contains_b and not b_contains_a:
            return SpatialRelation.CONTAINS
        if b_contains_a and not a_contains_b:
            return SpatialRelation.INSIDE

        # Check disjoint
        if (a.x_max < b.x_min or b.x_max < a.x_min
                or a.y_max < b.y_min or b.y_max < a.y_min):
            return SpatialRelation.DISJOINT

        # Check adjacent (edges touch but no interior overlap)
        if (a.x_max == b.x_min or b.x_max == a.x_min
                or a.y_max == b.y_min or b.y_max == a.y_min):
            return SpatialRelation.ADJACENT

        # Boxes overlap
        return SpatialRelation.OVERLAPS

    def check_containment(self, point_id: str, shape_id: str) -> bool:
        """Check if a point is inside a shape's bounding box."""
        pt = self.get_point(point_id)
        sh = self.get_shape(shape_id)
        return (
            sh.x_min <= pt.x <= sh.x_max
            and sh.y_min <= pt.y <= sh.y_max
        )

    def check_overlap(self, shape_a_id: str, shape_b_id: str) -> bool:
        """Check if two shapes' bounding boxes overlap."""
        a = self.get_shape(shape_a_id)
        b = self.get_shape(shape_b_id)
        if (a.x_max < b.x_min or b.x_max < a.x_min
                or a.y_max < b.y_min or b.y_max < a.y_min):
            return False
        return True

    # ------------------------------------------------------------------
    # Constraint evaluation
    # ------------------------------------------------------------------

    def evaluate_constraints(self, tenant_id: str) -> tuple[SpatialDecision, ...]:
        """Evaluate all constraints for a tenant, producing decisions."""
        now = self._now()
        decisions: list[SpatialDecision] = []
        tenant_constraints = [
            c for c in self._constraints.values() if c.tenant_id == tenant_id
        ]
        for constraint in tenant_constraints:
            did = stable_identifier("dec-geort", {
                "constraint": constraint.constraint_id, "tenant": tenant_id,
            })
            if did in self._decisions:
                decisions.append(self._decisions[did])
                continue

            passed = True
            reason = "constraint satisfied"

            if constraint.kind == "no_overlap":
                # Both targets must be shapes
                sa = self._shapes.get(constraint.target_a_ref)
                sb = self._shapes.get(constraint.target_b_ref)
                if sa is not None and sb is not None:
                    if self.check_overlap(constraint.target_a_ref, constraint.target_b_ref):
                        passed = False
                        reason = "shapes overlap"
                else:
                    reason = "one or both shape targets not found"

            elif constraint.kind == "must_contain":
                # target_a is shape, target_b is point
                sh = self._shapes.get(constraint.target_a_ref)
                pt = self._points.get(constraint.target_b_ref)
                if sh is not None and pt is not None:
                    if not self.check_containment(constraint.target_b_ref, constraint.target_a_ref):
                        passed = False
                        reason = "point is outside shape"
                else:
                    reason = "shape or point target not found"

            elif constraint.kind == "max_distance":
                pa = self._points.get(constraint.target_a_ref)
                pb = self._points.get(constraint.target_b_ref)
                if pa is not None and pb is not None:
                    dist = self.compute_distance(constraint.target_a_ref, constraint.target_b_ref)
                    if dist > constraint.threshold:
                        passed = False
                        reason = "distance exceeds threshold"
                else:
                    reason = "one or both point targets not found"

            dec = SpatialDecision(
                decision_id=did,
                tenant_id=tenant_id,
                constraint_ref=constraint.constraint_id,
                passed=passed,
                reason=reason,
                decided_at=now,
            )
            self._decisions[did] = dec
            decisions.append(dec)
            _emit(self._events, "constraint_evaluated", {
                "decision_id": did, "passed": passed,
            }, did, self._now())

        return tuple(decisions)

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def spatial_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> SpatialAssessment:
        """Produce a spatial assessment for a tenant."""
        now = self._now()
        t_regions = sum(1 for r in self._regions.values() if r.tenant_id == tenant_id)
        t_shapes = sum(1 for s in self._shapes.values() if s.tenant_id == tenant_id)
        t_violations = sum(1 for v in self._violations.values() if v.tenant_id == tenant_id)

        total = t_regions + t_shapes
        rate = (total - t_violations) / total if total > 0 else 1.0
        rate = max(0.0, min(1.0, rate))

        asm = SpatialAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_regions=t_regions,
            total_shapes=t_shapes,
            total_violations=t_violations,
            compliance_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "spatial_assessed", {
            "assessment_id": assessment_id, "compliance_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def spatial_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> SpatialSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        return SpatialSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_points=sum(1 for p in self._points.values() if p.tenant_id == tenant_id),
            total_shapes=sum(1 for s in self._shapes.values() if s.tenant_id == tenant_id),
            total_regions=sum(1 for r in self._regions.values() if r.tenant_id == tenant_id),
            total_paths=sum(1 for p in self._paths.values() if p.tenant_id == tenant_id),
            total_constraints=sum(1 for c in self._constraints.values() if c.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def spatial_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> SpatialClosureReport:
        """Produce a final closure report for a tenant."""
        now = self._now()
        return SpatialClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_points=sum(1 for p in self._points.values() if p.tenant_id == tenant_id),
            total_shapes=sum(1 for s in self._shapes.values() if s.tenant_id == tenant_id),
            total_regions=sum(1 for r in self._regions.values() if r.tenant_id == tenant_id),
            total_paths=sum(1 for p in self._paths.values() if p.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_spatial_violations(self, tenant_id: str) -> tuple[SpatialViolation, ...]:
        """Detect spatial violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[SpatialViolation] = []

        tenant_shapes = [s for s in self._shapes.values() if s.tenant_id == tenant_id]
        tenant_points = [p for p in self._points.values() if p.tenant_id == tenant_id]
        tenant_paths = [p for p in self._paths.values() if p.tenant_id == tenant_id]
        tenant_regions = [r for r in self._regions.values() if r.tenant_id == tenant_id]

        # 1) overlap_detected: any two shapes overlap
        for i, sa in enumerate(tenant_shapes):
            for sb in tenant_shapes[i + 1:]:
                if self.check_overlap(sa.shape_id, sb.shape_id):
                    vid = stable_identifier("viol-geort", {
                        "a": sa.shape_id, "b": sb.shape_id, "op": "overlap_detected",
                    })
                    if vid not in self._violations:
                        v = SpatialViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="overlap_detected",
                            reason="shapes overlap",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2) containment_breach: point outside all regions' shapes
        for pt in tenant_points:
            contained = False
            for sh in tenant_shapes:
                if self.check_containment(pt.point_id, sh.shape_id):
                    contained = True
                    break
            if not contained and tenant_shapes:
                vid = stable_identifier("viol-geort", {
                    "point": pt.point_id, "op": "containment_breach",
                })
                if vid not in self._violations:
                    v = SpatialViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="containment_breach",
                        reason="point is not contained in any shape",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) route_blocked: any path with BLOCKED routing
        for path in tenant_paths:
            if path.routing == RoutingDisposition.BLOCKED:
                vid = stable_identifier("viol-geort", {
                    "path": path.path_id, "op": "route_blocked",
                })
                if vid not in self._violations:
                    v = SpatialViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="route_blocked",
                        reason="path routing is blocked",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "constraints": self._constraints,
            "decisions": self._decisions,
            "paths": self._paths,
            "points": self._points,
            "regions": self._regions,
            "shapes": self._shapes,
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
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys, full 64-char)."""
        parts = [
            f"constraints={self.constraint_count}",
            f"decisions={self.decision_count}",
            f"paths={self.path_count}",
            f"points={self.point_count}",
            f"regions={self.region_count}",
            f"shapes={self.shape_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
