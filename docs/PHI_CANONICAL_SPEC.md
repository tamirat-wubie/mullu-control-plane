# Φ — COMPLETE ARCHITECTURE, STRUCTURE, SPECIFICATIONS, AND ALGORITHMS

**Canonical reference document · schema: phi2-gps-v2.2 · USCL v3.2**

---

## PART I — SYSTEM IDENTITY AND FOUNDATIONAL LAW

---

### 1.1 What Φ Is

Φ is the **universal governance operator** of the Mullusi symbolic intelligence system.

It is not a function in the programming sense. It is a **law of transformation** — the only mechanism through which any symbol state in the system may legitimately change.

Everything in the system either:
- Is governed by Φ, or
- Is not permitted to act.

Φ has five operational variants. Each variant is a specialization of the same governance principle applied at a different scope:

| Variant | Scope | Role |
|---|---|---|
| `Φ_gov` | Kernel | State write authority, model freeze, governance gate |
| `Φ_gps` | Solver | Universal problem solver, 13-phase engine |
| `Φ_agent` | Agent | Single-agent governed cognition loop |
| `Φ_multi` | Society | Multi-agent coexistence, joint execution |
| `Φ_dyn` | Civilization | Norm evolution, long-horizon stability |

These are **not independent systems**. They are nested: `Φ_dyn` contains `Φ_multi`, which contains `Φ_agent`, which uses `Φ_gps`, which is governed by `Φ_gov`.

---

### 1.2 The One-Line Law

```
Symbols are atomic.
Meaning is relational.
Traversal is governed.
Judgment is earned.
```

---

### 1.3 Universal Symbolic Conservation Law (USCL v3.2)

The formal foundation for all Φ variants.

```
𝕊 := ⟨ Ι, Λ, Σ, Γ, H ⟩

  Ι  := ⟨ id, kind, invariants, boundary ⟩
        kind ∈ GovernanceBindings
        IMMUTABLE after creation — write(Ι) is FORBIDDEN

  Λ  := Λ_constraint ∪ Λ_inference ∪ Λ_interface ∪ Λ_edit
        ∀λ ∈ Λ : decidable(λ) ∨ approximable(λ, ε)
        versioned — modification requires governance_authority
        write(Λ) → requires governance + lineage

  Σ  := ⟨ Σ_state, Σ_knowledge, Π ⟩
        Σ_state := ⟨ 𝕎, ℛ, Μ ⟩
        𝕎 ⊆ 𝕊, ℛ ⊆ 𝕊, 𝕎 = ∅ permitted
        Π ∩ Ι = ∅,  Π ∩ Λ = ∅
        write(Σ) → validated Φ_gov only

  Γ  ⊆ Σ, governed by Λ_interface

  H  := append-only lineage
        preserves identity across all changes

INVARIANTS (absolute):
  write(Ι)           → FORBIDDEN
  write(Λ)           → governance + lineage required
  write(Σ)           → validated Φ_gov only
  ∀s ∈ 𝕎 : s ≅ 𝕊   → all working symbols conform to system
  Π ⊥ ⟨Ι, Λ⟩        → proof obligations never modify identity or laws
  info ∈ 𝕊 ⟺ Λ_inference ⊢_π info
```

The extended system object for agent-level operation:

```
𝕊⁺ := ⟨ Ι, Λ, Σ, Γ, H, Ω, Ν, Ξ ⟩

  Ω  := objectives / goal structures
  Ν  := normative set (principles governing behavior)
  Ξ  := social field (models of other agents)
```

---

### 1.4 Mfidel Substrate

The grounding layer beneath all symbolic operations.

