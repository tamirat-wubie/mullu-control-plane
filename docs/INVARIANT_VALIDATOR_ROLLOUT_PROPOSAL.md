# Invariant Validator Rollout Status

**Status:** infrastructure implemented, validators default-off. The registry,
dispatch checker, first built-in validator, governed write-path wiring, and
`PhiGov(graph)` default-constructor wiring are present. Strict production
enablement remains a governed follow-up.

**Companion documents:** `docs/USCL_v3.3_AMENDMENT_CANDIDATES.md` (A1),
`docs/PHI_CANONICAL_SPEC.md`, `docs/GOVERNANCE_GUARD_CHAIN.md`.

**Code touchpoints:** `mcoi/mcoi_runtime/substrate/cascade.py`,
`mcoi/mcoi_runtime/substrate/invariant_validators.py`,
`mcoi/mcoi_runtime/substrate/phi_gov.py`,
`mcoi/mcoi_runtime/app/routers/constructs/_governance.py`,
`mcoi/mcoi_runtime/app/routers/musia_governance_metrics/`.

---

## 1. Context

The edit gate validates a construct change in three phases:
`PhiGov.evaluate`, external validators, and cascade analysis. Cascade analysis
asks whether each dependent of the changed construct still holds its
invariants.

The original cascade checker was permissive:

```text
cascade.py :: default_invariant_checker(dependent, changed) -> True
```

That fallback is still preserved for unregistered construct types, but it is no
longer the only path. The cascade now supports:

```text
INVARIANT_VALIDATORS
register_invariant_validator(...)
unregister_invariant_validator(...)
clear_invariant_validators()
registry_dispatch_checker(dependent, changed)
```

The governed construct write path and the default `PhiGov(graph)` constructor
both route cascade checks through `registry_dispatch_checker`. With an empty
registry, behavior is identical to the permissive default. When a validator is
registered, the cascade can detect a dependent invariant violation and route it
to the A1 fail-closed escalation path.

Current net effect: the governance core is no longer registry-unaware. It can
detect registered per-type invariant violations while production strictness
remains opt-in and reversible.

---

## 2. Validator Contract

Per-type invariant validators replace the permissive default one construct type
at a time.

```text
InvariantChecker := (dependent: ConstructBase, changed: ConstructBase) -> bool
  returns True  iff dependent invariants still hold after changed changed
  returns False iff a dependent invariant is now violated
                 -> cascade auto-repairs if a repairer exists
                 -> otherwise ESCALATED -> PhiGov blocks fail-closed, per A1
```

Requirements:

```text
- PURE: no side effects, I/O, or mutation.
- TOTAL: returns for any (dependent, changed) of its type.
- CONSERVATIVE DEFAULT: an unregistered type keeps permissive behavior.
- DETERMINISTIC: same inputs produce the same verdict.
```

Dispatch is per dependent type:

```text
INVARIANT_VALIDATORS : dict[ConstructType, InvariantChecker] # opt-in
registry_dispatch_checker(dependent, changed)
PhiGov(graph) -> CascadeEngine(graph, invariant_checker=registry_dispatch_checker)
```

---

## 3. Opt-In Mechanism

```text
- Default-off: no type is strict until its validator is registered.
- Production behavior is unchanged while the registry is empty.
- Per-type enablement is governed Sigma-config, not a law change.
- A1 guarantees fail-closed reaction, so enabling a type cannot fail open.
- Worst-case validator error mode is a visible reject, reversible by disablement.
```

---

## 4. Rollout Order

Remaining strict validators should ship one construct type at a time:

```text
1. State          - referenced by Change, Causation, Transformation.
2. Transformation - composite invariants over parts.
3. Causation      - causal edge integrity.
4. Boundary       - boundary predicate integrity.
5. Pattern        - pattern reference integrity.
```

`Change` has the first inert built-in validator:
`mcoi/mcoi_runtime/substrate/invariant_validators.py ::
change_state_refs_are_states`. It validates that a `Change`'s
`state_before_id` and `state_after_id` references point to `State` constructs
when the referenced construct is the changed construct. It is not registered in
production by default.

---

## 5. Test Pattern

Reuse this cycle per type:

```text
1. Add the per-type validator and predicate-level tests.
2. Add a cascade + PhiGov integration test:
   violated invariant -> ESCALATED -> PhiGov FAIL.
3. Lock PASS behavior for non-violating changes.
4. Confirm PhiGov(graph) and the governed write path both use registry dispatch.
5. Run focused tests and workspace governance preflight before PR closure.
6. Enable the type in governed Sigma-config in a separate, revertible step.
```

Current proof points:

```text
mcoi/tests/test_invariant_validator_registry.py
mcoi/tests/test_invariant_validator_change_refs.py
mcoi/tests/test_cascade.py
mcoi/tests/test_phi_gov.py
```

---

## 6. Observability

Operators need counts of allowed, escalated, and rejected decisions plus a
bounded blocking category. The governed write path records:

```text
record_phi_gov_decision(...)
record_phi_gov_cascade_coverage(...)
```

These are dedicated PhiGov counters, separate from external guard-chain metrics,
so the overall PhiGov verdict is visible without double-counting the bridge's
`write` surface.

---

## 7. Optional Companion

The USCL v3.3 real-claim classifier can still ship as a pure, inert standalone
module if a consumer appears. It remains lower priority while no route, schema,
or derived-view surface consumes it.

---

## 8. Risks, Non-Goals, Sequence

```text
RISKS
  - Enabling a strict type changes governance outcomes.
  - Validator bugs can false-reject.

MITIGATIONS
  - Opt-in registry.
  - Default-off production behavior.
  - Pure, total, unit-tested predicates.
  - Visible fail-closed rejection path.
  - Reversible disablement.

NON-GOALS
  - No kernel identity or law mutation.
  - No new construct types.
  - Not the S^Phi derived-view layer.

SEQUENCE
  1. Observability counters: completed.
  2. Validator infrastructure: completed.
  3. Default PhiGov registry dispatch: completed.
  4. First built-in validator: Change state-reference validator exists, inert.
  5. Remaining validators: State, Transformation, Causation, Boundary, Pattern.
  6. Reality classifier only if a consumer appears.
```

---

**Bottom line.** A1 hardened how the gate reacts; the implemented registry and
default routing make the gate able to detect registered per-type violations.
The remaining governed work is strict enablement and additional validators, not
base infrastructure.
