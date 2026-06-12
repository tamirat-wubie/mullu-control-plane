use crate::{
    hash_serializable, EventId, KubernetesDryRunExecutionReceipt, KubernetesDryRunExecutionRequest,
    MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesAdmissionOperation {
    Create,
    Update,
    Delete,
    Connect,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesAdmissionAuditStatus {
    Planned,
    Allowed,
    Denied,
    AuditMissing,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAdmissionAuditPolicy {
    pub require_server_dry_run: bool,
    pub require_audit_uid: bool,
    #[serde(default)]
    pub required_annotations: Vec<String>,
}

impl Default for KubernetesAdmissionAuditPolicy {
    fn default() -> Self {
        Self {
            require_server_dry_run: true,
            require_audit_uid: true,
            required_annotations: vec!["nested.mind/rehearsal".to_owned()],
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAdmissionAuditRequest {
    pub audit_request_id: EventId,
    pub dry_run_request_id: EventId,
    pub namespace: String,
    pub operation: KubernetesAdmissionOperation,
    pub object_hash: String,
    pub user: String,
    pub request_hash: String,
    pub created_at: OffsetDateTime,
}

impl KubernetesAdmissionAuditRequest {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.audit_request_id,
            self.dry_run_request_id,
            &self.namespace,
            self.operation,
            &self.object_hash,
            &self.user,
            self.created_at,
        ))?;
        if expected != self.request_hash {
            return Err(MindError::Store(
                "Kubernetes admission audit request hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAdmissionAuditReceipt {
    pub audit_receipt_id: EventId,
    pub audit_request_id: EventId,
    pub dry_run_receipt_id: EventId,
    pub status: KubernetesAdmissionAuditStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_uid: Option<String>,
    #[serde(default)]
    pub annotations: BTreeMap<String, String>,
    #[serde(default)]
    pub warnings: Vec<String>,
    pub receipt_hash: String,
    pub captured_at: OffsetDateTime,
}

impl KubernetesAdmissionAuditReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.audit_receipt_id,
            self.audit_request_id,
            self.dry_run_receipt_id,
            self.status,
            &self.audit_uid,
            &self.annotations,
            &self.warnings,
            self.captured_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "Kubernetes admission audit receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAdmissionAuditReport {
    pub report_id: EventId,
    pub audit_request_id: EventId,
    pub audit_receipt_id: EventId,
    pub status: KubernetesAdmissionAuditStatus,
    pub policy_hash: String,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl KubernetesAdmissionAuditReport {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.report_id,
            self.audit_request_id,
            self.audit_receipt_id,
            self.status,
            &self.policy_hash,
            self.evaluated_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "Kubernetes admission audit report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_kubernetes_admission_audit(
    request: &KubernetesDryRunExecutionRequest,
    operation: KubernetesAdmissionOperation,
    object_hash: impl Into<String>,
    user: impl Into<String>,
) -> MindResult<KubernetesAdmissionAuditRequest> {
    request.verify()?;
    let object_hash = object_hash.into();
    let user = user.into();
    if object_hash.trim().is_empty() || user.trim().is_empty() {
        return Err(MindError::Store(
            "Kubernetes admission audit requires object hash and user".to_owned(),
        ));
    }
    let audit_request_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let request_hash = hash_serializable(&(
        audit_request_id,
        request.request_id,
        &request.namespace,
        operation,
        &object_hash,
        &user,
        created_at,
    ))?;
    let planned = KubernetesAdmissionAuditRequest {
        audit_request_id,
        dry_run_request_id: request.request_id,
        namespace: request.namespace.clone(),
        operation,
        object_hash,
        user,
        request_hash,
        created_at,
    };
    planned.verify()?;
    Ok(planned)
}

pub fn record_kubernetes_admission_audit_receipt(
    audit: &KubernetesAdmissionAuditRequest,
    dry_run_receipt: &KubernetesDryRunExecutionReceipt,
    policy: &KubernetesAdmissionAuditPolicy,
    audit_uid: Option<String>,
    annotations: BTreeMap<String, String>,
    warnings: Vec<String>,
    admitted: bool,
) -> MindResult<(
    KubernetesAdmissionAuditReceipt,
    KubernetesAdmissionAuditReport,
)> {
    audit.verify()?;
    dry_run_receipt.verify()?;
    if audit.dry_run_request_id != dry_run_receipt.request_id {
        return Err(MindError::Store(
            "admission audit does not match dry-run receipt".to_owned(),
        ));
    }
    let missing_annotations = policy
        .required_annotations
        .iter()
        .any(|key| !annotations.contains_key(key));
    let status = if policy.require_audit_uid && audit_uid.is_none() {
        KubernetesAdmissionAuditStatus::AuditMissing
    } else if missing_annotations {
        KubernetesAdmissionAuditStatus::Rejected
    } else if admitted {
        KubernetesAdmissionAuditStatus::Allowed
    } else {
        KubernetesAdmissionAuditStatus::Denied
    };
    let audit_receipt_id = EventId::new();
    let captured_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        audit_receipt_id,
        audit.audit_request_id,
        dry_run_receipt.receipt_id,
        status,
        &audit_uid,
        &annotations,
        &warnings,
        captured_at,
    ))?;
    let receipt = KubernetesAdmissionAuditReceipt {
        audit_receipt_id,
        audit_request_id: audit.audit_request_id,
        dry_run_receipt_id: dry_run_receipt.receipt_id,
        status,
        audit_uid,
        annotations,
        warnings,
        receipt_hash,
        captured_at,
    };
    receipt.verify()?;
    let report_id = EventId::new();
    let policy_hash = hash_serializable(policy)?;
    let evaluated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        report_id,
        audit.audit_request_id,
        receipt.audit_receipt_id,
        status,
        &policy_hash,
        evaluated_at,
    ))?;
    let report = KubernetesAdmissionAuditReport {
        report_id,
        audit_request_id: audit.audit_request_id,
        audit_receipt_id: receipt.audit_receipt_id,
        status,
        policy_hash,
        report_hash,
        evaluated_at,
    };
    report.verify()?;
    Ok((receipt, report))
}
