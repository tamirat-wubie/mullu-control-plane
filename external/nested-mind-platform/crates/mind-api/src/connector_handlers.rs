//! Purpose: connector, credential, token, Kubernetes adapter, notification, and action-promotion handlers for the Nested Mind API.
//! Governance scope: secret access planning, GitHub token/JWT receipts, connector workers, Kubernetes audit/dry-run adapters, notification delivery, action promotion, and waiver notification endpoints.
//! Dependencies: API state, connector and credential contracts, Kubernetes adapter contracts, notification contracts, action promotion gates, and audit/event stores.
//! Invariants: admin authorization, hash/fingerprint-only credential evidence, receipt persistence, connector orchestration checks, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_github_app_installation_token_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubAppInstallationTokenPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .github_app_installation_token_plans()?,
    ))
}

pub(super) async fn create_github_app_installation_token_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubAppInstallationTokenApiRequest>,
) -> Result<Json<GitHubAppInstallationTokenPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mode = request.mode;
    let token_request = GitHubAppInstallationTokenRequest::new(
        request.app_id,
        request.installation_id,
        request.repository,
        request.private_key_fingerprint,
        request.permissions,
        request.repositories,
        request.token_ttl_seconds,
    )?;
    let plan = plan_github_app_installation_token(token_request, mode)?;
    state
        .store
        .write()
        .await
        .record_github_app_installation_token_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_app_installation_token_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubAppInstallationTokenReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .github_app_installation_token_receipts()?,
    ))
}

pub(super) async fn create_github_app_installation_token_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubAppInstallationTokenReceiptApiRequest>,
) -> Result<Json<GitHubAppInstallationTokenReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_github_app_installation_token_receipt(
        &request.plan,
        request.token_fingerprint,
        request.response_payload.as_ref(),
    )?;
    state
        .store
        .write()
        .await
        .record_github_app_installation_token_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_github_action_execution_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubActionExecutionPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.github_action_execution_plans()?,
    ))
}

pub(super) async fn create_github_action_execution_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubActionExecutionPlanApiRequest>,
) -> Result<Json<GitHubActionExecutionPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = if let Some(check_plan) = request.check_run_plan {
        plan_github_check_run_action_execution(&request.token_plan, &check_plan, request.mode)?
    } else if let Some(branch_plan) = request.branch_protection_plan {
        plan_branch_protection_action_execution(&request.token_plan, &branch_plan, request.mode)?
    } else {
        return Err(ApiError(MindError::Store(
            "GitHub action execution requires check_run_plan or branch_protection_plan".to_owned(),
        )));
    };
    state
        .store
        .write()
        .await
        .record_github_action_execution_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_action_execution_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubActionExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .github_action_execution_receipts()?,
    ))
}

pub(super) async fn create_github_action_execution_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubActionExecutionReceiptApiRequest>,
) -> Result<Json<GitHubActionExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_github_action_execution_receipt(
        &request.plan,
        &request.token_receipt,
        request.http_status,
        request.response_payload.as_ref(),
    )?;
    state
        .store
        .write()
        .await
        .record_github_action_execution_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_secret_access_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<SecretAccessPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.secret_access_plans()?))
}

pub(super) async fn create_secret_access_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<SecretAccessApiRequest>,
) -> Result<Json<SecretAccessPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mut reference = SecretReference::new(request.backend, request.locator, request.key_id)?;
    if let Some(version) = request.version {
        reference = reference.with_version(version);
    }
    let plan = plan_secret_access(
        reference,
        request.purpose,
        request.mode,
        request.allowed_fingerprint,
    )?;
    state.store.write().await.record_secret_access_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_secret_access_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<SecretAccessReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.secret_access_receipts()?))
}

pub(super) async fn create_secret_access_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<SecretAccessReceiptApiRequest>,
) -> Result<Json<SecretAccessReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_secret_access_receipt(
        &request.plan,
        request.material_fingerprint,
        request.secret_version,
        request.metadata,
    )?;
    state
        .store
        .write()
        .await
        .record_secret_access_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_github_app_jwt_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubAppJwtPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.github_app_jwt_plans()?))
}

pub(super) async fn create_github_app_jwt_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubAppJwtPlanApiRequest>,
) -> Result<Json<GitHubAppJwtPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_github_app_jwt_from_secret(
        request.app_id,
        request.installation_id,
        &request.secret_plan,
        request.ttl_seconds,
    )?;
    state
        .store
        .write()
        .await
        .record_github_app_jwt_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_app_jwt_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubAppJwtReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.github_app_jwt_receipts()?))
}

