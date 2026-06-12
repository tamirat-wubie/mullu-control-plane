use crate::{
    hash_serializable, EventId, MindError, MindResult, ScheduledJob, SchedulerLeasePolicy,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DistributedLeaseBackendKind {
    SqliteCompareAndSwap,
    PostgresAdvisoryLock,
    RedisRedlock,
    EtcdLease,
    ConsulSession,
    ExternalHttpGateway,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseServiceBoundary {
    pub boundary_id: EventId,
    pub backend: DistributedLeaseBackendKind,
    pub service_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    pub default_lease_seconds: u64,
    pub fencing_tokens_required: bool,
    pub receipt_required: bool,
    pub created_at: OffsetDateTime,
}

impl DistributedLeaseServiceBoundary {
    pub fn sqlite_local(service_id: impl Into<String>) -> MindResult<Self> {
        Self::new(
            DistributedLeaseBackendKind::SqliteCompareAndSwap,
            service_id,
            None,
            60,
        )
    }

    pub fn external_gateway(
        service_id: impl Into<String>,
        endpoint: impl Into<String>,
        default_lease_seconds: u64,
    ) -> MindResult<Self> {
        Self::new(
            DistributedLeaseBackendKind::ExternalHttpGateway,
            service_id,
            Some(endpoint.into()),
            default_lease_seconds,
        )
    }

    pub fn new(
        backend: DistributedLeaseBackendKind,
        service_id: impl Into<String>,
        endpoint: Option<String>,
        default_lease_seconds: u64,
    ) -> MindResult<Self> {
        let service_id = service_id.into();
        if service_id.trim().is_empty() {
            return Err(MindError::Store(
                "distributed lease service id is required".to_owned(),
            ));
        }
        if default_lease_seconds == 0 {
            return Err(MindError::Store(
                "distributed lease duration must be greater than zero".to_owned(),
            ));
        }
        Ok(Self {
            boundary_id: EventId::new(),
            backend,
            service_id,
            endpoint,
            default_lease_seconds,
            fencing_tokens_required: true,
            receipt_required: true,
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseClaimRequest {
    pub request_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub target: String,
    pub attempt: u32,
    pub expected_payload_hash: String,
    pub lease_seconds: u64,
    pub idempotency_key: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub requested_at: OffsetDateTime,
}

impl DistributedLeaseClaimRequest {
    pub fn from_job(
        job: &ScheduledJob,
        worker_id: impl Into<String>,
        policy: &SchedulerLeasePolicy,
    ) -> MindResult<Self> {
        policy.validate()?;
        let worker_id = worker_id.into();
        if worker_id.trim().is_empty() {
            return Err(MindError::Store(
                "distributed lease worker id is required".to_owned(),
            ));
        }
        let idempotency_key =
            hash_serializable(&(job.job_id, &worker_id, job.attempt_count, &job.payload_hash))?;
        let mut metadata = BTreeMap::new();
        metadata.insert(
            "scheduled_job_idempotency_key".to_owned(),
            job.idempotency_key.clone(),
        );
        Ok(Self {
            request_id: EventId::new(),
            job_id: job.job_id,
            worker_id,
            target: job.target.clone(),
            attempt: job.attempt_count.saturating_add(1),
            expected_payload_hash: job.payload_hash.clone(),
            lease_seconds: policy.lease_seconds,
            idempotency_key,
            metadata,
            requested_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DistributedLeaseClaimStatus {
    Granted,
    Rejected,
    Conflict,
    Deferred,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseClaimReceipt {
    pub receipt_id: EventId,
    pub request_id: EventId,
    pub backend: DistributedLeaseBackendKind,
    pub status: DistributedLeaseClaimStatus,
    pub job_id: EventId,
    pub worker_id: String,
    pub expected_payload_hash: String,
    pub observed_payload_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fencing_token: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lease_expires_at: Option<OffsetDateTime>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub issued_at: OffsetDateTime,
}

impl DistributedLeaseClaimReceipt {
    #[must_use]
    pub fn granted(
        boundary: &DistributedLeaseServiceBoundary,
        request: &DistributedLeaseClaimRequest,
    ) -> Self {
        let expires = OffsetDateTime::now_utc() + Duration::seconds(request.lease_seconds as i64);
        Self {
            receipt_id: EventId::new(),
            request_id: request.request_id,
            backend: boundary.backend,
            status: DistributedLeaseClaimStatus::Granted,
            job_id: request.job_id,
            worker_id: request.worker_id.clone(),
            expected_payload_hash: request.expected_payload_hash.clone(),
            observed_payload_hash: request.expected_payload_hash.clone(),
            fencing_token: Some(format!(
                "{}:{}:{}",
                boundary.service_id, request.job_id, request.attempt
            )),
            lease_expires_at: Some(expires),
            reasons: vec!["lease claim granted by boundary contract".to_owned()],
            issued_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn rejected(
        boundary: &DistributedLeaseServiceBoundary,
        request: &DistributedLeaseClaimRequest,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            receipt_id: EventId::new(),
            request_id: request.request_id,
            backend: boundary.backend,
            status: DistributedLeaseClaimStatus::Rejected,
            job_id: request.job_id,
            worker_id: request.worker_id.clone(),
            expected_payload_hash: request.expected_payload_hash.clone(),
            observed_payload_hash: String::new(),
            fencing_token: None,
            lease_expires_at: None,
            reasons: vec![reason.into()],
            issued_at: OffsetDateTime::now_utc(),
        }
    }

    pub fn verify_for(&self, request: &DistributedLeaseClaimRequest) -> MindResult<()> {
        if self.request_id != request.request_id
            || self.job_id != request.job_id
            || self.worker_id != request.worker_id
        {
            return Err(MindError::Store(
                "distributed lease receipt target mismatch".to_owned(),
            ));
        }
        if self.expected_payload_hash != request.expected_payload_hash {
            return Err(MindError::Store(
                "distributed lease expected hash mismatch".to_owned(),
            ));
        }
        if self.status == DistributedLeaseClaimStatus::Granted
            && self.observed_payload_hash != request.expected_payload_hash
        {
            return Err(MindError::Store(
                "distributed lease observed hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseGatewayPlan {
    pub plan_id: EventId,
    pub boundary: DistributedLeaseServiceBoundary,
    pub request: DistributedLeaseClaimRequest,
    pub request_hash: String,
    pub created_at: OffsetDateTime,
}

pub fn plan_external_distributed_lease_claim(
    boundary: &DistributedLeaseServiceBoundary,
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    policy: &SchedulerLeasePolicy,
) -> MindResult<DistributedLeaseGatewayPlan> {
    let request = DistributedLeaseClaimRequest::from_job(job, worker_id, policy)?;
    let request_hash = hash_serializable(&request)?;
    Ok(DistributedLeaseGatewayPlan {
        plan_id: EventId::new(),
        boundary: boundary.clone(),
        request,
        request_hash,
        created_at: OffsetDateTime::now_utc(),
    })
}
