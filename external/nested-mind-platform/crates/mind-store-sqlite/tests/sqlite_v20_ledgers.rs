use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use std::collections::BTreeSet;
use time::{Duration, OffsetDateTime};

#[test]
fn sqlite_persists_v20_ledgers() {
    let mut store = SqliteEventStore::in_memory().unwrap();
    assert_eq!(
        store.current_schema_version().unwrap(),
        PLATFORM_SCHEMA_VERSION
    );

    let repository = "mullusi/nested-mind-platform";
    let head_sha = "abc123";
    let pr = GitHubPullRequestEvidence::new(
        repository,
        20,
        "v20 evidence",
        "tamirat",
        "main",
        "feature/v20",
        head_sha,
        false,
        false,
        Some("APPROVED".to_owned()),
        Vec::new(),
        GitHubEvidenceSource::Fixture,
    )
    .unwrap();
    let check = GitHubCheckRunEvidence::new(
        repository,
        head_sha,
        "cargo test",
        "completed",
        GitHubCheckConclusion::Success,
        None,
        None,
        GitHubEvidenceSource::Fixture,
    )
    .unwrap();
    let bundle = collect_github_readiness_evidence(
        pr,
        vec![check],
        BTreeSet::from(["cargo test".to_owned()]),
    )
    .unwrap();
    store
        .record_github_readiness_evidence_bundle(&bundle)
        .unwrap();
    assert_eq!(store.github_readiness_evidence_bundles().unwrap().len(), 1);

    let policy = production_branch_protection_policy(repository, "main").unwrap();
    store.record_branch_protection_policy(&policy).unwrap();
    let observed = BranchProtectionObservedState {
        required_status_checks: policy.required_status_checks.clone(),
        enforce_admins: true,
        required_approving_review_count: 2,
        require_code_owner_reviews: true,
        require_conversation_resolution: true,
        require_linear_history: true,
    };
    let report = evaluate_branch_protection_policy(&policy, observed).unwrap();
    store
        .record_branch_protection_evaluation_report(&report)
        .unwrap();
    assert!(store.branch_protection_evaluation_reports().unwrap()[0].compliant);

    let rehearsal = production_chaos_rehearsal_plan(None).unwrap();
    let adapter = plan_live_staging_chaos_adapter(
        &rehearsal,
        None,
        LiveChaosAdapterBackend::KubernetesServerDryRun,
        LiveChaosAdapterMode::ServerDryRun,
    )
    .unwrap();
    store
        .record_live_staging_chaos_adapter_plan(&adapter)
        .unwrap();
    let receipt = execute_live_staging_chaos_adapter_dry_run(&adapter).unwrap();
    store
        .record_live_staging_chaos_adapter_receipt(&receipt)
        .unwrap();
    assert_eq!(
        store.live_staging_chaos_adapter_receipts().unwrap().len(),
        1
    );

    let creative_input = CreativeEngineeringReportInput {
        observed_fractures: vec!["critical fracture".to_owned()],
        desired_next_layer: "sqlite v20".to_owned(),
        ..CreativeEngineeringReportInput::default()
    };
    let creative = generate_creative_engineering_report(creative_input).unwrap();
    let fuzz = generate_invariant_fuzz_run(
        MindId::new(),
        InvariantFuzzRunConfig {
            seed: 20,
            cases: 12,
            ..InvariantFuzzRunConfig::default()
        },
    )
    .unwrap();
    let gate = evaluate_production_readiness_gate(
        &creative,
        Some(&rehearsal),
        Some(&fuzz),
        ProductionReadinessGatePolicy::default(),
    )
    .unwrap();
    let proposal = ReadinessWaiverProposal::new(
        &gate,
        gate.blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect(),
        "maintainer-a",
        "sqlite waiver review",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )
    .unwrap();
    let item = open_waiver_review_queue_item(
        &proposal,
        &gate.blockers,
        BTreeSet::from([WaiverOperatorRole::Maintainer]),
        24,
    )
    .unwrap();
    let comment = WaiverReviewComment::new(
        item.review_id,
        "maintainer-a",
        WaiverOperatorRole::Maintainer,
        ReadinessWaiverVoteDecision::Approve,
        "approved",
    )
    .unwrap();
    let certificate = certify_waiver_review(&item, vec![comment]).unwrap();
    store
        .record_waiver_review_certificate(&certificate)
        .unwrap();
    assert_eq!(store.waiver_review_certificates().unwrap().len(), 1);
}
