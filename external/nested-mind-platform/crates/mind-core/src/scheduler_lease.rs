use crate::{
    hash_serializable, EventId, MindError, MindResult, ScheduledJob, ScheduledJobClaim,
    SchedulerLeasePolicy,
};
use serde::{Deserialize, Serialize};
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum SchedulerLeaseStatus {
    Active,
    Released,
    Expired,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchedulerLeaseRecord {
    pub lease_id: EventId,
    pub claim_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub attempt: u32,
    pub claim_hash: String,
    pub job_payload_hash: String,
    pub status: SchedulerLeaseStatus,
    pub acquired_at: OffsetDateTime,
    pub lease_expires_at: OffsetDateTime,
    pub updated_at: OffsetDateTime,
}

impl SchedulerLeaseRecord {
    pub fn from_claim(job: &ScheduledJob, claim: &ScheduledJobClaim) -> MindResult<Self> {
        if job.job_id != claim.job_id {
            return Err(MindError::Store(
                "scheduler lease claim does not match job".to_owned(),
            ));
        }
        Ok(Self {
            lease_id: EventId::new(),
            claim_id: claim.claim_id,
            job_id: claim.job_id,
            worker_id: claim.worker_id.clone(),
            attempt: claim.attempt,
            claim_hash: hash_serializable(claim)?,
            job_payload_hash: job.payload_hash.clone(),
            status: SchedulerLeaseStatus::Active,
            acquired_at: claim.claimed_at,
            lease_expires_at: claim.lease_expires_at,
            updated_at: claim.claimed_at,
        })
    }

    pub fn verify_for(&self, job: &ScheduledJob, claim: &ScheduledJobClaim) -> MindResult<()> {
        if self.job_id != job.job_id || self.job_id != claim.job_id {
            return Err(MindError::Store(
                "scheduler lease does not match job/claim".to_owned(),
            ));
        }
        if self.worker_id != claim.worker_id || self.attempt != claim.attempt {
            return Err(MindError::Store(
                "scheduler lease worker/attempt mismatch".to_owned(),
            ));
        }
        if self.job_payload_hash != job.payload_hash {
            return Err(MindError::Store(
                "scheduler lease payload hash mismatch".to_owned(),
            ));
        }
        let expected = hash_serializable(claim)?;
        if expected != self.claim_hash {
            return Err(MindError::Store(
                "scheduler lease claim hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn is_active_at(&self, now: OffsetDateTime) -> bool {
        self.status == SchedulerLeaseStatus::Active && now < self.lease_expires_at
    }

    pub fn renew(&self, policy: &SchedulerLeasePolicy, now: OffsetDateTime) -> MindResult<Self> {
        policy.validate()?;
        if !self.is_active_at(now) {
            return Err(MindError::Store(
                "scheduler lease is not active and cannot be renewed".to_owned(),
            ));
        }
        let mut next = self.clone();
        next.lease_expires_at = now + Duration::seconds(policy.lease_seconds as i64);
        next.updated_at = now;
        Ok(next)
    }

    #[must_use]
    pub fn release(&self, now: OffsetDateTime) -> Self {
        let mut next = self.clone();
        next.status = SchedulerLeaseStatus::Released;
        next.updated_at = now;
        next
    }

    #[must_use]
    pub fn expire_if_elapsed(&self, now: OffsetDateTime) -> Self {
        if self.status != SchedulerLeaseStatus::Active || now < self.lease_expires_at {
            return self.clone();
        }
        let mut next = self.clone();
        next.status = SchedulerLeaseStatus::Expired;
        next.updated_at = now;
        next
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchedulerLeaseClaimReport {
    pub report_id: EventId,
    pub worker_id: String,
    pub requested_limit: usize,
    pub claimed_count: usize,
    #[serde(default)]
    pub leases: Vec<SchedulerLeaseRecord>,
    #[serde(default)]
    pub updated_jobs: Vec<ScheduledJob>,
    pub claimed_at: OffsetDateTime,
}

pub fn claim_due_jobs_with_leases(
    jobs: &[ScheduledJob],
    worker_id: impl Into<String>,
    policy: &SchedulerLeasePolicy,
    limit: usize,
    now: OffsetDateTime,
) -> MindResult<SchedulerLeaseClaimReport> {
    policy.validate()?;
    let worker_id = worker_id.into();
    if worker_id.trim().is_empty() {
        return Err(MindError::Store(
            "scheduler worker id is required".to_owned(),
        ));
    }
    let mut leases = Vec::new();
    let mut updated_jobs = Vec::new();
    for job in jobs
        .iter()
        .filter(|job| job.is_due_at(now))
        .take(limit.max(1).min(policy.max_claims_per_poll.max(1)))
    {
        let (claimed_job, claim) = job.claim(worker_id.clone(), policy, now)?;
        let lease = SchedulerLeaseRecord::from_claim(&claimed_job, &claim)?;
        leases.push(lease);
        updated_jobs.push(claimed_job);
    }
    Ok(SchedulerLeaseClaimReport {
        report_id: EventId::new(),
        worker_id,
        requested_limit: limit,
        claimed_count: leases.len(),
        leases,
        updated_jobs,
        claimed_at: now,
    })
}
