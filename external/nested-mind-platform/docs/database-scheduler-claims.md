# Database-backed scheduler claims

SQLite scheduler claims use a compare-and-swap shape:

```text
read due candidate
  → simulate claim
  → UPDATE scheduled_jobs
       WHERE job_id = candidate.job_id
         AND status = 'Pending'
         AND attempt_count = candidate.attempt_count
         AND payload_hash = candidate.payload_hash
  → insert SchedulerLeaseRecord when one row changed
```

This prevents two workers from claiming the same stored job when they race on the same due candidate. The lease record stores:

```text
claim_hash
job_payload_hash
worker_id
attempt
lease_expires_at
status
```

A worker can therefore prove which payload it claimed and whether the execution evidence corresponds to that payload.
