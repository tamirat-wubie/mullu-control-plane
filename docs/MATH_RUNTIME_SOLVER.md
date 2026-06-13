# Math Runtime Solver

Purpose: document deterministic solver backends for the governed math runtime.
Governance scope: `MathRuntimeEngine.solve_solver_request` behavior, outcome classes, metadata contracts, evidence records, and known limits.
Dependencies: `mcoi/mcoi_runtime/core/math_runtime.py`, `mcoi/mcoi_runtime/contracts/math_runtime.py`, and `mcoi/tests/test_math_runtime_engine.py`.
Invariants: solver execution is deterministic, bounded, event-emitting, and explicit about infeasible or unbounded states.

## Scope

`MathRuntimeEngine.solve_solver_request(request_id, result_id=None)` supports two deterministic paths.

### Scalar Interval Solver

The scalar path runs when no linear metadata is present:

1. One objective.
2. One scalar decision value.
3. Zero or more interval constraints attached to the objective.
4. `MINIMIZE` selects the lower feasible bound.
5. `MAXIMIZE` selects the upper feasible bound.
6. `objective_value = decision_value * objective.weight`.

### Bounded Linear Solver

The linear path runs when the objective has `metadata["linear_coefficients"]` or a constraint has `metadata["linear_terms"]`.

Objective metadata:

```json
{
  "decision_variables": ["x", "y"],
  "linear_coefficients": {"x": 3.0, "y": 1.0},
  "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]}
}
```

Constraint metadata:

```json
{
  "linear_terms": {"x": 1.0, "y": 1.0}
}
```

For each linear constraint, `lower_bound <= sum(linear_terms[var] * var) <= upper_bound`.

The linear backend:

1. Requires finite variable bounds for every variable.
2. Supports up to four variables.
3. Enumerates feasible vertices deterministically.
4. Selects the minimum or maximum weighted linear objective.
5. Rejects malformed metadata with bounded messages.

Each solver records:

1. One `OptimizationTrace`.
2. One `SolverResult`.
3. Event-spine records for trace and result writes.
4. Metadata with solver id, bound envelope, objective direction, decision value, weighted objective value, and reason.

## Outcomes

| Condition | Status | Disposition | Reason |
| --- | --- | --- | --- |
| Combined lower bound is greater than upper bound | `INFEASIBLE` | `FAILED` | `infeasible_bounds` |
| `MINIMIZE` has no finite lower bound | `UNBOUNDED` | `FAILED` | `unbounded_minimize` |
| `MAXIMIZE` has no finite upper bound | `UNBOUNDED` | `FAILED` | `unbounded_maximize` |
| Direction has a finite optimum bound | `OPTIMAL` | `SOLVED` | `bounded_optimum` |
| Linear domain lacks finite per-variable bounds | `UNBOUNDED` | `FAILED` | `unbounded_linear_domain` |
| Linear constraints have no feasible vertex | `INFEASIBLE` | `FAILED` | `infeasible_linear_constraints` |
| Linear variable bounds contradict | `INFEASIBLE` | `FAILED` | `infeasible_variable_bounds` |
| Linear objective has a finite optimum vertex | `OPTIMAL` | `SOLVED` | `bounded_linear_optimum` |

## Guardrails

The backend rejects:

1. Unknown request ids.
2. Requests already solved.
3. Missing or tenant-mismatched objective references.
4. `NaN` constraint bounds.
5. Missing linear objective metadata when linear constraints are present.
6. Non-numeric or non-finite linear metadata.
7. Unknown or duplicate linear variable names.

The backend does not yet solve:

1. Nonlinear objectives.
2. Integer or mixed-integer programs.
3. Constraint expressions without explicit linear metadata.
4. Unbounded-domain linear programs beyond explicit `UNBOUNDED` classification.
5. Iterative numerical optimization.

## Verification

Focused test command:

```powershell
python -m pytest mcoi/tests/test_math_runtime_engine.py mcoi/tests/test_math_runtime_contracts.py mcoi/tests/test_math_runtime_integration.py -q
```

Broader math/cognition verification:

```powershell
python -m pytest mcoi/tests/test_math_runtime_contracts.py mcoi/tests/test_math_runtime_engine.py mcoi/tests/test_math_runtime_integration.py mcoi/tests/test_operational_math_loop.py mcoi/tests/test_operational_math_cli.py mcoi/tests/test_operational_math_observability.py mcoi/tests/test_operational_math_receipt_store.py mcoi/tests/test_cognition.py mcoi/tests/test_phi_gps.py mcoi/tests/test_phi_inceptadive_bridge.py tests/test_operational_math_control_plane_integration.py -q
```
