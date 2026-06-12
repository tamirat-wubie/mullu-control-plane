use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v11_records_scheduler_provider_and_consensus_commit_ledgers() {
    let mut store = SqliteEventStore::in_memory().expect("sqlite");
    assert_eq!(
        store.current_schema_version().expect("schema"),
        PLATFORM_SCHEMA_VERSION
    );

    let payload = serde_json::json!({"kind": "replication_delivery"});
    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "follower-a",
        &payload,
        OffsetDateTime::now_utc(),
        3,
    )
    .expect("job");
    store.record_scheduled_job(&job).expect("record job");
    assert_eq!(store.scheduled_jobs().expect("jobs").len(), 1);

    let request = ProviderExecutionRequest::new(
        ProviderAdapterKind::HttpGateway,
        ProviderCommandKind::ReplicationPush,
        "follower-a",
        &payload,
    )
    .expect("provider request");
    let receipt = ProviderExecutionReceipt::succeeded(&request, request.payload_hash.clone());
    store
        .record_provider_execution_receipt(&receipt)
        .expect("record receipt");
    assert_eq!(
        store.provider_execution_receipts().expect("receipts").len(),
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
    let entry = ConsensusLogEntry::new(&membership, "node-a", "append_batch", &payload, None)
        .expect("entry");
    let votes = vec![
        ConsensusCommitVote::accept(&entry, "node-a"),
        ConsensusCommitVote::accept(&entry, "node-b"),
    ];
    let certificate = ConsensusCommitCertificate::certify(&membership, entry, votes).expect("cert");
    store
        .record_consensus_commit_certificate(&certificate)
        .expect("record cert");
    assert_eq!(
        store.consensus_commit_certificates().expect("certs").len(),
        1
    );
}
