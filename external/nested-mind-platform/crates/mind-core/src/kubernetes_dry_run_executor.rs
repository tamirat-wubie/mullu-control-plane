use crate::{hash_serializable, EventId, KubernetesStagingChaosPlan, MindError, MindResult};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesDryRunExecutionStatus {
    Planned,
    ServerAccepted,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesDryRunExecutionRequest {
    pub request_id: EventId,
    pub plan_id: EventId,
    pub context_name: String,
    pub namespace: String,
    pub field_manager: String,
    pub manifest_count: usize,
    pub server_side: bool,
    pub request_hash: String,
    pub created_at: OffsetDateTime,
}

impl KubernetesDryRunExecutionRequest {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.request_id,
            self.plan_id,
            &self.context_name,
            &self.namespace,
            &self.field_manager,
            self.manifest_count,
            self.server_side,
            self.created_at,
        ))?;
        if expected != self.request_hash {
            return Err(MindError::Store(
                "Kubernetes dry-run request hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesDryRunExecutionReceipt {
    pub receipt_id: EventId,
    pub request_id: EventId,
    pub plan_id: EventId,
    pub status: KubernetesDryRunExecutionStatus,
    pub namespace: String,
    #[serde(default)]
    pub validated_manifest_hashes: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    #[serde(default)]
    pub warnings: Vec<String>,
    pub receipt_hash: String,
    pub executed_at: OffsetDateTime,
}

impl KubernetesDryRunExecutionReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.request_id,
            self.plan_id,
            self.status,
            &self.namespace,
            &self.validated_manifest_hashes,
            &self.response_hash,
            &self.warnings,
            self.executed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "Kubernetes dry-run receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_kubernetes_server_dry_run_execution(
    plan: &KubernetesStagingChaosPlan,
    context_name: impl Into<String>,
    field_manager: impl Into<String>,
) -> MindResult<KubernetesDryRunExecutionRequest> {
    plan.verify()?;
    let context_name = context_name.into();
    let field_manager = field_manager.into();
    if context_name.trim().is_empty() || field_manager.trim().is_empty() {
        return Err(MindError::Store(
            "Kubernetes dry-run requires context and field manager".to_owned(),
        ));
    }
    let request_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let request_hash = hash_serializable(&(
        request_id,
        plan.plan_id,
        &context_name,
        &plan.namespace,
        &field_manager,
        plan.manifests.len(),
        true,
        created_at,
    ))?;
    Ok(KubernetesDryRunExecutionRequest {
        request_id,
        plan_id: plan.plan_id,
        context_name,
        namespace: plan.namespace.clone(),
        field_manager,
        manifest_count: plan.manifests.len(),
        server_side: true,
        request_hash,
        created_at,
    })
}

pub fn record_kubernetes_server_dry_run_receipt(
    request: &KubernetesDryRunExecutionRequest,
    plan: &KubernetesStagingChaosPlan,
    response: Option<&Value>,
    warnings: Vec<String>,
) -> MindResult<KubernetesDryRunExecutionReceipt> {
    request.verify()?;
    plan.verify()?;
    if request.plan_id != plan.plan_id || request.namespace != plan.namespace {
        return Err(MindError::Store(
            "Kubernetes dry-run request does not match plan".to_owned(),
        ));
    }
    let validated_manifest_hashes = plan
        .manifests
        .iter()
        .map(|manifest| manifest.manifest_hash.clone())
        .collect::<Vec<_>>();
    let response_hash = match response {
        Some(value) => Some(hash_serializable(value)?),
        None => None,
    };
    let status = if request.server_side && request.manifest_count == plan.manifests.len() {
        KubernetesDryRunExecutionStatus::ServerAccepted
    } else {
        KubernetesDryRunExecutionStatus::Rejected
    };
    let receipt_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        request.request_id,
        request.plan_id,
        status,
        &request.namespace,
        &validated_manifest_hashes,
        &response_hash,
        &warnings,
        executed_at,
    ))?;
    let receipt = KubernetesDryRunExecutionReceipt {
        receipt_id,
        request_id: request.request_id,
        plan_id: request.plan_id,
        status,
        namespace: request.namespace.clone(),
        validated_manifest_hashes,
        response_hash,
        warnings,
        receipt_hash,
        executed_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
