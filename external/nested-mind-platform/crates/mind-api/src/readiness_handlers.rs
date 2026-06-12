//! Purpose: readiness, quality, waiver, branch-protection, and staging-chaos handlers for the Nested Mind API.
//! Governance scope: release readiness evaluation, quality evidence generation, waiver certification, branch protection planning, staging chaos, and implementation evidence endpoints.
//! Dependencies: API state, readiness gates, chaos and fuzz contracts, waiver policies, branch protection policies, GitHub readiness evidence, and audit/event stores.
//! Invariants: readiness authorization, quality evidence persistence, waiver certification, branch protection planning, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_creative_engineering_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<CreativeEngineeringReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.creative_engineering_reports()?,
    ))
}

pub(super) async fn generate_creative_engineering(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<CreativeEngineeringReportInput>,
) -> Result<Json<CreativeEngineeringReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = generate_creative_engineering_report(input)?;
    state
        .store
        .write()
        .await
        .record_creative_engineering_report(&report)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "creative engineering report generated",
        )
        .with_mind_id(root_id)
        .with_attribute("report_id", report.report_id.to_string())
        .with_attribute("suggestion_count", report.suggestions.len().to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_chaos_rehearsal_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ChaosRehearsalPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.chaos_rehearsal_plans()?))
}

pub(super) async fn generate_chaos_rehearsal_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ChaosRehearsalApiRequest>,
) -> Result<Json<ChaosRehearsalPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = production_chaos_rehearsal_plan(Some(request.mind_id.unwrap_or(root_id)))?;
    state
        .store
        .write()
        .await
        .record_chaos_rehearsal_plan(&plan)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "chaos rehearsal plan generated",
        )
        .with_mind_id(root_id)
        .with_attribute("plan_id", plan.plan_id.to_string())
        .with_attribute("experiment_count", plan.experiments.len().to_string()),
    );
    Ok(Json(plan))
}

pub(super) async fn system_invariant_fuzz_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<InvariantFuzzRunReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.invariant_fuzz_run_reports()?))
}

pub(super) async fn generate_invariant_fuzz(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<InvariantFuzzApiRequest>,
) -> Result<Json<InvariantFuzzRunReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = generate_invariant_fuzz_run(
        request.mind_id.unwrap_or(root_id),
        request.config.unwrap_or_default(),
    )?;
    state
        .store
        .write()
        .await
        .record_invariant_fuzz_run_report(&report)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "invariant fuzz run generated",
        )
        .with_mind_id(root_id)
        .with_attribute("run_id", report.run_id.to_string())
        .with_attribute("case_count", report.cases.len().to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_readiness_gates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ProductionReadinessGateReport>>, ApiError> {
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
            .production_readiness_gate_reports()?,
    ))
}

pub(super) async fn evaluate_readiness_gate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ReadinessGateApiRequest>,
) -> Result<Json<ProductionReadinessGateReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = evaluate_production_readiness_gate(
        &request.creative_report,
        request.chaos_plan.as_ref(),
        request.fuzz_report.as_ref(),
        request.policy.unwrap_or_default(),
    )?;
    state
        .store
        .write()
        .await
        .record_production_readiness_gate_report(&report)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "production readiness gate evaluated",
        )
        .with_mind_id(root_id)
        .with_attribute("gate_id", report.gate_id.to_string())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute("blocker_count", report.blockers.len().to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_chaos_execution_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ChaosExecutionRun>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.chaos_execution_runs()?))
}

pub(super) async fn execute_chaos_rehearsal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ChaosExecutionApiRequest>,
) -> Result<Json<ChaosExecutionRun>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let run = execute_chaos_rehearsal_plan(&request.plan, request.mode.unwrap_or_default())?;
    state.store.write().await.record_chaos_execution_run(&run)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "chaos rehearsal executed",
        )
        .with_mind_id(root_id)
        .with_attribute("run_id", run.run_id.to_string())
        .with_attribute("status", format!("{:?}", run.status)),
    );
    Ok(Json(run))
}

pub(super) async fn system_invariant_fuzz_executions(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<InvariantFuzzExecutionReport>>, ApiError> {
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
            .invariant_fuzz_execution_reports()?,
    ))
}

