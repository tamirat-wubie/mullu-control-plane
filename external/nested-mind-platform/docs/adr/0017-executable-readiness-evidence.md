# ADR 0017: Executable readiness evidence

## Decision

Promote v17 creative-engineering artifacts from plans into executable evidence artifacts.

## Context

The platform had planning objects for chaos rehearsal, invariant fuzzing, and readiness gates. That was useful but insufficient for production because a plan that is never executed can create false confidence.

## Mechanism

v18 adds:

```text
ChaosExecutionRun
InvariantFuzzExecutionReport
ReadinessWaiverCertificate
ReadinessWaiverApplicationReport
EngineeringImplementationJobPlan
```

External mutation remains outside the symbolic kernel. The new objects are deterministic reports, certificates, and scheduled jobs.

## Consequences

Positive:

```text
+ failure rehearsals create evidence
+ fuzz banks can be executed in CI
+ readiness waivers are explicit and expiring
+ creative suggestions become scheduled implementation work
```

Tradeoffs:

```text
- deterministic dry-run is not a substitute for full staging chaos
- waiver policy needs stronger multi-operator controls before production
- scheduled implementation jobs still require domain-specific executors
```
