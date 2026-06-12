use mind_core::*;
use time::{Duration, OffsetDateTime};

#[test]
fn scheduler_leases_and_worker_runtime_claim_due_jobs() {
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
    let policy = SchedulerLeasePolicy {
        lease_seconds: 30,
        max_claims_per_poll: 2,
    };

    let claim_report =
        claim_due_jobs_with_leases(std::slice::from_ref(&job), "worker-a", &policy, 1, now)
            .expect("claim");
    assert_eq!(claim_report.claimed_count, 1);
    assert_eq!(claim_report.leases.len(), 1);
    assert!(claim_report.leases[0].is_active_at(now + Duration::seconds(1)));
    assert_eq!(
        claim_report.updated_jobs[0].status,
        ScheduledJobStatus::Claimed
    );

    let config = WorkerRuntimeConfig::new("worker-b")
        .expect("config")
        .with_lease_policy(policy)
        .with_limit(1)
        .with_mode(WorkerRuntimeMode::ExecuteAndMarkSucceeded);
    let run_report = WorkerRuntime::run_once(&[job], &config, now).expect("worker run");
    assert_eq!(run_report.claimed_count, 1);
    assert_eq!(run_report.succeeded_count, 1);
    assert_eq!(
        run_report.updated_jobs[0].status,
        ScheduledJobStatus::Succeeded
    );
}

#[test]
fn provider_sdk_dry_run_receipt_is_hash_bound() {
    let payload = serde_json::json!({"object": "root/backup.json"});
    let request = ProviderExecutionRequest::for_object_put(
        CloudObjectProvider::S3Compatible,
        "mind-backups",
        "root/backup.json",
        &payload,
    )
    .expect("provider request");
    let report = ProviderSdkAdapterReport::dry_run(&request).expect("dry run");
    assert_eq!(report.receipt.status, ProviderExecutionStatus::Succeeded);
    assert_eq!(report.receipt.expected_request_hash, request.payload_hash);
    report
        .receipt
        .verify_for(&report.invocation)
        .expect("receipt verifies against invocation");
}

#[test]
fn consensus_commit_certificate_applies_replication_batch_to_follower_store() {
    let mut leader_mind = Mind::new_root("root");
    let mut leader_store = InMemoryEventStore::new();
    let patch = StatePatch::new().set("goal", SymbolValue::from("replicate me"));
    let proposal = EditProposal::new(leader_mind.id(), "test", "set replicated goal", patch);
    let plan = EvolutionEngine::evaluate(&leader_mind, proposal).expect("plan");
    leader_store
        .append(plan.commit().clone())
        .expect("leader append");
    EvolutionEngine::apply_plan(&mut leader_mind, plan).expect("apply leader plan");

    let records = leader_store
        .records_for_mind(leader_mind.id())
        .expect("leader records");
    let protocol = LeaderReplicationProtocol::new(ReplicationTerm::new(1, "node-a"), 10, 2);
    let batch = protocol
        .prepare_batch(
            ReplicationCursor::start(leader_mind.id()),
            &records,
            SignatureRequirement::Optional,
        )
        .expect("batch");

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
    let entry = ConsensusLogEntry::new(
        &membership,
        "node-a",
        "replication_batch_commit",
        &batch,
        None,
    )
    .expect("entry");
    let votes = vec![
        ConsensusCommitVote::accept(&entry, "node-a"),
        ConsensusCommitVote::accept(&entry, "node-b"),
    ];
    let certificate =
        ConsensusCommitCertificate::certify(&membership, entry, votes).expect("certificate");

    let mut follower_store = InMemoryEventStore::new();
    let report =
        apply_certified_replication_batch(&mut follower_store, &membership, &certificate, "node-b")
            .expect("apply certified batch");
    assert_eq!(report.status, ConsensusApplyStatus::Applied);
    assert_eq!(report.records_appended, 1);
    assert_eq!(
        follower_store
            .records_for_mind(leader_mind.id())
            .expect("follower records")
            .len(),
        1
    );
}
