# USCL v3.3 Amendment Candidates — S^Φ Derived-View Layer

**Status:** PROPOSAL. NOT ratified. Each item below is a separate `Φ_gov`
amendment proposal requiring governance review. The locked kernel is
unchanged by this document.
**Companion documents:** `docs/PHI_CANONICAL_SPEC.md` (USCL v3.2 — FIXED
POINT), `docs/STATE_HASH_SPEC.md`, `docs/LEDGER_SPEC.md`,
`docs/ENGINEERING_PUZZLE_KERNEL.md`.
**Schema target:** `USCL v3.3` (additive; `phi2-gps-v2.2` unaffected).
**Provenance:** two-pass structural audit — first of the corrected S^Φ
verdict, then of these amendments themselves (second gate). Reject as
kernel replacement / accept as derived extension layer.

---

## 0. Scope and non-goals

The S^Φ verdict is accepted in **direction only**: S^Φ is a *derived
projection* over the locked substrate, never a new kernel. The verdict's
stronger operational claim — that the derived layer is *read-only / pure*
— does not hold as originally written. This document specifies the
minimal amendments that make that claim true.

```text
NON-GOALS (HARD):
  - No write to I.            write(I) remains FORBIDDEN.
  - No write to Lambda.       Lambda partitions are NOT added/replaced.
  - No new kernel field.      S := <I, Lambda, Sigma, Gamma, H> is locked.
  - No relocation of Psi.     Psi stays an operator, validated by Lambda_J.

CLASSIFICATION (per PHI_CANONICAL_SPEC amendment table):
  - All amendments fall under Delta_INFO, Delta_H, Delta_PI, Delta_LABEL.
  - None require Delta_Omega (kernel field) or Delta_Psi (law relocation).
  - Delta_REAL / Delta_WORLD are out of scope here (separate proposals).
```

**Governed parameters live in Σ, never in Λ.** Every new tunable this
document introduces (`B_ceiling`, per-class `eps_class` values, the
escalation ladder, the eviction/retention policy, the stale-retry count
`k`) is **governed configuration in Σ**, written only via `Φ_gov`. They
are NOT laws and are NOT written into `Λ`. The v3.2 *law*
`∀λ: decidable ∨ approximable(λ, ε)` stays in `Λ`; only the ε *values* are
Σ-config. This keeps the "No write to Λ" non-goal intact across all
amendments (a breach caught and fixed in the second-gate audit).

USCL v3.2 invariants reproduced verbatim and held INVARIANT by every
amendment below:

```text
write(I)            -> FORBIDDEN
write(Lambda)       -> governance + lineage required
write(Sigma)        -> validated Phi_gov only
Gamma subset Sigma  (governed by Lambda_interface)
H                   -> append-only lineage
forall s in W : s ~= S
Pi  orthogonal  <I, Lambda>
info in S  <=>  Lambda_inference |-_pi info     (UNBOUNDED |- )
forall lambda in Lambda : decidable(lambda) or approximable(lambda, eps)
```

---

## 1. Decision recap

```text
ProofState( S^Phi as replacement )        = Fail(governance_violation)
ProofState( S^Phi as derived extension )  = Pass(conditional)

Conditions to discharge "conditional" = A1..A5 + C1..C2 + G below
                                        (all hardened by second-gate audit).
Blocking-for-safety condition          = A1 (incomplete contradiction veto).
```

The derived view is the pure object produced by `D_Φ`; it is **not** a
member of the kernel tuple and carries **no** write authority:

```text
V^Phi_t[pi, B] := D_Phi(S_t, pi, B)
  = < anchor_t, Omega_d_t, L^Phi, Pi_t, pi_star, Gamma_d, H_d_t, B >
```

---

## 2. Amendments

Each amendment states: **Defect** (the fracture being closed),
**Amendment** (the normative change), **Class** (amendment category),
**Restores** (the invariant made true), **Obligation** (the proof/test a
ratifier must see).

### A1 — Edit-gate completeness under bounds  `[Delta_INFO]`  *(BLOCKING)*

**Defect.** The transition uses `C_t := Propagate^B(...)` then
`DetectFractures(C_t, ...)` on the **edit-validation** path. On bound
exhaustion this yields a *false negative*: a contradiction beyond `B`
passes the write gate. Silent incompleteness re-enters at the one gate
USCL cannot tolerate.

