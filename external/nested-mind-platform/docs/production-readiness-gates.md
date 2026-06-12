# Production Readiness Gates

A readiness gate evaluates creative engineering suggestions, chaos rehearsal plans, and invariant fuzz runs into a release status.

```text
CreativeEngineeringReport
  + ChaosRehearsalPlan
  + InvariantFuzzRunReport
  + ProductionReadinessGatePolicy
  → ProductionReadinessGateReport
```

Statuses:

```text
blocked
ready_for_staging
ready_for_canary
```

The default policy requires:

```text
chaos plan present
invariant fuzz report present
at least 12 fuzz cases
destructive rejection cases present
zero unwaived critical fractures
```

## CLI

```bash
cargo run -p mind-cli -- readiness-gate-demo <mind-id>
```

## API

```http
POST /system/creative-engineering/readiness-gates
GET  /system/creative-engineering/readiness-gates
```
