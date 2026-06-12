# API

## Public

```text
GET /health
GET /minds/root?scope=public
GET /minds/root?scope=summary
```

Public and summary projections may be read anonymously under the default authorization policy.

## Protected projection

```text
GET /minds/root?scope=internal
```

Requires `ReadInternalProjection`.

## Event trail, replay, and audit

```text
GET /minds/root/events
GET /minds/root/replay
GET /minds/root/audit
GET /minds/root/audit?from_snapshot=true
```

`/events` requires `ReadEvents`.
`/replay` requires `Replay`.
`/audit` requires `AuditReplay`.

When `from_snapshot=true`, the API uses the latest stored snapshot when available and audits only tail events after the snapshot. If no snapshot exists, it falls back to full replay audit.

## Mutation

```text
POST /minds/root/proposals
POST /minds/root/children
POST /minds/root/lawbook/migrations
```

Patch request:

```json
{
  "reason": "set initial platform goal",
  "ops": [
    {"op": "set", "key": "goal", "value": "nested symbolic minds"}
  ]
}
```

Child request:

```json
{
  "kind": "planner",
  "reason": "attach planner child mind"
}
```

Lawbook migration request:

```json
{
  "reason": "forbid password cells",
  "operations": [
    {"op":"add_rule", "rule":{"type":"forbid_key", "key":"password"}}
  ],
  "allow_foundation_removal": false
}
```

Supported migration operations:

```json
{"op":"add_rule", "rule":{"type":"require_key", "key":"goal"}}
{"op":"add_rule", "rule":{"type":"forbid_key", "key":"password"}}
{"op":"add_rule", "rule":{"type":"immutable_key", "key":"identity.id"}}
{"op":"remove_rule", "rule":{"type":"forbid_key", "key":"legacy.debug"}}
```

Foundation rule removal is rejected unless `allow_foundation_removal` is set and the actor is authorized for lawbook migration.

## Snapshots

```text
GET  /minds/root/snapshots
GET  /minds/root/snapshots/latest
POST /minds/root/snapshots
```

Reading snapshots requires `ReadSnapshots`.
Creating snapshots requires `CreateSnapshot`.

A snapshot stores:

```text
snapshot_id
mind_id
after_sequence
after_record_hash
latest_commit_id
state_hash
lawbook_hash
snapshot_hash
nested MindSnapshot
```


## v5 maintenance endpoints

```text
GET  /system/schema
GET  /system/observability/audit-events
POST /minds/root/snapshots/compact
```

Snapshot compaction uses:

```bash
MIND_SNAPSHOT_KEEP_LATEST=3
MIND_SNAPSHOT_MIN_EVENTS_BETWEEN=25
```

Observability sink:

```bash
MIND_OBSERVABILITY_LOG=./data/observability.jsonl
```

## Runtime tracing

```bash
MIND_LOG_LEVEL=mind_api=info,tower_http=info
MIND_TRACE_JSON=false
```

HTTP request tracing is attached at the API router boundary. Audit-event records are available through:

```text
GET /system/observability/audit-events
```


## v6 endpoints

```text
GET  /system/observability/export?format=internal_json
GET  /system/observability/export?format=otlp_json
GET  /system/backups/manifests
POST /system/backups/root
POST /system/backups/verify
```

These endpoints require telemetry or backup permissions. Backup verification checks backup hash, event chain, optional signatures, snapshots, and mind-id consistency.


## v6 request safety headers

Successful responses may include:

```text
x-ratelimit-limit
x-ratelimit-remaining
x-ratelimit-reset
```

Oversized requests return `413`. Rate-limited requests return `429`.

## v7 identity, signing, object backup, and distributed strategy endpoints

```text
GET  /system/identity-policy
GET  /system/signing/status
GET  /system/distributed-plan
POST /system/backups/root/object
POST /system/backups/object/verify
```

`/system/identity-policy` requires `ReadIdentityPolicy`, `/system/signing/status` requires `ReadSigningPolicy`, and `/system/distributed-plan` requires `ReadEventStoreStrategy`.

`/system/backups/root/object` requires `CreateObjectBackup` and returns an `ObjectBackupPointer`.

