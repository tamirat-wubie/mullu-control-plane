# Worker Runtime

The worker runtime turns durable scheduled jobs into explicit execution reports.

```text
scheduled_jobs
  -> claim_due_jobs_with_leases
  -> SchedulerLeaseRecord
  -> WorkerRunReport
  -> updated ScheduledJob rows
```

The kernel supports two modes:

```text
PlanOnly
ExecuteAndMarkSucceeded
```

`PlanOnly` is the default rehearsal mode. It claims due work and returns a report but does not assert that external effects happened. `ExecuteAndMarkSucceeded` is only appropriate for local dry-run actions or adapter calls whose receipt has already been verified by a separate boundary.

API routes:

```text
GET  /system/worker/runs
POST /system/worker/run-once
```

Example request:

```json
{
  "worker_id": "worker-a",
  "limit": 10,
  "lease_seconds": 60,
  "execute_and_mark_succeeded": false
}
```
