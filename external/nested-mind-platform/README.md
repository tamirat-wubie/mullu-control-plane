# Nested Mind Platform

Production-oriented Rust scaffold for a nested symbolic mind platform.

```text
𝕊 := ⟨ Ι, Λ, Σ, Γ, H ⟩

Ι = immutable identity
Λ = lawbook, invariants, migrations, authorization rules
Σ = mutable symbolic state, changed only through validated edits
Γ = projection/API boundary, exposes without leaking mutation authority
H = causal history: signed event chain + snapshots + replay audit + backup/object manifests
```


## v24 layer

```text
secret access evidence
  → live secret connector receipt
  → GitHub token exchange worker receipt
  → Kubernetes audit-log collector report
  → notification delivery client receipt
  → SQLite v24 operational ledgers
```

The v24 layer adds live worker evidence contracts for secret-manager reads, GitHub App installation-token exchange, Kubernetes audit-log collection, and provider-specific waiver notification delivery. Raw secrets, raw JWTs, raw installation tokens, and raw provider response bodies stay outside kernel persistence.

## v14 layer

```text
durable scheduled job
  → SQLite compare-and-swap lease claim
  → receipt-producing job execution
  → native provider capability evaluation
  → optional distributed lease-service boundary
  → backup-guarded physical consensus compaction
  → SQLite v14 operational ledgers
```

The v14 scaffold includes the prior v13 layer and adds:

```text
+ JobExecutionReceipt for worker-executed scheduled jobs
+ job receipt verification reports
+ native provider adapter registry and evaluation reports
+ compile-time provider feature propagation across API/CLI/worker/connectors
+ distributed lease service boundary/request/receipt model
+ backup-guarded physical consensus compaction plan/report
+ SQLite v14 ledgers for job receipts, native provider reports, distributed lease receipts, and physical compaction reports
+ API routes and CLI commands for v14 operations
+ tests and docs for the new execution evidence layer
```

Earlier layers remain in the repo: event sourcing, signed commits, transactional SQLite, snapshots, audit, schema migrations, observability, backup/restore, deployment templates, OIDC/JWKS verification, connector boundaries, scheduler leases, worker daemon ticks, provider SDK dry-run receipts, consensus commit certificates, idempotent follower apply, and consensus compaction decisions.

## Workspace

```text
crates/mind-core          symbolic kernel
crates/mind-connectors    live HTTP connector/adaptor boundary
crates/mind-api           HTTP API runtime
crates/mind-cli           local/audit/maintenance CLI
crates/mind-worker        always-on SQLite-backed worker daemon
crates/mind-store-sqlite  transactional SQLite event, snapshot, observability, backup, and v14 metadata store
```

## Run local API

```bash
export MIND_BOOTSTRAP_TOKEN="$(openssl rand -hex 32)"
export MIND_BOOTSTRAP_PRINCIPAL="tamirat"
export MIND_REQUIRE_SIGNATURES=true
export MIND_SIGNING_BACKEND=env_ed25519
export MIND_COMMIT_SIGNING_KEY_ID="root-runtime-ed25519"
export MIND_COMMIT_SIGNING_SEED_HEX="$(openssl rand -hex 32)"
export MIND_EVENT_DB="./data/mind-events.sqlite"
export MIND_OBSERVABILITY_USE_EVENT_DB=true
export MIND_MAX_BODY_BYTES=65536
export MIND_RATE_LIMIT_REQUESTS=60
export MIND_RATE_LIMIT_WINDOW_SECONDS=60
export MIND_BACKUP_OBJECT_DIR="./data/object-store"
export MIND_CLOUD_OBJECT_MIRROR_DIR="./data/cloud-mirror"
export MIND_EVENT_STORE_STRATEGY=single_writer
cargo run -p mind-api
```

## OIDC discovery-backed verifier

```bash
export MIND_OIDC_DISCOVERY_FILE="./config/openid-configuration.json"
export MIND_OIDC_JWKS_FILE="./config/jwks.json"
export MIND_OIDC_ISSUER="https://issuer.example"
export MIND_OIDC_AUDIENCES="nested-mind-api"
export MIND_OIDC_ALLOWED_ALGORITHMS="RS256"
export MIND_OIDC_REFRESH_TTL_SECONDS=3600
```