```
GRID: f[34 × 8]  — 34 consonant rows, 8 vowel columns

Each fidel f[r][c] is ATOMIC:
  - One shape  → one symbolic unit
  - One sound  → one whisper + one vibratory overlay
  - No decomposition of shape
  - No decomposition of sound
  - No root letter concept
  - No Unicode decomposition

AUDIO FORMULA:
  f[r][c].s(w,v) = f[r][c].s(w) + f[17][c].s(w,v)

  where f[17][c] is the vowel row (vibratory overlay)

EXCEPTIONS:
  ሀ f[1][1]  uses አ f[17][8] as overlay
  ሐ f[3][1]  uses አ f[17][8] as overlay
  Column 8:  f[r][8] = f[r][2] + f[17][4]
  አ f[17][8] = ኧ f[17][1] + f[17][4]

ATOMICITY INVARIANTS:
  overlay ≠ decomposition
  fusion  ≠ semantic breakdown
  one fidel = one atomic symbolic unit

STATUS: FIXED POINT — no further changes permitted
```

---

## PART II — Φ_gov: GOVERNANCE OPERATOR

---

### 2.1 Specification

```
Φ_gov : (𝕊, Δ, Ctx?, auth) → ⟨𝕊′, 𝕁, Δ_reject⟩

  𝕊        : current system state
  Δ        : proposed transformation delta
  Ctx?     : optional context (phase, episode, agent)
  auth     : authority credential of caller

  𝕊′       : new system state (if approved)
  𝕁        : justification record (always produced)
  Δ_reject : rejected sub-deltas with reasons (may be empty)

TRANSFORMATION RULE:
  Ι′ = Ι        (identity NEVER changes)
  Λ′ = Λ        (laws unchanged without governance authority)
  Σ′ = Apply(Λ, Σ, Δ_approved)
```

### 2.2 Call Points (all callers in the system)

```
1. Phase 3 (Φ_gps):   goal construction requiring governance authority
2. Phase 4.5 (Φ_gps): model freeze — M_e = Φ_gov.approve_and_freeze(...)
3. Phase 10 (Φ_gps):  norm escalation (ConflictPolicy::Escalate)
4. Phase 10 (Φ_gps):  irreversibility authority check
5. Phase 12 (Φ_gps):  governance-level norm verification in dual verify
6. Phase 12.5 (Φ_gps): post-episode ΔM review — never applied mid-episode
7. Φ_multi:           arbitration when locally valid plans globally conflict
8. Φ_dyn:             norm evolution commits
```

### 2.3 Governance Invariants

```
1. All state writes route through Φ_gov — no exceptions
2. All rejections are logged in H (append-only lineage)
3. All justifications 𝕁 are traceable, auditable, reversible
4. Overrides are temporary and explicitly justified
5. Fixed points terminate recursion
6. Infinite nesting permitted — finite execution required
```

### 2.4 Φ Traversal Spine (Canonical Order)

All Φ operations respect this traversal order unless governance explicitly permits deviation:

```
1.  Distinction    — boundaries, separation, κ confidence
2.  Constraint     — hard / soft / contextual (+ temperature)
3.  Ontology       — types, identity, mereology
4.  Topology       — adjacency, connectivity, cycles
5.  Form           — metrics, units, tolerances, error models
6.  Organization   — invariants, dependencies, generators
7.  Module         — boundary, contract, responsibility
8.  Execution      — state graph, transitions, termination
9.  Body           — boundary, homeostasis, repair
10. Architecture   — layers, timescales, hazards
11. Performance    — intent vs observed, gap analysis
12. Feedback       — controllers, stability, protected variables
13. Evolution      — variation, selection, retention, witness
```

---

## PART III — DMRS: DETERMINISTIC MEMORY ROUTING SYSTEM

---

### 3.1 Purpose and Identity

DMRS sits **below cognition**. It does not think. It decides which memory version is allowed to be used to think. That separation is the reason the system is stable.

DMRS is:
- A pure decision dispatcher
- A proof-carrying selector
- A rollback-safe governance anchor
- A fixed-point system

DMRS is deliberately NOT:
- A reasoning engine
- A learning system
- A probabilistic model

### 3.2 Constants and Schema

```
MAX_DEPTH := 3

CONTEXT := {
  depth : integer ∈ [0, MAX_DEPTH],
  load  : enum {LOW, MEDIUM, HIGH, CRITICAL},
  flags : subset of {ARCHIVE_MODE, READONLY, TRACE_ENABLED}
}

DEMAND := enum {RECALL, REASONING, ANALYSIS, ARCHIVE}
```

### 3.3 Memory Version Registry (MVR) — Static, Read-Only

