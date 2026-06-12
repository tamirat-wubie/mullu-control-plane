# Executable chaos rehearsal

v18 turns chaos rehearsal plans into executable evidence.

```text
ChaosRehearsalPlan
  → execute_chaos_rehearsal_plan
  → ChaosExecutionRun
  → SQLite chaos_execution_runs ledger
```

Execution modes:

```text
plan_only              records planned experiments without injection
deterministic_dry_run  verifies declared containment/evidence contracts deterministically
```

The first production target is not uncontrolled failure injection. The target is a repeatable evidence artifact that proves every declared experiment has:

```text
invariant under test
injection point
expected containment
expected signal
rollback guard
required evidence
execution hash
```

Live destructive injection should remain behind staging-only controls until dry-run evidence and rollback paths are green.
