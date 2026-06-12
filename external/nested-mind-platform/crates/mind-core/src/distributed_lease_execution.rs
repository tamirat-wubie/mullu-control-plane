use crate::{
    evaluate_distributed_lease_adapter_claim, hash_serializable, DistributedLeaseAdapterRegistry,
    DistributedLeaseAdapterReport, DistributedLeaseBackendKind, DistributedLeaseClaimReceipt,
    DistributedLeaseClaimStatus, DistributedLeaseServiceBoundary, EventId, MindError, MindResult,
    ScheduledJob, SchedulerLeasePolicy,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DistributedLeaseExecutionMode {
    PlanOnly,
    SqliteCompareAndSwap,
    PostgresAdvisoryLock,
    EtcdTxn,
    ExternalGateway,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseExecutionPlan {
    pub plan_id: EventId,
    pub backend: DistributedLeaseBackendKind,
    pub mode: DistributedLeaseExecutionMode,
    pub job_id: EventId,
    pub worker_id: String,
    pub expected_payload_hash: String,
    pub operation_json: String,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl DistributedLeaseExecutionPlan {
    pub fn from_boundary(
        boundary: &DistributedLeaseServiceBoundary,
        job: &ScheduledJob,
        worker_id: impl Into<String>,
        policy: &SchedulerLeasePolicy,
        mode: DistributedLeaseExecutionMode,
    ) -> MindResult<Self> {
        policy.validate()?;
        let worker_id = worker_id.into();
        let operation = match boundary.backend {
            DistributedLeaseBackendKind::SqliteCompareAndSwap => json!({
                "adapter": "sqlite_compare_and_swap",
                "where": {
                    "job_id": job.job_id,
                    "status": "pending",
                    "attempt_count": job.attempt_count,
                    "payload_hash": &job.payload_hash,
                },
                "set": {
                    "claimed_by": &worker_id,
                    "lease_seconds": policy.lease_seconds,
                }
            }),
            DistributedLeaseBackendKind::PostgresAdvisoryLock => json!({
                "adapter": "postgres_advisory_lock",
                "sql": "SELECT pg_try_advisory_xact_lock(hashtext($1)); UPDATE scheduled_jobs SET status='Claimed' WHERE job_id=$2 AND status='Pending' AND payload_hash=$3;",
                "lock_key_material": [job.job_id.to_string(), worker_id.clone()],
                "lease_seconds": policy.lease_seconds,
            }),
            DistributedLeaseBackendKind::EtcdLease => json!({
                "adapter": "etcd_txn_lease",
                "compare": {"key": format!("/mind/scheduler/jobs/{}/owner", job.job_id), "version": 0},
                "success": {"put": &worker_id, "lease_seconds": policy.lease_seconds},
                "payload_hash": &job.payload_hash,
            }),
            DistributedLeaseBackendKind::ExternalHttpGateway => json!({
                "adapter": "external_http_gateway",
                "endpoint": &boundary.endpoint,
                "job_id": job.job_id,
                "worker_id": &worker_id,
                "lease_seconds": policy.lease_seconds,
            }),
            DistributedLeaseBackendKind::RedisRedlock
            | DistributedLeaseBackendKind::ConsulSession => json!({
                "adapter": format!("{:?}", boundary.backend),
                "status": "boundary_defined_execution_pending",
                "job_id": job.job_id,
                "worker_id": &worker_id,
            }),
        };
        let operation_json = serde_json::to_string(&operation)?;
        let plan_hash = hash_serializable(&(
            boundary.boundary_id,
            boundary.backend,
            job.job_id,
            &worker_id,
            &job.payload_hash,
            &operation_json,
            mode,
        ))?;
        Ok(Self {
            plan_id: EventId::new(),
            backend: boundary.backend,
            mode,
            job_id: job.job_id,
            worker_id,
            expected_payload_hash: job.payload_hash.clone(),
            operation_json,
            plan_hash,
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseExecutionReceipt {
    pub receipt_id: EventId,
    pub plan: DistributedLeaseExecutionPlan,
    pub adapter_report: DistributedLeaseAdapterReport,
    pub lease_receipt: DistributedLeaseClaimReceipt,
    pub accepted: bool,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub executed_at: OffsetDateTime,
}

impl DistributedLeaseExecutionReceipt {
    pub fn verify(&self) -> MindResult<()> {
        if self.plan.job_id != self.lease_receipt.job_id {
            return Err(MindError::Store(
                "distributed lease execution job mismatch".to_owned(),
            ));
        }
        if self.plan.expected_payload_hash != self.lease_receipt.expected_payload_hash {
            return Err(MindError::Store(
                "distributed lease execution payload hash mismatch".to_owned(),
            ));
        }
        if self.accepted && self.lease_receipt.status != DistributedLeaseClaimStatus::Granted {
            return Err(MindError::Store(
                "accepted lease execution without granted receipt".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn execute_distributed_lease_with_receipt(
    boundary: &DistributedLeaseServiceBoundary,
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    policy: &SchedulerLeasePolicy,
    registry: &DistributedLeaseAdapterRegistry,
    mode: DistributedLeaseExecutionMode,
) -> MindResult<DistributedLeaseExecutionReceipt> {
    let worker_id = worker_id.into();
    let plan = DistributedLeaseExecutionPlan::from_boundary(
        boundary,
        job,
        worker_id.clone(),
        policy,
        mode,
    )?;
    let adapter_report =
        evaluate_distributed_lease_adapter_claim(boundary, job, worker_id, policy, registry)?;
    let accepted = adapter_report.accepted
        && adapter_report.receipt.status == DistributedLeaseClaimStatus::Granted;
    let mut reasons = adapter_report.reasons.clone();
    reasons.push(format!("execution mode {:?}", mode));
    let receipt = DistributedLeaseExecutionReceipt {
        receipt_id: EventId::new(),
        plan,
        lease_receipt: adapter_report.receipt.clone(),
        adapter_report,
        accepted,
        reasons,
        executed_at: OffsetDateTime::now_utc(),
    };
    receipt.verify()?;
    Ok(receipt)
}
