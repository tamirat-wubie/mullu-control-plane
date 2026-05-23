# Invariant Validator Rollout — Design Proposal

**Status:** PROPOSAL for review. No behavior change in this document; it
specifies the next safe build on top of the A1 edit-gate hardening.
**Companion documents:** `docs/USCL_v3.3_AMENDMENT_CANDIDATES.md` (A1),
`docs/PHI_CANONICAL_SPEC.md`, `docs/GOVERNANCE_GUARD_CHAIN.md`.
**Code touchpoints:** `mcoi/mcoi_runtime/substrate/cascade.py`,
`mcoi/mcoi_runtime/substrate/phi_gov.py`,
`mcoi/mcoi_runtime/app/routers/constructs/_governance.py`,
`mcoi/mcoi_runtime/app/routers/musia_governance_metrics/`.

---

## 1. Context — why this is the next build, and why now

The edit gate validates a construct change in three phases
(`PhiGov.evaluate`): Φ_agent 6-level filter, external validators (guard
chain), and **cascade analysis** (does each dependent of the changed
construct still hold its invariants?).

The cascade's invariant check is currently a **stub**:

```text
cascade.py :: default_invariant_checker(dependent, changed) -> True
  "Default is permissive — Φ_gov is expected to wire stricter per-type
   validators in for production use."
```

So today, when construct X changes, the cascade assumes **every dependent
of X is still fine**. The structural-integrity half of the governance core
does not actually detect violations yet.

