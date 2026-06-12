# Readiness waiver workflow

Readiness gates block promotion when required evidence is missing. v18 adds governed, auditable waivers for staging-only movement.

```text
ProductionReadinessGateReport
  → ReadinessWaiverProposal
  → ReadinessWaiverVote[]
  → ReadinessWaiverCertificate
  → ReadinessWaiverApplicationReport
```

A waiver binds:

```text
gate id
blocker ids
proposer
risk owner
reason
optional expiry
approval votes
certificate hash
```

An approved waiver can move a blocked gate to `ready_for_staging` only when all blockers are covered. It does not silently promote to production or canary.

Production promotion should still require blocker removal or a stronger multi-operator approval policy.
