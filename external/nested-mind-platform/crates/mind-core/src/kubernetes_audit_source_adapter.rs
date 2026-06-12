use crate::{
    hash_serializable, EventId, KubernetesAuditLogCollectorPlan, KubernetesAuditLogCollectorReport,
    KubernetesAuditLogCollectorStatus, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesAuditSourceKind {
    ApiServerAuditLog,
    WebhookSink,
    FileTail,
    ExternalGateway,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum KubernetesAuditSourceAdapterMode {
    #[default]
    PlanOnly,
    DryRun,
    CollectApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesAuditSourceAdapterStatus {
    Planned,
    DryRunAccepted,
    Collected,
    Missing,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct KubernetesAuditSourceAdapterPlan {
    pub source_plan_id: EventId,
    pub collector_plan_id: EventId,
    pub kind: KubernetesAuditSourceKind,
    pub namespace: String,
    pub mode: KubernetesAuditSourceAdapterMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub since_watermark: Option<String>,
    pub source_reference: String,
    pub request_template: Value,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl KubernetesAuditSourceAdapterPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.namespace.trim().is_empty() || self.source_reference.trim().is_empty() {
            return Err(MindError::Store(
                "Kubernetes audit source adapter plan requires namespace and source reference"
                    .to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.source_plan_id,
            self.collector_plan_id,
            self.kind,
            &self.namespace,
            self.mode,
            &self.since_watermark,
            &self.source_reference,
            &self.request_template,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "Kubernetes audit source adapter plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAuditSourceAdapterReceipt {
    pub source_receipt_id: EventId,
    pub source_plan_id: EventId,
    pub collector_report_id: EventId,
    pub kind: KubernetesAuditSourceKind,
    pub status: KubernetesAuditSourceAdapterStatus,
    pub observed_event_count: u64,
    #[serde(default)]
    pub audit_uids: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub receipt_hash: String,
    pub collected_at: OffsetDateTime,
}

impl KubernetesAuditSourceAdapterReceipt {
    pub fn verify(&self) -> MindResult<()> {
        if self.status == KubernetesAuditSourceAdapterStatus::Collected
            && self.audit_uids.is_empty()
        {
            return Err(MindError::Store(
                "collected Kubernetes audit source receipt requires audit UID evidence".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.source_receipt_id,
            self.source_plan_id,
            self.collector_report_id,
            self.kind,
            self.status,
            self.observed_event_count,
            &self.audit_uids,
            &self.provider_response_hash,
            &self.failures,
            self.collected_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "Kubernetes audit source adapter receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_kubernetes_audit_source_adapter(
    collector_plan: &KubernetesAuditLogCollectorPlan,
    kind: KubernetesAuditSourceKind,
    mode: KubernetesAuditSourceAdapterMode,
    source_reference: impl Into<String>,
    request_template: Value,
) -> MindResult<KubernetesAuditSourceAdapterPlan> {
    collector_plan.verify()?;
    let source_reference = source_reference.into();
    let source_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        source_plan_id,
        collector_plan.collector_plan_id,
        kind,
        &collector_plan.namespace,
        mode,
        &collector_plan.previous_watermark,
        &source_reference,
        &request_template,
        created_at,
    ))?;
    let plan = KubernetesAuditSourceAdapterPlan {
        source_plan_id,
        collector_plan_id: collector_plan.collector_plan_id,
        kind,
        namespace: collector_plan.namespace.clone(),
        mode,
        since_watermark: collector_plan.previous_watermark.clone(),
        source_reference,
        request_template,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_kubernetes_audit_source_adapter_receipt(
    plan: &KubernetesAuditSourceAdapterPlan,
    collector_report: &KubernetesAuditLogCollectorReport,
    provider_response_hash: Option<String>,
    failures: Vec<String>,
) -> MindResult<KubernetesAuditSourceAdapterReceipt> {
    plan.verify()?;
    collector_report.verify()?;
    if collector_report.collector_plan_id != plan.collector_plan_id {
        return Err(MindError::Store(
            "Kubernetes audit source receipt does not match collector plan".to_owned(),
        ));
    }
    let status = if !failures.is_empty() {
        KubernetesAuditSourceAdapterStatus::Rejected
    } else {
        match collector_report.status {
            KubernetesAuditLogCollectorStatus::Collected => {
                KubernetesAuditSourceAdapterStatus::Collected
            }
            KubernetesAuditLogCollectorStatus::Missing => {
                KubernetesAuditSourceAdapterStatus::Missing
            }
            KubernetesAuditLogCollectorStatus::Planned => {
                KubernetesAuditSourceAdapterStatus::Planned
            }
            KubernetesAuditLogCollectorStatus::Rejected => {
                KubernetesAuditSourceAdapterStatus::Rejected
            }
        }
    };
    let source_receipt_id = EventId::new();
    let collected_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        source_receipt_id,
        plan.source_plan_id,
        collector_report.collector_report_id,
        plan.kind,
        status,
        collector_report.observed_event_count,
        &collector_report.audit_uids,
        &provider_response_hash,
        &failures,
        collected_at,
    ))?;
    let receipt = KubernetesAuditSourceAdapterReceipt {
        source_receipt_id,
        source_plan_id: plan.source_plan_id,
        collector_report_id: collector_report.collector_report_id,
        kind: plan.kind,
        status,
        observed_event_count: collector_report.observed_event_count,
        audit_uids: collector_report.audit_uids.clone(),
        provider_response_hash,
        failures,
        receipt_hash,
        collected_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
