# 71 Intelligence Coordination Layer

Purpose: define the coordination layer that raises Mullu capability by improving representation, causal structure, constraint handling, method arbitration, world modeling, error correction, and adaptive planning.
Governance scope: Mullu symbolic intelligence planning, diagnosis, and execution control.
Dependencies: `docs/04_policy_and_verification.md`, `docs/13_temporal_plane.md`, `docs/14_coordination_plane.md`, `docs/16_world_state_plane.md`, `docs/17_meta_reasoning_plane.md`, `docs/22_goal_reasoning.md`.
Invariants: impossible states are eliminated before planning; uncertainty is preserved; method choice is explicit; world-model deltas are evidence-bound; every adaptive change has a proof record.

## Architecture

The intelligence coordination layer is not a larger knowledge store. It is the control surface that binds constraints, causality, uncertainty, world state, planning, method selection, and feedback into one governed episode.

| Module | Responsibility | Inputs | Outputs | Hard invariant |
|---|---|---|---|---|
| `ConstraintReasoningKernel` | Reject impossible or invalid states before planning | constraint set, world snapshot, goal descriptor | satisfiability report, blocked branches, propagated constraints | hard constraints with `Unknown` block execution |
| `CounterfactualEngine` | Evaluate intervention branches and dependency breaks | causal graph, baseline state, intervention | alternate state delta, breakpoints, reversible steps | baseline state is never mutated by simulation |
| `FailureReasoningKernel` | Search collapse paths before execution | plan, constraints, dependencies, hazards | failure map, edge cases, invariant-risk report | unresolved critical failure path blocks promotion |
| `MethodArbiter` | Select the reasoning method that fits the problem shape | problem signature, resource bounds, capability confidence | selected method, rejected methods, arbitration proof | no implicit method selection |
| `UncertaintyPropagator` | Preserve and accumulate uncertainty across dependencies | evidence confidence, contradictions, dependency graph | uncertainty envelope, degraded assumptions, escalation triggers | uncertainty is never overwritten by confidence language |
| `AbstractionController` | Move between micro, meso, and macro symbol scales | symbol mesh, goal scope, compression policy | active abstraction level, loss report, reversible mapping | abstraction must be reversible or explicitly lossy |
| `TemporalCausalTracker` | Track ordering, persistence, delayed effects, and decay | event history, temporal task state, causal graph | temporal dependency graph, stale-state markers | no fabricated timestamps |
| `WorldModelCoordinator` | Apply evidence-bound world-model deltas through governance | observations, verification results, contradiction records | proposed state delta, rejected delta list, snapshot reference | all world writes route through governance |
| `TradeoffEvaluator` | Compare competing constraints and resource limits | candidate plans, utility model, safety floor | Pareto report, selected compromise, rejected options | safety floor cannot be traded away |
| `SelfDiagnosisLoop` | Detect method mismatch, uncertainty growth, and reasoning drift | execution trace, verification result, resource usage | diagnosis report, replan recommendation, method score update | self-diagnosis recursion has bounded depth |

## Episode Contract

Every governed reasoning episode MUST materialize the following artifact:

```text
IntelligenceCoordinationEpisode:
  episode_id
  goal_id
  input_symbol_mesh_ref
  world_snapshot_ref
  active_constraints_ref
  causal_graph_ref
  uncertainty_envelope
  problem_signature
  method_candidates
  selected_method
  rejected_methods
  counterfactual_branches
  failure_map
  tradeoff_report
  execution_plan_ref
  diagnosis_report
  world_model_delta
  proof_record_ref
  terminal_outcome
```

Rules:

1. `episode_id` MUST be stable for the full episode.
2. `world_snapshot_ref` MUST reference an immutable world-state snapshot.
3. `selected_method` MUST reference a `MethodArbitrationProof`.
4. `rejected_methods` MUST include explicit reason codes.
5. `world_model_delta` MUST be empty unless verification produced evidence.
6. `terminal_outcome` MUST use the solver outcome taxonomy.

## Algorithm

