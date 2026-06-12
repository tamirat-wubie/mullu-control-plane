use mind_connectors::{
    HttpOidcDiscoveryClient, HttpReplicationTransportClient, HttpSignedUrlObjectClient,
};
use mind_core::{
    apply_readiness_waivers_to_gate, apply_replication_batch, attach_implementation_evidence,
    certify_consensus_retention_approval, certify_multi_operator_readiness_waiver,
    certify_readiness_waiver, certify_waiver_escalation, certify_waiver_review,
    collect_github_readiness_evidence, default_implementation_evidence_requirements,
    distributed_lease_adapter_registry, domain_job_executor_registry,
    evaluate_branch_protection_policy, evaluate_consensus_apply_idempotency,
    evaluate_consensus_log_compaction, evaluate_distributed_lease_adapter_claim,
    evaluate_mandatory_ci_gate, evaluate_native_provider_request,
    evaluate_production_readiness_gate, execute_chaos_rehearsal_plan,
    execute_distributed_lease_with_receipt, execute_domain_job_with_receipt,
    execute_invariant_fuzz_run, execute_job_with_receipt, execute_live_domain_job,
    execute_live_staging_chaos_adapter_dry_run, execute_native_provider_with_receipt,
    execute_provider_sdk_with_policy, generate_creative_engineering_report,
    generate_invariant_fuzz_run, live_domain_job_executor_registry,
    native_provider_adapter_registry, open_waiver_review_queue_item,
    plan_branch_protection_reconcile, plan_branch_protection_reconcile_worker,
    plan_connector_worker_job, plan_consensus_retention_enforcement,
    plan_external_distributed_lease_claim, plan_github_app_installation_token,
    plan_github_app_jwt_from_secret, plan_github_check_run_action_execution,
    plan_github_check_run_write, plan_implementation_evidence_automation,
    plan_kubernetes_admission_audit, plan_kubernetes_server_dry_run_execution,
    plan_kubernetes_staging_chaos, plan_live_staging_chaos_adapter,
    plan_physical_consensus_compaction, plan_secret_access, plan_waiver_notification_adapter,
    plan_waiver_notification_delivery, plan_waiver_reviewer_assignment,
    production_branch_protection_policy, production_chaos_rehearsal_plan,
    record_branch_protection_reconcile_receipt, record_branch_protection_worker_report,
    record_connector_worker_execution_receipt, record_github_action_execution_receipt,
    record_github_app_installation_token_receipt, record_github_app_jwt_receipt,
    record_github_check_run_write_receipt, record_kubernetes_admission_audit_receipt,
    record_kubernetes_server_dry_run_receipt, record_kubernetes_staging_chaos_receipt,
    record_secret_access_receipt, record_waiver_notification_adapter_receipt,
    record_waiver_notification_receipt, report_consensus_retention_enforcement_planned,
    run_staging_chaos_rehearsal, schedule_engineering_implementation_jobs,
    synthetic_pull_request_evidence, AppendOnlyEventStore, BackupObjectRef, BackupRestoreMode,
    BranchProtectionObservedState, BranchProtectionPolicy, BranchProtectionReconcileMode,
    BranchProtectionWorkerMode, ChaosExecutionMode, CiCheckStatus, CloudObjectAdapter,
    CloudObjectProvider, CloudObjectStoreTarget, CloudSignedUrlRequest, CloudTransferMode,
    ClusterHealthReport, CompactingSnapshotStore, ConnectorWorkerActionKind, ConnectorWorkerMode,
    ConsensusChangeProposal, ConsensusCommitCertificate, ConsensusCommitVote,
    ConsensusCompactionBackupGuard, ConsensusLogCompactionPolicy, ConsensusLogEntry,
    ConsensusMember, ConsensusMembership, ConsensusPhysicalCompactionReport,
    ConsensusRetentionApprovalPolicy, ConsensusRetentionApprovalProposal,
    ConsensusRetentionApprovalVote, ConsensusRetentionPolicy, CreativeEngineeringReport,
    CreativeEngineeringReportInput, DistributedEventStorePlan, DistributedLeaseClaimReceipt,
    DistributedLeaseExecutionMode, DistributedLeaseServiceBoundary, DistributedNodeRole,
    Ed25519CommitSigner, EditProposal, EventStoreStrategy, EvolutionEngine, FileObjectBackupStore,
    FollowerReplicationProtocol, GitHubActionExecutionMode, GitHubAppInstallationTokenRequest,
    GitHubAppTokenMode, GitHubCheckConclusion, GitHubCheckRunEvidence, GitHubCheckRunOutput,
    GitHubCheckRunWriteMode, GitHubEvidenceSource, GitHubPullRequestEvidence, Identity,
    IdentityBindingPolicy, InMemoryEventStore, InvariantFuzzHarnessConfig, InvariantFuzzRunConfig,
    InvariantFuzzRunReport, JobExecutionMode, JsonBackupStore, JsonlEventStore,
    JsonlObservabilitySink, JsonlReplicationInbox, JsonlSchedulerQueue, JsonlSnapshotStore,
    KubernetesAdmissionAuditPolicy, KubernetesAdmissionOperation, KubernetesChaosExecutionMode,
    LawRule, LawbookMigration, LawbookMigrationOp, LeaderReplicationProtocol,
    LiveChaosAdapterBackend, LiveChaosAdapterMode, LiveDomainJobExecutorMode,
    LocalCloudMirrorStore, ManagedSigningAdapter, ManagedSigningKey, ManagedSigningProvider,
    MandatoryCiGateInput, MandatoryCiGatePolicy, Mind, MindBackup, MindError, MindId,
    MultiOperatorWaiverPolicy, MultiOperatorWaiverVote, NativeProviderAdapterRegistry,
    ObservabilitySink, OidcDiscoveryConfig, OidcDiscoveryDocument, OidcJwksCacheEntry,
    OidcJwksVerifier, OidcJwksVerifierConfig, ProductionReadinessGatePolicy,
    ProductionReadinessGateReport, ProjectionPolicy, ProviderExecutionReceipt,
    ProviderExecutionRequest, ProviderSdkExecutionPolicy, ProviderSdkFeatureMatrix,
    ReadinessWaiverProposal, ReadinessWaiverVote, ReadinessWaiverVoteDecision, ReplayAudit,
    ReplayEngine, ReplicationBatch, ReplicationCursor, ReplicationEndpoint, ReplicationEnvelope,
    ReplicationRetryPolicy, ReplicationTerm, ScheduledJob, ScheduledJobKind, SchedulerLeasePolicy,
    SchedulerPollReport, SecretAccessMode, SecretManagerBackend, SecretReference,
    SignatureRequirement, SnapshotCompactionPolicy, SnapshotRecord, SnapshotStore,
    StagingChaosEnvironment, StagingChaosRunMode, StagingChaosRunReport, StagingChaosSafetyPolicy,
    StatePatch, SymbolValue, TelemetryExportFormat, TelemetryExporter, VendorSigningAdapterReport,
    VendorSigningExecutionRequest, WaiverNotificationAdapterKind, WaiverNotificationAdapterMode,
    WaiverNotificationChannel, WaiverNotificationPlan, WaiverOperatorRole, WaiverReviewComment,
    WaiverReviewerAssignmentPlan, WaiverReviewerCandidate, WorkerDaemonConfig,
    WorkerDaemonTickReport, WorkerRuntimeMode, PLATFORM_SCHEMA_VERSION,
};
use mind_store_sqlite::SqliteEventStore;
use serde_json::json;
use std::{env, fs, process};
use time::{Duration, OffsetDateTime};

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(1);
    }
}

fn run() -> Result<(), MindError> {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        None | Some("demo") => demo(),
        Some("audit-jsonl") => audit_jsonl(&args[1..]),
        Some("snapshot-jsonl") => snapshot_jsonl(&args[1..]),
        Some("compact-jsonl") => compact_jsonl(&args[1..]),
        Some("schema-sqlite") => schema_sqlite(&args[1..]),
        Some("audit-events-jsonl") => audit_events_jsonl(&args[1..]),
        Some("telemetry-jsonl") => telemetry_jsonl(&args[1..]),
        Some("backup-jsonl") => backup_jsonl(&args[1..]),
        Some("backup-object-jsonl") => backup_object_jsonl(&args[1..]),
        Some("verify-backup") => verify_backup(&args[1..]),
        Some("verify-object-backup") => verify_object_backup(&args[1..]),
        Some("restore-backup-jsonl") => restore_backup_jsonl(&args[1..]),
        Some("distributed-plan") => distributed_plan(&args[1..]),
        Some("verify-oidc-jwt") => verify_oidc_jwt(&args[1..]),
        Some("managed-signing-request") => managed_signing_request(&args[1..]),
        Some("cloud-backup-plan-jsonl") => cloud_backup_plan_jsonl(&args[1..]),
        Some("replication-batch-jsonl") => replication_batch_jsonl(&args[1..]),
        Some("replication-ingest-jsonl") => replication_ingest_jsonl(&args[1..]),
        Some("replication-push-http") => replication_push_http(&args[1..]),
        Some("oidc-discovery-refresh") => oidc_discovery_refresh(&args[1..]),
        Some("oidc-live-refresh") => oidc_live_refresh(&args[1..]),
        Some("vendor-signing-execution") => vendor_signing_execution(&args[1..]),
        Some("cloud-backup-upload-mirror-jsonl") => cloud_backup_upload_mirror_jsonl(&args[1..]),
        Some("cloud-backup-signed-url-jsonl") => cloud_backup_signed_url_jsonl(&args[1..]),
        Some("consensus-membership") => consensus_membership(&args[1..]),
        Some("consensus-change") => consensus_change(&args[1..]),
        Some("scheduler-job-jsonl") => scheduler_job_jsonl(&args[1..]),
        Some("scheduler-due-jsonl") => scheduler_due_jsonl(&args[1..]),
        Some("provider-execution-receipt") => provider_execution_receipt(&args[1..]),
        Some("provider-sdk-features") => provider_sdk_features(&args[1..]),
        Some("scheduler-claim-sqlite") => scheduler_claim_sqlite(&args[1..]),
        Some("worker-tick-sqlite") => worker_tick_sqlite(&args[1..]),
        Some("consensus-apply-idempotency") => consensus_apply_idempotency(&args[1..]),
        Some("consensus-log-compact") => consensus_log_compact(&args[1..]),
        Some("job-receipt-json") => job_receipt_json(&args[1..]),
        Some("distributed-lease-request") => distributed_lease_request(&args[1..]),
        Some("native-provider-adapters") => native_provider_adapters(&args[1..]),
        Some("native-provider-evaluate") => native_provider_evaluate(&args[1..]),
        Some("consensus-physical-compact") => consensus_physical_compact(&args[1..]),
        Some("domain-job-execute-json") => domain_job_execute_json(&args[1..]),
        Some("distributed-lease-adapters") => distributed_lease_adapters(&args[1..]),
        Some("distributed-lease-adapter-evaluate") => distributed_lease_adapter_evaluate(&args[1..]),
        Some("native-provider-execute") => native_provider_execute(&args[1..]),
        Some("consensus-retention-enforce") => consensus_retention_enforce(&args[1..]),
        Some("live-domain-job-execute-json") => live_domain_job_execute_json(&args[1..]),
        Some("distributed-lease-execute") => distributed_lease_execute(&args[1..]),
        Some("provider-sdk-execute") => provider_sdk_execute(&args[1..]),
        Some("creative-engineering-report") => creative_engineering_report(&args[1..]),
        Some("chaos-rehearsal-plan") => chaos_rehearsal_plan(&args[1..]),
        Some("invariant-fuzz-run") => invariant_fuzz_run(&args[1..]),
        Some("readiness-gate-demo") => readiness_gate_demo(&args[1..]),
        Some("chaos-rehearsal-execute") => chaos_rehearsal_execute(&args[1..]),
        Some("invariant-fuzz-execute") => invariant_fuzz_execute(&args[1..]),
        Some("readiness-waiver-demo") => readiness_waiver_demo(&args[1..]),
        Some("engineering-jobs") => engineering_jobs(&args[1..]),
        Some("staging-chaos-run") => staging_chaos_run(&args[1..]),
        Some("mandatory-ci-gate-demo") => mandatory_ci_gate_demo(&args[1..]),
        Some("multi-operator-waiver-demo") => multi_operator_waiver_demo(&args[1..]),
        Some("implementation-evidence-automation") => implementation_evidence_automation(&args[1..]),
        Some("implementation-evidence-bundle-demo") => implementation_evidence_bundle_demo(&args[1..]),
        Some("github-evidence-demo") => github_evidence_demo(&args[1..]),
        Some("branch-protection-policy") => branch_protection_policy_cmd(&args[1..]),
        Some("branch-protection-evaluate") => branch_protection_evaluate_cmd(&args[1..]),
        Some("live-chaos-adapter-plan") => live_chaos_adapter_plan_cmd(&args[1..]),
        Some("waiver-review-demo") => waiver_review_demo(&args[1..]),
        Some("github-check-run-plan") | Some("github-check-run-write") => github_check_run_plan_cmd(&args[1..]),
        Some("branch-protection-reconcile") => branch_protection_reconcile_cmd(&args[1..]),
        Some("kubernetes-staging-chaos-plan") | Some("kubernetes-staging-chaos") => kubernetes_staging_chaos_plan_cmd(&args[1..]),
        Some("waiver-reviewer-assignment-demo") | Some("waiver-reviewer-assignments") => waiver_reviewer_assignment_demo(&args[1..]),
        Some("github-app-token-plan") => github_app_token_plan_cmd(&args[1..]),
        Some("github-action-execution-plan") => github_action_execution_plan_cmd(&args[1..]),
        Some("branch-protection-worker") => branch_protection_worker_cmd(&args[1..]),
        Some("kubernetes-dry-run-execute") => kubernetes_dry_run_execute_cmd(&args[1..]),
        Some("waiver-notification-delivery") => waiver_notification_delivery_cmd(&args[1..]),
        Some("github-secret-jwt-demo") => github_secret_jwt_demo(&args[1..]),
        Some("connector-worker-demo") => connector_worker_demo(&args[1..]),
        Some("kubernetes-admission-audit-demo") => kubernetes_admission_audit_demo(&args[1..]),
        Some("waiver-notification-adapter-demo") => waiver_notification_adapter_demo(&args[1..]),
        Some("live-secret-connector-demo") => live_secret_connector_demo(&args[1..]),
        Some("github-token-exchange-worker-demo") => github_token_exchange_worker_demo(&args[1..]),
        Some("kubernetes-audit-log-collector-demo") => kubernetes_audit_log_collector_demo(&args[1..]),
        Some("notification-delivery-client-demo") => notification_delivery_client_demo(&args[1..]),
        Some("connector-orchestration-demo") => connector_orchestration_demo(&args[1..]),
        Some("kubernetes-audit-source-demo") => kubernetes_audit_source_demo(&args[1..]),
        Some("notification-provider-delivery-demo") => notification_provider_delivery_demo(&args[1..]),
        Some("action-promotion-gate-demo") => action_promotion_gate_demo(&args[1..]),
        Some("retention-approval") => retention_approval(&args[1..]),
        Some("consensus-commit") => consensus_commit(&args[1..]),
        Some(other) => Err(MindError::Store(format!("unknown command `{other}`; expected demo, audit-jsonl, snapshot-jsonl, compact-jsonl, schema-sqlite, audit-events-jsonl, telemetry-jsonl, backup-jsonl, backup-object-jsonl, verify-backup, verify-object-backup, restore-backup-jsonl, distributed-plan, verify-oidc-jwt, managed-signing-request, cloud-backup-plan-jsonl, replication-batch-jsonl, replication-ingest-jsonl, replication-push-http, oidc-discovery-refresh, oidc-live-refresh, vendor-signing-execution, cloud-backup-upload-mirror-jsonl, cloud-backup-signed-url-jsonl, consensus-membership, consensus-change, scheduler-job-jsonl, scheduler-due-jsonl, provider-execution-receipt, provider-sdk-features, scheduler-claim-sqlite, worker-tick-sqlite, consensus-apply-idempotency, consensus-log-compact, consensus-commit, job-receipt-json, distributed-lease-request, native-provider-adapters, native-provider-evaluate, consensus-physical-compact, domain-job-execute-json, distributed-lease-adapters, distributed-lease-adapter-evaluate, native-provider-execute, consensus-retention-enforce, live-domain-job-execute-json, distributed-lease-execute, provider-sdk-execute, creative-engineering-report, chaos-rehearsal-plan, invariant-fuzz-run, readiness-gate-demo, readiness-gate-demo, chaos-rehearsal-execute, invariant-fuzz-execute, readiness-waiver-demo, engineering-jobs, staging-chaos-run, mandatory-ci-gate-demo, multi-operator-waiver-demo, implementation-evidence-automation, implementation-evidence-bundle-demo, github-evidence-demo, branch-protection-policy, branch-protection-evaluate, live-chaos-adapter-plan, waiver-review-demo, github-check-run-write, branch-protection-reconcile, kubernetes-staging-chaos, waiver-reviewer-assignments, github-app-token-plan, github-action-execution-plan, branch-protection-worker, kubernetes-dry-run-execute, waiver-notification-delivery, or retention-approval"))),
    }
}