pub(super) async fn execute_invariant_fuzz(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<InvariantFuzzExecutionApiRequest>,
) -> Result<Json<InvariantFuzzExecutionReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = execute_invariant_fuzz_run(&request.report, request.config.unwrap_or_default())?;
    state
        .store
        .write()
        .await
        .record_invariant_fuzz_execution_report(&report)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "invariant fuzz run executed",
        )
        .with_mind_id(root_id)
        .with_attribute("execution_id", report.execution_id.to_string())
        .with_attribute("failed_count", report.failed_count.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn system_readiness_waiver_proposals(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ReadinessWaiverProposal>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.readiness_waiver_proposals()?))
}

pub(super) async fn create_readiness_waiver_proposal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ReadinessWaiverProposalApiRequest>,
) -> Result<Json<ReadinessWaiverProposal>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let expires_at = request
        .expires_in_seconds
        .map(|seconds| OffsetDateTime::now_utc() + Duration::seconds(seconds));
    let blocker_ids = if request.blocker_ids.is_empty() {
        request
            .gate
            .blockers
            .iter()
            .map(|blocker| blocker.blocker_id)
            .collect()
    } else {
        request.blocker_ids
    };
    let proposal = ReadinessWaiverProposal::new(
        &request.gate,
        blocker_ids,
        request.proposed_by,
        request.reason,
        request.risk_owner,
        expires_at,
    )?;
    state
        .store
        .write()
        .await
        .record_readiness_waiver_proposal(&proposal)?;
    Ok(Json(proposal))
}

pub(super) async fn system_readiness_waiver_certificates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ReadinessWaiverCertificate>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.readiness_waiver_certificates()?,
    ))
}

pub(super) async fn create_readiness_waiver_certificate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ReadinessWaiverCertificateApiRequest>,
) -> Result<Json<ReadinessWaiverCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let certificate =
        certify_readiness_waiver(request.proposal, request.votes, request.required_approvals)?;
    state
        .store
        .write()
        .await
        .record_readiness_waiver_certificate(&certificate)?;
    Ok(Json(certificate))
}

pub(super) async fn system_readiness_waiver_applications(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ReadinessWaiverApplicationReport>>, ApiError> {
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
            .readiness_waiver_application_reports()?,
    ))
}

pub(super) async fn apply_readiness_waivers(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ReadinessWaiverApplicationApiRequest>,
) -> Result<Json<ReadinessWaiverApplicationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = apply_readiness_waivers_to_gate(&request.gate, &request.certificates)?;
    state
        .store
        .write()
        .await
        .record_readiness_waiver_application_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_engineering_implementation_job_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<EngineeringImplementationJobPlan>>, ApiError> {
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
            .engineering_implementation_job_plans()?,
    ))
}

pub(super) async fn create_engineering_implementation_job_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<EngineeringImplementationJobsApiRequest>,
) -> Result<Json<EngineeringImplementationJobPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = schedule_engineering_implementation_jobs(
        &request.report,
        request.limit,
        request.due_in_seconds,
    )?;
    state
        .store
        .write()
        .await
        .record_engineering_implementation_job_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_staging_chaos_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<StagingChaosRunReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.staging_chaos_run_reports()?))
}

pub(super) async fn run_staging_chaos(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<StagingChaosApiRequest>,
) -> Result<Json<StagingChaosRunReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = run_staging_chaos_rehearsal(
        &request.plan,
        request.environment,
        request.mode.unwrap_or_default(),
        request.policy.unwrap_or_default(),
    )?;
    state
        .store
        .write()
        .await
        .record_staging_chaos_run_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_mandatory_ci_gates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<MandatoryCiGateReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.mandatory_ci_gate_reports()?))
}

pub(super) async fn evaluate_mandatory_ci(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<MandatoryCiGateApiRequest>,
) -> Result<Json<MandatoryCiGateReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = evaluate_mandatory_ci_gate(request.input, request.policy.unwrap_or_default())?;
    state
        .store
        .write()
        .await
        .record_mandatory_ci_gate_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_multi_operator_waivers(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<MultiOperatorWaiverCertificate>>, ApiError> {
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
            .multi_operator_waiver_certificates()?,
    ))
}

pub(super) async fn certify_multi_operator_waiver(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<MultiOperatorWaiverApiRequest>,
) -> Result<Json<MultiOperatorWaiverCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let certificate = certify_multi_operator_readiness_waiver(
        request.proposal,
        &request.gate,
        request.votes,
        request.policy.unwrap_or_default(),
    )?;
    state
        .store
        .write()
        .await
        .record_multi_operator_waiver_certificate(&certificate)?;
    Ok(Json(certificate))
}

