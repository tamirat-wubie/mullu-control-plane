//! Purpose: scheduler and distributed lease handlers for the Nested Mind API.
//! Governance scope: administrative scheduling, lease claim, adapter evaluation, and lease execution endpoints.
//! Dependencies: API state, scheduler lease policy helpers, distributed lease adapters, and audit/event stores.
//! Invariants: scheduler authorization, lease persistence, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_scheduler_jobs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ScheduledJob>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.scheduled_jobs()?))
}

pub(super) async fn schedule_system_job(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ScheduleJobRequest>,
) -> Result<Json<ScheduledJob>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let due_at = OffsetDateTime::now_utc() + Duration::seconds(request.due_in_seconds as i64);
    let job = ScheduledJob::new(
        request.kind,
        request.target,
        &request.payload,
        due_at,
        request.max_attempts,
    )?;
    state.store.write().await.record_scheduled_job(&job)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "scheduler job recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", job.job_id.to_string())
        .with_attribute("kind", format!("{:?}", job.kind)),
    );
    Ok(Json(job))
}

pub(super) async fn system_scheduler_due_jobs(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<DueJobsRequest>,
) -> Result<Json<SchedulerPollReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let now = OffsetDateTime::now_utc();
    let jobs = state
        .store
        .read()
        .await
        .scheduled_jobs()?
        .into_iter()
        .filter(|job| job.is_due_at(now))
        .take(request.limit.max(1))
        .collect::<Vec<_>>();
    Ok(Json(SchedulerPollReport::from_jobs(now, jobs)))
}

pub(super) async fn system_scheduler_leases(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<SchedulerLeaseRecord>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.scheduler_leases()?))
}

pub(super) async fn system_scheduler_claim_jobs(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<SchedulerClaimRequest>,
) -> Result<Json<SchedulerLeaseClaimReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let now = OffsetDateTime::now_utc();
    let policy = scheduler_lease_policy(request.lease_seconds, request.limit)?;
    let jobs = state.store.read().await.scheduled_jobs()?;
    let report = mind_core::claim_due_jobs_with_leases(
        &jobs,
        request.worker_id,
        &policy,
        request.limit,
        now,
    )?;
    {
        let mut store = state.store.write().await;
        for job in &report.updated_jobs {
            store.record_scheduled_job(job)?;
        }
        for lease in &report.leases {
            store.record_scheduler_lease(lease)?;
        }
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "scheduler jobs claimed with leases",
        )
        .with_mind_id(root_id)
        .with_attribute("worker_id", report.worker_id.clone())
        .with_attribute("claimed_count", report.claimed_count.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_distributed_lease_boundary(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<DistributedLeaseServiceBoundary>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(distributed_lease_boundary_from_env()?))
}

pub(super) async fn system_distributed_lease_claim(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<DistributedLeaseClaimApiRequest>,
) -> Result<Json<DistributedLeaseClaimReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let boundary = distributed_lease_boundary_from_env()?;
    let policy = scheduler_lease_policy(request.lease_seconds, 1)?;
    let plan =
        plan_external_distributed_lease_claim(&boundary, &request.job, request.worker_id, &policy)?;
    let receipt = DistributedLeaseClaimReceipt::granted(&boundary, &plan.request);
    receipt.verify_for(&plan.request)?;
    state
        .store
        .write()
        .await
        .record_distributed_lease_claim_receipt(&receipt)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "distributed lease claim receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", receipt.job_id.to_string())
        .with_attribute("backend", format!("{:?}", receipt.backend))
        .with_attribute("status", format!("{:?}", receipt.status)),
    );
    Ok(Json(receipt))
}

pub(super) async fn system_distributed_lease_adapters(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<DistributedLeaseAdapterRegistry>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(distributed_lease_adapter_registry()))
}

pub(super) async fn system_distributed_lease_adapter_evaluate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<DistributedLeaseAdapterClaimApiRequest>,
) -> Result<Json<DistributedLeaseAdapterReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let boundary = distributed_lease_boundary_from_env()?;
    let policy = scheduler_lease_policy(request.lease_seconds, 1)?;
    let registry = distributed_lease_adapter_registry();
    let report = evaluate_distributed_lease_adapter_claim(
        &boundary,
        &request.job,
        request.worker_id,
        &policy,
        &registry,
    )?;
    {
        let mut store = state.store.write().await;
        store.record_distributed_lease_adapter_report(&report)?;
        store.record_distributed_lease_claim_receipt(&report.receipt)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "distributed lease adapter evaluated",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", report.job_id.to_string())
        .with_attribute("backend", format!("{:?}", report.backend))
        .with_attribute("accepted", report.accepted.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_distributed_lease_executions(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<DistributedLeaseExecutionReceipt>>, ApiError> {
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
            .distributed_lease_execution_receipts()?,
    ))
}

pub(super) async fn system_distributed_lease_execute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<DistributedLeaseExecutionApiRequest>,
) -> Result<Json<DistributedLeaseExecutionReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let boundary = distributed_lease_boundary_from_env()?;
    let policy = scheduler_lease_policy(request.lease_seconds, 1)?;
    let registry = distributed_lease_adapter_registry();
    let mode = request
        .mode
        .unwrap_or(DistributedLeaseExecutionMode::PlanOnly);
    let receipt = execute_distributed_lease_with_receipt(
        &boundary,
        &request.job,
        request.worker_id,
        &policy,
        &registry,
        mode,
    )?;
    {
        let mut store = state.store.write().await;
        store.record_distributed_lease_adapter_report(&receipt.adapter_report)?;
        store.record_distributed_lease_claim_receipt(&receipt.lease_receipt)?;
        store.record_distributed_lease_execution_receipt(&receipt)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "distributed lease execution receipt recorded",
        )
        .with_mind_id(root_id)
        .with_attribute("job_id", receipt.plan.job_id.to_string())
        .with_attribute("backend", format!("{:?}", receipt.plan.backend))
        .with_attribute("accepted", receipt.accepted.to_string()),
    );
    Ok(Json(receipt))
}
