# Temporal Scheduler v2 Plan

Purpose: move temporal work from phrase admission toward production-grade delayed execution, missed-action handling, evidence freshness, recurrence, and worker safety.
Governance scope: schedules, recurrence, leases, wake-time revalidation, evidence freshness, missed-action policy, receipts, reconciliation, and operator replay.
Dependencies: `RELEASE_NOTES_v4.46.0.md`, `RELEASE_NOTES_v4.47.0.md`, `docs/TEMPORAL_ACTION_CONTRACT.md`, `docs/RECEIPT_VIEWER_V1_SPEC.md`.
Invariants: no scheduled action executes without wake-time revalidation; no high-risk action executes with stale evidence; no expired approval authorizes future work; no missed action runs blindly.

## Why v2

The current temporal substrate already supports time-aware admission and local scheduler execution. The next product gain is not more phrase coverage alone. The next gain is safe operational timing:

```text
run later only if it is still safe, still needed, still approved, still within budget, and still true.
```

## v2 modules

| Module | Purpose | Priority |
| --- | --- | --- |
| `MissedActionPolicy` | decide what happens when a due action wakes late | P0 |
| `EvidenceFreshnessRevalidator` | refresh or reject stale evidence at wake time | P0 |
| `TemporalExecutionClosure` | require postcondition/reconciliation before terminal success | P0 |
| `RecurrenceRuleEngine` | expand recurrence into governed occurrence instances | P1 |
| `DistributedLeaseStore` | prevent duplicate execution across workers | P1 |
| `DeadLetterQueue` | preserve failed/blocked schedule outcomes for operator review | P1 |
| `CalendarAwareScheduler` | bind user/business calendars and timezone policy | P2 |
| `OperatorReplayConsole` | inspect, replay, reschedule, cancel, or escalate schedule outcomes | P2 |

## Execution lifecycle

```text
scheduled
  -> due
  -> lease_requested
  -> leased
  -> wake_time_revalidated
  -> evidence_refreshed
  -> approval_checked
  -> capability_checked
  -> executed
  -> provider_confirmed
  -> reconciled
  -> closed
```

Terminal states:

```text
completed
failed
blocked
missed
expired
cancelled
compensated
requires_review
```

## Missed-action policies

| Policy | Meaning | Example |
| --- | --- | --- |
| `run_if_still_valid` | execute late only after full revalidation | low-risk reminder |
| `skip_and_record` | mark missed without execution | time-sensitive notification |
| `escalate_to_operator` | require human review before action | invoice/payment window missed |
| `reschedule_next_window` | find next valid recurrence window | weekly report |
| `cancel_if_past_deadline` | terminal cancel after deadline | market/price/time-sensitive action |

High-risk missed actions should default to `escalate_to_operator` or `cancel_if_past_deadline`.

## Evidence freshness checks

Wake-time revalidation should answer:

1. Is the source evidence still fresh?
2. Did the target state change?
3. Did approval expire?
4. Did budget change?
5. Did policy change?
6. Did capability maturity or environment permission change?
7. Did any contradiction appear?
8. Is rollback/recovery still available?

## Recurrence rules

A recurring rule must never grant unlimited execution authority. It only creates occurrence candidates.

```text
recurring_rule -> occurrence_instance -> temporal admission -> evidence refresh -> approval check -> execution -> closure receipt
```

Supported v2 recurrence targets:

1. daily;
2. weekly;
3. monthly;
4. business days;
5. first/last weekday of month;
6. bounded interval until date;
7. event-relative recurrence.

## Distributed lease invariant

```text
one schedule_id + one occurrence_id -> one active lease -> one terminal closure
```

A worker may execute only after acquiring a lease with:

1. worker id;
2. lease id;
3. acquired at;
4. expires at;
5. heartbeat state;
6. attempt count;
7. fencing token.

## Receipt sequence

Temporal v2 should emit or expose receipts for:

1. schedule registration;
2. occurrence creation;
3. lease acquisition;
4. wake-time revalidation;
5. evidence freshness decision;
6. execution dispatch;
7. provider confirmation;
8. reconciliation;
9. terminal closure;
10. missed/expired/cancelled outcome.

## Implementation order

### Phase 1 — Safe delayed operation

1. `MissedActionPolicy`.
2. `EvidenceFreshnessRevalidator`.
3. `TemporalExecutionClosure`.
4. tests for late high-risk action blocking.

### Phase 2 — Recurrence and review

1. `RecurrenceRuleEngine`.
2. occurrence instance model.
3. dead-letter/read-model for blocked schedules.
4. simple operator review route.

### Phase 3 — Worker scale

1. `DistributedLeaseStore`.
2. heartbeat/fencing token.
3. duplicate execution detector.
4. multi-worker tests.

## Non-goals for v2

1. unlimited natural-language time parsing;
2. autonomous high-risk execution;
3. external marketplace scheduling;
4. production health claim;
5. bypassing approval through recurrence.