`/system/backups/object/verify` requires `VerifyBackup` and accepts an `ObjectBackupPointer` body.

Trusted identity headers are disabled unless:

```bash
MIND_TRUSTED_IDENTITY_HEADERS=true
```

When enabled, the API maps verified upstream identity headers into a `Principal` after issuer/audience/client-certificate binding checks.

## v8 identity endpoints

```text
GET  /system/oidc-verifier
POST /system/identity/verify-jwt
```

`GET /system/oidc-verifier` returns the active direct OIDC/JWKS verifier configuration, excluding the JWKS body.

`POST /system/identity/verify-jwt` accepts:

```json
{
  "jwt": "eyJ..."
}
```

It returns `OidcJwtVerificationReport` after signature and claim verification. The endpoint itself is protected by the same authorization policy as identity-policy reads.

## v8 CLI/API maintenance additions

```bash
cargo run -p mind-cli -- verify-oidc-jwt ./config/jwks.json ./config/token.jwt https://issuer.example nested-mind-api
cargo run -p mind-cli -- managed-signing-request ./data/commit.json aws_kms root-key arn:aws:kms:us-east-1:111122223333:key/demo <public-key-hex>
cargo run -p mind-cli -- cloud-backup-plan-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl s3 mind-backups root optional
cargo run -p mind-cli -- replication-batch-jsonl <root-mind-id> ./data/root.events.jsonl leader-a 1 none optional
```

## v9 API additions

```text
GET  /system/oidc-discovery
POST /system/oidc-verifier/refresh
GET  /system/replication/transport
POST /system/replication/follower/batches
GET  /system/consensus/membership
POST /system/backups/root/cloud-mirror
```

`POST /system/replication/follower/batches` accepts a leader-produced `ReplicationBatch`, verifies the follower cursor, event-record hash chain, and signature requirement, then persists the exact leader records through `ReplicatedEventStore`.

`POST /system/backups/root/cloud-mirror` creates a normal verified backup, creates a provider-shaped cloud backup plan, writes the backup body into the local cloud mirror adapter, and records a `CloudUploadReceipt` when SQLite storage is active.


## v10 API additions

```text
POST /system/oidc-verifier/refresh-live
POST /system/replication/outbound/batches
POST /system/consensus/membership/changes
POST /system/backups/root/signed-url-upload
```

`POST /system/oidc-verifier/refresh-live` uses the configured issuer/audience/allowed algorithms to fetch the OIDC discovery document and JWKS over HTTPS, then records a `LiveOidcRefreshReport` and JWKS cache entry when the SQLite store is active.

`POST /system/replication/outbound/batches` accepts a leader-produced `ReplicationBatch`, wraps it in a `ReplicationEnvelope`, and pushes it to configured followers using retry policy settings. It returns one `ReplicationDeliveryReceipt` per follower.

`POST /system/consensus/membership/changes` accepts a `ConsensusChangeProposal`, verifies expected configuration id and term, applies changes through the consensus membership validator, records a `ConsensusChangeJudgment`, and updates the runtime membership.

`POST /system/backups/root/signed-url-upload` accepts:

```json
{
  "provider": "s3_compatible",
  "url": "https://signed-upload-url",
  "bucket": "mind-backups",
  "key": "root/backup.json"
}
```

It captures a verified root backup, uploads it to the supplied signed URL, and records a `CloudSignedUrlReceipt` when SQLite storage is active.


## v10 live connector endpoints

```text
POST /system/oidc-verifier/refresh-live
POST /system/replication/outbound/batches
POST /system/consensus/membership/changes
POST /system/backups/root/signed-url-upload
```

These endpoints execute external connector actions or governed consensus changes and persist receipts/judgments through the runtime store.


## v11 scheduler, provider, and consensus commit endpoints

```text
GET  /system/scheduler/jobs
POST /system/scheduler/jobs
POST /system/scheduler/jobs/due
GET  /system/provider/execution-receipts
POST /system/provider/execution-receipts
GET  /system/consensus/commit-certificates
POST /system/consensus/commit-certificates
```

Scheduler endpoints require `Administer`. Provider execution receipt endpoints require `ExecuteSigningAdapter`. Consensus commit certificate endpoints require `ManageConsensus`.

