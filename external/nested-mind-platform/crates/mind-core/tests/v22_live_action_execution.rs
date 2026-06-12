use mind_core::*;
use serde_json::json;
use std::collections::BTreeMap;

#[test]
fn github_app_token_and_action_execution_receipts_verify() {
    let mut permissions = BTreeMap::new();
    permissions.insert("checks".to_owned(), "write".to_owned());
    let request = GitHubAppInstallationTokenRequest::new(
        123,
        456,
        "mullusi/nested-mind-platform",
        "key-fingerprint",
        permissions,
        Vec::new(),
        3600,
    )
    .unwrap();
    let token_plan =
        plan_github_app_installation_token(request, GitHubAppTokenMode::DryRun).unwrap();
    let token_receipt = record_github_app_installation_token_receipt(
        &token_plan,
        None,
        Some(&token_plan.rest_payload),
    )
    .unwrap();
    token_receipt.verify().unwrap();

    let check_plan = plan_github_check_run_write(
        "mullusi/nested-mind-platform",
        "abc123",
        "mandatory-readiness-gates",
        GitHubCheckRunOutput::new("readiness", "ok"),
        Some(GitHubCheckConclusion::Success),
        None,
        None,
        "nested-mind-readiness",
        GitHubCheckRunWriteMode::DryRun,
    )
    .unwrap();
    let action_plan = plan_github_check_run_action_execution(
        &token_plan,
        &check_plan,
        GitHubActionExecutionMode::DryRun,
    )
    .unwrap();
    let receipt = record_github_action_execution_receipt(
        &action_plan,
        &token_receipt,
        None,
        Some(&action_plan.rest_payload),
    )
    .unwrap();
    receipt.verify().unwrap();
    assert_eq!(receipt.status, GitHubActionExecutionStatus::DryRunAccepted);
}

#[test]
fn branch_worker_and_kubernetes_dry_run_reports_verify() {
    let policy =
        production_branch_protection_policy("mullusi/nested-mind-platform", "main").unwrap();
    let reconcile =
        plan_branch_protection_reconcile(policy, None, BranchProtectionReconcileMode::DryRun)
            .unwrap();
    let receipt = record_branch_protection_reconcile_receipt(
        &reconcile,
        Some(reconcile.rest_payload.clone()),
    )
    .unwrap();
    let worker_plan =
        plan_branch_protection_reconcile_worker(&[reconcile], BranchProtectionWorkerMode::DryRun)
            .unwrap();
    let worker_report = record_branch_protection_worker_report(&worker_plan, &[receipt]).unwrap();
    worker_report.verify().unwrap();

    let rehearsal = production_chaos_rehearsal_plan(None).unwrap();
    let kube_plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        "nested-mind-staging",
        "nested-mind-chaos",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )
    .unwrap();
    let dry_request =
        plan_kubernetes_server_dry_run_execution(&kube_plan, "staging", "nested-mind-platform")
            .unwrap();
    let dry_receipt = record_kubernetes_server_dry_run_receipt(
        &dry_request,
        &kube_plan,
        Some(&json!({"accepted": true})),
        vec![],
    )
    .unwrap();
    dry_receipt.verify().unwrap();
    assert_eq!(
        dry_receipt.status,
        KubernetesDryRunExecutionStatus::ServerAccepted
    );
}

#[test]
fn waiver_notification_delivery_binds_assignment() {
    let creative = generate_creative_engineering_report(CreativeEngineeringReportInput {
        deployment_stage: "staging".to_owned(),
        current_schema_version: PLATFORM_SCHEMA_VERSION,
        observed_fractures: vec!["provider sdk pending".to_owned()],
        enabled_features: vec![],
        desired_next_layer: "test".to_owned(),
        constraints: BTreeMap::new(),
    })
    .unwrap();
    let chaos = production_chaos_rehearsal_plan(None).unwrap();
    let fuzz = generate_invariant_fuzz_run(
        MindId::new(),
        InvariantFuzzRunConfig {
            seed: 22,
            cases: 12,
            include_valid: true,
            include_projection_probes: true,
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
        gate.blockers.iter().map(|b| b.blocker_id).collect(),
        "maintainer-a",
        "test waiver",
        "risk-owner-a",
        None,
    )
    .unwrap();
    let mut roles = std::collections::BTreeSet::new();
    roles.insert(WaiverOperatorRole::Maintainer);
    let queue = open_waiver_review_queue_item(&proposal, &gate.blockers, roles, 24).unwrap();
    let candidate = WaiverReviewerCandidate::new(
        "maintainer-reviewer",
        "platform",
        WaiverOperatorRole::Maintainer,
        true,
        0,
    )
    .unwrap();
    let assignment =
        plan_waiver_reviewer_assignment(&queue, vec![candidate], BTreeMap::new(), 24).unwrap();
    let plan = plan_waiver_notification_delivery(
        &assignment,
        WaiverNotificationChannel::Manual,
        "review",
        "body",
    )
    .unwrap();
    let receipt = record_waiver_notification_receipt(
        &plan,
        plan.recipients.clone(),
        Some("manual".to_owned()),
        None,
        vec![],
    )
    .unwrap();
    receipt.verify().unwrap();
    assert_eq!(receipt.status, WaiverNotificationStatus::Delivered);
}
