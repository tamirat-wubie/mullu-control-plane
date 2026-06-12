# ADR 0003: Lawbook Migration, Snapshot Checkpoints, and Replay Audit

## Decision

The platform will model lawbook changes as causal signed commits, persist snapshots as independently hashed checkpoint records, and expose replay audit as both API and CLI functionality.

## Context

A nested symbolic mind platform cannot treat governance changes as ordinary configuration reloads. The active lawbook Λ determines which states Σ are valid. A lawbook migration therefore must be replayable and auditable.

Full replay is exact but can become expensive as H grows. Snapshots provide bounded recovery while preserving causal continuity through `after_sequence` and `after_record_hash`.

## Consequences

Constructive delta:

```text
+ lawbook changes are event-sourced
+ replay verifies lawbook transition hashes
+ snapshots capture lawbook, state, children, and history
+ audit can run from genesis or from checkpoint
```

Fracture delta:

```text
- snapshot signing/attestation policy is not implemented yet
- no external attestation service for snapshots yet
- no distributed consensus or multi-writer event log yet
```
