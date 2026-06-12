use crate::{
    execute_job_with_receipt, hash_serializable, EventId, JobExecutionHandlerKind,
    JobExecutionMode, JobExecutionReceipt, JobExecutionStatus, MindError, MindResult, ScheduledJob,
    ScheduledJobKind, SchedulerLeaseRecord,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DomainJobExecutionStatus {
    Planned,
    Executed,
    Rejected,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobHandlerBinding {
    pub kind: ScheduledJobKind,
    pub handler: JobExecutionHandlerKind,
    #[serde(default)]
    pub required_payload_keys: Vec<String>,
    #[serde(default)]
    pub required_evidence_keys: Vec<String>,
    pub local_execution_allowed: bool,
    pub provider_receipt_required: bool,
}

impl DomainJobHandlerBinding {
    #[must_use]
    pub fn new(
        kind: ScheduledJobKind,
        required_payload_keys: Vec<&str>,
        required_evidence_keys: Vec<&str>,
        local_execution_allowed: bool,
        provider_receipt_required: bool,
    ) -> Self {
        Self {
            kind,
            handler: JobExecutionHandlerKind::from(kind),
            required_payload_keys: required_payload_keys
                .into_iter()
                .map(str::to_owned)
                .collect(),
            required_evidence_keys: required_evidence_keys
                .into_iter()
                .map(str::to_owned)
                .collect(),
            local_execution_allowed,
            provider_receipt_required,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobExecutorRegistry {
    pub registry_id: EventId,
    #[serde(default)]
    pub handlers: Vec<DomainJobHandlerBinding>,
    pub generated_at: OffsetDateTime,
}

impl DomainJobExecutorRegistry {
    #[must_use]
    pub fn production_default() -> Self {
        Self {
            registry_id: EventId::new(),
            handlers: vec![
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::OidcJwksRefresh,
                    vec!["issuer", "audience"],
                    vec!["jwks_cache_entry", "issuer", "jwks_uri"],
                    true,
                    false,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::SigningExecution,
                    vec!["request_id", "payload_hash", "key_id"],
                    vec!["provider_receipt", "signature_hash"],
                    false,
                    true,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::CloudBackupUpload,
                    vec!["backup_id", "backup_hash", "target"],
                    vec!["upload_receipt", "content_hash"],
                    true,
                    true,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::ReplicationDelivery,
                    vec!["batch_id", "follower_id"],
                    vec!["delivery_receipt", "ack"],
                    true,
                    false,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::SnapshotCompaction,
                    vec!["mind_id", "policy"],
                    vec!["compaction_decision"],
                    true,
                    false,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::BackupVerification,
                    vec!["backup_id", "backup_hash"],
                    vec!["verification_report"],
                    true,
                    false,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::ConsensusCommit,
                    vec!["cluster_id", "entry_id", "entry_hash"],
                    vec!["commit_certificate", "quorum"],
                    true,
                    false,
                ),
                DomainJobHandlerBinding::new(
                    ScheduledJobKind::ProviderExecution,
                    vec!["execution_id", "payload_hash", "adapter"],
                    vec!["provider_execution_receipt"],
                    false,
                    true,
                ),
            ],
            generated_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn binding_for(&self, kind: ScheduledJobKind) -> Option<&DomainJobHandlerBinding> {
        self.handlers.iter().find(|binding| binding.kind == kind)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobExecutionPlan {
    pub plan_id: EventId,
    pub job_id: EventId,
    pub kind: ScheduledJobKind,
    pub handler: JobExecutionHandlerKind,
    pub target: String,
    pub payload_hash: String,
    pub payload_shape_hash: String,
    pub valid: bool,
    #[serde(default)]
    pub missing_payload_keys: Vec<String>,
    #[serde(default)]
    pub required_evidence_keys: Vec<String>,
    pub local_execution_allowed: bool,
    pub provider_receipt_required: bool,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobExecutionReport {
    pub report_id: EventId,
    pub plan_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub kind: ScheduledJobKind,
    pub handler: JobExecutionHandlerKind,
    pub status: DomainJobExecutionStatus,
    pub receipt: JobExecutionReceipt,
    #[serde(default)]
    pub produced_evidence_keys: Vec<String>,
    #[serde(default)]
    pub required_evidence_keys: Vec<String>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub executed_at: OffsetDateTime,
}

impl DomainJobExecutionReport {
    pub fn verify_for(&self, plan: &DomainJobExecutionPlan, job: &ScheduledJob) -> MindResult<()> {
        if self.plan_id != plan.plan_id || self.job_id != job.job_id || self.kind != job.kind {
            return Err(MindError::Store(
                "domain job execution report target mismatch".to_owned(),
            ));
        }
        if self.receipt.job_id != job.job_id
            || self.receipt.expected_payload_hash != job.payload_hash
        {
            return Err(MindError::Store(
                "domain job execution receipt mismatch".to_owned(),
            ));
        }
        let produced: BTreeSet<&str> = self
            .produced_evidence_keys
            .iter()
            .map(String::as_str)
            .collect();
        for key in &plan.required_evidence_keys {
            if self.status == DomainJobExecutionStatus::Executed && !produced.contains(key.as_str())
            {
                return Err(MindError::Store(format!(
                    "domain job execution missing evidence key `{key}`"
                )));
            }
        }
        Ok(())
    }
}

#[must_use]
pub fn domain_job_executor_registry() -> DomainJobExecutorRegistry {
    DomainJobExecutorRegistry::production_default()
}

pub fn plan_domain_job_execution(
    job: &ScheduledJob,
    registry: &DomainJobExecutorRegistry,
) -> MindResult<DomainJobExecutionPlan> {
    let binding = registry
        .binding_for(job.kind)
        .ok_or_else(|| MindError::Store("domain job handler is not registered".to_owned()))?;
    let payload: Value = serde_json::from_str(&job.payload_json)?;
    let present = payload_key_set(&payload);
    let mut missing_payload_keys = Vec::new();
    for key in &binding.required_payload_keys {
        if !present.contains(key) {
            missing_payload_keys.push(key.clone());
        }
    }
    let payload_shape_hash = hash_serializable(&present)?;
    let plan_hash = hash_serializable(&(
        job.job_id,
        job.kind,
        &job.target,
        &job.payload_hash,
        &payload_shape_hash,
        &missing_payload_keys,
        &binding.required_evidence_keys,
    ))?;
    Ok(DomainJobExecutionPlan {
        plan_id: EventId::new(),
        job_id: job.job_id,
        kind: job.kind,
        handler: binding.handler,
        target: job.target.clone(),
        payload_hash: job.payload_hash.clone(),
        payload_shape_hash,
        valid: missing_payload_keys.is_empty(),
        missing_payload_keys,
        required_evidence_keys: binding.required_evidence_keys.clone(),
        local_execution_allowed: binding.local_execution_allowed,
        provider_receipt_required: binding.provider_receipt_required,
        plan_hash,
        created_at: OffsetDateTime::now_utc(),
    })
}

pub fn execute_domain_job_with_receipt(
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    lease: Option<&SchedulerLeaseRecord>,
    mode: JobExecutionMode,
    registry: &DomainJobExecutorRegistry,
) -> MindResult<DomainJobExecutionReport> {
    let worker_id = worker_id.into();
    let plan = plan_domain_job_execution(job, registry)?;
    if !plan.valid {
        let mut receipt = JobExecutionReceipt::failed(
            job,
            worker_id.clone(),
            format!(
                "missing required payload keys: {}",
                plan.missing_payload_keys.join(",")
            ),
        );
        receipt
            .metadata
            .insert("domain_plan_id".to_owned(), plan.plan_id.to_string());
        receipt
            .metadata
            .insert("domain_plan_hash".to_owned(), plan.plan_hash.clone());
        return Ok(DomainJobExecutionReport {
            report_id: EventId::new(),
            plan_id: plan.plan_id,
            job_id: job.job_id,
            worker_id,
            kind: job.kind,
            handler: plan.handler,
            status: DomainJobExecutionStatus::Rejected,
            receipt,
            produced_evidence_keys: Vec::new(),
            required_evidence_keys: plan.required_evidence_keys,
            reasons: plan
                .missing_payload_keys
                .iter()
                .map(|key| format!("required payload key `{key}` is missing"))
                .collect(),
            executed_at: OffsetDateTime::now_utc(),
        });
    }
    if mode == JobExecutionMode::LocalExecutor && !plan.local_execution_allowed {
        return Err(MindError::Store(
            "domain job requires external/provider receipt and cannot use local executor"
                .to_owned(),
        ));
    }
    let mut receipt = execute_job_with_receipt(job, worker_id.clone(), lease, mode)?;
    receipt
        .metadata
        .insert("domain_plan_id".to_owned(), plan.plan_id.to_string());
    receipt
        .metadata
        .insert("domain_plan_hash".to_owned(), plan.plan_hash.clone());
    receipt.metadata.insert(
        "provider_receipt_required".to_owned(),
        plan.provider_receipt_required.to_string(),
    );
    let produced_evidence_keys = if receipt.status == JobExecutionStatus::Succeeded {
        plan.required_evidence_keys.clone()
    } else {
        Vec::new()
    };
    let status = match receipt.status {
        JobExecutionStatus::Planned => DomainJobExecutionStatus::Planned,
        JobExecutionStatus::Succeeded => DomainJobExecutionStatus::Executed,
        JobExecutionStatus::Failed => DomainJobExecutionStatus::Failed,
        JobExecutionStatus::Rejected => DomainJobExecutionStatus::Rejected,
    };
    let report = DomainJobExecutionReport {
        report_id: EventId::new(),
        plan_id: plan.plan_id,
        job_id: job.job_id,
        worker_id,
        kind: job.kind,
        handler: plan.handler,
        status,
        receipt,
        produced_evidence_keys,
        required_evidence_keys: plan.required_evidence_keys.clone(),
        reasons: if plan.provider_receipt_required {
            vec![
                "provider receipt must be attached before production success is trusted".to_owned(),
            ]
        } else {
            vec!["domain job receipt produced by registered handler".to_owned()]
        },
        executed_at: OffsetDateTime::now_utc(),
    };
    report.verify_for(&plan, job)?;
    Ok(report)
}

fn payload_key_set(value: &Value) -> BTreeSet<String> {
    match value {
        Value::Object(map) => map.keys().cloned().collect(),
        _ => BTreeSet::new(),
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobExecutionSummary {
    pub registry_id: EventId,
    pub planned_count: usize,
    pub executed_count: usize,
    pub rejected_count: usize,
    pub failed_count: usize,
    #[serde(default)]
    pub by_handler: BTreeMap<JobExecutionHandlerKind, usize>,
}

#[must_use]
pub fn summarize_domain_job_reports(
    registry: &DomainJobExecutorRegistry,
    reports: &[DomainJobExecutionReport],
) -> DomainJobExecutionSummary {
    let mut by_handler = BTreeMap::new();
    let mut planned_count = 0;
    let mut executed_count = 0;
    let mut rejected_count = 0;
    let mut failed_count = 0;
    for report in reports {
        *by_handler.entry(report.handler).or_insert(0) += 1;
        match report.status {
            DomainJobExecutionStatus::Planned => planned_count += 1,
            DomainJobExecutionStatus::Executed => executed_count += 1,
            DomainJobExecutionStatus::Rejected => rejected_count += 1,
            DomainJobExecutionStatus::Failed => failed_count += 1,
        }
    }
    DomainJobExecutionSummary {
        registry_id: registry.registry_id,
        planned_count,
        executed_count,
        rejected_count,
        failed_count,
        by_handler,
    }
}
