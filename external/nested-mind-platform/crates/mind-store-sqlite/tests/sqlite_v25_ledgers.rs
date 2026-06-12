use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use std::collections::BTreeMap;

#[test]
fn sqlite_schema_advances_to_v25() {
    let store = SqliteEventStore::in_memory().expect("store");
    let report = store.schema_report().expect("schema");
    assert_eq!(report.current_version_after, PLATFORM_SCHEMA_VERSION);
    assert_eq!(PLATFORM_SCHEMA_VERSION, 25);
}

#[test]
fn sqlite_persists_connector_orchestration_reports() {
    let mut store = SqliteEventStore::in_memory().expect("store");
    let plan = plan_connector_orchestration(
        "worker-a",
        "readiness action",
        ConnectorOrchestrationMode::ExecuteApproved,
        Vec::new(),
    )
    .expect("plan");
    let mut artifacts = BTreeMap::new();
    artifacts.insert("secret".to_owned(), "secret-hash".to_owned());
    artifacts.insert("github_token".to_owned(), "token-hash".to_owned());
    artifacts.insert("kubernetes_audit".to_owned(), "audit-hash".to_owned());
    artifacts.insert("notification".to_owned(), "notification-hash".to_owned());
    let report =
        evaluate_connector_orchestration(&plan, &[], &[], &[], &[], artifacts).expect("report");
    store
        .record_connector_orchestration_plan(&plan)
        .expect("record plan");
    store
        .record_connector_orchestration_report(&report)
        .expect("record report");
    assert_eq!(
        store.connector_orchestration_plans().expect("plans").len(),
        1
    );
    assert_eq!(
        store
            .connector_orchestration_reports()
            .expect("reports")
            .len(),
        1
    );
}
