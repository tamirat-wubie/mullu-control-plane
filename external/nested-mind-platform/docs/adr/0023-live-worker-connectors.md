# ADR 0023: Live worker connector evidence

## Decision

Introduce live worker evidence for secret access, GitHub token exchange, Kubernetes audit-log collection, and notification delivery.

## Context

v23 modeled secret/JWT/action/admission/notification evidence. Production execution needs worker-level receipts that bind the provider side effect to deterministic kernel artifacts without storing raw credentials or raw provider bodies.

## Consequences

```text
+ live connector workers have stable plan/receipt contracts
+ secrets and tokens remain outside kernel persistence
+ Kubernetes staging gates can require audit-log watermarks
+ notification delivery has idempotency and provider message evidence
- live provider clients still require runtime credential wiring
- UI/workflow orchestration remains separate from the kernel
```