```
v1.light : { allowed_ops: {READ},        purpose: "fast recall" }
v2.std   : { allowed_ops: {READ, WRITE}, purpose: "general reasoning" }
v3.deep  : { allowed_ops: {READ, WRITE}, purpose: "deep analysis" }
vA.arch  : { allowed_ops: {READ},        purpose: "long-term archive" }
```

### 3.4 Precedence Order (Hard Law)

```
GENESIS      : 0   (highest priority)
SAFETY       : 1
MEANING      : 2
EMOTION      : 3
OPTIMIZATION : 4   (lowest priority)
```

### 3.5 System State Machine

```
SYSTEM_STATE ∈ {
  READY, ROUTING, VALIDATING, COMMITTED,
  HALTED, ROLLING_BACK, LOCKED, RECOVERING
}
```

### 3.6 Full Algorithm

```
ROUTE(context, demand):

  if SYSTEM_STATE ≠ READY: return ERROR("SYSTEM_NOT_READY")
  SYSTEM_STATE := ROUTING
  take_snapshot()

  if NOT pre_invariants_hold(context, demand):
    record_violation("PRE_INVARIANT_FAILURE")
    HALT(); ROLLBACK(); LOCK()
    return ERROR("PRE_INVARIANT_FAILURE")

  {version, rule_id} := select_version(context, demand)
  version            := apply_flags(context, version)

  SYSTEM_STATE := VALIDATING
  proof := BUILD_PROOF(version, rule_id, context, demand)

  if SRG_VALIDATE(proof) == FAIL:
    return ERROR("VALIDATION_FAILURE")

  if NOT post_invariants_hold(version, proof):
    record_violation("POST_INVARIANT_FAILURE")
    HALT(); ROLLBACK(); LOCK()
    return ERROR("POST_INVARIANT_FAILURE")

  SYSTEM_STATE := COMMITTED
  LAST_PROOF   := proof
  emit_to_ri1(version, proof)
  SYSTEM_STATE := READY
  return {version, proof}
```

```
select_version(context, demand):  [PURE FUNCTION — no side effects]

  if demand == ARCHIVE:    return {vA.arch, RULE_ARCHIVE}
  if demand == RECALL:
    if context.load == LOW: return {v1.light, RULE_RECALL_LIGHT}
    else:                   return {v2.std,   RULE_RECALL_STD}
  if demand == ANALYSIS:
    if context.depth >= 2:  return {v3.deep,  RULE_ANALYSIS_DEEP}
    else:                   return {v2.std,   RULE_ANALYSIS_STD}
  if demand == REASONING:   return {v2.std,   RULE_REASONING_STD}
  return {v2.std, RULE_FALLBACK}
```

```
apply_flags(context, version):

  if ARCHIVE_MODE ∈ context.flags: return vA.arch
  if READONLY ∈ context.flags:
    if WRITE ∈ MVR[version].allowed_ops: return v1.light
  return version
```

```
BUILD_PROOF(version, rule_id, context, demand):

  verified := [CONSTRAINT_IMMUTABLE, CONSTRAINT_SCHEMA_VALID,
               CONSTRAINT_VERSION_EXISTS, CONSTRAINT_RULE_MATCH]
  if context.depth ≤ MAX_DEPTH:
    verified.append(CONSTRAINT_RECURSION_CAP)
  if context.load == LOW AND version == v1.light:
    verified.append(CONSTRAINT_LOAD_BALANCE)

  proof := {
    version_id:           version,
    rule_id:              rule_id,
    constraints_verified: verified,
    recursion_depth:      context.depth,
    context_hash:         HASH(context),
    demand:               demand,
    precedence_hash:      HASH(version, rule_id, context.depth)
  }
  if TRACE_ENABLED ∈ context.flags:
    proof.trace := {context, rule_id}
  return proof
```