fn demo() -> Result<(), MindError> {
    let mut root = Mind::new_root("root");
    let identity = root.identity().clone();
    let signer = Ed25519CommitSigner::from_seed("cli-demo-ed25519", [7_u8; 32]);
    let mut event_store =
        InMemoryEventStore::new().with_signature_requirement(SignatureRequirement::Required);

    let mut attach_plan = EvolutionEngine::evaluate_child_attachment(
        &root,
        Identity::child(root.id(), "planner"),
        "cli",
        "attach planner child mind",
    )?;
    attach_plan.commit_mut().sign_with(&signer)?;
    event_store.append(attach_plan.commit().clone())?;
    EvolutionEngine::apply_plan(&mut root, attach_plan)?;

    let patch = StatePatch::new()
        .set("goal", SymbolValue::from("nested symbolic minds"))
        .set("secret.operator_token", SymbolValue::from("demo-secret"));
    let proposal = EditProposal::new(root.id(), "cli", "initialize root goal", patch);
    let mut plan = EvolutionEngine::evaluate(&root, proposal)?;
    plan.commit_mut().sign_with(&signer)?;
    event_store.append(plan.commit().clone())?;
    let commit = EvolutionEngine::apply_plan(&mut root, plan)?;

    let migration = LawbookMigration::new(
        root.lawbook().version(),
        root.lawbook().version() + 1,
        "cli",
        "forbid password cells",
        vec![LawbookMigrationOp::AddRule {
            rule: LawRule::ForbidKey {
                key: "password".to_owned(),
            },
        }],
    );
    let mut migration_plan = EvolutionEngine::evaluate_lawbook_migration(&root, migration)?;
    migration_plan.commit_mut().sign_with(&signer)?;
    event_store.append(migration_plan.commit().clone())?;
    let migration_commit = EvolutionEngine::apply_plan(&mut root, migration_plan)?;

    let records = event_store.records_for_mind(root.id())?;
    let (_, replay_report) = ReplayEngine::replay_with_signature_requirement(
        identity.clone(),
        &records,
        SignatureRequirement::Required,
    )?;
    let snapshot = SnapshotRecord::capture(&root, records.last())?;
    let audit = ReplayAudit::audit_from_snapshot(&snapshot, &[], SignatureRequirement::Required);
    let compaction = SnapshotCompactionPolicy::default().evaluate(
        root.id(),
        records.last().map_or(0, |record| record.sequence),
        std::slice::from_ref(&snapshot),
    )?;
    let public_projection =
        mind_core::MindProjection::with_policy(&root, &ProjectionPolicy::public_default());
    let output = json!({
        "commit": commit,
        "migration_commit": migration_commit,
        "snapshot": snapshot,
        "snapshot_compaction": compaction,
        "audit": audit,
        "replay": replay_report,
        "public_projection": public_projection,
        "signer_public_key_hex": signer.public_key_hex()
    });
    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}

fn audit_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let signature_requirement = parse_signature_requirement(args.get(2).map(String::as_str));
    let identity = Identity::root_with_id(
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?,
        "root",
    );
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let records = event_store.records_for_mind(identity.id)?;
    let audit = ReplayAudit::audit_full(identity, &records, signature_requirement);
    println!("{}", serde_json::to_string_pretty(&audit)?);
    Ok(())
}

fn snapshot_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let signature_requirement = parse_signature_requirement(args.get(3).map(String::as_str));
    let identity = Identity::root_with_id(
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?,
        "root",
    );
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let records = event_store.records_for_mind(identity.id)?;
    let (mind, _) =
        ReplayEngine::replay_with_signature_requirement(identity, &records, signature_requirement)?;
    let snapshot = SnapshotRecord::capture(&mind, records.last())?;
    let mut snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let saved = snapshot_store.save_snapshot(snapshot)?;
    println!("{}", serde_json::to_string_pretty(&saved)?);
    Ok(())
}

fn compact_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let signature_requirement = parse_signature_requirement(args.get(3).map(String::as_str));
    let keep_latest = args
        .get(4)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(3);
    let min_events = args
        .get(5)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(25);
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let records = event_store.records_for_mind(mind_id)?;
    let latest_sequence = records.last().map_or(0, |record| record.sequence);
    let mut snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let policy = SnapshotCompactionPolicy::new(keep_latest, min_events);
    let decision = snapshot_store.compact_snapshots(mind_id, &policy, latest_sequence)?;
    println!("{}", serde_json::to_string_pretty(&decision)?);
    Ok(())
}

fn schema_sqlite(args: &[String]) -> Result<(), MindError> {
    let db = required_arg(args, 0, "mind-events.sqlite")?;
    let store = SqliteEventStore::open(db)?;
    println!("{}", serde_json::to_string_pretty(&store.schema_report()?)?);
    Ok(())
}

fn audit_events_jsonl(args: &[String]) -> Result<(), MindError> {
    let log = required_arg(args, 0, "observability.jsonl")?;
    let sink = JsonlObservabilitySink::new(log)?;
    println!("{}", serde_json::to_string_pretty(&sink.audit_events()?)?);
    Ok(())
}

fn telemetry_jsonl(args: &[String]) -> Result<(), MindError> {
    let log = required_arg(args, 0, "observability.jsonl")?;
    let format = match args.get(1).map(String::as_str) {
        Some("otlp_json") | Some("otlp") => TelemetryExportFormat::OtlpJson,
        _ => TelemetryExportFormat::InternalJson,
    };
    let sink = JsonlObservabilitySink::new(log)?;
    let export = TelemetryExporter::export(format, sink.trace_events()?, sink.audit_events()?)?;
    println!("{}", serde_json::to_string_pretty(&export)?);
    Ok(())
}