```text
Input goal and current world snapshot
-> Distinguish episode boundary, goal boundary, and execution authority
-> Load admitted constraints and evidence-bound world state
-> Build problem signature
-> Propagate hard constraints
-> If any hard constraint is Unknown: block execution and request sensing
-> Generate method candidates from problem signature
-> Score methods against constraints, resources, and capability confidence
-> Select method through MethodArbiter
-> Simulate counterfactual branches for high-impact variables
-> Search failure paths and collapse conditions
-> Propagate uncertainty across dependencies
-> Evaluate tradeoffs without crossing safety floor
-> Produce execution plan
-> Execute only after policy gate allows action
-> Verify observed effects
-> Diagnose mismatch, drift, and resource use
-> Propose evidence-bound world-model delta
-> Commit or reject delta through governance
-> Emit proof record and terminal outcome
```

## Method Arbitration

The `MethodArbiter` chooses by problem structure, not by default preference.

| Problem signature | Preferred method family | Required proof fields |
|---|---|---|
| Boolean feasibility | SAT or constraint propagation | variables, clauses, unsatisfied constraints |
| Linear resource allocation | ILP or linear programming | objective, bounds, infeasible region |
| Ordered scheduling | temporal constraint propagation | tasks, deadlines, precedence graph |
| Symbol rewrite | rewrite system | rewrite rules, normal form, termination argument |
| Graph dependency | graph traversal or flow analysis | nodes, edges, cycles, cut points |
| Causal diagnosis | causal graph and intervention analysis | baseline graph, intervention, affected descendants |
| Local search landscape | bounded search, annealing, or evolutionary search | budget, neighborhood, acceptance rule |
| High uncertainty forecast | probabilistic model with confidence envelope | priors, evidence weights, uncertainty propagation |

Arbitration rules:

1. A method candidate MUST declare compatible problem signatures.
2. A method candidate MUST declare resource requirements.
3. A candidate whose requirements exceed available bounds MUST be rejected before scoring utility.
4. A candidate with degraded capability confidence MUST carry that degradation into the proof.
5. The selected method MUST be the highest-ranked candidate after hard rejections, not before.

## Constraint Reasoning Kernel

Constraint categories:

| Category | Examples | Blocking rule |
|---|---|---|
| Hard law | policy, safety, identity, authority | `Fail` or `Unknown` blocks |
| Hard physical | time, space, resource, conservation | `Fail` or `Unknown` blocks physical-world claims |
| Temporal | order, deadline, persistence, decay | invalid ordering blocks plan acceptance |
| Causal | dependency, precondition, effect chain | missing cause blocks claimed effect |
| Interface | schema, API contract, capability boundary | invalid contract blocks execution |
| Soft utility | cost, latency, preference, convenience | may degrade under policy |

Kernel output:

```text
ConstraintSatisfiabilityReport:
  report_id
  evaluated_constraint_ids
  satisfied_constraint_ids
  violated_constraint_ids
  unknown_constraint_ids
  propagated_dependencies
  contradiction_records
  blocked_branch_ids
  proof_state
```

## Counterfactual Reasoning

Counterfactuals are simulations over snapshots. They never mutate canonical world state.

```text
CounterfactualBranch:
  branch_id
  baseline_snapshot_ref
  intervention
  affected_entities
  affected_relations
  predicted_delta
  reversible_steps
  irreversible_risks
  confidence_envelope
```

Rules:

1. Every branch MUST reference the baseline snapshot.
2. Every intervention MUST identify the changed variable or relation.
3. Effects MUST be propagated through declared causal edges.
4. Branches with irreversible risk MUST be visible to planning and policy.
5. Counterfactual output MUST NOT be promoted to world state without observation.

## Failure-Oriented Reasoning

Failure reasoning runs before execution and after verification.

Pre-execution checks:

1. Hidden assumptions.
2. Missing preconditions.
3. Dependency fragility.
4. Contradiction emergence.
5. Invariant violation.
6. Cascading failures.
7. Resource exhaustion.
8. Temporal expiry.

Post-execution checks:

1. Observed effects differ from assumed effects.
2. Verification is inconclusive.
3. Resource use exceeds budget.
4. Method confidence decreases.
5. World model contradiction increases.

## Dynamic World Model

The world model is dynamic but not permissive. It evolves only by evidence-bound deltas.

```text
WorldModelDelta:
  delta_id
  source_episode_id
  source_evidence_ids
  prior_snapshot_ref
  proposed_entity_changes
  proposed_relation_changes
  proposed_confidence_changes
  contradictions_created
  contradictions_resolved
  governance_decision_ref
```

Rules:

