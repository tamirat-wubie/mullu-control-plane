# ADR 0013: Receipt executors, native provider boundaries, physical compaction, and distributed leases

## Decision

Add v14 operational contracts for receipt-producing scheduled-job executors, native provider feature evaluation, backup-guarded physical consensus compaction, and distributed scheduler lease services.

## Rationale

v13 made workers and consensus compaction visible, but claiming a job was still too close to executing a job, and compaction was still decision-only. v14 makes each irreversible or external action produce a hash-bound receipt before state or operational ledgers advance.

## Consequences

Constructive:

```text
+ jobs now have execution receipts
+ native provider features are queryable and auditable
+ physical consensus compaction requires backup guard evidence
+ distributed lease services have request/receipt contracts
```

Fracture:

```text
- provider SDK calls still need concrete vendor implementations
- distributed lease services are modeled but not fully implemented as external services
- consensus certificate deletion exists only in SQLite
- compaction of apply/idempotency reports is intentionally conservative
```