Scheduler create request:

```json
{
  "kind": "replication_delivery",
  "target": "follower-a",
  "payload": {"batch_id": "batch-1"},
  "due_in_seconds": 0,
  "max_attempts": 3
}
```

Consensus commit request:

```json
{
  "operation_kind": "replication_batch_commit",
  "operation": {"batch_id": "batch-1"},
  "voters": ["node-a", "node-b"],
  "previous_entry_hash": null
}
```

## v12 worker, scheduler lease, provider SDK, and consensus apply endpoints

```text
GET  /system/scheduler/leases
POST /system/scheduler/jobs/claim
GET  /system/worker/runs
POST /system/worker/run-once
GET  /system/provider/sdk/receipts
POST /system/provider/sdk/dry-run
GET  /system/consensus/apply-reports
POST /system/consensus/log/apply
```

Scheduler lease and worker endpoints require `Administer`. Provider SDK endpoints require `ExecuteSigningAdapter`. Consensus apply endpoints require `ManageConsensus`.

Scheduler claim request:

```json
{
  "worker_id": "worker-a",
  "limit": 5,
  "lease_seconds": 60
}
```

Worker run request:

```json
{
  "worker_id": "worker-a",
  "limit": 5,
  "lease_seconds": 60,
  "execute_and_mark_succeeded": false
}
```

Consensus apply request:

```json
{
  "certificate": {"...": "ConsensusCommitCertificate"},
  "follower_id": "node-b"
}
```


## v13 worker daemon, provider feature, and consensus idempotency endpoints

```text
GET  /system/worker/daemon-ticks
POST /system/worker/tick
GET  /system/provider/sdk/features
POST /system/consensus/log/apply-idempotent
POST /system/consensus/log/compact
```

`POST /system/worker/tick` performs one scheduler claim cycle and records a `WorkerDaemonTickReport`. With SQLite storage, claims use a compare-and-swap update against pending jobs.

Worker tick request:

```json
{
  "worker_id": "worker-a",
  "limit": 10,
  "lease_seconds": 60,
  "execute_and_mark_succeeded": false,
  "tick_index": 0
}
```

`GET /system/provider/sdk/features` returns the conservative provider SDK feature matrix and records it when SQLite storage is active. Native vendor SDK features are listed but disabled by default.

`POST /system/consensus/log/apply-idempotent` checks prior apply reports before applying a consensus certificate. Matching prior applied entries are skipped; conflicting entry/operation hashes are rejected.

`POST /system/consensus/log/compact` evaluates retention for committed and applied consensus certificates. It produces a compaction decision; deletion/physical compaction is deliberately separate.

Consensus compaction request:

```json
{
  "keep_latest_committed": 64,
  "min_committed_entries_between_compactions": 128
}
```


## v14 operational evidence endpoints

```text
GET  /system/worker/job-receipts
POST /system/worker/jobs/receipt
GET  /system/provider/native-adapters
POST /system/provider/native-adapters/evaluate
GET  /system/scheduler/distributed-lease
POST /system/scheduler/distributed-lease/claims
GET  /system/consensus/log/physical-compactions
POST /system/consensus/log/compact/physical
```

`POST /system/worker/jobs/receipt` accepts a scheduled job, worker id, optional lease, and execution mode flag. It returns a `JobExecutionReceipt`.

`POST /system/provider/native-adapters/evaluate` accepts a `ProviderExecutionRequest` and returns a `NativeProviderAdapterReport` showing whether the requested provider command is disabled, gateway-backed, dry-run only, or compiled as a native feature.

`POST /system/consensus/log/compact/physical` accepts a `ConsensusLogCompactionDecision` plus a `BackupVerificationReport`. With `apply=false`, it records a planned report. With `apply=true`, SQLite deletes compacted consensus certificates after verifying the backup guard.

## v15 endpoints

```text
GET  /system/worker/domain-job-reports
POST /system/worker/domain-jobs/execute
GET  /system/scheduler/distributed-lease/adapters
POST /system/scheduler/distributed-lease/adapters/evaluate
GET  /system/provider/native-executions
POST /system/provider/native-executions/execute
GET  /system/consensus/log/retention-enforcements
POST /system/consensus/log/retention/enforce
```