1. Deltas MUST reference evidence.
2. Deltas MUST reference the prior immutable snapshot.
3. Deltas MUST not erase contradiction history.
4. Deltas rejected by governance MUST be logged with reason.
5. Identical accepted deltas over identical prior state MUST produce identical next snapshot hash.

## Self-Diagnosis

The self-diagnosis loop is the learning boundary for reasoning quality.

Diagnosis dimensions:

| Dimension | Signal | Action |
|---|---|---|
| Method mismatch | selected method failed despite valid inputs | reduce method confidence for matching signature |
| Uncertainty growth | uncertainty envelope expands across critical path | request sensing or escalate |
| Contradiction growth | new contradictions outnumber resolved contradictions | block world-model promotion |
| Resource overrun | budget exceeded before closure | replan with lower-cost method |
| Plan brittleness | many single-point dependency failures | add redundancy or narrow scope |
| Verification gap | execution passed but observation missing | mark `SolvedUnverified` or accepted-risk path |

Recursion rule:

```text
self_diagnose(trace, depth):
  if depth > 2:
    return BudgetUnknown
  produce diagnosis
  if diagnosis requires replan:
    return bounded_replan(depth + 1)
  return diagnosis
```

## Integration With Existing Planes

| Existing plane | Coordination-layer dependency |
|---|---|
| Policy and Verification | policy gates execution; verification supplies observed effects |
| Temporal Plane | schedules delayed effects, deadlines, and persistence checks |
| Coordination Plane | records delegation, handoff, merge, and conflict provenance |
| World State Plane | supplies immutable snapshots and accepts governed deltas |
| Meta-Reasoning Plane | supplies capability confidence and degradation status |
| Goal Reasoning Layer | supplies goals, plans, replanning records, and priorities |

## Project Discipline Mesh Scan

| Discipline | Lens finding | Gap or pass | Fix |
|---|---|---|---|
| Strategy/Product | Smartness is defined as coordination quality, not knowledge volume | Pass | Use coordination-layer metrics as capability milestones |
| Design/Research | Operator must see constraints, uncertainty, method choice, and failure map | Gap | Add operator-facing episode summary after first implementation |
| Engineering | Module boundaries and data contracts are explicit | Pass | Implement contract types before execution logic |
| Quality/Security | Hard constraints and uncertainty block unsafe execution | Pass | Add property tests for constraint blocking and snapshot immutability |
| Operations | Dynamic world-model deltas require replayable receipts | Gap | Persist episode receipts and rejected deltas in append-only lineage |
| Business/GTM | Capability story shifts from bigger memory to governed coordination | Pass | Use this as product positioning language after implementation evidence exists |

## Initial Implementation Order

1. Define data contracts for `IntelligenceCoordinationEpisode`, `ConstraintSatisfiabilityReport`, `MethodArbitrationProof`, `CounterfactualBranch`, and `WorldModelDelta`.
2. Implement `ConstraintReasoningKernel` with hard, soft, temporal, causal, interface, and resource constraints.
3. Implement `MethodArbiter` with explicit candidate rejection and proof output.
4. Implement `CounterfactualEngine` against immutable world snapshots.
5. Implement `SelfDiagnosisLoop` and connect it to verification results.
6. Add world-model delta admission through governance.

## Verification Plan

Required test lanes:

1. Happy path: satisfiable goal selects method, executes, verifies, and emits accepted world-model delta.
2. Hard constraint violation: execution is blocked and rejected delta is logged.
3. Unknown hard constraint: action is blocked with `AwaitingEvidence`.
4. Counterfactual isolation: simulated branch does not mutate baseline snapshot.
5. Method arbitration: infeasible method is rejected before utility scoring.
6. Uncertainty propagation: dependent plan confidence does not exceed weakest critical dependency.
7. Failure path detection: single-point dependency failure is reported before execution.
8. Recursion bound: self-diagnosis returns `BudgetUnknown` after depth limit.

## Status

STATUS:
  Completeness: 100%
  Invariants verified: [constraint-first pruning, explicit method arbitration, evidence-bound world-model deltas, uncertainty preservation, counterfactual isolation, bounded self-diagnosis]
  Open issues: [operator-facing episode summary not implemented, persisted episode receipt schema not yet defined]
  Next action: implement the coordination contracts and the `ConstraintReasoningKernel`
