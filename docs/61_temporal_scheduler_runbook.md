# Temporal Scheduler Runbook

Purpose: operate governed scheduled temporal actions across API admission,
persistence, worker execution, receipts, and proof certification.
Governance scope: temporal scheduler runtime, store, worker, background loop,
and HTTP endpoints.
Dependencies: `TemporalRuntimeEngine`, `TemporalSchedulerEngine`,
`TemporalSchedulerStore`, `TemporalSchedulerWorker`, `ProofBridge`, and the
temporal scheduler router.
Invariants:
- Runtime clock is authoritative.
- Scheduled actions require `execute_at`.
- Worker execution requires lease acquisition and temporal policy re-check.
- Handlers run only after a `due` scheduler receipt.
- Every evaluation or closure emits a bounded receipt.
- Optional background execution must be explicitly enabled.

## Capability

The temporal scheduler turns a future action into a governed lifecycle:

```text
create schedule
  -> persist action
  -> detect due action
  -> acquire lease
  -> re-check temporal policy
  -> emit evaluation receipt
  -> run handler only if due
  -> emit closure receipt
  -> persist state
  -> optionally certify proof
```

This means Mullu can hold a command until a future time, wake it up, and still
refuse execution if the approval expired, the evidence is stale, the command is
expired, or the retry window is not open.

## API

### Create schedule

```text
POST /api/v1/temporal/schedules
```

Required fields:

| Field | Meaning |
| --- | --- |
| `schedule_id` | scheduler identity |
| `action_id` | governed action identity |
| `tenant_id` | tenant boundary |
| `actor_id` | requesting actor |
| `action_type` | action domain label |
| `execute_at` | earliest due instant |

Optional fields:

| Field | Meaning |
| --- | --- |
| `requested_at` | request time; defaults to runtime clock |
| `risk` | `low`, `medium`, `high`, or `critical` |
| `not_before` | earliest valid execution instant |
| `expires_at` | command expiry |
| `approval_expires_at` | approval expiry |
| `evidence_fresh_until` | evidence freshness boundary |
| `retry_after` | retry lower bound |
| `max_attempts` | retry ceiling |
| `attempt_count` | attempts already consumed |
| `handler_name` | worker handler key |
| `metadata` | bounded operator metadata |

Example:

```json
{
  "schedule_id": "sched-followup-001",
  "action_id": "act-followup-001",
  "tenant_id": "tenant-a",
  "actor_id": "user-a",
  "action_type": "reminder",
  "execute_at": "2026-05-04T14:00:00+00:00",
  "handler_name": "reminder"
}
```

### List schedules

```text
GET /api/v1/temporal/schedules
GET /api/v1/temporal/schedules?tenant_id=tenant-a
GET /api/v1/temporal/schedules?state=pending
```

### Get schedule and receipts

```text
GET /api/v1/temporal/schedules/{schedule_id}
```

Returns the current schedule snapshot and all scheduler receipts for that
schedule.

### Cancel schedule

```text
POST /api/v1/temporal/schedules/{schedule_id}/cancel
```

Cancellation:

- moves the schedule to `cancelled`
- emits a `blocked` scheduler receipt with reason `cancelled`
- certifies a temporal scheduler proof receipt
- persists the terminal state

### Manual worker tick

```text
POST /api/v1/temporal/worker/tick
```

Request:

```json
{
  "worker_id": "temporal-worker",
  "limit": 10,
  "lease_seconds": 60,
  "certify_proofs": true
}
```

The tick processes currently due schedules up to `limit`. It does not execute
future schedules.

### Summary

```text
GET /api/v1/temporal/summary
```

Returns runtime counters, persistent store counters, and background worker
status.

## States

| State | Meaning |
| --- | --- |
| `pending` | waiting for due time or retry window |
| `running` | leased and admitted by temporal policy |
| `completed` | handler completed |
| `expired` | command expiry passed before execution |
| `blocked` | temporal policy denied or escalated before handler dispatch |
| `missed` | operator marked the due run missed |
| `failed` | handler missing or handler execution failed |
| `cancelled` | operator/API cancelled the schedule |

