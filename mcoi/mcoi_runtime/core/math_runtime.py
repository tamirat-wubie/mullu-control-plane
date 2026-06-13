"""Purpose: math / optimization / units runtime engine.
Governance scope: managing quantities, unit conversions, optimization objectives,
    constraints, solver requests / results, uncertainty intervals, traces,
    violations, snapshots, and closure reports.
Dependencies: math_runtime contracts, event_spine, core invariants.
Invariants:
  - Dimension mismatches are detected and reported as violations.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from itertools import combinations, product
import re
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.math_runtime import (
    MathClosureReport,
    MathOptimizationConstraint,
    MathSnapshot,
    ObjectiveDirection,
    OptimizationObjective,
    OptimizationStatus,
    OptimizationTrace,
    QuantityRecord,
    QuantityValidation,
    SolverDisposition,
    SolverRequest,
    SolverResult,
    UncertaintyInterval,
    UncertaintyKind,
    UnitConversion,
    UnitDimension,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Violation record (lightweight, stored internally)
# ---------------------------------------------------------------------------

class _MathViolation:
    """Internal violation record for math runtime."""
    __slots__ = ("violation_id", "tenant_id", "operation", "reason", "detected_at")

    def __init__(self, violation_id: str, tenant_id: str, operation: str, reason: str, detected_at: str) -> None:
        self.violation_id = violation_id
        self.tenant_id = tenant_id
        self.operation = operation
        self.reason = reason
        self.detected_at = detected_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "tenant_id": self.tenant_id,
            "operation": self.operation,
            "reason": self.reason,
            "detected_at": self.detected_at,
        }


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-math", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_LINEAR_TOLERANCE = 1e-9
_MAX_LINEAR_VARIABLES = 4
_MAX_LINEAR_INTEGER_ASSIGNMENTS = 256
_LINEAR_TERM_RE = re.compile(r"^((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)?(?:\*)?([A-Za-z_][A-Za-z0-9_]*)$")
_LINEAR_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_LINEAR_COMPARATOR_RE = re.compile(r"(<=|>=|=)")


def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _bounded_number(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeCoreInvariantError("Linear solver metadata must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeCoreInvariantError("Linear solver metadata must be finite")
    return number


def _bounded_terms(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise RuntimeCoreInvariantError("Linear solver metadata requires terms")
    terms: dict[str, float] = {}
    for key, raw_number in value.items():
        if not isinstance(key, str) or not key.strip():
            raise RuntimeCoreInvariantError("Linear solver metadata requires variable names")
        number = _bounded_number(raw_number)
        if abs(number) > _LINEAR_TOLERANCE:
            terms[key] = number
    if not terms:
        raise RuntimeCoreInvariantError("Linear solver metadata requires nonzero terms")
    return terms


def _merge_linear_term(target: dict[str, float], variable_name: str, coefficient: float) -> None:
    updated = target.get(variable_name, 0.0) + coefficient
    if abs(updated) <= _LINEAR_TOLERANCE:
        target.pop(variable_name, None)
    else:
        target[variable_name] = updated


def _parse_linear_side(expression: str) -> tuple[dict[str, float], float]:
    normalized = expression.replace(" ", "")
    if not normalized:
        raise RuntimeCoreInvariantError("Linear expression is empty")
    if any(symbol in normalized for symbol in ("(", ")", "/", "^")):
        raise RuntimeCoreInvariantError("Linear expression contains unsupported syntax")
    terms: dict[str, float] = {}
    constant = 0.0
    for raw_part in re.findall(r"[+-]?[^+-]+", normalized):
        sign = -1.0 if raw_part.startswith("-") else 1.0
        part = raw_part[1:] if raw_part[:1] in {"+", "-"} else raw_part
        if not part:
            raise RuntimeCoreInvariantError("Linear expression contains unsupported syntax")
        if _LINEAR_NUMBER_RE.fullmatch(part):
            constant += sign * _bounded_number(float(part))
            continue
        term_match = _LINEAR_TERM_RE.fullmatch(part)
        if term_match is None:
            raise RuntimeCoreInvariantError("Linear expression contains unsupported syntax")
        raw_coefficient, variable_name = term_match.groups()
        coefficient = 1.0 if raw_coefficient in (None, "") else _bounded_number(float(raw_coefficient))
        _merge_linear_term(terms, variable_name, sign * coefficient)
    return terms, constant


def _parse_linear_expression(expression: str) -> dict[str, float]:
    terms, constant = _parse_linear_side(expression)
    if abs(constant) > _LINEAR_TOLERANCE:
        raise RuntimeCoreInvariantError("Linear objective expression must not contain constants")
    if not terms:
        raise RuntimeCoreInvariantError("Linear solver metadata requires nonzero terms")
    return terms


def _parse_linear_constraint_expression(expression: str) -> tuple[dict[str, float], float, float]:
    matches = tuple(_LINEAR_COMPARATOR_RE.finditer(expression))
    if len(matches) > 1:
        raise RuntimeCoreInvariantError("Linear constraint expression must contain one comparator")
    if not matches:
        terms, constant = _parse_linear_side(expression)
        if abs(constant) > _LINEAR_TOLERANCE:
            raise RuntimeCoreInvariantError("Linear constraint expression constant requires comparator")
        if not terms:
            raise RuntimeCoreInvariantError("Linear solver metadata requires nonzero terms")
        return terms, float("-inf"), float("inf")

    match = matches[0]
    operator = match.group(1)
    lhs = expression[:match.start()]
    rhs = expression[match.end():]
    lhs_terms, lhs_constant = _parse_linear_side(lhs)
    rhs_terms, rhs_constant = _parse_linear_side(rhs)
    terms = dict(lhs_terms)
    for variable_name, coefficient in rhs_terms.items():
        _merge_linear_term(terms, variable_name, -coefficient)
    if not terms:
        raise RuntimeCoreInvariantError("Linear solver metadata requires nonzero terms")
    bound = rhs_constant - lhs_constant
    if operator == "<=":
        return terms, float("-inf"), bound
    if operator == ">=":
        return terms, bound, float("inf")
    return terms, bound, bound


def _solve_linear_system(matrix: tuple[tuple[float, ...], ...], vector: tuple[float, ...]) -> tuple[float, ...] | None:
    dimension = len(vector)
    rows = [list(row) + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(dimension):
        pivot = max(range(column, dimension), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) <= _LINEAR_TOLERANCE:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        pivot_value = rows[column][column]
        for current_column in range(column, dimension + 1):
            rows[column][current_column] /= pivot_value
        for row in range(dimension):
            if row == column:
                continue
            factor = rows[row][column]
            for current_column in range(column, dimension + 1):
                rows[row][current_column] -= factor * rows[column][current_column]
    return tuple(rows[row][dimension] for row in range(dimension))


class MathRuntimeEngine:
    """Engine for governed math / optimization / units runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._quantities: dict[str, QuantityRecord] = {}
        self._conversions: dict[str, UnitConversion] = {}
        self._objectives: dict[str, OptimizationObjective] = {}
        self._constraints: dict[str, MathOptimizationConstraint] = {}
        self._requests: dict[str, SolverRequest] = {}
        self._results: dict[str, SolverResult] = {}
        self._intervals: dict[str, UncertaintyInterval] = {}
        self._traces: dict[str, OptimizationTrace] = {}
        self._violations: dict[str, _MathViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def quantity_count(self) -> int:
        return len(self._quantities)

    @property
    def conversion_count(self) -> int:
        return len(self._conversions)

    @property
    def objective_count(self) -> int:
        return len(self._objectives)

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def interval_count(self) -> int:
        return len(self._intervals)

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Quantities
    # ------------------------------------------------------------------

    def register_quantity(
        self,
        quantity_id: str,
        tenant_id: str,
        value: float,
        unit_label: str,
        dimension: UnitDimension,
        tolerance: float = 0.0,
    ) -> QuantityRecord:
        """Register a new quantity. Duplicate quantity_id raises."""
        if quantity_id in self._quantities:
            raise RuntimeCoreInvariantError("Duplicate quantity_id")
        now = self._now()
        q = QuantityRecord(
            quantity_id=quantity_id,
            tenant_id=tenant_id,
            value=value,
            unit_label=unit_label,
            dimension=dimension,
            tolerance=tolerance,
            created_at=now,
        )
        self._quantities[quantity_id] = q
        _emit(self._events, "quantity_registered", {
            "quantity_id": quantity_id, "dimension": dimension.value,
        }, quantity_id, self._now())
        return q

    def get_quantity(self, quantity_id: str) -> QuantityRecord:
        q = self._quantities.get(quantity_id)
        if q is None:
            raise RuntimeCoreInvariantError("Unknown quantity_id")
        return q

    def quantities_for_tenant(self, tenant_id: str) -> tuple[QuantityRecord, ...]:
        return tuple(q for q in self._quantities.values() if q.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------

    def register_conversion(
        self,
        conversion_id: str,
        tenant_id: str,
        from_unit: str,
        to_unit: str,
        factor: float,
        dimension: UnitDimension,
    ) -> UnitConversion:
        """Register a unit conversion factor. Duplicate conversion_id raises."""
        if conversion_id in self._conversions:
            raise RuntimeCoreInvariantError("Duplicate conversion_id")
        now = self._now()
        uc = UnitConversion(
            conversion_id=conversion_id,
            tenant_id=tenant_id,
            from_unit=from_unit,
            to_unit=to_unit,
            factor=factor,
            dimension=dimension,
            created_at=now,
        )
        self._conversions[conversion_id] = uc
        _emit(self._events, "conversion_registered", {
            "conversion_id": conversion_id, "from": from_unit, "to": to_unit,
        }, conversion_id, self._now())
        return uc

    def convert_quantity(self, quantity_id: str, target_unit: str) -> float:
        """Convert a quantity to a target unit. Returns value * factor.
        Raises if no matching conversion or dimension mismatch."""
        q = self.get_quantity(quantity_id)
        if q.unit_label == target_unit:
            return q.value
        # Find conversion
        for conv in self._conversions.values():
            if conv.from_unit == q.unit_label and conv.to_unit == target_unit:
                if conv.dimension != q.dimension:
                    raise RuntimeCoreInvariantError(
                        "Dimension mismatch between quantity and conversion"
                    )
                return q.value * conv.factor
        raise RuntimeCoreInvariantError("No conversion available for requested unit pair")

    def validate_dimension(self, quantity_id_a: str, quantity_id_b: str) -> QuantityValidation:
        """Validate that two quantities share the same dimension."""
        a = self.get_quantity(quantity_id_a)
        b = self.get_quantity(quantity_id_b)
        if a.dimension == b.dimension:
            return QuantityValidation.VALID
        return QuantityValidation.DIMENSION_MISMATCH

    # ------------------------------------------------------------------
    # Objectives
    # ------------------------------------------------------------------

    def register_objective(
        self,
        objective_id: str,
        tenant_id: str,
        display_name: str,
        direction: ObjectiveDirection,
        target_value: float = 0.0,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> OptimizationObjective:
        """Register an optimization objective. Duplicate objective_id raises."""
        if objective_id in self._objectives:
            raise RuntimeCoreInvariantError("Duplicate objective_id")
        now = self._now()
        obj = OptimizationObjective(
            objective_id=objective_id,
            tenant_id=tenant_id,
            display_name=display_name,
            direction=direction,
            target_value=target_value,
            weight=weight,
            created_at=now,
            metadata=metadata or {},
        )
        self._objectives[objective_id] = obj
        _emit(self._events, "objective_registered", {
            "objective_id": objective_id, "direction": direction.value,
        }, objective_id, self._now())
        return obj

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def add_constraint(
        self,
        constraint_id: str,
        tenant_id: str,
        objective_ref: str,
        expression: str,
        lower_bound: float = float("-inf"),
        upper_bound: float = float("inf"),
        metadata: dict[str, Any] | None = None,
    ) -> MathOptimizationConstraint:
        """Add a constraint on an objective. Duplicate constraint_id raises."""
        if constraint_id in self._constraints:
            raise RuntimeCoreInvariantError("Duplicate constraint_id")
        now = self._now()
        con = MathOptimizationConstraint(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            objective_ref=objective_ref,
            expression=expression,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            created_at=now,
            metadata=metadata or {},
        )
        self._constraints[constraint_id] = con
        _emit(self._events, "constraint_added", {
            "constraint_id": constraint_id, "objective_ref": objective_ref,
        }, constraint_id, self._now())
        return con

    # ------------------------------------------------------------------
    # Solver Requests
    # ------------------------------------------------------------------

    def submit_solver_request(
        self,
        request_id: str,
        tenant_id: str,
        objective_ref: str,
        max_iterations: int = 1000,
        timeout_ms: int = 30000,
    ) -> SolverRequest:
        """Submit a solver request with FEASIBLE status. Duplicate request_id raises."""
        if request_id in self._requests:
            raise RuntimeCoreInvariantError("Duplicate request_id")
        now = self._now()
        sr = SolverRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            objective_ref=objective_ref,
            status=OptimizationStatus.FEASIBLE,
            max_iterations=max_iterations,
            timeout_ms=timeout_ms,
            created_at=now,
        )
        self._requests[request_id] = sr
        _emit(self._events, "solver_request_submitted", {
            "request_id": request_id, "objective_ref": objective_ref,
        }, request_id, self._now())
        return sr

    def solve_solver_request(
        self,
        request_id: str,
        result_id: str | None = None,
    ) -> SolverResult:
        """Solve a one-dimensional bounded objective deterministically.

        The first built-in backend treats constraints for the objective as
        interval bounds over a single decision scalar. It records one trace
        step and one result. Non-finite or contradictory bounds are explicit
        solver outcomes, never silent fallbacks.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise RuntimeCoreInvariantError("Unknown solver request")
        if any(result.request_ref == request_id for result in self._results.values()):
            raise RuntimeCoreInvariantError("Solver request already has result")

        objective = self._objectives.get(request.objective_ref)
        if objective is None or objective.tenant_id != request.tenant_id:
            raise RuntimeCoreInvariantError("Unknown objective_ref")

        constraints = tuple(
            constraint
            for constraint in self._constraints.values()
            if constraint.tenant_id == request.tenant_id and constraint.objective_ref == objective.objective_id
        )
        if self._uses_linear_solver_metadata(objective, constraints):
            return self._solve_linear_request(request, objective, constraints, result_id)

        lower_bound = float("-inf")
        upper_bound = float("inf")
        for constraint in constraints:
            if math.isnan(constraint.lower_bound) or math.isnan(constraint.upper_bound):
                raise RuntimeCoreInvariantError("Constraint bound must not be NaN")
            lower_bound = max(lower_bound, constraint.lower_bound)
            upper_bound = min(upper_bound, constraint.upper_bound)

        effective_result_id = result_id or stable_identifier("res-math-solver", {"request": request_id})
        trace_id = stable_identifier("trace-math-solver", {"request": request_id, "result": effective_result_id})
        iterations = 1 if constraints else 0
        metadata: dict[str, Any] = {
            "solver": "deterministic_interval_v1",
            "decision_dimension": 1,
            "constraint_count": len(constraints),
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "objective_direction": objective.direction.value,
            "objective_weight": objective.weight,
        }

        if lower_bound > upper_bound:
            status = OptimizationStatus.INFEASIBLE
            disposition = SolverDisposition.FAILED
            decision_value = objective.target_value
            metadata["reason"] = "infeasible_bounds"
        elif objective.direction is ObjectiveDirection.MINIMIZE and math.isinf(lower_bound):
            status = OptimizationStatus.UNBOUNDED
            disposition = SolverDisposition.FAILED
            decision_value = objective.target_value
            metadata["reason"] = "unbounded_minimize"
        elif objective.direction is ObjectiveDirection.MAXIMIZE and math.isinf(upper_bound):
            status = OptimizationStatus.UNBOUNDED
            disposition = SolverDisposition.FAILED
            decision_value = objective.target_value
            metadata["reason"] = "unbounded_maximize"
        else:
            status = OptimizationStatus.OPTIMAL
            disposition = SolverDisposition.SOLVED
            decision_value = lower_bound if objective.direction is ObjectiveDirection.MINIMIZE else upper_bound
            metadata["reason"] = "bounded_optimum"

        objective_value = decision_value * objective.weight
        metadata["decision_value"] = decision_value
        metadata["weighted_objective_value"] = objective_value

        self.record_trace_step(
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            request_ref=request_id,
            step=0,
            objective_value=objective_value,
            feasible=status is OptimizationStatus.OPTIMAL,
            metadata={"solver": metadata["solver"], "reason": metadata["reason"]},
        )
        return self.record_solver_result(
            result_id=effective_result_id,
            tenant_id=request.tenant_id,
            request_ref=request_id,
            status=status,
            disposition=disposition,
            objective_value=objective_value,
            iterations=iterations,
            duration_ms=0.0,
            metadata=metadata,
        )

    def _uses_linear_solver_metadata(
        self,
        objective: OptimizationObjective,
        constraints: tuple[MathOptimizationConstraint, ...],
    ) -> bool:
        return "linear_coefficients" in objective.metadata or "linear_expression" in objective.metadata or any(
            "linear_terms" in constraint.metadata for constraint in constraints
        )

    def _solve_linear_request(
        self,
        request: SolverRequest,
        objective: OptimizationObjective,
        constraints: tuple[MathOptimizationConstraint, ...],
        result_id: str | None,
    ) -> SolverResult:
        objective_terms = self._linear_objective_terms(objective)
        if objective_terms is None:
            raise RuntimeCoreInvariantError("Linear objective metadata required")
        variable_names = self._linear_variable_names(objective, objective_terms, constraints)
        coefficients = tuple(objective_terms.get(name, 0.0) for name in variable_names)
        inequalities, lower_bounds, upper_bounds = self._linear_inequalities(
            objective,
            constraints,
            variable_names,
        )
        active_inequalities = list(inequalities)
        integer_variables, binary_variables = self._linear_integrality(objective, variable_names)
        if binary_variables:
            variable_index = {name: index for index, name in enumerate(variable_names)}
            for name in binary_variables:
                lower_bounds[name] = max(lower_bounds[name], 0.0)
                upper_bounds[name] = min(upper_bounds[name], 1.0)
                self._append_variable_bound_inequalities(
                    active_inequalities,
                    variable_index[name],
                    len(variable_names),
                    0.0,
                    1.0,
                )
        effective_result_id = result_id or stable_identifier("res-math-linear-solver", {"request": request.request_id})
        trace_id = stable_identifier("trace-math-linear-solver", {
            "request": request.request_id,
            "result": effective_result_id,
        })
        metadata: dict[str, Any] = {
            "solver": "deterministic_linear_v1",
            "decision_dimension": len(variable_names),
            "decision_variables": variable_names,
            "constraint_count": len(constraints),
            "objective_direction": objective.direction.value,
            "objective_weight": objective.weight,
            "variable_bounds": {
                name: {"lower": lower_bounds[name], "upper": upper_bounds[name]}
                for name in variable_names
            },
        }
        if integer_variables:
            metadata |= {
                "integer_variables": integer_variables,
                "binary_variables": binary_variables,
                "integer_assignment_limit": _MAX_LINEAR_INTEGER_ASSIGNMENTS,
            }

        infeasible_variable = next(
            (name for name in variable_names if lower_bounds[name] > upper_bounds[name] + _LINEAR_TOLERANCE),
            None,
        )
        if infeasible_variable is not None:
            return self._record_linear_solver_outcome(
                request=request,
                result_id=effective_result_id,
                trace_id=trace_id,
                status=OptimizationStatus.INFEASIBLE,
                disposition=SolverDisposition.FAILED,
                objective_value=objective.target_value * objective.weight,
                iterations=0,
                metadata=metadata | {"reason": "infeasible_variable_bounds", "decision_values": {}},
            )

        if any(math.isinf(lower_bounds[name]) or math.isinf(upper_bounds[name]) for name in variable_names):
            return self._record_linear_solver_outcome(
                request=request,
                result_id=effective_result_id,
                trace_id=trace_id,
                status=OptimizationStatus.UNBOUNDED,
                disposition=SolverDisposition.FAILED,
                objective_value=objective.target_value * objective.weight,
                iterations=0,
                metadata=metadata | {"reason": "unbounded_linear_domain", "decision_values": {}},
            )

        if integer_variables:
            integer_assignments = self._linear_integer_assignments(variable_names, integer_variables, lower_bounds, upper_bounds)
            metadata["integer_assignment_count"] = len(integer_assignments)
            if not integer_assignments:
                return self._record_linear_solver_outcome(
                    request=request,
                    result_id=effective_result_id,
                    trace_id=trace_id,
                    status=OptimizationStatus.INFEASIBLE,
                    disposition=SolverDisposition.FAILED,
                    objective_value=objective.target_value * objective.weight,
                    iterations=0,
                    metadata=metadata | {"reason": "infeasible_integer_domain", "decision_values": {}},
                )
            candidates = self._linear_integer_candidate_points(
                tuple(active_inequalities),
                len(variable_names),
                integer_assignments,
            )
        else:
            candidates = self._linear_candidate_points(tuple(active_inequalities), len(variable_names))
        feasible_candidates = tuple(
            candidate
            for candidate in candidates
            if all(
                _dot(coefficients_row, candidate) <= bound + _LINEAR_TOLERANCE
                for coefficients_row, bound in inequalities
            )
        )
        if not feasible_candidates:
            return self._record_linear_solver_outcome(
                request=request,
                result_id=effective_result_id,
                trace_id=trace_id,
                status=OptimizationStatus.INFEASIBLE,
                disposition=SolverDisposition.FAILED,
                objective_value=objective.target_value * objective.weight,
                iterations=len(candidates),
                metadata=metadata | {"reason": "infeasible_linear_constraints", "decision_values": {}},
            )

        if objective.direction is ObjectiveDirection.MINIMIZE:
            decision = min(feasible_candidates, key=lambda candidate: (_dot(coefficients, candidate), candidate))
        else:
            decision = max(feasible_candidates, key=lambda candidate: (_dot(coefficients, candidate), candidate))
        objective_value = _dot(coefficients, decision) * objective.weight
        decision_values = {name: decision[index] for index, name in enumerate(variable_names)}
        return self._record_linear_solver_outcome(
            request=request,
            result_id=effective_result_id,
            trace_id=trace_id,
            status=OptimizationStatus.OPTIMAL,
            disposition=SolverDisposition.SOLVED,
            objective_value=objective_value,
            iterations=len(candidates),
            metadata=metadata | {
                "reason": "bounded_linear_optimum",
                "decision_values": decision_values,
                "weighted_objective_value": objective_value,
            },
        )

    def _linear_variable_names(
        self,
        objective: OptimizationObjective,
        objective_terms: dict[str, float],
        constraints: tuple[MathOptimizationConstraint, ...],
    ) -> tuple[str, ...]:
        variable_metadata = objective.metadata.get("decision_variables")
        if variable_metadata is None:
            names = set(objective_terms)
            for constraint in constraints:
                if "linear_terms" in constraint.metadata:
                    names.update(_bounded_terms(constraint.metadata["linear_terms"]))
                else:
                    terms, _lower, _upper = _parse_linear_constraint_expression(constraint.expression)
                    names.update(terms)
            variable_names = tuple(sorted(names))
        else:
            if not isinstance(variable_metadata, (list, tuple)) or not variable_metadata:
                raise RuntimeCoreInvariantError("Linear solver metadata requires variables")
            variable_names = tuple(variable_metadata)
            if any(not isinstance(name, str) or not name.strip() for name in variable_names):
                raise RuntimeCoreInvariantError("Linear solver metadata requires variable names")
            if len(set(variable_names)) != len(variable_names):
                raise RuntimeCoreInvariantError("Linear solver metadata requires unique variables")
            unknown_terms = set(objective_terms) - set(variable_names)
            if unknown_terms:
                raise RuntimeCoreInvariantError("Linear objective references unknown variable")
        if len(variable_names) > _MAX_LINEAR_VARIABLES:
            raise RuntimeCoreInvariantError("Linear solver variable limit exceeded")
        return variable_names

    def _linear_objective_terms(self, objective: OptimizationObjective) -> dict[str, float] | None:
        coefficient_metadata = objective.metadata.get("linear_coefficients")
        if coefficient_metadata is not None:
            return _bounded_terms(coefficient_metadata)
        expression_metadata = objective.metadata.get("linear_expression")
        if expression_metadata is None:
            return None
        if not isinstance(expression_metadata, str):
            raise RuntimeCoreInvariantError("Linear objective expression must be text")
        return _parse_linear_expression(expression_metadata)

    def _linear_inequalities(
        self,
        objective: OptimizationObjective,
        constraints: tuple[MathOptimizationConstraint, ...],
        variable_names: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], float], dict[str, float], dict[str, float]]:
        variable_index = {name: index for index, name in enumerate(variable_names)}
        inequalities: list[tuple[tuple[float, ...], float]] = []
        lower_bounds = {name: float("-inf") for name in variable_names}
        upper_bounds = {name: float("inf") for name in variable_names}

        raw_bounds = objective.metadata.get("variable_bounds", {})
        if raw_bounds:
            if not isinstance(raw_bounds, Mapping):
                raise RuntimeCoreInvariantError("Linear solver metadata requires variable bounds")
            for name, bounds in raw_bounds.items():
                if name not in variable_index:
                    raise RuntimeCoreInvariantError("Linear bounds reference unknown variable")
                if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                    raise RuntimeCoreInvariantError("Linear solver metadata requires bound pairs")
                lower, upper = _bounded_number(bounds[0]), _bounded_number(bounds[1])
                lower_bounds[name] = max(lower_bounds[name], lower)
                upper_bounds[name] = min(upper_bounds[name], upper)
                self._append_variable_bound_inequalities(
                    inequalities,
                    variable_index[name],
                    len(variable_names),
                    lower,
                    upper,
                )

        for constraint in constraints:
            if math.isnan(constraint.lower_bound) or math.isnan(constraint.upper_bound):
                raise RuntimeCoreInvariantError("Constraint bound must not be NaN")
            terms, lower_bound, upper_bound = self._linear_constraint_terms_and_bounds(constraint)
            unknown_terms = set(terms) - set(variable_names)
            if unknown_terms:
                raise RuntimeCoreInvariantError("Linear constraint references unknown variable")
            coefficients = tuple(terms.get(name, 0.0) for name in variable_names)
            if math.isfinite(upper_bound):
                inequalities.append((coefficients, upper_bound))
            if math.isfinite(lower_bound):
                inequalities.append((tuple(-value for value in coefficients), -lower_bound))
            if sum(1 for value in coefficients if abs(value) > _LINEAR_TOLERANCE) == 1:
                index = next(index for index, value in enumerate(coefficients) if abs(value) > _LINEAR_TOLERANCE)
                name = variable_names[index]
                coefficient = coefficients[index]
                if math.isfinite(lower_bound):
                    bound = lower_bound / coefficient
                    if coefficient > 0:
                        lower_bounds[name] = max(lower_bounds[name], bound)
                    else:
                        upper_bounds[name] = min(upper_bounds[name], bound)
                if math.isfinite(upper_bound):
                    bound = upper_bound / coefficient
                    if coefficient > 0:
                        upper_bounds[name] = min(upper_bounds[name], bound)
                    else:
                        lower_bounds[name] = max(lower_bounds[name], bound)
        return tuple(inequalities), lower_bounds, upper_bounds

    def _linear_constraint_terms_and_bounds(
        self,
        constraint: MathOptimizationConstraint,
    ) -> tuple[dict[str, float], float, float]:
        if "linear_terms" in constraint.metadata:
            return _bounded_terms(constraint.metadata["linear_terms"]), constraint.lower_bound, constraint.upper_bound
        expression_terms, expression_lower, expression_upper = _parse_linear_constraint_expression(constraint.expression)
        lower_bound = constraint.lower_bound
        upper_bound = constraint.upper_bound
        if math.isinf(lower_bound) and not math.isinf(expression_lower):
            lower_bound = expression_lower
        if math.isinf(upper_bound) and not math.isinf(expression_upper):
            upper_bound = expression_upper
        return expression_terms, lower_bound, upper_bound

    def _linear_integrality(
        self,
        objective: OptimizationObjective,
        variable_names: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        variable_set = set(variable_names)
        integer_variables = self._linear_variable_metadata_tuple(
            objective.metadata.get("integer_variables"),
            "Linear integer metadata requires variable names",
        )
        binary_variables = self._linear_variable_metadata_tuple(
            objective.metadata.get("binary_variables"),
            "Linear binary metadata requires variable names",
        )
        unknown_variables = (set(integer_variables) | set(binary_variables)) - variable_set
        if unknown_variables:
            raise RuntimeCoreInvariantError("Linear integrality references unknown variable")
        all_integer_variables = tuple(name for name in variable_names if name in set(integer_variables) | set(binary_variables))
        ordered_binary_variables = tuple(name for name in variable_names if name in set(binary_variables))
        return all_integer_variables, ordered_binary_variables

    def _linear_variable_metadata_tuple(self, raw_value: Any, error_message: str) -> tuple[str, ...]:
        if raw_value is None:
            return ()
        if not isinstance(raw_value, (list, tuple)) or not raw_value:
            raise RuntimeCoreInvariantError(error_message)
        variable_names = tuple(raw_value)
        if any(not isinstance(name, str) or not name.strip() for name in variable_names):
            raise RuntimeCoreInvariantError(error_message)
        if len(set(variable_names)) != len(variable_names):
            raise RuntimeCoreInvariantError("Linear integrality metadata requires unique variables")
        return variable_names

    def _append_variable_bound_inequalities(
        self,
        inequalities: list[tuple[tuple[float, ...], float]],
        variable_index: int,
        dimension: int,
        lower: float,
        upper: float,
    ) -> None:
        upper_row = [0.0] * dimension
        upper_row[variable_index] = 1.0
        inequalities.append((tuple(upper_row), upper))
        lower_row = [0.0] * dimension
        lower_row[variable_index] = -1.0
        inequalities.append((tuple(lower_row), -lower))

    def _linear_candidate_points(
        self,
        inequalities: tuple[tuple[tuple[float, ...], float], ...],
        dimension: int,
    ) -> tuple[tuple[float, ...], ...]:
        candidates: list[tuple[float, ...]] = []
        seen: set[tuple[float, ...]] = set()
        for selected in combinations(inequalities, dimension):
            matrix = tuple(row for row, _bound in selected)
            vector = tuple(bound for _row, bound in selected)
            solved = _solve_linear_system(matrix, vector)
            if solved is None or any(not math.isfinite(value) for value in solved):
                continue
            rounded = tuple(0.0 if abs(value) <= _LINEAR_TOLERANCE else round(value, 12) for value in solved)
            if rounded not in seen:
                seen.add(rounded)
                candidates.append(rounded)
        return tuple(candidates)

    def _linear_integer_assignments(
        self,
        variable_names: tuple[str, ...],
        integer_variables: tuple[str, ...],
        lower_bounds: dict[str, float],
        upper_bounds: dict[str, float],
    ) -> tuple[tuple[tuple[int, float], ...], ...]:
        integer_indices = tuple(
            (index, name) for index, name in enumerate(variable_names) if name in set(integer_variables)
        )
        domains: list[tuple[float, ...]] = []
        assignment_count = 1
        for _index, name in integer_indices:
            lower = math.ceil(lower_bounds[name] - _LINEAR_TOLERANCE)
            upper = math.floor(upper_bounds[name] + _LINEAR_TOLERANCE)
            if lower > upper:
                return ()
            domain = tuple(float(value) for value in range(lower, upper + 1))
            assignment_count *= len(domain)
            if assignment_count > _MAX_LINEAR_INTEGER_ASSIGNMENTS:
                raise RuntimeCoreInvariantError("Linear integer assignment limit exceeded")
            domains.append(domain)
        return tuple(
            tuple((integer_indices[index][0], value) for index, value in enumerate(values))
            for values in product(*domains)
        )

    def _linear_integer_candidate_points(
        self,
        inequalities: tuple[tuple[tuple[float, ...], float], ...],
        dimension: int,
        integer_assignments: tuple[tuple[tuple[int, float], ...], ...],
    ) -> tuple[tuple[float, ...], ...]:
        candidates: list[tuple[float, ...]] = []
        seen: set[tuple[float, ...]] = set()
        for assignment in integer_assignments:
            assignment_inequalities = list(inequalities)
            for variable_index, value in assignment:
                upper_row = [0.0] * dimension
                upper_row[variable_index] = 1.0
                assignment_inequalities.append((tuple(upper_row), value))
                lower_row = [0.0] * dimension
                lower_row[variable_index] = -1.0
                assignment_inequalities.append((tuple(lower_row), -value))
            for candidate in self._linear_candidate_points(tuple(assignment_inequalities), dimension):
                if any(abs(candidate[variable_index] - value) > _LINEAR_TOLERANCE for variable_index, value in assignment):
                    continue
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
        return tuple(candidates)

    def _record_linear_solver_outcome(
        self,
        request: SolverRequest,
        result_id: str,
        trace_id: str,
        status: OptimizationStatus,
        disposition: SolverDisposition,
        objective_value: float,
        iterations: int,
        metadata: dict[str, Any],
    ) -> SolverResult:
        self.record_trace_step(
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            request_ref=request.request_id,
            step=0,
            objective_value=objective_value,
            feasible=status is OptimizationStatus.OPTIMAL,
            metadata={"solver": metadata["solver"], "reason": metadata["reason"]},
        )
        return self.record_solver_result(
            result_id=result_id,
            tenant_id=request.tenant_id,
            request_ref=request.request_id,
            status=status,
            disposition=disposition,
            objective_value=objective_value,
            iterations=iterations,
            duration_ms=0.0,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Solver Results
    # ------------------------------------------------------------------

    def record_solver_result(
        self,
        result_id: str,
        tenant_id: str,
        request_ref: str,
        status: OptimizationStatus,
        disposition: SolverDisposition,
        objective_value: float,
        iterations: int = 0,
        duration_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> SolverResult:
        """Record a solver result. Duplicate result_id raises."""
        if result_id in self._results:
            raise RuntimeCoreInvariantError("Duplicate result_id")
        now = self._now()
        res = SolverResult(
            result_id=result_id,
            tenant_id=tenant_id,
            request_ref=request_ref,
            status=status,
            disposition=disposition,
            objective_value=objective_value,
            iterations=iterations,
            duration_ms=duration_ms,
            solved_at=now,
            metadata=metadata or {},
        )
        self._results[result_id] = res
        _emit(self._events, "solver_result_recorded", {
            "result_id": result_id, "status": status.value, "disposition": disposition.value,
        }, result_id, self._now())
        return res

    # ------------------------------------------------------------------
    # Uncertainty
    # ------------------------------------------------------------------

    def record_uncertainty(
        self,
        interval_id: str,
        tenant_id: str,
        quantity_ref: str,
        kind: UncertaintyKind,
        lower: float,
        upper: float,
        confidence: float = 0.95,
    ) -> UncertaintyInterval:
        """Record an uncertainty interval. Duplicate interval_id raises."""
        if interval_id in self._intervals:
            raise RuntimeCoreInvariantError("Duplicate interval_id")
        now = self._now()
        ui = UncertaintyInterval(
            interval_id=interval_id,
            tenant_id=tenant_id,
            quantity_ref=quantity_ref,
            kind=kind,
            lower=lower,
            upper=upper,
            confidence=confidence,
            created_at=now,
        )
        self._intervals[interval_id] = ui
        _emit(self._events, "uncertainty_recorded", {
            "interval_id": interval_id, "kind": kind.value,
        }, interval_id, self._now())
        return ui

    # ------------------------------------------------------------------
    # Trace Steps
    # ------------------------------------------------------------------

    def record_trace_step(
        self,
        trace_id: str,
        tenant_id: str,
        request_ref: str,
        step: int,
        objective_value: float,
        feasible: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> OptimizationTrace:
        """Record a trace step. Duplicate trace_id raises."""
        if trace_id in self._traces:
            raise RuntimeCoreInvariantError("Duplicate trace_id")
        now = self._now()
        ot = OptimizationTrace(
            trace_id=trace_id,
            tenant_id=tenant_id,
            request_ref=request_ref,
            step=step,
            objective_value=objective_value,
            feasible=feasible,
            recorded_at=now,
            metadata=metadata or {},
        )
        self._traces[trace_id] = ot
        _emit(self._events, "trace_step_recorded", {
            "trace_id": trace_id, "step": step,
        }, trace_id, self._now())
        return ot

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def math_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> MathSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = MathSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_quantities=sum(1 for q in self._quantities.values() if q.tenant_id == tenant_id),
            total_conversions=sum(1 for c in self._conversions.values() if c.tenant_id == tenant_id),
            total_objectives=sum(1 for o in self._objectives.values() if o.tenant_id == tenant_id),
            total_constraints=sum(1 for c in self._constraints.values() if c.tenant_id == tenant_id),
            total_requests=sum(1 for r in self._requests.values() if r.tenant_id == tenant_id),
            total_results=sum(1 for r in self._results.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_math_violations(self, tenant_id: str) -> tuple[_MathViolation, ...]:
        """Detect math violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[_MathViolation] = []

        # 1) dimension_mismatch_in_constraint: constraint references quantities
        #    with different dimensions (check expression for quantity refs)
        # Since expressions are opaque strings, we check constraints whose
        # objective_ref references an objective, and if the constraint's
        # expression references known quantity IDs with mismatched dimensions.
        # Simplified: detect constraints where lower_bound > upper_bound
        # (logically infeasible bounds).
        tenant_constraints = [c for c in self._constraints.values() if c.tenant_id == tenant_id]
        for con in tenant_constraints:
            if con.lower_bound > con.upper_bound:
                vid = stable_identifier("viol-math", {
                    "constraint": con.constraint_id, "op": "dimension_mismatch_in_constraint",
                })
                if vid not in self._violations:
                    v = _MathViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="dimension_mismatch_in_constraint",
                        reason="Constraint bounds are inverted",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) infeasible_no_result: solver request with no result
        tenant_requests = [r for r in self._requests.values() if r.tenant_id == tenant_id]
        result_request_refs = {r.request_ref for r in self._results.values() if r.tenant_id == tenant_id}
        for req in tenant_requests:
            if req.request_id not in result_request_refs:
                vid = stable_identifier("viol-math", {
                    "request": req.request_id, "op": "infeasible_no_result",
                })
                if vid not in self._violations:
                    v = _MathViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="infeasible_no_result",
                        reason="Solver request has no result",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) uncertainty_inverted: interval where lower > upper
        tenant_intervals = [i for i in self._intervals.values() if i.tenant_id == tenant_id]
        for interval in tenant_intervals:
            if interval.lower > interval.upper:
                vid = stable_identifier("viol-math", {
                    "interval": interval.interval_id, "op": "uncertainty_inverted",
                })
                if vid not in self._violations:
                    v = _MathViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="uncertainty_inverted",
                        reason="Uncertainty interval bounds are inverted",
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
            "conversions": self._conversions,
            "intervals": self._intervals,
            "objectives": self._objectives,
            "quantities": self._quantities,
            "requests": self._requests,
            "results": self._results,
            "traces": self._traces,
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
        """Compute a deterministic hash of engine state (sorted keys)."""
        parts = [
            f"constraints={self.constraint_count}",
            f"conversions={self.conversion_count}",
            f"intervals={self.interval_count}",
            f"objectives={self.objective_count}",
            f"quantities={self.quantity_count}",
            f"requests={self.request_count}",
            f"results={self.result_count}",
            f"traces={self.trace_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