Protected routes:

```text
GET  /system/oidc-discovery
POST /system/oidc-verifier/refresh
POST /system/oidc-verifier/refresh-live
POST /system/identity/verify-jwt
```

`POST /system/oidc-verifier/refresh` records a file-backed cache report. `POST /system/oidc-verifier/refresh-live` performs HTTPS discovery/JWKS fetch and records a `LiveOidcRefreshReport` when SQLite storage is active.

## Replication and consensus

Follower ingestion is intentionally separate from leader append:

```text
AppendOnlyEventStore::append(commit)
  = leader creates new EventRecord

ReplicatedEventStore::append_replicated_records(records)
  = follower verifies and persists leader-produced EventRecord values exactly
```

This prevents a follower from recalculating sequence/hash data and accidentally forking `H`.

Runtime config:

```bash
export MIND_REPLICATION_INBOX_LOG="./data/replication-inbox.jsonl"
export MIND_REPLICATION_LEADER_ID="node-a"
export MIND_REPLICATION_FOLLOWERS="node-b=http://node-b:8080,node-c=http://node-c:8080"
export MIND_REPLICATION_REQUIRED_ACKS=2
export MIND_REPLICATION_MAX_RECORDS_PER_BATCH=100
export MIND_CONSENSUS_CLUSTER_ID="mind-cluster"
export MIND_CONSENSUS_MEMBERS="node-a,node-b,node-c"
export MIND_CONSENSUS_LEADER_ID="node-a"
```

Protected routes:

```text
GET  /system/replication/transport
POST /system/replication/follower/batches
POST /system/replication/outbound/batches
GET  /system/consensus/membership
POST /system/consensus/membership/changes
GET  /system/consensus/commit-certificates
POST /system/consensus/commit-certificates
```

## Cloud mirror transfer adapter

The v8 cloud layer produced provider-shaped plans. v9 adds an executable local mirror adapter for transfer rehearsals:

```bash
export MIND_CLOUD_OBJECT_MIRROR_DIR="./data/cloud-mirror"
export MIND_CLOUD_BACKUP_PROVIDER=s3
export MIND_CLOUD_BACKUP_BUCKET=mind-backups
export MIND_CLOUD_BACKUP_PREFIX=root
```

Protected route:

```text
POST /system/backups/root/cloud-mirror
POST /system/backups/root/signed-url-upload
```


## v12 worker, SDK, and consensus-apply layer

```text
scheduled job
  -> lease claim
  -> worker run report
  -> provider SDK receipt boundary
  -> consensus commit certificate
  -> exact-record follower apply
```

Protected API additions:

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

`POST /system/worker/run-once` can run in plan-only mode or mark claimed jobs as succeeded when `execute_and_mark_succeeded=true`. The worker path records leases and reports without bypassing the scheduler ledger.

`POST /system/consensus/log/apply` accepts a `ConsensusCommitCertificate` whose operation is a serialized `ReplicationBatch`. It verifies quorum against the active membership before calling the follower ingestion path.


## v13 worker daemon, provider features, and consensus idempotency

```text
scheduled job
  → database compare-and-swap lease claim
  → worker daemon tick
  → optional mark-succeeded execution mode
  → provider feature matrix
  → consensus apply idempotency guard
  → consensus log compaction decision
```

Protected API additions:

```text
GET  /system/worker/daemon-ticks
POST /system/worker/tick
GET  /system/provider/sdk/features
POST /system/consensus/log/apply-idempotent
POST /system/consensus/log/compact
```

Worker daemon example:

```bash
export MIND_EVENT_DB=./data/mind-events.sqlite
export MIND_WORKER_ID=worker-a
export MIND_WORKER_MODE=plan
export MIND_WORKER_MAX_TICKS=0
export MIND_WORKER_STOP_AFTER_IDLE_TICKS=5
cargo run -p mind-worker
```

SQLite claim semantics are intentionally CAS-shaped: a worker updates a pending job only when the stored `status`, `attempt_count`, and `payload_hash` still match the candidate it read. The lease record stores the claim hash and payload hash so the executed payload can be audited later.