The domain job execution endpoint validates job-kind-specific payload keys and records both the generic `JobExecutionReceipt` and the higher-level `DomainJobExecutionReport`.

## v16 API additions

```text
GET  /system/worker/live-domain-job-reports
POST /system/worker/live-domain-jobs/execute
GET  /system/scheduler/distributed-lease/executions
POST /system/scheduler/distributed-lease/executions
GET  /system/provider/sdk/executions
POST /system/provider/sdk/executions
GET  /system/consensus/log/retention/approvals
POST /system/consensus/log/retention/approvals
```

The v16 endpoints record execution evidence. They do not bypass governed commit, replay, or projection rules.

## v17 creative engineering endpoints

```text
GET  /system/creative-engineering/reports
POST /system/creative-engineering/reports
GET  /system/creative-engineering/chaos-rehearsal-plans
POST /system/creative-engineering/chaos-rehearsal-plans
GET  /system/creative-engineering/invariant-fuzz-runs
POST /system/creative-engineering/invariant-fuzz-runs
GET  /system/creative-engineering/readiness-gates
POST /system/creative-engineering/readiness-gates
```

These endpoints require administrative authorization. They do not mutate symbolic mind state; they record operational planning and release-readiness evidence.

## v18 executable readiness evidence endpoints

```text
GET  /system/creative-engineering/chaos-executions
POST /system/creative-engineering/chaos-executions
GET  /system/creative-engineering/invariant-fuzz-executions
POST /system/creative-engineering/invariant-fuzz-executions
GET  /system/creative-engineering/readiness-waivers/proposals
POST /system/creative-engineering/readiness-waivers/proposals
GET  /system/creative-engineering/readiness-waivers/certificates
POST /system/creative-engineering/readiness-waivers/certificates
GET  /system/creative-engineering/readiness-waivers/applications
POST /system/creative-engineering/readiness-waivers/applications
GET  /system/creative-engineering/implementation-job-plans
POST /system/creative-engineering/implementation-job-plans
```

These endpoints are maintenance/admin surfaces. They create evidence records and scheduled implementation plans; they do not mutate symbolic mind state directly.

## v19 enforced readiness endpoints

```text
GET  /system/creative-engineering/staging-chaos-runs
POST /system/creative-engineering/staging-chaos-runs
GET  /system/creative-engineering/ci-readiness-gates
POST /system/creative-engineering/ci-readiness-gates
GET  /system/creative-engineering/multi-operator-waivers
POST /system/creative-engineering/multi-operator-waivers
GET  /system/creative-engineering/implementation-evidence
POST /system/creative-engineering/implementation-evidence
GET  /system/creative-engineering/implementation-evidence/automation
POST /system/creative-engineering/implementation-evidence/automation
```

## v20 GitHub readiness, branch protection, live chaos adapter, and waiver review endpoints

```text
GET  /system/github/readiness-evidence
POST /system/github/readiness-evidence
GET  /system/github/branch-protection/policies
POST /system/github/branch-protection/policies
GET  /system/github/branch-protection/evaluations
POST /system/github/branch-protection/evaluations
GET  /system/creative-engineering/live-staging-chaos-adapters
POST /system/creative-engineering/live-staging-chaos-adapters
GET  /system/creative-engineering/live-staging-chaos-adapters/receipts
POST /system/creative-engineering/live-staging-chaos-adapters/receipts
GET  /system/creative-engineering/waiver-reviews
POST /system/creative-engineering/waiver-reviews
```

These endpoints create operational evidence. They do not mutate symbolic mind state directly.

## v21 action enforcement endpoints

