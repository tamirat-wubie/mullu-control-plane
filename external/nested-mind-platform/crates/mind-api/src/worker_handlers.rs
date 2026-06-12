//! Purpose: worker and domain-job handlers for the Nested Mind API.
//! Governance scope: administrative worker runs, daemon ticks, execution receipts, and domain-job execution endpoints.
//! Dependencies: API state, scheduler lease policy helpers, worker runtime contracts, domain job registries, and audit/event stores.
//! Invariants: worker authorization, lease updates, receipt persistence, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_worker_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WorkerRunReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.worker_run_reports()?))
}

pub(super) async fn system_worker_run_once(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WorkerRunRequest>,
) -> Result<Json<WorkerRunReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mode = if request.execute_and_mark_succeeded {
        WorkerRuntimeMode::ExecuteAndMarkSucceeded
    } else {
        WorkerRuntimeMode::PlanOnly
    };
    let policy = scheduler_lease_policy(request.lease_seconds, request.limit)?;
    let config = WorkerRuntimeConfig::new(request.worker_id)?
        .with_limit(request.limit.max(1))
        .with_lease_policy(policy)
        .with_mode(mode);
    let now = OffsetDateTime::now_utc();
    let jobs = state.store.read().await.scheduled_jobs()?;
    let report = WorkerRuntime::run_once(&jobs, &config, now)?;
    {
        let mut store = state.store.write().await;
        for job in &report.updated_jobs {
            store.record_scheduled_job(job)?;
        }
        for lease in &report.leases {
            store.record_scheduler_lease(lease)?;
        }
        store.record_worker_run_report(&report)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "worker run recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("worker_id", report.worker_id.clone())
        .with_attribute("claimed_count", report.claimed_count.to_string())
        .with_attribute("succeeded_count", report.succeeded_count.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_worker_daemon_ticks(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WorkerDaemonTickReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.worker_daemon_ticks()?))
}

pub(super) async fn system_worker_tick(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WorkerTickRequest>,
) -> Result<Json<WorkerDaemonTickReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mode = if request.execute_and_mark_succeeded {
        WorkerRuntimeMode::ExecuteAndMarkSucceeded
    } else {
        WorkerRuntimeMode::PlanOnly
    };
    let policy = scheduler_lease_policy(request.lease_seconds, request.limit)?;
    let config = WorkerDaemonConfig::new(request.worker_id.clone())?
        .with_mode(mode)
        .with_lease_policy(policy)
        .with_max_jobs_per_tick(request.limit.max(1));
    let now = OffsetDateTime::now_utc();
    let tick = {
        let mut store = state.store.write().await;
        let claim_report = store.claim_due_jobs_for_worker(
            request.worker_id,
            &config.lease_policy,
            config.max_jobs_per_tick,
            now,
        )?;
        let tick = WorkerDaemonTickReport::from_claim_report(
            &config,
            request.tick_index.unwrap_or(0),
            claim_report,
            now,
        )?;
        let receipt_mode = if request.execute_and_mark_succeeded {
            JobExecutionMode::LocalExecutor
        } else {
            JobExecutionMode::PlanOnly
        };
        for job in &tick.claim_report.updated_jobs {
            let lease = tick
                .claim_report
                .leases
                .iter()
                .find(|lease| lease.job_id == job.job_id);
            let registry = domain_job_executor_registry();
            let report = execute_domain_job_with_receipt(
                job,
                &tick.worker_id,
                lease,
                receipt_mode,
                &registry,
            )?;
            store.record_job_execution_receipt(&report.receipt)?;
            store.record_domain_job_execution_report(&report)?;
        }
        for job in &tick.updated_jobs {
            store.record_scheduled_job(job)?;
        }
        store.record_worker_daemon_tick(&tick)?;
        tick
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "worker daemon tick recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("worker_id", tick.worker_id.clone())
        .with_attribute("claimed_count", tick.claimed_count.to_string())
        .with_attribute("succeeded_count", tick.succeeded_count.to_string()),
    );
    Ok(Json(tick))
}

pub(super) async fn system_worker_job_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<JobExecutionReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.job_execution_receipts()?))
}

pub(super) async fn system_worker_job_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<JobExecutionReceiptRequest>,
) -> Result<Json<JobExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mode = if request.execute_and_mark_succeeded {
        JobExecutionMode::LocalExecutor
    } else {
        JobExecutionMode::PlanOnly
    };
    let receipt = execute_job_with_receipt(
        &request.job,
        request.worker_id,
        request.lease.as_ref(),
        mode,
    )?;
    state
        .store
        .write()
        .await
        .record_job_execution_receipt(&receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "job execution receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", receipt.job_id.to_string())
        .with_attribute("receipt_id", receipt.receipt_id.to_string())
        .with_attribute("status", format!("{:?}", receipt.status)),
    );
    Ok(Json(receipt))
}

pub(super) async fn system_worker_domain_job_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<DomainJobExecutionReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.domain_job_execution_reports()?,
    ))
}

pub(super) async fn system_worker_domain_job_execute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<DomainJobExecutionRequest>,
) -> Result<Json<DomainJobExecutionReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let mode = if request.execute_and_mark_succeeded {
        JobExecutionMode::LocalExecutor
    } else {
        JobExecutionMode::PlanOnly
    };
    let registry = domain_job_executor_registry();
    let report = execute_domain_job_with_receipt(
        &request.job,
        request.worker_id,
        request.lease.as_ref(),
        mode,
        &registry,
    )?;
    {
        let mut store = state.store.write().await;
        store.record_job_execution_receipt(&report.receipt)?;
        store.record_domain_job_execution_report(&report)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "domain job execution report recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", report.job_id.to_string())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute("handler", format!("{:?}", report.handler)),
    );
    Ok(Json(report))
}

pub(super) async fn system_worker_live_domain_job_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<LiveDomainJobExecutionReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .live_domain_job_execution_reports()?,
    ))
}

pub(super) async fn system_worker_live_domain_job_execute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LiveDomainJobExecutionRequest>,
) -> Result<Json<LiveDomainJobExecutionReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let registry = live_domain_job_executor_registry();
    let report = execute_live_domain_job(
        &request.job,
        request.worker_id,
        request.lease.as_ref(),
        request.mode,
        &registry,
    )?;
    {
        let mut store = state.store.write().await;
        store.record_job_execution_receipt(&report.domain_report.receipt)?;
        store.record_domain_job_execution_report(&report.domain_report)?;
        store.record_live_domain_job_execution_report(&report)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "live domain job execution report recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", report.job_id.to_string())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute("evidence_count", report.evidence.len().to_string()),
    );
    Ok(Json(report))
}