pub(super) async fn create_github_app_jwt_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubAppJwtReceiptApiRequest>,
) -> Result<Json<GitHubAppJwtReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_github_app_jwt_receipt(
        &request.plan,
        &request.secret_receipt,
        request.jwt_fingerprint,
        request.signer_response_hash,
    )?;
    state
        .store
        .write()
        .await
        .record_github_app_jwt_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_connector_worker_job_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConnectorWorkerJobPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.connector_worker_job_plans()?))
}

pub(super) async fn create_connector_worker_job_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConnectorWorkerPlanApiRequest>,
) -> Result<Json<ConnectorWorkerJobPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_connector_worker_job(
        &request.job,
        request.worker_id,
        request.action_kind,
        request.mode,
    )?;
    state
        .store
        .write()
        .await
        .record_connector_worker_job_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_connector_worker_execution_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConnectorWorkerExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .connector_worker_execution_receipts()?,
    ))
}

pub(super) async fn create_connector_worker_execution_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConnectorWorkerReceiptApiRequest>,
) -> Result<Json<ConnectorWorkerExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_connector_worker_execution_receipt(
        &request.plan,
        request.external_receipt_hash,
        request.response_hash,
        request.errors,
    )?;
    state
        .store
        .write()
        .await
        .record_connector_worker_execution_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_kubernetes_admission_audit_requests(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAdmissionAuditRequest>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_admission_audit_requests()?,
    ))
}

pub(super) async fn system_kubernetes_admission_audit_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAdmissionAuditReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_admission_audit_receipts()?,
    ))
}

pub(super) async fn system_kubernetes_admission_audit_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAdmissionAuditReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_admission_audit_reports()?,
    ))
}

pub(super) async fn create_kubernetes_admission_audit(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesAdmissionAuditApiRequest>,
) -> Result<Json<KubernetesAdmissionAuditReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let audit_request = plan_kubernetes_admission_audit(
        &request.dry_run_request,
        request.operation,
        request.object_hash,
        request.user,
    )?;
    let policy = KubernetesAdmissionAuditPolicy::default();
    let (receipt, report) = record_kubernetes_admission_audit_receipt(
        &audit_request,
        &request.dry_run_receipt,
        &policy,
        request.audit_uid,
        request.annotations,
        request.warnings,
        request.admitted,
    )?;
    let mut store = state.store.write().await;
    store.record_kubernetes_admission_audit_request(&audit_request)?;
    store.record_kubernetes_admission_audit_receipt(&receipt)?;
    store.record_kubernetes_admission_audit_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_waiver_notification_adapter_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverNotificationAdapterPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .waiver_notification_adapter_plans()?,
    ))
}

pub(super) async fn create_waiver_notification_adapter_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverNotificationAdapterPlanApiRequest>,
) -> Result<Json<WaiverNotificationAdapterPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_waiver_notification_adapter(
        &request.notification_plan,
        request.adapter_kind,
        request.endpoint_reference,
        request.request_template_hash,
        request.mode,
    )?;
    state
        .store
        .write()
        .await
        .record_waiver_notification_adapter_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_waiver_notification_adapter_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverNotificationAdapterReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .waiver_notification_adapter_receipts()?,
    ))
}

pub(super) async fn create_waiver_notification_adapter_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverNotificationAdapterReceiptApiRequest>,
) -> Result<Json<WaiverNotificationAdapterReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_waiver_notification_adapter_receipt(
        &request.adapter_plan,
        request.notification_receipt.as_ref(),
        request.provider_message_id,
        request.provider_response_hash,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_waiver_notification_adapter_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_live_secret_connector_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<LiveSecretConnectorPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.live_secret_connector_plans()?,
    ))
}

pub(super) async fn create_live_secret_connector_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LiveSecretConnectorPlanApiRequest>,
) -> Result<Json<LiveSecretConnectorPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan =
        plan_live_secret_connector(&request.access_plan, request.mode, request.request_template)?;
    state
        .store
        .write()
        .await
        .record_live_secret_connector_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_live_secret_connector_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<LiveSecretConnectorReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.live_secret_connector_receipts()?,
    ))
}

pub(super) async fn create_live_secret_connector_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LiveSecretConnectorReceiptApiRequest>,
) -> Result<Json<LiveSecretConnectorReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_live_secret_connector_receipt(
        &request.plan,
        &request.access_receipt,
        request.provider_request_id,
        request.provider_response_hash,
        request.warnings,
    )?;
    state
        .store
        .write()
        .await
        .record_live_secret_connector_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_github_token_exchange_worker_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubTokenExchangeWorkerPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .github_token_exchange_worker_plans()?,
    ))
}

