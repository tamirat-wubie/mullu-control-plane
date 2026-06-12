use mind_core::{
    plan_branch_protection_reconcile, plan_github_check_run_write, plan_kubernetes_staging_chaos,
    production_branch_protection_policy, production_chaos_rehearsal_plan,
    record_branch_protection_reconcile_receipt, record_github_check_run_write_receipt,
    record_kubernetes_staging_chaos_receipt, BranchProtectionReconcileMode, GitHubCheckConclusion,
    GitHubCheckRunOutput, GitHubCheckRunWriteMode, KubernetesChaosExecutionMode,
    PLATFORM_SCHEMA_VERSION,
};
use mind_store_sqlite::SqliteEventStore;

#[test]
fn sqlite_v21_schema_and_ledgers_round_trip() {
    let mut store = SqliteEventStore::in_memory().expect("store");
    let report = store.schema_report().expect("schema");
    assert_eq!(report.current_version_after, PLATFORM_SCHEMA_VERSION);
    assert_eq!(report.target_version, PLATFORM_SCHEMA_VERSION);

    let github_plan = plan_github_check_run_write(
        "mullusi/nested-mind-platform",
        "abc123",
        "mandatory-readiness-gates",
        GitHubCheckRunOutput::new("ready", "passed"),
        Some(GitHubCheckConclusion::Success),
        None,
        None,
        "nested-mind-readiness",
        GitHubCheckRunWriteMode::DryRun,
    )
    .expect("github plan");
    store
        .record_github_check_run_write_plan(&github_plan)
        .expect("record plan");
    let github_receipt = record_github_check_run_write_receipt(&github_plan, None, None, None)
        .expect("github receipt");
    store
        .record_github_check_run_write_receipt(&github_receipt)
        .expect("record receipt");
    assert_eq!(
        store.github_check_run_write_plans().expect("plans").len(),
        1
    );
    assert_eq!(
        store
            .github_check_run_write_receipts()
            .expect("receipts")
            .len(),
        1
    );

    let branch_policy = production_branch_protection_policy("mullusi/nested-mind-platform", "main")
        .expect("policy");
    let branch_plan = plan_branch_protection_reconcile(
        branch_policy,
        None,
        BranchProtectionReconcileMode::PlanOnly,
    )
    .expect("branch plan");
    store
        .record_branch_protection_reconcile_plan(&branch_plan)
        .expect("record branch plan");
    let branch_receipt =
        record_branch_protection_reconcile_receipt(&branch_plan, None).expect("branch receipt");
    store
        .record_branch_protection_reconcile_receipt(&branch_receipt)
        .expect("record branch receipt");
    assert_eq!(
        store
            .branch_protection_reconcile_plans()
            .expect("branch plans")
            .len(),
        1
    );

    let chaos = production_chaos_rehearsal_plan(None).expect("chaos");
    let kube_plan = plan_kubernetes_staging_chaos(
        &chaos,
        None,
        "nested-mind-staging",
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )
    .expect("kube plan");
    store
        .record_kubernetes_staging_chaos_plan(&kube_plan)
        .expect("record kube plan");
    let kube_receipt =
        record_kubernetes_staging_chaos_receipt(&kube_plan, None).expect("kube receipt");
    store
        .record_kubernetes_staging_chaos_receipt(&kube_receipt)
        .expect("record kube receipt");
    assert_eq!(
        store
            .kubernetes_staging_chaos_plans()
            .expect("kube plans")
            .len(),
        1
    );
    assert_eq!(
        store
            .kubernetes_staging_chaos_receipts()
            .expect("kube receipts")
            .len(),
        1
    );
}