pub(super) async fn system_implementation_evidence_bundles(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ImplementationJobEvidenceBundle>>, ApiError> {
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
            .implementation_job_evidence_bundles()?,
    ))
}

pub(super) async fn attach_engineering_implementation_evidence(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ImplementationEvidenceApiRequest>,
) -> Result<Json<ImplementationJobEvidenceBundle>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let required_kinds = if request.required_kinds.is_empty() {
        default_implementation_evidence_requirements()
    } else {
        request.required_kinds.into_iter().collect()
    };
    let bundle = attach_implementation_evidence(&request.job, request.artifacts, required_kinds)?;
    state
        .store
        .write()
        .await
        .record_implementation_job_evidence_bundle(&bundle)?;
    Ok(Json(bundle))
}

pub(super) async fn system_implementation_evidence_automation_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ImplementationEvidenceAutomationPlan>>, ApiError> {
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
            .implementation_evidence_automation_plans()?,
    ))
}

pub(super) async fn plan_engineering_evidence_automation(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ImplementationEvidenceAutomationApiRequest>,
) -> Result<Json<ImplementationEvidenceAutomationPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_implementation_evidence_automation(
        &request.plan,
        request.repository,
        request.base_branch,
    )?;
    state
        .store
        .write()
        .await
        .record_implementation_evidence_automation_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_readiness_evidence_bundles(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubReadinessEvidenceBundle>>, ApiError> {
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
            .github_readiness_evidence_bundles()?,
    ))
}

pub(super) async fn collect_github_readiness_bundle(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubEvidenceApiRequest>,
) -> Result<Json<GitHubReadinessEvidenceBundle>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let required = request.required_check_names.into_iter().collect();
    let bundle =
        collect_github_readiness_evidence(request.pull_request, request.check_runs, required)?;
    state
        .store
        .write()
        .await
        .record_github_readiness_evidence_bundle(&bundle)?;
    Ok(Json(bundle))
}

pub(super) async fn system_branch_protection_policies(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionPolicy>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.branch_protection_policies()?))
}

pub(super) async fn create_branch_protection_policy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionPolicyApiRequest>,
) -> Result<Json<BranchProtectionPolicy>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let policy = production_branch_protection_policy(request.repository, request.branch)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_policy(&policy)?;
    Ok(Json(policy))
}

pub(super) async fn system_branch_protection_evaluations(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionEvaluationReport>>, ApiError> {
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
            .branch_protection_evaluation_reports()?,
    ))
}

pub(super) async fn evaluate_branch_protection(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionEvaluationApiRequest>,
) -> Result<Json<BranchProtectionEvaluationReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let report = evaluate_branch_protection_policy(&request.policy, request.observed)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_evaluation_report(&report)?;
    Ok(Json(report))
}

pub(super) async fn system_live_staging_chaos_adapter_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<LiveStagingChaosAdapterPlan>>, ApiError> {
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
            .live_staging_chaos_adapter_plans()?,
    ))
}

pub(super) async fn create_live_staging_chaos_adapter_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LiveStagingChaosAdapterApiRequest>,
) -> Result<Json<LiveStagingChaosAdapterPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_live_staging_chaos_adapter(
        &request.rehearsal,
        request.staging_report.as_ref(),
        request
            .backend
            .unwrap_or(LiveChaosAdapterBackend::KubernetesServerDryRun),
        request.mode.unwrap_or_default(),
    )?;
    state
        .store
        .write()
        .await
        .record_live_staging_chaos_adapter_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_live_staging_chaos_adapter_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<LiveStagingChaosAdapterReceipt>>, ApiError> {
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
            .live_staging_chaos_adapter_receipts()?,
    ))
}

pub(super) async fn execute_live_staging_chaos_adapter(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<LiveStagingChaosAdapterReceiptApiRequest>,
) -> Result<Json<LiveStagingChaosAdapterReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = execute_live_staging_chaos_adapter_dry_run(&request.plan)?;
    state
        .store
        .write()
        .await
        .record_live_staging_chaos_adapter_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_waiver_review_certificates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverReviewCertificate>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(state.store.read().await.waiver_review_certificates()?))
}

pub(super) async fn create_waiver_review_certificate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverReviewCertificateApiRequest>,
) -> Result<Json<WaiverReviewCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let certificate = certify_waiver_review(&request.item, request.comments)?;
    state
        .store
        .write()
        .await
        .record_waiver_review_certificate(&certificate)?;
    Ok(Json(certificate))
}