New CLI commands:

```bash
cargo run -p mind-cli -- provider-sdk-features
cargo run -p mind-cli -- scheduler-claim-sqlite ./data/mind-events.sqlite worker-a 10 60
cargo run -p mind-cli -- worker-tick-sqlite ./data/mind-events.sqlite worker-a 10 plan
cargo run -p mind-cli -- consensus-apply-idempotency ./data/certificate.json ./data/apply-reports.json
cargo run -p mind-cli -- consensus-log-compact mind-cluster ./data/certificates.json ./data/apply-reports.json 64 128
```

## Maintenance commands

```bash
cargo run -p mind-cli -- demo
cargo run -p mind-cli -- audit-jsonl <root-mind-id> ./data/root.events.jsonl optional
cargo run -p mind-cli -- snapshot-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl optional
cargo run -p mind-cli -- compact-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl optional 3 25
cargo run -p mind-cli -- schema-sqlite ./data/mind-events.sqlite
cargo run -p mind-cli -- audit-events-jsonl ./data/observability.jsonl
cargo run -p mind-cli -- telemetry-jsonl ./data/observability.jsonl otlp_json
cargo run -p mind-cli -- backup-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl ./data/root.backup.json optional
cargo run -p mind-cli -- backup-object-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl ./data/object-store mind-backups optional
cargo run -p mind-cli -- verify-backup ./data/root.backup.json optional
cargo run -p mind-cli -- verify-object-backup ./data/object-store ./data/pointer.json optional
cargo run -p mind-cli -- restore-backup-jsonl ./data/root.backup.json ./restore/root.events.jsonl ./restore/root.snapshots.jsonl ./restore/observability.jsonl optional
cargo run -p mind-cli -- distributed-plan leader_replicated node-a leader 3
cargo run -p mind-cli -- verify-oidc-jwt ./config/jwks.json ./config/token.jwt https://issuer.example nested-mind-api
cargo run -p mind-cli -- oidc-discovery-refresh ./config/openid-configuration.json ./config/jwks.json https://issuer.example nested-mind-api RS256
cargo run -p mind-cli -- oidc-live-refresh https://issuer.example nested-mind-api RS256
cargo run -p mind-cli -- managed-signing-request ./data/commit.json aws_kms root-key arn:aws:kms:us-east-1:111122223333:key/demo <ed25519-public-key-hex>
cargo run -p mind-cli -- vendor-signing-execution ./data/managed-signing-request.json
cargo run -p mind-cli -- cloud-backup-plan-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl s3 mind-backups root optional
cargo run -p mind-cli -- cloud-backup-upload-mirror-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl s3 mind-backups root ./data/cloud-mirror optional
cargo run -p mind-cli -- cloud-backup-signed-url-jsonl <root-mind-id> ./data/root.events.jsonl ./data/root.snapshots.jsonl ./data/observability.jsonl <signed-url> mind-backups root/backup.json s3 optional
cargo run -p mind-cli -- replication-batch-jsonl <root-mind-id> ./data/root.events.jsonl leader-a 1 none optional
cargo run -p mind-cli -- replication-ingest-jsonl ./data/follower.events.jsonl ./data/replication-batch.json optional ./data/replication-inbox.jsonl
cargo run -p mind-cli -- replication-push-http ./data/replication-batch.json /system/replication/follower/batches node-b=http://node-b:8080,node-c=http://node-c:8080 3
cargo run -p mind-cli -- consensus-membership mind-cluster node-a,node-b,node-c node-a
cargo run -p mind-cli -- consensus-change ./data/membership.json ./data/consensus-change-proposal.json
cargo run -p mind-cli -- scheduler-job-jsonl ./data/scheduler.jsonl replication_delivery follower-a '{"batch_id":"batch-1"}' 0 3
cargo run -p mind-cli -- scheduler-due-jsonl ./data/scheduler.jsonl 10
cargo run -p mind-cli -- provider-execution-receipt ./data/provider-execution-request.json same
cargo run -p mind-cli -- consensus-commit ./data/membership.json replication_batch_commit '{"batch_id":"batch-1"}' node-a,node-b none
```