## Receipt Reasons

| Reason | Meaning |
| --- | --- |
| `temporal_policy_passed` | schedule is due and admissible |
| `not_due` | execute time has not arrived |
| `retry_window_not_open` | retry lower bound is still in the future |
| `approval_expired` | approval is no longer valid |
| `command_expired` | action expired before execution |
| `evidence_stale` | evidence freshness window is closed |
| `retry_attempts_exhausted` | retry ceiling reached |
| `completed` | handler completed |
| `missing_handler` | no handler was registered for `handler_name` |
| `handler_error` | registered handler raised an exception |
| `missed_run` | operator closed the schedule as missed |
| `cancelled` | operator/API cancelled the schedule |

## Persistence

By default the scheduler store is in memory. To persist schedules and receipts:

```text
MULLU_TEMPORAL_SCHEDULER_STORE_PATH=C:\mullu\temporal_scheduler.json
```

The file stores deterministic JSON with:

```text
actions[]
receipts[]
```

On server startup, saved actions are restored into the scheduler engine. Receipt
history remains in the store for operator review.

## Background Worker

Manual worker ticks are always available through the API. Background execution
is opt-in:

```text
MULLU_TEMPORAL_WORKER_ENABLED=true
MULLU_TEMPORAL_WORKER_ID=temporal-worker
MULLU_TEMPORAL_WORKER_INTERVAL_SECONDS=30
MULLU_TEMPORAL_WORKER_LIMIT=10
MULLU_TEMPORAL_WORKER_LEASE_SECONDS=60
```

When enabled:

1. The server builds a `TemporalSchedulerWorker`.
2. The server starts `TemporalSchedulerBackgroundLoop`.
3. Each loop calls `run_once(limit=...)`.
4. Shutdown manager registers `stop_temporal_scheduler`.
5. Shutdown stops the background thread before connection closure.

If the background worker raises, the loop records a bounded error and continues
until stopped.

## Handler Registration

Handlers are resolved by `handler_name` from `deps.temporal_action_handlers`.
The default registry is empty. Operators or platform bootstrap code must add
handlers explicitly:

```python
deps.temporal_action_handlers["reminder"] = reminder_handler
```

A missing handler does not silently pass. It closes the schedule as `failed`
with reason `missing_handler`.

## Proof Witness

Scheduler receipts can be certified through `ProofBridge` using the temporal
scheduler state machine:

```text
pending -> running      temporal_action_due
running -> completed    temporal_action_completed
pending -> blocked      temporal_action_blocked
pending -> expired      temporal_action_expired
pending -> missed       temporal_action_missed
pending -> cancelled    temporal_action_cancelled
running -> failed       temporal_action_failed
```

Proof guard detail includes:

```text
schedule_id
scheduler_receipt_id
scheduler_verdict
worker_id
temporal_decision_id
temporal_verdict
action_id
action_type
execute_at
handler_name
```

## Operator Checklist

For a scheduled action:

1. Confirm `execute_at` is in UTC or has an explicit offset.
2. Confirm tenant and actor are correct.
3. Confirm high-impact actions carry expiry and approval windows.
4. Confirm handler registration before enabling background execution.
5. Check `/api/v1/temporal/summary` before and after worker ticks.
6. For blocked runs, inspect the scheduler receipt `reason`.
7. For proof review, join `scheduler_receipt_id` to the proof guard detail.
8. Confirm cancelled, failed, expired, missed, and completed schedules do not
   return to `pending`.

## Current Limits

This runbook covers durable local JSON persistence and in-process background
execution. It does not yet define:

- distributed scheduler leader election
- multi-process lease persistence
- external handler plugin loading
- natural-language time parsing
- recurring schedule expansion

Those are later layers built on this governed temporal substrate.
