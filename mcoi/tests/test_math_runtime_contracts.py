"""Tests for math / optimization / units runtime contracts.

Validates finite-float enforcement on quantity values, conversion factors,
objective target values, trace objective values, and uncertainty bounds,
while confirming that MathOptimizationConstraint bounds still allow inf.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from mcoi_runtime.contracts.math_runtime import (
    MathOptimizationConstraint,
    MathSolverReceipt,
    ObjectiveDirection,
    OptimizationObjective,
    OptimizationStatus,
    OptimizationTrace,
    QuantityRecord,
    SolverDisposition,
    SolverResult,
    UncertaintyInterval,
    UncertaintyKind,
    UnitConversion,
    UnitDimension,
)


TS = "2025-06-01T12:00:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quantity(**overrides) -> QuantityRecord:
    defaults = dict(
        quantity_id="q-1", tenant_id="t-1", value=1.0,
        unit_label="kg", dimension=UnitDimension.MASS, created_at=TS,
    )
    defaults.update(overrides)
    return QuantityRecord(**defaults)


def _conversion(**overrides) -> UnitConversion:
    defaults = dict(
        conversion_id="conv-1", tenant_id="t-1",
        from_unit="kg", to_unit="lb", factor=2.20462,
        dimension=UnitDimension.MASS, created_at=TS,
    )
    defaults.update(overrides)
    return UnitConversion(**defaults)


def _objective(**overrides) -> OptimizationObjective:
    defaults = dict(
        objective_id="obj-1", tenant_id="t-1", display_name="Cost",
        direction=ObjectiveDirection.MINIMIZE, target_value=100.0,
        created_at=TS,
    )
    defaults.update(overrides)
    return OptimizationObjective(**defaults)


def _constraint(**overrides) -> MathOptimizationConstraint:
    defaults = dict(
        constraint_id="cst-1", tenant_id="t-1",
        objective_ref="obj-1", expression="x >= 0",
        lower_bound=0.0, upper_bound=100.0, created_at=TS,
    )
    defaults.update(overrides)
    return MathOptimizationConstraint(**defaults)


def _uncertainty(**overrides) -> UncertaintyInterval:
    defaults = dict(
        interval_id="ui-1", tenant_id="t-1", quantity_ref="q-1",
        kind=UncertaintyKind.INTERVAL, lower=0.5, upper=1.5,
        confidence=0.95, created_at=TS,
    )
    defaults.update(overrides)
    return UncertaintyInterval(**defaults)


def _trace(**overrides) -> OptimizationTrace:
    defaults = dict(
        trace_id="tr-1", tenant_id="t-1", request_ref="req-1",
        step=0, objective_value=42.0, recorded_at=TS,
    )
    defaults.update(overrides)
    return OptimizationTrace(**defaults)


def _solver_result(**overrides) -> SolverResult:
    defaults = dict(
        result_id="res-1", tenant_id="t-1", request_ref="req-1",
        status=OptimizationStatus.OPTIMAL,
        disposition=SolverDisposition.SOLVED,
        objective_value=42.0, solved_at=TS,
    )
    defaults.update(overrides)
    return SolverResult(**defaults)


def _solver_receipt(**overrides) -> MathSolverReceipt:
    defaults = dict(
        receipt_id="math-solver-receipt-123456789abc",
        tenant_id="t-1",
        request_ref="req-1",
        result_id="res-1",
        trace_id="trace-1",
        solver="deterministic_interval_v1",
        status=OptimizationStatus.OPTIMAL,
        disposition=SolverDisposition.SOLVED,
        reason="bounded_optimum",
        objective_value=42.0,
        iterations=1,
        decision_summary={"decision_dimension": 1, "decision_value": 4.0},
        evidence_refs=("math-request:req-1", "math-result:res-1", "math-trace:trace-1"),
        emitted_at=TS,
        receipt_hash="a" * 64,
    )
    defaults.update(overrides)
    return MathSolverReceipt(**defaults)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestHappyPaths:
    def test_quantity_valid(self):
        q = _quantity(value=-5.0)
        assert q.value == -5.0

    def test_conversion_valid(self):
        c = _conversion(factor=2.20462)
        assert c.factor == 2.20462

    def test_objective_valid(self):
        o = _objective(target_value=0.0)
        assert o.target_value == 0.0

    def test_constraint_inf_bounds_allowed(self):
        c = _constraint(lower_bound=float("-inf"), upper_bound=float("inf"))
        assert c.lower_bound == float("-inf")
        assert c.upper_bound == float("inf")

    def test_uncertainty_valid(self):
        u = _uncertainty(lower=-1.0, upper=1.0)
        assert u.lower == -1.0

    def test_trace_valid(self):
        t = _trace(objective_value=0.0)
        assert t.objective_value == 0.0

    def test_solver_result_valid(self):
        r = _solver_result(objective_value=-10.5)
        assert r.objective_value == -10.5

    def test_math_solver_receipt_valid_and_schema_bound(self):
        receipt = _solver_receipt()
        schema = json.loads((REPO_ROOT / "schemas/math_solver_receipt.schema.json").read_text(encoding="utf-8"))

        Draft202012Validator(schema).validate(receipt.to_json_dict())

        assert receipt.receipt_id == "math-solver-receipt-123456789abc"
        assert receipt.evidence_refs == ("math-request:req-1", "math-result:res-1", "math-trace:trace-1")
        assert receipt.to_json_dict()["status"] == OptimizationStatus.OPTIMAL.value
        assert receipt.to_json_dict()["decision_summary"]["decision_value"] == 4.0
        assert len(receipt.receipt_hash) == 64


# ---------------------------------------------------------------------------
# Inf / NaN rejection
# ---------------------------------------------------------------------------


class TestInfNanRejection:
    def test_quantity_value_type_message_is_bounded(self):
        with pytest.raises(ValueError) as exc_info:
            _quantity(value=True)
        message = str(exc_info.value)
        assert message == "numeric value must be a number"
        assert "bool" not in message

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_quantity_value_rejects_non_finite(self, bad):
        with pytest.raises(ValueError) as exc_info:
            _quantity(value=bad)
        message = str(exc_info.value)
        assert message == "numeric value must be finite"
        assert repr(float(bad)) not in message

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_conversion_factor_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _conversion(factor=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_objective_target_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _objective(target_value=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_uncertainty_lower_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _uncertainty(lower=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_uncertainty_upper_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _uncertainty(upper=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_trace_objective_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _trace(objective_value=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_solver_result_objective_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _solver_result(objective_value=bad)

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_math_solver_receipt_objective_rejects_non_finite(self, bad):
        with pytest.raises(ValueError, match="numeric value must be finite"):
            _solver_receipt(objective_value=bad)

    def test_constraint_bounds_allow_inf(self):
        """MathOptimizationConstraint bounds intentionally allow inf."""
        c = _constraint(lower_bound=float("-inf"), upper_bound=float("inf"))
        assert math.isinf(c.lower_bound)
        assert math.isinf(c.upper_bound)

    @pytest.mark.parametrize("field_name", ["lower_bound", "upper_bound"])
    def test_constraint_bounds_reject_nan(self, field_name):
        with pytest.raises(ValueError) as exc_info:
            _constraint(**{field_name: float("nan")})
        message = str(exc_info.value)
        assert message == "numeric value must not be NaN"
        assert "nan" not in message
