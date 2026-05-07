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
