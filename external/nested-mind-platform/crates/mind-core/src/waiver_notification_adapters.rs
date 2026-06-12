use crate::{
    hash_serializable, EventId, MindError, MindResult, WaiverNotificationPlan,
    WaiverNotificationReceipt,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverNotificationAdapterKind {
    EmailSmtp,
    SlackWebhook,
    GitHubIssue,
    GenericWebhook,
    Manual,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum WaiverNotificationAdapterMode {
    #[default]
    PlanOnly,
    DryRun,
    SendApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverNotificationAdapterStatus {
    Planned,
    DryRunAccepted,
    Sent,
    Failed,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverNotificationAdapterPlan {
    pub adapter_plan_id: EventId,
    pub notification_plan_id: EventId,
    pub adapter_kind: WaiverNotificationAdapterKind,
    pub mode: WaiverNotificationAdapterMode,
    pub endpoint_reference: String,
    pub request_template_hash: String,
    #[serde(default)]
    pub headers_fingerprint: BTreeMap<String, String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl WaiverNotificationAdapterPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.endpoint_reference.trim().is_empty() || self.request_template_hash.trim().is_empty()
        {
            return Err(MindError::Store(
                "waiver notification adapter requires endpoint reference and request template hash"
                    .to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.adapter_plan_id,
            self.notification_plan_id,
            self.adapter_kind,
            self.mode,
            &self.endpoint_reference,
            &self.request_template_hash,
            &self.headers_fingerprint,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "waiver notification adapter plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverNotificationAdapterReceipt {
    pub receipt_id: EventId,
    pub adapter_plan_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub notification_receipt_id: Option<EventId>,
    pub adapter_kind: WaiverNotificationAdapterKind,
    pub status: WaiverNotificationAdapterStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_message_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub receipt_hash: String,
    pub delivered_at: OffsetDateTime,
}

impl WaiverNotificationAdapterReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.adapter_plan_id,
            &self.notification_receipt_id,
            self.adapter_kind,
            self.status,
            &self.provider_message_id,
            &self.provider_response_hash,
            &self.failures,
            self.delivered_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "waiver notification adapter receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_waiver_notification_adapter(
    plan: &WaiverNotificationPlan,
    adapter_kind: WaiverNotificationAdapterKind,
    endpoint_reference: impl Into<String>,
    request_template_hash: impl Into<String>,
    mode: WaiverNotificationAdapterMode,
) -> MindResult<WaiverNotificationAdapterPlan> {
    plan.verify()?;
    let endpoint_reference = endpoint_reference.into();
    let request_template_hash = request_template_hash.into();
    let adapter_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let headers_fingerprint = BTreeMap::new();
    let plan_hash = hash_serializable(&(
        adapter_plan_id,
        plan.notification_plan_id,
        adapter_kind,
        mode,
        &endpoint_reference,
        &request_template_hash,
        &headers_fingerprint,
        created_at,
    ))?;
    let adapter_plan = WaiverNotificationAdapterPlan {
        adapter_plan_id,
        notification_plan_id: plan.notification_plan_id,
        adapter_kind,
        mode,
        endpoint_reference,
        request_template_hash,
        headers_fingerprint,
        plan_hash,
        created_at,
    };
    adapter_plan.verify()?;
    Ok(adapter_plan)
}

pub fn record_waiver_notification_adapter_receipt(
    adapter_plan: &WaiverNotificationAdapterPlan,
    notification_receipt: Option<&WaiverNotificationReceipt>,
    provider_message_id: Option<String>,
    provider_response_hash: Option<String>,
    failures: Vec<String>,
) -> MindResult<WaiverNotificationAdapterReceipt> {
    adapter_plan.verify()?;
    if let Some(receipt) = notification_receipt {
        receipt.verify()?;
        if receipt.notification_plan_id != adapter_plan.notification_plan_id {
            return Err(MindError::Store(
                "waiver notification receipt does not match adapter plan".to_owned(),
            ));
        }
    }
    let status = match adapter_plan.mode {
        WaiverNotificationAdapterMode::PlanOnly => WaiverNotificationAdapterStatus::Planned,
        WaiverNotificationAdapterMode::DryRun => WaiverNotificationAdapterStatus::DryRunAccepted,
        WaiverNotificationAdapterMode::SendApproved => {
            if failures.is_empty() && provider_message_id.is_some() {
                WaiverNotificationAdapterStatus::Sent
            } else if failures.is_empty() {
                WaiverNotificationAdapterStatus::Rejected
            } else {
                WaiverNotificationAdapterStatus::Failed
            }
        }
    };
    let receipt_id = EventId::new();
    let delivered_at = OffsetDateTime::now_utc();
    let notification_receipt_id = notification_receipt.map(|receipt| receipt.receipt_id);
    let receipt_hash = hash_serializable(&(
        receipt_id,
        adapter_plan.adapter_plan_id,
        &notification_receipt_id,
        adapter_plan.adapter_kind,
        status,
        &provider_message_id,
        &provider_response_hash,
        &failures,
        delivered_at,
    ))?;
    let receipt = WaiverNotificationAdapterReceipt {
        receipt_id,
        adapter_plan_id: adapter_plan.adapter_plan_id,
        notification_receipt_id,
        adapter_kind: adapter_plan.adapter_kind,
        status,
        provider_message_id,
        provider_response_hash,
        failures,
        receipt_hash,
        delivered_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