fn backup_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let observability_log = required_arg(args, 3, "observability.jsonl")?;
    let backup_path = required_arg(args, 4, "backup.json")?;
    let signature_requirement = parse_signature_requirement(args.get(5).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let observability = JsonlObservabilitySink::new(observability_log)?;
    let backup = MindBackup::capture(
        Some(mind_id),
        event_store.records_for_mind(mind_id)?,
        snapshot_store.snapshots_for_mind(mind_id)?,
        observability.trace_events()?,
        observability.audit_events()?,
        PLATFORM_SCHEMA_VERSION,
    )?;
    let report = backup.verify(signature_requirement)?;
    JsonBackupStore::new(backup_path)?.save(&backup)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn backup_object_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let observability_log = required_arg(args, 3, "observability.jsonl")?;
    let object_dir = required_arg(args, 4, "object-dir")?;
    let bucket = args
        .get(5)
        .cloned()
        .unwrap_or_else(|| "mind-backups".to_owned());
    let signature_requirement = parse_signature_requirement(args.get(6).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let observability = JsonlObservabilitySink::new(observability_log)?;
    let backup = MindBackup::capture(
        Some(mind_id),
        event_store.records_for_mind(mind_id)?,
        snapshot_store.snapshots_for_mind(mind_id)?,
        observability.trace_events()?,
        observability.audit_events()?,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(signature_requirement)?;
    let store = FileObjectBackupStore::new(object_dir)?;
    let key = format!("{}/{}.json", mind_id, backup.manifest.backup_id);
    let pointer = store.put_verified_backup(bucket, key, &backup, signature_requirement)?;
    println!("{}", serde_json::to_string_pretty(&pointer)?);
    Ok(())
}

fn verify_object_backup(args: &[String]) -> Result<(), MindError> {
    let object_dir = required_arg(args, 0, "object-dir")?;
    let pointer_path = required_arg(args, 1, "pointer.json")?;
    let signature_requirement = parse_signature_requirement(args.get(2).map(String::as_str));
    let pointer = serde_json::from_str::<BackupObjectRef>(&fs::read_to_string(pointer_path)?)?;
    let report =
        FileObjectBackupStore::new(object_dir)?.verify_pointer(&pointer, signature_requirement)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn distributed_plan(args: &[String]) -> Result<(), MindError> {
    let strategy = args.first().map(String::as_str).unwrap_or("single_writer");
    let node_id = args.get(1).cloned().unwrap_or_else(|| "local".to_owned());
    let role = args.get(2).map(String::as_str).unwrap_or("single");
    let voting_members = args
        .get(3)
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(1);
    let plan = match strategy {
        "leader_replicated" => match role {
            "leader" => DistributedEventStorePlan::leader(node_id, voting_members),
            _ => DistributedEventStorePlan::follower(node_id, voting_members),
        },
        "consensus" | "consensus_replicated" => DistributedEventStorePlan {
            strategy: EventStoreStrategy::ConsensusReplicated,
            node_id,
            role: parse_cli_node_role(role),
            voting_members,
            quorum_size: voting_members / 2 + 1,
            allow_local_appends: matches!(parse_cli_node_role(role), DistributedNodeRole::Leader),
            replication_lag_limit_events: Some(128),
        },
        "object_archived_follower" => DistributedEventStorePlan {
            strategy: EventStoreStrategy::ObjectArchivedFollower,
            node_id,
            role: DistributedNodeRole::Follower,
            voting_members: 1,
            quorum_size: 1,
            allow_local_appends: false,
            replication_lag_limit_events: Some(0),
        },
        _ => DistributedEventStorePlan::single_writer(node_id),
    };
    plan.validate()?;
    let report = ClusterHealthReport::from_plan(plan)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn parse_cli_node_role(value: &str) -> DistributedNodeRole {
    match value {
        "leader" => DistributedNodeRole::Leader,
        "follower" => DistributedNodeRole::Follower,
        "witness" => DistributedNodeRole::Witness,
        "learner" => DistributedNodeRole::Learner,
        _ => DistributedNodeRole::Single,
    }
}

fn verify_backup(args: &[String]) -> Result<(), MindError> {
    let backup_path = required_arg(args, 0, "backup.json")?;
    let signature_requirement = parse_signature_requirement(args.get(1).map(String::as_str));
    let backup = JsonBackupStore::new(backup_path)?.load()?;
    println!(
        "{}",
        serde_json::to_string_pretty(&backup.verify(signature_requirement)?)?
    );
    Ok(())
}

fn restore_backup_jsonl(args: &[String]) -> Result<(), MindError> {
    let backup_path = required_arg(args, 0, "backup.json")?;
    let event_log = required_arg(args, 1, "event-log-out.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log-out.jsonl")?;
    let observability_log = args
        .get(3)
        .filter(|value| !matches!(value.as_str(), "optional" | "required" | "none"))
        .cloned();
    let signature_index = if observability_log.is_some() { 4 } else { 3 };
    let signature_requirement =
        parse_signature_requirement(args.get(signature_index).map(String::as_str));
    let report = JsonBackupStore::new(backup_path)?.restore_to_jsonl(
        event_log,
        snapshot_log,
        observability_log,
        signature_requirement,
        BackupRestoreMode::NewFilesOnly,
    )?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn verify_oidc_jwt(args: &[String]) -> Result<(), MindError> {
    let jwks_path = required_arg(args, 0, "jwks.json")?;
    let jwt_path = required_arg(args, 1, "jwt.txt")?;
    let issuer = required_arg(args, 2, "issuer")?;
    let audience = required_arg(args, 3, "audience")?;
    let jwks_json = fs::read_to_string(jwks_path)?;
    let jwt = fs::read_to_string(jwt_path)?;
    let config = OidcJwksVerifierConfig::new(issuer.clone()).with_audience(audience.clone());
    let binding = IdentityBindingPolicy::default()
        .allow_issuer(issuer)
        .require_audience(audience);
    let report = OidcJwksVerifier::from_jwks_json(config, &jwks_json)?
        .verify_with_report(jwt.trim(), &binding)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn managed_signing_request(args: &[String]) -> Result<(), MindError> {
    let commit_path = required_arg(args, 0, "commit.json")?;
    let provider =
        parse_managed_signing_provider(args.get(1).map(String::as_str).unwrap_or("aws_kms"));
    let key_id = required_arg(args, 2, "key-id")?;
    let resource = required_arg(args, 3, "provider-key-resource")?;
    let public_key_hex = required_arg(args, 4, "public-key-hex")?;
    let commit: mind_core::Commit = serde_json::from_str(&fs::read_to_string(commit_path)?)?;
    let key = ManagedSigningKey::ed25519(provider, key_id, resource, public_key_hex);
    let adapter = ManagedSigningAdapter::new(key)?;
    let request = adapter.prepare(&commit)?;
    println!("{}", serde_json::to_string_pretty(&request)?);
    Ok(())
}

fn cloud_backup_plan_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let observability_log = required_arg(args, 3, "observability.jsonl")?;
    let provider = parse_cloud_provider(args.get(4).map(String::as_str).unwrap_or("s3"));
    let bucket = required_arg(args, 5, "bucket-or-container")?;
    let prefix = args
        .get(6)
        .cloned()
        .unwrap_or_else(|| "mind-backups".to_owned());
    let signature_requirement = parse_signature_requirement(args.get(7).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let observability = JsonlObservabilitySink::new(observability_log)?;
    let backup = MindBackup::capture(
        Some(mind_id),
        event_store.records_for_mind(mind_id)?,
        snapshot_store.snapshots_for_mind(mind_id)?,
        observability.trace_events()?,
        observability.audit_events()?,
        PLATFORM_SCHEMA_VERSION,
    )?;
    let target = CloudObjectStoreTarget::new(provider, bucket, prefix);
    let plan = CloudObjectAdapter::new(target)?.plan_backup_put(&backup, signature_requirement)?;
    println!("{}", serde_json::to_string_pretty(&plan)?);
    Ok(())
}

fn replication_batch_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let leader_id = args
        .get(2)
        .cloned()
        .unwrap_or_else(|| "leader-a".to_owned());
    let next_sequence = args
        .get(3)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    let previous_record_hash = args
        .get(4)
        .filter(|value| !value.trim().is_empty() && value.as_str() != "none")
        .cloned();
    let signature_requirement = parse_signature_requirement(args.get(5).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let records = event_store.records_for_mind(mind_id)?;
    let cursor = ReplicationCursor {
        mind_id,
        next_sequence,
        previous_record_hash,
    };
    let leader = LeaderReplicationProtocol::new(ReplicationTerm::new(1, leader_id), 100, 1);
    let batch = leader.prepare_batch(cursor.clone(), &records, signature_requirement)?;
    let follower =
        FollowerReplicationProtocol::new("follower-preview", cursor, signature_requirement);
    let ack = follower.validate_batch(&batch)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"batch": batch, "follower_ack": ack}))?
    );
    Ok(())
}

fn oidc_discovery_refresh(args: &[String]) -> Result<(), MindError> {
    let discovery_path = required_arg(args, 0, "openid-configuration.json")?;
    let jwks_path = required_arg(args, 1, "jwks.json")?;
    let issuer = required_arg(args, 2, "issuer")?;
    let audience = required_arg(args, 3, "audience")?;
    let mut config = OidcDiscoveryConfig::new(issuer.clone()).with_audience(audience);
    if let Some(algorithms) = args.get(4) {
        config.allowed_algorithms = algorithms
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .collect();
    }
    let document =
        serde_json::from_str::<OidcDiscoveryDocument>(&fs::read_to_string(discovery_path)?)?;
    document.validate_for(&config)?;
    let jwks_json = fs::read_to_string(jwks_path)?;
    let cache = OidcJwksCacheEntry::from_jwks_json(
        issuer,
        document.jwks_uri.clone(),
        jwks_json,
        Some(config.refresh_ttl_seconds),
    )?;
    let report = mind_core::OidcDiscoveryRefreshReport::refreshed(&config, &document, &cache)?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"document": document, "cache": cache, "report": report})
        )?
    );
    Ok(())
}

fn oidc_live_refresh(args: &[String]) -> Result<(), MindError> {
    let issuer = required_arg(args, 0, "issuer")?;
    let audience = required_arg(args, 1, "audience")?;
    let mut config = OidcDiscoveryConfig::new(issuer).with_audience(audience);
    if let Some(algorithms) = args.get(2) {
        config.allowed_algorithms = algorithms
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .collect();
    }
    let runtime =
        tokio::runtime::Runtime::new().map_err(|error| MindError::Store(error.to_string()))?;
    let report =
        runtime.block_on(async { HttpOidcDiscoveryClient::new().refresh(&config).await })?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn vendor_signing_execution(args: &[String]) -> Result<(), MindError> {
    let request_path = required_arg(args, 0, "managed-signing-request.json")?;
    let request: mind_core::ManagedSigningRequest =
        serde_json::from_str(&fs::read_to_string(request_path)?)?;
    let execution = VendorSigningExecutionRequest::from_request(&request);
    let report = VendorSigningAdapterReport::from_execution_request(&execution);
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"execution": execution, "report": report}))?
    );
    Ok(())
}

fn cloud_backup_upload_mirror_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let observability_log = required_arg(args, 3, "observability.jsonl")?;
    let provider = parse_cloud_provider(args.get(4).map(String::as_str).unwrap_or("s3"));
    let bucket = required_arg(args, 5, "bucket-or-container")?;
    let prefix = args
        .get(6)
        .cloned()
        .unwrap_or_else(|| "mind-backups".to_owned());
    let mirror_dir = required_arg(args, 7, "cloud-mirror-dir")?;
    let signature_requirement = parse_signature_requirement(args.get(8).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let observability = JsonlObservabilitySink::new(observability_log)?;
    let backup = MindBackup::capture(
        Some(mind_id),
        event_store.records_for_mind(mind_id)?,
        snapshot_store.snapshots_for_mind(mind_id)?,
        observability.trace_events()?,
        observability.audit_events()?,
        PLATFORM_SCHEMA_VERSION,
    )?;
    let target = CloudObjectStoreTarget::new(provider, bucket, prefix);
    let plan = CloudObjectAdapter::new(target)?.plan_backup_put(&backup, signature_requirement)?;
    let request =
        mind_core::CloudUploadExecutionRequest::from_plan(&plan, CloudTransferMode::LocalMirror);
    let receipt = LocalCloudMirrorStore::new(mirror_dir)?.put_backup(
        &plan,
        &backup,
        signature_requirement,
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"request": request, "receipt": receipt}))?
    );
    Ok(())
}

fn cloud_backup_signed_url_jsonl(args: &[String]) -> Result<(), MindError> {
    let root_id = required_arg(args, 0, "root-mind-id")?;
    let event_log = required_arg(args, 1, "event-log.jsonl")?;
    let snapshot_log = required_arg(args, 2, "snapshot-log.jsonl")?;
    let observability_log = required_arg(args, 3, "observability.jsonl")?;
    let signed_url = required_arg(args, 4, "signed-url")?;
    let bucket = required_arg(args, 5, "bucket-or-container")?;
    let key = required_arg(args, 6, "object-key")?;
    let provider = parse_cloud_provider(args.get(7).map(String::as_str).unwrap_or("s3"));
    let signature_requirement = parse_signature_requirement(args.get(8).map(String::as_str));
    let mind_id =
        MindId::parse_str(&root_id).map_err(|error| MindError::Store(error.to_string()))?;
    let event_store =
        JsonlEventStore::new(event_log)?.with_signature_requirement(signature_requirement);
    let snapshot_store = JsonlSnapshotStore::new(snapshot_log)?;
    let observability = JsonlObservabilitySink::new(observability_log)?;
    let backup = MindBackup::capture(
        Some(mind_id),
        event_store.records_for_mind(mind_id)?,
        snapshot_store.snapshots_for_mind(mind_id)?,
        observability.trace_events()?,
        observability.audit_events()?,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(signature_requirement)?;
    let request = CloudSignedUrlRequest::put_backup(provider, signed_url, bucket, key, &backup)?;
    let runtime =
        tokio::runtime::Runtime::new().map_err(|error| MindError::Store(error.to_string()))?;
    let receipt = runtime.block_on(async {
        HttpSignedUrlObjectClient::new()
            .put_backup(&request, &backup)
            .await
    })?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"request": request, "receipt": receipt}))?
    );
    Ok(())
}

fn replication_ingest_jsonl(args: &[String]) -> Result<(), MindError> {
    let follower_event_log = required_arg(args, 0, "follower-event-log.jsonl")?;
    let batch_path = required_arg(args, 1, "replication-batch.json")?;
    let signature_requirement = parse_signature_requirement(args.get(2).map(String::as_str));
    let inbox_log = args
        .get(3)
        .filter(|value| !value.trim().is_empty() && value.as_str() != "none")
        .cloned();
    let batch = serde_json::from_str::<ReplicationBatch>(&fs::read_to_string(batch_path)?)?;
    let envelope = ReplicationEnvelope::from_batch(batch.clone())?;
    if let Some(inbox_log) = inbox_log {
        JsonlReplicationInbox::new(inbox_log)?.append_envelope(&envelope)?;
    }
    let mut store =
        JsonlEventStore::new(follower_event_log)?.with_signature_requirement(signature_requirement);
    let report = apply_replication_batch(&mut store, "cli-follower", &batch)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"envelope": envelope, "apply_report": report}))?
    );
    Ok(())
}

fn replication_push_http(args: &[String]) -> Result<(), MindError> {
    let batch_path = required_arg(args, 0, "replication-batch.json")?;
    let push_path = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "/system/replication/follower/batches".to_owned());
    let endpoints_csv = required_arg(args, 2, "endpoint=node-url[,endpoint=node-url]")?;
    let max_attempts = args
        .get(3)
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(3);
    let batch = serde_json::from_str::<ReplicationBatch>(&fs::read_to_string(batch_path)?)?;
    let envelope = ReplicationEnvelope::from_batch(batch)?;
    let endpoints = endpoints_csv
        .split(',')
        .map(parse_replication_endpoint)
        .collect::<Result<Vec<_>, _>>()?;
    let policy = ReplicationRetryPolicy {
        max_attempts,
        ..ReplicationRetryPolicy::default()
    };
    let runtime =
        tokio::runtime::Runtime::new().map_err(|error| MindError::Store(error.to_string()))?;
    let client = HttpReplicationTransportClient::new(policy, None)?;
    let mut receipts = Vec::new();
    for endpoint in endpoints {
        receipts.push(
            runtime.block_on(async { client.deliver(&endpoint, &push_path, &envelope).await })?,
        );
    }
    println!("{}", serde_json::to_string_pretty(&receipts)?);
    Ok(())
}

