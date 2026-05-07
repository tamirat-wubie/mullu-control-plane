"""Focused tests for geometry runtime bounded contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.geometry_runtime import GeometryKind, RoutingDisposition
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.geometry_runtime import GeometryRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _make_engine() -> tuple[GeometryRuntimeEngine, EventSpineEngine]:
    spine = EventSpineEngine()
    engine = GeometryRuntimeEngine(spine)
    return engine, spine


class TestBoundedGeometryContracts:
    def test_duplicate_and_unknown_messages_are_bounded(self):
        engine, _ = _make_engine()
        engine.register_point("pt-secret", "t1", "P1", 0.0, 0.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate point_id") as duplicate_exc:
            engine.register_point("pt-secret", "t1", "P1", 0.0, 0.0)
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown shape_id") as unknown_exc:
            engine.get_shape("shape-secret")
        assert "pt-secret" not in str(duplicate_exc.value)
        assert "shape-secret" not in str(unknown_exc.value)
        assert engine.point_count == 1

    def test_constraint_decision_reasons_are_bounded(self):
        engine, _ = _make_engine()
        engine.register_shape("shape-a", "t1", GeometryKind.BOX, "A", 0.0, 0.0, 5.0, 5.0)
        engine.register_shape("shape-b", "t1", GeometryKind.BOX, "B", 4.0, 4.0, 6.0, 6.0)
        engine.register_point("point-secret", "t1", "P", 10.0, 10.0)
        engine.register_constraint("c-overlap", "t1", "no_overlap", "shape-a", "shape-b")
        engine.register_constraint("c-contain", "t1", "must_contain", "shape-a", "point-secret")
        decisions = engine.evaluate_constraints("t1")
        reasons = {decision.reason for decision in decisions if not decision.passed}
        assert "shapes overlap" in reasons
        assert "point is outside shape" in reasons
        assert all("secret" not in reason for reason in reasons)

    def test_distance_constraint_reason_is_bounded(self):
        engine, _ = _make_engine()
        engine.register_point("point-a", "t1", "A", 0.0, 0.0)
        engine.register_point("point-b", "t1", "B", 10.0, 0.0)
        engine.register_constraint("c-distance", "t1", "max_distance", "point-a", "point-b", threshold=1.0)
        decisions = engine.evaluate_constraints("t1")
        distance_decision = next(decision for decision in decisions if decision.constraint_ref == "c-distance")
        assert distance_decision.passed is False
        assert distance_decision.reason == "distance exceeds threshold"
        assert "10.0" not in distance_decision.reason

    def test_violation_reasons_are_bounded(self):
        engine, _ = _make_engine()
        engine.register_shape("shape-a", "t1", GeometryKind.BOX, "A", 0.0, 0.0, 5.0, 5.0)
        engine.register_shape("shape-b", "t1", GeometryKind.BOX, "B", 4.0, 4.0, 6.0, 6.0)
        engine.register_point("point-secret", "t1", "P", 10.0, 10.0)
        engine.register_path("path-secret", "t1", "Path", 2, 12.0, routing=RoutingDisposition.BLOCKED)
        reasons = {violation.reason for violation in engine.detect_spatial_violations("t1")}
        assert "shapes overlap" in reasons
        assert "point is not contained in any shape" in reasons
        assert "path routing is blocked" in reasons
        assert all("secret" not in reason for reason in reasons)