## Validation

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## Production fractures still open

```text
- Live OIDC discovery/JWKS refresh is implemented through HTTPS, but automatic background rotation is not implemented yet.
- Vendor signing has an HTTP gateway boundary; direct AWS/GCP/Azure/Vault/PKCS#11 SDK calls are still outside this repo.
- Cloud backup supports local mirror and signed-URL upload; direct S3/GCS/Azure SDK clients are not implemented yet.
- Outbound replication HTTP delivery has retry receipts and v11 scheduled-job records, but no always-on queue worker is implemented yet.
- Consensus membership changes and commit certificates are governed and ledgered, but no full consensus protocol or leader election loop is implemented yet.
- Rate limiting remains in-memory and per-process.
```


## v10 live connector layer

```text
live connector boundary
  -> OIDC/JWKS HTTP refresh
  -> signed URL backup upload
  -> replication HTTP delivery receipts
  -> governed consensus membership change
  -> SQLite v10 ledgers
```

New crate:

```text
crates/mind-connectors
```

New API routes:

```text
POST /system/oidc-verifier/refresh-live
POST /system/replication/outbound/batches
POST /system/consensus/membership/changes
POST /system/backups/root/signed-url-upload
```


## v11 durable operation layer

```text
durable scheduler
  -> provider execution receipt
  -> consensus commit certificate
  -> SQLite v11 ledgers
```

New protected API routes:

```text
GET  /system/scheduler/jobs
POST /system/scheduler/jobs
POST /system/scheduler/jobs/due
GET  /system/provider/execution-receipts
POST /system/provider/execution-receipts
GET  /system/consensus/commit-certificates
POST /system/consensus/commit-certificates
```


## v14 job receipts, native providers, physical compaction, and distributed leases

```text
scheduled job
  → CAS lease claim
  → receipt-producing executor
  → provider adapter capability check
  → optional distributed lease service boundary
  → backup-guarded physical consensus compaction
```

Protected API additions:

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

New CLI commands:

```bash
cargo run -p mind-cli -- job-receipt-json ./data/job.json worker-a plan
cargo run -p mind-cli -- distributed-lease-request ./data/job.json worker-a local-scheduler-lease 60
cargo run -p mind-cli -- native-provider-adapters
cargo run -p mind-cli -- native-provider-evaluate ./data/provider-execution-request.json
cargo run -p mind-cli -- consensus-physical-compact ./data/decision.json ./data/backup-verification.json plan
```

Native provider feature flags are available on `mind-core`, `mind-connectors`, `mind-api`, `mind-cli`, and `mind-worker`:

```text
provider-aws-kms
provider-aws-s3
provider-gcp-kms
provider-gcs
provider-azure-key-vault
provider-azure-blob
provider-vault
provider-pkcs11
provider-http-gateway
provider-local-mirror
```

The v14 kernel still treats native provider execution as a receipt boundary. Enabling a feature exposes capability state and request evaluation; provider-specific SDK calls must return hash-bound receipts before being considered production-ready.

Physical consensus compaction is no longer only a decision. v14 adds a guarded plan/report path:

```text
ConsensusLogCompactionDecision
  → BackupVerificationReport
  → ConsensusCompactionBackupGuard
  → ConsensusPhysicalCompactionPlan
  → ConsensusPhysicalCompactionReport
```

The SQLite implementation can delete compacted consensus certificates only after a backup guard is present. Apply reports remain preserved by default so retry/idempotency evidence is not silently erased.

## v15 layer: domain executors, lease adapters, provider receipts, retention enforcement

v15 adds the next production boundary:

```text
scheduled job
  → domain handler registry
  → required payload/evidence validation
  → job receipt
  → domain execution report
```

It also adds:

```text
+ distributed lease adapter reports
+ native provider execution receipts
+ consensus retention enforcement policy
+ SQLite schema version 15 ledgers
+ worker daemon domain-job report recording
```

New commands:

```bash
cargo run -p mind-cli -- domain-job-execute-json ./data/job.json worker-a plan
cargo run -p mind-cli -- distributed-lease-adapters
cargo run -p mind-cli -- distributed-lease-adapter-evaluate ./data/job.json worker-a sqlite 60
cargo run -p mind-cli -- native-provider-execute ./data/provider-execution-request.json dry-run
cargo run -p mind-cli -- consensus-retention-enforce ./data/decision.json ./data/backup-verification.json ./data/apply-reports.json plan
```

New API endpoints:

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

## v16 layer: live executors, lease execution receipts, provider SDK policy, retention approval

v16 adds the next production boundary:

```text
durable scheduled job
  → live domain executor
  → Postgres/etcd/SQlite lease execution receipt
  → provider SDK execution policy
  → consensus retention approval certificate
  → SQLite v16 operational ledgers
```

New runtime surfaces:

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

New CLI commands:

```bash
cargo run -p mind-cli -- live-domain-job-execute-json ./data/job.json worker-a plan
cargo run -p mind-cli -- distributed-lease-execute ./data/job.json worker-a postgres 60 postgres
cargo run -p mind-cli -- provider-sdk-execute ./data/provider-execution-request.json dry-run
cargo run -p mind-cli -- retention-approval ./data/retention-plan.json ./data/membership.json ./data/votes.json maintainer-a 2
```

New docs:

```text
docs/live-domain-job-executors.md
docs/postgres-etcd-lease-adapters.md
docs/provider-sdk-execution-policy.md
docs/retention-approval-workflow.md
docs/adr/0015-live-executors-lease-provider-retention-approval.md
```

## v17 creative engineering layer

v17 adds a planning and readiness plane:

```text
fractures / desired next layer
  → CreativeEngineeringReport
  → ChaosRehearsalPlan
  → InvariantFuzzRunReport
  → ProductionReadinessGateReport
```

New commands:

```bash
cargo run -p mind-cli -- creative-engineering-report pre_production "provider sdk pending,consensus loop incomplete"
cargo run -p mind-cli -- chaos-rehearsal-plan <mind-id>
cargo run -p mind-cli -- invariant-fuzz-run <mind-id> 64 17
cargo run -p mind-cli -- readiness-gate-demo <mind-id>
```

New API endpoints:

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

SQLite schema version is now `17` and includes ledgers for creative reports, chaos rehearsal plans, invariant fuzz runs, and readiness gates.

## v18 executable readiness evidence layer

v18 turns v17 planning artifacts into executable and schedulable evidence:

```text
ChaosRehearsalPlan
  → ChaosExecutionRun

InvariantFuzzRunReport
  → InvariantFuzzExecutionReport

ProductionReadinessGateReport
  → ReadinessWaiverProposal
  → ReadinessWaiverCertificate
  → ReadinessWaiverApplicationReport

CreativeEngineeringReport
  → EngineeringImplementationJobPlan
```

New CLI commands:

```bash
cargo run -p mind-cli -- chaos-rehearsal-execute ./data/chaos-plan.json dry-run
cargo run -p mind-cli -- invariant-fuzz-execute ./data/invariant-fuzz-run.json strict
cargo run -p mind-cli -- readiness-waiver-demo ./data/readiness-gate.json maintainer-a risk-owner-a 1
cargo run -p mind-cli -- engineering-jobs ./data/creative-engineering-report.json 5 0
```

New API endpoints:

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

SQLite schema version is now `18` and includes ledgers for chaos execution runs, invariant fuzz executions, readiness waivers, waiver applications, and engineering implementation job plans.

## v19 enforced readiness engineering layer

v19 adds:

```text
+ staging chaos runner reports
+ mandatory CI readiness gate reports
+ multi-operator waiver certificates
+ implementation evidence automation plans
+ PR/test/readiness/rollback evidence bundles
+ SQLite schema version 19
```

CLI examples:

```bash
cargo run -p mind-cli -- staging-chaos-run ./data/chaos-plan.json nested-mind-staging dry-run
cargo run -p mind-cli -- mandatory-ci-gate-demo ./data/readiness-gate.json ./data/fuzz-execution.json PR-19
cargo run -p mind-cli -- multi-operator-waiver-demo ./data/readiness-gate.json maintainer-a risk-owner-a
cargo run -p mind-cli -- implementation-evidence-automation ./data/engineering-job-plan.json mullusi/nested-mind-platform main
cargo run -p mind-cli -- implementation-evidence-bundle-demo ./data/engineering-job-plan.json
```