```text
GET  /system/github/check-runs/write-plans
POST /system/github/check-runs/write-plans
GET  /system/github/check-runs/write-receipts
POST /system/github/check-runs/write-receipts

GET  /system/github/branch-protection/reconcile-plans
POST /system/github/branch-protection/reconcile-plans
GET  /system/github/branch-protection/reconcile-receipts
POST /system/github/branch-protection/reconcile-receipts

GET  /system/creative-engineering/kubernetes-staging-chaos/plans
POST /system/creative-engineering/kubernetes-staging-chaos/plans
GET  /system/creative-engineering/kubernetes-staging-chaos/receipts
POST /system/creative-engineering/kubernetes-staging-chaos/receipts

GET  /system/creative-engineering/waiver-reviewer-assignments
POST /system/creative-engineering/waiver-reviewer-assignments
GET  /system/creative-engineering/waiver-escalations
POST /system/creative-engineering/waiver-escalations
```

## v22 live action execution endpoints

```text
GET  /system/github/app/installation-token-plans
POST /system/github/app/installation-token-plans
GET  /system/github/app/installation-token-receipts
POST /system/github/app/installation-token-receipts

GET  /system/github/action-execution/plans
POST /system/github/action-execution/plans
GET  /system/github/action-execution/receipts
POST /system/github/action-execution/receipts

GET  /system/github/branch-protection/worker-plans
POST /system/github/branch-protection/worker-plans
GET  /system/github/branch-protection/worker-reports
POST /system/github/branch-protection/worker-reports

GET  /system/creative-engineering/kubernetes-dry-run-executions/requests
POST /system/creative-engineering/kubernetes-dry-run-executions/requests
GET  /system/creative-engineering/kubernetes-dry-run-executions/receipts

GET  /system/creative-engineering/waiver-notifications/plans
POST /system/creative-engineering/waiver-notifications/plans
GET  /system/creative-engineering/waiver-notifications/receipts
POST /system/creative-engineering/waiver-notifications/receipts
```


## v23 endpoints

```text
GET/POST /system/secrets/access-plans
GET/POST /system/secrets/access-receipts
GET/POST /system/github/app/jwt-plans
GET/POST /system/github/app/jwt-receipts
GET/POST /system/connectors/worker-plans
GET/POST /system/connectors/worker-receipts
GET      /system/creative-engineering/kubernetes-admission-audits/requests
GET      /system/creative-engineering/kubernetes-admission-audits/receipts
GET/POST /system/creative-engineering/kubernetes-admission-audits/reports
GET/POST /system/creative-engineering/waiver-notification-adapters/plans
GET/POST /system/creative-engineering/waiver-notification-adapters/receipts
```

## v24 live worker connector surfaces

Planned API surfaces for the v24 live worker evidence layer:

```text
GET/POST /system/secrets/live-connectors/plans
GET/POST /system/secrets/live-connectors/receipts
GET/POST /system/github/token-exchange-workers/plans
GET/POST /system/github/token-exchange-workers/receipts
GET/POST /system/creative-engineering/kubernetes-audit-log-collectors/plans
GET/POST /system/creative-engineering/kubernetes-audit-log-collectors/reports
GET/POST /system/creative-engineering/notification-delivery-clients/plans
GET/POST /system/creative-engineering/notification-delivery-clients/receipts
```

The kernel objects are deterministic plan/receipt records; live provider calls remain in connector workers.

## v25 runtime-wired connector and promotion APIs

v25 wires the v24 live connector objects and adds orchestration/promotion endpoints.

```text
GET/POST /system/secrets/live-connectors/plans
GET/POST /system/secrets/live-connectors/receipts
GET/POST /system/github/app/token-exchange/plans
GET/POST /system/github/app/token-exchange/receipts
GET/POST /system/creative-engineering/kubernetes-audit-log-collectors/plans
GET/POST /system/creative-engineering/kubernetes-audit-log-collectors/reports
GET/POST /system/creative-engineering/notification-delivery-clients/plans
GET/POST /system/creative-engineering/notification-delivery-clients/receipts
GET/POST /system/connectors/orchestration/plans
GET/POST /system/connectors/orchestration/reports
GET/POST /system/creative-engineering/kubernetes-audit-source-adapters/plans
GET/POST /system/creative-engineering/kubernetes-audit-source-adapters/receipts
GET/POST /system/creative-engineering/notification-provider-deliveries/plans
GET/POST /system/creative-engineering/notification-provider-deliveries/receipts
GET/POST /system/connectors/action-promotion-gates
```

All endpoints require administrator authorization and persist evidence only when the runtime is backed by SQLite.
