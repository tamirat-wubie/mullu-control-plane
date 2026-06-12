# Staging chaos runner

v19 turns chaos rehearsal plans into staging-gated execution reports.

```text
ChaosRehearsalPlan
  → StagingChaosEnvironment
  → StagingChaosSafetyPolicy
  → StagingChaosRunReport
```

The runner is intentionally conservative. `LiveStaging` mode still requires a staging-named environment, an allow-listed namespace, and an approval certificate hash. The current execution path uses deterministic dry-run evidence and records whether live execution was permitted. Actual destructive injection remains a separate adapter boundary.

The report binds:

```text
plan id
staging environment
safety policy
inner chaos execution run
preflight findings
live execution flags
report hash
```
