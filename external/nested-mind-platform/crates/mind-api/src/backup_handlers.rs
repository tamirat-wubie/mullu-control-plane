//! Purpose: backup manifest creation, object backup, cloud mirror, signed URL, and backup verification handlers for the Nested Mind API.
//! Governance scope: root backup endpoints, object backup verification, mirror/write planning, signed URL transfer, and manifest verification.
//! Dependencies: API state, backup stores, object backup store, cloud mirror, signed URL client, hash verification, and audit/event stores.
//! Invariants: backup authorization, manifest persistence, object verification, cloud mirror receipts, signed URL verification, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_backup_manifests(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BackupManifest>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadBackups)?;
    Ok(Json(state.store.read().await.backup_manifests()?))
}

pub(super) async fn create_root_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<MindBackup>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::CreateBackup)?;
    let records = state.store.read().await.records_for_mind(root_id)?;
    let snapshots = state.snapshots.read().await.snapshots_for_mind(root_id)?;
    let sink = state.observability.read().await;
    let traces = sink.trace_events()?;
    let audits = sink.audit_events()?;
    drop(sink);
    let backup = MindBackup::capture(
        Some(root_id),
        records,
        snapshots,
        traces,
        audits,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(state.store.read().await.signature_requirement())?;
    state
        .store
        .write()
        .await
        .record_backup_manifest(&backup.manifest)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::BackupCreated, "root backup generated")
            .with_mind_id(root_id)
            .with_attribute("backup_id", backup.manifest.backup_id.to_string())
            .with_attribute("backup_hash", backup.manifest.backup_hash.clone()),
    );
    Ok(Json(backup))
}

pub(super) async fn create_root_object_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<BackupObjectRef>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::CreateObjectBackup)?;
    let Some(object_store) = state.object_backups.clone() else {
        return Err(
            MindError::ObjectStore("MIND_BACKUP_OBJECT_DIR is not configured".to_owned()).into(),
        );
    };
    let records = state.store.read().await.records_for_mind(root_id)?;
    let snapshots = state.snapshots.read().await.snapshots_for_mind(root_id)?;
    let sink = state.observability.read().await;
    let traces = sink.trace_events()?;
    let audits = sink.audit_events()?;
    drop(sink);
    let backup = MindBackup::capture(
        Some(root_id),
        records,
        snapshots,
        traces,
        audits,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(state.store.read().await.signature_requirement())?;
    let key = format!("{}/{}.json", root_id, backup.manifest.backup_id);
    let bucket = env::var("MIND_BACKUP_OBJECT_BUCKET")
        .or_else(|_| env::var("MIND_BACKUP_OBJECT_PREFIX"))
        .unwrap_or_else(|_| "mind-backups".to_owned());
    let pointer = object_store.put_verified_backup(
        bucket,
        key,
        &backup,
        state.store.read().await.signature_requirement(),
    )?;
    state
        .store
        .write()
        .await
        .record_backup_manifest(&backup.manifest)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::BackupCreated,
            "root backup uploaded to object store",
        )
        .with_mind_id(root_id)
        .with_attribute("backup_id", backup.manifest.backup_id.to_string())
        .with_attribute("object_key", pointer.key().to_owned()),
    );
    Ok(Json(pointer))
}

pub(super) async fn create_root_cloud_mirror_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<CloudUploadReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::CreateObjectBackup)?;
    let Some(mirror) = state.cloud_mirror.clone() else {
        return Err(MindError::ObjectStorage {
            reason: "MIND_CLOUD_OBJECT_MIRROR_DIR is not configured".to_owned(),
        }
        .into());
    };
    let records = state.store.read().await.records_for_mind(root_id)?;
    let snapshots = state.snapshots.read().await.snapshots_for_mind(root_id)?;
    let sink = state.observability.read().await;
    let traces = sink.trace_events()?;
    let audits = sink.audit_events()?;
    drop(sink);
    let requirement = state.store.read().await.signature_requirement();
    let backup = MindBackup::capture(
        Some(root_id),
        records,
        snapshots,
        traces,
        audits,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(requirement)?;
    let target = cloud_backup_target_from_env()?;
    let plan = CloudObjectAdapter::new(target)?.plan_backup_put(&backup, requirement)?;
    let request =
        mind_core::CloudUploadExecutionRequest::from_plan(&plan, CloudTransferMode::LocalMirror);
    let receipt = mirror.put_backup(&plan, &backup, requirement)?;
    state
        .store
        .write()
        .await
        .record_backup_manifest(&backup.manifest)?;
    state
        .store
        .write()
        .await
        .record_cloud_upload_receipt(&receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::ObjectBackupCreated,
            "root backup uploaded through cloud mirror adapter",
        )
        .with_mind_id(root_id)
        .with_attribute("backup_id", backup.manifest.backup_id.to_string())
        .with_attribute("execution_id", request.execution_id.to_string())
        .with_attribute("object_uri", receipt.object_uri.clone()),
    );
    Ok(Json(receipt))
}

pub(super) async fn create_root_signed_url_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<SignedUrlBackupRequest>,
) -> Result<Json<CloudSignedUrlReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::CreateObjectBackup)?;
    let records = state.store.read().await.records_for_mind(root_id)?;
    let snapshots = state.snapshots.read().await.snapshots_for_mind(root_id)?;
    let sink = state.observability.read().await;
    let traces = sink.trace_events()?;
    let audits = sink.audit_events()?;
    drop(sink);
    let requirement = state.store.read().await.signature_requirement();
    let backup = MindBackup::capture(
        Some(root_id),
        records,
        snapshots,
        traces,
        audits,
        PLATFORM_SCHEMA_VERSION,
    )?;
    backup.verify(requirement)?;
    let signed_request = CloudSignedUrlRequest::put_backup(
        request.provider,
        request.url,
        request.bucket,
        request.key,
        &backup,
    )?;
    let receipt = HttpSignedUrlObjectClient::new()
        .put_backup(&signed_request, &backup)
        .await?;
    state
        .store
        .write()
        .await
        .record_backup_manifest(&backup.manifest)?;
    state
        .store
        .write()
        .await
        .record_cloud_signed_url_receipt(&receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::ObjectBackupCreated,
            "root backup uploaded through signed URL adapter",
        )
        .with_mind_id(root_id)
        .with_attribute("backup_id", backup.manifest.backup_id.to_string())
        .with_attribute("receipt_id", receipt.receipt_id.to_string()),
    );
    Ok(Json(receipt))
}

pub(super) async fn verify_object_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(pointer): Json<BackupObjectRef>,
) -> Result<Json<BackupObjectVerificationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::VerifyBackup)?;
    let Some(object_store) = state.object_backups.clone() else {
        return Err(
            MindError::ObjectStore("MIND_BACKUP_OBJECT_DIR is not configured".to_owned()).into(),
        );
    };
    let report =
        object_store.verify_pointer(&pointer, state.store.read().await.signature_requirement())?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::BackupVerified,
            "object backup verification executed",
        )
        .with_mind_id(report.mind_id.unwrap_or(root_id))
        .with_attribute("backup_id", report.backup_id.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn verify_backup(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(backup): Json<MindBackup>,
) -> Result<Json<BackupVerificationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::VerifyBackup)?;
    let report = backup.verify(state.store.read().await.signature_requirement())?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::BackupVerified,
            "backup verification executed",
        )
        .with_mind_id(report.mind_id.unwrap_or(root_id))
        .with_attribute("backup_id", report.backup_id.to_string())
        .with_attribute("valid", report.valid.to_string()),
    );
    Ok(Json(report))
}