fn consensus_membership(args: &[String]) -> Result<(), MindError> {
    let cluster_id = args
        .first()
        .cloned()
        .unwrap_or_else(|| "local-cluster".to_owned());
    let members_csv = args.get(1).cloned().unwrap_or_else(|| "node-a".to_owned());
    let members = members_csv
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ConsensusMember::voter)
        .collect::<Vec<_>>();
    let mut membership = ConsensusMembership::new(cluster_id, members);
    if let Some(leader_id) = args.get(2) {
        if !leader_id.trim().is_empty() {
            membership =
                membership.apply_change(mind_core::ConsensusMembershipChange::SetLeader {
                    member_id: leader_id.clone(),
                })?;
        }
    }
    membership.validate()?;
    println!("{}", serde_json::to_string_pretty(&membership)?);
    Ok(())
}

fn consensus_change(args: &[String]) -> Result<(), MindError> {
    let membership_path = required_arg(args, 0, "membership.json")?;
    let proposal_path = required_arg(args, 1, "proposal.json")?;
    let membership =
        serde_json::from_str::<ConsensusMembership>(&fs::read_to_string(membership_path)?)?;
    let proposal =
        serde_json::from_str::<ConsensusChangeProposal>(&fs::read_to_string(proposal_path)?)?;
    let judgment = proposal.evaluate(&membership)?;
    judgment.verify_transition(&membership)?;
    println!("{}", serde_json::to_string_pretty(&judgment)?);
    Ok(())
}

fn scheduler_job_jsonl(args: &[String]) -> Result<(), MindError> {
    let scheduler_log = required_arg(args, 0, "scheduler-log.jsonl")?;
    let kind = parse_scheduled_job_kind(&required_arg(args, 1, "job-kind")?);
    let target = required_arg(args, 2, "target")?;
    let payload_json = args.get(3).cloned().unwrap_or_else(|| "{}".to_owned());
    let payload = serde_json::from_str::<serde_json::Value>(&payload_json)?;
    let due_in_seconds = args
        .get(4)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0);
    let max_attempts = args
        .get(5)
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(3);
    let due_at = OffsetDateTime::now_utc() + Duration::seconds(due_in_seconds as i64);
    let job = ScheduledJob::new(kind, target, &payload, due_at, max_attempts)?;
    JsonlSchedulerQueue::new(scheduler_log)?.append_job(&job)?;
    println!("{}", serde_json::to_string_pretty(&job)?);
    Ok(())
}

fn scheduler_due_jsonl(args: &[String]) -> Result<(), MindError> {
    let scheduler_log = required_arg(args, 0, "scheduler-log.jsonl")?;
    let limit = args
        .get(1)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(10);
    let now = OffsetDateTime::now_utc();
    let jobs = JsonlSchedulerQueue::new(scheduler_log)?.due_jobs(now, limit.max(1))?;
    let report = SchedulerPollReport::from_jobs(now, jobs);
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn provider_execution_receipt(args: &[String]) -> Result<(), MindError> {
    let request_path = required_arg(args, 0, "provider-execution-request.json")?;
    let request =
        serde_json::from_str::<ProviderExecutionRequest>(&fs::read_to_string(request_path)?)?;
    let observed_hash = args
        .get(1)
        .filter(|value| value.as_str() != "same")
        .cloned()
        .unwrap_or_else(|| request.payload_hash.clone());
    let receipt = ProviderExecutionReceipt::succeeded(&request, observed_hash);
    receipt.verify_for(&request)?;
    println!("{}", serde_json::to_string_pretty(&receipt)?);
    Ok(())
}

fn consensus_commit(args: &[String]) -> Result<(), MindError> {
    let membership_path = required_arg(args, 0, "membership.json")?;
    let operation_kind = required_arg(args, 1, "operation-kind")?;
    let operation_json = args.get(2).cloned().unwrap_or_else(|| "{}".to_owned());
    let operation = serde_json::from_str::<serde_json::Value>(&operation_json)?;
    let membership =
        serde_json::from_str::<ConsensusMembership>(&fs::read_to_string(membership_path)?)?;
    let leader_id = membership
        .leader_id
        .clone()
        .or_else(|| {
            membership
                .voting_members()
                .first()
                .map(|member| member.member_id.clone())
        })
        .ok_or_else(|| MindError::DistributedPlanInvalid {
            reason: "consensus membership has no voting leader candidate".to_owned(),
        })?;
    let previous_entry_hash = args
        .get(4)
        .filter(|value| value.as_str() != "none")
        .cloned();
    let entry = ConsensusLogEntry::new(
        &membership,
        leader_id,
        operation_kind,
        &operation,
        previous_entry_hash,
    )?;
    let voters = args
        .get(3)
        .map(|csv| {
            csv.split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
                .collect::<Vec<_>>()
        })
        .filter(|values| !values.is_empty())
        .unwrap_or_else(|| {
            membership
                .voting_members()
                .into_iter()
                .map(|member| member.member_id.clone())
                .collect()
        });
    let votes = voters
        .into_iter()
        .map(|voter| ConsensusCommitVote::accept(&entry, voter))
        .collect::<Vec<_>>();
    let certificate = ConsensusCommitCertificate::certify(&membership, entry, votes)?;
    println!("{}", serde_json::to_string_pretty(&certificate)?);
    Ok(())
}

fn provider_sdk_features(_args: &[String]) -> Result<(), MindError> {
    let matrix = ProviderSdkFeatureMatrix::conservative_default();
    println!("{}", serde_json::to_string_pretty(&matrix)?);
    Ok(())
}

fn scheduler_claim_sqlite(args: &[String]) -> Result<(), MindError> {
    let db = required_arg(args, 0, "mind-events.sqlite")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let limit = args
        .get(2)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(10);
    let lease_seconds = args
        .get(3)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    let policy = SchedulerLeasePolicy {
        max_claims_per_poll: limit.max(1),
        lease_seconds,
    };
    let now = OffsetDateTime::now_utc();
    let mut store = SqliteEventStore::open(db)?;
    let report = store.claim_due_jobs_for_worker(worker_id, &policy, limit.max(1), now)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn worker_tick_sqlite(args: &[String]) -> Result<(), MindError> {
    let db = required_arg(args, 0, "mind-events.sqlite")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let limit = args
        .get(2)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(10);
    let mode = match args.get(3).map(String::as_str) {
        Some("execute") | Some("execute_and_mark_succeeded") => {
            WorkerRuntimeMode::ExecuteAndMarkSucceeded
        }
        _ => WorkerRuntimeMode::PlanOnly,
    };
    let policy = SchedulerLeasePolicy {
        max_claims_per_poll: limit.max(1),
        ..SchedulerLeasePolicy::default()
    };
    let config = WorkerDaemonConfig::new(worker_id.clone())?
        .with_mode(mode)
        .with_lease_policy(policy)
        .with_max_jobs_per_tick(limit.max(1));
    let mut store = SqliteEventStore::open(db)?;
    let now = OffsetDateTime::now_utc();
    let claim_report =
        store.claim_due_jobs_for_worker(worker_id, &config.lease_policy, limit.max(1), now)?;
    let tick = WorkerDaemonTickReport::from_claim_report(&config, 0, claim_report, now)?;
    let receipt_mode = match config.mode {
        WorkerRuntimeMode::PlanOnly => JobExecutionMode::PlanOnly,
        WorkerRuntimeMode::ExecuteAndMarkSucceeded => JobExecutionMode::LocalExecutor,
    };
    for job in &tick.claim_report.updated_jobs {
        let lease = tick
            .claim_report
            .leases
            .iter()
            .find(|lease| lease.job_id == job.job_id);
        let receipt = execute_job_with_receipt(job, &config.worker_id, lease, receipt_mode)?;
        store.record_job_execution_receipt(&receipt)?;
    }
    for job in &tick.updated_jobs {
        store.record_scheduled_job(job)?;
    }
    store.record_worker_daemon_tick(&tick)?;
    println!("{}", serde_json::to_string_pretty(&tick)?);
    Ok(())
}

fn consensus_apply_idempotency(args: &[String]) -> Result<(), MindError> {
    let certificate_path = required_arg(args, 0, "certificate.json")?;
    let reports_path = required_arg(args, 1, "apply-reports.json")?;
    let certificate =
        serde_json::from_str::<ConsensusCommitCertificate>(&fs::read_to_string(certificate_path)?)?;
    let reports = serde_json::from_str::<Vec<mind_core::ConsensusApplyReport>>(
        &fs::read_to_string(reports_path)?,
    )?;
    let decision = evaluate_consensus_apply_idempotency(&certificate, &reports);
    println!("{}", serde_json::to_string_pretty(&decision)?);
    Ok(())
}

fn consensus_log_compact(args: &[String]) -> Result<(), MindError> {
    let cluster_id = required_arg(args, 0, "cluster-id")?;
    let certificates_path = required_arg(args, 1, "certificates.json")?;
    let reports_path = required_arg(args, 2, "apply-reports.json")?;
    let keep_latest = args
        .get(3)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(64);
    let min_between = args
        .get(4)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(128);
    let certificates = serde_json::from_str::<Vec<ConsensusCommitCertificate>>(
        &fs::read_to_string(certificates_path)?,
    )?;
    let reports = serde_json::from_str::<Vec<mind_core::ConsensusApplyReport>>(
        &fs::read_to_string(reports_path)?,
    )?;
    let policy = ConsensusLogCompactionPolicy {
        keep_latest_committed: keep_latest,
        min_committed_entries_between_compactions: min_between,
    };
    let decision = evaluate_consensus_log_compaction(cluster_id, &certificates, &reports, &policy)?;
    println!("{}", serde_json::to_string_pretty(&decision)?);
    Ok(())
}

fn job_receipt_json(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let mode = match args.get(2).map(String::as_str) {
        Some("execute") | Some("local") | Some("local_executor") => JobExecutionMode::LocalExecutor,
        Some("receipt") | Some("receipt_only") => JobExecutionMode::ReceiptOnly,
        _ => JobExecutionMode::PlanOnly,
    };
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let receipt = execute_job_with_receipt(&job, worker_id, None, mode)?;
    println!("{}", serde_json::to_string_pretty(&receipt)?);
    Ok(())
}

fn distributed_lease_request(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let service_id = args
        .get(2)
        .cloned()
        .unwrap_or_else(|| "local-scheduler-lease".to_owned());
    let lease_seconds = args
        .get(3)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let policy = SchedulerLeasePolicy {
        lease_seconds,
        ..SchedulerLeasePolicy::default()
    };
    let boundary = DistributedLeaseServiceBoundary::sqlite_local(service_id)?;
    let plan = plan_external_distributed_lease_claim(&boundary, &job, worker_id, &policy)?;
    let receipt = DistributedLeaseClaimReceipt::granted(&boundary, &plan.request);
    receipt.verify_for(&plan.request)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"plan": plan, "receipt": receipt}))?
    );
    Ok(())
}

fn native_provider_adapters(_args: &[String]) -> Result<(), MindError> {
    let registry: NativeProviderAdapterRegistry = native_provider_adapter_registry();
    println!("{}", serde_json::to_string_pretty(&registry)?);
    Ok(())
}

fn native_provider_evaluate(args: &[String]) -> Result<(), MindError> {
    let request_path = required_arg(args, 0, "provider-execution-request.json")?;
    let request =
        serde_json::from_str::<ProviderExecutionRequest>(&fs::read_to_string(request_path)?)?;
    let registry = native_provider_adapter_registry();
    let report = evaluate_native_provider_request(&request, &registry)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn consensus_physical_compact(args: &[String]) -> Result<(), MindError> {
    let decision_path = required_arg(args, 0, "consensus-compaction-decision.json")?;
    let backup_verification_path = required_arg(args, 1, "backup-verification.json")?;
    let apply = matches!(args.get(2).map(String::as_str), Some("apply"));
    let decision = serde_json::from_str::<mind_core::ConsensusLogCompactionDecision>(
        &fs::read_to_string(decision_path)?,
    )?;
    let verification = serde_json::from_str::<mind_core::BackupVerificationReport>(
        &fs::read_to_string(backup_verification_path)?,
    )?;
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(&decision, &verification)?;
    let plan = plan_physical_consensus_compaction(&decision, guard)?;
    let report = if apply {
        ConsensusPhysicalCompactionReport::applied(&plan, plan.certificate_ids_to_delete.len(), 0)
    } else {
        ConsensusPhysicalCompactionReport::planned(&plan)
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"plan": plan, "report": report}))?
    );
    Ok(())
}

