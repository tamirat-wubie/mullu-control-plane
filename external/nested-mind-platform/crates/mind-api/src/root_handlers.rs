//! Purpose: root projection, event, replay, snapshot, patch, child attach, and lawbook migration handlers for the Nested Mind API.
//! Governance scope: root state read/write endpoints and snapshot/replay operations without changing authorization, persistence, or audit semantics.
//! Dependencies: API state, root symbol store, event store, snapshot store, replay audit, patch contracts, and authorization policy.
//! Invariants: root authorization, snapshot persistence, event replay, lawbook migration, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn root_projection(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<ProjectionQuery>,
) -> Result<Json<MindProjection>, ApiError> {
    let root = state.root.read().await;
    let principal = state.authn.authenticate(&headers)?;
    state.authz.require(
        principal.as_ref(),
        root.id(),
        &MindAction::ReadProjection {
            scope: query.scope.clone(),
        },
    )?;
    Ok(Json(MindProjection::with_policy(
        &root,
        &ProjectionPolicy::for_scope(query.scope),
    )))
}
pub(super) async fn root_events(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<EventRecord>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadEvents)?;
    Ok(Json(state.store.read().await.records_for_mind(root_id)?))
}
pub(super) async fn root_replay(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<ReplayReport>, ApiError> {
    let identity = { state.root.read().await.identity().clone() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), identity.id, &MindAction::Replay)?;
    let store = state.store.read().await;
    let records = store.records_for_mind(identity.id)?;
    let (_, report) = ReplayEngine::replay_with_signature_requirement(
        identity,
        &records,
        store.signature_requirement(),
    )?;
    Ok(Json(report))
}
pub(super) async fn root_audit(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<AuditQuery>,
) -> Result<Json<ReplayAuditReport>, ApiError> {
    let identity = { state.root.read().await.identity().clone() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), identity.id, &MindAction::AuditReplay)?;
    let store = state.store.read().await;
    let records = store.records_for_mind(identity.id)?;
    let requirement = store.signature_requirement();
    drop(store);
    let report = if query.from_snapshot {
        match state
            .snapshots
            .read()
            .await
            .latest_snapshot_for_mind(identity.id)?
        {
            Some(snapshot) => {
                let tail: Vec<EventRecord> = records
                    .into_iter()
                    .filter(|record| record.sequence > snapshot.after_sequence)
                    .collect();
                ReplayAudit::audit_from_snapshot(&snapshot, &tail, requirement)
            }
            None => ReplayAudit::audit_full(identity, &records, requirement),
        }
    } else {
        ReplayAudit::audit_full(identity, &records, requirement)
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::ReplayAudited, "root replay audit executed")
            .with_mind_id(report.mind_id),
    );
    Ok(Json(report))
}
pub(super) async fn root_snapshots(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<SnapshotRecord>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadSnapshots)?;
    Ok(Json(
        state.snapshots.read().await.snapshots_for_mind(root_id)?,
    ))
}
pub(super) async fn root_latest_snapshot(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Option<SnapshotRecord>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadSnapshots)?;
    Ok(Json(
        state
            .snapshots
            .read()
            .await
            .latest_snapshot_for_mind(root_id)?,
    ))
}
pub(super) async fn create_root_snapshot(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<SnapshotRecord>, ApiError> {
    let root = state.root.read().await;
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root.id(), &MindAction::CreateSnapshot)?;
    let records = state.store.read().await.records_for_mind(root.id())?;
    let latest_record = records.last();
    let snapshot = SnapshotRecord::capture(&root, latest_record)?;
    let mind_id = root.id();
    drop(root);
    let saved = state.snapshots.write().await.save_snapshot(snapshot)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::SnapshotCreated, "root snapshot created")
            .with_mind_id(mind_id)
            .with_attribute("snapshot_id", saved.snapshot_id.to_string()),
    );
    Ok(Json(saved))
}
pub(super) async fn compact_root_snapshots(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<SnapshotCompactionDecision>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::CompactSnapshots)?;
    let latest_sequence = state
        .store
        .read()
        .await
        .records_for_mind(root_id)?
        .last()
        .map_or(0, |record| record.sequence);
    let policy = snapshot_compaction_policy_from_env();
    let decision =
        state
            .snapshots
            .write()
            .await
            .compact_snapshots(root_id, &policy, latest_sequence)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::SnapshotCompacted,
            "root snapshots compacted",
        )
        .with_mind_id(root_id)
        .with_attribute("removed", decision.remove_snapshot_ids.len().to_string()),
    );
    Ok(Json(decision))
}
pub(super) async fn apply_root_patch(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<PatchRequest>,
) -> Result<Json<Commit>, ApiError> {
    let mut root = state.root.write().await;
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root.id(), &MindAction::ProposePatch)?;
    let principal = principal.ok_or(MindError::MissingCredentials)?;
    let actor = resolve_actor(&principal, request.actor, &state.authz, root.id())?;
    state.distributed_plan.validate_append_authority()?;
    let proposal = EditProposal::new(
        root.id(),
        actor.clone(),
        request.reason,
        StatePatch::from_ops(request.ops),
    );
    let mut plan = EvolutionEngine::evaluate(&root, proposal)?;
    sign_plan_if_configured(&mut plan, state.signer.as_ref())?;
    state.store.write().await.append(plan.commit().clone())?;
    let commit = EvolutionEngine::apply_plan(&mut root, plan)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::MutationCommitted, "root patch committed")
            .with_mind_id(root.id())
            .with_actor(actor)
            .with_attribute("commit_id", commit.id.to_string()),
    );
    Ok(Json(commit))
}
pub(super) async fn attach_root_child(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ChildRequest>,
) -> Result<Json<Commit>, ApiError> {
    let mut root = state.root.write().await;
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root.id(), &MindAction::AttachChild)?;
    let principal = principal.ok_or(MindError::MissingCredentials)?;
    let actor = resolve_actor(&principal, request.actor, &state.authz, root.id())?;
    state.distributed_plan.validate_append_authority()?;
    let mut plan = EvolutionEngine::evaluate_child_attachment(
        &root,
        Identity::child(root.id(), request.kind),
        actor.clone(),
        request.reason,
    )?;
    sign_plan_if_configured(&mut plan, state.signer.as_ref())?;
    state.store.write().await.append(plan.commit().clone())?;
    let commit = EvolutionEngine::apply_plan(&mut root, plan)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(AuditEventKind::ChildAttached, "child mind attached")
            .with_mind_id(root.id())
            .with_actor(actor)
            .with_attribute("commit_id", commit.id.to_string()),
    );
    Ok(Json(commit))
}
pub(super) async fn migrate_root_lawbook(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LawbookMigrationRequest>,
) -> Result<Json<Commit>, ApiError> {
    let mut root = state.root.write().await;
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root.id(), &MindAction::MigrateLawbook)?;
    let principal = principal.ok_or(MindError::MissingCredentials)?;
    let actor = resolve_actor(&principal, request.actor, &state.authz, root.id())?;
    state.distributed_plan.validate_append_authority()?;
    let mut migration = LawbookMigration::new(
        root.lawbook().version(),
        root.lawbook().version() + 1,
        actor.clone(),
        request.reason,
        request.operations,
    );
    if request.allow_foundation_removal {
        migration = migration.with_foundation_removal();
    }
    let mut plan = EvolutionEngine::evaluate_lawbook_migration(&root, migration)?;
    sign_plan_if_configured(&mut plan, state.signer.as_ref())?;
    state.store.write().await.append(plan.commit().clone())?;
    let commit = EvolutionEngine::apply_plan(&mut root, plan)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::LawbookMigrated,
            "lawbook migration committed",
        )
        .with_mind_id(root.id())
        .with_actor(actor)
        .with_attribute("commit_id", commit.id.to_string()),
    );
    Ok(Json(commit))
}
