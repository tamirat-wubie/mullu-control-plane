"""Purpose: math / optimization / units runtime contracts.
Governance scope: typed descriptors for quantities, unit conversions,
    optimization objectives, constraints, solver requests / results,
    uncertainty intervals, optimization traces, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - float fields allow negative values (math quantities).
  - Optimization status flow is tracked deterministically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UnitDimension(Enum):
    """Physical or logical dimension of a measured quantity."""
    LENGTH = "length"
    TIME = "time"
    MASS = "mass"
    CURRENCY = "currency"
    TEMPERATURE = "temperature"
    DIMENSIONLESS = "dimensionless"


class OptimizationStatus(Enum):
    """Status of an optimization solver run."""
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    OPTIMAL = "optimal"
    BOUNDED = "bounded"
    UNBOUNDED = "unbounded"
    TIMEOUT = "timeout"


class ObjectiveDirection(Enum):
    """Direction of optimization."""
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class UncertaintyKind(Enum):
    """Kind of uncertainty representation."""
    POINT = "point"
    INTERVAL = "interval"
    DISTRIBUTION = "distribution"
    UNKNOWN = "unknown"


class QuantityValidation(Enum):
    """Result of validating a quantity."""
    VALID = "valid"
    OUT_OF_RANGE = "out_of_range"
    DIMENSION_MISMATCH = "dimension_mismatch"
    OVERFLOW = "overflow"


class SolverDisposition(Enum):
    """Final disposition of a solver execution."""
    SOLVED = "solved"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_any_float(value: float, field_name: str) -> float:
    """Validate that a value is a real number (int or float, not bool). Allows negative and inf."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _require_finite_float(value: float, field_name: str) -> float:
    """Validate that a value is a finite real number (rejects inf and nan)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{field_name} must be finite (got {v!r})")
    return v


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuantityRecord(ContractRecord):
    """A measured or computed quantity with unit and dimension."""

    quantity_id: str = ""
    tenant_id: str = ""
    value: float = 0.0
    unit_label: str = ""
    dimension: UnitDimension = UnitDimension.DIMENSIONLESS
    tolerance: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity_id", require_non_empty_text(self.quantity_id, "quantity_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "value", _require_finite_float(self.value, "value"))
        object.__setattr__(self, "unit_label", require_non_empty_text(self.unit_label, "unit_label"))
        if not isinstance(self.dimension, UnitDimension):
            raise ValueError("dimension must be a UnitDimension")
        object.__setattr__(self, "tolerance", require_non_negative_float(self.tolerance, "tolerance"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UnitConversion(ContractRecord):
    """A conversion factor between two units within a dimension."""

    conversion_id: str = ""
    tenant_id: str = ""
    from_unit: str = ""
    to_unit: str = ""
    factor: float = 1.0
    dimension: UnitDimension = UnitDimension.DIMENSIONLESS
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversion_id", require_non_empty_text(self.conversion_id, "conversion_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "from_unit", require_non_empty_text(self.from_unit, "from_unit"))
        object.__setattr__(self, "to_unit", require_non_empty_text(self.to_unit, "to_unit"))
        object.__setattr__(self, "factor", _require_finite_float(self.factor, "factor"))
        if not isinstance(self.dimension, UnitDimension):
            raise ValueError("dimension must be a UnitDimension")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationObjective(ContractRecord):
    """An optimization objective with direction and target."""

    objective_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE
    target_value: float = 0.0
    weight: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective_id", require_non_empty_text(self.objective_id, "objective_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.direction, ObjectiveDirection):
            raise ValueError("direction must be an ObjectiveDirection")
        object.__setattr__(self, "target_value", _require_finite_float(self.target_value, "target_value"))
        object.__setattr__(self, "weight", require_unit_float(self.weight, "weight"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MathOptimizationConstraint(ContractRecord):
    """A constraint on an optimization objective."""

    constraint_id: str = ""
    tenant_id: str = ""
    objective_ref: str = ""
    expression: str = ""
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", require_non_empty_text(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "objective_ref", require_non_empty_text(self.objective_ref, "objective_ref"))
        object.__setattr__(self, "expression", require_non_empty_text(self.expression, "expression"))
        object.__setattr__(self, "lower_bound", _require_any_float(self.lower_bound, "lower_bound"))
        object.__setattr__(self, "upper_bound", _require_any_float(self.upper_bound, "upper_bound"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SolverRequest(ContractRecord):
    """A request to run an optimization solver."""

    request_id: str = ""
    tenant_id: str = ""
    objective_ref: str = ""
    status: OptimizationStatus = OptimizationStatus.FEASIBLE
    max_iterations: int = 1000
    timeout_ms: int = 30000
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "objective_ref", require_non_empty_text(self.objective_ref, "objective_ref"))
        if not isinstance(self.status, OptimizationStatus):
            raise ValueError("status must be an OptimizationStatus")
        object.__setattr__(self, "max_iterations", require_non_negative_int(self.max_iterations, "max_iterations"))
        object.__setattr__(self, "timeout_ms", require_non_negative_int(self.timeout_ms, "timeout_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SolverResult(ContractRecord):
    """The result of a solver execution."""

    result_id: str = ""
    tenant_id: str = ""
    request_ref: str = ""
    status: OptimizationStatus = OptimizationStatus.FEASIBLE
    disposition: SolverDisposition = SolverDisposition.SOLVED
    objective_value: float = 0.0
    iterations: int = 0
    duration_ms: float = 0.0
    solved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "request_ref", require_non_empty_text(self.request_ref, "request_ref"))
        if not isinstance(self.status, OptimizationStatus):
            raise ValueError("status must be an OptimizationStatus")
        if not isinstance(self.disposition, SolverDisposition):
            raise ValueError("disposition must be a SolverDisposition")
        object.__setattr__(self, "objective_value", _require_finite_float(self.objective_value, "objective_value"))
        object.__setattr__(self, "iterations", require_non_negative_int(self.iterations, "iterations"))
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.solved_at, "solved_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintyInterval(ContractRecord):
    """An uncertainty interval for a quantity."""

    interval_id: str = ""
    tenant_id: str = ""
    quantity_ref: str = ""
    kind: UncertaintyKind = UncertaintyKind.POINT
    lower: float = 0.0
    upper: float = 0.0
    confidence: float = 0.95
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interval_id", require_non_empty_text(self.interval_id, "interval_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "quantity_ref", require_non_empty_text(self.quantity_ref, "quantity_ref"))
        if not isinstance(self.kind, UncertaintyKind):
            raise ValueError("kind must be an UncertaintyKind")
        object.__setattr__(self, "lower", _require_finite_float(self.lower, "lower"))
        object.__setattr__(self, "upper", _require_finite_float(self.upper, "upper"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OptimizationTrace(ContractRecord):
    """A single step in an optimization solver trace."""

    trace_id: str = ""
    tenant_id: str = ""
    request_ref: str = ""
    step: int = 0
    objective_value: float = 0.0
    feasible: bool = True
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "request_ref", require_non_empty_text(self.request_ref, "request_ref"))
        object.__setattr__(self, "step", require_non_negative_int(self.step, "step"))
        object.__setattr__(self, "objective_value", _require_finite_float(self.objective_value, "objective_value"))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a bool")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MathSnapshot(ContractRecord):
    """Point-in-time snapshot of math runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_quantities: int = 0
    total_conversions: int = 0
    total_objectives: int = 0
    total_constraints: int = 0
    total_requests: int = 0
    total_results: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_quantities", require_non_negative_int(self.total_quantities, "total_quantities"))
        object.__setattr__(self, "total_conversions", require_non_negative_int(self.total_conversions, "total_conversions"))
        object.__setattr__(self, "total_objectives", require_non_negative_int(self.total_objectives, "total_objectives"))
        object.__setattr__(self, "total_constraints", require_non_negative_int(self.total_constraints, "total_constraints"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MathClosureReport(ContractRecord):
    """Final closure report for math runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_quantities: int = 0
    total_objectives: int = 0
    total_requests: int = 0
    total_results: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_quantities", require_non_negative_int(self.total_quantities, "total_quantities"))
        object.__setattr__(self, "total_objectives", require_non_negative_int(self.total_objectives, "total_objectives"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