fn domain_job_execute_json(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let mode = match args.get(2).map(String::as_str) {
        Some("execute") | Some("local") | Some("local_executor") => JobExecutionMode::LocalExecutor,
        Some("receipt") | Some("receipt_only") => JobExecutionMode::ReceiptOnly,
        _ => JobExecutionMode::PlanOnly,
    };
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let registry = domain_job_executor_registry();
    let report = execute_domain_job_with_receipt(&job, worker_id, None, mode, &registry)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn distributed_lease_adapters(_args: &[String]) -> Result<(), MindError> {
    println!(
        "{}",
        serde_json::to_string_pretty(&distributed_lease_adapter_registry())?
    );
    Ok(())
}

fn distributed_lease_adapter_evaluate(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let backend = args.get(2).map(String::as_str).unwrap_or("sqlite");
    let lease_seconds = args
        .get(3)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let policy = SchedulerLeasePolicy {
        lease_seconds,
        ..SchedulerLeasePolicy::default()
    };
    let boundary = match backend.trim().to_ascii_lowercase().as_str() {
        "gateway" | "http" | "external" => DistributedLeaseServiceBoundary::external_gateway(
            "external-lease-gateway",
            env::var("MIND_LEASE_GATEWAY_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:8088".to_owned()),
            lease_seconds,
        )?,
        _ => DistributedLeaseServiceBoundary::sqlite_local("local-scheduler-lease")?,
    };
    let registry = distributed_lease_adapter_registry();
    let report =
        evaluate_distributed_lease_adapter_claim(&boundary, &job, worker_id, &policy, &registry)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn native_provider_execute(args: &[String]) -> Result<(), MindError> {
    let request_path = required_arg(args, 0, "provider-execution-request.json")?;
    let allow_dry_run = matches!(
        args.get(1).map(String::as_str),
        Some("dry-run") | Some("dry_run") | Some("allow-dry-run")
    );
    let request =
        serde_json::from_str::<ProviderExecutionRequest>(&fs::read_to_string(request_path)?)?;
    let registry = native_provider_adapter_registry();
    let receipt = execute_native_provider_with_receipt(&request, &registry, allow_dry_run)?;
    println!("{}", serde_json::to_string_pretty(&receipt)?);
    Ok(())
}

fn consensus_retention_enforce(args: &[String]) -> Result<(), MindError> {
    let decision_path = required_arg(args, 0, "consensus-compaction-decision.json")?;
    let backup_verification_path = required_arg(args, 1, "backup-verification.json")?;
    let apply_reports_path = required_arg(args, 2, "apply-reports.json")?;
    let apply = matches!(args.get(3).map(String::as_str), Some("apply"));
    let delete_apply_reports = matches!(
        args.get(4).map(String::as_str),
        Some("delete-apply-reports") | Some("true")
    );
    let keep_latest_apply_reports = args
        .get(5)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(128);
    let decision = serde_json::from_str::<mind_core::ConsensusLogCompactionDecision>(
        &fs::read_to_string(decision_path)?,
    )?;
    let verification = serde_json::from_str::<mind_core::BackupVerificationReport>(
        &fs::read_to_string(backup_verification_path)?,
    )?;
    let apply_reports = serde_json::from_str::<Vec<mind_core::ConsensusApplyReport>>(
        &fs::read_to_string(apply_reports_path)?,
    )?;
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(&decision, &verification)?;
    let physical_plan = plan_physical_consensus_compaction(&decision, guard)?;
    let policy = ConsensusRetentionPolicy {
        delete_apply_reports,
        keep_latest_apply_reports,
        ..ConsensusRetentionPolicy::default()
    };
    let plan =
        plan_consensus_retention_enforcement(&decision, &physical_plan, &apply_reports, &policy)?;
    let report = if apply {
        mind_core::report_consensus_retention_enforcement_applied(
            &plan,
            plan.certificate_ids_to_delete.len(),
            plan.apply_report_ids_to_delete.len(),
        )
    } else {
        report_consensus_retention_enforcement_planned(&plan)
    };
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"plan": plan, "report": report}))?
    );
    Ok(())
}

fn parse_replication_endpoint(value: &str) -> Result<ReplicationEndpoint, MindError> {
    let mut parts = value.splitn(2, '=');
    let node_id = parts.next().unwrap_or_default().trim();
    let base_url = parts.next().unwrap_or_default().trim();
    if node_id.is_empty() || base_url.is_empty() {
        return Err(MindError::DistributedPlanInvalid {
            reason: "replication endpoint must use node_id=base_url".to_owned(),
        });
    }
    Ok(ReplicationEndpoint::new(node_id, base_url))
}

fn parse_scheduled_job_kind(value: &str) -> ScheduledJobKind {
    match value.trim().to_ascii_lowercase().as_str() {
        "oidc" | "oidc_jwks_refresh" | "jwks_refresh" => ScheduledJobKind::OidcJwksRefresh,
        "signing" | "signing_execution" => ScheduledJobKind::SigningExecution,
        "cloud" | "cloud_backup_upload" | "object_upload" => ScheduledJobKind::CloudBackupUpload,
        "replication" | "replication_delivery" => ScheduledJobKind::ReplicationDelivery,
        "snapshot" | "snapshot_compaction" => ScheduledJobKind::SnapshotCompaction,
        "backup" | "backup_verification" => ScheduledJobKind::BackupVerification,
        "consensus" | "consensus_commit" => ScheduledJobKind::ConsensusCommit,
        _ => ScheduledJobKind::ProviderExecution,
    }
}

fn parse_cloud_provider(value: &str) -> CloudObjectProvider {
    match value.trim().to_ascii_lowercase().as_str() {
        "gcs" | "google" | "google_cloud_storage" => CloudObjectProvider::Gcs,
        "azure" | "azure_blob" => CloudObjectProvider::AzureBlob,
        _ => CloudObjectProvider::S3Compatible,
    }
}

fn parse_managed_signing_provider(value: &str) -> ManagedSigningProvider {
    match value.trim().to_ascii_lowercase().as_str() {
        "gcp" | "gcp_cloud_kms" | "cloud_kms" => ManagedSigningProvider::GcpCloudKms,
        "azure" | "azure_key_vault" | "key_vault" => ManagedSigningProvider::AzureKeyVault,
        "vault" | "hashicorp_vault" => ManagedSigningProvider::HashicorpVault,
        "pkcs11" | "pkcs11_hsm" | "hsm" => ManagedSigningProvider::Pkcs11Hsm,
        _ => ManagedSigningProvider::AwsKms,
    }
}

fn required_arg(args: &[String], index: usize, name: &str) -> Result<String, MindError> {
    args.get(index)
        .cloned()
        .ok_or_else(|| MindError::Store(format!("missing required argument {name}")))
}

fn parse_signature_requirement(value: Option<&str>) -> SignatureRequirement {
    match value.map(str::to_ascii_lowercase).as_deref() {
        Some("required") | Some("require") | Some("true") | Some("1") => {
            SignatureRequirement::Required
        }
        _ => SignatureRequirement::Optional,
    }
}

fn live_domain_job_execute_json(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let mode = match args.get(2).map(String::as_str) {
        Some("local") | Some("simulate") | Some("local_simulation") => {
            Some(LiveDomainJobExecutorMode::LocalSimulation)
        }
        Some("receipt") | Some("receipt_only") => Some(LiveDomainJobExecutorMode::ReceiptOnly),
        Some("plan") | Some("plan_only") => Some(LiveDomainJobExecutorMode::PlanOnly),
        _ => None,
    };
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let registry = live_domain_job_executor_registry();
    let report = execute_live_domain_job(&job, worker_id, None, mode, &registry)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn distributed_lease_execute(args: &[String]) -> Result<(), MindError> {
    let job_path = required_arg(args, 0, "job.json")?;
    let worker_id = required_arg(args, 1, "worker-id")?;
    let backend = args.get(2).map(String::as_str).unwrap_or("sqlite");
    let lease_seconds = args
        .get(3)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(60);
    let mode = match args.get(4).map(String::as_str) {
        Some("postgres") | Some("postgres_advisory_lock") => {
            DistributedLeaseExecutionMode::PostgresAdvisoryLock
        }
        Some("etcd") | Some("etcd_txn") => DistributedLeaseExecutionMode::EtcdTxn,
        Some("gateway") | Some("external") => DistributedLeaseExecutionMode::ExternalGateway,
        Some("sqlite") | Some("sqlite_cas") => DistributedLeaseExecutionMode::SqliteCompareAndSwap,
        _ => DistributedLeaseExecutionMode::PlanOnly,
    };
    let job = serde_json::from_str::<ScheduledJob>(&fs::read_to_string(job_path)?)?;
    let policy = SchedulerLeasePolicy {
        lease_seconds,
        ..SchedulerLeasePolicy::default()
    };
    let boundary = match backend.trim().to_ascii_lowercase().as_str() {
        "postgres" | "postgres_advisory_lock" => DistributedLeaseServiceBoundary::new(
            mind_core::DistributedLeaseBackendKind::PostgresAdvisoryLock,
            "postgres-scheduler-lease",
            env::var("DATABASE_URL").ok(),
            lease_seconds,
        )?,
        "etcd" | "etcd_lease" => DistributedLeaseServiceBoundary::new(
            mind_core::DistributedLeaseBackendKind::EtcdLease,
            "etcd-scheduler-lease",
            env::var("ETCD_ENDPOINTS").ok(),
            lease_seconds,
        )?,
        "gateway" | "external" => DistributedLeaseServiceBoundary::external_gateway(
            "external-lease-gateway",
            env::var("MIND_LEASE_GATEWAY_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:8088".to_owned()),
            lease_seconds,
        )?,
        _ => DistributedLeaseServiceBoundary::sqlite_local("local-scheduler-lease")?,
    };
    let registry = distributed_lease_adapter_registry();
    let receipt = execute_distributed_lease_with_receipt(
        &boundary, &job, worker_id, &policy, &registry, mode,
    )?;
    println!("{}", serde_json::to_string_pretty(&receipt)?);
    Ok(())
}

fn provider_sdk_execute(args: &[String]) -> Result<(), MindError> {
    let request_path = required_arg(args, 0, "provider-execution-request.json")?;
    let policy = match args.get(1).map(String::as_str) {
        Some("native") | Some("native_required") => {
            ProviderSdkExecutionPolicy::NativeFeatureRequired
        }
        Some("gateway") | Some("external_receipt") => {
            ProviderSdkExecutionPolicy::ExternalReceiptRequired
        }
        Some("plan") | Some("plan_only") => ProviderSdkExecutionPolicy::PlanOnly,
        _ => ProviderSdkExecutionPolicy::DryRunAllowed,
    };
    let request =
        serde_json::from_str::<ProviderExecutionRequest>(&fs::read_to_string(request_path)?)?;
    let registry = native_provider_adapter_registry();
    let report = execute_provider_sdk_with_policy(&request, &registry, policy)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn retention_approval(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "retention-plan.json")?;
    let membership_path = required_arg(args, 1, "membership.json")?;
    let votes_path = required_arg(args, 2, "votes.json")?;
    let proposed_by = args
        .get(3)
        .cloned()
        .unwrap_or_else(|| "cli-maintainer".to_owned());
    let minimum_approvals = args
        .get(4)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1);
    let plan = serde_json::from_str::<mind_core::ConsensusRetentionEnforcementPlan>(
        &fs::read_to_string(plan_path)?,
    )?;
    let membership =
        serde_json::from_str::<ConsensusMembership>(&fs::read_to_string(membership_path)?)?;
    let votes = serde_json::from_str::<Vec<ConsensusRetentionApprovalVote>>(&fs::read_to_string(
        votes_path,
    )?)?;
    let proposal = ConsensusRetentionApprovalProposal::from_plan(&plan, &membership, proposed_by)?;
    let policy = ConsensusRetentionApprovalPolicy {
        minimum_approvals,
        ..ConsensusRetentionApprovalPolicy::default()
    };
    let certificate =
        certify_consensus_retention_approval(&proposal, &membership, &policy, &votes)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"proposal": proposal, "certificate": certificate}))?
    );
    Ok(())
}

fn creative_engineering_report(args: &[String]) -> Result<(), MindError> {
    let mut input = CreativeEngineeringReportInput::default();
    if let Some(stage) = args.first() {
        input.deployment_stage = stage.clone();
    }
    if let Some(fractures_csv) = args.get(1) {
        input.observed_fractures = fractures_csv
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned)
            .collect();
    }
    if let Some(next_layer) = args.get(2) {
        input.desired_next_layer = next_layer.clone();
    }
    let report = generate_creative_engineering_report(input)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn chaos_rehearsal_plan(args: &[String]) -> Result<(), MindError> {
    let mind_id = match args.first() {
        Some(value) if value != "none" => {
            Some(MindId::parse_str(value).map_err(|error| MindError::Store(error.to_string()))?)
        }
        _ => None,
    };
    let plan = production_chaos_rehearsal_plan(mind_id)?;
    println!("{}", serde_json::to_string_pretty(&plan)?);
    Ok(())
}

fn invariant_fuzz_run(args: &[String]) -> Result<(), MindError> {
    let mind_id = MindId::parse_str(&required_arg(args, 0, "mind-id")?)
        .map_err(|error| MindError::Store(error.to_string()))?;
    let mut config = InvariantFuzzRunConfig::default();
    if let Some(cases) = args.get(1).and_then(|value| value.parse::<usize>().ok()) {
        config.cases = cases;
    }
    if let Some(seed) = args.get(2).and_then(|value| value.parse::<u64>().ok()) {
        config.seed = seed;
    }
    let report = generate_invariant_fuzz_run(mind_id, config)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn readiness_gate_demo(args: &[String]) -> Result<(), MindError> {
    let mind_id = MindId::parse_str(&required_arg(args, 0, "mind-id")?)
        .map_err(|error| MindError::Store(error.to_string()))?;
    let input = CreativeEngineeringReportInput {
        observed_fractures: vec![
            "provider SDK live adapters pending".to_owned(),
            "consensus leader loop incomplete".to_owned(),
        ],
        ..CreativeEngineeringReportInput::default()
    };
    let creative = generate_creative_engineering_report(input)?;
    let chaos = production_chaos_rehearsal_plan(Some(mind_id))?;
    let fuzz = generate_invariant_fuzz_run(mind_id, InvariantFuzzRunConfig::default())?;
    let gate = evaluate_production_readiness_gate(
        &creative,
        Some(&chaos),
        Some(&fuzz),
        ProductionReadinessGatePolicy::default(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "creative_report": creative,
            "chaos_plan": chaos,
            "invariant_fuzz_run": fuzz,
            "readiness_gate": gate
        }))?
    );
    Ok(())
}

