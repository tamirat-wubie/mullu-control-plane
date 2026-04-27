# Proof Object Migration: v1 → v2

**Scope:** mullu-control-plane / shared schemas / MAF Rust + MCOI Python

**Trigger:** MUSIA Phase 2 governance extension

**Compatibility window:** v1 reads supported through v4.2.x; writes default to v2 from v4.0.0.

---

## 1. Format Delta

| Field                   | v1 (current)         | v2 (MUSIA)                                     |
| ----------------------- | -------------------- | ---------------------------------------------- |
| `proof_id`              | uuid                 | uuid (unchanged)                               |
| `tenant_id`             | string               | string (unchanged)                             |
| `action`                | string               | string (unchanged)                             |
| `timestamp`             | rfc3339              | rfc3339 (unchanged)                            |
| `verdict`               | `pass` \| `fail`     | `ProofState` enum (4 values, see §2)           |
| `reason`                | string?              | string? (unchanged)                            |
| `prev_hash`             | hex                  | hex (unchanged)                                |
| `proof_hash`            | hex                  | hex (unchanged)                                |
| **NEW** `construct_id`  | —                    | uuid (the construct this proof binds to)       |
| **NEW** `tier`          | —                    | integer 1..5                                   |
| **NEW** `mfidel_sig`    | —                    | optional `[[r,c], ...]`                        |
| **NEW** `cascade_chain` | —                    | array of construct uuids; empty if no cascade  |
| **NEW** `tension_snap`  | —                    | optional float (T_total at decision time)      |
| **NEW** `phi_level`     | —                    | integer 0..5 (which Φ_agent filter passed)     |
| **NEW** `schema_ver`    | (implied)            | `"2"` (explicit)                               |

## 2. ProofState Enum (replaces binary verdict)

```
ProofState ∈ { Pass | Fail(reason) | Unknown | BudgetUnknown }
```

| State           | When                                          | Required handling                            |
| --------------- | --------------------------------------------- | -------------------------------------------- |
| `Pass`          | All checks satisfied                          | Proceed                                      |
| `Fail`          | Constraint violated, reason mandatory         | Block, log, escalate per policy              |
| `Unknown`       | Cannot decide with available evidence         | Block on hard constraints; sense-then-retry  |
| `BudgetUnknown` | Decision exceeded compute/time budget         | Block on hard constraints; escalate          |

**v1 mapping:**
- v1 `pass` → v2 `Pass`
- v1 `fail` → v2 `Fail(reason)` (reason carried over; if absent, set to `"v1_migration_no_reason"`)

## 3. Migration Strategy

### 3.1 Phased rollout

```
Phase 2.0  (v3.13.x → v3.14.0)  — DUAL-WRITE
  - All new proofs written in BOTH v1 and v2 format
  - Reads still default to v1
  - v2 records validated but not authoritative

Phase 2.1  (v3.14.x → v3.15.0)  — DUAL-READ
  - Reads prefer v2 when available, fall back to v1
  - New v1 writes deprecated (warning logged)

Phase 2.2  (v3.15.x → v4.0.0)   — V2 PRIMARY
  - All new writes are v2 only
  - v1 records read via legacy adapter
  - Migration tool available for bulk upgrade

Phase 2.3  (v4.2.0+)             — V1 FROZEN
  - v1 reads still supported but deprecated
  - All new tenants v2-only
```

### 3.2 Bulk migration tool

Command: `mcoi migrate-proofs --from v1 --to v2 [--tenant <id>] [--dry-run]`

Behavior per record:
1. Load v1 proof.
2. Verify v1 hash chain integrity. **Halt batch on first chain break.**
3. Synthesize v2 fields:
   - `construct_id`: derived from action mapping table (see §4)
   - `tier`: derived from action category
   - `mfidel_sig`: empty (legacy proofs ungrounded by design)
   - `cascade_chain`: empty (v1 had no cascade tracking)
   - `tension_snap`: null
   - `phi_level`: 3 (assumed normative-compliance level for v1 actions)
   - `schema_ver`: "2"
4. Recompute `proof_hash` over v2 payload.
5. Write v2 record with `lineage.parent_ids = [v1_proof_id]` linking back.
6. Mark v1 record as `migrated_to: <v2_uuid>` (does NOT delete v1).

### 3.3 Hash chain continuity

**Critical:** v1 chain and v2 chain are **separate but linked**.

- v1 chain remains intact (immutable history).
- v2 chain begins at migration timestamp.
- Genesis v2 record's `prev_hash` = `H(last_v1_proof_hash || "v2_genesis")`.
- `lineage.parent_ids` provides the cross-version causal link.

### 3.4 Rollback plan

If Phase 2.x reveals critical fault:
1. Stop dual-writes.
2. Mark v2 chain as `quarantined`.
3. Resume v1-only operation.
4. v2 records preserved for forensic analysis but not authoritative.

## 4. Action → Construct Mapping (Legacy)

For v1 actions that predate the 25-construct framework:

| v1 action prefix          | v2 construct type | tier |
| ------------------------- | ----------------- | ---- |
| `budget.*`                | `constraint`      | 1    |
| `tenant.*`                | `boundary`        | 1    |
| `agent.invoke.*`          | `execution`       | 5    |
| `llm.call.*`              | `execution`       | 5    |
| `audit.write.*`           | `validation`      | 4    |
| `governance.guard.*`      | `validation`      | 4    |
| `workflow.step.*`         | `transformation`  | 2    |
| `policy.*`                | `constraint`      | 1    |
| `circuit.*`               | `constraint`      | 1    |
| `health.*`                | `observation`     | 5    |
| (other / unknown)         | `execution`       | 5    |

Mapping table is versioned and shipped in `mcoi/mcoi_runtime/migration/v1_to_v2_mapping.py`.

## 5. Test Requirements

Migration tooling must pass:

1. **Idempotency:** running `migrate-proofs` twice produces no new records on the second run.
2. **Hash integrity:** every migrated batch's v2 chain validates standalone.
3. **Cross-link integrity:** every v2 record's `lineage.parent_ids[0]` resolves to a valid v1 record.
4. **Rollback:** `migrate-proofs --rollback <batch_id>` restores pre-migration state in dual-read mode.
5. **Performance:** migrate 1M v1 records in under 30 minutes on standard production hardware.
6. **Tenant isolation:** per-tenant migration cannot leak proofs across tenants.

## 6. Operator Checklist

Before triggering production migration:

- [ ] Backup v1 hash chain heads (`mcoi audit snapshot --tag pre-v2-migration`)
- [ ] Verify dual-write has run successfully for at least 14 days
- [ ] Confirm v2 schema validation passes on 100% of dual-written records
- [ ] Run `--dry-run` on full corpus and review delta report
- [ ] Confirm rollback procedure tested in staging
- [ ] Notify pilot tenants 7 days in advance
- [ ] Schedule migration during low-traffic window
- [ ] Have on-call engineer + governance reviewer present
