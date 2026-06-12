# Durable scheduler

v11 adds a durable scheduler model for connector and maintenance work that must not be hidden in process memory.

```text
ScheduledJob
  -> due_at / not_before
  -> idempotency_key
  -> payload_hash
  -> attempt_count
  -> status
  -> optional claim lease
```

The scheduler is deliberately metadata-oriented. It records *what should be done* and its deterministic payload hash. Execution still happens through a worker or connector adapter, and the result is recorded as a receipt.

## Job kinds

```text
oidc_jwks_refresh
signing_execution
cloud_backup_upload
replication_delivery
snapshot_compaction
backup_verification
consensus_commit
provider_execution
```

## API

```text
GET  /system/scheduler/jobs
POST /system/scheduler/jobs
POST /system/scheduler/jobs/due
```

Create job request:

```json
{
  "kind": "replication_delivery",
  "target": "follower-a",
  "payload": {"batch_id": "..."},
  "due_in_seconds": 0,
  "max_attempts": 3
}
```

Due-job polling returns `SchedulerPollReport` and does not mutate the job. Workers should claim or update jobs through the persistence layer or a future worker runtime.

## CLI

```bash
cargo run -p mind-cli -- scheduler-job-jsonl \
  ./data/scheduler.jsonl \
  replication_delivery \
  follower-a \
  '{"batch_id":"batch-1"}' \
  0 \
  3

cargo run -p mind-cli -- scheduler-due-jsonl ./data/scheduler.jsonl 10
```