**A1 made it safe to fix this.** Before the A1 work (#745, #746) a detected
violation would `ESCALATE` and then silently pass the gate (fail-open).
Now:
- an unresolved escalation is **rejected fail-closed** (`phi_gov.py`), and
- depth exhaustion **routes to authority** rather than opaque-rejecting
  (`cascade.py`).

That is the precondition for wiring real detection: A1 built the safety net;
real validators are what fall into it. Wiring validators **before** A1 would
have been dangerous; wiring them **now** is the natural, safe next step.

**Net effect of this rollout:** turn the governance core from *wired* into
*actually enforcing* — the single highest-leverage build available, and the
codebase's own stated follow-up.

---

## 2. The validator contract

Per-type invariant validators replace the permissive default, one construct
type at a time.

```text
InvariantChecker := (dependent: ConstructBase, changed: ConstructBase) -> bool
  returns True  iff dependent's invariants STILL HOLD after `changed` changed
  returns False iff a dependent invariant is now violated
                 (-> cascade auto-repairs if a repairer exists, else
                     ESCALATES -> Φ_gov blocks fail-closed, per A1)

REQUIREMENTS:
  - PURE: no side effects, no I/O, no mutation. A checker is a predicate.
  - TOTAL: must return for any (dependent, changed) of its type; never raise
    for ordinary inputs (a raise is a bug, not a verdict).
  - CONSERVATIVE DEFAULT: a type with NO registered validator keeps today's
    permissive behavior (returns True) — opt-in, never silently strict.
  - DETERMINISTIC: same inputs -> same verdict (so cascade results are
    replayable; aligns with docs/15 serialization policy).
```

Dispatch: a per-(dependent-type) registry, consulted by the cascade. Absent
an entry, fall back to the permissive default. This makes the rollout
**incremental and reversible** — turning a type on or off is a registry
change, not a kernel change.

```text
INVARIANT_VALIDATORS : dict[ConstructType, InvariantChecker]   # opt-in
CascadeEngine(invariant_checker = registry_dispatch_or_default)
```

---

## 3. Opt-in mechanism (safe by construction)

```text
- Default-OFF: no type is strict until its validator is registered AND the
  type is on the enabled set. Production behavior is unchanged on day one.
- Per-type enablement is governed Sigma-config (Phi_gov-written), NOT a law.
  (Same placement rule as the USCL v3.3 governed parameters.)
- A1 guarantees fail-closed reaction, so enabling a type cannot introduce a
  silent fail-open: worst case is an over-strict reject, which is visible
  (HTTP 403 + reason) and reversible (disable the type).
```

---

## 4. Rollout order (most-depended-on / highest-blast first)

Order by how many constructs depend on a type (a change to a
heavily-depended-on type is where missing invariant checks hurt most). From
the construct dependency graph (`test_cascade::_build_simple_graph` is a
representative shape):

```text
1. State          — referenced by Change, Causation, Transformation; the
                    most-depended-on substrate node.
2. Change         — referenced by Causation, Transformation.
3. Transformation — top of the chain; composite invariants over its parts.
4. Causation, Boundary, Pattern — lower fan-in; later.
```

Each type ships as its own PR, in this order, so blast radius is bounded and
attributable.

---

## 5. Test pattern (reuse the A1 harness-then-enable cycle)

The A1 work proved this cycle; reuse it per type:

```text
1. Add the per-type validator (pure predicate) + unit tests for the
   predicate alone (holds / violated cases).
2. Add a cascade+Φ_gov integration test: a change that violates the type's
   invariant -> ESCALATED -> Φ_gov FAIL (uses the A1 fail-closed path).
3. Lock current PASS behavior for non-violating changes (no over-reject).
4. Run the FULL suite (governance core; ~50.8k tests) before merge.
5. Enable the type in Sigma-config in a separate, revertible step.
```

---

## 6. Observability hook (scoped — has a real pitfall)

Operators should see the gate working: counts of allowed / escalated /
rejected decisions and the blocking reason. The metrics surface already
exists (`musia_governance_metrics/`), with a thread-safe
`REGISTRY.record(surface, tenant_id, allowed, blocking_guard, reason, ...)`.

**Finding (pitfall to avoid):** today `REGISTRY.record` is called only by the
external-guard **bridge** (`chain_to_validator`), NOT by the
`_governed_write` path. So the Φ_gov/cascade verdict — including the new A1
escalation/route signals — is **not recorded** unless an external chain is
installed. The obvious fix (add `record()` in `_governed_write`) would
**double-count** when a chain IS installed, because the bridge already
records on the same `write` surface.

```text
PROPOSED (needs care, NOT a blind add):
  - Record the OVERALL Φ_gov verdict once, in _governed_write, with a guard
    label drawn from the rejection-reason category:
        phi_agent_blocked_at:<L>  | cascade_rejected:<...>
        cascade_escalated:<n>_unresolved_invariant_violation
  - AVOID double counting: when the external bridge is the recorder for a
    write, _governed_write must NOT also record (or use a distinct surface /
    label). Resolve by reading musia_governance_bridge + the metrics tests
    (test_v4_20_prometheus_exposition) before wiring.
```

This is a small, additive change but the double-count subtlety means it
should be its own reviewed PR, not folded into a validator PR.

---

## 7. Optional companion — reality classifier (`C^B_real`)

The USCL v3.3 `Δ_REAL` classifier (`Physical / Observed / Inferred /
Simulated / Hypothetical / Invalid / Unresolved`, with ground + trace) can
ship as a **pure, inert standalone module** with tests — zero blast radius,
nothing calls it until a consumer exists. It has standalone honesty value
(never label a simulated claim as physical) and is reusable by the future
derived-view layer. **Optional / lower priority** precisely because it has no
consumer yet; include only if a near-term surface will label claim
provenance.

---

## 8. Risks, non-goals, sequencing

```text
RISKS
  - Enabling a strict type changes governance outcomes (edits that passed may
    now 403). Mitigated: opt-in per type, default-off, A1 fail-closed makes
    rejects visible+reversible, full-suite gate per PR.
  - Validator bugs (false reject). Mitigated: pure+total+unit-tested
    predicates; conservative default for unregistered types.

NON-GOALS
  - No kernel change (I / Lambda untouched; USCL v3.2 stays FIXED POINT).
  - No new construct types; validators are predicates over existing types.
  - Not the S^Phi derived-view layer (separate, design-gated decision).

SEQUENCE (recommended)
  1. Observability PR (own PR; resolve the double-count first).
  2. Validator infrastructure: registry + dispatch + default fallback (no
     type enabled yet — pure plumbing, behavior unchanged).
  3. Per-type validators in fan-in order (State -> Change -> Transformation
     -> ...), one PR each, enabled via Sigma-config in a follow-up step.
  4. Reality classifier only if a consumer appears.
```

---

**Bottom line.** A1 hardened how the gate *reacts*; this rollout makes it
*detect*. It is incremental, opt-in, default-off, and safe by construction
(A1 removed the fail-open). It needs a review sign-off on the validator
contract and the per-type enablement policy before any type is turned on —
this document is that review surface.
