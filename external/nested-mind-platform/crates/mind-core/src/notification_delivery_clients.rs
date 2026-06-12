use crate::{
    hash_serializable, EventId, MindError, MindResult, WaiverNotificationAdapterKind,
    WaiverNotificationAdapterPlan, WaiverNotificationAdapterReceipt,
    WaiverNotificationAdapterStatus,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum NotificationDeliveryClientMode {
    #[default]
    PlanOnly,
    DryRun,
    SendApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum NotificationDeliveryClientStatus {
    Planned,
    DryRunAccepted,
    Sent,
    Failed,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct NotificationDeliveryClientPlan {
    pub client_plan_id: EventId,
    pub adapter_plan_id: EventId,
    pub adapter_kind: WaiverNotificationAdapterKind,
    pub mode: NotificationDeliveryClientMode,
    pub endpoint_reference: String,
    pub request_template: Value,
    pub idempotency_key: String,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl NotificationDeliveryClientPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.endpoint_reference.trim().is_empty() || self.idempotency_key.trim().is_empty() {
            return Err(MindError::Store(
                "notification delivery client plan requires endpoint and idempotency key"
                    .to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.client_plan_id,
            self.adapter_plan_id,
            self.adapter_kind,
            self.mode,
            &self.endpoint_reference,
            &self.request_template,
            &self.idempotency_key,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "notification delivery client plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NotificationDeliveryClientReceipt {
    pub client_receipt_id: EventId,
    pub client_plan_id: EventId,
    pub adapter_receipt_id: EventId,
    pub adapter_kind: WaiverNotificationAdapterKind,
    pub status: NotificationDeliveryClientStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_message_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub receipt_hash: String,
    pub delivered_at: OffsetDateTime,
}

impl NotificationDeliveryClientReceipt {
    pub fn verify(&self) -> MindResult<()> {
        if self.status == NotificationDeliveryClientStatus::Sent
            && self.provider_message_id.is_none()
        {
            return Err(MindError::Store(
                "sent notification delivery receipt requires provider message id".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.client_receipt_id,
            self.client_plan_id,
            self.adapter_receipt_id,
            self.adapter_kind,
            self.status,
            &self.provider_message_id,
            &self.provider_response_hash,
            &self.failures,
            self.delivered_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "notification delivery client receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_notification_delivery_client(
    adapter_plan: &WaiverNotificationAdapterPlan,
    mode: NotificationDeliveryClientMode,
    endpoint_reference: impl Into<String>,
    request_template: Value,
) -> MindResult<NotificationDeliveryClientPlan> {
    adapter_plan.verify()?;
    let endpoint_reference = endpoint_reference.into();
    let client_plan_id = EventId::new();
    let idempotency_key = hash_serializable(&(
        adapter_plan.adapter_plan_id,
        adapter_plan.notification_plan_id,
        &endpoint_reference,
        &request_template,
    ))?;
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        client_plan_id,
        adapter_plan.adapter_plan_id,
        adapter_plan.adapter_kind,
        mode,
        &endpoint_reference,
        &request_template,
        &idempotency_key,
        created_at,
    ))?;
    let plan = NotificationDeliveryClientPlan {
        client_plan_id,
        adapter_plan_id: adapter_plan.adapter_plan_id,
        adapter_kind: adapter_plan.adapter_kind,
        mode,
        endpoint_reference,
        request_template,
        idempotency_key,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_notification_delivery_client_receipt(
    plan: &NotificationDeliveryClientPlan,
    adapter_receipt: &WaiverNotificationAdapterReceipt,
    provider_message_id: Option<String>,
    provider_response_hash: Option<String>,
    failures: Vec<String>,
) -> MindResult<NotificationDeliveryClientReceipt> {
    plan.verify()?;
    adapter_receipt.verify()?;
    if adapter_receipt.adapter_plan_id != plan.adapter_plan_id
        || adapter_receipt.adapter_kind != plan.adapter_kind
    {
        return Err(MindError::Store(
            "notification delivery client receipt does not match adapter receipt".to_owned(),
        ));
    }
    let status = if !failures.is_empty() {
        NotificationDeliveryClientStatus::Failed
    } else {
        match adapter_receipt.status {
            WaiverNotificationAdapterStatus::Sent => NotificationDeliveryClientStatus::Sent,
            WaiverNotificationAdapterStatus::DryRunAccepted => {
                NotificationDeliveryClientStatus::DryRunAccepted
            }
            WaiverNotificationAdapterStatus::Planned => NotificationDeliveryClientStatus::Planned,
            WaiverNotificationAdapterStatus::Failed => NotificationDeliveryClientStatus::Failed,
            WaiverNotificationAdapterStatus::Rejected => NotificationDeliveryClientStatus::Rejected,
        }
    };
    let client_receipt_id = EventId::new();
    let delivered_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        client_receipt_id,
        plan.client_plan_id,
        adapter_receipt.receipt_id,
        plan.adapter_kind,
        status,
        &provider_message_id,
        &provider_response_hash,
        &failures,
        delivered_at,
    ))?;
    let receipt = NotificationDeliveryClientReceipt {
        client_receipt_id,
        client_plan_id: plan.client_plan_id,
        adapter_receipt_id: adapter_receipt.receipt_id,
        adapter_kind: plan.adapter_kind,
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
