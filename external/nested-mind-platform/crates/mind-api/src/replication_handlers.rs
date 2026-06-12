//! Purpose: replication ingest and outbound delivery handlers for the Nested Mind API.
//! Governance scope: follower batch ingestion, outbound follower delivery, replication envelope persistence, and delivery receipts.
//! Dependencies: API state, replication inbox, replication transport, retry policy, HTTP replication transport client, and audit/event stores.
//! Invariants: replication authorization, envelope persistence, follower apply, delivery receipt recording, and audit writes remain behavior-preserving.

use super::*;

pub(super) async fn ingest_replication_batch(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(batch): Json<ReplicationBatch>,
) -> Result<Json<mind_core::ReplicationApplyReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::IngestReplication)?;
    let envelope = mind_core::ReplicationEnvelope::from_batch(batch.clone())?;
    if let Some(inbox) = &state.replication_inbox {
        inbox.append_envelope(&envelope)?;
    }
    state
        .store
        .write()
        .await
        .record_replication_envelope(&envelope)?;
    let follower_id = state.distributed_plan.node_id.clone();
    let report = apply_replication_batch(&mut *state.store.write().await, follower_id, &batch)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "replication batch ingested",
        )
        .with_mind_id(batch.mind_id)
        .with_attribute("batch_id", batch.batch_id.to_string())
        .with_attribute("accepted", report.accepted.to_string())
        .with_attribute("appended_records", report.appended_records.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn push_replication_batch(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(batch): Json<ReplicationBatch>,
) -> Result<Json<Vec<ReplicationDeliveryReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::IngestReplication)?;
    state.replication_transport.validate()?;
    let envelope = ReplicationEnvelope::from_batch(batch.clone())?;
    let policy = replication_retry_policy_from_env()?;
    let bearer_token = env::var("MIND_REPLICATION_BEARER_TOKEN")
        .ok()
        .filter(|value| !value.trim().is_empty());
    let client = HttpReplicationTransportClient::new(policy, bearer_token)?;
    let mut receipts = Vec::new();
    for endpoint in &state.replication_transport.followers {
        let receipt = client
            .deliver(endpoint, &state.replication_transport.push_path, &envelope)
            .await?;
        state
            .store
            .write()
            .await
            .record_replication_delivery_receipt(&receipt)?;
        receipts.push(receipt);
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "replication batch pushed to followers",
        )
        .with_mind_id(batch.mind_id)
        .with_attribute("batch_id", batch.batch_id.to_string())
        .with_attribute("deliveries", receipts.len().to_string()),
    );
    Ok(Json(receipts))
}
