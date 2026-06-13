"""Focused bounded-contract tests for MathRuntimeEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.math_runtime import (
    ObjectiveDirection,
    OptimizationStatus,
    SolverDisposition,
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


class TestDeterministicIntervalSolver:
    def test_minimize_solver_records_optimal_result_and_trace(self, engine):
        engine.register_objective("obj-1", "t-1", "Cost", ObjectiveDirection.MINIMIZE, weight=0.5)
        engine.add_constraint("c-1", "t-1", "obj-1", "x >= 4", 4.0, 10.0)
        engine.submit_solver_request("req-1", "t-1", "obj-1")

        result = engine.solve_solver_request("req-1")
        snapshot = engine.snapshot()

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert result.objective_value == 2.0
        assert result.metadata["decision_value"] == 4.0
        assert result.metadata["weighted_objective_value"] == 2.0
        assert engine.result_count == 1
        assert engine.trace_count == 1
        assert next(iter(snapshot["traces"].values()))["metadata"]["reason"] == "bounded_optimum"

    def test_maximize_solver_uses_upper_bound(self, engine):
        engine.register_objective("obj-2", "t-1", "Throughput", ObjectiveDirection.MAXIMIZE)
        engine.add_constraint("c-2", "t-1", "obj-2", "x <= 9", 1.0, 9.0)
        engine.submit_solver_request("req-2", "t-1", "obj-2")

        result = engine.solve_solver_request("req-2", result_id="res-2")

        assert result.result_id == "res-2"
        assert result.status is OptimizationStatus.OPTIMAL
        assert result.objective_value == 9.0
        assert result.metadata["decision_value"] == 9.0
        assert result.metadata["objective_direction"] == ObjectiveDirection.MAXIMIZE.value
        assert result.iterations == 1

    def test_solver_records_infeasible_bounds_without_pending_request_violation(self, engine):
        engine.register_objective("obj-3", "t-1", "Budget", ObjectiveDirection.MINIMIZE, target_value=7.0)
        engine.add_constraint("c-3", "t-1", "obj-3", "x impossible", 10.0, 5.0)
        engine.submit_solver_request("req-3", "t-1", "obj-3")

        result = engine.solve_solver_request("req-3")
        violations = {item.operation for item in engine.detect_math_violations("t-1")}

        assert result.status is OptimizationStatus.INFEASIBLE
        assert result.disposition is SolverDisposition.FAILED
        assert result.metadata["reason"] == "infeasible_bounds"
        assert result.metadata["decision_value"] == 7.0
        assert "infeasible_no_result" not in violations
        assert "dimension_mismatch_in_constraint" in violations

    def test_solver_classifies_unbounded_minimize(self, engine):
        engine.register_objective("obj-4", "t-1", "Latency", ObjectiveDirection.MINIMIZE, target_value=3.0)
        engine.add_constraint("c-4", "t-1", "obj-4", "x <= 12", float("-inf"), 12.0)
        engine.submit_solver_request("req-4", "t-1", "obj-4")

        result = engine.solve_solver_request("req-4")

        assert result.status is OptimizationStatus.UNBOUNDED
        assert result.disposition is SolverDisposition.FAILED
        assert result.objective_value == 3.0
        assert result.metadata["reason"] == "unbounded_minimize"
        assert result.metadata["constraint_count"] == 1

    def test_solver_rejects_duplicate_and_nan_bound_with_bounded_messages(self, engine):
        engine.register_objective("obj-5", "t-1", "Risk", ObjectiveDirection.MINIMIZE)
        engine.add_constraint("c-5", "t-1", "obj-5", "x >= 0", 0.0, 1.0)
        engine.submit_solver_request("req-5", "t-1", "obj-5")
        engine.solve_solver_request("req-5")

        with pytest.raises(RuntimeCoreInvariantError, match="Solver request already has result") as duplicate_exc:
            engine.solve_solver_request("req-5")

        engine.register_objective("obj-6", "t-1", "NaN guard", ObjectiveDirection.MINIMIZE)
        engine.add_constraint("c-6", "t-1", "obj-6", "bad bound", float("nan"), 1.0)
        engine.submit_solver_request("req-6", "t-1", "obj-6")
        with pytest.raises(RuntimeCoreInvariantError, match="Constraint bound must not be NaN") as nan_exc:
            engine.solve_solver_request("req-6")

        assert str(duplicate_exc.value) == "Solver request already has result"
        assert str(nan_exc.value) == "Constraint bound must not be NaN"
        assert "req-5" not in str(duplicate_exc.value)
        assert "c-6" not in str(nan_exc.value)


class TestDeterministicLinearSolver:
    def test_two_variable_solver_selects_bounded_linear_optimum(self, engine):
        engine.register_objective(
            "obj-linear-1",
            "t-1",
            "Cost mix",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_coefficients": {"x": 3.0, "y": 1.0},
                "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]},
            },
        )
        engine.add_constraint(
            "c-linear-1",
            "t-1",
            "obj-linear-1",
            "x + y >= 5",
            5.0,
            float("inf"),
            metadata={"linear_terms": {"x": 1.0, "y": 1.0}},
        )
        engine.submit_solver_request("req-linear-1", "t-1", "obj-linear-1")

        result = engine.solve_solver_request("req-linear-1")
        decision_values = result.metadata["decision_values"]

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert result.metadata["solver"] == "deterministic_linear_v1"
        assert result.metadata["reason"] == "bounded_linear_optimum"
        assert decision_values["x"] == 0.0
        assert decision_values["y"] == 5.0
        assert result.objective_value == 5.0
        assert engine.trace_count == 1

    def test_linear_solver_records_infeasible_coupled_constraints(self, engine):
        engine.register_objective(
            "obj-linear-2",
            "t-1",
            "Capacity",
            ObjectiveDirection.MAXIMIZE,
            target_value=2.0,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_coefficients": {"x": 1.0, "y": 1.0},
                "variable_bounds": {"x": [0.0, 4.0], "y": [0.0, 4.0]},
            },
        )
        engine.add_constraint(
            "c-linear-2",
            "t-1",
            "obj-linear-2",
            "x + y >= 9",
            9.0,
            float("inf"),
            metadata={"linear_terms": {"x": 1.0, "y": 1.0}},
        )
        engine.submit_solver_request("req-linear-2", "t-1", "obj-linear-2")

        result = engine.solve_solver_request("req-linear-2")

        assert result.status is OptimizationStatus.INFEASIBLE
        assert result.disposition is SolverDisposition.FAILED
        assert result.objective_value == 2.0
        assert result.metadata["reason"] == "infeasible_linear_constraints"
        assert result.metadata["decision_values"] == {}
        assert result.iterations > 0

    def test_linear_solver_rejects_unbounded_domain_before_enumeration(self, engine):
        engine.register_objective(
            "obj-linear-3",
            "t-1",
            "Open domain",
            ObjectiveDirection.MINIMIZE,
            target_value=11.0,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_coefficients": {"x": 1.0, "y": 1.0},
                "variable_bounds": {"x": [0.0, 10.0]},
            },
        )
        engine.add_constraint(
            "c-linear-3",
            "t-1",
            "obj-linear-3",
            "x + y >= 1",
            1.0,
            float("inf"),
            metadata={"linear_terms": {"x": 1.0, "y": 1.0}},
        )
        engine.submit_solver_request("req-linear-3", "t-1", "obj-linear-3")

        result = engine.solve_solver_request("req-linear-3")

        assert result.status is OptimizationStatus.UNBOUNDED
        assert result.disposition is SolverDisposition.FAILED
        assert result.objective_value == 11.0
        assert result.metadata["reason"] == "unbounded_linear_domain"
        assert result.metadata["decision_values"] == {}
        assert result.iterations == 0

    def test_linear_solver_rejects_malformed_metadata_with_bounded_message(self, engine):
        engine.register_objective(
            "obj-linear-4",
            "t-1",
            "Malformed",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x"],
                "linear_coefficients": {"x": "bad"},
                "variable_bounds": {"x": [0.0, 1.0]},
            },
        )
        engine.submit_solver_request("req-linear-4", "t-1", "obj-linear-4")

        with pytest.raises(RuntimeCoreInvariantError, match="Linear solver metadata must be numeric") as exc_info:
            engine.solve_solver_request("req-linear-4")

        assert str(exc_info.value) == "Linear solver metadata must be numeric"
        assert "bad" not in str(exc_info.value)
        assert "obj-linear-4" not in str(exc_info.value)

    def test_scalar_interval_solver_remains_default_without_linear_metadata(self, engine):
        engine.register_objective("obj-linear-5", "t-1", "Legacy scalar", ObjectiveDirection.MINIMIZE)
        engine.add_constraint("c-linear-5", "t-1", "obj-linear-5", "x >= 2", 2.0, 8.0)
        engine.submit_solver_request("req-linear-5", "t-1", "obj-linear-5")

        result = engine.solve_solver_request("req-linear-5")

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.metadata["solver"] == "deterministic_interval_v1"
        assert result.metadata["reason"] == "bounded_optimum"
        assert result.metadata["decision_value"] == 2.0
        assert result.objective_value == 2.0


class TestDeterministicLinearExpressionParser:
    def test_linear_expression_metadata_and_constraint_expression_solve(self, engine):
        engine.register_objective(
            "obj-expr-1",
            "t-1",
            "Expression cost",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_expression": "3*x + y",
                "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]},
            },
        )
        engine.add_constraint("c-expr-1", "t-1", "obj-expr-1", "x + y >= 5")
        engine.submit_solver_request("req-expr-1", "t-1", "obj-expr-1")

        result = engine.solve_solver_request("req-expr-1")
        decision_values = result.metadata["decision_values"]

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.metadata["solver"] == "deterministic_linear_v1"
        assert result.metadata["reason"] == "bounded_linear_optimum"
        assert decision_values["x"] == 0.0
        assert decision_values["y"] == 5.0
        assert result.objective_value == 5.0

    def test_linear_constraint_expression_supports_two_sided_variable_terms(self, engine):
        engine.register_objective(
            "obj-expr-2",
            "t-1",
            "Throughput expression",
            ObjectiveDirection.MAXIMIZE,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_expression": "x + 2*y",
                "variable_bounds": {"x": [0.0, 6.0], "y": [0.0, 6.0]},
            },
        )
        engine.add_constraint("c-expr-2", "t-1", "obj-expr-2", "x + y <= 6")
        engine.add_constraint("c-expr-3", "t-1", "obj-expr-2", "x - y >= 0")
        engine.submit_solver_request("req-expr-2", "t-1", "obj-expr-2")

        result = engine.solve_solver_request("req-expr-2")
        decision_values = result.metadata["decision_values"]

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert decision_values["x"] == 3.0
        assert decision_values["y"] == 3.0
        assert result.objective_value == 9.0
        assert result.iterations > 0

    def test_linear_constraint_expression_intersects_explicit_bounds(self, engine):
        engine.register_objective(
            "obj-expr-5",
            "t-1",
            "Bound intersection",
            ObjectiveDirection.MAXIMIZE,
            metadata={
                "decision_variables": ["x"],
                "linear_expression": "x",
                "variable_bounds": {"x": [0.0, 10.0]},
            },
        )
        engine.add_constraint("c-expr-5", "t-1", "obj-expr-5", "x <= 6", 0.0, 8.0)
        engine.submit_solver_request("req-expr-5", "t-1", "obj-expr-5")

        result = engine.solve_solver_request("req-expr-5")

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert result.metadata["solver"] == "deterministic_linear_v1"
        assert result.metadata["decision_values"]["x"] == 6.0
        assert result.objective_value == 6.0

    def test_linear_constraint_expression_supports_chained_bounds(self, engine):
        engine.register_objective(
            "obj-expr-6",
            "t-1",
            "Chained bounds",
            ObjectiveDirection.MAXIMIZE,
            metadata={
                "decision_variables": ["x"],
                "linear_expression": "x",
            },
        )
        engine.add_constraint("c-expr-6", "t-1", "obj-expr-6", "0 <= x <= 6")
        engine.submit_solver_request("req-expr-6", "t-1", "obj-expr-6")

        result = engine.solve_solver_request("req-expr-6")

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert result.metadata["solver"] == "deterministic_linear_v1"
        assert result.metadata["variable_bounds"]["x"] == {"lower": 0.0, "upper": 6.0}
        assert result.metadata["decision_values"]["x"] == 6.0
        assert result.objective_value == 6.0

    def test_linear_constraint_expression_supports_reversed_chained_bounds(self, engine):
        engine.register_objective(
            "obj-expr-7",
            "t-1",
            "Reversed chained bounds",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_expression": "x + y",
                "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]},
            },
        )
        engine.add_constraint("c-expr-7", "t-1", "obj-expr-7", "7 >= x + y >= 3")
        engine.submit_solver_request("req-expr-7", "t-1", "obj-expr-7")

        result = engine.solve_solver_request("req-expr-7")
        decision_values = result.metadata["decision_values"]

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.disposition is SolverDisposition.SOLVED
        assert result.metadata["reason"] == "bounded_linear_optimum"
        assert decision_values["x"] + decision_values["y"] == 3.0
        assert result.objective_value == 3.0
        assert result.iterations > 0

    def test_linear_constraint_expression_rejects_chained_variable_outer_bound(self, engine):
        engine.register_objective(
            "obj-expr-8",
            "t-1",
            "Bad chained bounds",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x", "y"],
                "linear_expression": "x",
                "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]},
            },
        )
        engine.add_constraint("c-expr-8", "t-1", "obj-expr-8", "y <= x <= 6")
        engine.submit_solver_request("req-expr-8", "t-1", "obj-expr-8")

        with pytest.raises(RuntimeCoreInvariantError, match="constant outer bounds") as exc_info:
            engine.solve_solver_request("req-expr-8")

        assert str(exc_info.value) == "Linear chained constraint requires constant outer bounds"
        assert "y <= x <= 6" not in str(exc_info.value)
        assert "obj-expr-8" not in str(exc_info.value)

    def test_linear_expression_rejects_unsupported_syntax_with_bounded_message(self, engine):
        engine.register_objective(
            "obj-expr-3",
            "t-1",
            "Bad expression",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x"],
                "linear_expression": "x^2",
                "variable_bounds": {"x": [0.0, 1.0]},
            },
        )
        engine.submit_solver_request("req-expr-3", "t-1", "obj-expr-3")

        with pytest.raises(RuntimeCoreInvariantError, match="Linear expression contains unsupported syntax") as exc_info:
            engine.solve_solver_request("req-expr-3")

        assert str(exc_info.value) == "Linear expression contains unsupported syntax"
        assert "x^2" not in str(exc_info.value)
        assert "obj-expr-3" not in str(exc_info.value)

    def test_linear_metadata_terms_take_precedence_over_expression_text(self, engine):
        engine.register_objective(
            "obj-expr-4",
            "t-1",
            "Metadata precedence",
            ObjectiveDirection.MINIMIZE,
            metadata={
                "decision_variables": ["x"],
                "linear_coefficients": {"x": 1.0},
                "linear_expression": "unsupported(x)",
                "variable_bounds": {"x": [0.0, 10.0]},
            },
        )
        engine.add_constraint(
            "c-expr-4",
            "t-1",
            "obj-expr-4",
            "unsupported constraint",
            4.0,
            8.0,
            metadata={"linear_terms": {"x": 1.0}},
        )
        engine.submit_solver_request("req-expr-4", "t-1", "obj-expr-4")

        result = engine.solve_solver_request("req-expr-4")

        assert result.status is OptimizationStatus.OPTIMAL
        assert result.metadata["reason"] == "bounded_linear_optimum"
        assert result.metadata["decision_values"]["x"] == 4.0
        assert result.objective_value == 4.0
