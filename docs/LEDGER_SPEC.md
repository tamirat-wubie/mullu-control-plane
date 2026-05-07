# Audit Ledger Specification — v1

**Status:** Stable contract. Breaking changes require schema version bump.
**Verifier:** `mcoi verify-ledger <input.jsonl>` (also: `verify_chain_from_entries`)
**Schema version:** `1`

## Purpose

The audit ledger is the platform's tamper-evident record of every governed
operation. This document is the canonical specification of the ledger's
on-disk layout and verification semantics. **The verifier implements this
spec, not the other way around.** Future refactoring of the verifier code
must preserve the byte-level entry-hash content layout described here.

## Hash function

`SHA-256` (FIPS 180-4). All hashes are 64-character lowercase hexadecimal.

## Genesis anchor

The first entry in any chain links to the constant:

```python
GENESIS_HASH = sha256(b"genesis").hexdigest()
# = "5b21d423a210cd6e0b1da19d0e1da89867e0a3e3c3a3a86e7e9e7e9e7e9e7e9e"  (illustrative)
```

The literal byte string is `b"genesis"` (8 bytes, ASCII). Empty chains
verify trivially (no entries to check).

## Entry layout

Each entry is a JSON object with the following required fields, in any
key order. The verifier rejects entries missing any required field.

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | integer | Monotonic 1-based counter. `entries[i].sequence == i + 1`. |
| `action` | string | Action name (e.g., `llm.complete`, `session.create`). |
| `actor_id` | string | Identity that initiated the action. |
| `tenant_id` | string | Tenant scope for the action. |
| `target` | string | Resource acted upon. |
| `outcome` | string | One of `success`, `denied`, `error`, `blocked`. |
| `detail` | object | Action-specific metadata (size-bounded). |
| `previous_hash` | string | SHA-256 hex of the prior entry's `entry_hash`, or `GENESIS_HASH` for sequence 1. |
| `entry_hash` | string | SHA-256 hex of the canonical content (defined below). |
| `recorded_at` | string | ISO-8601 UTC timestamp. |

Optional but recommended:

| Field | Type | Description |
|-------|------|-------------|
| `entry_id` | string | Stable opaque ID. Not part of the hash content. |
| `schema_version` | integer | Defaults to `1` if absent. Verifier refuses unknown versions. |

## Canonical entry-hash content layout (v1)

`entry_hash` is computed as:

```python
content = {
    "sequence":      entry["sequence"],
    "action":        entry["action"],
    "actor_id":      entry["actor_id"],
    "tenant_id":     entry["tenant_id"],
    "target":        entry["target"],
    "outcome":       entry["outcome"],
    "detail":        entry["detail"],
    "previous_hash": entry["previous_hash"],
    "recorded_at":   entry["recorded_at"],
}
content_bytes = json.dumps(content, sort_keys=True, default=str).encode()
entry_hash = sha256(content_bytes).hexdigest()
```

The hash content **excludes** `entry_id`, `entry_hash` itself, and
`schema_version`. `json.dumps(..., sort_keys=True)` produces a
deterministic byte sequence regardless of source key order.

**Stability guarantee:** The set of fields in `content` and their
serialization order are frozen for schema version `1`. Adding,
removing, or renaming any of these fields requires a new schema
version. Field semantics may not be redefined within a version.

## Verification semantics

The verifier checks (in order, per entry):

1. **Schema completeness** — every required field is present.
2. **Schema version** — `schema_version` (if present) ≤ verifier's max known version. Fails with `failure_field="schema"` for unknown versions.
3. **Sequence monotonicity** — `entries[i].sequence == entries[i-1].sequence + 1`, and `entries[0].sequence == 1` (or `== anchor_sequence` when verifying a slice). No gaps. Detects deletions even when downstream entries are re-hashed consistently.
4. **Chain linkage** — `entries[i].previous_hash == entries[i-1].entry_hash` (or `GENESIS_HASH` for the first entry, or the operator-supplied `--anchor-hash` for a slice).
5. **Entry-hash integrity** — `recompute_entry_hash(entry) == entry.entry_hash`. Detects in-place tampering.

