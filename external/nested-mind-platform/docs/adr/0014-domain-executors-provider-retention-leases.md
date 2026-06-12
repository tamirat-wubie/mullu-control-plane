# ADR 0014: Domain Executors, Provider Receipts, Lease Adapters, and Retention Enforcement

## Status

Accepted for v15 scaffold.

## Context

v14 created generic job receipts, native provider capability reports, distributed lease boundaries, and physical consensus compaction. Those objects were sufficient for planning but not specific enough to prevent a generic worker from claiming success for a job without job-type evidence.

## Decision

v15 introduces four enforcement layers:

```text
1. domain-aware scheduled-job execution reports
2. distributed lease adapter capability reports
3. native provider execution receipts binding SDK and provider receipts
4. consensus retention enforcement policy and reports
```

The kernel still avoids hidden side effects. Each adapter produces deterministic evidence objects, and stores persist reports instead of mutating symbolic state directly.

## Consequences

Constructive:

```text
+ scheduled jobs now declare required payload/evidence
+ native provider execution cannot bypass receipt verification
+ distributed leases are evaluated through backend-specific capability reports
+ consensus apply-report deletion is governed rather than accidental
```

Fracture:

```text
- vendor SDK execution still needs provider-specific live adapters
- non-SQLite lease adapters remain boundary definitions
- job handlers still need side-effect executors for every domain workflow
```
