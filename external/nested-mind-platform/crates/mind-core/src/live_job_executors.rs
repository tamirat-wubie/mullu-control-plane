use crate::{
    domain_job_executor_registry, execute_domain_job_with_receipt, hash_serializable,
    DomainJobExecutionReport, DomainJobExecutionStatus, DomainJobExecutorRegistry, EventId,
    JobExecutionMode, MindResult, ScheduledJob, ScheduledJobKind, SchedulerLeaseRecord,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum LiveDomainJobExecutorMode {
    PlanOnly,
    LocalSimulation,
    ReceiptOnly,
}

impl LiveDomainJobExecutorMode {
    #[must_use]
    pub fn to_job_execution_mode(self) -> JobExecutionMode {
        match self {
            Self::PlanOnly => JobExecutionMode::PlanOnly,
            Self::LocalSimulation => JobExecutionMode::LocalExecutor,
            Self::ReceiptOnly => JobExecutionMode::ReceiptOnly,
        }
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum LiveDomainJobExecutionStatus {
    Planned,
    Executed,
    Rejected,
    Failed,
}

impl From<DomainJobExecutionStatus> for LiveDomainJobExecutionStatus {
    fn from(status: DomainJobExecutionStatus) -> Self {
        match status {
            DomainJobExecutionStatus::Planned => Self::Planned,
            DomainJobExecutionStatus::Executed => Self::Executed,
            DomainJobExecutionStatus::Rejected => Self::Rejected,
            DomainJobExecutionStatus::Failed => Self::Failed,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DomainJobEvidenceRecord {
    pub evidence_id: EventId,
    pub job_id: EventId,
    pub evidence_key: String,
    pub evidence_hash: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub produced_at: OffsetDateTime,
}

impl DomainJobEvidenceRecord {
    pub fn from_report(
        report: &DomainJobExecutionReport,
        evidence_key: impl Into<String>,
    ) -> MindResult<Self> {
        let evidence_key = evidence_key.into();
        let evidence_hash = hash_serializable(&(
            report.report_id,
            report.job_id,
            &report.receipt.evidence_hash,
            &evidence_key,
            &report.receipt.expected_payload_hash,
        ))?;
        let mut metadata = BTreeMap::new();
        metadata.insert("domain_report_id".to_owned(), report.report_id.to_string());
        metadata.insert(
            "receipt_id".to_owned(),
            report.receipt.receipt_id.to_string(),
        );
        Ok(Self {
            evidence_id: EventId::new(),
            job_id: report.job_id,
            evidence_key,
            evidence_hash,
            metadata,
            produced_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveDomainJobExecutorBinding {
    pub kind: ScheduledJobKind,
    pub executor_id: String,
    pub mode: LiveDomainJobExecutorMode,
    pub side_effect_boundary: String,
    pub receipts_required: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveDomainJobExecutorRegistry {
    pub registry_id: EventId,
    pub domain_registry: DomainJobExecutorRegistry,
    #[serde(default)]
    pub bindings: Vec<LiveDomainJobExecutorBinding>,
    pub generated_at: OffsetDateTime,
}

impl LiveDomainJobExecutorRegistry {
    #[must_use]
    pub fn production_default() -> Self {
        let domain_registry = domain_job_executor_registry();
        let bindings = domain_registry
            .handlers
            .iter()
            .map(|handler| LiveDomainJobExecutorBinding {
                kind: handler.kind,
                executor_id: format!("{:?}-executor", handler.handler).to_ascii_lowercase(),
                mode: if handler.provider_receipt_required {
                    LiveDomainJobExecutorMode::ReceiptOnly
                } else {
                    LiveDomainJobExecutorMode::LocalSimulation
                },
                side_effect_boundary: if handler.provider_receipt_required {
                    "provider-receipt-boundary".to_owned()
                } else {
                    "local-deterministic-simulation".to_owned()
                },
                receipts_required: handler.provider_receipt_required,
            })
            .collect();
        Self {
            registry_id: EventId::new(),
            domain_registry,
            bindings,
            generated_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn binding_for(&self, kind: ScheduledJobKind) -> Option<&LiveDomainJobExecutorBinding> {
        self.bindings.iter().find(|binding| binding.kind == kind)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveDomainJobExecutionReport {
    pub report_id: EventId,
    pub registry_id: EventId,
    pub job_id: EventId,
    pub worker_id: String,
    pub kind: ScheduledJobKind,
    pub status: LiveDomainJobExecutionStatus,
    pub mode: LiveDomainJobExecutorMode,
    pub domain_report: DomainJobExecutionReport,
    #[serde(default)]
    pub evidence: Vec<DomainJobEvidenceRecord>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub executed_at: OffsetDateTime,
}

impl LiveDomainJobExecutionReport {
    pub fn verify_for(&self, job: &ScheduledJob) -> MindResult<()> {
        if self.job_id != job.job_id || self.kind != job.kind {
            return Err(crate::MindError::Store(
                "live domain job report target mismatch".to_owned(),
            ));
        }
        self.domain_report.receipt.verify_for(job, None)?;
        for evidence in &self.evidence {
            if evidence.job_id != job.job_id {
                return Err(crate::MindError::Store(
                    "live domain job evidence target mismatch".to_owned(),
                ));
            }
        }
        Ok(())
    }
}

#[must_use]
pub fn live_domain_job_executor_registry() -> LiveDomainJobExecutorRegistry {
    LiveDomainJobExecutorRegistry::production_default()
}

pub fn execute_live_domain_job(
    job: &ScheduledJob,
    worker_id: impl Into<String>,
    lease: Option<&SchedulerLeaseRecord>,
    requested_mode: Option<LiveDomainJobExecutorMode>,
    registry: &LiveDomainJobExecutorRegistry,
) -> MindResult<LiveDomainJobExecutionReport> {
    let worker_id = worker_id.into();
    let binding = registry.binding_for(job.kind);
    let mode = requested_mode
        .or_else(|| binding.map(|binding| binding.mode))
        .unwrap_or(LiveDomainJobExecutorMode::PlanOnly);
    let domain_report = execute_domain_job_with_receipt(
        job,
        worker_id.clone(),
        lease,
        mode.to_job_execution_mode(),
        &registry.domain_registry,
    )?;
    let mut evidence = Vec::new();
    if domain_report.status == DomainJobExecutionStatus::Executed {
        for key in &domain_report.produced_evidence_keys {
            evidence.push(DomainJobEvidenceRecord::from_report(
                &domain_report,
                key.clone(),
            )?);
        }
    }
    let mut reasons = domain_report.reasons.clone();
    if let Some(binding) = binding {
        reasons.push(format!(
            "executor boundary: {}",
            binding.side_effect_boundary
        ));
    }
    let report = LiveDomainJobExecutionReport {
        report_id: EventId::new(),
        registry_id: registry.registry_id,
        job_id: job.job_id,
        worker_id,
        kind: job.kind,
        status: LiveDomainJobExecutionStatus::from(domain_report.status),
        mode,
        domain_report,
        evidence,
        reasons,
        executed_at: OffsetDateTime::now_utc(),
    };
    report.verify_for(job)?;
    Ok(report)
}
