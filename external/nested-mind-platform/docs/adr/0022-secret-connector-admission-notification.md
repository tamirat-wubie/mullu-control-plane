# ADR 0022: secret-backed actions, connector workers, admission capture, and notification adapters

## Decision

Add v23 operational ledgers for secret access, GitHub App JWT creation, connector-worker execution, Kubernetes admission/audit capture, and waiver notification adapter receipts.

## Rationale

v22 could plan live actions, but credential material, execution workers, admission evidence, and notification delivery still needed stronger boundaries. v23 preserves deterministic kernel behavior by storing only plans, fingerprints, hashes, receipts, and policy reports.

## Consequences

Constructive:

```text
+ GitHub App JWT signing can be backed by secret-manager evidence
+ connector workers can prove side effects with external receipt hashes
+ Kubernetes admission/audit capture can gate live staging chaos
+ waiver notification delivery can be adapter-specific and auditable
```

Fracture:

```text
- live secret manager clients are still connector responsibilities
- raw JWT/private-key material is intentionally never stored
- notification providers still need production credential wiring
```