**Amendment.**

```text
1. Membership stays UNBOUNDED (kernel biconditional unchanged):
     info in S  <=>  Lambda_inference |-_pi info        (semantic)
   Operational exposure is a BOUNDED, LOGGED restriction of it:
     info exposed  =>  Lambda_inference |-^B_pi info     (operational)

2. Soundness obligation (stated, not assumed):
     forall B :  ( |-^B_pi )  subset  ( |-_pi )
   Bounded derivation introduces NO theorem absent from unbounded.

3. Edit gate ESCALATES, then fails closed at a finite ceiling (so a valid
   edit needing depth > d_max is NOT permanently rejected — fail-closed
   without escalation would be a self-DoS):
     Exhausted(B) on a HARD-invariant edit path
       =>  EscalateToGovernedReeval(B'),  B < B' <= B_ceiling
       =>  if still Exhausted at B_ceiling:
             Reject(Delta)  [or route to authority decision]
             /\ H ++ <edit_closure_cutoff, B_ceiling, DeltaHash, reason>
   B_ceiling is a finite governed Sigma-config constant => termination
   preserved. A HARD fracture unresolved by B_ceiling is treated as
   PRESENT. Partial-pass at the write gate is FORBIDDEN.

4. Grade scoping (InvariantGrade {Hard, Soft{eps}, Candidate}):
     Hard      -> fail-closed as in (3).
     Soft{eps} -> exhaustion logs a graded warning, NON-blocking.
     Candidate -> exhaustion logs, NON-blocking.
   Only HARD invariants block an edit on exhaustion; this stops soft-heavy
   but valid edits from being frozen out.
```

**Restores.** `Lambda_constraint |- Contradiction` veto is sound;
incompleteness at the write gate is impossible-to-be-silent (escalate ->
fail-closed + logged); valid edits within `B_ceiling` are not falsely
rejected.
**Obligation.** Test 1: a HARD contradiction reachable only at depth
`> B_ceiling` ⇒ `Reject` + logged `edit_closure_cutoff`, never an admitted
`Δ`. Test 2: a valid HARD edit needing `d_max < depth ≤ B_ceiling` ⇒
admitted via escalation (no false reject). Test 3: a `Soft{ε}` exhaustion
⇒ logged warning, edit NOT blocked.

### A2 — Deterministic bound (purity of the projection)  `[Delta_INFO]`

**Defect.** A wall-clock `τ_max` makes `|-^B_pi` a function of machine
load, so `D_Φ(S, π, B)` is not pure and audit replay diverges (same
inputs cut at different depths).

**Amendment.**

```text
B := < d_max, n_step, size_max, eps_class >

  d_max     : max derivation depth        (deterministic)
  n_step    : max logical inference steps  (deterministic)
  size_max  : max proof size               (deterministic)
  eps_class : per-law-class tolerance, a governed Sigma-config VALUE
              (Phi_gov-written, NOT caller-supplied, NOT a Lambda write)

  The semantic cutoff is defined SOLELY by (d_max, n_step, size_max).

  Determinism precondition: D_Phi enumerates Sigma_knowledge and candidate
  derivations in a TOTAL canonical order (docs/15_deterministic_
  serialization_policy.md). Without it, purity is broken by iteration
  order even with fixed step bounds.

  tau_kill (out-of-band wall-clock safety only) preserves purity:
    - firing ABORTS D_Phi, which RETURNS Aborted(partial) as a VALUE and
      still writes nothing (consistent with A3).
    - the CALLER (Phi^Phi_ext) logs <safety_halt> and flags the run
      non-replayable-by-design. tau_kill is NEVER a normal cutoff.
```

**Restores.** `D_Φ(S, π, B)` is a pure, total function; replay is
reproducible from `(S, π, B)` alone.
**Obligation.** Test: run the same `(S, π, B)` under artificial load;
assert byte-identical `V^Φ` and identical cutoff point.

### A3 — Projection purity boundary  `[Delta_INFO]`

**Defect.** Cutoff/reject/partial-output events were attributed to the
"read-only" view, but those append to `H` — kernel state. A layer that
writes `H` is not read-only.

