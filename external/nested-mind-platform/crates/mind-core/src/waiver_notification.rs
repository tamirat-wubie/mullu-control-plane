use crate::{hash_serializable, EventId, MindError, MindResult, WaiverReviewerAssignmentPlan};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverNotificationChannel {
    Email,
    GitHubIssue,
    Slack,
    Webhook,
    Manual,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WaiverNotificationStatus {
    Planned,
    Delivered,
    Failed,
    Escalated,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverNotificationPlan {
    pub notification_plan_id: EventId,
    pub assignment_plan_id: EventId,
    pub review_id: EventId,
    pub proposal_id: EventId,
    pub channel: WaiverNotificationChannel,
    #[serde(default)]
    pub recipients: Vec<String>,
    pub subject: String,
    pub body_hash: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl WaiverNotificationPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.notification_plan_id,
            self.assignment_plan_id,
            self.review_id,
            self.proposal_id,
            self.channel,
            &self.recipients,
            &self.subject,
            &self.body_hash,
            &self.metadata,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "waiver notification plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WaiverNotificationReceipt {
    pub receipt_id: EventId,
    pub notification_plan_id: EventId,
    pub assignment_plan_id: EventId,
    pub status: WaiverNotificationStatus,
    pub channel: WaiverNotificationChannel,
    #[serde(default)]
    pub delivered_to: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_message_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    #[serde(default)]
    pub failures: Vec<String>,
    pub receipt_hash: String,
    pub delivered_at: OffsetDateTime,
}

impl WaiverNotificationReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.notification_plan_id,
            self.assignment_plan_id,
            self.status,
            self.channel,
            &self.delivered_to,
            &self.provider_message_id,
            &self.response_hash,
            &self.failures,
            self.delivered_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "waiver notification receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_waiver_notification_delivery(
    assignment: &WaiverReviewerAssignmentPlan,
    channel: WaiverNotificationChannel,
    subject: impl Into<String>,
    body: impl Into<String>,
) -> MindResult<WaiverNotificationPlan> {
    assignment.verify()?;
    let subject = subject.into();
    let body = body.into();
    if subject.trim().is_empty() || body.trim().is_empty() {
        return Err(MindError::Store(
            "waiver notification requires subject and body".to_owned(),
        ));
    }
    let recipients = assignment
        .selected_reviewers
        .iter()
        .map(|reviewer| reviewer.operator.clone())
        .collect::<Vec<_>>();
    let mut metadata = BTreeMap::new();
    metadata.insert(
        "selected_reviewers".to_owned(),
        assignment.selected_reviewers.len().to_string(),
    );
    metadata.insert("status".to_owned(), format!("{:?}", assignment.status));
    let notification_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let body_hash = hash_serializable(&body)?;
    let plan_hash = hash_serializable(&(
        notification_plan_id,
        assignment.assignment_plan_id,
        assignment.review_id,
        assignment.proposal_id,
        channel,
        &recipients,
        &subject,
        &body_hash,
        &metadata,
        created_at,
    ))?;
    let plan = WaiverNotificationPlan {
        notification_plan_id,
        assignment_plan_id: assignment.assignment_plan_id,
        review_id: assignment.review_id,
        proposal_id: assignment.proposal_id,
        channel,
        recipients,
        subject,
        body_hash,
        metadata,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_waiver_notification_receipt(
    plan: &WaiverNotificationPlan,
    delivered_to: Vec<String>,
    provider_message_id: Option<String>,
    response_hash: Option<String>,
    failures: Vec<String>,
) -> MindResult<WaiverNotificationReceipt> {
    plan.verify()?;
    let status = if !failures.is_empty() {
        WaiverNotificationStatus::Failed
    } else if delivered_to.is_empty() {
        WaiverNotificationStatus::Planned
    } else {
        WaiverNotificationStatus::Delivered
    };
    let receipt_id = EventId::new();
    let delivered_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.notification_plan_id,
        plan.assignment_plan_id,
        status,
        plan.channel,
        &delivered_to,
        &provider_message_id,
        &response_hash,
        &failures,
        delivered_at,
    ))?;
    let receipt = WaiverNotificationReceipt {
        receipt_id,
        notification_plan_id: plan.notification_plan_id,
        assignment_plan_id: plan.assignment_plan_id,
        status,
        channel: plan.channel,
        delivered_to,
        provider_message_id,
        response_hash,
        failures,
        receipt_hash,
        delivered_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
