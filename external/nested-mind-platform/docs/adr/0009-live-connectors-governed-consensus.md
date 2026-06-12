# ADR 0009: Live connectors and governed consensus changes

## Status

Accepted.

## Context

The platform now has deterministic kernel objects for identity discovery, signing execution, cloud backup transfer, replication, and consensus membership. The next step required live side-effecting adapters without allowing those adapters to bypass kernel invariants.

## Decision

Add `crates/mind-connectors` for live HTTP/provider adapters. Keep request/receipt/report types in `mind-core`.

Add v10 ledgers for:

```text
live_oidc_refreshes
cloud_signed_url_receipts
replication_delivery_receipts
consensus_change_judgments
```

Add governed membership changes through `ConsensusChangeProposal` and `ConsensusChangeJudgment`.

## Consequences

Constructive:

```text
+ live integrations are isolated from the kernel
+ side effects return auditable receipts
+ OIDC refresh, signed URL upload, and replication delivery can be executed through CLI/API
+ consensus membership mutation is stale-state checked and hash-traced
```

Fracture:

```text
- provider SDK implementations remain outside the kernel
- distributed retry state is local, not scheduler-backed
- consensus judgment does not yet run a full leader-election protocol
```
