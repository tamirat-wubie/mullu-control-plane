use mind_core::*;
use time::OffsetDateTime;

#[test]
fn job_execution_receipt_binds_claimed_job_and_lease() {
    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"batch_id":"batch-1"});
    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "follower-a",
        &payload,
        now,
        3,
    )
    .expect("job");
    let policy = SchedulerLeasePolicy::default();
    let (claimed, claim) = job.claim("worker-a", &policy, now).expect("claim");
    let lease = SchedulerLeaseRecord::from_claim(&claimed, &claim).expect("lease");
    let receipt = execute_job_with_receipt(
        &claimed,
        "worker-a",
        Some(&lease),
        JobExecutionMode::LocalExecutor,
    )
    .expect("receipt");
    assert_eq!(receipt.status, JobExecutionStatus::Succeeded);
    assert_eq!(receipt.expected_payload_hash, claimed.payload_hash);
    assert_eq!(receipt.lease_id, Some(lease.lease_id));
    let report = verify_job_execution_receipt(&claimed, &receipt, Some(&lease));
    assert!(report.valid);
}

#[test]
fn distributed_lease_request_and_receipt_verify_payload_hash() {
    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"job":"backup"});
    let job = ScheduledJob::new(
        ScheduledJobKind::BackupVerification,
        "root-backup",
        &payload,
        now,
        3,
    )
    .expect("job");
    let boundary =
        DistributedLeaseServiceBoundary::sqlite_local("local-scheduler").expect("boundary");
    let policy = SchedulerLeasePolicy::default();
    let plan =
        plan_external_distributed_lease_claim(&boundary, &job, "worker-a", &policy).expect("plan");
    let receipt = DistributedLeaseClaimReceipt::granted(&boundary, &plan.request);
    receipt
        .verify_for(&plan.request)
        .expect("receipt verification");
    assert_eq!(receipt.status, DistributedLeaseClaimStatus::Granted);
    assert_eq!(receipt.expected_payload_hash, job.payload_hash);
    assert!(receipt.fencing_token.is_some());
}

#[test]
fn native_provider_registry_reports_local_mirror_boundary() {
    let request = ProviderExecutionRequest::new(
        ProviderAdapterKind::LocalMirror,
        ProviderCommandKind::ObjectPut,
        "mirror-bucket/root/backup.json",
        &serde_json::json!({"backup_id":"b1"}),
    )
    .expect("request");
    let registry = native_provider_adapter_registry();
    let report = evaluate_native_provider_request(&request, &registry).expect("report");
    assert_eq!(report.sdk, DirectProviderSdk::LocalMirror);
    assert!(report.accepted);
    assert_eq!(report.mode, NativeProviderExecutionMode::DryRunOnly);
}

#[test]
fn physical_consensus_compaction_requires_backup_guard() {
    let decision = ConsensusLogCompactionDecision {
        compaction_id: EventId::new(),
        cluster_id: "cluster-a".to_owned(),
        policy: ConsensusLogCompactionPolicy {
            keep_latest_committed: 1,
            min_committed_entries_between_compactions: 1,
        },
        committed_count: 2,
        should_compact: true,
        keep_certificate_ids: vec![EventId::new()],
        compact_certificate_ids: vec![EventId::new()],
        high_watermark_entry_hash: Some("entry-hash".to_owned()),
        high_watermark_entry_id: Some(EventId::new()),
        reasons: vec!["test".to_owned()],
        decided_at: OffsetDateTime::now_utc(),
    };
    let verification = BackupVerificationReport {
        backup_id: EventId::new(),
        mind_id: None,
        valid: true,
        event_count: 3,
        snapshot_count: 0,
        trace_count: 0,
        audit_count: 0,
        latest_event_sequence: Some(3),
        latest_event_hash: Some("record-hash".to_owned()),
        backup_hash: "backup-hash".to_owned(),
    };
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(&decision, &verification)
        .expect("guard");
    let plan = plan_physical_consensus_compaction(&decision, guard).expect("plan");
    let report = ConsensusPhysicalCompactionReport::planned(&plan);
    assert_eq!(plan.certificate_ids_to_delete.len(), 1);
    assert_eq!(report.status, ConsensusPhysicalCompactionStatus::Planned);
}
