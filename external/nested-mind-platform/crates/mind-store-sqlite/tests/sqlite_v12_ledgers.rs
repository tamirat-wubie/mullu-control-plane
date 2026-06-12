use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v12_records_worker_scheduler_provider_sdk_and_consensus_apply_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"batch_id": "batch-1"});
    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "follower-a",
        &payload,
        now,
        3,
    )
    .expect("job");
    store.record_scheduled_job(&job).expect("record job");
    let claim_report =
        claim_due_jobs_with_leases(&[job], "worker-a", &SchedulerLeasePolicy::default(), 1, now)
            .expect("claim");
    store
        .record_scheduled_job(&claim_report.updated_jobs[0])
        .expect("update job");
    store
        .record_scheduler_lease(&claim_report.leases[0])
        .expect("lease");
    assert_eq!(store.scheduler_leases().expect("leases").len(), 1);

    let worker_config = WorkerRuntimeConfig::new("worker-b").expect("worker config");
    let worker_report = WorkerRuntime::run_once(&claim_report.updated_jobs, &worker_config, now)
        .expect("worker run on already-claimed set");
    store
        .record_worker_run_report(&worker_report)
        .expect("worker report");
    assert_eq!(store.worker_run_reports().expect("reports").len(), 1);

    let request = ProviderExecutionRequest::new(
        ProviderAdapterKind::HttpGateway,
        ProviderCommandKind::ReplicationPush,
        "follower-a",
        &payload,
    )
    .expect("provider request");
    let sdk_report = ProviderSdkAdapterReport::dry_run(&request).expect("provider sdk dry-run");
    store
        .record_provider_sdk_receipt(&sdk_report.receipt)
        .expect("provider sdk receipt");
    assert_eq!(store.provider_sdk_receipts().expect("receipts").len(), 1);

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
    let apply_report = ConsensusApplyReport::skipped(&certificate);
    store
        .record_consensus_apply_report(&apply_report)
        .expect("apply report");
    assert_eq!(
        store
            .consensus_apply_reports()
            .expect("apply reports")
            .len(),
        1
    );
}
