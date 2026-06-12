use crate::{
    EventId, MindError, MindResult, ScheduledJob, SchedulerLeaseClaimReport, SchedulerLeasePolicy,
    WorkerRuntimeMode,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerDaemonConfig {
    pub worker_id: String,
    pub mode: WorkerRuntimeMode,
    pub lease_policy: SchedulerLeasePolicy,
    pub max_jobs_per_tick: usize,
    pub tick_interval_ms: u64,
    pub stop_after_idle_ticks: u32,
}

impl WorkerDaemonConfig {
    pub fn new(worker_id: impl Into<String>) -> MindResult<Self> {
        let config = Self {
            worker_id: worker_id.into(),
            mode: WorkerRuntimeMode::PlanOnly,
            lease_policy: SchedulerLeasePolicy::default(),
            max_jobs_per_tick: 10,
            tick_interval_ms: 1_000,
            stop_after_idle_ticks: 0,
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
    pub fn with_lease_policy(mut self, lease_policy: SchedulerLeasePolicy) -> Self {
        self.lease_policy = lease_policy;
        self
    }

    #[must_use]
    pub fn with_max_jobs_per_tick(mut self, max_jobs_per_tick: usize) -> Self {
        self.max_jobs_per_tick = max_jobs_per_tick;
        self
    }

    #[must_use]
    pub fn with_tick_interval_ms(mut self, tick_interval_ms: u64) -> Self {
        self.tick_interval_ms = tick_interval_ms;
        self
    }

    #[must_use]
    pub fn with_stop_after_idle_ticks(mut self, stop_after_idle_ticks: u32) -> Self {
        self.stop_after_idle_ticks = stop_after_idle_ticks;
        self
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.worker_id.trim().is_empty() {
            return Err(MindError::Store("worker daemon id is required".to_owned()));
        }
        self.lease_policy.validate()?;
        if self.max_jobs_per_tick == 0 {
            return Err(MindError::Store(
                "worker daemon max_jobs_per_tick must be greater than zero".to_owned(),
            ));
        }
        if self.tick_interval_ms == 0 {
            return Err(MindError::Store(
                "worker daemon tick_interval_ms must be greater than zero".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerDaemonTickReport {
    pub tick_id: EventId,
    pub worker_id: String,
    pub tick_index: u64,
    pub mode: WorkerRuntimeMode,
    pub claimed_count: usize,
    pub succeeded_count: usize,
    pub failed_count: usize,
    pub planned_count: usize,
    #[serde(default)]
    pub updated_jobs: Vec<ScheduledJob>,
    pub claim_report: SchedulerLeaseClaimReport,
    pub started_at: OffsetDateTime,
    pub finished_at: OffsetDateTime,
    pub next_tick_after_ms: u64,
}

impl WorkerDaemonTickReport {
    pub fn from_claim_report(
        config: &WorkerDaemonConfig,
        tick_index: u64,
        claim_report: SchedulerLeaseClaimReport,
        now: OffsetDateTime,
    ) -> MindResult<Self> {
        config.validate()?;
        if claim_report.worker_id != config.worker_id {
            return Err(MindError::Store(
                "worker daemon claim report belongs to another worker".to_owned(),
            ));
        }
        let mut updated_jobs = Vec::with_capacity(claim_report.updated_jobs.len());
        let mut succeeded_count = 0;
        let mut planned_count = 0;
        for job in &claim_report.updated_jobs {
            match config.mode {
                WorkerRuntimeMode::PlanOnly => {
                    planned_count += 1;
                    updated_jobs.push(job.clone());
                }
                WorkerRuntimeMode::ExecuteAndMarkSucceeded => {
                    succeeded_count += 1;
                    updated_jobs.push(job.mark_succeeded(now));
                }
            }
        }
        Ok(Self {
            tick_id: EventId::new(),
            worker_id: config.worker_id.clone(),
            tick_index,
            mode: config.mode,
            claimed_count: claim_report.claimed_count,
            succeeded_count,
            failed_count: 0,
            planned_count,
            updated_jobs,
            claim_report,
            started_at: now,
            finished_at: OffsetDateTime::now_utc(),
            next_tick_after_ms: config.tick_interval_ms,
        })
    }

    #[must_use]
    pub fn idle(&self) -> bool {
        self.claimed_count == 0
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkerDaemonRunSummary {
    pub run_id: EventId,
    pub worker_id: String,
    pub tick_count: u64,
    pub claimed_count: usize,
    pub succeeded_count: usize,
    pub failed_count: usize,
    pub stopped_after_idle: bool,
    #[serde(default)]
    pub ticks: Vec<WorkerDaemonTickReport>,
    pub started_at: OffsetDateTime,
    pub finished_at: OffsetDateTime,
}

impl WorkerDaemonRunSummary {
    #[must_use]
    pub fn from_ticks(config: &WorkerDaemonConfig, ticks: Vec<WorkerDaemonTickReport>) -> Self {
        let started_at = ticks
            .first()
            .map_or_else(OffsetDateTime::now_utc, |tick| tick.started_at);
        let finished_at = ticks
            .last()
            .map_or_else(OffsetDateTime::now_utc, |tick| tick.finished_at);
        let claimed_count = ticks.iter().map(|tick| tick.claimed_count).sum();
        let succeeded_count = ticks.iter().map(|tick| tick.succeeded_count).sum();
        let failed_count = ticks.iter().map(|tick| tick.failed_count).sum();
        let stopped_after_idle = config.stop_after_idle_ticks > 0
            && ticks
                .iter()
                .rev()
                .take(config.stop_after_idle_ticks as usize)
                .all(WorkerDaemonTickReport::idle);
        Self {
            run_id: EventId::new(),
            worker_id: config.worker_id.clone(),
            tick_count: ticks.len() as u64,
            claimed_count,
            succeeded_count,
            failed_count,
            stopped_after_idle,
            ticks,
            started_at,
            finished_at,
        }
    }
}
