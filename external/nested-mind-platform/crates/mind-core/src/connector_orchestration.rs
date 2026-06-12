use crate::{
    hash_serializable, EventId, GitHubTokenExchangeWorkerReceipt, GitHubTokenExchangeWorkerStatus,
    KubernetesAuditLogCollectorReport, KubernetesAuditLogCollectorStatus,
    LiveSecretConnectorReceipt, LiveSecretConnectorStatus, MindError, MindResult,
    NotificationDeliveryClientReceipt, NotificationDeliveryClientStatus,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum ConnectorOrchestrationMode {
    #[default]
    PlanOnly,
    DryRun,
    ExecuteApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConnectorOrchestrationStatus {
    Planned,
    Ready,
    EvidenceComplete,
    Blocked,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConnectorOrchestrationPlan {
    pub orchestration_plan_id: EventId,
    pub worker_id: String,
    pub purpose: String,
    pub mode: ConnectorOrchestrationMode,
    #[serde(default)]
    pub required_artifacts: Vec<String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl ConnectorOrchestrationPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.worker_id.trim().is_empty() || self.purpose.trim().is_empty() {
            return Err(MindError::Store(
                "connector orchestration plan requires worker and purpose".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.orchestration_plan_id,
            &self.worker_id,
            &self.purpose,
            self.mode,
            &self.required_artifacts,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "connector orchestration plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConnectorOrchestrationReport {
    pub orchestration_report_id: EventId,
    pub orchestration_plan_id: EventId,
    pub status: ConnectorOrchestrationStatus,
    #[serde(default)]
    pub observed_artifacts: BTreeMap<String, String>,
    #[serde(default)]
    pub missing_artifacts: Vec<String>,
    #[serde(default)]
    pub blockers: Vec<String>,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl ConnectorOrchestrationReport {
    pub fn verify(&self) -> MindResult<()> {
        if self.status == ConnectorOrchestrationStatus::EvidenceComplete
            && !self.missing_artifacts.is_empty()
        {
            return Err(MindError::Store(
                "complete connector orchestration report cannot have missing artifacts".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.orchestration_report_id,
            self.orchestration_plan_id,
            self.status,
            &self.observed_artifacts,
            &self.missing_artifacts,
            &self.blockers,
            self.evaluated_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "connector orchestration report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn default_connector_orchestration_artifacts() -> Vec<String> {
    vec![
        "secret".to_owned(),
        "github_token".to_owned(),
        "kubernetes_audit".to_owned(),
        "notification".to_owned(),
    ]
}

pub fn plan_connector_orchestration(
    worker_id: impl Into<String>,
    purpose: impl Into<String>,
    mode: ConnectorOrchestrationMode,
    required_artifacts: Vec<String>,
) -> MindResult<ConnectorOrchestrationPlan> {
    let worker_id = worker_id.into();
    let purpose = purpose.into();
    let required_artifacts = if required_artifacts.is_empty() {
        default_connector_orchestration_artifacts()
    } else {
        required_artifacts
    };
    let orchestration_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        orchestration_plan_id,
        &worker_id,
        &purpose,
        mode,
        &required_artifacts,
        created_at,
    ))?;
    let plan = ConnectorOrchestrationPlan {
        orchestration_plan_id,
        worker_id,
        purpose,
        mode,
        required_artifacts,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn evaluate_connector_orchestration(
    plan: &ConnectorOrchestrationPlan,
    secret_receipts: &[LiveSecretConnectorReceipt],
    token_receipts: &[GitHubTokenExchangeWorkerReceipt],
    audit_reports: &[KubernetesAuditLogCollectorReport],
    notification_receipts: &[NotificationDeliveryClientReceipt],
    external_artifacts: BTreeMap<String, String>,
) -> MindResult<ConnectorOrchestrationReport> {
    plan.verify()?;
    let mut observed = external_artifacts;
    if let Some(receipt) = secret_receipts.iter().find(|receipt| {
        matches!(
            receipt.status,
            LiveSecretConnectorStatus::Resolved | LiveSecretConnectorStatus::DryRunAccepted
        )
    }) {
        receipt.verify()?;
        observed.insert("secret".to_owned(), receipt.receipt_hash.clone());
    }
    if let Some(receipt) = token_receipts.iter().find(|receipt| {
        matches!(
            receipt.status,
            GitHubTokenExchangeWorkerStatus::TokenIssued
                | GitHubTokenExchangeWorkerStatus::DryRunAccepted
        )
    }) {
        receipt.verify()?;
        observed.insert("github_token".to_owned(), receipt.receipt_hash.clone());
    }
    if let Some(report) = audit_reports
        .iter()
        .find(|report| report.status == KubernetesAuditLogCollectorStatus::Collected)
    {
        report.verify()?;
        observed.insert("kubernetes_audit".to_owned(), report.report_hash.clone());
    }
    if let Some(receipt) = notification_receipts.iter().find(|receipt| {
        matches!(
            receipt.status,
            NotificationDeliveryClientStatus::Sent
                | NotificationDeliveryClientStatus::DryRunAccepted
        )
    }) {
        receipt.verify()?;
        observed.insert("notification".to_owned(), receipt.receipt_hash.clone());
    }

    let missing: Vec<String> = plan
        .required_artifacts
        .iter()
        .filter(|name| !observed.contains_key(*name))
        .cloned()
        .collect();
    let blockers = missing
        .iter()
        .map(|name| format!("missing required connector evidence artifact: {name}"))
        .collect::<Vec<_>>();
    let status = if !missing.is_empty() {
        ConnectorOrchestrationStatus::Blocked
    } else if plan.mode == ConnectorOrchestrationMode::ExecuteApproved {
        ConnectorOrchestrationStatus::EvidenceComplete
    } else {
        ConnectorOrchestrationStatus::Ready
    };
    let orchestration_report_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        orchestration_report_id,
        plan.orchestration_plan_id,
        status,
        &observed,
        &missing,
        &blockers,
        evaluated_at,
    ))?;
    let report = ConnectorOrchestrationReport {
        orchestration_report_id,
        orchestration_plan_id: plan.orchestration_plan_id,
        status,
        observed_artifacts: observed,
        missing_artifacts: missing,
        blockers,
        report_hash,
        evaluated_at,
    };
    report.verify()?;
    Ok(report)
}