**Amendment.** Split the two operators explicitly and assign all write
authority to exactly one of them.

```text
D_Phi : S x pi x B -> V^Phi
  - TOTAL, PURE. Reads I, Lambda, Sigma_t, H_t. Writes NOTHING.
  - Produces the view object only.

Phi^Phi_ext : (S_t, Input, G, pi, Xi, B) -> (S_{t+1}, ..., Output)
  - The ONLY operator permitted to append to H, and only via Phi_gov.
  - Emits ALL cutoff / reject / compact / partial-output events.

Scoping (does NOT override locked PHI_CANONICAL_SPEC Section 2.2):
  the kernel keeps its existing Phi_gov H-write call points (Phases 3,
  4.5, 10, 12, 12.5, Phi_multi, Phi_dyn). This amendment adds ONE rule,
  LOCAL to the S^Phi layer:
    within S^Phi:  D_Phi writes no H; any H-write arising from view
    derivation routes through Phi^Phi_ext under Phi_gov.
  It neither adds nor removes kernel H-writers. Deriving a view has zero
  kernel effect.
```

**Restores.** "Derived layer = read-only" holds *by construction*.
**Obligation.** Static check: `D_Φ` has no call path to any `H.append`
or `Φ_gov`. Property test: `hash(S_before) == hash(S_after)` across any
number of `D_Φ` calls.

### A4 — Compaction availability (not just integrity)  `[Delta_H]`

**Defect.** `e^min` keeps only `TraceRoot = MerkleRoot(e^full)`, with
`e^full` in an external store. Append-only INTEGRITY survives, but
content AVAILABILITY does not: replay needs the deltas inside `e^full`.
"Auditable/reversible" silently degrades to "tamper-evident-if-content-
survives," and the external store enters the TCB unspecified.

**Amendment.**

```text
1. Governance-critical events stay INLINE FOREVER (never root-only, never
   evicted):
     {reject, amend, freeze, safety_halt, compact, content_evict}
       ->  e^full in H.

2. Routine event content lives in a content-addressed store keyed by
   TraceRoot; only e^min + TraceRoot sit on the H spine.

3. Real scaling relief = SNAPSHOT-SUPERSESSION, not infinite retention.
   ("retention >= lineage = forever" saves no bytes; it relocates them.)
     - Snapshot_k := hash(Sigma_{t_k}, H_{0:t_k}) is a governed checkpoint.
     - Routine e^full content strictly BEFORE the latest snapshot MAY be
       evicted IF replay-from-Snapshot_k is proven sufficient (no live
       obligation needs pre-snapshot detail).
     - Eviction is governed and logged:
         H ++ <content_evict, range, root, snapshot_k, sufficiency_proof>
   Gov-critical e^full (point 1) is NEVER evicted.

4. Replay is honest about availability:
     Replay(t) = Load(nearest Snapshot <= t) + Apply(H spine to t),
     fetching routine e^full from the store as needed.
     Non-evicted content missing => ReplayUnavailable(range);
     never a wrong or silently-partial replay.
```

**Restores.** Append-only INTEGRITY *and* AVAILABILITY for
governance-critical lineage; any degradation is explicit and logged.
**Obligation.** Test: drop a routine `e^full` from the store; assert
`ReplayUnavailable` (not a corrupt replay) and that all
governance-critical events still replay from inline content.

### A5 — Exposure freshness + bound governance  `[Delta_PI + Delta_INFO]`

**Defect.** (a) A held `V^Φ_t` can be exposed after a governed
`Σ_t -> Σ_{t+1}` write revoked a permission (TOCTOU leak). (b) `B` is
caller-controlled: large `B` = resource exhaustion; loose `ε` =
reality-class laundering (e.g. `Simulated` exposed as `Inferred`).

**Amendment.**

