//! Purpose: provider SDK and native-provider handlers for the Nested Mind API.
//! Governance scope: provider execution receipts, SDK dry runs, feature matrix, native adapter evaluation, and provider execution endpoints.
//! Dependencies: API state, provider SDK contracts, native provider registries, and audit/event stores.
//! Invariants: provider authorization, receipt persistence, adapter evidence, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_provider_sdk_executions(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ProviderSdkExecutionReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    Ok(Json(
        state.store.read().await.provider_sdk_execution_reports()?,
    ))
}

pub(super) async fn system_provider_sdk_execute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ProviderSdkExecutionApiRequest>,
) -> Result<Json<ProviderSdkExecutionReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    let registry = native_provider_adapter_registry();
    let policy = request
        .policy
        .unwrap_or(ProviderSdkExecutionPolicy::DryRunAllowed);
    let report = mind_core::execute_provider_sdk_with_policy(&request.request, &registry, policy)?;
    {
        let mut store = state.store.write().await;
        store.record_native_provider_adapter_report(&report.native_receipt.adapter_report)?;
        store.record_provider_sdk_receipt(&report.native_receipt.sdk_receipt)?;
        store.record_provider_execution_receipt(&report.native_receipt.provider_receipt)?;
        store.record_native_provider_execution_receipt(&report.native_receipt)?;
        store.record_provider_sdk_execution_report(&report)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::KeyCustodyChecked,
            "provider SDK execution report recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("execution_id", report.plan.execution_id.to_string())
        .with_attribute("sdk", format!("{:?}", report.plan.sdk))
        .with_attribute("accepted", report.accepted.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_provider_execution_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ProviderExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    Ok(Json(
        state.store.read().await.provider_execution_receipts()?,
    ))
}

pub(super) async fn record_provider_execution_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(receipt): Json<ProviderExecutionReceipt>,
) -> Result<Json<ProviderExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    state
        .store
        .write()
        .await
        .record_provider_execution_receipt(&receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::KeyCustodyChecked,
            "provider execution receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("receipt_id", receipt.receipt_id.to_string())
        .with_attribute("status", format!("{:?}", receipt.status)),
    );
    Ok(Json(receipt))
}

pub(super) async fn system_provider_sdk_features(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<ProviderSdkFeatureMatrix>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    let matrix = ProviderSdkFeatureMatrix::conservative_default();
    state
        .store
        .write()
        .await
        .record_provider_sdk_feature_matrix(&matrix)?;
    Ok(Json(matrix))
}

pub(super) async fn system_native_provider_adapters(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<NativeProviderAdapterRegistry>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    Ok(Json(native_provider_adapter_registry()))
}

pub(super) async fn system_native_provider_evaluate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ProviderExecutionRequest>,
) -> Result<Json<NativeProviderAdapterReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    let registry = native_provider_adapter_registry();
    let report = evaluate_native_provider_request(&request, &registry)?;
    state
        .store
        .write()
        .await
        .record_native_provider_adapter_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_native_provider_executions(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<NativeProviderExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .native_provider_execution_receipts()?,
    ))
}

pub(super) async fn system_native_provider_execute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<NativeProviderExecutionApiRequest>,
) -> Result<Json<NativeProviderExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    let registry = native_provider_adapter_registry();
    let receipt =
        execute_native_provider_with_receipt(&request.request, &registry, request.allow_dry_run)?;
    {
        let mut store = state.store.write().await;
        store.record_native_provider_adapter_report(&receipt.adapter_report)?;
        store.record_provider_sdk_receipt(&receipt.sdk_receipt)?;
        store.record_provider_execution_receipt(&receipt.provider_receipt)?;
        store.record_native_provider_execution_receipt(&receipt)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::KeyCustodyChecked,
            "native provider execution receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("execution_id", receipt.execution_id.to_string())
        .with_attribute("status", format!("{:?}", receipt.status))
        .with_attribute("sdk", format!("{:?}", receipt.sdk_invocation.sdk)),
    );
    Ok(Json(receipt))
}

pub(super) async fn system_provider_sdk_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ProviderSdkReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    Ok(Json(state.store.read().await.provider_sdk_receipts()?))
}

pub(super) async fn system_provider_sdk_dry_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ProviderExecutionRequest>,
) -> Result<Json<ProviderSdkAdapterReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ExecuteSigningAdapter,
    )?;
    let report = ProviderSdkAdapterReport::dry_run(&request)?;
    state
        .store
        .write()
        .await
        .record_provider_sdk_receipt(&report.receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::KeyCustodyChecked,
            "provider SDK dry-run receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("sdk", format!("{:?}", report.invocation.sdk))
        .with_attribute("receipt_id", report.receipt.receipt_id.to_string()),
    );
    Ok(Json(report))
}
