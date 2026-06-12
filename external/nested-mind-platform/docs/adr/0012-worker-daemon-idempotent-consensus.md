# ADR 0012: Worker daemon, database claims, and idempotent consensus apply

## Decision

Add a worker daemon binary, SQLite compare-and-swap scheduler claims, a provider SDK feature matrix, consensus apply idempotency checks, and consensus log compaction decisions.

## Rationale

The platform needs continuous operational progress without letting background work bypass symbolic governance. The worker daemon therefore claims jobs and records evidence, while canonical symbolic mutation still flows through commits, event records, replay, and projection policies.

Consensus apply must be safe under retries. A duplicate apply should skip, while a conflicting operation under the same consensus entry must fail.

## Consequences

Constructive:

```text
+ always-on worker process exists
+ scheduler claim races are CAS-protected in SQLite
+ provider SDK readiness is explicit
+ consensus apply can be retried safely
+ compaction is reviewable before physical deletion
```

Fractures:

```text
- provider native SDK calls are still feature-gated plans, not wired vendor calls
- worker job handlers are still generic; each job kind needs a receipt-producing executor
- distributed leases are SQLite-local, not a multi-node lease service
- compaction is decision-only; physical deletion policy is not implemented yet
```
