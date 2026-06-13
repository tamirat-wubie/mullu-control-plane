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

Objective metadata may also use a bounded expression:

```json
{
  "decision_variables": ["x", "y"],
  "linear_expression": "3*x + y",
  "variable_bounds": {"x": [0.0, 10.0], "y": [0.0, 10.0]}
}
```

When no `linear_terms` metadata is provided, constraint expressions can provide the linear terms and comparison:

```text
x + y >= 5
x - y <= 0
```

Supported expression grammar is intentionally small:

1. Variables: `x`, `machine_1`, `load2`.
2. Terms: `x`, `-y`, `3*x`, `0.5*y`.
3. Operators: `+`, `-`, `<=`, `>=`, `=`.
4. No parentheses, division, exponentiation, function calls, or dynamic evaluation.

The linear backend:

1. Requires finite variable bounds for every variable.
2. Supports up to four variables.
3. Enumerates feasible vertices deterministically.
4. Supports bounded integer and binary variables through explicit metadata.
5. Selects the minimum or maximum weighted linear objective.
6. Rejects malformed metadata with bounded messages.
7. Rejects unsupported expression syntax with bounded messages.

Integer metadata:

```json
{
  "decision_variables": ["x", "flag"],
  "linear_expression": "x + 5*flag",
  "integer_variables": ["x"],
  "binary_variables": ["flag"],
  "variable_bounds": {"x": [0.0, 10.0], "flag": [0.0, 1.0]}
}
```

Binary variables are also treated as integer variables and their effective
bounds are tightened to `[0, 1]`. Integer assignment enumeration is capped at
256 assignments. If a bounded integer or binary variable has no integer value
inside its effective bounds, the result is `INFEASIBLE`.

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
| Integer or binary bounds contain no integer assignment | `INFEASIBLE` | `FAILED` | `infeasible_integer_domain` |
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
8. Unsupported linear-expression syntax.
9. Unknown or duplicate integer/binary variable names.
10. Integer assignment surfaces above the deterministic cap.

The backend does not yet solve:

1. Nonlinear objectives.
2. Nonlinear constraint expressions.
3. Unbounded-domain linear programs beyond explicit `UNBOUNDED` classification.
4. Integer assignment surfaces above 256 assignments.
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
