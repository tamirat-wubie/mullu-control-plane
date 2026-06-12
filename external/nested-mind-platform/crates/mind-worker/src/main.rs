use mind_core::{
    execute_live_domain_job, live_domain_job_executor_registry, JobExecutionMode,
    LiveDomainJobExecutorMode, MindResult, SchedulerLeasePolicy, WorkerDaemonConfig,
    WorkerDaemonRunSummary, WorkerDaemonTickReport, WorkerRuntimeMode,
};
use mind_store_sqlite::SqliteEventStore;
use std::{env, process};
use time::OffsetDateTime;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    init_tracing();
    if let Err(error) = run_worker().await {
        eprintln!("{error}");
        process::exit(1);
    }
}

async fn run_worker() -> MindResult<()> {
    let db_path =
        env::var("MIND_EVENT_DB").unwrap_or_else(|_| "./data/mind-events.sqlite".to_owned());
    let mut store = SqliteEventStore::open(db_path)?;
    let config = config_from_env()?;
    let max_ticks = env_u64("MIND_WORKER_MAX_TICKS", 1);
    let mut ticks = Vec::new();
    let mut idle_ticks = 0_u32;
    let mut tick_index = 0_u64;

    loop {
        let report = run_tick(&mut store, &config, tick_index)?;
        if report.idle() {
            idle_ticks = idle_ticks.saturating_add(1);
        } else {
            idle_ticks = 0;
        }
        tracing::info!(
            worker_id = %report.worker_id,
            tick_index = report.tick_index,
            claimed = report.claimed_count,
            succeeded = report.succeeded_count,
            "worker_tick_completed"
        );
        ticks.push(report);
        tick_index = tick_index.saturating_add(1);

        if max_ticks > 0 && tick_index >= max_ticks {
            break;
        }
        if config.stop_after_idle_ticks > 0 && idle_ticks >= config.stop_after_idle_ticks {
            break;
        }
        sleep(Duration::from_millis(config.tick_interval_ms)).await;
    }

    let summary = WorkerDaemonRunSummary::from_ticks(&config, ticks);
    println!("{}", serde_json::to_string_pretty(&summary)?);
    Ok(())
}

fn run_tick(
    store: &mut SqliteEventStore,
    config: &WorkerDaemonConfig,
    tick_index: u64,
) -> MindResult<WorkerDaemonTickReport> {
    let now = OffsetDateTime::now_utc();
    let claim_report = store.claim_due_jobs_for_worker(
        config.worker_id.clone(),
        &config.lease_policy,
        config.max_jobs_per_tick,
        now,
    )?;
    let report = WorkerDaemonTickReport::from_claim_report(config, tick_index, claim_report, now)?;
    let receipt_mode = match config.mode {
        WorkerRuntimeMode::PlanOnly => JobExecutionMode::PlanOnly,
        WorkerRuntimeMode::ExecuteAndMarkSucceeded => JobExecutionMode::LocalExecutor,
    };
    for job in &report.claim_report.updated_jobs {
        let lease = report
            .claim_report
            .leases
            .iter()
            .find(|lease| lease.job_id == job.job_id);
        let registry = live_domain_job_executor_registry();
        let live_mode = match receipt_mode {
            JobExecutionMode::PlanOnly => LiveDomainJobExecutorMode::PlanOnly,
            JobExecutionMode::ReceiptOnly => LiveDomainJobExecutorMode::ReceiptOnly,
            JobExecutionMode::LocalExecutor => LiveDomainJobExecutorMode::LocalSimulation,
        };
        let report =
            execute_live_domain_job(job, &config.worker_id, lease, Some(live_mode), &registry)?;
        store.record_job_execution_receipt(&report.domain_report.receipt)?;
        store.record_domain_job_execution_report(&report.domain_report)?;
        store.record_live_domain_job_execution_report(&report)?;
    }
    for job in &report.updated_jobs {
        store.record_scheduled_job(job)?;
    }
    store.record_worker_daemon_tick(&report)?;
    Ok(report)
}

fn config_from_env() -> MindResult<WorkerDaemonConfig> {
    let worker_id = env::var("MIND_WORKER_ID").unwrap_or_else(|_| "worker-local".to_owned());
    let mode = match env::var("MIND_WORKER_MODE")
        .unwrap_or_else(|_| "plan".to_owned())
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "execute" | "execute_and_mark_succeeded" => WorkerRuntimeMode::ExecuteAndMarkSucceeded,
        _ => WorkerRuntimeMode::PlanOnly,
    };
    let mut lease_policy = SchedulerLeasePolicy::default();
    lease_policy.lease_seconds = env_u64("MIND_WORKER_LEASE_SECONDS", lease_policy.lease_seconds);
    lease_policy.max_claims_per_poll = env_usize(
        "MIND_WORKER_MAX_JOBS_PER_TICK",
        lease_policy.max_claims_per_poll,
    );
    let config = WorkerDaemonConfig::new(worker_id)?
        .with_mode(mode)
        .with_lease_policy(lease_policy)
        .with_max_jobs_per_tick(env_usize("MIND_WORKER_MAX_JOBS_PER_TICK", 10))
        .with_tick_interval_ms(env_u64("MIND_WORKER_TICK_INTERVAL_MS", 1_000))
        .with_stop_after_idle_ticks(env_u32("MIND_WORKER_STOP_AFTER_IDLE_TICKS", 0));
    config.validate()?;
    Ok(config)
}

fn env_u64(name: &str, default: u64) -> u64 {
    env::var(name)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(default)
}

fn env_u32(name: &str, default: u32) -> u32 {
    env::var(name)
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(default)
}

fn env_usize(name: &str, default: usize) -> usize {
    env::var(name)
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(default)
}

fn init_tracing() {
    let level = env::var("MIND_WORKER_LOG_LEVEL").unwrap_or_else(|_| "mind_worker=info".to_owned());
    let filter = tracing_subscriber::EnvFilter::new(level);
    let _ = tracing_subscriber::fmt().with_env_filter(filter).try_init();
}
