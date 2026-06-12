use mind_core::*;
use serde_json::json;
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[test]
fn secret_backed_github_app_jwt_receipts_verify() {
    let reference = SecretReference::new(
        SecretManagerBackend::ExternalGateway,
        "github-app/private-key",
        "github-app-key",
    )
    .unwrap();
    let plan = plan_secret_access(reference, "sign jwt", SecretAccessMode::DryRun, None).unwrap();
    let receipt = record_secret_access_receipt(
        &plan,
        Some("private-key-fingerprint".to_owned()),
        Some("v1".to_owned()),
        BTreeMap::new(),
    )
    .unwrap();
    let jwt_plan = plan_github_app_jwt_from_secret(123, 456, &plan, 540).unwrap();
    let jwt_receipt = record_github_app_jwt_receipt(
        &jwt_plan,
        &receipt,
        Some("jwt-fingerprint".to_owned()),
        Some(jwt_plan.claims_hash.clone()),
    )
    .unwrap();
    jwt_receipt.verify().unwrap();
}

#[test]
fn connector_worker_receipt_requires_external_evidence_when_approved() {
    let job = ScheduledJob::new(
        ScheduledJobKind::ProviderExecution,
        "github-check-run",
        &json!({"repository":"mullusi/nested-mind-platform"}),
        OffsetDateTime::now_utc(),
        3,
    )
    .unwrap();
    let plan = plan_connector_worker_job(
        &job,
        "worker-a",
        ConnectorWorkerActionKind::GitHubActionExecution,
        ConnectorWorkerMode::ExecuteApproved,
    )
    .unwrap();
    assert!(record_connector_worker_execution_receipt(&plan, None, None, Vec::new()).is_err());
    let receipt = record_connector_worker_execution_receipt(
        &plan,
        Some(plan.plan_hash.clone()),
        None,
        Vec::new(),
    )
    .unwrap();
    receipt.verify().unwrap();
}

#[test]
fn kubernetes_admission_audit_requires_rehearsal_annotation() {
    let rehearsal = production_chaos_rehearsal_plan(None).unwrap();
    let k8s_plan = plan_kubernetes_staging_chaos(
        &rehearsal,
        None,
        "nested-mind-staging",
        "nested-mind-chaos-runner",
        KubernetesChaosExecutionMode::ServerDryRun,
        None,
    )
    .unwrap();
    let request =
        plan_kubernetes_server_dry_run_execution(&k8s_plan, "staging", "nested-mind").unwrap();
    let dry_receipt =
        record_kubernetes_server_dry_run_receipt(&request, &k8s_plan, None, Vec::new()).unwrap();
    let audit = plan_kubernetes_admission_audit(
        &request,
        KubernetesAdmissionOperation::Create,
        dry_receipt.receipt_hash.clone(),
        "worker-a",
    )
    .unwrap();
    let (receipt, report) = record_kubernetes_admission_audit_receipt(
        &audit,
        &dry_receipt,
        &KubernetesAdmissionAuditPolicy::default(),
        Some("audit-uid".to_owned()),
        BTreeMap::new(),
        Vec::new(),
        true,
    )
    .unwrap();
    assert_eq!(receipt.status, KubernetesAdmissionAuditStatus::Rejected);
    assert_eq!(report.status, KubernetesAdmissionAuditStatus::Rejected);
}

#[test]
fn waiver_notification_adapter_plan_and_receipt_verify() {
    let notification_plan_id = EventId::new();
    let assignment_plan_id = EventId::new();
    let review_id = EventId::new();
    let proposal_id = EventId::new();
    let channel = WaiverNotificationChannel::Manual;
    let recipients = vec!["maintainer-a".to_owned()];
    let subject = "Review waiver".to_owned();
    let body_hash = hash_serializable(&"body").unwrap();
    let metadata = BTreeMap::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        notification_plan_id,
        assignment_plan_id,
        review_id,
        proposal_id,
        channel,
        &recipients,
        &subject,
        &body_hash,
        &metadata,
        created_at,
    ))
    .unwrap();
    let notification = WaiverNotificationPlan {
        notification_plan_id,
        assignment_plan_id,
        review_id,
        proposal_id,
        channel,
        recipients,
        subject,
        body_hash: body_hash.clone(),
        metadata,
        plan_hash,
        created_at,
    };
    notification.verify().unwrap();
    let adapter = plan_waiver_notification_adapter(
        &notification,
        WaiverNotificationAdapterKind::GenericWebhook,
        "notification-gateway",
        body_hash,
        WaiverNotificationAdapterMode::DryRun,
    )
    .unwrap();
    let receipt = record_waiver_notification_adapter_receipt(
        &adapter,
        None,
        Some("dry-run-message".to_owned()),
        Some(adapter.plan_hash.clone()),
        Vec::new(),
    )
    .unwrap();
    receipt.verify().unwrap();
}
