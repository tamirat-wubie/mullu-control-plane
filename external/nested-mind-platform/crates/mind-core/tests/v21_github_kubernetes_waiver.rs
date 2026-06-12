use mind_core::{
    certify_waiver_escalation, hash_serializable, plan_branch_protection_reconcile,
    plan_github_check_run_write, plan_kubernetes_staging_chaos, plan_waiver_reviewer_assignment,
    production_branch_protection_policy, production_chaos_rehearsal_plan,
    record_branch_protection_reconcile_receipt, record_github_check_run_write_receipt,
    record_kubernetes_staging_chaos_receipt, BranchProtectionObservedState,
    BranchProtectionReconcileMode, BranchProtectionReconcileStatus, EventId, GitHubCheckConclusion,
    GitHubCheckRunOutput, GitHubCheckRunWriteMode, GitHubCheckRunWriteStatus,
    KubernetesChaosExecutionMode, KubernetesChaosReceiptStatus, WaiverAssignmentStatus,
    WaiverOperatorRole, WaiverReviewQueueItem, WaiverReviewStatus, WaiverReviewerCandidate,
};
use std::collections::{BTreeMap, BTreeSet};
use time::{Duration, OffsetDateTime};

#[test]
fn github_check_run_write_plan_and_receipt_verify() {
    let plan = plan_github_check_run_write(
        "mullusi/nested-mind-platform",
        "abc123",
        "mandatory-readiness-gates",
        GitHubCheckRunOutput::new("ready", "all gates satisfied"),
        Some(GitHubCheckConclusion::Success),
        Some("https://example.test/details".to_owned()),
        Some("gate-1".to_owned()),
        "nested-mind-readiness",
        GitHubCheckRunWriteMode::DryRun,
    )
    .expect("plan");
    plan.verify().expect("verify plan");
    assert_eq!(
        plan.rest_endpoint,
        "/repos/mullusi/nested-mind-platform/check-runs"
    );

    let receipt = record_github_check_run_write_receipt(&plan, None, None, None).expect("receipt");
    receipt.verify().expect("verify receipt");
    assert_eq!(receipt.status, GitHubCheckRunWriteStatus::DryRunAccepted);
}

#[test]
fn branch_protection_reconcile_detects_drift() {
    let policy = production_branch_protection_policy("mullusi/nested-mind-platform", "main")
        .expect("policy");
    let observed = BranchProtectionObservedState {
        required_status_checks: BTreeSet::from(["cargo test".to_owned()]),
        enforce_admins: false,
        required_approving_review_count: 1,
        require_code_owner_reviews: false,
        require_conversation_resolution: false,
        require_linear_history: false,
    };
    let plan = plan_branch_protection_reconcile(
        policy,
        Some(observed),
        BranchProtectionReconcileMode::DryRun,
    )
    .expect("plan");
    plan.verify().expect("verify plan");
    assert!(plan
        .drift
        .iter()
        .any(|finding| finding.contains("missing required status checks")));
    let receipt =
        record_branch_protection_reconcile_receipt(&plan, Some(serde_json::json!({"ok": true})))
            .expect("receipt");
    receipt.verify().expect("verify receipt");
    assert_eq!(
        receipt.status,
        BranchProtectionReconcileStatus::DryRunAccepted
    );
}

#[test]
fn kubernetes_staging_chaos_server_dry_run_receipt_verifies() {
    let chaos = production_chaos_rehearsal_plan(None).expect("chaos");
    let plan = plan_kubernetes_staging_chaos(
        &chaos,
        None,
        "nested-mind-staging",
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )
    .expect("kubernetes plan");
    plan.verify().expect("verify plan");
    assert!(plan
        .kubectl_commands
        .iter()
        .all(|command| command.contains("--dry-run=server")));

    let receipt = record_kubernetes_staging_chaos_receipt(
        &plan,
        Some(serde_json::json!({"serverDryRun": true})),
    )
    .expect("receipt");
    receipt.verify().expect("verify receipt");
    assert_eq!(
        receipt.status,
        KubernetesChaosReceiptStatus::ServerDryRunAccepted
    );
    assert!(receipt.server_dry_run);
    assert!(!receipt.live_side_effects);
}

#[test]
fn waiver_reviewer_assignment_escalates_missing_roles() {
    let review_id = EventId::new();
    let proposal_id = EventId::new();
    let opened_at = OffsetDateTime::now_utc();
    let due_at = opened_at + Duration::hours(4);
    let required_roles =
        BTreeSet::from([WaiverOperatorRole::Maintainer, WaiverOperatorRole::Security]);
    let queue_hash = hash_serializable(&(
        review_id,
        proposal_id,
        &Vec::<EventId>::new(),
        &"risk-owner".to_owned(),
        &required_roles,
        WaiverReviewStatus::Open,
        due_at,
        opened_at,
    ))
    .expect("hash");
    let queue_item = WaiverReviewQueueItem {
        review_id,
        proposal_id,
        blocker_ids: Vec::new(),
        risk_owner: "risk-owner".to_owned(),
        required_roles,
        status: WaiverReviewStatus::Open,
        due_at,
        queue_hash,
        opened_at,
    };
    queue_item.verify().expect("queue verify");

    let candidates = vec![WaiverReviewerCandidate::new(
        "maintainer-a",
        "platform",
        WaiverOperatorRole::Maintainer,
        true,
        0,
    )
    .expect("candidate")];
    let escalation_targets =
        BTreeMap::from([(WaiverOperatorRole::Security, "security-oncall".to_owned())]);
    let assignment =
        plan_waiver_reviewer_assignment(&queue_item, candidates, escalation_targets, 24)
            .expect("assignment");
    assignment.verify().expect("verify assignment");
    assert_eq!(assignment.status, WaiverAssignmentStatus::NeedsEscalation);

    let escalation =
        certify_waiver_escalation(&assignment, "security reviewer missing").expect("escalation");
    escalation.verify().expect("verify escalation");
    assert_eq!(escalation.escalated_to, vec!["security-oncall".to_owned()]);
}