fn chaos_rehearsal_execute(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "chaos-plan.json")?;
    let plan =
        serde_json::from_str::<mind_core::ChaosRehearsalPlan>(&fs::read_to_string(plan_path)?)?;
    let mode = match args.get(1).map(String::as_str) {
        Some("plan") | Some("plan_only") => ChaosExecutionMode::PlanOnly,
        _ => ChaosExecutionMode::DeterministicDryRun,
    };
    let run = execute_chaos_rehearsal_plan(&plan, mode)?;
    println!("{}", serde_json::to_string_pretty(&run)?);
    Ok(())
}

fn invariant_fuzz_execute(args: &[String]) -> Result<(), MindError> {
    let run_path = required_arg(args, 0, "invariant-fuzz-run.json")?;
    let run = serde_json::from_str::<InvariantFuzzRunReport>(&fs::read_to_string(run_path)?)?;
    let mut config = InvariantFuzzHarnessConfig::default();
    if matches!(
        args.get(1).map(String::as_str),
        Some("open") | Some("no_strict")
    ) {
        config.strict_forbid_password = false;
    }
    let report = execute_invariant_fuzz_run(&run, config)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn readiness_waiver_demo(args: &[String]) -> Result<(), MindError> {
    let gate_path = required_arg(args, 0, "readiness-gate.json")?;
    let gate =
        serde_json::from_str::<ProductionReadinessGateReport>(&fs::read_to_string(gate_path)?)?;
    let proposed_by = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "maintainer-a".to_owned());
    let risk_owner = args.get(2).cloned().unwrap_or_else(|| proposed_by.clone());
    let required_approvals = args
        .get(3)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(1);
    let blocker_ids = gate
        .blockers
        .iter()
        .map(|blocker| blocker.blocker_id)
        .collect::<Vec<_>>();
    let proposal = mind_core::ReadinessWaiverProposal::new(
        &gate,
        blocker_ids,
        proposed_by.clone(),
        "temporary governed waiver for staging-only promotion",
        risk_owner,
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )?;
    let vote = ReadinessWaiverVote::new(
        proposal.proposal_id,
        proposed_by,
        ReadinessWaiverVoteDecision::Approve,
        "approval binds risk owner to follow-up remediation jobs",
    )?;
    let certificate = certify_readiness_waiver(proposal, vec![vote], required_approvals)?;
    let application = apply_readiness_waivers_to_gate(&gate, std::slice::from_ref(&certificate))?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "certificate": certificate,
            "application": application
        }))?
    );
    Ok(())
}

fn engineering_jobs(args: &[String]) -> Result<(), MindError> {
    let report_path = required_arg(args, 0, "creative-engineering-report.json")?;
    let report =
        serde_json::from_str::<CreativeEngineeringReport>(&fs::read_to_string(report_path)?)?;
    let limit = args
        .get(1)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(5);
    let due_in_seconds = args
        .get(2)
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(0);
    let plan = schedule_engineering_implementation_jobs(&report, limit, due_in_seconds)?;
    println!("{}", serde_json::to_string_pretty(&plan)?);
    Ok(())
}

fn staging_chaos_run(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "chaos-plan.json")?;
    let plan =
        serde_json::from_str::<mind_core::ChaosRehearsalPlan>(&fs::read_to_string(plan_path)?)?;
    let namespace = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "nested-mind-staging".to_owned());
    let mode = match args.get(2).map(String::as_str) {
        Some("live") | Some("live_staging") => StagingChaosRunMode::LiveStaging,
        Some("plan") | Some("plan_only") => StagingChaosRunMode::PlanOnly,
        _ => StagingChaosRunMode::GuardedDryRun,
    };
    let mut environment = StagingChaosEnvironment::staging(namespace);
    if let Some(approval_hash) = args.get(3) {
        environment.approval_certificate_hash = Some(approval_hash.clone());
    }
    let report = run_staging_chaos_rehearsal(
        &plan,
        environment,
        mode,
        StagingChaosSafetyPolicy::default(),
    )?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn mandatory_ci_gate_demo(args: &[String]) -> Result<(), MindError> {
    let readiness_gate_path = required_arg(args, 0, "readiness-gate.json")?;
    let fuzz_execution_path = required_arg(args, 1, "invariant-fuzz-execution.json")?;
    let gate = serde_json::from_str::<ProductionReadinessGateReport>(&fs::read_to_string(
        readiness_gate_path,
    )?)?;
    let fuzz = serde_json::from_str::<mind_core::InvariantFuzzExecutionReport>(
        &fs::read_to_string(fuzz_execution_path)?,
    )?;
    let input = MandatoryCiGateInput {
        rust_format: CiCheckStatus::Passed,
        clippy: CiCheckStatus::Passed,
        unit_tests: CiCheckStatus::Passed,
        executable_readiness_tests: CiCheckStatus::Passed,
        readiness_gate: Some(gate),
        chaos_execution: None,
        invariant_fuzz_execution: Some(fuzz),
        staging_chaos: None,
        pull_request: args.get(2).cloned(),
    };
    let report = evaluate_mandatory_ci_gate(input, MandatoryCiGatePolicy::default())?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn multi_operator_waiver_demo(args: &[String]) -> Result<(), MindError> {
    let gate_path = required_arg(args, 0, "readiness-gate.json")?;
    let gate =
        serde_json::from_str::<ProductionReadinessGateReport>(&fs::read_to_string(gate_path)?)?;
    let proposer = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "maintainer-a".to_owned());
    let risk_owner = args
        .get(2)
        .cloned()
        .unwrap_or_else(|| "risk-owner-a".to_owned());
    let blocker_ids = gate
        .blockers
        .iter()
        .map(|blocker| blocker.blocker_id)
        .collect::<Vec<_>>();
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        blocker_ids,
        proposer,
        "multi-operator staging waiver with explicit remediation follow-up",
        risk_owner,
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )?;
    let votes = vec![
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "maintainer-a",
            WaiverOperatorRole::Maintainer,
            "platform",
            ReadinessWaiverVoteDecision::Approve,
            "implementation risk accepted for staging only",
        )?,
        MultiOperatorWaiverVote::new(
            proposal.proposal_id,
            "security-a",
            WaiverOperatorRole::Security,
            "security",
            ReadinessWaiverVoteDecision::Approve,
            "secret and signature blockers remain tracked",
        )?,
    ];
    let certificate = certify_multi_operator_readiness_waiver(
        proposal,
        &gate,
        votes,
        MultiOperatorWaiverPolicy::default(),
    )?;
    println!("{}", serde_json::to_string_pretty(&certificate)?);
    Ok(())
}

fn implementation_evidence_automation(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "engineering-implementation-job-plan.json")?;
    let plan = serde_json::from_str::<mind_core::EngineeringImplementationJobPlan>(
        &fs::read_to_string(plan_path)?,
    )?;
    let repo = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let base = args.get(2).cloned().unwrap_or_else(|| "main".to_owned());
    let automation = plan_implementation_evidence_automation(&plan, repo, base)?;
    println!("{}", serde_json::to_string_pretty(&automation)?);
    Ok(())
}

fn implementation_evidence_bundle_demo(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "engineering-implementation-job-plan.json")?;
    let plan = serde_json::from_str::<mind_core::EngineeringImplementationJobPlan>(
        &fs::read_to_string(plan_path)?,
    )?;
    let automation =
        plan_implementation_evidence_automation(&plan, "mullusi/nested-mind-platform", "main")?;
    let job = plan
        .jobs
        .first()
        .ok_or_else(|| MindError::Store("implementation plan contains no jobs".to_owned()))?;
    let target = automation
        .targets
        .first()
        .ok_or_else(|| MindError::Store("automation plan contains no targets".to_owned()))?;
    let mut artifacts = synthetic_pull_request_evidence(target, "mind-cli")?;
    artifacts.push(mind_core::ImplementationEvidenceArtifact::new(
        mind_core::ImplementationEvidenceKind::ReadinessGate,
        "mandatory readiness gate report",
        format!("readiness://{}", target.target_id),
        "mind-cli",
        std::collections::BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
    )?);
    artifacts.push(mind_core::ImplementationEvidenceArtifact::new(
        mind_core::ImplementationEvidenceKind::RollbackPlan,
        "rollback plan retained in implementation job",
        format!("rollback://{}", job.implementation_job_id),
        "mind-cli",
        std::collections::BTreeMap::from([("status".to_owned(), "passed".to_owned())]),
    )?);
    let bundle = attach_implementation_evidence(
        job,
        artifacts,
        default_implementation_evidence_requirements(),
    )?;
    println!("{}", serde_json::to_string_pretty(&bundle)?);
    Ok(())
}

fn github_evidence_demo(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let pr_number = args
        .get(1)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(20);
    let head_sha = args
        .get(2)
        .cloned()
        .unwrap_or_else(|| "demo-head-sha".to_owned());
    let pr = GitHubPullRequestEvidence::new(
        repository.clone(),
        pr_number,
        "v20 readiness evidence connector",
        "mind-cli",
        "main",
        "feature/v20-readiness-evidence",
        head_sha.clone(),
        false,
        false,
        Some("APPROVED".to_owned()),
        vec!["readiness".to_owned(), "v20".to_owned()],
        GitHubEvidenceSource::Fixture,
    )?;
    let checks = mind_core::required_readiness_check_names()
        .iter()
        .map(|name| {
            GitHubCheckRunEvidence::new(
                repository.clone(),
                head_sha.clone(),
                name.clone(),
                "completed",
                GitHubCheckConclusion::Success,
                Some("github-actions".to_owned()),
                Some(format!("https://github.com/{repository}/actions")),
                GitHubEvidenceSource::Fixture,
            )
        })
        .collect::<Result<Vec<_>, _>>()?;
    let bundle =
        collect_github_readiness_evidence(pr, checks, mind_core::required_readiness_check_names())?;
    println!("{}", serde_json::to_string_pretty(&bundle)?);
    Ok(())
}

fn branch_protection_policy_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let branch = args.get(1).cloned().unwrap_or_else(|| "main".to_owned());
    let policy = production_branch_protection_policy(repository, branch)?;
    println!("{}", serde_json::to_string_pretty(&policy)?);
    Ok(())
}

fn branch_protection_evaluate_cmd(args: &[String]) -> Result<(), MindError> {
    let policy_path = required_arg(args, 0, "branch-protection-policy.json")?;
    let policy = serde_json::from_str::<BranchProtectionPolicy>(&fs::read_to_string(policy_path)?)?;
    let observed_checks = args
        .get(1)
        .map(|value| {
            value
                .split(',')
                .filter(|s| !s.is_empty())
                .map(ToOwned::to_owned)
                .collect()
        })
        .unwrap_or_else(mind_core::required_readiness_check_names);
    let observed = BranchProtectionObservedState {
        required_status_checks: observed_checks,
        enforce_admins: true,
        required_approving_review_count: 2,
        require_code_owner_reviews: true,
        require_conversation_resolution: true,
        require_linear_history: true,
    };
    let report = evaluate_branch_protection_policy(&policy, observed)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn live_chaos_adapter_plan_cmd(args: &[String]) -> Result<(), MindError> {
    let rehearsal_path = required_arg(args, 0, "chaos-plan.json")?;
    let rehearsal = serde_json::from_str::<mind_core::ChaosRehearsalPlan>(&fs::read_to_string(
        rehearsal_path,
    )?)?;
    let staging_report =
        if let Some(report_path) = args.get(1).filter(|value| value.as_str() != "none") {
            Some(serde_json::from_str::<StagingChaosRunReport>(
                &fs::read_to_string(report_path)?,
            )?)
        } else {
            None
        };
    let backend = match args.get(2).map(String::as_str) {
        Some("argo") => LiveChaosAdapterBackend::ArgoRolloutAnalysis,
        Some("http") => LiveChaosAdapterBackend::HttpGateway,
        Some("manual") => LiveChaosAdapterBackend::ManualRunbook,
        _ => LiveChaosAdapterBackend::KubernetesServerDryRun,
    };
    let mode = match args.get(3).map(String::as_str) {
        Some("plan") => LiveChaosAdapterMode::PlanOnly,
        Some("live") => LiveChaosAdapterMode::LiveApproved,
        _ => LiveChaosAdapterMode::ServerDryRun,
    };
    let plan = plan_live_staging_chaos_adapter(&rehearsal, staging_report.as_ref(), backend, mode)?;
    let receipt = execute_live_staging_chaos_adapter_dry_run(&plan)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn waiver_review_demo(args: &[String]) -> Result<(), MindError> {
    let gate_path = required_arg(args, 0, "readiness-gate.json")?;
    let gate =
        serde_json::from_str::<ProductionReadinessGateReport>(&fs::read_to_string(gate_path)?)?;
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        gate.blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect(),
        "maintainer-a",
        "review queued by v20 waiver-review flow",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )?;
    let item = open_waiver_review_queue_item(
        &proposal,
        &gate.blockers,
        std::collections::BTreeSet::from([
            WaiverOperatorRole::Maintainer,
            WaiverOperatorRole::Security,
        ]),
        24,
    )?;
    let comments = vec![
        WaiverReviewComment::new(
            item.review_id,
            "maintainer-a",
            WaiverOperatorRole::Maintainer,
            ReadinessWaiverVoteDecision::Approve,
            "implementation remediation is scheduled",
        )?,
        WaiverReviewComment::new(
            item.review_id,
            "security-a",
            WaiverOperatorRole::Security,
            ReadinessWaiverVoteDecision::Approve,
            "security accepts staging-only risk with expiry",
        )?,
    ];
    let certificate = certify_waiver_review(&item, comments)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "item": item, "certificate": certificate }))?
    );
    Ok(())
}

