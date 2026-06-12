use crate::{
    hash_serializable, EventId, KubernetesAdmissionAuditReceipt, KubernetesAdmissionAuditReport,
    KubernetesAdmissionAuditStatus, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum KubernetesAuditLogCollectorMode {
    #[default]
    PlanOnly,
    DryRun,
    CollectApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KubernetesAuditLogCollectorStatus {
    Planned,
    Collected,
    Missing,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAuditLogCollectorPlan {
    pub collector_plan_id: EventId,
    pub audit_report_id: EventId,
    pub namespace: String,
    pub mode: KubernetesAuditLogCollectorMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub previous_watermark: Option<String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl KubernetesAuditLogCollectorPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.namespace.trim().is_empty() {
            return Err(MindError::Store(
                "Kubernetes audit log collector requires namespace".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.collector_plan_id,
            self.audit_report_id,
            &self.namespace,
            self.mode,
            &self.previous_watermark,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "Kubernetes audit log collector plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct KubernetesAuditLogCollectorReport {
    pub collector_report_id: EventId,
    pub collector_plan_id: EventId,
    pub audit_receipt_id: EventId,
    pub status: KubernetesAuditLogCollectorStatus,
    pub observed_event_count: u64,
    #[serde(default)]
    pub audit_uids: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub new_watermark: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub report_hash: String,
    pub collected_at: OffsetDateTime,
}

impl KubernetesAuditLogCollectorReport {
    pub fn verify(&self) -> MindResult<()> {
        if self.status == KubernetesAuditLogCollectorStatus::Collected && self.audit_uids.is_empty()
        {
            return Err(MindError::Store(
                "collected Kubernetes audit log report requires audit UID evidence".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.collector_report_id,
            self.collector_plan_id,
            self.audit_receipt_id,
            self.status,
            self.observed_event_count,
            &self.audit_uids,
            &self.new_watermark,
            &self.failures,
            self.collected_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "Kubernetes audit log collector report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_kubernetes_audit_log_collector(
    admission_report: &KubernetesAdmissionAuditReport,
    namespace: impl Into<String>,
    mode: KubernetesAuditLogCollectorMode,
    previous_watermark: Option<String>,
) -> MindResult<KubernetesAuditLogCollectorPlan> {
    admission_report.verify()?;
    let namespace = namespace.into();
    let collector_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        collector_plan_id,
        admission_report.report_id,
        &namespace,
        mode,
        &previous_watermark,
        created_at,
    ))?;
    let plan = KubernetesAuditLogCollectorPlan {
        collector_plan_id,
        audit_report_id: admission_report.report_id,
        namespace,
        mode,
        previous_watermark,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_kubernetes_audit_log_collector_report(
    plan: &KubernetesAuditLogCollectorPlan,
    admission_receipt: &KubernetesAdmissionAuditReceipt,
    observed_event_count: u64,
    audit_uids: Vec<String>,
    new_watermark: Option<String>,
    failures: Vec<String>,
) -> MindResult<KubernetesAuditLogCollectorReport> {
    plan.verify()?;
    admission_receipt.verify()?;
    let status = if !failures.is_empty() {
        KubernetesAuditLogCollectorStatus::Rejected
    } else if admission_receipt.status == KubernetesAdmissionAuditStatus::AuditMissing
        || audit_uids.is_empty()
    {
        KubernetesAuditLogCollectorStatus::Missing
    } else {
        KubernetesAuditLogCollectorStatus::Collected
    };
    let collector_report_id = EventId::new();
    let collected_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        collector_report_id,
        plan.collector_plan_id,
        admission_receipt.audit_receipt_id,
        status,
        observed_event_count,
        &audit_uids,
        &new_watermark,
        &failures,
        collected_at,
    ))?;
    let report = KubernetesAuditLogCollectorReport {
        collector_report_id,
        collector_plan_id: plan.collector_plan_id,
        audit_receipt_id: admission_receipt.audit_receipt_id,
        status,
        observed_event_count,
        audit_uids,
        new_watermark,
        failures,
        report_hash,
        collected_at,
    };
    report.verify()?;
    Ok(report)
}
