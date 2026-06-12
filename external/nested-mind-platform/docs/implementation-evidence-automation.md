# Implementation evidence automation

v18 converted creative suggestions into scheduled implementation jobs. v19 adds PR/test evidence automation plans and evidence bundles.

```text
EngineeringImplementationJobPlan
  → ImplementationEvidenceAutomationPlan
  → PR branch / title / required test commands
  → ImplementationEvidenceArtifact[]
  → ImplementationJobEvidenceBundle
```

Default required evidence:

```text
pull request
test run
readiness gate
rollback plan
```

A bundle is `satisfied` only when all required evidence kinds are attached and none of the artifacts mark themselves failed, rejected, or blocked.
