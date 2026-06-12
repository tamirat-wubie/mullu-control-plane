use mind_core::{
    certify_consensus_retention_approval, claim_due_jobs_with_leases,
    execute_distributed_lease_with_receipt, execute_live_domain_job,
    execute_provider_sdk_with_policy, live_domain_job_executor_registry,
    native_provider_adapter_registry, ConsensusMember, ConsensusMembership,
    ConsensusRetentionApprovalPolicy, ConsensusRetentionApprovalProposal,
    ConsensusRetentionApprovalVote, DistributedLeaseExecutionMode, DistributedLeaseServiceBoundary,
    LiveDomainJobExecutorMode, ProviderAdapterKind, ProviderCommandKind, ProviderExecutionRequest,
    ProviderSdkExecutionPolicy, ScheduledJob, ScheduledJobKind, SchedulerLeasePolicy,
    PLATFORM_SCHEMA_VERSION,
};
use mind_store_sqlite::SqliteEventStore;
use serde_json::json;
use time::OffsetDateTime;

#[test]
fn sqlite_v16_ledgers_persist_live_execution_and_approval_evidence() {
    let mut store = SqliteEventStore::in_memory().unwrap();
    assert_eq!(
        store.current_schema_version().unwrap(),
        PLATFORM_SCHEMA_VERSION
    );

    let job = ScheduledJob::new(
        ScheduledJobKind::ReplicationDelivery,
        "follower-a",
        &json!({"batch_id":"batch-1", "follower_id":"follower-a"}),
        OffsetDateTime::now_utc(),
        3,
    )
    .unwrap();
    let policy = SchedulerLeasePolicy::default();
    let claim =
        claim_due_jobs_with_leases(&[job], "worker-a", &policy, 1, OffsetDateTime::now_utc())
            .unwrap();
    let claimed = claim.updated_jobs.first().unwrap();
    let lease = claim.leases.first().unwrap();
    let live = execute_live_domain_job(
        claimed,
        "worker-a",
        Some(lease),
        Some(LiveDomainJobExecutorMode::LocalSimulation),
        &live_domain_job_executor_registry(),
    )
    .unwrap();
    store
        .record_live_domain_job_execution_report(&live)
        .unwrap();
    assert_eq!(store.live_domain_job_execution_reports().unwrap().len(), 1);

    let boundary = DistributedLeaseServiceBoundary::sqlite_local("local-scheduler-lease").unwrap();
    let lease_receipt = execute_distributed_lease_with_receipt(
        &boundary,
        claimed,
        "worker-a",
        &policy,
        &mind_core::distributed_lease_adapter_registry(),
        DistributedLeaseExecutionMode::SqliteCompareAndSwap,
    )
    .unwrap();
    store
        .record_distributed_lease_execution_receipt(&lease_receipt)
        .unwrap();
    assert_eq!(
        store.distributed_lease_execution_receipts().unwrap().len(),
        1
    );

    let provider_request = ProviderExecutionRequest::new(
        ProviderAdapterKind::LocalMirror,
        ProviderCommandKind::ObjectPut,
        "local/object",
        &json!({"body":"backup"}),
    )
    .unwrap();
    let provider_report = execute_provider_sdk_with_policy(
        &provider_request,
        &native_provider_adapter_registry(),
        ProviderSdkExecutionPolicy::DryRunAllowed,
    )
    .unwrap();
    store
        .record_provider_sdk_execution_report(&provider_report)
        .unwrap();
    assert_eq!(store.provider_sdk_execution_reports().unwrap().len(), 1);

    let membership = ConsensusMembership::new(
        "mind-cluster",
        vec![
            ConsensusMember::voter("node-a"),
            ConsensusMember::voter("node-b"),
            ConsensusMember::voter("node-c"),
        ],
    );
    let plan = mind_core::ConsensusRetentionEnforcementPlan {
        plan_id: mind_core::EventId::new(),
        decision_id: mind_core::EventId::new(),
        cluster_id: "mind-cluster".to_owned(),
        policy: mind_core::ConsensusRetentionPolicy::default(),
        certificate_ids_to_delete: vec![mind_core::EventId::new()],
        apply_report_ids_to_delete: Vec::new(),
        apply_report_ids_to_keep: Vec::new(),
        evidence_classes_preserved: Vec::new(),
        backup_guard_hash: "backup-hash".to_owned(),
        created_at: OffsetDateTime::now_utc(),
    };
    let proposal =
        ConsensusRetentionApprovalProposal::from_plan(&plan, &membership, "maintainer-a").unwrap();
    let votes = vec![
        ConsensusRetentionApprovalVote::new(
            &proposal,
            "node-a",
            mind_core::RetentionApprovalVoteDecision::Approve,
        )
        .unwrap(),
        ConsensusRetentionApprovalVote::new(
            &proposal,
            "node-b",
            mind_core::RetentionApprovalVoteDecision::Approve,
        )
        .unwrap(),
    ];
    let cert = certify_consensus_retention_approval(
        &proposal,
        &membership,
        &ConsensusRetentionApprovalPolicy::default(),
        &votes,
    )
    .unwrap();
    store
        .record_consensus_retention_approval_proposal(&proposal)
        .unwrap();
    for vote in &votes {
        store
            .record_consensus_retention_approval_vote(vote)
            .unwrap();
    }
    store
        .record_consensus_retention_approval_certificate(&cert)
        .unwrap();
    assert_eq!(
        store
            .consensus_retention_approval_certificates()
            .unwrap()
            .len(),
        1
    );
}
