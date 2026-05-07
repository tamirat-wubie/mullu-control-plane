# Engineering Puzzle Kernel

Purpose: specify engineering-as-governed-arrangement-search as a USCL-style
kernel artifact.

Governance scope: episode framing, immutable episode goals, observer binding,
filter-stack ordering, dual verification, append-only lineage, and Phi_gov
commitment.

Dependencies: MCOI runtime contracts and proof substrate.

Invariants:

1. `Goal_P` is immutable inside one episode.
2. `Goal_P` appears in episode invariants as `goal:<goal>`.
3. `H_P` is append-only.
4. `O_v` is part of the puzzle, not external parent authority.
5. L2 survival is evaluated before L5 optimization.
6. State commits require Phi_gov certification and dual verification witness.
7. Runtime closure is not claimed without observation evidence.

## Closed Law

```text
Engineering(P)
  := governed arrangement search over a frozen episode model.

Given puzzle P, find Sigma_P_prime such that:

1. Invariants I_P are preserved.
2. Rules Lambda_P are obeyed.
3. Interfaces Gamma_P remain valid.
4. Attempt and rejection lineage H_P is append-only.
5. Survival passes before optimization.
6. Commitment is admitted only through Phi_gov.
7. A full judgment envelope J_full is emitted.
```

## Kernel Object

```text
ENGINEERING PUZZLE P :=
<
  I_P,
  Lambda_P,
  Sigma_P,
  Gamma_P,
  H_P,
  Goal_P,
  M_e,
  O_v,
  Witness_P
>
```

| Symbol | Runtime field | Meaning |
| --- | --- | --- |
| `I_P` | `EngineeringPuzzle.invariants` | Episode invariants, including `goal:<goal>` |
| `Lambda_P` | `EngineeringPuzzle.rules` | Constraint, inference, interface, and edit rules |
| `Sigma_P` | `EngineeringPuzzle.state` | Current arrangement of pieces and resources |
| `Gamma_P` | `EngineeringPuzzle.interfaces` | Exposed contracts, APIs, diagrams, and claims |
| `H_P` | `EngineeringPuzzle.history` | Append-only events for attempts, rejections, observations, commits |
| `Goal_P` | `EngineeringPuzzle.goal` | Episode satisfaction predicate label |
| `M_e` | `EngineeringPuzzle.episode_model_hash` | Frozen model snapshot for this episode |
| `O_v` | `EngineeringPuzzle.observer` | Architect/observer node inside the puzzle |
| `Witness_P` | `EngineeringPuzzle.witness` | Dual model and observation evidence |

## Verdict Taxonomy

```text
SolvedVerified
SolvedUnverified
AwaitingEvidence
GovernanceBlocked
BudgetExhausted
ImpossibleProved
ModelInvalidated
SafeHalt
GoalMutated
AwaitingNewEpisode
```

`SolvedVerified` is emitted only when:

1. Phi_gov certification is present.
2. All filter levels pass.
3. Confidence is at or above the floor.
4. Dual verification witness exists.
5. Model/observation mismatch is within threshold.

## Goal Mutability Closure

```text
Goal_P is immutable inside one engineering episode.

Goal clarification:
  SatisfactionPredicate(Goal_old) == SatisfactionPredicate(Goal_new)
  => append GoalClarified
  => continue current episode without editing Goal_P

Goal mutation:
  SatisfactionPredicate(Goal_old) != SatisfactionPredicate(Goal_new)
  => append GoalMutated
  => close current episode
  => append EpisodeForked
  => create new episode with fresh M_e
```

This blocks silent proof corruption while still allowing bounded clarification.

## Universal Witness Rule

```text
R1:
  Optimization is admissible only after survival passes.

Formal:
  not Pass(L2_survival) => Block(L5_optimization)
```

Witnesses:

| Domain | Survival before optimization example |
| --- | --- |
| Software | Do not optimize API gateway caching before authorization boundaries survive. |
| Physical engineering | Do not reduce bridge material before load survival is proven. |
| Legal/compliance | Do not remove approvals before authority preservation is proven. |

## Observer Binding

```text
O_v :=
<
  observer_id,
  observer_invariants,
  observer_rules,
  assumptions,
  known_unknowns,
  risk_margins,
  fragile_points,
  interfaces,
  history_refs
>

O_v belongs to P.
O_v may propose Delta_arrangement.
O_v may not directly commit Delta_arrangement.
Only Phi_gov may certify commitment.
```

## Runtime Algorithm

```text
Phase 0: Frame episode
  Declare Goal_P as episode invariant.
  Declare I_P, Lambda_P, M_e, O_v, confidence floor, and budget.
  Append framing event to H_P.

Phase 1: Discover puzzle
  Enumerate pieces, missing pieces, unknowns, dependency mesh, contradictions.
  Block or sense when hard-safety unknowns exist.

Phase 2: Generate candidate
  Generate Sigma_candidate.
  Check affected invariants.
  Check required authority.
  Define rollback path.
  Define verification plan.

Phase 3: Filter candidate
  L0 feasibility
  L1 identity
  L2 survival
  L3 normative
  L4 interface
  L5 optimization
  L6 learning

Phase 4: Verify
  Lane A: model evidence.
  Lane B: observation evidence.
  Compare prediction and observation.
  If mismatch exceeds threshold, emit ModelInvalidated and preserve prior state.

Phase 5: Commit or halt
  Construct J_full.
  Commit only when confidence, filters, witness, and Phi_gov certification pass.
  Otherwise halt with explicit verdict.

Phase 6: Learn
  Append final event.
  Admit learning only when evidence qualifies.
  Never overwrite lineage.
```

## Implementation Anchors

| Artifact | Role |
| --- | --- |
| `mcoi_runtime.contracts.engineering_puzzle` | Immutable contracts and verdict taxonomy |
| `mcoi_runtime.core.engineering_puzzle_kernel` | Reference pure functions for goal, filter, witness, and commit behavior |
| `mcoi_runtime.core.engineering_puzzle_integration` | Event-spine facade for governed goal and candidate workflow calls |
| `mcoi_runtime.app.engineering_puzzle_control` | JSON-like control adapter for route-ready request and response envelopes |
| `mcoi_runtime.app.routers.engineering_puzzle` | Standalone FastAPI router for goal-delta and candidate-judgment endpoints |
| `mcoi_runtime.app.server` | Registers the engineering puzzle control surface and includes the router |
| `mcoi/tests/test_engineering_puzzle_kernel.py` | Runtime contract tests for the closure rules |
| `mcoi/tests/test_engineering_puzzle_integration.py` | Event-spine integration tests for facade workflow behavior |
| `mcoi/tests/test_engineering_puzzle_control.py` | Control-surface tests for payload validation and JSON-safe responses |
| `mcoi/tests/test_engineering_puzzle_router.py` | Standalone router tests for dependency wiring and HTTP error behavior |
| `mcoi/tests/test_engineering_puzzle_server.py` | Server-level test for dependency registration and route inclusion |

## Status

```text
STATUS:
  Completeness: specification encoded as runtime-facing contract
  Invariants verified:
    - immutable episode goal
    - observer node binding
    - survival before optimization
    - Phi_gov commitment gate
    - append-only history
    - dual verification witness requirement
  Open issues:
    - broader empirical universality witness set is not encoded
  Next action:
    - run targeted kernel tests and then expand integration binding where needed
```