## What the verifier proves

`mcoi verify-ledger <input>` proves **internal consistency**:

- No entry was modified after the chain was written (under the assumption that the attacker cannot also rewrite all subsequent entries).
- The schema is intact.
- The sequence is monotonic from the genesis anchor.

## What the verifier does NOT prove

The current spec deliberately does not prove **event authenticity**:

- A party with write access to the ledger file can produce a
  self-consistent chain starting from `GENESIS_HASH` that bears no
  relationship to events that actually occurred.
- A party who can rewrite **every** downstream entry after a deletion
  point can produce a chain that passes all five checks while having
  silently dropped events at the deletion point. (Sequence monotonicity
  defeats the cheap variant of this attack but cannot defeat full
  rewrites — only an external anchor can.)

For high-assurance environments, the genesis anchor and periodic chain
hashes should be **externally anchored** (e.g., signed by a KMS key the
audited subject does not control, or published to a public timestamping
service). This is out of scope for v1; consumers requiring event
authenticity should layer it on top of the integrity guarantee provided
here.

## Slice verification

`mcoi verify-ledger --from-sequence N --to-sequence M [--anchor-hash HEX]`
verifies a contiguous range of entries.

**Bare slices are unmoored.** Without `--anchor-hash`, slice verification
proves only that the slice is internally consistent — it does not prove
the slice is part of the real chain. An attacker can produce a fabricated
self-consistent slice. Bare slice mode is intended for performance triage
(e.g., finding the first tampered entry in a large ledger), not for
compliance-grade verification.

For compliance-grade slice verification, the operator must supply
`--anchor-hash <hex>`: the verifier requires `entries[start].previous_hash
== anchor_hash`. The anchor hash itself must be obtained from a trusted
external source (e.g., a previously verified prefix of the same chain,
a published checkpoint).

## Exit codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Chain valid — all checks pass. | Continue. |
| 1 | Chain broken — `previous_hash` mismatch, `entry_hash` mismatch, or sequence gap. **Treat as a security event.** | Investigate tamper. |
| 2 | Input error — file missing, invalid JSON, non-object lines. | Fix input. |
| 3 | Schema corruption — missing required fields, unknown schema version. **Likely a writer bug, not an attack.** | Investigate writer. |

The split between 1 and 3 is operationally significant: 1 indicates
deliberate modification of correctly-formatted entries, while 3
indicates the writer never produced valid entries in the first place.
Alerting policies should escalate 1 differently from 3.

## Versioning

This spec is version `1`. Each entry MAY carry a `schema_version`
integer field. The verifier:

- Defaults missing `schema_version` to `1`.
- Refuses to verify entries with `schema_version > MAX_SUPPORTED_VERSION` (currently `1`), exiting with code `3`.
- A future v2 spec will define a new canonical content layout and a
  new `MAX_SUPPORTED_VERSION` for the verifier. Old ledgers (v1 entries)
  will continue to verify under the v1 layout.

## Compliance posture

Claims that depend on this spec:

| Claim | Status |
|-------|--------|
| "Every governed operation produces an immutable audit entry." | Architectural — enforced by `GovernedSession`/`AuditTrail`. |
| "Audit entries are tamper-evident." | **Verified** by this spec + `mcoi verify-ledger`. |
| "Audit entries are tamper-proof." | **NOT a claim.** Tamper-evidence ≠ tamper-prevention. |
| "The ledger captures all events that occurred." | **NOT a claim.** External anchoring is required for event authenticity. See "What the verifier does NOT prove." |

When citing the audit trail in compliance documentation, cite the
specific claim (tamper-evidence under internal consistency), not a
generic "hash-chain audit log."
