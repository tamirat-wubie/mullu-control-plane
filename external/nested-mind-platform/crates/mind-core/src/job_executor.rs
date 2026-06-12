use crate::{
    hash_serializable, EventId, MindError, MindResult, ScheduledJob, ScheduledJobKind,
    ScheduledJobStatus, SchedulerLeaseRecord,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum JobExecutionMode {
    PlanOnly,
    ReceiptOnly,
    LocalExecutor,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum JobExecutionStatus {
    Planned,
    Succeeded,
    Failed,
    Rejected,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum JobExecutionHandlerKind {
    OidcJwksRefresh,
    SigningExecution,
    CloudBackupUpload,
    ReplicationDelivery,
    SnapshotCompaction,
    BackupVerification,
    ConsensusCommit,
    ProviderExecution,
}

impl From<ScheduledJobKind> for JobExecutionHandlerKind {
    fn from(kind: ScheduledJobKind) -> Self {
        match kind {
            ScheduledJobKind::OidcJwksRefresh => Self::OidcJwksRefresh,
            ScheduledJobKind::SigningExecution => Self::SigningExecution,
            ScheduledJobKind::CloudBackupUpload => Self::CloudBackupUpload,
            ScheduledJobKind::ReplicationDelivery => Self::ReplicationDelivery,
            ScheduledJobKind::SnapshotCompaction => Self::SnapshotCompaction,
            ScheduledJobKind::BackupVerification => Self::BackupVerification,
            ScheduledJobKind::ConsensusCommit => Self::ConsensusCommit,
            ScheduledJobKind::ProviderExecution => Self::ProviderExecution,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct JobExecutionReceipt {
    pub receipt_id: EventId,
    pub job_id: EventId,
    pub kind: ScheduledJobKind,
    pub handler: JobExecutionHandlerKind,
    pub target: String,
    pub worker_id: String,
    pub attempt: u32,
    pub mode: JobExecutionMode,
    pub status: JobExecutionStatus,
    pub expected_payload_hash: String,
    pub observed_payload_hash: String,
    pub evidence_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lease_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub started_at: OffsetDateTime,
    pub completed_at: OffsetDateTime,
}

impl JobExecutionReceipt {
    pub fn new(
        job: &ScheduledJob,
        worker_id: impl Into<String>,
        lease: Option<&SchedulerLeaseRecord>,
        mode: JobExecutionMode,
    ) -> MindResult<Self> {
        let worker_id = worker_id.into();
        if worker_id.trim().is_empty() {
            return Err(MindError::Store(
                "job execution worker id is required".to_owned(),
            ));
        }
        if job.status != ScheduledJobStatus::Claimed && mode != JobExecutionMode::PlanOnly {
            return Err(MindError::Store(
                "job execution requires a claimed job unless mode is plan_only".to_owned(),
            ));
        }
        if let Some(lease) = lease {
            if lease.job_id != job.job_id {
                return Err(MindError::Store(
                    "job execution lease does not match job".to_owned(),
                ));
            }
            if lease.worker_id != worker_id {
                return Err(MindError::Store(
                    "job execution lease belongs to another worker".to_owned(),
                ));
            }
            if lease.job_payload_hash != job.payload_hash {
                return Err(MindError::Store(
                    "job execution lease payload hash mismatch".to_owned(),
                ));
            }
        }
        let handler = JobExecutionHandlerKind::from(job.kind);
        let status = match mode {
            JobExecutionMode::PlanOnly => JobExecutionStatus::Planned,
            JobExecutionMode::ReceiptOnly | JobExecutionMode::LocalExecutor => {
                JobExecutionStatus::Succeeded
            }
        };
        let observed_payload_hash = match status {
            JobExecutionStatus::Planned | JobExecutionStatus::Succeeded => job.payload_hash.clone(),
            JobExecutionStatus::Failed | JobExecutionStatus::Rejected => String::new(),
        };
        let mut metadata = BTreeMap::new();
        metadata.insert("idempotency_key".to_owned(), job.idempotency_key.clone());
        metadata.insert("job_status".to_owned(), format!("{:?}", job.status));
        metadata.insert(
            "payload_bytes".to_owned(),
            job.payload_json.len().to_string(),
        );
        let started_at = OffsetDateTime::now_utc();
        let evidence_hash = calculate_job_evidence_hash(
            job,
            &worker_id,
            lease.map(|lease| lease.lease_id),
            mode,
            status,
            &observed_payload_hash,
        )?;
        Ok(Self {
            receipt_id: EventId::new(),
            job_id: job.job_id,
            kind: job.kind,
            handler,
            target: job.target.clone(),
            worker_id,
            attempt: job.attempt_count,
            mode,
            status,
            expected_payload_hash: job.payload_hash.clone(),
            observed_payload_hash,
            evidence_hash,
            lease_id: lease.map(|lease| lease.lease_id),
            error: None,
            metadata,
            started_at,
            completed_at: OffsetDateTime::now_utc(),
        })
    }

    #[must_use]
    pub fn failed(
        job: &ScheduledJob,
        worker_id: impl Into<String>,
        error: impl Into<String>,
    ) -> Self {
        let worker_id = worker_id.into();
        let mut metadata = BTreeMap::new();
        metadata.insert("idempotency_key".to_owned(), job.idempotency_key.clone());
        Self {
            receipt_id: EventId::new(),
            job_id: job.job_id,
            kind: job.kind,
            handler: JobExecutionHandlerKind::from(job.kind),
            target: job.target.clone(),
            worker_id,
            attempt: job.attempt_count,
            mode: JobExecutionMode::ReceiptOnly,
            status: JobExecutionStatus::Failed,
            expected_payload_hash: job.payload_hash.clone(),
            observed_payload_hash: String::new(),
            evidence_hash: String::new(),
            lease_id: None,
            error: Some(error.into()),
            metadata,
            started_at: OffsetDateTime::now_utc(),
            completed_at: OffsetDateTime::now_utc(),
        }
    }

    pub fn verify_for(
        &self,
        job: &ScheduledJob,
        lease: Option<&SchedulerLeaseRecord>,
    ) -> MindResult<()> {
        if self.job_id != job.job_id || self.kind != job.kind || self.target != job.target {
            return Err(MindError::Store(
                "job execution receipt target mismatch".to_owned(),
            ));
        }
        if self.expected_payload_hash != job.payload_hash {
            return Err(MindError::Store(
                "job execution receipt expected payload hash mismatch".to_owned(),
            ));
        }
        if matches!(
            self.status,
            JobExecutionStatus::Succeeded | JobExecutionStatus::Planned
        ) && self.observed_payload_hash != job.payload_hash
        {
            return Err(MindError::Store(
                "job execution receipt observed payload hash mismatch".to_owned(),
            ));
        }
        if let Some(lease) = lease {
            if self.lease_id != Some(lease.lease_id) {
                return Err(MindError::Store(
                    "job execution receipt lease mismatch".to_owned(),
                ));
            }
            if lease.job_payload_hash != job.payload_hash {
                return Err(MindError::Store(
                    "job execution receipt lease payload hash mismatch".to_owned(),
                ));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn should_mark_job_succeeded(&self) -> bool {
        self.status == JobExecutionStatus::Succeeded
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct JobReceiptVerificationReport {
    pub report_id: EventId,
    pub receipt_id: EventId,
    pub job_id: EventId,
    pub valid: bool,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub checked_at: OffsetDateTime,
}

impl JobReceiptVerificationReport {
    #[must_use]
    pub fn valid(receipt: &JobExecutionReceipt) -> Self {
        Self {
            report_id: EventId::new(),
            receipt_id: receipt.receipt_id,
            job_id: receipt.job_id,
            valid: true,
            reasons: vec!["job execution receipt is hash-consistent".to_owned()],
            checked_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn invalid(receipt: &JobExecutionReceipt, reason: impl Into<String>) -> Self {
        Self {
            report_id: EventId::new(),
            receipt_id: receipt.receipt_id,
            job_id: receipt.job_id,
            valid: false,
            reasons: vec![reason.into()],
            checked_at: OffsetDateTime::now_utc(),
        }
    }
}

pub fn execute_job_with_receipt(
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    lease: Option<&SchedulerLeaseRecord>,
    mode: JobExecutionMode,
) -> MindResult<JobExecutionReceipt> {
    let receipt = JobExecutionReceipt::new(job, worker_id, lease, mode)?;
    receipt.verify_for(job, lease)?;
    Ok(receipt)
}

#[must_use]
pub fn verify_job_execution_receipt(
    job: &ScheduledJob,
    receipt: &JobExecutionReceipt,
    lease: Option<&SchedulerLeaseRecord>,
) -> JobReceiptVerificationReport {
    match receipt.verify_for(job, lease) {
        Ok(()) => JobReceiptVerificationReport::valid(receipt),
        Err(error) => JobReceiptVerificationReport::invalid(receipt, error.to_string()),
    }
}

fn calculate_job_evidence_hash(
    job: &ScheduledJob,
    worker_id: &str,
    lease_id: Option<EventId>,
    mode: JobExecutionMode,
    status: JobExecutionStatus,
    observed_payload_hash: &str,
) -> MindResult<String> {
    #[derive(Serialize)]
    struct Evidence<'a> {
        job_id: EventId,
        kind: ScheduledJobKind,
        target: &'a str,
        worker_id: &'a str,
        attempt: u32,
        payload_hash: &'a str,
        lease_id: Option<EventId>,
        mode: JobExecutionMode,
        status: JobExecutionStatus,
        observed_payload_hash: &'a str,
    }
    hash_serializable(&Evidence {
        job_id: job.job_id,
        kind: job.kind,
        target: &job.target,
        worker_id,
        attempt: job.attempt_count,
        payload_hash: &job.payload_hash,
        lease_id,
        mode,
        status,
        observed_payload_hash,
    })
}
