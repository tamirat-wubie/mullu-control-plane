# Operational Math Loop

Purpose: turn the "Teach Mullu Core Math Principles" audit into bounded
execution machinery.

Governance scope: the loop applies F1-F10 as deterministic roles and controls.
It does not collect formulas for display. It converts math into constraints,
solvers, invariants, bounds, controllers, metrics, and verification gates.

## Architecture

| Surface | Responsibility |
| --- | --- |
| `OperationalMathPrinciple` | Captures one audit principle and its executable role/control requirements. |
| `OperationalMathTarget` | Declares the system surface that receives the loop. |
| `OperationalMathLoopEngine` | Applies missing requirements one principle per iteration. |
| `OperationalMathLoopIteration` | Records added roles, added controls, tension before/after, and proof refs. |
| `OperationalMathLoopResult` | Records saturation or remaining gaps without silent completion. |
| `OperationalMathReceiptStore` | Stores JSON loop receipts with append-only, idempotent receipt-id semantics. |
| `operational_math` observability source | Exposes store counts, latest receipt posture, and review signals through the server dashboard. |

## Algorithm

1. Freeze the target roles and controls.
2. Load the canonical F1-F10 catalog.
3. Compute missing roles and controls across the catalog.
4. Apply the highest-priority unresolved principle.
5. Record a proof reference and optional event-spine record.
6. Recompute tension.
7. Repeat until saturated or `max_iterations` is reached.
8. Return `SolvedVerified` only when no gaps remain.
9. Return `AwaitingEvidence` when the iteration budget is exhausted with gaps.

## F1-F10 Operational Mapping

| Fracture | Executable addition |
| --- | --- |
| F1 | Constraint, transformation, invariant, proof receipt. |
| F2 | Executable solver, bounded approximation, optimizer, verification gate. |
| F3 | Complexity bound and tractability classification. |
| F4 | Numerical stability and convergence/error bounds. |
| F5 | Decision rule and uncertainty model. |
| F6 | Adversarial guard and stress case. |
| F7 | Belief-space metric for advanced uncertainty routing. |
| F8 | Temporal model and termination control. |
| F9 | Resource bound and budget control. |
| F10 | Physical feasibility and conservation check. |

## Verification

Focused test contract:

```powershell
python -m pytest mcoi/tests/test_operational_math_loop.py mcoi/tests/test_operational_math_cli.py mcoi/tests/test_operational_math_receipt_store.py mcoi/tests/test_operational_math_observability.py
```

## Receipt CLI

Run the operational math loop and emit a JSON receipt:

```powershell
python -m mcoi_runtime.app.operational_math_cli --timestamp 2026-05-18T12:00:00+00:00
```

Persist the same receipt:

```powershell
python -m mcoi_runtime.app.operational_math_cli --receipt-path ../.tmp/operational-math-loop-receipt.json
```

Append the receipt into the operational math receipt store:

```powershell
python -m mcoi_runtime.app.operational_math_cli --store-path ../.tmp/operational-math-receipts.json
```

Persist a dashboard-safe projection for operator visibility:

```powershell
python -m mcoi_runtime.app.operational_math_cli --projection-path ../.tmp/operational-math-loop-projection.json
```

Projection behavior:

| Receipt state | Operator signal |
| --- | --- |
| `SolvedVerified` and no unresolved principles | `requires_operator_review = false` |
| `AwaitingEvidence` or unresolved principles | `requires_operator_review = true` with review signals |

Server wiring:

| Binding | Value |
| --- | --- |
| Dependency key | `operational_math_receipt_store` |
| Optional durable path | `MULLU_OPERATIONAL_MATH_RECEIPT_STORE_PATH` |
| Dashboard source | `operational_math` |

Expected proof outcome:

```text
SolvedVerified when max_iterations >= 10
AwaitingEvidence when max_iterations is exhausted before all gaps close
```
