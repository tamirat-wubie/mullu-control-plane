use crate::{
    claim_due_jobs_with_leases, EventId, MindError, MindResult, ScheduledJob, ScheduledJobKind,
    SchedulerLeasePolicy, SchedulerLeaseRecord,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WorkerRuntimeMode {
    PlanOnly,
    ExecuteAndMarkSucceeded,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum WorkerJobOutcome {
    Planned,
    Succeeded,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerRuntimeConfig {
    pub worker_id: String,
    pub lease_policy: SchedulerLeasePolicy,
    pub max_jobs_per_tick: usize,
    pub mode: WorkerRuntimeMode,
}

impl WorkerRuntimeConfig {
    pub fn new(worker_id: impl Into<String>) -> MindResult<Self> {
        let config = Self {
            worker_id: worker_id.into(),
            lease_policy: SchedulerLeasePolicy::default(),
            max_jobs_per_tick: 10,
            mode: WorkerRuntimeMode::PlanOnly,
        };
        config.validate()?;
        Ok(config)
    }

    #[must_use]
    pub fn with_mode(mut self, mode: WorkerRuntimeMode) -> Self {
        self.mode = mode;
        self
    }
    #[must_use]
    pub fn with_limit(mut self, max_jobs_per_tick: usize) -> Self {
        self.max_jobs_per_tick = max_jobs_per_tick;
        self
    }
    #[must_use]
    pub fn with_lease_policy(mut self, lease_policy: SchedulerLeasePolicy) -> Self {
        self.lease_policy = lease_policy;
        self
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.worker_id.trim().is_empty() {
            return Err(MindError::Store("worker id is required".to_owned()));
        }
        self.lease_policy.validate()?;
        if self.max_jobs_per_tick == 0 {
            return Err(MindError::Store(
                "worker max_jobs_per_tick must be greater than zero".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerJobExecution {
    pub job_id: EventId,
    pub kind: ScheduledJobKind,
    pub target: String,
    pub attempt: u32,
    pub outcome: WorkerJobOutcome,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    pub executed_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerRunReport {
    pub run_id: EventId,
    pub worker_id: String,
    pub mode: WorkerRuntimeMode,
    pub started_at: OffsetDateTime,
    pub finished_at: OffsetDateTime,
    pub claimed_count: usize,
    pub succeeded_count: usize,
    pub failed_count: usize,
    #[serde(default)]
    pub executions: Vec<WorkerJobExecution>,
    #[serde(default)]
    pub leases: Vec<SchedulerLeaseRecord>,
    #[serde(default)]
    pub updated_jobs: Vec<ScheduledJob>,
}

pub struct WorkerRuntime;

impl WorkerRuntime {
    pub fn run_once(
        jobs: &[ScheduledJob],
        config: &WorkerRuntimeConfig,
        now: OffsetDateTime,
    ) -> MindResult<WorkerRunReport> {
        config.validate()?;
        let claim_report = claim_due_jobs_with_leases(
            jobs,
            config.worker_id.clone(),
            &config.lease_policy,
            config.max_jobs_per_tick,
            now,
        )?;
        let mut updated_jobs = Vec::new();
        let mut executions = Vec::new();
        let mut succeeded_count = 0;
        for job in &claim_report.updated_jobs {
            let outcome = match config.mode {
                WorkerRuntimeMode::PlanOnly => WorkerJobOutcome::Planned,
                WorkerRuntimeMode::ExecuteAndMarkSucceeded => WorkerJobOutcome::Succeeded,
            };
            if outcome == WorkerJobOutcome::Succeeded {
                succeeded_count += 1;
                updated_jobs.push(job.mark_succeeded(now));
            } else {
                updated_jobs.push(job.clone());
            }
            executions.push(WorkerJobExecution {
                job_id: job.job_id,
                kind: job.kind,
                target: job.target.clone(),
                attempt: job.attempt_count,
                outcome,
                error: None,
                executed_at: now,
            });
        }
        Ok(WorkerRunReport {
            run_id: EventId::new(),
            worker_id: config.worker_id.clone(),
            mode: config.mode,
            started_at: now,
            finished_at: OffsetDateTime::now_utc(),
            claimed_count: claim_report.claimed_count,
            succeeded_count,
            failed_count: 0,
            executions,
            leases: claim_report.leases,
            updated_jobs,
        })
    }
}