fn github_check_run_plan_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = required_arg(args, 0, "repository")?;
    let head_sha = required_arg(args, 1, "head-sha")?;
    let name = args
        .get(2)
        .map(String::as_str)
        .unwrap_or("mandatory-readiness-gates");
    let plan = plan_github_check_run_write(
        repository,
        head_sha,
        name,
        GitHubCheckRunOutput::new("nested mind readiness", "readiness evidence planned"),
        Some(GitHubCheckConclusion::Success),
        None,
        None,
        "nested-mind-readiness",
        GitHubCheckRunWriteMode::DryRun,
    )?;
    let receipt = record_github_check_run_write_receipt(&plan, None, None, None)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn branch_protection_reconcile_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = required_arg(args, 0, "repository")?;
    let branch = args.get(1).map(String::as_str).unwrap_or("main");
    let policy = production_branch_protection_policy(repository, branch)?;
    let plan =
        plan_branch_protection_reconcile(policy, None, BranchProtectionReconcileMode::PlanOnly)?;
    let receipt = record_branch_protection_reconcile_receipt(&plan, None)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn kubernetes_staging_chaos_plan_cmd(args: &[String]) -> Result<(), MindError> {
    let namespace = args
        .first()
        .map(String::as_str)
        .unwrap_or("nested-mind-staging");
    let mode = match args.get(1).map(String::as_str).unwrap_or("server-dry-run") {
        "plan" | "plan-only" => KubernetesChaosExecutionMode::PlanOnly,
        "live" | "live-approved" => KubernetesChaosExecutionMode::LiveApproved,
        _ => KubernetesChaosExecutionMode::ServerDryRun,
    };
    let approval = args.get(2).cloned();
    let rehearsal = production_chaos_rehearsal_plan(None)?;
    let plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        namespace,
        "nested-mind-chaos-runner",
        mode,
        approval,
    )?;
    let receipt = record_kubernetes_staging_chaos_receipt(&plan, None)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn waiver_reviewer_assignment_demo(args: &[String]) -> Result<(), MindError> {
    let gate_path = required_arg(args, 0, "readiness-gate.json")?;
    let gate =
        serde_json::from_str::<ProductionReadinessGateReport>(&fs::read_to_string(gate_path)?)?;
    let blocker_ids = gate
        .blockers
        .iter()
        .map(|blocker| blocker.blocker_id)
        .collect::<Vec<_>>();
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        blocker_ids,
        "maintainer-a",
        "demo waiver assignment",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )?;
    let mut required = std::collections::BTreeSet::new();
    required.insert(WaiverOperatorRole::Maintainer);
    required.insert(WaiverOperatorRole::Security);
    let queue = open_waiver_review_queue_item(&proposal, &gate.blockers, required, 24)?;
    let candidates = vec![WaiverReviewerCandidate::new(
        "maintainer-reviewer",
        "platform",
        WaiverOperatorRole::Maintainer,
        true,
        0,
    )?];
    let escalation_targets = std::collections::BTreeMap::from([(
        WaiverOperatorRole::Security,
        "security-oncall".to_owned(),
    )]);
    let assignment = plan_waiver_reviewer_assignment(&queue, candidates, escalation_targets, 24)?;
    let escalation = certify_waiver_escalation(&assignment, "security reviewer required")?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({ "queue": queue, "assignment": assignment, "escalation": escalation })
        )?
    );
    Ok(())
}

fn github_app_token_plan_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let app_id = args
        .get(1)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    let installation_id = args
        .get(2)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    let key_fingerprint = args
        .get(3)
        .cloned()
        .unwrap_or_else(|| "demo-private-key-fingerprint".to_owned());
    let mut permissions = std::collections::BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    permissions.insert("administration".to_owned(), "write".to_owned());
    let request = GitHubAppInstallationTokenRequest::new(
        app_id,
        installation_id,
        repository,
        key_fingerprint,
        permissions,
        Vec::new(),
        3600,
    )?;
    let plan = plan_github_app_installation_token(request, GitHubAppTokenMode::DryRun)?;
    let receipt =
        record_github_app_installation_token_receipt(&plan, None, Some(&plan.rest_payload))?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn github_action_execution_plan_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let head_sha = args
        .get(1)
        .cloned()
        .unwrap_or_else(|| "demo-head-sha".to_owned());
    let mut permissions = std::collections::BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    let token_request = GitHubAppInstallationTokenRequest::new(
        1,
        1,
        repository.clone(),
        "demo-private-key-fingerprint",
        permissions,
        Vec::new(),
        3600,
    )?;
    let token_plan = plan_github_app_installation_token(token_request, GitHubAppTokenMode::DryRun)?;
    let token_receipt = record_github_app_installation_token_receipt(
        &token_plan,
        None,
        Some(&token_plan.rest_payload),
    )?;
    let check_plan = plan_github_check_run_write(
        repository,
        head_sha,
        "mandatory-readiness-gates",
        GitHubCheckRunOutput::new("nested mind readiness", "v22 action execution planned"),
        Some(GitHubCheckConclusion::Success),
        None,
        None,
        "nested-mind-readiness",
        GitHubCheckRunWriteMode::DryRun,
    )?;
    let action_plan = plan_github_check_run_action_execution(
        &token_plan,
        &check_plan,
        GitHubActionExecutionMode::DryRun,
    )?;
    let action_receipt = record_github_action_execution_receipt(
        &action_plan,
        &token_receipt,
        None,
        Some(&action_plan.rest_payload),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({ "token_plan": token_plan, "token_receipt": token_receipt, "check_plan": check_plan, "action_plan": action_plan, "action_receipt": action_receipt })
        )?
    );
    Ok(())
}

fn branch_protection_worker_cmd(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let branch = args.get(1).cloned().unwrap_or_else(|| "main".to_owned());
    let policy = production_branch_protection_policy(repository, branch)?;
    let reconcile =
        plan_branch_protection_reconcile(policy, None, BranchProtectionReconcileMode::DryRun)?;
    let reconcile_receipt = mind_core::record_branch_protection_reconcile_receipt(
        &reconcile,
        Some(reconcile.rest_payload.clone()),
    )?;
    let worker_plan = plan_branch_protection_reconcile_worker(
        std::slice::from_ref(&reconcile),
        BranchProtectionWorkerMode::DryRun,
    )?;
    let worker_report = record_branch_protection_worker_report(
        &worker_plan,
        std::slice::from_ref(&reconcile_receipt),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({ "reconcile": reconcile, "reconcile_receipt": reconcile_receipt, "worker_plan": worker_plan, "worker_report": worker_report })
        )?
    );
    Ok(())
}

fn kubernetes_dry_run_execute_cmd(args: &[String]) -> Result<(), MindError> {
    let namespace = args
        .first()
        .map(String::as_str)
        .unwrap_or("nested-mind-staging");
    let context = args.get(1).map(String::as_str).unwrap_or("staging");
    let rehearsal = production_chaos_rehearsal_plan(None)?;
    let plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        namespace,
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )?;
    let request = plan_kubernetes_server_dry_run_execution(&plan, context, "nested-mind-platform")?;
    let receipt = record_kubernetes_server_dry_run_receipt(&request, &plan, None, Vec::new())?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({ "plan": plan, "request": request, "receipt": receipt })
        )?
    );
    Ok(())
}

fn waiver_notification_delivery_cmd(args: &[String]) -> Result<(), MindError> {
    let assignment_path = required_arg(args, 0, "waiver-assignment.json")?;
    let assignment = serde_json::from_str::<WaiverReviewerAssignmentPlan>(&fs::read_to_string(
        assignment_path,
    )?)?;
    let plan = plan_waiver_notification_delivery(
        &assignment,
        WaiverNotificationChannel::Manual,
        "Nested Mind waiver review requested",
        "Review the readiness waiver and attach approval evidence.",
    )?;
    let receipt = record_waiver_notification_receipt(
        &plan,
        plan.recipients.clone(),
        Some("manual-delivery".to_owned()),
        None,
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({ "plan": plan, "receipt": receipt }))?
    );
    Ok(())
}

fn github_secret_jwt_demo(args: &[String]) -> Result<(), MindError> {
    let repository = args
        .first()
        .cloned()
        .unwrap_or_else(|| "mullusi/nested-mind-platform".to_owned());
    let app_id = args
        .get(1)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    let installation_id = args
        .get(2)
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    let secret = SecretReference::new(
        SecretManagerBackend::ExternalGateway,
        format!("github-app/{repository}/private-key"),
        "github-app-private-key",
    )?;
    let secret_plan = plan_secret_access(
        secret,
        "sign GitHub App JWT",
        SecretAccessMode::DryRun,
        None,
    )?;
    let secret_receipt = record_secret_access_receipt(
        &secret_plan,
        Some("dry-run-private-key-fingerprint".to_owned()),
        Some("v1".to_owned()),
        std::collections::BTreeMap::from([("repository".to_owned(), repository.clone())]),
    )?;
    let jwt_plan = plan_github_app_jwt_from_secret(app_id, installation_id, &secret_plan, 540)?;
    let jwt_receipt = record_github_app_jwt_receipt(
        &jwt_plan,
        &secret_receipt,
        Some("dry-run-jwt-fingerprint".to_owned()),
        None,
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "secret_plan": secret_plan,
            "secret_receipt": secret_receipt,
            "jwt_plan": jwt_plan,
            "jwt_receipt": jwt_receipt
        }))?
    );
    Ok(())
}

fn connector_worker_demo(args: &[String]) -> Result<(), MindError> {
    let worker_id = args
        .first()
        .cloned()
        .unwrap_or_else(|| "connector-worker-a".to_owned());
    let job = ScheduledJob::new(
        ScheduledJobKind::ProviderExecution,
        "github-check-run",
        &json!({"repository":"mullusi/nested-mind-platform","head_sha":"demo"}),
        OffsetDateTime::now_utc(),
        3,
    )?;
    let plan = plan_connector_worker_job(
        &job,
        worker_id,
        ConnectorWorkerActionKind::GitHubActionExecution,
        ConnectorWorkerMode::DryRun,
    )?;
    let receipt = record_connector_worker_execution_receipt(
        &plan,
        Some(plan.plan_hash.clone()),
        None,
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"job": job, "plan": plan, "receipt": receipt}))?
    );
    Ok(())
}

fn kubernetes_admission_audit_demo(args: &[String]) -> Result<(), MindError> {
    let namespace = args
        .first()
        .map(String::as_str)
        .unwrap_or("nested-mind-staging");
    let rehearsal = production_chaos_rehearsal_plan(None)?;
    let chaos_plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        namespace,
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )?;
    let dry_request =
        plan_kubernetes_server_dry_run_execution(&chaos_plan, "staging", "nested-mind-platform")?;
    let dry_receipt =
        record_kubernetes_server_dry_run_receipt(&dry_request, &chaos_plan, None, Vec::new())?;
    let audit = plan_kubernetes_admission_audit(
        &dry_request,
        KubernetesAdmissionOperation::Create,
        dry_receipt.receipt_hash.clone(),
        "nested-mind-worker",
    )?;
    let mut annotations = std::collections::BTreeMap::new();
    annotations.insert("nested.mind/rehearsal".to_owned(), "true".to_owned());
    let (audit_receipt, report) = record_kubernetes_admission_audit_receipt(
        &audit,
        &dry_receipt,
        &KubernetesAdmissionAuditPolicy::default(),
        Some("audit-demo-uid".to_owned()),
        annotations,
        Vec::new(),
        true,
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "dry_request": dry_request,
            "dry_receipt": dry_receipt,
            "audit_request": audit,
            "audit_receipt": audit_receipt,
            "report": report
        }))?
    );
    Ok(())
}

fn waiver_notification_adapter_demo(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "waiver-notification-plan.json")?;
    let notification_plan =
        serde_json::from_str::<WaiverNotificationPlan>(&fs::read_to_string(plan_path)?)?;
    let adapter_plan = plan_waiver_notification_adapter(
        &notification_plan,
        WaiverNotificationAdapterKind::GenericWebhook,
        "https://notification-gateway.example/waivers",
        notification_plan.body_hash.clone(),
        WaiverNotificationAdapterMode::DryRun,
    )?;
    let adapter_receipt = record_waiver_notification_adapter_receipt(
        &adapter_plan,
        None,
        Some("dry-run-message".to_owned()),
        Some(adapter_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"adapter_plan": adapter_plan, "adapter_receipt": adapter_receipt})
        )?
    );
    Ok(())
}

