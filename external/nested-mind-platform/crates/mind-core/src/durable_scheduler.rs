use crate::{hash_serializable, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ScheduledJobKind {
    OidcJwksRefresh,
    SigningExecution,
    CloudBackupUpload,
    ReplicationDelivery,
    SnapshotCompaction,
    BackupVerification,
    ConsensusCommit,
    ProviderExecution,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ScheduledJobStatus {
    Pending,
    Claimed,
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchedulerLeasePolicy {
    pub lease_seconds: u64,
    pub max_claims_per_poll: usize,
}

impl Default for SchedulerLeasePolicy {
    fn default() -> Self {
        Self {
            lease_seconds: 60,
            max_claims_per_poll: 10,
        }
    }
}

impl SchedulerLeasePolicy {
    pub fn validate(&self) -> MindResult<()> {
        if self.lease_seconds == 0 {
            return Err(MindError::Store(
                "scheduler lease must be greater than zero seconds".to_owned(),
            ));
        }
        if self.max_claims_per_poll == 0 {
            return Err(MindError::Store(
                "scheduler max_claims_per_poll must be greater than zero".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScheduledJob {
    pub job_id: EventId,
    pub kind: ScheduledJobKind,
    pub target: String,
    pub due_at: OffsetDateTime,
    pub not_before: OffsetDateTime,
    pub max_attempts: u32,
    pub attempt_count: u32,
    pub idempotency_key: String,
    pub payload_hash: String,
    pub payload_json: String,
    pub status: ScheduledJobStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub claimed_by: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lease_expires_at: Option<OffsetDateTime>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_error: Option<String>,
    pub created_at: OffsetDateTime,
    pub updated_at: OffsetDateTime,
}

impl ScheduledJob {
    pub fn new<T: Serialize>(
        kind: ScheduledJobKind,
        target: impl Into<String>,
        payload: &T,
        due_at: OffsetDateTime,
        max_attempts: u32,
    ) -> MindResult<Self> {
        if max_attempts == 0 {
            return Err(MindError::Store(
                "scheduled job max_attempts must be greater than zero".to_owned(),
            ));
        }
        let target = target.into();
        if target.trim().is_empty() {
            return Err(MindError::Store(
                "scheduled job target is required".to_owned(),
            ));
        }
        let payload_json = serde_json::to_string(payload)?;
        let payload_hash = hash_serializable(payload)?;
        let idempotency_key = hash_serializable(&(kind, &target, &payload_hash))?;
        let now = OffsetDateTime::now_utc();
        Ok(Self {
            job_id: EventId::new(),
            kind,
            target,
            due_at,
            not_before: due_at,
            max_attempts,
            attempt_count: 0,
            idempotency_key,
            payload_hash,
            payload_json,
            status: ScheduledJobStatus::Pending,
            claimed_by: None,
            lease_expires_at: None,
            last_error: None,
            created_at: now,
            updated_at: now,
        })
    }

    #[must_use]
    pub fn is_due_at(&self, now: OffsetDateTime) -> bool {
        self.status == ScheduledJobStatus::Pending
            && self.due_at <= now
            && self.not_before <= now
            && self.attempt_count < self.max_attempts
    }

    pub fn claim(
        &self,
        worker_id: impl Into<String>,
        policy: &SchedulerLeasePolicy,
        now: OffsetDateTime,
    ) -> MindResult<(Self, ScheduledJobClaim)> {
        policy.validate()?;
        if !self.is_due_at(now) {
            return Err(MindError::Store(
                "scheduled job is not due or not claimable".to_owned(),
            ));
        }
        let worker_id = worker_id.into();
        if worker_id.trim().is_empty() {
            return Err(MindError::Store(
                "scheduler worker id is required".to_owned(),
            ));
        }
        let lease_expires_at = now + Duration::seconds(policy.lease_seconds as i64);
        let mut next = self.clone();
        next.status = ScheduledJobStatus::Claimed;
        next.attempt_count = next.attempt_count.saturating_add(1);
        next.claimed_by = Some(worker_id.clone());
        next.lease_expires_at = Some(lease_expires_at);
        next.updated_at = now;
        let claim = ScheduledJobClaim {
            claim_id: EventId::new(),
            job_id: self.job_id,
            worker_id,
            attempt: next.attempt_count,
            claimed_at: now,
            lease_expires_at,
        };
        Ok((next, claim))
    }

    #[must_use]
    pub fn mark_succeeded(&self, now: OffsetDateTime) -> Self {
        let mut next = self.clone();
        next.status = ScheduledJobStatus::Succeeded;
        next.lease_expires_at = None;
        next.last_error = None;
        next.updated_at = now;
        next
    }

    #[must_use]
    pub fn mark_failed(
        &self,
        error: impl Into<String>,
        retry_at: Option<OffsetDateTime>,
        now: OffsetDateTime,
    ) -> Self {
        let mut next = self.clone();
        next.last_error = Some(error.into());
        next.lease_expires_at = None;
        next.status = if next.attempt_count >= next.max_attempts {
            ScheduledJobStatus::Failed
        } else {
            ScheduledJobStatus::Pending
        };
        if let Some(retry_at) = retry_at {
            next.not_before = retry_at;
            next.due_at = retry_at;
        }
        next.updated_at = now;
        next
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScheduledJobClaim {
    pub claim_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub attempt: u32,
    pub claimed_at: OffsetDateTime,
    pub lease_expires_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchedulerPollReport {
    pub poll_id: EventId,
    pub now: OffsetDateTime,
    pub due_count: usize,
    #[serde(default)]
    pub jobs: Vec<ScheduledJob>,
}

impl SchedulerPollReport {
    #[must_use]
    pub fn from_jobs(now: OffsetDateTime, jobs: Vec<ScheduledJob>) -> Self {
        Self {
            poll_id: EventId::new(),
            now,
            due_count: jobs.len(),
            jobs,
        }
    }
}

#[derive(Clone, Debug)]
pub struct JsonlSchedulerQueue {
    path: PathBuf,
}

impl JsonlSchedulerQueue {
    pub fn new(path: impl Into<PathBuf>) -> MindResult<Self> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        Ok(Self { path })
    }

    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn append_job(&self, job: &ScheduledJob) -> MindResult<()> {
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", serde_json::to_string(job)?)?;
        file.flush()?;
        file.sync_data()?;
        Ok(())
    }

    pub fn jobs(&self) -> MindResult<Vec<ScheduledJob>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let file = OpenOptions::new().read(true).open(&self.path)?;
        let reader = BufReader::new(file);
        let mut jobs = Vec::new();
        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            jobs.push(serde_json::from_str::<ScheduledJob>(&line)?);
        }
        Ok(jobs)
    }

    pub fn due_jobs(&self, now: OffsetDateTime, limit: usize) -> MindResult<Vec<ScheduledJob>> {
        Ok(self
            .jobs()?
            .into_iter()
            .filter(|job| job.is_due_at(now))
            .take(limit)
            .collect())
    }
}
