use mind_core::*;
use time::{Duration, OffsetDateTime};

#[test]
fn scheduled_job_due_claim_and_completion_are_traceable() {
    let now = OffsetDateTime::now_utc();
    let payload = serde_json::json!({"issuer": "https://issuer.example"});
    let job = ScheduledJob::new(
        ScheduledJobKind::OidcJwksRefresh,
        "issuer.example",
        &payload,
        now,
        3,
    )
    .expect("job");
    assert!(job.is_due_at(now));
    assert!(!job.payload_hash.is_empty());

    let policy = SchedulerLeasePolicy::default();
    let (claimed, claim) = job.claim("worker-a", &policy, now).expect("claim");
    assert_eq!(claimed.status, ScheduledJobStatus::Claimed);
    assert_eq!(claim.attempt, 1);
    let succeeded = claimed.mark_succeeded(now + Duration::seconds(1));
    assert_eq!(succeeded.status, ScheduledJobStatus::Succeeded);
}

#[test]
fn provider_execution_receipt_verifies_against_request() {
    let payload = serde_json::json!({"object": "root/backup.json"});
    let request = ProviderExecutionRequest::for_object_put(
        CloudObjectProvider::S3Compatible,
        "mind-backups",
        "root/backup.json",
        &payload,
    )
    .expect("request");
    let receipt = ProviderExecutionReceipt::succeeded(&request, request.payload_hash.clone());
    receipt.verify_for(&request).expect("receipt verifies");
    assert_eq!(receipt.status, ProviderExecutionStatus::Succeeded);
}

#[test]
fn consensus_commit_certificate_requires_quorum_votes() {
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
    let operation = serde_json::json!({"append_record_batch": "batch-1"});
    let entry = ConsensusLogEntry::new(
        &membership,
        "node-a",
        "replication_batch_commit",
        &operation,
        None,
    )
    .expect("entry");
    let votes = vec![
        ConsensusCommitVote::accept(&entry, "node-a"),
        ConsensusCommitVote::accept(&entry, "node-b"),
    ];
    let certificate =
        ConsensusCommitCertificate::certify(&membership, entry, votes).expect("certificate");
    certificate.verify(&membership).expect("verified");
    assert!(certificate.committed);
    assert_eq!(certificate.required_quorum, 2);
}
