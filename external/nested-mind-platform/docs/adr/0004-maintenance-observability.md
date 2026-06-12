# ADR 0004: Schema, compaction, and observability layer

## Decision

Add a maintenance layer composed of:

```text
schema migration ledger
snapshot compaction policy
observability/audit-event sink
```

## Reason

A production symbolic platform needs bounded storage, auditable maintenance actions, and runtime evidence. These functions must be explicit platform objects rather than hidden operator scripts.

## Consequence

The platform can now report schema version, compact snapshots, and expose audit events. Remaining work is exporter integration, signed snapshots, and external identity providers.
