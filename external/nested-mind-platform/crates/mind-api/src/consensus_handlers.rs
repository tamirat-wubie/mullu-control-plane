//! Purpose: consensus membership, commit, apply, compaction, and retention handlers for the Nested Mind API.
//! Governance scope: consensus membership changes, commit certificates, certified apply, compaction decisions, physical compaction, and retention enforcement endpoints.
//! Dependencies: API state, consensus membership, replication apply contracts, compaction guards, and audit/event stores.
//! Invariants: consensus authorization, membership validation, certificate persistence, retention guards, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_consensus_membership(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<ConsensusMembership>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let consensus = state.consensus.read().await.clone();
    consensus.validate()?;
    Ok(Json(consensus))
}

pub(super) async fn apply_consensus_change(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(proposal): Json<ConsensusChangeProposal>,
) -> Result<Json<ConsensusChangeJudgment>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let mut current = state.consensus.write().await;
    let judgment = proposal.evaluate(&current)?;
    judgment.verify_transition(&current)?;
    *current = judgment.resulting_membership.clone();
    {
        let mut store = state.store.write().await;
        store.record_consensus_change_judgment(&judgment)?;
        store.record_consensus_membership(&judgment.resulting_membership)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus membership change accepted",
        )
        .with_attribute("cluster_id", judgment.cluster_id.clone())
        .with_attribute("proposal_id", judgment.proposal_id.to_string())
        .with_attribute(
            "after_configuration_id",
            judgment.after_configuration_id.to_string(),
        ),
    );
    Ok(Json(judgment))
}

pub(super) async fn system_consensus_retention_approvals(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConsensusRetentionApprovalCertificate>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .consensus_retention_approval_certificates()?,
    ))
}

pub(super) async fn approve_consensus_retention(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusRetentionApprovalApiRequest>,
) -> Result<Json<ConsensusRetentionApprovalCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let membership = state.consensus.read().await.clone();
    let proposed_by = request
        .proposed_by
        .or_else(|| principal.as_ref().map(|principal| principal.id.clone()))
        .unwrap_or_else(|| "anonymous-maintainer".to_owned());
    let proposal =
        ConsensusRetentionApprovalProposal::from_plan(&request.plan, &membership, proposed_by)?;
    let policy = ConsensusRetentionApprovalPolicy {
        minimum_approvals: request.minimum_approvals.unwrap_or(1),
        ..ConsensusRetentionApprovalPolicy::default()
    };
    let certificate =
        certify_consensus_retention_approval(&proposal, &membership, &policy, &request.votes)?;
    {
        let mut store = state.store.write().await;
        store.record_consensus_retention_approval_proposal(&proposal)?;
        for vote in &request.votes {
            store.record_consensus_retention_approval_vote(vote)?;
        }
        store.record_consensus_retention_approval_certificate(&certificate)?;
    }
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus retention approval certified",
        )
        .with_mind_id(root_id)
        .with_attribute("cluster_id", certificate.cluster_id.clone())
        .with_attribute("status", format!("{:?}", certificate.status))
        .with_attribute("approvals", certificate.approvals.to_string()),
    );
    Ok(Json(certificate))
}

pub(super) async fn system_consensus_commit_certificates(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConsensusCommitCertificate>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    Ok(Json(
        state.store.read().await.consensus_commit_certificates()?,
    ))
}

pub(super) async fn create_consensus_commit_certificate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusCommitRequest>,
) -> Result<Json<ConsensusCommitCertificate>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let membership = state.consensus.read().await.clone();
    let leader_id = membership
        .leader_id
        .clone()
        .or_else(|| {
            membership
                .voting_members()
                .first()
                .map(|member| member.member_id.clone())
        })
        .ok_or_else(|| MindError::DistributedPlanInvalid {
            reason: "consensus membership has no voting leader candidate".to_owned(),
        })?;
    let entry = ConsensusLogEntry::new(
        &membership,
        leader_id,
        request.operation_kind,
        &request.operation,
        request.previous_entry_hash,
    )?;
    let vote_ids = if request.voters.is_empty() {
        membership
            .voting_members()
            .into_iter()
            .map(|member| member.member_id.clone())
            .collect::<Vec<_>>()
    } else {
        request.voters
    };
    let votes = vote_ids
        .into_iter()
        .map(|voter| ConsensusCommitVote::accept(&entry, voter))
        .collect::<Vec<_>>();
    let certificate = ConsensusCommitCertificate::certify(&membership, entry, votes)?;
    state
        .store
        .write()
        .await
        .record_consensus_commit_certificate(&certificate)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus commit certificate recorded",
        )
        .with_attribute("cluster_id", certificate.entry.cluster_id.clone())
        .with_attribute("entry_id", certificate.entry.entry_id.to_string())
        .with_attribute("committed", certificate.committed.to_string()),
    );
    Ok(Json(certificate))
}

pub(super) async fn system_consensus_apply_reports(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConsensusApplyReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    Ok(Json(state.store.read().await.consensus_apply_reports()?))
}

pub(super) async fn apply_consensus_log_certificate(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusApplyRequest>,
) -> Result<Json<ConsensusApplyReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let membership = state.consensus.read().await.clone();
    let follower_id = request
        .follower_id
        .unwrap_or_else(|| state.distributed_plan.node_id.clone());
    let report = {
        let mut store = state.store.write().await;
        let report = apply_certified_replication_batch(
            &mut *store,
            &membership,
            &request.certificate,
            follower_id,
        )?;
        store.record_consensus_apply_report(&report)?;
        report
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus-certified log entry applied",
        )
        .with_mind_id(report.mind_id.unwrap_or(root_id))
        .with_attribute("certificate_id", report.certificate_id.to_string())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute("records_appended", report.records_appended.to_string()),
    );
    Ok(Json(report))
}

