# ADR 0010: Durable scheduler, provider receipts, consensus commit certificates

## Status

Accepted for v11 scaffold.

## Decision

Add three operational ledgers without changing the canonical event-chain semantics:

```text
scheduled_jobs
provider_execution_receipts
consensus_commit_certificates
```

## Rationale

The v10 platform could execute live connector calls, but long-running retry and provider evidence were still request-local. v11 makes pending work and external execution receipts explicit and hash-bound.

Consensus membership changes were governed in v10. v11 adds a certificate model for operation commits so a future consensus runtime can prove quorum before accepting distributed commit side effects.

## Consequences

Constructive:

```text
+ retryable work can be persisted
+ provider SDK/gateway effects produce auditable receipts
+ consensus commit decisions can be verified before durable append
```

Fracture remaining:

```text
- no always-on worker loop yet
- no distributed scheduler lease table yet
- no full Raft/Paxos implementation yet
```
