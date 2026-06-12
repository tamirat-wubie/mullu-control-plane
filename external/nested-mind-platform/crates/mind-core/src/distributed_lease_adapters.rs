use crate::{
    plan_external_distributed_lease_claim, DistributedLeaseBackendKind,
    DistributedLeaseClaimReceipt, DistributedLeaseClaimRequest, DistributedLeaseClaimStatus,
    DistributedLeaseServiceBoundary, EventId, MindError, MindResult, ScheduledJob,
    SchedulerLeasePolicy,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DistributedLeaseAdapterMode {
    LocalCompareAndSwap,
    NativeClient,
    ExternalGateway,
    Disabled,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseAdapterCapability {
    pub backend: DistributedLeaseBackendKind,
    pub mode: DistributedLeaseAdapterMode,
    pub fencing_tokens_supported: bool,
    pub compare_and_swap_supported: bool,
    pub production_ready: bool,
    #[serde(default)]
    pub required_environment: Vec<String>,
    #[serde(default)]
    pub reasons: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseAdapterRegistry {
    pub registry_id: EventId,
    #[serde(default)]
    pub capabilities: Vec<DistributedLeaseAdapterCapability>,
    pub generated_at: OffsetDateTime,
}

impl DistributedLeaseAdapterRegistry {
    #[must_use]
    pub fn production_default() -> Self {
        use DistributedLeaseAdapterMode::{
            Disabled, ExternalGateway, LocalCompareAndSwap, NativeClient,
        };
        Self {
            registry_id: EventId::new(),
            capabilities: vec![
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::SqliteCompareAndSwap,
                    mode: LocalCompareAndSwap,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: true,
                    production_ready: true,
                    required_environment: vec!["MIND_EVENT_DB".to_owned()],
                    reasons: vec!["SQLite compare-and-swap claim path is implemented locally".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::PostgresAdvisoryLock,
                    mode: NativeClient,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: true,
                    production_ready: false,
                    required_environment: vec!["DATABASE_URL".to_owned()],
                    reasons: vec!["Postgres adapter boundary defined; native client implementation pending".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::RedisRedlock,
                    mode: NativeClient,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: false,
                    production_ready: false,
                    required_environment: vec!["REDIS_URL".to_owned()],
                    reasons: vec!["Redis Redlock adapter boundary defined; production safety review required".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::EtcdLease,
                    mode: NativeClient,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: true,
                    production_ready: false,
                    required_environment: vec!["ETCD_ENDPOINTS".to_owned()],
                    reasons: vec!["etcd lease adapter boundary defined; native client implementation pending".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::ConsulSession,
                    mode: NativeClient,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: true,
                    production_ready: false,
                    required_environment: vec!["CONSUL_HTTP_ADDR".to_owned()],
                    reasons: vec!["Consul session adapter boundary defined; native client implementation pending".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::ExternalHttpGateway,
                    mode: ExternalGateway,
                    fencing_tokens_supported: true,
                    compare_and_swap_supported: true,
                    production_ready: false,
                    required_environment: vec!["MIND_LEASE_GATEWAY_URL".to_owned()],
                    reasons: vec!["external lease gateway must return hash-bound receipts".to_owned()],
                },
                DistributedLeaseAdapterCapability {
                    backend: DistributedLeaseBackendKind::PostgresAdvisoryLock,
                    mode: Disabled,
                    fencing_tokens_supported: false,
                    compare_and_swap_supported: false,
                    production_ready: false,
                    required_environment: Vec::new(),
                    reasons: vec!["disabled fallback marker; enabled capability must be explicit".to_owned()],
                },
            ],
            generated_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn capability_for(
        &self,
        backend: DistributedLeaseBackendKind,
    ) -> Option<&DistributedLeaseAdapterCapability> {
        self.capabilities.iter().find(|capability| {
            capability.backend == backend
                && capability.mode != DistributedLeaseAdapterMode::Disabled
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DistributedLeaseAdapterReport {
    pub report_id: EventId,
    pub backend: DistributedLeaseBackendKind,
    pub mode: DistributedLeaseAdapterMode,
    pub request_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub accepted: bool,
    pub receipt: DistributedLeaseClaimReceipt,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub evaluated_at: OffsetDateTime,
}

#[must_use]
pub fn distributed_lease_adapter_registry() -> DistributedLeaseAdapterRegistry {
    DistributedLeaseAdapterRegistry::production_default()
}

pub fn evaluate_distributed_lease_adapter_claim(
    boundary: &DistributedLeaseServiceBoundary,
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    policy: &SchedulerLeasePolicy,
    registry: &DistributedLeaseAdapterRegistry,
) -> MindResult<DistributedLeaseAdapterReport> {
    let worker_id = worker_id.into();
    let plan = plan_external_distributed_lease_claim(boundary, job, worker_id, policy)?;
    let capability = registry.capability_for(boundary.backend);
    let (mode, accepted, receipt, mut reasons) = match capability {
        Some(capability)
            if capability.mode == DistributedLeaseAdapterMode::LocalCompareAndSwap
                || capability.mode == DistributedLeaseAdapterMode::ExternalGateway
                || capability.production_ready =>
        {
            let receipt = DistributedLeaseClaimReceipt::granted(boundary, &plan.request);
            (capability.mode, true, receipt, capability.reasons.clone())
        }
        Some(capability) => {
            let receipt = rejected_receipt(
                boundary,
                &plan.request,
                "distributed lease adapter is configured but not production ready",
            );
            (capability.mode, false, receipt, capability.reasons.clone())
        }
        None => {
            let receipt = rejected_receipt(
                boundary,
                &plan.request,
                "distributed lease adapter backend is not registered",
            );
            (
                DistributedLeaseAdapterMode::Disabled,
                false,
                receipt,
                vec!["backend has no enabled adapter capability".to_owned()],
            )
        }
    };
    if boundary.fencing_tokens_required && receipt.fencing_token.is_none() && accepted {
        return Err(MindError::Store(
            "distributed lease receipt missing required fencing token".to_owned(),
        ));
    }
    receipt.verify_for(&plan.request)?;
    if !accepted && reasons.is_empty() {
        reasons.push("lease claim rejected by adapter capability".to_owned());
    }
    Ok(DistributedLeaseAdapterReport {
        report_id: EventId::new(),
        backend: boundary.backend,
        mode,
        request_id: plan.request.request_id,
        job_id: plan.request.job_id,
        worker_id: plan.request.worker_id,
        accepted,
        receipt,
        reasons,
        evaluated_at: OffsetDateTime::now_utc(),
    })
}

fn rejected_receipt(
    boundary: &DistributedLeaseServiceBoundary,
    request: &DistributedLeaseClaimRequest,
    reason: &str,
) -> DistributedLeaseClaimReceipt {
    let mut receipt = DistributedLeaseClaimReceipt::rejected(boundary, request, reason.to_owned());
    receipt.status = DistributedLeaseClaimStatus::Rejected;
    receipt
}
