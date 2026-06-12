# ADR 0015: Live executors, lease execution receipts, provider SDK policy, and retention approval

## Status

Accepted for v16 scaffold.

## Decision

Add four production boundaries:

```text
1. live domain job execution reports
2. backend-specific distributed lease execution receipts
3. provider SDK execution policy reports
4. consensus retention approval certificates
```

## Reasoning

v15 established contracts for domain jobs, distributed leases, native provider execution, and consensus retention. v16 turns those contracts into auditable execution workflows while keeping side effects outside the symbolic kernel.

## Consequences

Constructive:

```text
+ workers record evidence-producing live execution reports
+ Postgres/etcd lease execution has a stable command/receipt shape
+ provider SDK execution has explicit policy gates
+ retention deletion requires quorum-governed approval evidence
```

Fracture:

```text
- live vendor clients are still not embedded in the kernel
- Postgres/etcd execution requires adapter implementation using the command plans
- retention approval is certificate-based; operator UX for vote collection is still minimal
```
