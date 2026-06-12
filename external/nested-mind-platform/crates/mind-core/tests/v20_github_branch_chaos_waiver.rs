use mind_core::*;
use std::collections::BTreeSet;
use time::{Duration, OffsetDateTime};

#[test]
fn github_evidence_bundle_satisfies_required_checks() {
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
        vec!["readiness".to_owned()],
        GitHubEvidenceSource::Fixture,
    )
    .unwrap();
    let checks = required_readiness_check_names()
        .iter()
        .map(|name| {
            GitHubCheckRunEvidence::new(
                repository,
                head_sha,
                name.clone(),
                "completed",
                GitHubCheckConclusion::Success,
                Some("github-actions".to_owned()),
                None,
                GitHubEvidenceSource::Fixture,
            )
            .unwrap()
        })
        .collect::<Vec<_>>();
    let bundle =
        collect_github_readiness_evidence(pr, checks, required_readiness_check_names()).unwrap();
    assert_eq!(bundle.status, GitHubEvidenceBundleStatus::Satisfied);
    bundle.verify().unwrap();
    let artifacts = bundle.to_implementation_artifacts("test").unwrap();
    assert_eq!(artifacts.len(), 2);
}

#[test]
fn branch_protection_policy_detects_missing_checks() {
    let policy =
        production_branch_protection_policy("mullusi/nested-mind-platform", "main").unwrap();
    let observed = BranchProtectionObservedState {
        required_status_checks: BTreeSet::from(["cargo test".to_owned()]),
        enforce_admins: true,
        required_approving_review_count: 2,
        require_code_owner_reviews: true,
        require_conversation_resolution: true,
        require_linear_history: true,
    };
    let report = evaluate_branch_protection_policy(&policy, observed).unwrap();
    assert!(!report.compliant);
    assert!(report
        .missing_required_checks
        .contains("mandatory-readiness-gates"));
    report.verify().unwrap();
}

#[test]
fn live_staging_chaos_adapter_plan_and_receipt_verify() {
    let plan = production_chaos_rehearsal_plan(None).unwrap();
    let adapter = plan_live_staging_chaos_adapter(
        &plan,
        None,
        LiveChaosAdapterBackend::KubernetesServerDryRun,
        LiveChaosAdapterMode::ServerDryRun,
    )
    .unwrap();
    adapter.verify().unwrap();
    let receipt = execute_live_staging_chaos_adapter_dry_run(&adapter).unwrap();
    assert_eq!(receipt.status, LiveChaosAdapterStatus::DryRunAccepted);
    receipt.verify().unwrap();
}

#[test]
fn waiver_review_requires_required_roles() {
    let creative_input = CreativeEngineeringReportInput {
        observed_fractures: vec!["critical provider sdk pending".to_owned()],
        desired_next_layer: "waiver review".to_owned(),
        ..CreativeEngineeringReportInput::default()
    };
    let creative = generate_creative_engineering_report(creative_input).unwrap();
    let chaos = production_chaos_rehearsal_plan(None).unwrap();
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
        Some(&chaos),
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
        "test waiver review",
        "risk-owner-a",
        Some(OffsetDateTime::now_utc() + Duration::days(7)),
    )
    .unwrap();
    let item = open_waiver_review_queue_item(
        &proposal,
        &gate.blockers,
        BTreeSet::from([WaiverOperatorRole::Maintainer, WaiverOperatorRole::Security]),
        24,
    )
    .unwrap();
    let comment = WaiverReviewComment::new(
        item.review_id,
        "maintainer-a",
        WaiverOperatorRole::Maintainer,
        ReadinessWaiverVoteDecision::Approve,
        "ready for staging only",
    )
    .unwrap();
    let certificate = certify_waiver_review(&item, vec![comment]).unwrap();
    assert_eq!(certificate.status, WaiverReviewStatus::ChangesRequested);
    certificate.verify().unwrap();
}
