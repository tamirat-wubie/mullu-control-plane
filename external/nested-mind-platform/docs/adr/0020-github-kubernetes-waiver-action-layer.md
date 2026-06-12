# ADR 0020: GitHub, Kubernetes, and waiver action layer

## Decision

Keep GitHub check-run writes, branch-protection reconciliation, Kubernetes staging chaos execution, and waiver reviewer assignment as deterministic plan/receipt objects.

## Rationale

These operations create external side effects. The symbolic kernel must not trust side effects unless they return hash-bound evidence. Therefore v21 adds action plans, receipts, and ledgers instead of allowing direct mutation of symbolic state.

## Consequences

Constructive:

```text
+ GitHub readiness evidence can now publish check-run conclusions
+ branch protection can be reconciled instead of only generated
+ Kubernetes staging chaos has a dry-run/live approval boundary
+ waiver reviews can be assigned and escalated audibly
```

Fractures:

```text
- GitHub App token generation remains connector/runtime work
- Kubernetes client execution remains receipt-bound
- reviewer assignment UX is not a full UI
```
