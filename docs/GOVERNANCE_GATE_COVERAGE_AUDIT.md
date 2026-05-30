# Governance Gate Coverage Audit

**Status:** FINDINGS + upgrade path. Verified against live code (2026-05-23).
The one safe, additive instrument it recommends ships with it; the
behavior-changing upgrades are design-gated and listed for decision.
**Companion documents:** `docs/USCL_v3.3_AMENDMENT_CANDIDATES.md`,
`docs/INVARIANT_VALIDATOR_ROLLOUT_PROPOSAL.md`,
`docs/PHI_CANONICAL_SPEC.md`.
**Code audited:** `mcoi/mcoi_runtime/app/routers/constructs/_routes.py`,
`mcoi/mcoi_runtime/app/routers/constructs/_governance.py`,
`mcoi/mcoi_runtime/substrate/phi_gov.py`,
`mcoi/mcoi_runtime/substrate/cascade.py`.

---

## 1. Context

A1 (#743–#746) hardened how the edit gate *reacts* to a broken invariant
(fail-closed escalation, route-to-authority). The validator registry (#750)
and the first validator (#754) added the mechanism to *detect* them. This
audit asked the obvious next question: **do those mechanisms actually run on
the production write path?** The answer is mostly no — for structural reasons,
not bugs. This document records the verified findings and the upgrade path.

---

## 2. Findings (verified against live code)

### F1 — The dependency cascade never runs on creates (the live write path)

`_routes.py` performs every construct write via `_governed_write(..., "create",
...)` on a **freshly-constructed** object (new UUID). `_governed_write` runs
`phi.evaluate(...)` **before** `state.graph.register(...)`. In
`PhiGov.evaluate`, Phase 3 is gated by:

```python
if delta.construct_id in self._graph.constructs:   # phi_gov.py
    cascade = self._cascade.cascade(delta.construct_id)
    ...
```

For a create, the new construct is **not yet in the graph**, so Phase 3 is
**always skipped**. Consequences:

- The per-type invariant validators (#754) are **never invoked** on the live
  create path. Enabling one via the registry has **no production effect** as
  currently wired.
- The cascade half of A1 (#745 escalation-blocking, #746 depth-route) likewise
  does **not fire** on creates.
- The only governance that runs on a create is Phase 1 (Φ_agent filter — all
  permissive defaults) and Phase 2 (external guard chain — only if installed).

The mechanisms are correct (unit tests build graph state directly and exercise
them); they are simply not reached by live creates.

### F2 — Deletes bypass Φ_gov entirely

`delete_construct` and `delete_run` call `state.graph.unregister(...)`
**directly** — no `_governed_write`, no Φ_gov, no judgment, no lineage, no
cascade. A delete is the highest-blast-radius mutation (removing a construct
others depend on), and it is the **least** governed. `unregister` does refuse
when live dependents remain (a structural guard → HTTP 409), but that is not a
governed decision and is not recorded in lineage.

### F3 — The cascade direction is wrong for creates, right for deletes

`CascadeEngine.cascade(changed_id)` walks `dependents_of(changed)` — "who
depends on X; do they survive X changing?" That is the correct question for an
**update or delete**, not a create (a new construct's dependent set is empty).
The one mutation where the dependents-walk is the right semantics — **delete** —
is exactly the one (F2) that skips Φ_gov. For a *create*, the meaningful
question is the reverse: "does this new construct violate invariants w.r.t. the
constructs it depends on?"

### F4 — Deltas carry no content

`ProposedDelta(payload={"type", "tier"})` carries only metadata. Even where the
cascade runs, validators receive constructs from the graph, never the proposed
new value or a before/after diff — so *content* invariants are not expressible.
(Today the create routes hand-code referential-existence checks inline —
`referenced_state_not_found` — exactly the kind of invariant that belongs in a
validator but lives outside the gate because the gate does not fire there.)

---

## 3. Shipped with this audit (safe, additive)

**Cascade-coverage metric.** `_governed_write` now records, per write, whether
Phase 3 ran or was skipped, via a dedicated counter exposed as:

```
mullu_phi_gov_cascade_coverage_total{outcome="ran"|"skipped"}
```

A persistently high `skipped` ratio is the direct, fleet-level signal of F1.
This is purely additive (dedicated field; never enters the chain aggregates)
and changes no governance behavior — it makes the gap *visible* rather than
silent. (This instrument is exactly what would have surfaced F1 earlier.)

---

## 4. Upgrade path (design-gated — each needs a decision)

Ordered by leverage.

### U1 — Route deletes through Φ_gov  *(highest value)*

Add a `_governed_delete` → `phi.evaluate(delete-delta)` → cascade. This
**immediately activates the cascade, A1, and the validators with the correct
direction** (dependents-walk is right for deletes), and gives deletes a
judgment + lineage. It also closes F2 (ungoverned high-blast mutation).
**Contract change:** delete failure becomes a governed 403 + judgment shape
(today: structural 409). Needs sign-off.

### U2 — Forward-validation for creates

A create-time pass that validates the new construct against its `depends_on`
set (the reverse of the dependents-walk), so e.g. a new `Change` referencing a
non-`State` is rejected — what #754 checks, finally reachable. Either a new
cascade entry point (`validate_against_dependencies`) or a forward pass in
`_governed_write`.

### U3 — Payload-carrying deltas

Thread the proposed configuration (or a before/after pair) into `ProposedDelta`
so validators can check the *content* of a change, not only its structure.
Enables the real Candidate B / C invariants.

### U4 — Invariant grades through the cascade

Carry `InvariantGrade {Hard, Soft{ε}, Candidate}` on cascade steps so non-Hard
invariants warn instead of block (USCL v3.3 / A1 point 4, deferred).

### U5 — Batch atomicity

`PhiGov.evaluate` validates each delta independently against the current graph,
not against the hypothetical post-batch state; interdependent multi-construct
writes are not validated as a unit.

---

## 5. Recommendation

The high-leverage move is **U1 — govern deletes** — because it activates all
the already-built machinery (cascade, A1, validators) with correct semantics
and closes the ungoverned-delete hole in one well-scoped change. It is a
contract change, so it is design-gated, not autopilot.

Until U1 (or U2) lands, the cascade/validator work is correct-but-dormant on
the live path, and the new coverage metric quantifies exactly that.
