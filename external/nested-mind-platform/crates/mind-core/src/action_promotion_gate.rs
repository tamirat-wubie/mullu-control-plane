use crate::{
    hash_serializable, ConnectorOrchestrationReport, ConnectorOrchestrationStatus, EventId,
    KubernetesAuditSourceAdapterReceipt, KubernetesAuditSourceAdapterStatus, MindError, MindResult,
    NotificationProviderDeliveryReceipt, NotificationProviderDeliveryStatus,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ActionPromotionStatus {
    Blocked,
    ReadyForStagingAction,
    ReadyForApprovedLiveAction,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionPromotionGatePolicy {
    pub require_connector_evidence_complete: bool,
    pub require_kubernetes_audit_source: bool,
    pub require_notification_provider_receipt: bool,
}

impl Default for ActionPromotionGatePolicy {
    fn default() -> Self {
        Self {
            require_connector_evidence_complete: true,
            require_kubernetes_audit_source: true,
            require_notification_provider_receipt: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionPromotionGateReport {
    pub gate_report_id: EventId,
    pub status: ActionPromotionStatus,
    #[serde(default)]
    pub blockers: Vec<String>,
    #[serde(default)]
    pub evidence_hashes: Vec<String>,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl ActionPromotionGateReport {
    pub fn verify(&self) -> MindResult<()> {
        if self.status != ActionPromotionStatus::Blocked && !self.blockers.is_empty() {
            return Err(MindError::Store(
                "unblocked action promotion gate cannot contain blockers".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.gate_report_id,
            self.status,
            &self.blockers,
            &self.evidence_hashes,
            self.evaluated_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "action promotion gate report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn evaluate_action_promotion_gate(
    policy: &ActionPromotionGatePolicy,
    orchestration: &ConnectorOrchestrationReport,
    audit_source_receipts: &[KubernetesAuditSourceAdapterReceipt],
    notification_provider_receipts: &[NotificationProviderDeliveryReceipt],
) -> MindResult<ActionPromotionGateReport> {
    orchestration.verify()?;
    let mut blockers = Vec::new();
    let mut evidence_hashes = vec![orchestration.report_hash.clone()];
    if policy.require_connector_evidence_complete
        && orchestration.status != ConnectorOrchestrationStatus::EvidenceComplete
    {
        blockers.push("connector orchestration evidence is not complete".to_owned());
    }
    if policy.require_kubernetes_audit_source {
        let Some(receipt) = audit_source_receipts
            .iter()
            .find(|receipt| receipt.status == KubernetesAuditSourceAdapterStatus::Collected)
        else {
            blockers.push("Kubernetes audit source receipt is missing".to_owned());
            return build_report(blockers, evidence_hashes);
        };
        receipt.verify()?;
        evidence_hashes.push(receipt.receipt_hash.clone());
    }
    if policy.require_notification_provider_receipt {
        let Some(receipt) = notification_provider_receipts.iter().find(|receipt| {
            matches!(
                receipt.status,
                NotificationProviderDeliveryStatus::Sent
                    | NotificationProviderDeliveryStatus::DryRunAccepted
            )
        }) else {
            blockers.push("notification provider delivery receipt is missing".to_owned());
            return build_report(blockers, evidence_hashes);
        };
        receipt.verify()?;
        evidence_hashes.push(receipt.receipt_hash.clone());
    }
    build_report(blockers, evidence_hashes)
}

fn build_report(
    blockers: Vec<String>,
    evidence_hashes: Vec<String>,
) -> MindResult<ActionPromotionGateReport> {
    let status = if blockers.is_empty() {
        ActionPromotionStatus::ReadyForApprovedLiveAction
    } else {
        ActionPromotionStatus::Blocked
    };
    let gate_report_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        gate_report_id,
        status,
        &blockers,
        &evidence_hashes,
        evaluated_at,
    ))?;
    let report = ActionPromotionGateReport {
        gate_report_id,
        status,
        blockers,
        evidence_hashes,
        report_hash,
        evaluated_at,
    };
    report.verify()?;
    Ok(report)
}
