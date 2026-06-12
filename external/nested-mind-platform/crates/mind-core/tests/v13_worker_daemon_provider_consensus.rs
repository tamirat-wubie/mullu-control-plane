use mind_core::*;
use time::OffsetDateTime;

#[test]
fn worker_daemon_tick_marks_claimed_jobs_according_to_mode() {
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
        max_claims_per_poll: 1,
        ..SchedulerLeasePolicy::default()
    };
    let claim_report =
        claim_due_jobs_with_leases(&[job], "worker-a", &policy, 1, now).expect("claim report");
    let config = WorkerDaemonConfig::new("worker-a")
        .expect("config")
        .with_lease_policy(policy)
        .with_max_jobs_per_tick(1)
        .with_mode(WorkerRuntimeMode::ExecuteAndMarkSucceeded);
    let tick = WorkerDaemonTickReport::from_claim_report(&config, 0, claim_report, now)
        .expect("tick report");
    assert_eq!(tick.claimed_count, 1);
    assert_eq!(tick.succeeded_count, 1);
    assert_eq!(tick.updated_jobs[0].status, ScheduledJobStatus::Succeeded);
}

#[test]
fn provider_feature_matrix_exposes_disabled_native_boundaries() {
    let matrix = ProviderSdkFeatureMatrix::conservative_default();
    assert!(matrix
        .enabled_features()
        .iter()
        .any(|feature| feature.sdk == DirectProviderSdk::LocalMirror));
    assert!(matrix.native_features().is_empty());
    assert!(matrix
        .features
        .iter()
        .any(|feature| feature.cargo_feature == "provider-aws-kms"));
}

#[test]
fn consensus_apply_idempotency_detects_reapply_and_conflict() {
    let payload = serde_json::json!({"kind":"noop"});
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
    let applied = ConsensusApplyReport {
        apply_id: EventId::new(),
        certificate_id: certificate.certificate_id,
        entry_id: certificate.entry.entry_id,
        cluster_id: certificate.entry.cluster_id.clone(),
        operation_kind: certificate.entry.operation_kind.clone(),
        operation_hash: certificate.entry.operation_hash.clone(),
        committed: true,
        status: ConsensusApplyStatus::Applied,
        mind_id: None,
        records_appended: 0,
        error: None,
        applied_at: OffsetDateTime::now_utc(),
    };
    let decision = evaluate_consensus_apply_idempotency(&certificate, &[applied]);
    assert_eq!(
        decision.status,
        ConsensusApplyIdempotencyStatus::AlreadyApplied
    );

    let different_payload = serde_json::json!({"kind":"different"});
    let conflicting_entry = ConsensusLogEntry::new(
        &membership,
        "node-a",
        "non_executable",
        &different_payload,
        None,
    )
    .expect("conflicting entry");
    let conflicting_certificate = ConsensusCommitCertificate {
        certificate_id: EventId::new(),
        entry: ConsensusLogEntry {
            entry_id: certificate.entry.entry_id,
            ..conflicting_entry
        },
        votes: certificate.votes.clone(),
        required_quorum: certificate.required_quorum,
        accepted_votes: certificate.accepted_votes,
        committed: true,
        certified_at: OffsetDateTime::now_utc(),
    };
    let conflict = evaluate_consensus_apply_idempotency(
        &conflicting_certificate,
        &[ConsensusApplyReport::skipped(&certificate)],
    );
    assert_eq!(conflict.status, ConsensusApplyIdempotencyStatus::Conflict);
}

#[test]
fn consensus_log_compaction_keeps_latest_committed_entries() {
    let payload = serde_json::json!({"kind":"noop"});
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
    let mut certificates = Vec::new();
    let mut reports = Vec::new();
    let mut previous_hash = None;
    for _ in 0..4 {
        let entry = ConsensusLogEntry::new(
            &membership,
            "node-a",
            "non_executable",
            &payload,
            previous_hash,
        )
        .expect("entry");
        previous_hash = Some(entry.entry_hash.clone());
        let certificate = ConsensusCommitCertificate::certify(
            &membership,
            entry.clone(),
            vec![
                ConsensusCommitVote::accept(&entry, "node-a"),
                ConsensusCommitVote::accept(&entry, "node-b"),
            ],
        )
        .expect("certificate");
        reports.push(ConsensusApplyReport {
            apply_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            cluster_id: certificate.entry.cluster_id.clone(),
            operation_kind: certificate.entry.operation_kind.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            committed: true,
            status: ConsensusApplyStatus::Applied,
            mind_id: None,
            records_appended: 0,
            error: None,
            applied_at: OffsetDateTime::now_utc(),
        });
        certificates.push(certificate);
    }
    let policy = ConsensusLogCompactionPolicy {
        keep_latest_committed: 2,
        min_committed_entries_between_compactions: 1,
    };
    let decision = evaluate_consensus_log_compaction("cluster-a", &certificates, &reports, &policy)
        .expect("decision");
    assert!(decision.should_compact);
    assert_eq!(decision.keep_certificate_ids.len(), 2);
    assert_eq!(decision.compact_certificate_ids.len(), 2);
}
