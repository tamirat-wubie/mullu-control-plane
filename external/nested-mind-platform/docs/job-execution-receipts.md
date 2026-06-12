# Job execution receipts

v14 separates scheduled-job claiming from scheduled-job execution evidence.

```text
ScheduledJob
  → SchedulerLeaseRecord
  → JobExecutionReceipt
  → optional job status update
```

A receipt binds:

```text
job_id
kind
target
worker_id
attempt
payload_hash
lease_id
execution mode
status
evidence_hash
```

The executor supports three deterministic modes:

```text
plan_only       audit the work without claiming side effects
receipt_only    produce receipt evidence for an external executor
local_executor  local receipt-producing execution rehearsal
```

The worker daemon records `JobExecutionReceipt` values during each tick. This lets operators distinguish “job was claimed” from “job was executed with evidence.”
