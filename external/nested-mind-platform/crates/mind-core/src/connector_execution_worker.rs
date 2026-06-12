use crate::{hash_serializable, EventId, MindError, MindResult, ScheduledJob};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConnectorWorkerActionKind {
    GitHubActionExecution,
    BranchProtectionWorker,
    KubernetesDryRunExecution,
    WaiverNotificationDelivery,
    OidcRefresh,
    ReplicationDelivery,
    CloudBackupUpload,
    ProviderExecution,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum ConnectorWorkerMode {
    #[default]
    PlanOnly,
    DryRun,
    ExecuteApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConnectorWorkerExecutionStatus {
    Planned,
    Completed,
    Failed,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConnectorWorkerJobPlan {
    pub connector_plan_id: EventId,
    pub worker_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scheduled_job_id: Option<EventId>,
    pub action_kind: ConnectorWorkerActionKind,
    pub target: String,
    pub payload_hash: String,
    pub mode: ConnectorWorkerMode,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl ConnectorWorkerJobPlan {
    pub fn verify(&self) -> MindResult<()> {
        if self.worker_id.trim().is_empty()
            || self.target.trim().is_empty()
            || self.payload_hash.trim().is_empty()
        {
            return Err(MindError::Store(
                "connector worker plan requires worker, target and payload hash".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.connector_plan_id,
            &self.worker_id,
            &self.scheduled_job_id,
            self.action_kind,
            &self.target,
            &self.payload_hash,
            self.mode,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "connector worker job plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConnectorWorkerExecutionReceipt {
    pub receipt_id: EventId,
    pub connector_plan_id: EventId,
    pub action_kind: ConnectorWorkerActionKind,
    pub status: ConnectorWorkerExecutionStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub external_receipt_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    #[serde(default)]
    pub errors: Vec<String>,
    pub receipt_hash: String,
    pub executed_at: OffsetDateTime,
}

impl ConnectorWorkerExecutionReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.connector_plan_id,
            self.action_kind,
            self.status,
            &self.external_receipt_hash,
            &self.response_hash,
            &self.errors,
            self.executed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "connector worker receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_connector_worker_job(
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    action_kind: ConnectorWorkerActionKind,
    mode: ConnectorWorkerMode,
) -> MindResult<ConnectorWorkerJobPlan> {
    let worker_id = worker_id.into();
    if worker_id.trim().is_empty() {
        return Err(MindError::Store(
            "connector worker id is required".to_owned(),
        ));
    }
    let connector_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        connector_plan_id,
        &worker_id,
        &Some(job.job_id),
        action_kind,
        &job.target,
        &job.payload_hash,
        mode,
        created_at,
    ))?;
    let plan = ConnectorWorkerJobPlan {
        connector_plan_id,
        worker_id,
        scheduled_job_id: Some(job.job_id),
        action_kind,
        target: job.target.clone(),
        payload_hash: job.payload_hash.clone(),
        mode,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_connector_worker_execution_receipt(
    plan: &ConnectorWorkerJobPlan,
    external_receipt_hash: Option<String>,
    response_hash: Option<String>,
    errors: Vec<String>,
) -> MindResult<ConnectorWorkerExecutionReceipt> {
    plan.verify()?;
    let status = match plan.mode {
        ConnectorWorkerMode::PlanOnly => ConnectorWorkerExecutionStatus::Planned,
        ConnectorWorkerMode::DryRun | ConnectorWorkerMode::ExecuteApproved => {
            if errors.is_empty() {
                ConnectorWorkerExecutionStatus::Completed
            } else {
                ConnectorWorkerExecutionStatus::Failed
            }
        }
    };
    if plan.mode == ConnectorWorkerMode::ExecuteApproved
        && external_receipt_hash.is_none()
        && errors.is_empty()
    {
        return Err(MindError::Store(
            "approved connector execution requires external receipt hash".to_owned(),
        ));
    }
    let receipt_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.connector_plan_id,
        plan.action_kind,
        status,
        &external_receipt_hash,
        &response_hash,
        &errors,
        executed_at,
    ))?;
    let receipt = ConnectorWorkerExecutionReceipt {
        receipt_id,
        connector_plan_id: plan.connector_plan_id,
        action_kind: plan.action_kind,
        status,
        external_receipt_hash,
        response_hash,
        errors,
        receipt_hash,
        executed_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
