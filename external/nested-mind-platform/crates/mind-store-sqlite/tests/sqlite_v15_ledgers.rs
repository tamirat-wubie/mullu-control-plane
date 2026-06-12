use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v15_records_domain_lease_native_and_retention_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

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
    let domain_report = execute_domain_job_with_receipt(
        &claimed,
        "worker-a",
        Some(&lease),
        JobExecutionMode::LocalExecutor,
        &domain_job_executor_registry(),
    )
    .expect("domain report");
    store
        .record_domain_job_execution_report(&domain_report)
        .expect("domain ledger");
    assert_eq!(
        store
            .domain_job_execution_reports()
            .expect("domain reports")
            .len(),
        1
    );

    let boundary =
        DistributedLeaseServiceBoundary::sqlite_local("sqlite-scheduler").expect("boundary");
    let lease_report = evaluate_distributed_lease_adapter_claim(
        &boundary,
        &job,
        "worker-a",
        &policy,
        &distributed_lease_adapter_registry(),
    )
    .expect("lease report");
    store
        .record_distributed_lease_adapter_report(&lease_report)
        .expect("lease adapter ledger");
    assert_eq!(
        store
            .distributed_lease_adapter_reports()
            .expect("lease reports")
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
    let native_receipt = execute_native_provider_with_receipt(
        &provider_request,
        &native_provider_adapter_registry(),
        true,
    )
    .expect("native receipt");
    store
        .record_native_provider_execution_receipt(&native_receipt)
        .expect("native ledger");
    assert_eq!(
        store
            .native_provider_execution_receipts()
            .expect("native receipts")
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
    let apply_report = ConsensusApplyReport {
        apply_id: EventId::new(),
        certificate_id: certificate.certificate_id,
        entry_id: certificate.entry.entry_id,
        cluster_id: "cluster-a".to_owned(),
        operation_kind: certificate.entry.operation_kind.clone(),
        operation_hash: certificate.entry.operation_hash.clone(),
        committed: true,
        status: ConsensusApplyStatus::Applied,
        mind_id: None,
        records_appended: 1,
        error: None,
        applied_at: OffsetDateTime::now_utc(),
    };
    store
        .record_consensus_apply_report(&apply_report)
        .expect("apply report");
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
    let physical_plan =
        plan_physical_consensus_compaction(&decision, guard).expect("physical plan");
    let policy = ConsensusRetentionPolicy {
        delete_apply_reports: true,
        keep_latest_apply_reports: 0,
        ..ConsensusRetentionPolicy::default()
    };
    let retention_plan = plan_consensus_retention_enforcement(
        &decision,
        &physical_plan,
        &store.consensus_apply_reports().expect("apply reports"),
        &policy,
    )
    .expect("retention plan");
    let retention_report = store
        .apply_consensus_retention_enforcement(&retention_plan)
        .expect("retention apply");
    assert_eq!(retention_report.deleted_certificate_count, 1);
    assert_eq!(retention_report.deleted_apply_report_count, 1);
    assert_eq!(
        store
            .consensus_retention_enforcement_reports()
            .expect("retention reports")
            .len(),
        1
    );
}
