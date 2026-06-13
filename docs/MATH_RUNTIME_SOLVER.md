# Math Runtime Solver

Purpose: document the first deterministic solver backend for the governed math runtime.
Governance scope: `MathRuntimeEngine.solve_solver_request` behavior, outcome classes, evidence records, and known limits.
Dependencies: `mcoi/mcoi_runtime/core/math_runtime.py`, `mcoi/mcoi_runtime/contracts/math_runtime.py`, and `mcoi/tests/test_math_runtime_engine.py`.
Invariants: solver execution is deterministic, bounded, one-dimensional, event-emitting, and explicit about infeasible or unbounded states.

## Scope

`MathRuntimeEngine.solve_solver_request(request_id, result_id=None)` solves the first bounded math case supported by the platform:

1. One objective.
2. One scalar decision value.
3. Zero or more interval constraints attached to the objective.
4. `MINIMIZE` selects the lower feasible bound.
5. `MAXIMIZE` selects the upper feasible bound.
6. `objective_value = decision_value * objective.weight`.

The solver records:

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

## Guardrails

The backend rejects:

1. Unknown request ids.
2. Requests already solved.
3. Missing or tenant-mismatched objective references.
4. `NaN` constraint bounds.

The backend does not yet solve:

1. Multi-variable linear programs.
2. Nonlinear objectives.
3. Integer or mixed-integer programs.
4. Constraint expressions beyond their explicit interval bounds.
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
