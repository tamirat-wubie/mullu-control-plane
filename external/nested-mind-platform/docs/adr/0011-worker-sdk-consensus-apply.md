# ADR 0011: Worker Runtime, Provider SDK Boundary, and Consensus Apply

## Decision

Add v12 kernel objects and ledgers for scheduler leases, worker run reports, provider SDK receipts, and consensus-certified replication apply reports.

## Rationale

The platform needs to move from request-local retry and certificate recording toward executable operational loops. The worker runtime and scheduler lease model make work claiming explicit. The provider SDK boundary keeps external side effects evidence-based. The consensus apply path allows a committed replication batch to be durably ingested without recalculating leader event hashes.

## Consequences

Constructive:

```text
+ scheduled work can be leased and reported
+ provider SDK execution can be rehearsed and receipt-bound
+ committed replication batches can be applied through a governed path
+ SQLite schema advances to v12
```

Fractures:

```text
- no always-on worker process yet
- leases are ledgered but not backed by distributed compare-and-swap claims outside SQLite
- provider SDK receipts are dry-run/gateway-shaped, not real vendor calls
- consensus apply exists, but full replicated-log protocol is still future work
```
