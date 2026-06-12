use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use time::OffsetDateTime;

#[test]
fn sqlite_v13_claims_worker_ticks_features_and_consensus_ledgers() {
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
    store.record_scheduled_job(&job).expect("record job");
    let policy = SchedulerLeasePolicy {
        max_claims_per_poll: 1,
        ..SchedulerLeasePolicy::default()
    };
    let claim = store
        .claim_due_jobs_for_worker("worker-a", &policy, 1, now)
        .expect("claim");
    assert_eq!(claim.claimed_count, 1);
    assert_eq!(store.scheduler_leases().expect("leases").len(), 1);

    let config = WorkerDaemonConfig::new("worker-a")
        .expect("config")
        .with_lease_policy(policy)
        .with_max_jobs_per_tick(1);
    let tick = WorkerDaemonTickReport::from_claim_report(&config, 0, claim, now).expect("tick");
    store.record_worker_daemon_tick(&tick).expect("tick ledger");
    assert_eq!(store.worker_daemon_ticks().expect("ticks").len(), 1);

    let matrix = ProviderSdkFeatureMatrix::conservative_default();
    store
        .record_provider_sdk_feature_matrix(&matrix)
        .expect("feature matrix");
    assert_eq!(
        store
            .provider_sdk_feature_matrices()
            .expect("matrices")
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
    let report = ConsensusApplyReport::skipped(&certificate);
    let decision =
        evaluate_consensus_apply_idempotency(&certificate, std::slice::from_ref(&report));
    store
        .record_consensus_apply_idempotency_decision(&decision)
        .expect("idempotency");
    assert_eq!(
        store
            .consensus_apply_idempotency_decisions()
            .expect("decisions")
            .len(),
        1
    );

    let policy = ConsensusLogCompactionPolicy {
        keep_latest_committed: 1,
        min_committed_entries_between_compactions: 1,
    };
    let compaction =
        evaluate_consensus_log_compaction("cluster-a", &[certificate], &[report], &policy)
            .expect("compaction");
    store
        .record_consensus_log_compaction_decision(&compaction)
        .expect("compaction ledger");
    assert_eq!(
        store
            .consensus_log_compaction_decisions()
            .expect("compactions")
            .len(),
        1
    );
}
