# Schema migrations

Schema migration is now a first-class maintenance layer.

```text
schema_migrations(version, name, checksum, applied_at)
```

A migration is valid only when:

```text
checksum(migration body) = migration.checksum
version = current_version + 1
already-applied checksum = runtime checksum
```

The SQLite store applies migrations at open time. Existing v4/v5 databases with no migration ledger are handled by `CREATE TABLE IF NOT EXISTS` statements and then recorded in the ledger.

Current target:

```text
PLATFORM_SCHEMA_VERSION = 11
```

CLI:

```bash
cargo run -p mind-cli -- schema-sqlite ./data/mind-events.sqlite
```


Historical note: version 6 adds `backup_manifests`, which records backup id, optional mind id, backup hash, manifest JSON, and creation time.

## Version 7

```text
PLATFORM_SCHEMA_VERSION = 7
```

Version 7 adds operational metadata tables for identity bindings, signing-key descriptors, and object-backup receipts:

```text
identity_provider_bindings
signing_key_descriptors
backup_object_receipts
```

These tables do not change event-chain semantics. They record adapter metadata around the kernel.

## Version 8

```text
PLATFORM_SCHEMA_VERSION = 8
8 create_direct_identity_managed_signing_cloud_replication_ledgers
```

Adds ledgers for:

```text
- OIDC verifier configs
- managed signing requests
- cloud object backup plans
- replication batches
- replication acknowledgements
```

## v9 schema extension

```text
PLATFORM_SCHEMA_VERSION = 9
```

Migration 9 adds operational ledgers:

```text
oidc_jwks_cache
signing_execution_receipts
cloud_transfer_receipts
replication_inbox
consensus_memberships
```

These tables are metadata ledgers. They do not replace the canonical `mind_events` event chain.


## v10 schema extension

```text
PLATFORM_SCHEMA_VERSION = 10
```

Migration 10 adds operational ledgers:

```text
live_oidc_refreshes
cloud_signed_url_receipts
replication_delivery_receipts
consensus_change_judgments
```

These ledgers record adapter evidence and governed consensus-change judgments. They do not replace the canonical `mind_events` event chain.


## Schema version 10

Migration 10 adds operational ledgers for live connector receipts and governed consensus decisions:

```text
live_oidc_refreshes
cloud_signed_url_receipts
replication_delivery_receipts
consensus_change_judgments
```


## v11 schema extension

```text
PLATFORM_SCHEMA_VERSION = 11
```

Migration 11 adds durable operational ledgers:

```text
scheduled_jobs
provider_execution_receipts
consensus_commit_certificates
```

These tables persist retryable work, provider execution evidence, and quorum commit certificates. They do not replace the canonical `mind_events` event chain.

## v12 schema extension

```text
PLATFORM_SCHEMA_VERSION = 12
```

Migration 12 adds operational ledgers:

```text
scheduler_leases
worker_run_reports
provider_sdk_receipts
consensus_apply_reports
```

These tables record lease evidence, worker execution summaries, provider SDK receipts, and consensus-certified apply reports. They do not replace the canonical `mind_events` event chain.


## v13 schema extension

```text
PLATFORM_SCHEMA_VERSION = 13
```

Migration 13 adds operational ledgers:

```text
worker_daemon_ticks
provider_sdk_feature_matrices
consensus_apply_idempotency
consensus_log_compactions
```

These ledgers preserve worker daemon evidence, provider feature state, idempotency decisions, and consensus compaction decisions. They do not replace `mind_events`; they only explain and audit operational behavior around the canonical chain.


## v14 schema extension

```text
PLATFORM_SCHEMA_VERSION = 14
```

Migration 14 adds operational ledgers:

```text
job_execution_receipts
native_provider_adapter_reports
distributed_lease_claim_receipts
consensus_physical_compactions
```

These tables preserve execution receipts, native provider capability evaluations, distributed lease evidence, and backup-guarded physical consensus compaction reports. They do not replace the canonical `mind_events` chain.

## Version 15

v15 adds operational ledgers for:

```text
domain_job_execution_reports
distributed_lease_adapter_reports
native_provider_execution_receipts
consensus_retention_enforcements
```

