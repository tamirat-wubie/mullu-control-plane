use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v14_records_job_native_lease_and_physical_compaction_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

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
    .expect("job receipt");
    store
        .record_job_execution_receipt(&receipt)
        .expect("job receipt ledger");
    assert_eq!(
        store.job_execution_receipts().expect("job receipts").len(),
        1
    );

    let boundary =
        DistributedLeaseServiceBoundary::sqlite_local("local-scheduler").expect("boundary");
    let plan = plan_external_distributed_lease_claim(&boundary, &job, "worker-a", &policy)
        .expect("lease plan");
    let lease_receipt = DistributedLeaseClaimReceipt::granted(&boundary, &plan.request);
    store
        .record_distributed_lease_claim_receipt(&lease_receipt)
        .expect("lease receipt ledger");
    assert_eq!(
        store
            .distributed_lease_claim_receipts()
            .expect("lease receipts")
            .len(),
        1
    );

    let provider_request = ProviderExecutionRequest::new(
        ProviderAdapterKind::LocalMirror,
        ProviderCommandKind::ObjectPut,
        "mirror/root/backup.json",
        &payload,
    )
    .expect("provider request");
    let registry = native_provider_adapter_registry();
    let provider_report = evaluate_native_provider_request(&provider_request, &registry)
        .expect("native provider report");
    store
        .record_native_provider_adapter_report(&provider_report)
        .expect("native provider ledger");
    assert_eq!(
        store
            .native_provider_adapter_reports()
            .expect("native reports")
            .len(),
        1
    );

    let mut membership = ConsensusMembership::new(
        "cluster-a",
        vec![
            ConsensusMember::voter("node-a"),
            ConsensusMember::voter("node-b"),
            ConsensusMember::voter("node-c"),
        ],
    );
    membership = membership
        .apply_change(ConsensusMembershipChange::SetLeader {
            member_id: "node-a".to_owned(),
        })
        .expect("leader");
    let entry = ConsensusLogEntry::new(&membership, "node-a", "non_executable", &payload, None)
        .expect("entry");
    let certificate = ConsensusCommitCertificate::certify(
        &membership,
        entry.clone(),
        vec![
            ConsensusCommitVote::accept(&entry, "node-a"),
            ConsensusCommitVote::accept(&entry, "node-b"),
        ],
    )
    .expect("certificate");
    store
        .record_consensus_commit_certificate(&certificate)
        .expect("certificate ledger");
    assert_eq!(
        store
            .consensus_commit_certificates()
            .expect("certificates")
            .len(),
        1
    );

    let decision = ConsensusLogCompactionDecision {
        compaction_id: EventId::new(),
        cluster_id: "cluster-a".to_owned(),
        policy: ConsensusLogCompactionPolicy {
            keep_latest_committed: 1,
            min_committed_entries_between_compactions: 1,
        },
        committed_count: 1,
        should_compact: true,
        keep_certificate_ids: Vec::new(),
        compact_certificate_ids: vec![certificate.certificate_id],
        high_watermark_entry_hash: Some(certificate.entry.entry_hash.clone()),
        high_watermark_entry_id: Some(certificate.entry.entry_id),
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
    let compaction_plan = plan_physical_consensus_compaction(&decision, guard).expect("plan");
    let report = store
        .apply_consensus_physical_compaction(&compaction_plan)
        .expect("physical compaction");
    assert_eq!(report.deleted_certificate_count, 1);
    assert_eq!(
        store
            .consensus_physical_compaction_reports()
            .expect("reports")
            .len(),
        1
    );
    assert_eq!(
        store
            .consensus_commit_certificates()
            .expect("certificates")
            .len(),
        0
    );
}
