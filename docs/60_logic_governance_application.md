# Logic Governance Application

Purpose: define how formal logic is applied across Mullu control-plane changes,
runtime governance, proof coverage, Phi traversal, and Mfidel substrate work.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS. This document binds
logic practice to existing repository surfaces; it does not replace
`PHI_CANONICAL_SPEC.md`, `GOVERNANCE_ARCHITECTURE.md`,
`40_proof_coverage_matrix.md`, or `27_mfidel_semantic_layer.md`.

Dependencies:
- `docs/PHI_CANONICAL_SPEC.md`
- `docs/GOVERNANCE_ARCHITECTURE.md`
- `docs/40_proof_coverage_matrix.md`
- `docs/27_mfidel_semantic_layer.md`
- `mcoi_runtime.core.invariants`
- `mcoi_runtime.governance`
- `scripts/proof_coverage_matrix.py`

Invariants:
- Logic is operational: every rule maps to a code, schema, test, proof, or
  documented halt condition.
- No undefined symbol enters a governed execution path.
- No state transition is accepted without a causal witness.
- No constraint violation is swallowed or converted into ambiguous success.
- Mfidel atoms remain atomic; overlay reasoning never decomposes fidel units.

---

## 1. Decision

Full logic discipline is mandatory for repository surfaces that affect:

1. Symbol identity.
2. Constraint admission.
3. Governance decisions.
4. Proof emission.
5. State transitions.
6. Memory or audit lineage.
7. Mfidel substrate or semantic overlay behavior.
8. Public protocol/schema contracts.
9. Runtime promotion, closure, or replay determinism.

Logic discipline is lighter, but still required, for operator documentation,
UI text, release notes, and non-executing examples. In those surfaces, the
minimum requirement is that symbols, constraints, and status claims remain
consistent with the governed runtime.

---

## 2. Repository Logic Object

Every governed change is modeled as:

```text
Change := <Distinction, Constraint, Ontology, Topology, Form,
           Organization, Module, Execution, Body, Architecture,
           Performance, Feedback, Evolution>
```

The change is valid only if it can produce:

```text
Proof := <symbol_set, constraint_set, affected_surfaces,
          transition_claims, witnesses, tests, open_issues>
```

The proof is complete when:

```text
forall symbol in symbol_set:
  symbol is defined

forall constraint in constraint_set:
  constraint is decidable or bounded-approximable

forall transition in transition_claims:
  transition has a named cause and witness

forall hard invariant affected:
  happy path, boundary path, violation path, and rollback or halt path
  are covered by test, schema validation, or explicit documented exception
```

---

## 3. Phi Traversal Applied To Code Change

| Phi stage | Required repository action | Reject condition |
|---|---|---|
| Distinction | Name the exact boundary: module, schema, route, storage table, doc, or test. | Boundary is vague or mixes unrelated surfaces. |
| Constraint | Classify hard, soft, and contextual constraints before editing. | Constraint conflict is unresolved. |
| Ontology | Define domain objects, identifiers, statuses, and proof terms. | New term appears without type or role. |
| Topology | Map dependencies and allowed call direction. | New call edge bypasses governance or proof surfaces. |
| Form | Define metrics, units, bounds, and error representation. | Numeric, temporal, or status claim has no bound. |
| Organization | State invariants and ownership. | Invariant has no owner or test surface. |
| Module | Preserve module responsibility and public contracts. | Module absorbs unrelated authority. |
| Execution | Describe state graph and termination behavior. | Transition can loop or succeed silently after failure. |
| Body | Define repair, rollback, and fail-closed behavior. | Failure leaves partial state without witness. |
| Architecture | Check layer placement against existing docs. | Code lands in a layer that should only orchestrate. |
| Performance | Verify deterministic, bounded, measurable behavior. | Performance claim lacks measurement or test. |
| Feedback | Add regression path for discovered failure. | Same failure can recur undetected. |
| Evolution | Record retained lesson, migration, or release impact. | Change cannot be audited later. |

---

## 4. Core Predicates

Use these predicates as the working logic vocabulary for implementation and
review.

| Predicate | Meaning | Primary witness |
|---|---|---|
| `defined(symbol)` | Symbol has declared identity, type, and boundary. | Contract, schema, dataclass, enum, or doc definition. |
| `governed(surface)` | Surface is covered by guard, policy, proof, or read-model exemption. | Proof coverage matrix or route test. |
| `atomic(fidel)` | Fidel is treated as one unit, without decomposition. | Mfidel tests and substrate contract. |
| `caused(transition)` | State transition has an explicit cause. | Proof receipt, audit entry, or witness object. |
| `bounded(error)` | User-visible error is constant or controlled. | Exact-string test or bounded formatter. |
| `deterministic(operation)` | Same input and context produce same output. | Replay test, injected clock, stable hash, or fixture. |
| `terminates(operation)` | Loop or recursion has a bound or decreasing measure. | Test, limit constant, or formal state graph. |
| `fail_closed(gate)` | Missing, invalid, or ambiguous input denies execution. | Guard test or boot-time validation. |
| `append_only(record)` | Audit or lineage record cannot be overwritten. | Hash-chain, ledger, or storage invariant. |
| `pool_safe(write)` | Persistent governance write is atomic across concurrent workers. | Atomic SQL primitive or store override test. |

