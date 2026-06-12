# ADR 0009: live adapters and governed consensus changes

## Status

Accepted for v10 scaffold.

## Decision

Add live adapter execution outside the deterministic kernel:

```text
mind-core        deterministic models, reports, judgments
mind-connectors  HTTPS adapter execution
mind-api         authorization, recording, runtime exposure
mind-store       transactional ledgers
```

Add `ConsensusChangeProposal` and `ConsensusChangeJudgment` so membership changes are never silent in runtime configuration.

## Rationale

The symbolic kernel should not perform network I/O directly. Connector execution must return evidence objects that can be stored, audited, and replayed as operational context.

## Consequences

Constructive:

```text
+ OIDC discovery can run live over HTTPS
+ signed-URL backup upload can be rehearsed without vendor SDK lock-in
+ outbound replication has retry receipts
+ consensus membership changes become explicit judgments
```

Fractures:

```text
- active JWT verifier hot-swap needs a separate rotation policy
- direct cloud/KMS SDK clients are not yet implemented
- replication retry is request-bound, not a background worker
- consensus governance is not a leader-election protocol
```
