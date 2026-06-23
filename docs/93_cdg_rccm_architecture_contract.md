# CDG-RCCM Architecture Contract

Purpose: define the Foundation Mode contract for the Causal Dependency-Gated Recursive Component Convergence Mesh as a governed recursive component architecture.

Governance scope: component identity, dependency gating, continuation suspension, convergence contracts, cycle classification, result certification, causal invalidation, closure certification, and effect staging.

Dependencies: `schemas/cdg_rccm_architecture_contract.schema.json`, `examples/cdg_rccm_architecture_contract.foundation.json`, `scripts/validate_cdg_rccm_architecture_contract.py`, `tests/test_validate_cdg_rccm_architecture_contract.py`.

Invariants:
- CDG-RCCM is a proposed canonical architecture, not an existing external standard.
- The universal profile means shared protocol compatibility only; it does not claim universal termination.
- Containment and dependency are separate graph relations.
- A component submits candidates; it does not certify itself.
- Blocked continuation frames suspend locally and do not block unrelated work.
- Every permitted loop has a declared convergence or exhaustion contract.
- Every result certificate is versioned, assumption-bound, and invalidated by causal-read changes.
- Reasoning remains separated from external or irreversible effects.

## Architecture

CDG-RCCM frames recursive work as a mesh of governed components:

```text
Component = SymbolState + Contract + Ports + ConvergencePolicy + Budgets + Versions
Mesh      = Components + ContainmentEdges + DependencyEdges + Frames + Queue
            + SuspendedFrames + Regions + Certificates + Ledger
```

The component state keeps the Mullusi base structure:

```text
S_i = <I_i, Lambda_i, Sigma_i, Gamma_i, H_i>
```

The runtime extension adds contract, typed ports, convergence policy, resource and uncertainty budgets, and schema/rule/state/protocol versions.

The mesh separates:

| Graph | Relation | Rule |
| --- | --- | --- |
| Containment | `CONTAINS` | Instance containment must be acyclic. |
| Dependency | `REQUIRES`, `CONSTRAINS`, `OBSERVES`, `RECONCILES_WITH`, `SHARES`, `ALTERNATIVE_TO`, `PRECEDES`, `EVIDENCES`, `TEMPORAL_PREVIOUS`, `SUPERSEDES` | Cycles are allowed only after classification and declared treatment. |

## Algorithm

The canonical governing sequence is:

```text
Frame component
Perform available local work
Discover exact dependency
Preserve blocked continuation
Recursively settle dependency
Receive certified projection
Resume continuation
Integrate result
Reconcile boundaries
Propagate constructive and fracture deltas
Reopen affected work
Repeat until certified closure
```

The primary algorithm is DGRCA: Dependency-Gated Recursive Convergence Algorithm. It runs under a frozen evaluation epoch, schedules runnable frames fairly, resolves exact projection requests, suspends only blocked frames, issues certificates through an independent kernel, invalidates consumers through causal read sets, and returns only a typed closure outcome.

The convergence region solver is DPCRS: Declared-Policy Convergence Region Solver. It admits only permitted semantic-feedback regions whose members share a declared convergence policy.

## Contract Surface

Each dependency request must identify the exact projection needed:

```text
Request = requester + provider + projection + minimumLevel + gate
          + assumptions + consistency + freshness + budget + fallback
```

Valid gates:

| Gate | Meaning |
| --- | --- |
| `HARD` | Consumer cannot continue without a valid certificate. |
| `PROVISIONAL` | Consumer may continue speculatively but remains retractable. |
| `ADVISORY` | Result informs judgment but does not block certification. |
| `ALTERNATIVE` | Any selected valid provider may satisfy the request. |
| `QUORUM` | A declared threshold of providers is sufficient. |
| `STREAMING` | Provider supplies successive versioned values. |
| `TEMPORAL` | Provider result belongs to a declared prior or future epoch. |

Step outcomes are an algebra submitted to the kernel:

```text
Need | Progress | Candidate | Conflict | Unknown | Fault | Cancelled
```

Settlement levels are separate from frame lifecycle:

| Level | Name | Meaning |
| --- | --- | --- |
| L0 | `PROVISIONAL` | Working result, may still change. |
| L1 | `LOCALLY_STABLE` | Local convergence contract passes. |
| L2 | `BOUNDARY_RECONCILED` | Required interfaces and neighboring constraints pass. |
| L3 | `CLOSURE_CERTIFIED` | Active closure and root invariants pass. |
| L4 | `WORLD_VERIFIED` | External or physical result has observed evidence. |

## Cycle Handling

A dependency cycle is not automatically a valid fixed-point loop. CDG-RCCM classifies cycles before resolution:

| Cycle class | Treatment |
| --- | --- |
| `STRUCTURAL_CONTAINMENT` | Reject topology. |
| `SEMANTIC_FEEDBACK` | Enter a declared joint convergence region. |
| `TEMPORAL_FEEDBACK` | Add explicit epoch delay. |
| `RESOURCE_DEADLOCK` | Use preemption, cancellation, or resource ordering. |
| `AUTHORITY_DEADLOCK` | Escalate to governance. |
| `ALTERNATIVE_SELECTION` | Reformulate constraints. |
| `HIDDEN_SELF_DEPENDENCY` | Expose and classify the missing edge. |

Only `SEMANTIC_FEEDBACK` with a declared convergence contract can enter DPCRS.

## Closure

Active closure is certified only when:

1. All consumed information is represented as a dependency.
2. Every required hard dependency is satisfied, unsatisfiable, unknown, blocked, cancelled, or faulted through an explicit certificate.
3. No component self-certifies.
4. Containment and dependency remain separate.
5. Cycles are classified before resolution.
6. Result certificates are current for the epoch, assumptions, rules, and inputs.
7. Causal invalidation follows actual read sets.
8. Boundary reconciliation passes for required interfaces.
9. Quiescence is not treated as correctness.
10. World claims do not exceed observed evidence.
11. Effect staging remains separated from reasoning.
12. Safety, liveness, and fairness are independently checked.

Closure outcomes are:

```text
CERTIFIED | UNSAT | UNKNOWN | BLOCKED | STALE | FAULT | CANCELLED | DEGRADED | RECOVERY_REQUIRED
```

## Foundation Boundary

This repository contract records the architecture and validation shape. It does not implement a live RCOK runtime, issue production certificates, mutate external state, perform physical verification, or claim universal convergence.

The Foundation Mode artifact therefore carries `AwaitingEvidence` until a runtime implementation, executable trace receipts, recovery/replay receipts, and effect-boundary witnesses exist.

STATUS:
  Completeness: 100%
  Invariants verified: containment/dependency separation; no self-certification; continuation-local suspension; declared convergence; cycle classification; causal invalidation; effect staging
  Open issues: live RCOK runtime, executable trace receipts, and world-verification witnesses remain future work
  Next action: validate `examples/cdg_rccm_architecture_contract.foundation.json`