pub(super) async fn system_github_check_run_write_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubCheckRunWritePlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.github_check_run_write_plans()?,
    ))
}

pub(super) async fn create_github_check_run_write_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubCheckRunWritePlanApiRequest>,
) -> Result<Json<GitHubCheckRunWritePlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_github_check_run_write(
        request.repository,
        request.head_sha,
        request.name,
        request.output,
        request.conclusion,
        request.details_url,
        request.external_id,
        request.app_slug,
        request.mode,
    )?;
    state
        .store
        .write()
        .await
        .record_github_check_run_write_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_github_check_run_write_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<GitHubCheckRunWriteReceipt>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.github_check_run_write_receipts()?,
    ))
}

pub(super) async fn create_github_check_run_write_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<GitHubCheckRunWriteReceiptApiRequest>,
) -> Result<Json<GitHubCheckRunWriteReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_github_check_run_write_receipt(
        &request.plan,
        request.github_check_run_id,
        request.html_url,
        request.response_payload,
    )?;
    state
        .store
        .write()
        .await
        .record_github_check_run_write_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_branch_protection_reconcile_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionReconcilePlan>>, ApiError> {
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
            .branch_protection_reconcile_plans()?,
    ))
}

pub(super) async fn create_branch_protection_reconcile_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionReconcileApiRequest>,
) -> Result<Json<BranchProtectionReconcilePlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_branch_protection_reconcile(request.policy, request.observed, request.mode)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_reconcile_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_branch_protection_reconcile_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BranchProtectionReconcileReceipt>>, ApiError> {
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
            .branch_protection_reconcile_receipts()?,
    ))
}

pub(super) async fn create_branch_protection_reconcile_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<BranchProtectionReconcileReceiptApiRequest>,
) -> Result<Json<BranchProtectionReconcileReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt =
        record_branch_protection_reconcile_receipt(&request.plan, request.response_payload)?;
    state
        .store
        .write()
        .await
        .record_branch_protection_reconcile_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_kubernetes_staging_chaos_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesStagingChaosPlan>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.kubernetes_staging_chaos_plans()?,
    ))
}

pub(super) async fn create_kubernetes_staging_chaos_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesStagingChaosPlanApiRequest>,
) -> Result<Json<KubernetesStagingChaosPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_kubernetes_staging_chaos(
        &request.rehearsal,
        request.adapter_plan.as_ref(),
        request.namespace,
        request.service_account,
        request.mode,
        request.approval_certificate_hash,
    )?;
    state
        .store
        .write()
        .await
        .record_kubernetes_staging_chaos_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_kubernetes_staging_chaos_receipts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<KubernetesStagingChaosReceipt>>, ApiError> {
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
            .kubernetes_staging_chaos_receipts()?,
    ))
}

pub(super) async fn create_kubernetes_staging_chaos_receipt(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<KubernetesStagingChaosReceiptApiRequest>,
) -> Result<Json<KubernetesStagingChaosReceipt>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let receipt = record_kubernetes_staging_chaos_receipt(&request.plan, request.response_payload)?;
    state
        .store
        .write()
        .await
        .record_kubernetes_staging_chaos_receipt(&receipt)?;
    Ok(Json(receipt))
}

pub(super) async fn system_waiver_reviewer_assignment_plans(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverReviewerAssignmentPlan>>, ApiError> {
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
            .waiver_reviewer_assignment_plans()?,
    ))
}

pub(super) async fn create_waiver_reviewer_assignment_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverReviewerAssignmentApiRequest>,
) -> Result<Json<WaiverReviewerAssignmentPlan>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let plan = plan_waiver_reviewer_assignment(
        &request.item,
        request.candidates,
        request.escalation_targets,
        request.escalation_after_hours,
    )?;
    state
        .store
        .write()
        .await
        .record_waiver_reviewer_assignment_plan(&plan)?;
    Ok(Json(plan))
}

pub(super) async fn system_waiver_escalation_certificates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<WaiverEscalationCertificate>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    Ok(Json(
        state.store.read().await.waiver_escalation_certificates()?,
    ))
}

pub(super) async fn create_waiver_escalation_certificate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<WaiverEscalationApiRequest>,
) -> Result<Json<WaiverEscalationCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::Administer)?;
    let certificate = certify_waiver_escalation(&request.plan, request.reason)?;
    state
        .store
        .write()
        .await
        .record_waiver_escalation_certificate(&certificate)?;
    Ok(Json(certificate))
}