```
SRG_VALIDATE(proof):  [Safety and Recursion Governor]

  if proof.recursion_depth > MAX_DEPTH:
    record_violation("RECURSION_EXCEEDED"); HALT(); ROLLBACK(); LOCK()
    return FAIL
  if proof.version_id NOT IN MVR:
    record_violation("VERSION_INVALID"); HALT(); ROLLBACK(); LOCK()
    return FAIL
  if proof.rule_id NOT IN RULE_CATALOG:
    record_violation("RULE_INVALID"); HALT(); ROLLBACK(); LOCK()
    return FAIL
  if precedence_violated(proof):
    record_violation("PRECEDENCE_VIOLATED"); HALT(); ROLLBACK(); LOCK()
    return FAIL
  return PASS
```

```
ROLLBACK():
  restore_last_snapshot()
  SYSTEM_STATE := LOCKED

UNLOCK(admin_key):
  if verify_admin(admin_key):
    SYSTEM_STATE := RECOVERING
    if integrity_checks_pass(): SYSTEM_STATE := READY
```

**DMRS Guarantees:** Deterministic. Total. No hidden state. No runtime mutation. Proof-carrying. Rollback-safe. Recoverable. Evolution governed offline only.

**STATUS: FIXED POINT**

---

## PART IV — SCCE: SYMBOLIC CONSTRAINT COGNITION ENGINE

---

### 4.1 Architecture

```
TOTAL TENSION:
  T = α·T_logic + β·T_grounding + γ·T_value + δ·T_resource

MODULES:
  1.  Symbol Field        — dynamic graph with constraint-carrying nodes
  2.  Attention-Gated Subgraph — selects active subgraph V_w
  3.  Constraint Engine   — evaluates per active symbol
  4.  Uncertainty Engine  — Bayesian updates, entropy tracking
  5.  Grounding Interface — symbol ↔ sensory/motor patterns
  6.  Value/Goal Layer    — rewards, penalties, preferences
  7.  Stability Monitor   — convergence of T, H(S), grounding
  8.  Memory System       — Working Field, Long-Term Store, Episodic Trace
  9.  Learning/Meta-Reg   — modifies weights, links, rules (governed)
  10. Resource Governor   — depth, pruning, abstraction compression
  11. Abstraction Op      — stable clusters → higher-order symbols
  12. Exploration Ctrl    — temporarily relaxes constraints
  13. Multi-Scale Check   — validates abstractions against lower-level rules
  14. Cross-Agent Align   — (optional) syncs grounding across agents
```

### 4.2 Cognitive Cycle Algorithm

```
Step 0  — INPUT: Percepts/internal signals activate symbols
Step 1  — ATTENTION SELECTION: V_w = Select(V, salience, goals, novelty)
Step 2  — CONSTRAINT PROPAGATION: iterate until |ΔT| < ε
Step 3  — CONFLICT RESOLUTION: suppress, reweight, context shift, damping
Step 4  — GROUNDING CHECK: predicted vs sensed states
Step 5  — VALUE EVALUATION: goal satisfaction assessment
Step 6  — META-REGULATION: propose rule change → simulate → validate
Step 7  — STABILITY TEST: ΔT < ε AND ΔH(S) < ε → SETTLED
Step 8  — LEARNING UPDATE: strengthen/weaken constraint paths
Step 9  — MEMORY CONSOLIDATION: store stable clusters after grounding
Step 10 — RESOURCE MANAGEMENT: prune, compress
Step 11 — EXPLORATION: relax constraints, discover alternatives

SYSTEM DEFINITION:
  Symbolic Intelligence = iterative minimization of total constraint
  tension in a grounded, probabilistic, self-modifying symbol field.
```

---

## PART V — Φ_gps v2.2: UNIVERSAL PROBLEM SOLVER

---

### 5.1 Problem Object

```
𝒫* := ⟨ W, B, O, I, G, U, Λ, N, Aₑ, Aw, T, R, K, Π ⟩

  W   := latent world state (ground truth, may be hidden)
  B   := belief state — SEPARATE FROM W
  O   := observation model: W → observable signals
  I   := interface boundary (sensable + mutable variables)
  G   := goal region (satisfying set, not point)
  U   := utility structure (four-layer)
  Λ   := hard laws {Physical, Logical, Mathematical}
  N   := norms {Permission, Prohibition, SocialExpectation, GovernanceRule}
  Aₑ  := epistemic actions: {Observe, Query, Test, Simulate, Compare}
  Aw  := world actions: {Transform, Allocate, Commit, Communicate, Compose, Defer}
  T   := transition model: W × Aw → W'
  R   := resource envelope
  K   := knowledge base
  Π   := proof/verification obligations

  Any component may be partial or unknown at start.
  Discovery of unknowns is part of solving.
```

