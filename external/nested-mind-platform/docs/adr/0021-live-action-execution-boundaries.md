# ADR 0021: Live action execution boundaries

## Status

Accepted.

## Context

v21 created action plans for GitHub, Kubernetes, and waiver review operations. Production operation needs a stronger boundary: external credentials and side effects must be executable without letting external systems mutate the symbolic kernel directly.

## Decision

v22 introduces receipt-bound execution objects for:

```text
- GitHub App installation token exchange
- GitHub check-run and branch-protection action execution
- branch-protection reconcile worker reports
- Kubernetes server dry-run execution
- waiver notification delivery
```

All external effects must produce hash-bound receipts. Raw credentials and provider tokens are connector concerns and are not persisted in kernel objects.

## Consequences

```text
+ live action execution can be scheduled and audited
+ credentials remain outside the kernel
+ GitHub/Kubernetes/notification connectors can evolve independently
- full live provider wiring still requires deployed secret management
- notification delivery UX is still minimal
```
