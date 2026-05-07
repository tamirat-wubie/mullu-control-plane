"""Focused bounded-contract tests for MathRuntimeEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.math_runtime import (
    ObjectiveDirection,
    UncertaintyKind,
    UnitDimension,
)
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.math_runtime import MathRuntimeEngine


@pytest.fixture()
def engine():
    return MathRuntimeEngine(
        EventSpineEngine(),
        clock=FixedClock("2026-01-01T00:00:00+00:00"),
    )


def _register_quantity(engine, quantity_id="q-1", unit_label="kg", dimension=UnitDimension.MASS):
    return engine.register_quantity(quantity_id, "t-1", 1.0, unit_label, dimension)


class TestBoundedInvariantContracts:
    def test_duplicate_and_unknown_quantity_messages_are_bounded(self, engine):
        _register_quantity(engine, quantity_id="qty-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate quantity_id") as duplicate_exc:
            _register_quantity(engine, quantity_id="qty-secret")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown quantity_id") as unknown_exc:
            engine.get_quantity("qty-missing")
        assert str(duplicate_exc.value) == "Duplicate quantity_id"
        assert "qty-secret" not in str(duplicate_exc.value)
        assert str(unknown_exc.value) == "Unknown quantity_id"
        assert "qty-missing" not in str(unknown_exc.value)

    def test_conversion_messages_are_bounded(self, engine):
        _register_quantity(engine, quantity_id="qty-secret", unit_label="kg", dimension=UnitDimension.MASS)
        engine.register_conversion("conv-secret", "t-1", "kg", "lb", 2.2, UnitDimension.TIME)
        with pytest.raises(RuntimeCoreInvariantError, match="Dimension mismatch") as mismatch_exc:
            engine.convert_quantity("qty-secret", "lb")
        with pytest.raises(RuntimeCoreInvariantError, match="No conversion available") as missing_exc:
            engine.convert_quantity("qty-secret", "oz")
        assert "qty-secret" not in str(mismatch_exc.value)
        assert UnitDimension.MASS.value not in str(mismatch_exc.value)
        assert "kg" not in str(missing_exc.value)
        assert "oz" not in str(missing_exc.value)


class TestBoundedViolationReasons:
    def test_detect_math_violations_reasons_are_bounded(self, engine):
        _register_quantity(engine, quantity_id="qty-secret")
        engine.register_objective("obj-secret", "t-1", "Cost", ObjectiveDirection.MINIMIZE)
        engine.add_constraint("constraint-secret", "t-1", "obj-secret", "x >= 0", 10.0, 5.0)
        engine.submit_solver_request("request-secret", "t-1", "obj-secret")
        engine.record_uncertainty("interval-secret", "t-1", "qty-secret", UncertaintyKind.INTERVAL, 3.0, 1.0)
        violations = {v.operation: v.reason for v in engine.detect_math_violations("t-1")}
        assert violations["dimension_mismatch_in_constraint"] == "Constraint bounds are inverted"
        assert violations["infeasible_no_result"] == "Solver request has no result"
        assert violations["uncertainty_inverted"] == "Uncertainty interval bounds are inverted"
