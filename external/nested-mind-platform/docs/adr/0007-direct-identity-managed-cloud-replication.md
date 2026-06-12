# ADR 0007: Direct identity, managed signing, cloud backup planning, and replication protocol

## Decision

Add direct JWT/JWKS identity verification, managed signing request/completion adapters, provider-shaped cloud backup plans, and explicit leader/follower replication protocol types.

## Rationale

The platform already had a safe local mutation path, signed commits, object backup pointers, and append-authority guards. v8 adds the missing production seams that allow external systems to perform identity, signing, backup transfer, and replication without bypassing kernel invariants.

## Consequences

```text
+ direct JWT identity can authenticate without trusted header injection
+ provider signing requests are auditable before completion
+ cloud backup transfer can be planned without mutating Σ
+ replication batches can be verified before follower acceptance
- live vendor SDK calls remain outside the kernel
- replication transport and consensus remain future work
```
