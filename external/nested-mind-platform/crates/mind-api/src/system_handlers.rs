//! Purpose: system metadata, identity, signing, and transport handlers for the Nested Mind API.
//! Governance scope: read/refresh HTTP handlers that expose runtime status and identity trust evidence.
//! Dependencies: API state, authentication/authorization, OIDC discovery, and replication transport plans.
//! Invariants: handler authorization checks, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn health(State(state): State<AppState>) -> Json<serde_json::Value> {
    let _ = state
        .observability
        .write()
        .await
        .record_audit(AuditEvent::new(
            AuditEventKind::HealthChecked,
            "health check",
        ));
    Json(
        json!({"status": "ok", "platform_schema_version": PLATFORM_SCHEMA_VERSION, "request_safety": &state.safety_config}),
    )
}

pub(super) async fn system_schema(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<SchemaMigrationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadSchema)?;
    Ok(Json(state.store.read().await.schema_report()?))
}

pub(super) async fn system_identity_policy(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<IdentityBindingPolicy>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadIdentityPolicy)?;
    Ok(Json(state.authn.identity_policy.clone()))
}

pub(super) async fn system_oidc_verifier(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Option<OidcJwksVerifierConfig>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadIdentityPolicy)?;
    Ok(Json(
        state
            .authn
            .oidc_verifier
            .as_ref()
            .map(|verifier| verifier.config.clone()),
    ))
}

pub(super) async fn system_oidc_discovery(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Option<OidcDiscoveryDocument>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadIdentityPolicy)?;
    Ok(Json(
        state
            .oidc_discovery
            .as_ref()
            .map(|runtime| runtime.document.clone()),
    ))
}

pub(super) async fn system_refresh_oidc_keys(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<OidcDiscoveryRefreshReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::RefreshIdentityKeys,
    )?;
    let Some(runtime) = &state.oidc_discovery else {
        return Err(
            MindError::Identity("OIDC discovery runtime is not configured".to_owned()).into(),
        );
    };
    let cache = runtime.cache_entry()?;
    let report = runtime.refresh_report()?;
    state.store.write().await.record_oidc_jwks_cache(&cache)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::IdentityMapped, "OIDC JWKS cache refreshed")
            .with_mind_id(root_id)
            .with_attribute("issuer", report.issuer.clone())
            .with_attribute("jwks_hash", report.jwks_hash.clone()),
    );
    Ok(Json(report))
}

pub(super) async fn system_refresh_oidc_keys_live(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<LiveOidcRefreshReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::RefreshIdentityKeys,
    )?;
    let config = oidc_live_config_from_env()?;
    let report = HttpOidcDiscoveryClient::new().refresh(&config).await?;
    {
        let mut store = state.store.write().await;
        store.record_oidc_jwks_cache(&report.cache)?;
        store.record_live_oidc_refresh(&report)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::IdentityMapped,
            "live OIDC discovery/JWKS refresh completed",
        )
        .with_mind_id(root_id)
        .with_attribute("issuer", report.request.issuer.clone())
        .with_attribute("jwks_hash", report.jwks_hash.clone()),
    );
    Ok(Json(report))
}

pub(super) async fn system_verify_oidc_jwt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<JwtVerificationRequest>,
) -> Result<Json<OidcJwtVerificationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadIdentityPolicy)?;
    let Some(verifier) = &state.authn.oidc_verifier else {
        return Err(
            MindError::Identity("direct OIDC verifier is not configured".to_owned()).into(),
        );
    };
    Ok(Json(verifier.verify_with_report(
        request.jwt.trim(),
        &state.authn.identity_policy,
    )?))
}

pub(super) async fn system_signing_status(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<SigningBackendStatus>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadSigningPolicy)?;
    Ok(Json(state.signing_status.clone()))
}

pub(super) async fn system_distributed_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<ClusterHealthReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root_id,
        &MindAction::ReadEventStoreStrategy,
    )?;
    Ok(Json(ClusterHealthReport::from_plan(
        state.distributed_plan.clone(),
    )?))
}

pub(super) async fn system_replication_transport(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<ReplicationTransportPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadReplication)?;
    state.replication_transport.validate()?;
    Ok(Json(state.replication_transport.clone()))
}