```text
1. Freshness gate at exposure — O(1), NOT a full re-hash of H:
     anchor_t carries the kernel HEAD hash = (Merkle head of H per
     LEDGER_SPEC) + (Sigma state-hash per STATE_HASH_SPEC), NOT a re-hash
     of all of H (which grows with |H|). Before emitting Output_{pi,B}:
       require  anchor_t.head == kernel.head_now     (constant cost)
       mismatch => StaleView.

2. Stale handling is BOUNDED (no livelock under concurrent writes):
     on StaleView: re-derive at most k times (k = Sigma-config). If still
     stale => return Deferred(reason); NEVER spin, NEVER expose against a
     superseded substrate. Fail-closed.

3. Bound governance (B authenticated like pi):
     B <= min( B_max(pi), B_ceiling )
       B_max(pi) : per-principal budget -> lives in Pi (authorization).
                   Per-principal budgets are NOT laws; not a Lambda write.
       B_ceiling : single global hard ceiling -> Sigma-config (Phi_gov).
       eps_class : fidelity floor -> Sigma-config (Phi_gov), not caller-set.
     Malformed / over-budget B => Reject /\ H ++ <reject, reason>
     (same fail+log path as malformed pi).
```

**Restores.** `Pi orthogonal <I, Lambda>` preserved; permission decisions
are made against the current substrate at O(1) cost; stale handling cannot
livelock; bounds cannot be weaponized for exhaustion or mislabeling.
**Obligation.** Test (a): revoke a permission between derive and expose ⇒
`StaleView`, not a leak. Test (b): `B` above `min(B_max(π), B_ceiling)` ⇒
`Reject` + log. Test (c): drive continuous Σ-writes during exposure ⇒
`Deferred` after `k` retries, never an unbounded spin.

---

## 3. Secondary clarifications (close the two conditional passes)

These are not new fractures; they convert two "conditional pass" findings
into unconditional passes. Both are metadata-level and touch no kernel
field.

### C1 — Label map binding rules  `[Delta_LABEL]`

`L^Φ` is admissible as binding metadata over the existing `Λ` **iff**
both rules are stated as binding:

```text
(a) Dispatch always resolves on the underlying Lambda partition,
    never on the label. A label is a view, not an authority.
(b) Union-valued labels inherit the GLOBAL precedence lattice
    intra-label:
      edit validation:  Lambda_constraint > Lambda_edit > Lambda_inference
      output exposure:  Lambda_constraint > Lambda_inference > Pi
                                          > Lambda_interface
    A multi-partition label (e.g. Lambda_real, Lambda_val) has a defined
    conflict resolution; no nondeterministic dispatch remains.
(c) Per context, partitions ABSENT from that context's lattice are INERT
    for the label (Lambda_real's interface aspect is inert during edit
    validation; its edit/constraint aspects are inert during pure
    exposure). No label aspect is consulted without a rank in the active
    context.
```

No partition is added or replaced; `Λ` stays the locked 4-way union.

### C2 — `Λ_J` reversibility re-home  `[Delta_LABEL]`

`Reversible(J)` is an **edit-partition** property; it must not be
enforced inside judgment validation.

```text
ValidJudgment(J)  <=>  Traceable(J) /\ Auditable(J)
                       /\ Consistent(J, I, Lambda, Sigma_t, H_t)

Reversibility is enforced at the Phi_gov WRITE gate (edit partition),
where a Sigma-write's undoability actually matters — not at Lambda_J.
Lambda_J mapping stays {constraint, interface}.
```

Exposure irreversibility (you cannot un-disclose) is a *separate* concern,
owned by `Lambda_interface` NonLeak — not by `Reversible`. A judgment that
drives no Σ-write needs no reversibility check at all.

### G — Genesis of governed parameters (bootstrap)  `[Delta_INFO]`

The amendments add Σ-config parameters; the system cannot derive (there is
no defined `B`) until they exist. They are set at kernel init under the
DMRS GENESIS precedence (0), as Σ-config, amendable only via `Φ_gov`:

```text
GENESIS DEFAULTS (Sigma-config, Phi_gov-amendable):
  B_ceiling         : finite global derivation ceiling (> any B_max)
  B_max(role)       : per-role default budgets, held in Pi
  eps_class[class]  : per-law-class fidelity floors
  k_stale_retries   : bounded exposure re-derive count (A5)
  eviction_policy   : snapshot-supersession retention rule (A4)
  escalation_ladder : B' steps from default B up to B_ceiling (A1)

Until GENESIS config is committed, D_Phi is UNDEFINED and the S^Phi layer
is DISABLED — fail-closed, never default-open.
```

