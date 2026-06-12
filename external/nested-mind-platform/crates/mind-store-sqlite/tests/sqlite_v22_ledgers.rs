use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use std::collections::BTreeMap;

#[test]
fn sqlite_v22_ledgers_round_trip() {
    let mut store = SqliteEventStore::in_memory()
        .unwrap()
        .with_signature_requirement(SignatureRequirement::Optional);
    assert_eq!(
        store.current_schema_version().unwrap(),
        PLATFORM_SCHEMA_VERSION
    );

    let token_request = GitHubAppInstallationTokenRequest::new(
        123,
        456,
        "mullusi/nested-mind-platform",
        "key-fingerprint",
        BTreeMap::new(),
        Vec::new(),
        3600,
    )
    .unwrap();
    let token_plan =
        plan_github_app_installation_token(token_request, GitHubAppTokenMode::DryRun).unwrap();
    let token_receipt = record_github_app_installation_token_receipt(
        &token_plan,
        None,
        Some(&token_plan.rest_payload),
    )
    .unwrap();
    store
        .record_github_app_installation_token_plan(&token_plan)
        .unwrap();
    store
        .record_github_app_installation_token_receipt(&token_receipt)
        .unwrap();
    assert_eq!(
        store.github_app_installation_token_plans().unwrap().len(),
        1
    );
    assert_eq!(
        store
            .github_app_installation_token_receipts()
            .unwrap()
            .len(),
        1
    );

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
    let action_receipt = record_github_action_execution_receipt(
        &action_plan,
        &token_receipt,
        None,
        Some(&action_plan.rest_payload),
    )
    .unwrap();
    store
        .record_github_action_execution_plan(&action_plan)
        .unwrap();
    store
        .record_github_action_execution_receipt(&action_receipt)
        .unwrap();
    assert_eq!(store.github_action_execution_plans().unwrap().len(), 1);
    assert_eq!(store.github_action_execution_receipts().unwrap().len(), 1);

    let policy =
        production_branch_protection_policy("mullusi/nested-mind-platform", "main").unwrap();
    let reconcile =
        plan_branch_protection_reconcile(policy, None, BranchProtectionReconcileMode::DryRun)
            .unwrap();
    let reconcile_receipt = record_branch_protection_reconcile_receipt(
        &reconcile,
        Some(reconcile.rest_payload.clone()),
    )
    .unwrap();
    let worker_plan =
        plan_branch_protection_reconcile_worker(&[reconcile], BranchProtectionWorkerMode::DryRun)
            .unwrap();
    let worker_report =
        record_branch_protection_worker_report(&worker_plan, &[reconcile_receipt]).unwrap();
    store
        .record_branch_protection_worker_plan(&worker_plan)
        .unwrap();
    store
        .record_branch_protection_worker_report(&worker_report)
        .unwrap();
    assert_eq!(store.branch_protection_worker_reports().unwrap().len(), 1);

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
    let dry_receipt =
        record_kubernetes_server_dry_run_receipt(&dry_request, &kube_plan, None, Vec::new())
            .unwrap();
    store
        .record_kubernetes_dry_run_execution_request(&dry_request)
        .unwrap();
    store
        .record_kubernetes_dry_run_execution_receipt(&dry_receipt)
        .unwrap();
    assert_eq!(
        store.kubernetes_dry_run_execution_receipts().unwrap().len(),
        1
    );
}
