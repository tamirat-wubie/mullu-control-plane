# Pilot Operations Guide v0.1

## Overview

This guide covers operating the Mullu Platform MCOI Runtime during controlled pilot use. It assumes familiarity with the OPERATOR_GUIDE_v0.1.md basics.

## Telemetry

The platform provides a `TelemetryCollector` that tracks:

| Metric | Source | What it measures |
|---|---|---|
| Run success rate | runs | Succeeded / total runs |
| Verification closure rate | runs | Closed verifications / total runs |
| Skill success rate | per skill | Succeeded / total skill executions |
| Provider failure rate | per provider | Failed / total provider invocations |
| Autonomy violation rate | autonomy | Violations / total autonomy decisions |
| Escalation count | runs | Total escalation triggers |

## Alerting

Configure thresholds to trigger alerts:

- `failure_rate` on `runs` — triggers when run failure rate exceeds threshold
- `failure_rate` on a skill_id — triggers when that skill's failure rate exceeds threshold
- `failure_rate` on a provider_id — triggers when that provider's failure rate exceeds threshold
- `violation_rate` on `autonomy` — triggers when autonomy violation rate exceeds threshold

Alerts have three severities: `info`, `warning`, `critical`.

## Run History

The telemetry collector maintains an in-memory run history ledger that supports filtering by:

- success/failure status
- skill_id
- autonomy_mode

Use `get_run_history()` for post-run analysis and `snapshot()` for full telemetry state.

## Pilot Workflow Operation

### Before each pilot run
1. Select config profile with appropriate autonomy mode
2. Verify provider registrations (if applicable)
3. Clear or check telemetry state

### During pilot run
1. Execute through operator loop (`run_step` or `run_skill`)
2. Record telemetry from the run report
3. Check for triggered alerts

### After pilot run
1. Review telemetry snapshot
2. Check run history for patterns
3. Review active alerts
4. Update pilot checklist

## Incident Response

If a pilot run fails unexpectedly:
1. Check structured errors in the run report
2. Check provider health status
3. Check meta-reasoning degraded capabilities
4. Check autonomy mode decision
5. Review telemetry for trending failures
6. If escalation triggered, review escalation message content
