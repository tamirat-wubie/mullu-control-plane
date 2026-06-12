# ADR 0008: discovery, execution, replication ingestion, and consensus membership

## Status

Accepted as v9 scaffold direction.

## Context

v8 introduced direct JWT verification, provider-shaped signing requests, cloud backup plans, and leader/follower replication batches. The remaining fracture was that several boundaries were still only planned: key discovery refresh, vendor signing execution evidence, cloud transfer execution, durable follower append, and consensus membership.

## Decision

Add explicit models for:

```text
OIDC discovery/JWKS cache
vendor signing execution requests and receipts
local cloud mirror upload/download receipts
durable replicated-record append
replication inbox envelopes
consensus membership and election tally
```

The follower path must preserve leader-produced `EventRecord` values exactly. It must not call the leader append path.

## Consequences

```text
+ identity key refresh becomes auditable
+ external signing execution becomes traceable without trusting receipts blindly
+ cloud transfer can be rehearsed locally with verification
+ follower ingestion no longer risks record-hash recomputation
+ consensus assumptions become explicit configuration
- live HTTP discovery, SDK signing, cloud SDK upload, transport retry, and full consensus remain future adapters
```
