# ADR 0018: Enforced readiness and engineering evidence

## Status

Accepted.

## Context

The platform had planning and executable evidence, but promotion and implementation work could still remain advisory. Risky waivers also needed stronger operator separation.

## Decision

Add four deterministic kernel layers:

```text
staging chaos runner
mandatory CI readiness gate
multi-operator waiver certificate
implementation evidence automation
```

External side effects stay outside the kernel. The kernel records plans, reports, certificates, and evidence bundles with hash-bound verification.

## Consequences

Constructive:

```text
+ CI can block missing readiness evidence
+ staging chaos requires preflight and approval evidence
+ waivers require role/team separation
+ implementation jobs require PR/test/readiness/rollback evidence
```

Fracture:

```text
- live destructive chaos still needs an adapter
- GitHub API integration is modeled through evidence, not called directly
- CI enforcement depends on branch protection wiring
```
