# ADR 0019: GitHub readiness evidence, branch protection, chaos adapters, and waiver review

## Status

Accepted for v20 scaffold.

## Context

v19 enforced readiness inside the platform but still depended on external PR/check evidence, GitHub branch settings, staging-chaos adapter receipts, and waiver review UX being attached manually.

## Decision

Add deterministic evidence objects for:

```text
GitHub PR/check data
branch-protection policy generation/evaluation
live staging chaos adapter plan/receipt
waiver review queue/certification
```

External systems provide evidence. The kernel validates and ledgers it without allowing external connectors to mutate symbolic state directly.

## Consequences

Constructive:

```text
+ PR/check evidence can become implementation evidence
+ branch protection can be generated and audited as code
+ staging chaos can move toward live adapters without silent side effects
+ waiver review can be role-bound and hash-certified
```

Fractures:

```text
- GitHub evidence connector retrieves PR/check data but does not yet create GitHub checks
- branch protection policy is generated/evaluated, not automatically applied
- live chaos adapter remains dry-run/receipt-bound
- waiver review storage is certificate-focused; full UI workflow remains future work
```
