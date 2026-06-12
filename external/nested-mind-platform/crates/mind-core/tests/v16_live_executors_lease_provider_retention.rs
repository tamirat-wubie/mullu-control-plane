use mind_core::{
    certify_consensus_retention_approval, claim_due_jobs_with_leases,
    execute_distributed_lease_with_receipt, execute_live_domain_job,
    execute_provider_sdk_with_policy, live_domain_job_executor_registry,
    native_provider_adapter_registry, ConsensusMember, ConsensusMembership,
    ConsensusRetentionApprovalPolicy, ConsensusRetentionApprovalProposal,
    ConsensusRetentionApprovalVote, DistributedLeaseExecutionMode, DistributedLeaseServiceBoundary,
    LiveDomainJobExecutorMode, ProviderAdapterKind, ProviderCommandKind, ProviderExecutionRequest,
    ProviderSdkExecutionPolicy, ScheduledJob, ScheduledJobKind, SchedulerLeasePolicy,
};
use serde_json::json;
use time::OffsetDateTime;

#[test]
fn live_domain_job_execution_produces_evidence_for_claimed_replication_job() {
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
    let registry = live_domain_job_executor_registry();
    let report = execute_live_domain_job(
        claimed,
        "worker-a",
        Some(lease),
        Some(LiveDomainJobExecutorMode::LocalSimulation),
        &registry,
    )
    .unwrap();
    assert_eq!(report.evidence.len(), 2);
}

#[test]
fn distributed_lease_execution_receipt_binds_job_payload_hash() {
    let job = ScheduledJob::new(
        ScheduledJobKind::SnapshotCompaction,
        "root",
        &json!({"mind_id":"root", "policy":"default"}),
        OffsetDateTime::now_utc(),
        3,
    )
    .unwrap();
    let boundary = DistributedLeaseServiceBoundary::sqlite_local("local-scheduler-lease").unwrap();
    let registry = mind_core::distributed_lease_adapter_registry();
    let policy = SchedulerLeasePolicy::default();
    let receipt = execute_distributed_lease_with_receipt(
        &boundary,
        &job,
        "worker-a",
        &policy,
        &registry,
        DistributedLeaseExecutionMode::SqliteCompareAndSwap,
    )
    .unwrap();
    assert_eq!(
        receipt.plan.expected_payload_hash,
        receipt.lease_receipt.expected_payload_hash
    );
}

#[test]
fn provider_sdk_execution_policy_records_dry_run_report() {
    let request = ProviderExecutionRequest::new(
        ProviderAdapterKind::LocalMirror,
        ProviderCommandKind::ObjectPut,
        "local/object",
        &json!({"body":"backup"}),
    )
    .unwrap();
    let registry = native_provider_adapter_registry();
    let report = execute_provider_sdk_with_policy(
        &request,
        &registry,
        ProviderSdkExecutionPolicy::DryRunAllowed,
    )
    .unwrap();
    assert!(report.accepted);
}

#[test]
fn retention_approval_certificate_requires_voting_quorum() {
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
    assert_eq!(cert.status, mind_core::RetentionApprovalStatus::Approved);
}
