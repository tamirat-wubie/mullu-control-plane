use crate::{
    hash_serializable, EventId, MindError, MindResult, NotificationDeliveryClientPlan,
    NotificationDeliveryClientReceipt, NotificationDeliveryClientStatus,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum NotificationProviderKind {
    Smtp,
    SlackWebhook,
    GitHubIssue,
    GenericWebhook,
    Manual,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum NotificationProviderDeliveryMode {
    #[default]
    PlanOnly,
    DryRun,
    SendApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum NotificationProviderDeliveryStatus {
    Planned,
    DryRunAccepted,
    Sent,
    Failed,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct NotificationProviderDeliveryPlan {
    pub provider_plan_id: EventId,
    pub client_plan_id: EventId,
    pub provider_kind: NotificationProviderKind,
    pub mode: NotificationProviderDeliveryMode,
    pub endpoint_reference: String,
    pub request_template: Value,
    pub request_body_hash: String,
    pub idempotency_key: String,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl NotificationProviderDeliveryPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.endpoint_reference.trim().is_empty()
            || self.request_body_hash.trim().is_empty()
            || self.idempotency_key.trim().is_empty()
        {
            return Err(MindError::Store(
                "notification provider delivery plan requires endpoint, body hash and idempotency key"
                    .to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.provider_plan_id,
            self.client_plan_id,
            self.provider_kind,
            self.mode,
            &self.endpoint_reference,
            &self.request_template,
            &self.request_body_hash,
            &self.idempotency_key,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "notification provider delivery plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NotificationProviderDeliveryReceipt {
    pub provider_receipt_id: EventId,
    pub provider_plan_id: EventId,
    pub client_receipt_id: EventId,
    pub provider_kind: NotificationProviderKind,
    pub status: NotificationProviderDeliveryStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_message_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub receipt_hash: String,
    pub delivered_at: OffsetDateTime,
}

impl NotificationProviderDeliveryReceipt {
    pub fn verify(&self) -> MindResult<()> {
        if self.status == NotificationProviderDeliveryStatus::Sent
            && self.provider_message_id.is_none()
        {
            return Err(MindError::Store(
                "sent provider delivery receipt requires provider message id".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.provider_receipt_id,
            self.provider_plan_id,
            self.client_receipt_id,
            self.provider_kind,
            self.status,
            &self.provider_message_id,
            &self.provider_response_hash,
            &self.failures,
            self.delivered_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "notification provider delivery receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_notification_provider_delivery(
    client_plan: &NotificationDeliveryClientPlan,
    provider_kind: NotificationProviderKind,
    mode: NotificationProviderDeliveryMode,
    endpoint_reference: impl Into<String>,
    request_template: Value,
) -> MindResult<NotificationProviderDeliveryPlan> {
    client_plan.verify()?;
    let endpoint_reference = endpoint_reference.into();
    let request_body_hash = hash_serializable(&request_template)?;
    let idempotency_key = hash_serializable(&(
        client_plan.client_plan_id,
        provider_kind,
        &endpoint_reference,
        &request_body_hash,
    ))?;
    let provider_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        provider_plan_id,
        client_plan.client_plan_id,
        provider_kind,
        mode,
        &endpoint_reference,
        &request_template,
        &request_body_hash,
        &idempotency_key,
        created_at,
    ))?;
    let plan = NotificationProviderDeliveryPlan {
        provider_plan_id,
        client_plan_id: client_plan.client_plan_id,
        provider_kind,
        mode,
        endpoint_reference,
        request_template,
        request_body_hash,
        idempotency_key,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_notification_provider_delivery_receipt(
    plan: &NotificationProviderDeliveryPlan,
    client_receipt: &NotificationDeliveryClientReceipt,
    provider_message_id: Option<String>,
    provider_response_hash: Option<String>,
    failures: Vec<String>,
) -> MindResult<NotificationProviderDeliveryReceipt> {
    plan.verify()?;
    client_receipt.verify()?;
    if client_receipt.client_plan_id != plan.client_plan_id {
        return Err(MindError::Store(
            "notification provider receipt does not match client plan".to_owned(),
        ));
    }
    let status = if !failures.is_empty() {
        NotificationProviderDeliveryStatus::Failed
    } else {
        match client_receipt.status {
            NotificationDeliveryClientStatus::Sent => NotificationProviderDeliveryStatus::Sent,
            NotificationDeliveryClientStatus::DryRunAccepted => {
                NotificationProviderDeliveryStatus::DryRunAccepted
            }
            NotificationDeliveryClientStatus::Planned => {
                NotificationProviderDeliveryStatus::Planned
            }
            NotificationDeliveryClientStatus::Failed => NotificationProviderDeliveryStatus::Failed,
            NotificationDeliveryClientStatus::Rejected => {
                NotificationProviderDeliveryStatus::Rejected
            }
        }
    };
    let provider_receipt_id = EventId::new();
    let delivered_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        provider_receipt_id,
        plan.provider_plan_id,
        client_receipt.client_receipt_id,
        plan.provider_kind,
        status,
        &provider_message_id,
        &provider_response_hash,
        &failures,
        delivered_at,
    ))?;
    let receipt = NotificationProviderDeliveryReceipt {
        provider_receipt_id,
        provider_plan_id: plan.provider_plan_id,
        client_receipt_id: client_receipt.client_receipt_id,
        provider_kind: plan.provider_kind,
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
