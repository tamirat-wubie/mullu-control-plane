use mind_core::*;
use std::collections::BTreeMap;

#[test]
fn connector_orchestration_blocks_until_required_artifacts_exist() {
    let plan = plan_connector_orchestration(
        "worker-a",
        "readiness action",
        ConnectorOrchestrationMode::ExecuteApproved,
        Vec::new(),
    )
    .expect("plan");
    let report = evaluate_connector_orchestration(&plan, &[], &[], &[], &[], BTreeMap::new())
        .expect("report");
    assert_eq!(report.status, ConnectorOrchestrationStatus::Blocked);
    assert!(!report.missing_artifacts.is_empty());
}

#[test]
fn connector_orchestration_accepts_external_artifact_evidence() {
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
    assert_eq!(
        report.status,
        ConnectorOrchestrationStatus::EvidenceComplete
    );
    report.verify().expect("verify");
}
