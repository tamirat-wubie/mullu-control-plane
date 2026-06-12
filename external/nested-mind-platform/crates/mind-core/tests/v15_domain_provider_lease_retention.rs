use mind_core::*;
use time::OffsetDateTime;

#[test]
fn domain_job_execution_requires_domain_payload_and_records_evidence() {
    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"batch_id":"batch-1", "follower_id":"node-b"});
    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "node-b",
        &payload,
        now,
        3,
    )
    .expect("job");
    let policy = SchedulerLeasePolicy::default();
    let (claimed, claim) = job.claim("worker-a", &policy, now).expect("claim");
    let lease = SchedulerLeaseRecord::from_claim(&claimed, &claim).expect("lease");
    let registry = domain_job_executor_registry();
    let report = execute_domain_job_with_receipt(
        &claimed,
        "worker-a",
        Some(&lease),
        JobExecutionMode::LocalExecutor,
        &registry,
    )
    .expect("domain execution");
    assert_eq!(report.status, DomainJobExecutionStatus::Executed);
    assert!(report
        .produced_evidence_keys
        .contains(&"delivery_receipt".to_owned()));
    assert_eq!(report.receipt.lease_id, Some(lease.lease_id));
}

#[test]
fn domain_job_execution_rejects_missing_required_payload_key() {
    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"batch_id":"batch-1"});
    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "node-b",
        &payload,
        now,
        3,
    )
    .expect("job");
    let registry = domain_job_executor_registry();
    let report = execute_domain_job_with_receipt(
        &job,
        "worker-a",
        None,
        JobExecutionMode::PlanOnly,
        &registry,
    )
    .expect("domain rejection");
    assert_eq!(report.status, DomainJobExecutionStatus::Rejected);
    assert!(report
        .reasons
        .iter()
        .any(|reason| reason.contains("follower_id")));
}

#[test]
fn distributed_lease_adapter_accepts_sqlite_and_rejects_unready_native_backend() {
    let now = OffsetDateTime::now_utc();
    let job = ScheduledJob::new(
        ScheduledJobKind::BackupVerification,
        "backup-a",
        &serde_json::json!({"backup_id":"b1", "backup_hash":"h1"}),
        now,
        3,
    )
    .expect("job");
    let policy = SchedulerLeasePolicy::default();
    let registry = distributed_lease_adapter_registry();
    let sqlite = DistributedLeaseServiceBoundary::sqlite_local("sqlite-scheduler").expect("sqlite");
    let accepted =
        evaluate_distributed_lease_adapter_claim(&sqlite, &job, "worker-a", &policy, &registry)
            .expect("sqlite lease");
    assert!(accepted.accepted);

    let postgres = DistributedLeaseServiceBoundary::new(
        DistributedLeaseBackendKind::PostgresAdvisoryLock,
        "postgres-scheduler",
        None,
        60,
    )
    .expect("postgres boundary");
    let rejected =
        evaluate_distributed_lease_adapter_claim(&postgres, &job, "worker-a", &policy, &registry)
            .expect("postgres lease report");
    assert!(!rejected.accepted);
}

#[test]
fn native_provider_execution_produces_hash_bound_receipts() {
    let request = ProviderExecutionRequest::new(
        ProviderAdapterKind::LocalMirror,
        ProviderCommandKind::ObjectPut,
        "mirror/root/backup.json",
        &serde_json::json!({"backup_id":"b1"}),
    )
    .expect("request");
    let registry = native_provider_adapter_registry();
    let receipt = execute_native_provider_with_receipt(&request, &registry, true)
        .expect("native provider receipt");
    assert_eq!(receipt.status, NativeProviderExecutionStatus::Executed);
    assert_eq!(
        receipt.provider_receipt.status,
        ProviderExecutionStatus::Succeeded
    );
    receipt.verify_for(&request).expect("receipt verifies");
}

#[test]
fn consensus_retention_plan_selects_apply_reports_only_when_policy_allows() {
    let certificate_id = EventId::new();
    let entry_id = EventId::new();
    let decision = ConsensusLogCompactionDecision {
        compaction_id: EventId::new(),
        cluster_id: "cluster-a".to_owned(),
        policy: ConsensusLogCompactionPolicy {
            keep_latest_committed: 1,
            min_committed_entries_between_compactions: 1,
        },
        committed_count: 2,
        should_compact: true,
        keep_certificate_ids: Vec::new(),
        compact_certificate_ids: vec![certificate_id],
        high_watermark_entry_hash: Some("entry-hash".to_owned()),
        high_watermark_entry_id: Some(entry_id),
        reasons: vec!["test".to_owned()],
        decided_at: OffsetDateTime::now_utc(),
    };
    let verification = BackupVerificationReport {
        backup_id: EventId::new(),
        mind_id: None,
        valid: true,
        event_count: 1,
        snapshot_count: 0,
        trace_count: 0,
        audit_count: 0,
        latest_event_sequence: Some(1),
        latest_event_hash: Some("record-hash".to_owned()),
        backup_hash: "backup-hash".to_owned(),
    };
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(&decision, &verification)
        .expect("guard");
    let physical_plan =
        plan_physical_consensus_compaction(&decision, guard).expect("physical plan");
    let apply_report = ConsensusApplyReport {
        apply_id: EventId::new(),
        certificate_id,
        entry_id,
        cluster_id: "cluster-a".to_owned(),
        operation_kind: "replication_batch_commit".to_owned(),
        operation_hash: "operation-hash".to_owned(),
        committed: true,
        status: ConsensusApplyStatus::Applied,
        mind_id: None,
        records_appended: 1,
        error: None,
        applied_at: OffsetDateTime::now_utc(),
    };
    let policy = ConsensusRetentionPolicy {
        delete_apply_reports: true,
        keep_latest_apply_reports: 0,
        ..ConsensusRetentionPolicy::default()
    };
    let plan = plan_consensus_retention_enforcement(
        &decision,
        &physical_plan,
        std::slice::from_ref(&apply_report),
        &policy,
    )
    .expect("retention plan");
    assert_eq!(plan.certificate_ids_to_delete, vec![certificate_id]);
    assert_eq!(plan.apply_report_ids_to_delete, vec![apply_report.apply_id]);
}