**Restores.** No undefined-budget bootstrap; the layer cannot come up
default-open with missing governance parameters.
**Obligation.** Test: boot with genesis config absent ⇒ S^Φ layer reports
DISABLED and refuses derivation, never falls open.

---

## 4. Net invariant ledger

```text
UNCHANGED (LOCKED — USCL v3.2 FIXED POINT):
  S := <I, Lambda, Sigma, Gamma, H>
  write(I) FORBIDDEN ; write(Lambda) gov+lineage ; write(Sigma) Phi_gov
  Gamma subset Sigma ; H append-only ; forall s in W : s ~= S
  Pi orthogonal <I, Lambda>
  info in S <=> Lambda_inference |-_pi info        (UNBOUNDED)
  forall lambda : decidable or approximable(eps)

ADDED (DERIVED LAYER ONLY — USCL v3.3 candidates; ALL params in Sigma):
  A1  edit gate ESCALATE-then-fail-closed (Hard only); +|-^B subset |-
  A2  deterministic B + canonical enumeration; D_Phi pure; tau_kill = abort
  A3  D_Phi writes no H; Phi^Phi_ext sole H-writer WITHIN S^Phi (not kernel)
  A4  snapshot-supersession eviction; gov-critical e^full inline-forever
  A5  O(1) freshness head-check; bounded k-retry; B_max in Pi, B_ceiling Sig
  C1  label binding: dispatch on partition; precedence inherit; inert OOC
  C2  reversibility at write gate; exposure-irrev is Lambda_interface
  G   genesis Sigma-config; S^Phi disabled until committed (fail-closed)

NOTE: every added parameter is Sigma-config (Phi_gov). NOTHING is written
to Lambda. The "No write to Lambda" non-goal holds across all amendments.
```

---

## 5. Decision (after second-gate audit)

The amendments were re-audited; eight second-gate fractures were found and
folded in above: self-DoS in A1; τ_kill/purity contradiction + enumeration
nondeterminism in A2; A3 over-claim vs locked §2.2; illusory scaling relief
in A4; full-rehash + livelock + B-placement in A5; out-of-context label
rank in C1; bootstrap gap (G); and a cross-cutting **Λ-write breach** in
A2/A5 — all governance parameters moved to Σ-config. Resulting disposition:

```text
A1  ACCEPT-CANDIDATE   Delta_INFO     BLOCKING until Test 1-3 green
A2  ACCEPT-CANDIDATE   Delta_INFO     needs docs/15 canonical-order tie-in
A3  ACCEPT-CANDIDATE   Delta_INFO     scoped; no conflict with locked kernel
A4  ACCEPT-CANDIDATE   Delta_H        needs snapshot/eviction proof harness
A5  ACCEPT-CANDIDATE   Delta_PI+INFO  needs O(1) head-hash + k-retry impl
C1  ACCEPT-CANDIDATE   Delta_LABEL    metadata-only; ready
C2  ACCEPT-CANDIDATE   Delta_LABEL    metadata-only; ready
G   ACCEPT-CANDIDATE   Delta_INFO     genesis precondition for all of A1-A5
```

**Verdict: ACCEPT S^Φ as a derived-extension layer over USCL v3.2**, gated
per-amendment. The kernel stays a FIXED POINT; verified that
`Targets(Δ) ∩ {Ι, Λ} = ∅` for every amendment. Ratification order:

```text
NOW       C1, C2          pure metadata; ratifiable on review
NOW       A3, G           definitional / precondition; ratifiable on review
GATED     A2, A4, A5      ratify after obligation harness is green
BLOCKER   A1              ratify only after Test 1-3 green; until then the
                          S^Phi layer MUST NOT be enabled on any edit path,
                          and per G is disabled-by-default at boot.
```

Per-amendment ratification gate (process unchanged):
```text
[ ] Filed as a separate Phi_gov proposal with lineage entry.
[ ] Confirmed Targets(Delta) ∩ {I, Lambda} = empty.   (verified: holds)
[ ] Class recorded (Delta_INFO | Delta_H | Delta_PI | Delta_LABEL).
[ ] Obligation test implemented and green.
[ ] PHI_CANONICAL_SPEC.md cross-reference added only AFTER ratification;
    this doc is the staging surface, not a kernel edit.
```