pub(super) async fn apply_consensus_log_certificate_idempotent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusApplyRequest>,
) -> Result<Json<ConsensusApplyReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let membership = state.consensus.read().await.clone();
    let follower_id = request
        .follower_id
        .unwrap_or_else(|| state.distributed_plan.node_id.clone());
    let (decision, report) = {
        let mut store = state.store.write().await;
        let prior = store.consensus_apply_reports()?;
        let (decision, report) = apply_certified_replication_batch_idempotent(
            &mut *store,
            &membership,
            &request.certificate,
            &prior,
            follower_id,
        )?;
        store.record_consensus_apply_idempotency_decision(&decision)?;
        store.record_consensus_apply_report(&report)?;
        (decision, report)
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "idempotent consensus-certified log entry checked",
        )
        .with_mind_id(report.mind_id.unwrap_or(root_id))
        .with_attribute("certificate_id", report.certificate_id.to_string())
        .with_attribute("idempotency", format!("{:?}", decision.status))
        .with_attribute("status", format!("{:?}", report.status)),
    );
    Ok(Json(report))
}

pub(super) async fn compact_consensus_log(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusLogCompactionRequest>,
) -> Result<Json<ConsensusLogCompactionDecision>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let membership = state.consensus.read().await.clone();
    let policy = ConsensusLogCompactionPolicy {
        keep_latest_committed: request.keep_latest_committed.unwrap_or(64),
        min_committed_entries_between_compactions: request
            .min_committed_entries_between_compactions
            .unwrap_or(128),
    };
    let decision = {
        let mut store = state.store.write().await;
        let certificates = store.consensus_commit_certificates()?;
        let reports = store.consensus_apply_reports()?;
        let decision = evaluate_consensus_log_compaction(
            membership.cluster_id.clone(),
            &certificates,
            &reports,
            &policy,
        )?;
        store.record_consensus_log_compaction_decision(&decision)?;
        decision
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus log compaction evaluated",
        )
        .with_attribute("cluster_id", decision.cluster_id.clone())
        .with_attribute("should_compact", decision.should_compact.to_string())
        .with_attribute(
            "compacted_count",
            decision.compact_certificate_ids.len().to_string(),
        ),
    );
    Ok(Json(decision))
}

pub(super) async fn system_consensus_physical_compactions(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConsensusPhysicalCompactionReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .consensus_physical_compaction_reports()?,
    ))
}

pub(super) async fn physical_compact_consensus_log(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<PhysicalConsensusCompactionRequest>,
) -> Result<Json<ConsensusPhysicalCompactionReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(
        &request.decision,
        &request.backup_verification,
    )?;
    let plan = plan_physical_consensus_compaction(&request.decision, guard)?;
    let report = if request.apply {
        state
            .store
            .write()
            .await
            .apply_consensus_physical_compaction(&plan)?
    } else {
        let report = ConsensusPhysicalCompactionReport::planned(&plan);
        state
            .store
            .write()
            .await
            .record_consensus_physical_compaction_report(&report)?;
        report
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "physical consensus compaction evaluated",
        )
        .with_mind_id(root_id)
        .with_attribute("cluster_id", report.cluster_id.clone())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute(
            "deleted_certificate_count",
            report.deleted_certificate_count.to_string(),
        ),
    );
    Ok(Json(report))
}

pub(super) async fn system_consensus_retention_enforcements(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<ConsensusRetentionEnforcementReport>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    Ok(Json(
        state
            .store
            .read()
            .await
            .consensus_retention_enforcement_reports()?,
    ))
}

pub(super) async fn enforce_consensus_retention(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<ConsensusRetentionEnforcementRequest>,
) -> Result<Json<ConsensusRetentionEnforcementReport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ManageConsensus)?;
    let guard = ConsensusCompactionBackupGuard::from_backup_verification(
        &request.decision,
        &request.backup_verification,
    )?;
    let physical_plan = plan_physical_consensus_compaction(&request.decision, guard)?;
    let policy = ConsensusRetentionPolicy {
        delete_apply_reports: request.delete_apply_reports,
        keep_latest_apply_reports: request.keep_latest_apply_reports.unwrap_or(128),
        ..ConsensusRetentionPolicy::default()
    };
    let report = {
        let mut store = state.store.write().await;
        let apply_reports = store.consensus_apply_reports()?;
        let plan = plan_consensus_retention_enforcement(
            &request.decision,
            &physical_plan,
            &apply_reports,
            &policy,
        )?;
        if request.apply {
            store.apply_consensus_retention_enforcement(&plan)?
        } else {
            let report = report_consensus_retention_enforcement_planned(&plan);
            store.record_consensus_retention_enforcement_report(&report)?;
            report
        }
    };
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::DistributedPlanChecked,
            "consensus retention enforcement evaluated",
        )
        .with_mind_id(root_id)
        .with_attribute("cluster_id", report.cluster_id.clone())
        .with_attribute("status", format!("{:?}", report.status))
        .with_attribute(
            "deleted_apply_report_count",
            report.deleted_apply_report_count.to_string(),
        ),
    );
    Ok(Json(report))
}
