use mind_core::*;
use mind_store_sqlite::SqliteEventStore;
use serde_json::json;
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[test]
fn sqlite_v23_ledgers_round_trip_secret_connector_admission() {
    let mut store = SqliteEventStore::in_memory().unwrap();
    assert_eq!(
        store.current_schema_version().unwrap(),
        PLATFORM_SCHEMA_VERSION
    );

    let reference = SecretReference::new(
        SecretManagerBackend::ExternalGateway,
        "github/private-key",
        "key-a",
    )
    .unwrap();
    let plan = plan_secret_access(reference, "jwt", SecretAccessMode::DryRun, None).unwrap();
    let receipt = record_secret_access_receipt(
        &plan,
        Some("fingerprint".to_owned()),
        Some("v1".to_owned()),
        BTreeMap::new(),
    )
    .unwrap();
    let jwt_plan = plan_github_app_jwt_from_secret(1, 2, &plan, 540).unwrap();
    let jwt_receipt =
        record_github_app_jwt_receipt(&jwt_plan, &receipt, Some("jwt".to_owned()), None).unwrap();
    store.record_secret_access_plan(&plan).unwrap();
    store.record_secret_access_receipt(&receipt).unwrap();
    store.record_github_app_jwt_plan(&jwt_plan).unwrap();
    store.record_github_app_jwt_receipt(&jwt_receipt).unwrap();
    assert_eq!(store.secret_access_plans().unwrap().len(), 1);
    assert_eq!(store.github_app_jwt_receipts().unwrap().len(), 1);

    let job = ScheduledJob::new(
        ScheduledJobKind::ProviderExecution,
        "github",
        &json!({"x":1}),
        OffsetDateTime::now_utc(),
        3,
    )
    .unwrap();
    let worker_plan = plan_connector_worker_job(
        &job,
        "worker-a",
        ConnectorWorkerActionKind::GitHubActionExecution,
        ConnectorWorkerMode::DryRun,
    )
    .unwrap();
    let worker_receipt = record_connector_worker_execution_receipt(
        &worker_plan,
        Some(worker_plan.plan_hash.clone()),
        None,
        Vec::new(),
    )
    .unwrap();
    store
        .record_connector_worker_job_plan(&worker_plan)
        .unwrap();
    store
        .record_connector_worker_execution_receipt(&worker_receipt)
        .unwrap();
    assert_eq!(
        store.connector_worker_execution_receipts().unwrap().len(),
        1
    );
}
