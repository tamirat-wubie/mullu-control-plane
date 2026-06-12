# Distributed Scheduler Leases

Scheduler claims are represented as hash-bound lease records.

```text
ScheduledJob
  -> ScheduledJobClaim
  -> SchedulerLeaseRecord
```

The lease contains:

```text
lease_id
claim_id
job_id
worker_id
attempt
claim_hash
job_payload_hash
lease_expires_at
status
```

A lease is valid only when the job id, worker id, attempt, claim hash, and job payload hash still match. This prevents a worker from silently claiming one job and executing another.

API routes:

```text
GET  /system/scheduler/leases
POST /system/scheduler/jobs/claim
```

Example request:

```json
{
  "worker_id": "worker-a",
  "limit": 5,
  "lease_seconds": 60
}
```