pub(super) async fn create_github_token_exchange_worker_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubTokenExchangeWorkerPlanApiRequest>,
) -> Result<Json<GitHubTokenExchangeWorkerPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_github_token_exchange_worker(
        request.repository,
        request.installation_id,
        &request.jwt_receipt,
        &request.secret_connector,
        request.mode,
        request.permissions_hash,
    )?;
    state
        .store
        .write()
        .await
        .record_github_token_exchange_worker_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_token_exchange_worker_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubTokenExchangeWorkerReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .github_token_exchange_worker_receipts()?,
    ))
}

pub(super) async fn create_github_token_exchange_worker_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubTokenExchangeWorkerReceiptApiRequest>,
) -> Result<Json<GitHubTokenExchangeWorkerReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt =
        record_github_token_exchange_worker_receipt(&request.plan, &request.token_receipt)?;
    state
        .store
        .write()
        .await
        .record_github_token_exchange_worker_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_kubernetes_audit_log_collector_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAuditLogCollectorPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_audit_log_collector_plans()?,
    ))
}

pub(super) async fn create_kubernetes_audit_log_collector_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesAuditLogCollectorPlanApiRequest>,
) -> Result<Json<KubernetesAuditLogCollectorPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_kubernetes_audit_log_collector(
        &request.admission_report,
        request.namespace,
        request.mode,
        request.previous_watermark,
    )?;
    state
        .store
        .write()
        .await
        .record_kubernetes_audit_log_collector_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_kubernetes_audit_log_collector_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAuditLogCollectorReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_audit_log_collector_reports()?,
    ))
}

pub(super) async fn create_kubernetes_audit_log_collector_report(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesAuditLogCollectorReportApiRequest>,
) -> Result<Json<KubernetesAuditLogCollectorReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = record_kubernetes_audit_log_collector_report(
        &request.plan,
        &request.admission_receipt,
        request.observed_event_count,
        request.audit_uids,
        request.new_watermark,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_kubernetes_audit_log_collector_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_notification_delivery_client_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<NotificationDeliveryClientPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .notification_delivery_client_plans()?,
    ))
}

pub(super) async fn create_notification_delivery_client_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<NotificationDeliveryClientPlanApiRequest>,
) -> Result<Json<NotificationDeliveryClientPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_notification_delivery_client(
        &request.adapter_plan,
        request.mode,
        request.endpoint_reference,
        request.request_template,
    )?;
    state
        .store
        .write()
        .await
        .record_notification_delivery_client_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_notification_delivery_client_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<NotificationDeliveryClientReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .notification_delivery_client_receipts()?,
    ))
}

pub(super) async fn create_notification_delivery_client_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<NotificationDeliveryClientReceiptApiRequest>,
) -> Result<Json<NotificationDeliveryClientReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_notification_delivery_client_receipt(
        &request.plan,
        &request.adapter_receipt,
        request.provider_message_id,
        request.provider_response_hash,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_notification_delivery_client_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_connector_orchestration_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConnectorOrchestrationPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.connector_orchestration_plans()?,
    ))
}

pub(super) async fn create_connector_orchestration_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConnectorOrchestrationPlanApiRequest>,
) -> Result<Json<ConnectorOrchestrationPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_connector_orchestration(
        request.worker_id,
        request.purpose,
        request.mode,
        request.required_artifacts,
    )?;
    state
        .store
        .write()
        .await
        .record_connector_orchestration_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_connector_orchestration_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConnectorOrchestrationReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.connector_orchestration_reports()?,
    ))
}

pub(super) async fn create_connector_orchestration_report(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConnectorOrchestrationReportApiRequest>,
) -> Result<Json<ConnectorOrchestrationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = evaluate_connector_orchestration(
        &request.plan,
        &request.secret_receipts,
        &request.token_receipts,
        &request.audit_reports,
        &request.notification_receipts,
        request.external_artifacts,
    )?;
    state
        .store
        .write()
        .await
        .record_connector_orchestration_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_kubernetes_audit_source_adapter_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAuditSourceAdapterPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_audit_source_adapter_plans()?,
    ))
}

pub(super) async fn create_kubernetes_audit_source_adapter_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesAuditSourceAdapterPlanApiRequest>,
) -> Result<Json<KubernetesAuditSourceAdapterPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_kubernetes_audit_source_adapter(
        &request.collector_plan,
        request.kind,
        request.mode,
        request.source_reference,
        request.request_template,
    )?;
    state
        .store
        .write()
        .await
        .record_kubernetes_audit_source_adapter_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_kubernetes_audit_source_adapter_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesAuditSourceAdapterReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_audit_source_adapter_receipts()?,
    ))
}