## v20 GitHub readiness and waiver-review layer

v20 adds:

```text
+ GitHub PR/check-run readiness evidence bundles
+ GitHub evidence connector scaffold
+ branch-protection policy generator/evaluator
+ live staging chaos adapter plan/receipt contracts
+ waiver review queue/certificate flow
+ SQLite schema version 20
```

CLI examples:

```bash
cargo run -p mind-cli -- github-evidence-demo mullusi/nested-mind-platform 20 demo-head-sha
cargo run -p mind-cli -- branch-protection-policy mullusi/nested-mind-platform main
cargo run -p mind-cli -- branch-protection-evaluate ./data/branch-policy.json cargo\ test,mandatory-readiness-gates
cargo run -p mind-cli -- live-chaos-adapter-plan ./data/chaos-plan.json none kubernetes dry-run
cargo run -p mind-cli -- waiver-review-demo ./data/readiness-gate.json
```

New ledgers:

```text
github_readiness_evidence_bundles
branch_protection_policies
branch_protection_evaluation_reports
live_staging_chaos_adapter_plans
live_staging_chaos_adapter_receipts
waiver_review_certificates
```

## v21 action enforcement layer

v21 adds executable action boundaries for GitHub readiness publishing, branch-protection reconciliation, Kubernetes staging chaos execution, and waiver reviewer assignment.

```text
GitHub/Kubernetes/waiver action intent
  → deterministic plan
  → external connector execution
  → hash-bound receipt
  → operational ledger
```

New modules:

```text
crates/mind-core/src/github_check_writer.rs
crates/mind-core/src/branch_protection_reconcile.rs
crates/mind-core/src/kubernetes_staging_chaos.rs
crates/mind-core/src/waiver_assignment.rs
```

## v22 live action execution boundary

v22 adds receipt-bound live action execution boundaries:

```text
+ GitHub App installation token exchange plan/receipt
+ GitHub action execution plan/receipt
+ branch-protection reconcile worker plan/report
+ Kubernetes server dry-run execution request/receipt
+ waiver notification plan/receipt
+ SQLite schema version 22 ledgers
```

The kernel records plans and receipts. Raw GitHub tokens, Kubernetes credentials, and notification-provider secrets remain connector/runtime concerns.


## v23 secret/action evidence layer

```text
secret manager reference
  → secret access receipt
  → GitHub App JWT receipt
  → connector worker execution receipt
  → Kubernetes admission/audit report
  → waiver notification adapter receipt
```

New modules:

```text
secret_manager_jwt
connector_execution_worker
kubernetes_admission_audit
waiver_notification_adapters
```

New CLI demos:

```bash
cargo run -p mind-cli -- github-secret-jwt-demo mullusi/nested-mind-platform 12345 67890
cargo run -p mind-cli -- connector-worker-demo connector-worker-a
cargo run -p mind-cli -- kubernetes-admission-audit-demo nested-mind-staging
cargo run -p mind-cli -- waiver-notification-adapter-demo ./data/waiver-notification-plan.json
```

## v25: Runtime-wired connector orchestration

v25 wires the v24 live connector objects through API, CLI, runtime store, and SQLite surfaces, then adds connector orchestration and action-promotion gates.

New kernel modules:

```text
connector_orchestration
kubernetes_audit_source_adapter
notification_provider_delivery
action_promotion_gate
```

New CLI rehearsals:

```bash
cargo run -p mind-cli -- live-secret-connector-demo
cargo run -p mind-cli -- github-token-exchange-worker-demo
cargo run -p mind-cli -- kubernetes-audit-log-collector-demo
cargo run -p mind-cli -- notification-delivery-client-demo ./data/waiver-notification-plan.json
cargo run -p mind-cli -- connector-orchestration-demo
cargo run -p mind-cli -- kubernetes-audit-source-demo
cargo run -p mind-cli -- notification-provider-delivery-demo ./data/waiver-notification-plan.json
cargo run -p mind-cli -- action-promotion-gate-demo
```

SQLite schema version is now `25`.
