# Domain Job Executors

v15 promotes generic worker receipts into domain-aware job execution reports.

```text
ScheduledJob
  → DomainJobExecutorRegistry
  → DomainJobExecutionPlan
  → JobExecutionReceipt
  → DomainJobExecutionReport
```

Each scheduled job kind now has an explicit handler contract:

| Job kind | Required payload keys | Required evidence |
|---|---|---|
| `oidc_jwks_refresh` | `issuer`, `audience` | `jwks_cache_entry`, `issuer`, `jwks_uri` |
| `signing_execution` | `request_id`, `payload_hash`, `key_id` | `provider_receipt`, `signature_hash` |
| `cloud_backup_upload` | `backup_id`, `backup_hash`, `target` | `upload_receipt`, `content_hash` |
| `replication_delivery` | `batch_id`, `follower_id` | `delivery_receipt`, `ack` |
| `snapshot_compaction` | `mind_id`, `policy` | `compaction_decision` |
| `backup_verification` | `backup_id`, `backup_hash` | `verification_report` |
| `consensus_commit` | `cluster_id`, `entry_id`, `entry_hash` | `commit_certificate`, `quorum` |
| `provider_execution` | `execution_id`, `payload_hash`, `adapter` | `provider_execution_receipt` |

A missing required payload key yields a rejected domain report rather than a silent success.

## API

```text
GET  /system/worker/domain-job-reports
POST /system/worker/domain-jobs/execute
```

## CLI

```bash
cargo run -p mind-cli -- domain-job-execute-json ./data/job.json worker-a plan
cargo run -p mind-cli -- domain-job-execute-json ./data/job.json worker-a execute
```