fn live_secret_connector_demo(_args: &[String]) -> Result<(), MindError> {
    let secret = SecretReference::new(
        SecretManagerBackend::ExternalGateway,
        "github-app/mullusi/private-key",
        "github-app-private-key",
    )?;
    let access_plan = plan_secret_access(
        secret,
        "sign GitHub App JWT",
        SecretAccessMode::DryRun,
        None,
    )?;
    let access_receipt = record_secret_access_receipt(
        &access_plan,
        Some("dry-run-private-key-fingerprint".to_owned()),
        Some("v1".to_owned()),
        std::collections::BTreeMap::new(),
    )?;
    let connector_plan = mind_core::plan_live_secret_connector(
        &access_plan,
        mind_core::LiveSecretConnectorMode::DryRun,
        json!({"operation":"read_secret_fingerprint_only"}),
    )?;
    let connector_receipt = mind_core::record_live_secret_connector_receipt(
        &connector_plan,
        &access_receipt,
        Some("dry-run-secret-request".to_owned()),
        Some(connector_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "access_plan": access_plan,
            "access_receipt": access_receipt,
            "connector_plan": connector_plan,
            "connector_receipt": connector_receipt
        }))?
    );
    Ok(())
}

fn github_token_exchange_worker_demo(_args: &[String]) -> Result<(), MindError> {
    let secret = SecretReference::new(
        SecretManagerBackend::ExternalGateway,
        "github-app/mullusi/private-key",
        "github-app-private-key",
    )?;
    let access_plan = plan_secret_access(
        secret,
        "sign GitHub App JWT",
        SecretAccessMode::DryRun,
        None,
    )?;
    let access_receipt = record_secret_access_receipt(
        &access_plan,
        Some("dry-run-private-key-fingerprint".to_owned()),
        Some("v1".to_owned()),
        std::collections::BTreeMap::new(),
    )?;
    let jwt_plan = plan_github_app_jwt_from_secret(1, 1, &access_plan, 540)?;
    let jwt_receipt = record_github_app_jwt_receipt(
        &jwt_plan,
        &access_receipt,
        Some("dry-run-jwt-fingerprint".to_owned()),
        None,
    )?;
    let connector_plan = mind_core::plan_live_secret_connector(
        &access_plan,
        mind_core::LiveSecretConnectorMode::DryRun,
        json!({"operation":"read_secret"}),
    )?;
    let connector_receipt = mind_core::record_live_secret_connector_receipt(
        &connector_plan,
        &access_receipt,
        Some("dry-run-secret-request".to_owned()),
        Some(connector_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    let mut permissions = std::collections::BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    let token_request = GitHubAppInstallationTokenRequest::new(
        1,
        1,
        "mullusi/nested-mind-platform",
        "dry-run-private-key-fingerprint",
        permissions,
        Vec::new(),
        3600,
    )?;
    let token_plan = plan_github_app_installation_token(token_request, GitHubAppTokenMode::DryRun)?;
    let token_receipt = record_github_app_installation_token_receipt(
        &token_plan,
        None,
        Some(&token_plan.rest_payload),
    )?;
    let exchange_plan = mind_core::plan_github_token_exchange_worker(
        "mullusi/nested-mind-platform",
        1,
        &jwt_receipt,
        &connector_receipt,
        mind_core::GitHubTokenExchangeWorkerMode::DryRun,
        token_plan.request.request_hash.clone(),
    )?;
    let exchange_receipt =
        mind_core::record_github_token_exchange_worker_receipt(&exchange_plan, &token_receipt)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "jwt_plan": jwt_plan,
            "jwt_receipt": jwt_receipt,
            "token_plan": token_plan,
            "token_receipt": token_receipt,
            "exchange_plan": exchange_plan,
            "exchange_receipt": exchange_receipt
        }))?
    );
    Ok(())
}

fn kubernetes_audit_log_collector_demo(args: &[String]) -> Result<(), MindError> {
    let namespace = args
        .first()
        .map(String::as_str)
        .unwrap_or("nested-mind-staging");
    let rehearsal = production_chaos_rehearsal_plan(None)?;
    let chaos_plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        namespace,
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )?;
    let dry_request =
        plan_kubernetes_server_dry_run_execution(&chaos_plan, "staging", "nested-mind-platform")?;
    let dry_receipt =
        record_kubernetes_server_dry_run_receipt(&dry_request, &chaos_plan, None, Vec::new())?;
    let audit_request = plan_kubernetes_admission_audit(
        &dry_request,
        KubernetesAdmissionOperation::Create,
        dry_receipt.receipt_hash.clone(),
        "nested-mind-worker",
    )?;
    let mut annotations = std::collections::BTreeMap::new();
    annotations.insert("nested.mind/rehearsal".to_owned(), "true".to_owned());
    let (audit_receipt, admission_report) = record_kubernetes_admission_audit_receipt(
        &audit_request,
        &dry_receipt,
        &KubernetesAdmissionAuditPolicy::default(),
        Some("audit-demo-uid".to_owned()),
        annotations,
        Vec::new(),
        true,
    )?;
    let collector_plan = mind_core::plan_kubernetes_audit_log_collector(
        &admission_report,
        namespace,
        mind_core::KubernetesAuditLogCollectorMode::DryRun,
        None,
    )?;
    let collector_report = mind_core::record_kubernetes_audit_log_collector_report(
        &collector_plan,
        &audit_receipt,
        1,
        vec!["audit-demo-uid".to_owned()],
        Some("watermark-1".to_owned()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"collector_plan": collector_plan, "collector_report": collector_report})
        )?
    );
    Ok(())
}

fn notification_delivery_client_demo(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "waiver-notification-plan.json")?;
    let notification_plan =
        serde_json::from_str::<WaiverNotificationPlan>(&fs::read_to_string(plan_path)?)?;
    let adapter_plan = plan_waiver_notification_adapter(
        &notification_plan,
        WaiverNotificationAdapterKind::GenericWebhook,
        "https://notification-gateway.example/waivers",
        notification_plan.body_hash.clone(),
        WaiverNotificationAdapterMode::DryRun,
    )?;
    let adapter_receipt = record_waiver_notification_adapter_receipt(
        &adapter_plan,
        None,
        Some("dry-run-message".to_owned()),
        Some(adapter_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    let client_plan = mind_core::plan_notification_delivery_client(
        &adapter_plan,
        mind_core::NotificationDeliveryClientMode::DryRun,
        "https://notification-gateway.example/waivers",
        json!({"body_hash": notification_plan.body_hash}),
    )?;
    let client_receipt = mind_core::record_notification_delivery_client_receipt(
        &client_plan,
        &adapter_receipt,
        Some("dry-run-message".to_owned()),
        Some(client_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"client_plan": client_plan, "client_receipt": client_receipt})
        )?
    );
    Ok(())
}

fn connector_orchestration_demo(_args: &[String]) -> Result<(), MindError> {
    let plan = mind_core::plan_connector_orchestration(
        "connector-worker-a",
        "end-to-end readiness action rehearsal",
        mind_core::ConnectorOrchestrationMode::DryRun,
        Vec::new(),
    )?;
    let mut artifacts = std::collections::BTreeMap::new();
    artifacts.insert("secret".to_owned(), "demo-secret-receipt-hash".to_owned());
    artifacts.insert(
        "github_token".to_owned(),
        "demo-token-receipt-hash".to_owned(),
    );
    artifacts.insert(
        "kubernetes_audit".to_owned(),
        "demo-audit-report-hash".to_owned(),
    );
    artifacts.insert(
        "notification".to_owned(),
        "demo-notification-receipt-hash".to_owned(),
    );
    let report = mind_core::evaluate_connector_orchestration(&plan, &[], &[], &[], &[], artifacts)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"plan": plan, "report": report}))?
    );
    Ok(())
}

fn kubernetes_audit_source_demo(args: &[String]) -> Result<(), MindError> {
    let namespace = args
        .first()
        .map(String::as_str)
        .unwrap_or("nested-mind-staging");
    let rehearsal = production_chaos_rehearsal_plan(None)?;
    let chaos_plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        namespace,
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )?;
    let dry_request =
        plan_kubernetes_server_dry_run_execution(&chaos_plan, "staging", "nested-mind-platform")?;
    let dry_receipt =
        record_kubernetes_server_dry_run_receipt(&dry_request, &chaos_plan, None, Vec::new())?;
    let audit_request = plan_kubernetes_admission_audit(
        &dry_request,
        KubernetesAdmissionOperation::Create,
        dry_receipt.receipt_hash.clone(),
        "nested-mind-worker",
    )?;
    let mut annotations = std::collections::BTreeMap::new();
    annotations.insert("nested.mind/rehearsal".to_owned(), "true".to_owned());
    let (audit_receipt, admission_report) = record_kubernetes_admission_audit_receipt(
        &audit_request,
        &dry_receipt,
        &KubernetesAdmissionAuditPolicy::default(),
        Some("audit-demo-uid".to_owned()),
        annotations,
        Vec::new(),
        true,
    )?;
    let collector_plan = mind_core::plan_kubernetes_audit_log_collector(
        &admission_report,
        namespace,
        mind_core::KubernetesAuditLogCollectorMode::DryRun,
        None,
    )?;
    let collector_report = mind_core::record_kubernetes_audit_log_collector_report(
        &collector_plan,
        &audit_receipt,
        1,
        vec!["audit-demo-uid".to_owned()],
        Some("watermark-1".to_owned()),
        Vec::new(),
    )?;
    let source_plan = mind_core::plan_kubernetes_audit_source_adapter(
        &collector_plan,
        mind_core::KubernetesAuditSourceKind::ExternalGateway,
        mind_core::KubernetesAuditSourceAdapterMode::DryRun,
        "audit-gateway://staging",
        json!({"namespace": namespace}),
    )?;
    let source_receipt = mind_core::record_kubernetes_audit_source_adapter_receipt(
        &source_plan,
        &collector_report,
        Some(source_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"source_plan": source_plan, "source_receipt": source_receipt})
        )?
    );
    Ok(())
}

fn notification_provider_delivery_demo(args: &[String]) -> Result<(), MindError> {
    let plan_path = required_arg(args, 0, "waiver-notification-plan.json")?;
    let notification_plan =
        serde_json::from_str::<WaiverNotificationPlan>(&fs::read_to_string(plan_path)?)?;
    let adapter_plan = plan_waiver_notification_adapter(
        &notification_plan,
        WaiverNotificationAdapterKind::GenericWebhook,
        "https://notification-gateway.example/waivers",
        notification_plan.body_hash.clone(),
        WaiverNotificationAdapterMode::DryRun,
    )?;
    let adapter_receipt = record_waiver_notification_adapter_receipt(
        &adapter_plan,
        None,
        Some("dry-run-message".to_owned()),
        Some(adapter_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    let client_plan = mind_core::plan_notification_delivery_client(
        &adapter_plan,
        mind_core::NotificationDeliveryClientMode::DryRun,
        "https://notification-gateway.example/waivers",
        json!({"body_hash": notification_plan.body_hash}),
    )?;
    let client_receipt = mind_core::record_notification_delivery_client_receipt(
        &client_plan,
        &adapter_receipt,
        Some("dry-run-message".to_owned()),
        Some(client_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    let provider_plan = mind_core::plan_notification_provider_delivery(
        &client_plan,
        mind_core::NotificationProviderKind::GenericWebhook,
        mind_core::NotificationProviderDeliveryMode::DryRun,
        "https://notification-gateway.example/waivers",
        json!({"client_plan": client_plan.client_plan_id.to_string()}),
    )?;
    let provider_receipt = mind_core::record_notification_provider_delivery_receipt(
        &provider_plan,
        &client_receipt,
        Some("dry-run-message".to_owned()),
        Some(provider_plan.plan_hash.clone()),
        Vec::new(),
    )?;
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"provider_plan": provider_plan, "provider_receipt": provider_receipt})
        )?
    );
    Ok(())
}

fn action_promotion_gate_demo(_args: &[String]) -> Result<(), MindError> {
    let plan = mind_core::plan_connector_orchestration(
        "connector-worker-a",
        "action promotion",
        mind_core::ConnectorOrchestrationMode::ExecuteApproved,
        Vec::new(),
    )?;
    let mut artifacts = std::collections::BTreeMap::new();
    artifacts.insert("secret".to_owned(), "secret-hash".to_owned());
    artifacts.insert("github_token".to_owned(), "token-hash".to_owned());
    artifacts.insert("kubernetes_audit".to_owned(), "audit-hash".to_owned());
    artifacts.insert("notification".to_owned(), "notification-hash".to_owned());
    let orchestration =
        mind_core::evaluate_connector_orchestration(&plan, &[], &[], &[], &[], artifacts)?;
    let policy = mind_core::ActionPromotionGatePolicy {
        require_connector_evidence_complete: true,
        require_kubernetes_audit_source: false,
        require_notification_provider_receipt: false,
    };
    let gate = mind_core::evaluate_action_promotion_gate(&policy, &orchestration, &[], &[])?;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({"orchestration": orchestration, "gate": gate}))?
    );
    Ok(())
}