pub(super) async fn create_kubernetes_audit_source_adapter_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesAuditSourceAdapterReceiptApiRequest>,
) -> Result<Json<KubernetesAuditSourceAdapterReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_kubernetes_audit_source_adapter_receipt(
        &request.plan,
        &request.collector_report,
        request.provider_response_hash,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_kubernetes_audit_source_adapter_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_notification_provider_delivery_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<NotificationProviderDeliveryPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .notification_provider_delivery_plans()?,
    ))
}

pub(super) async fn create_notification_provider_delivery_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<NotificationProviderDeliveryPlanApiRequest>,
) -> Result<Json<NotificationProviderDeliveryPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_notification_provider_delivery(
        &request.client_plan,
        request.provider_kind,
        request.mode,
        request.endpoint_reference,
        request.request_template,
    )?;
    state
        .store
        .write()
        .await
        .record_notification_provider_delivery_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_notification_provider_delivery_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<NotificationProviderDeliveryReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .notification_provider_delivery_receipts()?,
    ))
}

pub(super) async fn create_notification_provider_delivery_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<NotificationProviderDeliveryReceiptApiRequest>,
) -> Result<Json<NotificationProviderDeliveryReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_notification_provider_delivery_receipt(
        &request.plan,
        &request.client_receipt,
        request.provider_message_id,
        request.provider_response_hash,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_notification_provider_delivery_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_action_promotion_gate_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ActionPromotionGateReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.action_promotion_gate_reports()?,
    ))
}

pub(super) async fn evaluate_action_promotion_gate_api(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ActionPromotionGateApiRequest>,
) -> Result<Json<ActionPromotionGateReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = evaluate_action_promotion_gate(
        &request.policy,
        &request.orchestration,
        &request.audit_source_receipts,
        &request.notification_provider_receipts,
    )?;
    state
        .store
        .write()
        .await
        .record_action_promotion_gate_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_branch_protection_worker_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionWorkerPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.branch_protection_worker_plans()?,
    ))
}

pub(super) async fn create_branch_protection_worker_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionWorkerPlanApiRequest>,
) -> Result<Json<BranchProtectionWorkerPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_branch_protection_reconcile_worker(&request.plans, request.mode)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_worker_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_branch_protection_worker_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionWorkerReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .branch_protection_worker_reports()?,
    ))
}

pub(super) async fn create_branch_protection_worker_report(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionWorkerReportApiRequest>,
) -> Result<Json<BranchProtectionWorkerReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = record_branch_protection_worker_report(&request.plan, &request.receipts)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_worker_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_kubernetes_dry_run_execution_requests(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesDryRunExecutionRequest>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_dry_run_execution_requests()?,
    ))
}

pub(super) async fn create_kubernetes_dry_run_execution(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesDryRunExecutionApiRequest>,
) -> Result<Json<serde_json::Value>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let dry_request = plan_kubernetes_server_dry_run_execution(
        &request.plan,
        request.context_name,
        request.field_manager,
    )?;
    let receipt = record_kubernetes_server_dry_run_receipt(
        &dry_request,
        &request.plan,
        request.response_payload.as_ref(),
        request.warnings,
    )?;
    {
        let mut store = state.store.write().await;
        store.record_kubernetes_dry_run_execution_request(&dry_request)?;
        store.record_kubernetes_dry_run_execution_receipt(&receipt)?;
    }
    Ok(Json(json!({ "request": dry_request, "receipt": receipt })))
}

pub(super) async fn system_kubernetes_dry_run_execution_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesDryRunExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .kubernetes_dry_run_execution_receipts()?,
    ))
}

pub(super) async fn system_waiver_notification_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverNotificationPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.waiver_notification_plans()?))
}

pub(super) async fn create_waiver_notification_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverNotificationPlanApiRequest>,
) -> Result<Json<WaiverNotificationPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_waiver_notification_delivery(
        &request.assignment,
        request.channel.unwrap_or(WaiverNotificationChannel::Manual),
        request.subject,
        request.body,
    )?;
    state
        .store
        .write()
        .await
        .record_waiver_notification_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_waiver_notification_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverNotificationReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.waiver_notification_receipts()?,
    ))
}

pub(super) async fn create_waiver_notification_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverNotificationReceiptApiRequest>,
) -> Result<Json<WaiverNotificationReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_waiver_notification_receipt(
        &request.plan,
        request.delivered_to,
        request.provider_message_id,
        request.response_hash,
        request.failures,
    )?;
    state
        .store
        .write()
        .await
        .record_waiver_notification_receipt(&receipt)?;
    Ok(Json(receipt))
}