---

## 5. Governance Law Mapping

| Law | Repository enforcement | Minimum proof |
|---|---|---|
| OCE | No undefined route, schema field, enum value, proof id, tenant id, or status term. | Type/schema validation and named docs. |
| RAG | Dependencies and relationships are explicit. | Import/call boundary review and topology note. |
| CDCV | State transitions carry cause and witness. | Receipt, audit entry, proof id, or test fixture. |
| CQTE | Constraints are decidable or bounded. | Validation predicate and violation test. |
| UWMA | Decisions are recorded with justification. | Change assurance artifact, release note, or witness. |
| SRCA | Recursion and loops terminate. | Bound, decreasing measure, timeout, or state graph. |
| PRS | Completed work has verifiable resolution trace. | Passing command, proof matrix check, or explicit gap. |

---

## 6. Surface-Specific Logic Rules

### 6.1 Governance package

Affected path: `mcoi_runtime/governance/`

Mandatory predicates:

```text
fail_closed(auth_gate)
bounded(user_error)
pool_safe(persistent_write)
append_only(audit_record)
caused(policy_decision)
```

Implementation rules:

1. Authentication-affecting defaults must be strict.
2. User-visible errors must not include caller-controlled values or backend
   exception details.
3. Persistent budget, rate-limit, audit, and tenant-gating mutations must use
   atomic write semantics.
4. Any new guard must define verdict values, rejection reasons, audit payload,
   and exact test assertions.
5. Orchestrators may consume governance decisions; they must not become hidden
   policy engines.

Violation handling:

```text
if governance_change lacks fail_closed proof:
  halt with invariant violation

if persistent write is read_then_write:
  reject until atomic primitive or bounded single-writer proof exists

if error leaks dynamic user input:
  reject until bounded formatter and exact-string test exist
```

### 6.2 Proof coverage matrix

Affected paths:

- `docs/40_proof_coverage_matrix.md`
- `scripts/proof_coverage_matrix.py`
- `tests/test_proof_coverage_matrix.py`
- `tests/fixtures/proof_coverage_matrix.json`

Mandatory predicates:

```text
governed(surface)
caused(action_proof)
defined(coverage_state)
append_only(audit_reference)
```

Rules:

1. Every externally callable mutating surface must have request proof and action
   proof unless it is explicitly documented as a read-model.
2. Every witnessed surface must name its runtime witness.
3. A surface cannot move to `proven` unless the machine witness and tests agree.
4. Open closure actions must be represented as explicit unresolved work, not
   hidden in prose.

### 6.3 Phi operator and UCJA pipeline

Affected paths:

- `mcoi_runtime/substrate/phi_gov.py`
- `mcoi_runtime/ucja/`
- `docs/PHI_CANONICAL_SPEC.md`
- `docs/04_policy_and_verification.md`

Mandatory predicates:

```text
defined(stage)
terminates(traversal)
caused(stage_transition)
deterministic(stage_result)
```

Rules:

1. Stage order is fixed unless a recorded governance exception names the
   skipped or reordered stage and why it remains sound.
2. A stage result must distinguish pass, fail, reclassify, and unknown when the
   implementation supports those proof states.
3. Unknown is not fail and not success; it must route to bounded halt,
   escalation, or reclassification.
4. Domain adapters may enrich stage logic; they must preserve the outer
   pipeline contract.

### 6.4 Mfidel substrate and overlay

Affected paths:

- `mcoi_runtime/substrate/mfidel/`
- `mcoi_runtime/core/mfidel_matrix.py`
- `docs/27_mfidel_semantic_layer.md`
- `schemas/universal_construct.schema.json`

Mandatory predicates:

```text
atomic(fidel)
defined(grid_position)
deterministic(lookup)
bounded(invalid_position_error)
```

Rules:

1. Fidel lookup is by atomic grid position or whole glyph identity.
2. No Unicode normalization, decomposition, recomposition, root-letter logic,
   or consonant/vowel split may enter runtime processing.
3. Semantic overlay may group artifacts by meaning, but it cannot redefine
   persistence identity or execution contracts.
4. Overlay similarity is advisory unless admitted by a typed governance rule.
5. Invalid grid coordinates must fail explicitly.

Violation handling:

```text
if implementation decomposes Ethiopic codepoint:
  reject change

if overlay output mutates typed operational identity:
  reject change

if approximate similarity controls execution without governance admission:
  reject change
```

### 6.5 Schemas and public protocol

Affected paths:

- `schemas/`
- `docs/52_mullu_governance_protocol.md`
- `schemas/mullu_governance_protocol.manifest.json`
- validation scripts under `scripts/`