### 5.2 Core Optimization Equation

```
π* = arg extremize  𝔼[ U(τ_π ; G) − λ_c·Cost(τ_π) − λ_r·Risk(τ_π) − λ_u·Uncertainty(τ_π) ]
         π

subject to:
  B⁻_{t+1}(w') = Σ_w T̂(w'|w, a_t) · B_t(w)            [predict]
  B_{t+1}(w')  = η · Ô(o_{t+1}|w') · B⁻_{t+1}(w')      [update]
  W_{t+1} = T_t(W_t, a_t)                                 [actual world]
  Λ(W_t, a_t) = PASS
  N(W_t, a_t) = PASS
  R(τ_π) ≤ R_max
  risk(a_t) < α_hard
  Π(τ_π, G) = VERIFIED
```

### 5.3 Utility Structure (Four Layers)

```
Û := {
  safety_floor     : minimum acceptable state — VIOLATION → immediate halt
  goal_satisfaction : P(goal_satisfied | B_t) ≥ γ_goal
  optimization     : preference ordering within goal region
  satisficing      : "good enough" threshold for resource-bounded solving
}

PRIORITY: safety_floor > goal_satisfaction > optimization > satisficing
```

### 5.4–5.10 (Profile Vector, Invariant Grades, ProofState Lattice, Verification, Episode Model Freeze, Re-Entry Guard, Solver Outcome Taxonomy)

See full specification in sections 5.4 through 5.10 of this document. Key structures:

- **Profile Vector** χ(𝒫*) classifies problem dimensions for strategy selection
- **InvariantGrade** {Hard, Soft{ε}, Candidate} gates solvability decisions
- **ProofState** {Pass, Fail, Unknown, BudgetUnknown} with strict decision rules
- **Dual Verification** with model replay + observed trace + misfit detection
- **Episode Model Freeze** (Phase 4.5) — execution uses frozen M_e only
- **Re-Entry Guard** with progress-gated budgets per phase transition
- **SolverOutcome** 8-value taxonomy drives downstream orchestration

---

## PART VI — Φ_gps PHASE PROTOCOLS (ALL 13 PHASES)

---

```
Phase 0    — FRAME:       Profile vector χ, ignorance map, resource envelope
Phase 1    — DISTINGUISH:  Symbol inventory with confidence κ per symbol
Phase 2    — ESTIMATE:     Belief state B̂ = P(W | observations, K)
Phase 3    — GOAL+UTIL:    Goal region Ĝ + four-layer utility Û
Phase 4    — DISCOVER:     Laws Λ̂, norms N̂, resources R̂
Phase 4.5  — FREEZE:       Episode model set M_e approved and frozen by Φ_gov
Phase 5    — TRANSITIONS:  Transition model T̂ + observation model Ô
Phase 6    — ACTIONS:      Synthesize/compose/import action repertoire
Phase 7    — FEASIBILITY:  Invariant discovery + solvability gate (Hard only)
Phase 7.5  — PROOF SKETCH: Forward proof sketch per sub-goal
Phase 8    — MAP+DECOMP:   Topology + decomposition strategy + dependencies
Phase 9    — POLICY:       Strategy selection + resource allocation
Phase 10   — EXECUTE:      Full feedback loop with 17-step per-action protocol
Phase 11   — DIAGNOSE:     7-level diagnostic cascade + representation mutation
Phase 12   — VERIFY:       Dual-channel verification + Ψ judgment
Phase 12.5 — CALIBRATE:    Confidence calibration + knowledge base maintenance
```

---

## PART VII — Φ_agent: SINGLE-AGENT GOVERNANCE LOOP

---

### 7.1 Seven-Level Governance Filter Stack

