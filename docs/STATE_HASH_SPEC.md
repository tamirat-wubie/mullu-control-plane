# State Hash Specification — v1

**Status:** Stable contract. Breaking changes require schema version bump.
**Companion documents:** `docs/LEDGER_SPEC.md`, `docs/MAF_RECEIPT_COVERAGE.md`
**Schema version:** `1`

## Purpose

`TransitionReceipt.before_state_hash` and `after_state_hash` are the receipt
fields that bind the receipt to the entity's state at the moment the
transition was certified. `MAF_RECEIPT_COVERAGE.md` describes them as
"SHA-256 hashes of pre/post state" but does not specify what gets hashed.

This document is the canonical specification of the state-hash content
layout. **The Python implementation in
`mcoi/mcoi_runtime/core/proof_bridge.py::_state_hash` follows this spec,
not the other way around.** Future refactoring of state-hash construction
must preserve the byte-level layout described here, or bump the schema
version.

This is the companion to `LEDGER_SPEC.md`'s entry-hash specification:
that document specifies how audit-ledger entries are content-addressed;
this document specifies how transition-receipt state inputs are
content-addressed.

## Hash function

`SHA-256` (FIPS 180-4). All hashes are 64-character lowercase hexadecimal.

## Canonical state-hash content layout (v1)

`state_hash` is computed as:

```python
content = f"{state}:{entity_id}:{timestamp}"
state_hash = sha256(content.encode()).hexdigest()
```

**Field separator:** ASCII colon `:`. Field values MUST NOT contain `:`
in this version (a future v2 may switch to JSON canonicalization for
field values that need it).

**Field set (frozen for v1):**

| Field        | Source                                               | Notes                                       |
|--------------|------------------------------------------------------|---------------------------------------------|
| `state`      | The state name in the state machine.                 | E.g. `"pending"`, `"evaluating"`, `"allowed"`. |
| `entity_id`  | The entity whose state is being hashed.              | Format: `"request:{tenant_id}:{endpoint}"` for governance receipts. |
| `timestamp`  | The clock value at the moment of certification.      | ISO-8601 UTC, e.g. `"2026-04-28T00:00:00Z"`. |

**Stability guarantee:** The set of fields, their order, and the `:`
separator are frozen for schema version `1`. Adding, removing, renaming,
or reordering any of these fields requires a new schema version. Field
semantics may not be redefined within a version.

## Where it's used

In `ProofBridge.certify_governance_decision`, three state hashes are
computed for each governance decision:

```python
before_hash = state_hash("evaluating", entity_id, timestamp)
after_hash  = state_hash(to_state,    entity_id, timestamp)

# Step 1 receipt: pending → evaluating
state_hash("pending",   entity_id, timestamp)  # → receipt.before_state_hash
before_hash                                    # → receipt.after_state_hash

# Step 2 receipt: evaluating → final
before_hash                                    # → receipt.before_state_hash
after_hash                                     # → receipt.after_state_hash
```

Both `before_state_hash` and `after_state_hash` then feed into the
receipt's `receipt_hash` (SHA-256 of the canonical receipt-content
string — see `proof.py::certify_transition`). State-hash deviation
therefore propagates into receipt-hash deviation, which the existing
contract test `mcoi/tests/test_proof_hash_contract.py` already locks
against the Rust implementation for a known canonical fixture.

## Verification semantics

Given a `TransitionReceipt`, `state_hash` consistency is verified by:

1. **Hash function** — recompute `sha256(f"{state}:{entity_id}:{timestamp}".encode()).hexdigest()` and compare to the receipt's stored hash.
2. **Field separator** — `state`, `entity_id`, `timestamp` are joined by literal `:` with no surrounding whitespace.
3. **No additional fields** — implementations MUST NOT silently incorporate other state into the hash. Any extension requires a schema version bump.

The invariant the receipt relies on: **two state-hash computations on
the same `(state, entity_id, timestamp)` triple, performed by any
conforming implementation, MUST produce the same SHA-256 output.**

## What this spec does NOT claim

These are explicitly NOT claims today; listed so compliance reviewers
do not infer them.

### 1. State hashes capture full entity state

The state-hash content is structured (state name + entity id +
timestamp), not a serialization of every entity field. Two transitions
with identical `(state, entity_id, timestamp)` triples produce
identical state hashes regardless of any other entity state that may
have changed. This is intentional: the state-hash binds the receipt
to the entity's state machine position at a moment in time, not to
the full data shape.

A future v2 spec MAY extend the canonical content to include a
serialization of structured entity fields (e.g. tenant config, budget
balance, policy hash). Such an extension requires a new schema version
and cross-language implementation.

### 2. Rust kernel computes state hashes

The Rust `maf-kernel` implementation in `maf/rust/crates/maf-kernel/src/lib.rs`
treats `before_state_hash` and `after_state_hash` as opaque
caller-provided strings. **The Rust kernel does NOT compute state
hashes.** Only the Python `ProofBridge._state_hash` implements the
construction. A Rust-side state-hash function would be required for
true cross-language certification of state inputs (parallel to how
the receipt-hash function `sha256_hex` is mirrored on both sides).

When such a function is added, this spec's "Canonical state-hash content
layout" section becomes the cross-language contract — the existing
contract test pattern can be extended to lock state-hash equality
between languages for a known fixture.

### 3. State hashes are externally verifiable as "the entity was in this state"

A consumer holding a receipt sees `before_state_hash = "abc..."` but
cannot independently confirm that the entity was actually in the named
state at the named timestamp — the consumer would need an authoritative
state log to compare against. This is the same epistemic gap the
ledger spec describes: the chain proves *internal* consistency, not
*external* truth.

## Known gaps (issue-tracker-ready)

| Gap | Severity | Resolution path | Status |
|-----|----------|-----------------|--------|
| Rust kernel does not implement state-hash construction | Medium | Add `fn state_hash(state, entity_id, timestamp) -> String` to `maf-kernel` mirroring Python `_state_hash`; add a paired contract test pinning a known fixture. | Open |
| State-hash content is structurally minimal (state + entity_id + timestamp only) | Low | Define a v2 canonical layout that includes selected entity fields (tenant config hash, budget hash, policy version) and bump schema version. | Open — design needed |
| No external verifier for state-hash consistency | Medium | After Rust mirror lands: implement `mcoi verify-state-hash` mirroring `mcoi verify-ledger`. | Open — depends on row 1 |

## Versioning

This spec is version `1`. It documents the state-hash protocol as
implemented in `mcoi/mcoi_runtime/core/proof_bridge.py::_state_hash`
on the date this file was added. Schema changes to the canonical
content layout require a new spec version.

A future `STATE_HASH_SCHEMA_VERSION_MAX` constant should be added to
the codebase (parallel to `LEDGER_SCHEMA_VERSION_MAX`) once a verifier
exists that reads the version from receipts. Today receipts do not
carry a state-hash schema version field — adoption of this spec is
implicit by deployment.

## Why this document exists

`MAF_RECEIPT_COVERAGE.md` listed "State-hash content layout
undocumented" as a Medium-severity Open gap. Without this spec, two
implementations (Python today; a hypothetical Rust mirror tomorrow)
could each "implement state hashing" with different content layouts
and the divergence would only surface at integration time — exactly
the failure mode the SHA-256 drift / cross-language receipt-hash
contract was written to prevent.

This document doesn't add code. It documents what the code already
does and — more importantly — declares the layout as a frozen
contract that future implementations must respect. That distinction
is the difference between a property the codebase happens to have and
a property reviewers can rely on.