Mandatory predicates:

```text
defined(field)
bounded(enum)
deterministic(serialization)
caused(protocol_change)
```

Rules:

1. Required fields must represent real runtime obligations.
2. Optional fields must state the condition under which absence is valid.
3. Enum expansion requires tests for acceptance, rejection, and documentation
   drift.
4. Public schemas cannot drift from examples, validators, and protocol
   manifest entries.

### 6.6 Runtime closure and promotion

Affected paths:

- `docs/37_terminal_closure_certificate.md`
- `docs/57_general_agent_capability_closure_manifest.md`
- `docs/58_general_agent_promotion_operator_runbook.md`
- `docs/59_general_agent_promotion_handoff_packet.md`
- related `scripts/validate_*` and `tests/test_validate_*`

Mandatory predicates:

```text
caused(closure_decision)
append_only(closure_witness)
defined(disposition)
fail_closed(promotion_gate)
```

Rules:

1. Closure cannot claim completion without terminal proof.
2. Accepted risk must name owner, scope, expiration or review condition, and
   compensating controls.
3. Promotion requires environment binding evidence and operator checklist
   validation.
4. Runtime promotion cannot depend on unverified local assumptions.

---

## 7. Test Logic Contract

Every new or changed test function for proof-critical code should carry at
least three assertions unless the test is a single-purpose exception-path guard
whose assertion is the raised violation.

Required coverage by change type:

| Change type | Happy path | Boundary path | Violation path | Rollback or halt path |
|---|---:|---:|---:|---:|
| Guard or policy | yes | yes | yes | yes |
| Persistent governance write | yes | yes | yes | yes |
| Schema | yes | yes | yes | contextual |
| Proof witness | yes | yes | yes | yes |
| Read-model route | yes | yes | yes | no mutation proof |
| Mfidel lookup | yes | yes | yes | explicit halt |
| Documentation-only | statement consistency | link validity | contradiction scan | status block |

Assertion pattern:

```python
def test_governed_transition_emits_causal_witness() -> None:
    result = run_transition(...)

    assert result.status == "accepted"
    assert result.proof_id.startswith("proof:")
    assert result.cause == "named-cause"
```

Violation pattern:

```python
def test_invalid_transition_fails_closed() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="bounded reason"):
        run_transition(...)
```

---

## 8. Change Execution Checklist

Use this checklist before editing a governed surface:

1. Distinction: name the exact files and runtime surfaces affected.
2. Constraint: list hard constraints and reject conditions.
3. Ontology: define new types, statuses, fields, routes, or symbols.
4. Topology: identify dependencies and forbidden bypass paths.
5. Form: define units, bounds, enum values, status states, and error shape.
6. Organization: name preserved invariants.
7. Module: confirm the target module owns the responsibility.
8. Execution: define state transitions and terminal states.
9. Body: define failure repair, rollback, or halt behavior.
10. Architecture: confirm layer placement against canonical docs.
11. Performance: define deterministic and bounded behavior.
12. Feedback: add regression tests or validation checks.
13. Evolution: update docs, release notes, or witness artifacts when needed.

Completion checklist:

1. Tests or validators executed.
2. Proof or witness updated when behavior changed.
3. Open issues listed explicitly.
4. Status block records completeness, invariants, and next action.

---

## 9. Halt Conditions

Halt rather than continue when any of these conditions is true:

1. A symbol, status, field, route, or proof term is undefined.
2. A hard constraint conflicts with another hard constraint.
3. A state transition lacks a cause or witness.
4. A failure path can silently succeed.
5. A public schema change lacks validator/test alignment.
6. A governance write is not atomic and affects shared runtime state.
7. A user-visible error leaks unbounded caller-controlled input.
8. A Phi traversal can recurse or loop without termination evidence.
9. Mfidel processing decomposes a fidel unit.
10. A completed task cannot produce a proof-of-resolution trace.

---

## 10. Proof-of-Resolution Stamp Template

Use this template for substantial governed changes:

```text
PRS:
  change_id:
  affected_surfaces:
  symbols_defined:
  constraints_enforced:
  invariants_preserved:
  tests_or_validators:
  witness_artifacts:
  rollback_or_halt_path:
  open_issues:
```

---

## 11. Operator Summary

Logic is fully applied when the repository can answer seven questions for the
change:

1. What symbol changed?
2. What constraint admitted or rejected it?
3. What state transition occurred?
4. What proof witnessed the transition?
5. What invariant was preserved?
6. What test or validator can reproduce the claim?
7. What halt path prevents unsafe ambiguity?

If any answer is missing, the change is incomplete.

STATUS:
  Completeness: 100%
  Invariants verified: logic-to-runtime mapping, governance law mapping, Phi traversal binding, proof coverage binding, Mfidel atomicity preservation, test contract, halt conditions, proof-of-resolution template
  Open issues: none
  Next action: apply this checklist to the next concrete governed code or schema change