These tables preserve execution and maintenance evidence. They do not replace `mind_events` as the canonical causal event chain.

## Version 16

Migration name:

```text
create_live_executors_lease_provider_retention_approval_ledgers
```

Tables:

```text
live_domain_job_execution_reports
distributed_lease_execution_receipts
provider_sdk_execution_reports
consensus_retention_approval_proposals
consensus_retention_approval_votes
consensus_retention_approval_certificates
```

Purpose:

```text
+ record live domain executor evidence
+ record backend-specific lease execution receipts
+ record provider SDK execution policy reports
+ record quorum-bound consensus retention approval certificates
```

## Version 17

Migration `17 create_creative_engineering_readiness_ledgers` adds:

```text
creative_engineering_reports
chaos_rehearsal_plans
invariant_fuzz_runs
production_readiness_gates
```

These tables preserve planning and readiness evidence. They do not replace the canonical event chain.

## Version 18

Migration 18 adds executable readiness evidence ledgers:

```text
chaos_execution_runs
invariant_fuzz_execution_reports
readiness_waiver_proposals
readiness_waiver_votes
readiness_waiver_certificates
readiness_waiver_application_reports
engineering_implementation_job_plans
```

These tables preserve operational evidence for chaos execution, invariant fuzz harness runs, waiver approvals, waiver application, and scheduled implementation jobs.

## v19 enforced readiness and engineering evidence

Migration 19 adds:

```text
staging_chaos_run_reports
mandatory_ci_gate_reports
multi_operator_waiver_certificates
implementation_job_evidence_bundles
implementation_evidence_automation_plans
```

## v20 GitHub readiness and review evidence

Migration 20 adds:

```text
github_readiness_evidence_bundles
branch_protection_policies
branch_protection_evaluation_reports
live_staging_chaos_adapter_plans
live_staging_chaos_adapter_receipts
waiver_review_certificates
```

Purpose:

```text
+ preserve PR/check-run readiness evidence
+ preserve generated branch-protection policy and evaluation evidence
+ preserve live staging chaos adapter plans and receipts
+ preserve waiver review certificates
```

## Version 21

Adds operational ledgers for external enforcement actions:

```text
github_check_run_write_plans
github_check_run_write_receipts
branch_protection_reconcile_plans
branch_protection_reconcile_receipts
kubernetes_staging_chaos_plans
kubernetes_staging_chaos_receipts
waiver_reviewer_assignment_plans
waiver_escalation_certificates
```

## v22 live action execution ledgers

```text
PLATFORM_SCHEMA_VERSION = 22
```

Migration 22 adds:

```text
github_app_installation_token_plans
github_app_installation_token_receipts
github_action_execution_plans
github_action_execution_receipts
branch_protection_worker_plans
branch_protection_worker_reports
kubernetes_dry_run_execution_requests
kubernetes_dry_run_execution_receipts
waiver_notification_plans
waiver_notification_receipts
```


## Version 23

Adds operational ledgers for:

```text
secret_access_plans
secret_access_receipts
github_app_jwt_plans
github_app_jwt_receipts
connector_worker_job_plans
connector_worker_execution_receipts
kubernetes_admission_audit_requests
kubernetes_admission_audit_receipts
kubernetes_admission_audit_reports
waiver_notification_adapter_plans
waiver_notification_adapter_receipts
```

## Version 24

Adds live worker connector ledgers:

```text
live_secret_connector_plans
live_secret_connector_receipts
github_token_exchange_worker_plans
github_token_exchange_worker_receipts
kubernetes_audit_log_collector_plans
kubernetes_audit_log_collector_reports
notification_delivery_client_plans
notification_delivery_client_receipts
```

## Version 25

Migration `25 create_connector_orchestration_audit_source_notification_provider_ledgers` adds:

```text
connector_orchestration_plans
connector_orchestration_reports
kubernetes_audit_source_adapter_plans
kubernetes_audit_source_adapter_receipts
notification_provider_delivery_plans
notification_provider_delivery_receipts
action_promotion_gate_reports
```
