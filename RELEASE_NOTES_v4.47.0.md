# Mullu Platform v4.47.0 - Temporal Scheduler Runtime

**Release date:** TBD
**Codename:** Chronos Worker
**Migration required:** No

---

## What this release is

Adds durable temporal scheduling on top of the temporal admission substrate from
v4.46.0.

Mullu can now persist scheduled temporal actions, restore them after restart,
process due actions through a governed worker, emit scheduler receipts, certify
temporal scheduler proofs, expose temporal scheduler HTTP endpoints, and run an
optional background worker loop.

---

## What is new in v4.47.0

### Temporal scheduler engine

`TemporalSchedulerEngine` now supports:

- scheduled temporal action registration
- due-action discovery
- worker leases
- wake-time temporal policy re-check
- completion, failure, missed, expired, blocked, and cancelled closure
- restart restore into an empty scheduler

### Persistent scheduler store

New store:

```text
TemporalSchedulerStore
FileTemporalSchedulerStore
```

The file-backed store writes deterministic JSON with:

```text
actions[]
receipts[]
```

Set:

```text
MULLU_TEMPORAL_SCHEDULER_STORE_PATH=C:\mullu\temporal_scheduler.json
```

### Governed worker

New worker:

```text
TemporalSchedulerWorker
```

The worker:

1. finds due schedules
2. acquires a lease
3. re-checks temporal policy
4. persists the evaluation receipt
5. runs a handler only after `due`
6. persists the closure receipt
7. optionally certifies proof receipts

Missing handlers close as `failed` with reason `missing_handler`.
Handler exceptions close as `failed` with reason `handler_error`.

### Background loop

New optional background loop:

```text
TemporalSchedulerBackgroundLoop
```

Enable with:

```text
MULLU_TEMPORAL_WORKER_ENABLED=true
MULLU_TEMPORAL_WORKER_ID=temporal-worker
MULLU_TEMPORAL_WORKER_INTERVAL_SECONDS=30
MULLU_TEMPORAL_WORKER_LIMIT=10
MULLU_TEMPORAL_WORKER_LEASE_SECONDS=60
```

When enabled, shutdown registers:

```text
stop_temporal_scheduler
```

### HTTP API

New endpoints:

```text
POST /api/v1/temporal/schedules
GET  /api/v1/temporal/schedules
GET  /api/v1/temporal/schedules/{schedule_id}
POST /api/v1/temporal/schedules/{schedule_id}/cancel
POST /api/v1/temporal/worker/tick
GET  /api/v1/temporal/summary
```

Manual worker tick remains available even when the background worker is disabled.

### Proof bridge

New temporal scheduler proof path certifies scheduler receipts through the
temporal scheduler state machine.

Supported transitions include:

```text
pending -> running
running -> completed
pending -> blocked
pending -> expired
pending -> missed
pending -> cancelled
running -> failed
```

---

## Documentation

New:

- `docs/61_temporal_scheduler_runbook.md`

Updated:

- `docs/TEMPORAL_ACTION_CONTRACT.md`

---

## Test coverage

Focused coverage includes:

- scheduler due and lease behavior
- wake-time approval expiry
- stale evidence escalation
- retry window deferral
- max-attempt denial
- persistent store round-trip
- malformed store fail-closed behavior
- worker handler dispatch
- missing handler failure
- handler exception failure
- proof certification for scheduler receipts
- temporal scheduler HTTP endpoints
- cancellation receipt and proof
- default router mounting
- background loop start/stop
- bounded background worker errors

Focused verification:

```text
63 passed
Ruff: All checks passed
```

---

## Operational guidance

Use manual worker ticks first:

```text
POST /api/v1/temporal/worker/tick
```

Then enable the background worker only after:

1. handler registry is configured
2. persistence path is set if restart survival is required
3. `/api/v1/temporal/summary` reports the expected pending count
4. blocked and failed receipt handling is understood by operators

---

## Honest assessment

This release makes scheduled temporal execution operational inside one server
process with local durable storage.

It does not yet implement:

- distributed scheduler leader election
- multi-process lease persistence
- recurring schedule expansion
- natural-language time parsing
- external handler plugin loading

Those remain future layers. The important gain is that Mullu now has a governed
time-aware execution path from API schedule creation to worker execution to
receipt persistence to proof witness.