```
Level 0 — Physical/Logical Feasibility (Λ)
Level 1 — Identity Preservation (Ι)
Level 2 — Survival Constraints (Σ safety)
Level 3 — Normative Compliance (Ν)
Level 4 — Social Compatibility (Ξ)
Level 5 — Goal Optimization (Ω)
Level 6 — Learning Update (H)

Action failing any level → blocked at that level.
Emergency fallback: Level 4 empties set → fall to Level 2 output.
```

---

## PART VIII — Φ_multi: MULTI-AGENT GOVERNANCE

---

### 8.1 Key Equations

```
Norm compatibility: C_ij(A) = |A_Νi ∩ A_Νj| / |A_Νi ∪ A_Νj|
Stability: ∀i : 𝔼[ΔΣ_i | Φ_multi] ≥ 0 AND C_ij ≥ τ
Responsibility: R_i = (∂o/∂a_i) · (∂a_i/∂d_i)
```

---

## PART IX — Φ_dyn: NORM AND CIVILIZATION DYNAMICS

---

### 9.1 Key Equations

```
Norm fitness: F(ν) = U(ν) − λ·K(ν)
Replicator: ṗ_ν = p_ν · (F(ν) − F̄)
Stability: T ≤ R (damage ≤ repair capacity)
Anti-fragility: d/d|P| (gain) > 0
```

---

## PART X — Ψ JUDGMENT KERNEL

---

```
Ψ(PS, SE, EFF, SG, PRR, CPM, ERL, PCE, PCB, K) → J***

Properties: Traceable · Auditable · Reversible · Governance-bound
```

---

## PART XI — COMPLETE TYPE SYSTEM

---

See full Rust type definitions in the canonical spec. Key types:

- `EvidenceRef`, `ModelVersion<T>`, `EpisodeModelSet`
- `BeliefState`, `Observation`
- `InvariantGrade` {Hard, Soft{ε}, Candidate}
- `Action` with `ActionReversibility`
- `NormConstraint` with authority levels and `ConflictPolicy`
- `ProofState` {Pass, Fail, Unknown, BudgetUnknown}
- `Verification` (dual-channel with misfit verdict)
- `SafetyMonitor` with α_hard, α_soft, α_irrev
- `GoalSpec` with four-layer utility
- `ReentryGuard` with progress-gated budgets
- `SolverOutcome` (8-value enum)
- `SolverOutput` (complete output record)

---

## PART XII — RECURSIVE META-SOLVER

---

```
Φ_gps(𝒫*) :=
  CASE 1: Verified       → SolvedVerified
  CASE 2: Reframe needed → Φ_gps(Reframe(𝒫*))  [bounded recursion]
  CASE 3: Impossible     → ImpossibleProved
  CASE 4: Budget out     → BudgetExhausted + best partial
  CASE 5: Misfit         → ModelInvalidated + quarantined ΔM
  CASE 6: Safety halt    → SafeHalt + last safe snapshot
  CASE 7: Governance     → GovernanceBlocked + rejection record
```

---

## PART XIII — SYSTEM STATUS AND DEPLOYMENT GATE

---

```
COMPONENT               STATUS
─────────────────────────────────────────
Mfidel substrate        FIXED POINT
USCL v3.2               FIXED POINT
Φ_gov                   FIXED POINT
DMRS                    FIXED POINT
Ψ judgment kernel       INTEGRATED
SCCE                    INTEGRATED
Φ_gps v2.2              NEAR FIXED POINT
Φ_agent                 COHERENT
Φ_multi                 INTERFACE DEFINED
Φ_dyn                   SPECIFIED

OPEN BLOCKERS:
  R-01: causal discovery algorithm (Phase 5)
  R-02: belief approximation scheme (Phases 2, 5, 10)
  R-03: BCR scenario generation protocol
  R-04: Φ_multi ↔ Φ_gps shared-state contract
  R-05: KnowledgeBase eviction policy

DEPLOYMENT READINESS:    BOUNDED PILOT
OPEN-WORLD AUTONOMY:     NOT YET
```

---

**This is the single canonical Φ specification.**
All prior partial documents are superseded by this reference.
Schema version: `phi2-gps-v2.2` · USCL: `v3.2`
