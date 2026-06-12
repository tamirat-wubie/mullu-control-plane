//! Purpose: runtime store adapter boundary for the Nested Mind API.
//! Governance scope: event, snapshot, and observability store selection and adapter delegation.
//! Dependencies: mind-core store traits, SQLite store adapter, JSONL stores, and API runtime configuration helpers.
//! Invariants: selected stores preserve signature requirements; non-SQLite adapters explicitly no-op unsupported persistence surfaces.

use super::*;

pub(super) enum RuntimeEventStore {
    Memory(InMemoryEventStore),
    Jsonl(JsonlEventStore),
    Sqlite(SqliteEventStore),
}
impl RuntimeEventStore {
    pub(super) fn from_env(signature_requirement: SignatureRequirement) -> Result<Self, MindError> {
        if let Ok(path) = env::var("MIND_EVENT_DB") {
            if !path.trim().is_empty() {
                return Ok(Self::Sqlite(
                    SqliteEventStore::open(path.trim())?
                        .with_signature_requirement(signature_requirement),
                ));
            }
        }
        match env::var("MIND_EVENT_LOG") {
            Ok(path) if !path.trim().is_empty() => Ok(Self::Jsonl(
                JsonlEventStore::new(path)?.with_signature_requirement(signature_requirement),
            )),
            _ => Ok(Self::Memory(
                InMemoryEventStore::new().with_signature_requirement(signature_requirement),
            )),
        }
    }
    pub(super) fn schema_report(&self) -> Result<SchemaMigrationReport, MindError> {
        match self {
            Self::Sqlite(store) => store.schema_report(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(SchemaMigrationReport::already_current(
                PLATFORM_SCHEMA_VERSION,
            )),
        }
    }

    pub(super) fn record_backup_manifest(
        &mut self,
        manifest: &BackupManifest,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_backup_manifest(manifest),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn backup_manifests(&self) -> Result<Vec<BackupManifest>, MindError> {
        match self {
            Self::Sqlite(store) => store.backup_manifests(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_oidc_jwks_cache(
        &mut self,
        cache: &OidcJwksCacheEntry,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_oidc_jwks_cache(cache),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_cloud_upload_receipt(
        &mut self,
        receipt: &CloudUploadReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_cloud_upload_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_replication_envelope(
        &mut self,
        envelope: &mind_core::ReplicationEnvelope,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_replication_envelope(envelope),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_live_oidc_refresh(
        &mut self,
        report: &LiveOidcRefreshReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_oidc_refresh(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_cloud_signed_url_receipt(
        &mut self,
        receipt: &CloudSignedUrlReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_cloud_signed_url_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_replication_delivery_receipt(
        &mut self,
        receipt: &ReplicationDeliveryReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_replication_delivery_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_change_judgment(
        &mut self,
        judgment: &ConsensusChangeJudgment,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_change_judgment(judgment),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_membership(
        &mut self,
        membership: &ConsensusMembership,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_membership(membership),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_scheduled_job(&mut self, job: &ScheduledJob) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_scheduled_job(job),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn scheduled_jobs(&self) -> Result<Vec<ScheduledJob>, MindError> {
        match self {
            Self::Sqlite(store) => store.scheduled_jobs(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_provider_execution_receipt(
        &mut self,
        receipt: &ProviderExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_provider_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn provider_execution_receipts(
        &self,
    ) -> Result<Vec<ProviderExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.provider_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_consensus_commit_certificate(
        &mut self,
        certificate: &ConsensusCommitCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_commit_certificate(certificate),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn consensus_commit_certificates(
        &self,
    ) -> Result<Vec<ConsensusCommitCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.consensus_commit_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_scheduler_lease(
        &mut self,
        lease: &SchedulerLeaseRecord,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_scheduler_lease(lease),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn scheduler_leases(&self) -> Result<Vec<SchedulerLeaseRecord>, MindError> {
        match self {
            Self::Sqlite(store) => store.scheduler_leases(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_worker_run_report(
        &mut self,
        report: &WorkerRunReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_worker_run_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn worker_run_reports(&self) -> Result<Vec<WorkerRunReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.worker_run_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_provider_sdk_receipt(
        &mut self,
        receipt: &ProviderSdkReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_provider_sdk_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn provider_sdk_receipts(&self) -> Result<Vec<ProviderSdkReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.provider_sdk_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_consensus_apply_report(
        &mut self,
        report: &ConsensusApplyReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_apply_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn consensus_apply_reports(&self) -> Result<Vec<ConsensusApplyReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.consensus_apply_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn claim_due_jobs_for_worker(
        &mut self,
        worker_id: impl Into<String>,
        policy: &SchedulerLeasePolicy,
        limit: usize,
        now: OffsetDateTime,
    ) -> Result<SchedulerLeaseClaimReport, MindError> {
        let worker_id = worker_id.into();
        if let Self::Sqlite(store) = self {
            return store.claim_due_jobs_for_worker(worker_id, policy, limit, now);
        }
        let jobs = self.scheduled_jobs()?;
        let report = mind_core::claim_due_jobs_with_leases(&jobs, worker_id, policy, limit, now)?;
        for job in &report.updated_jobs {
            self.record_scheduled_job(job)?;
        }
        for lease in &report.leases {
            self.record_scheduler_lease(lease)?;
        }
        Ok(report)
    }

    pub(super) fn record_worker_daemon_tick(
        &mut self,
        report: &WorkerDaemonTickReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_worker_daemon_tick(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn worker_daemon_ticks(&self) -> Result<Vec<WorkerDaemonTickReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.worker_daemon_ticks(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_provider_sdk_feature_matrix(
        &mut self,
        matrix: &ProviderSdkFeatureMatrix,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_provider_sdk_feature_matrix(matrix),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_apply_idempotency_decision(
        &mut self,
        decision: &ConsensusApplyIdempotencyDecision,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_apply_idempotency_decision(decision),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_log_compaction_decision(
        &mut self,
        decision: &ConsensusLogCompactionDecision,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_log_compaction_decision(decision),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_job_execution_receipt(
        &mut self,
        receipt: &JobExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_job_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn job_execution_receipts(&self) -> Result<Vec<JobExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.job_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_native_provider_adapter_report(
        &mut self,
        report: &NativeProviderAdapterReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_native_provider_adapter_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_distributed_lease_claim_receipt(
        &mut self,
        receipt: &DistributedLeaseClaimReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_distributed_lease_claim_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn consensus_physical_compaction_reports(
        &self,
    ) -> Result<Vec<ConsensusPhysicalCompactionReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.consensus_physical_compaction_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_consensus_physical_compaction_report(
        &mut self,
        report: &ConsensusPhysicalCompactionReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_physical_compaction_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn apply_consensus_physical_compaction(
        &mut self,
        plan: &mind_core::ConsensusPhysicalCompactionPlan,
    ) -> Result<ConsensusPhysicalCompactionReport, MindError> {
        match self {
            Self::Sqlite(store) => store.apply_consensus_physical_compaction(plan),
            Self::Memory(_) | Self::Jsonl(_) => {
                Ok(ConsensusPhysicalCompactionReport::planned(plan))
            }
        }
    }

    pub(super) fn record_domain_job_execution_report(
        &mut self,
        report: &DomainJobExecutionReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_domain_job_execution_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn domain_job_execution_reports(
        &self,
    ) -> Result<Vec<DomainJobExecutionReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.domain_job_execution_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_distributed_lease_adapter_report(
        &mut self,
        report: &DistributedLeaseAdapterReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_distributed_lease_adapter_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_native_provider_execution_receipt(
        &mut self,
        receipt: &NativeProviderExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_native_provider_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn native_provider_execution_receipts(
        &self,
    ) -> Result<Vec<NativeProviderExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.native_provider_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_consensus_retention_enforcement_report(
        &mut self,
        report: &ConsensusRetentionEnforcementReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_retention_enforcement_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn consensus_retention_enforcement_reports(
        &self,
    ) -> Result<Vec<ConsensusRetentionEnforcementReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.consensus_retention_enforcement_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn apply_consensus_retention_enforcement(
        &mut self,
        plan: &mind_core::ConsensusRetentionEnforcementPlan,
    ) -> Result<ConsensusRetentionEnforcementReport, MindError> {
        match self {
            Self::Sqlite(store) => store.apply_consensus_retention_enforcement(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(
                mind_core::report_consensus_retention_enforcement_planned(plan),
            ),
        }
    }

    pub(super) fn record_live_domain_job_execution_report(
        &mut self,
        report: &LiveDomainJobExecutionReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_domain_job_execution_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn live_domain_job_execution_reports(
        &self,
    ) -> Result<Vec<LiveDomainJobExecutionReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.live_domain_job_execution_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_distributed_lease_execution_receipt(
        &mut self,
        receipt: &DistributedLeaseExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_distributed_lease_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn distributed_lease_execution_receipts(
        &self,
    ) -> Result<Vec<DistributedLeaseExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.distributed_lease_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_provider_sdk_execution_report(
        &mut self,
        report: &ProviderSdkExecutionReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_provider_sdk_execution_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn provider_sdk_execution_reports(
        &self,
    ) -> Result<Vec<ProviderSdkExecutionReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.provider_sdk_execution_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_consensus_retention_approval_proposal(
        &mut self,
        proposal: &ConsensusRetentionApprovalProposal,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_retention_approval_proposal(proposal),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_retention_approval_vote(
        &mut self,
        vote: &ConsensusRetentionApprovalVote,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_consensus_retention_approval_vote(vote),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn record_consensus_retention_approval_certificate(
        &mut self,
        certificate: &ConsensusRetentionApprovalCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => {
                store.record_consensus_retention_approval_certificate(certificate)
            }
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn consensus_retention_approval_certificates(
        &self,
    ) -> Result<Vec<ConsensusRetentionApprovalCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.consensus_retention_approval_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_creative_engineering_report(
        &mut self,
        report: &CreativeEngineeringReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_creative_engineering_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn creative_engineering_reports(
        &self,
    ) -> Result<Vec<CreativeEngineeringReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.creative_engineering_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_chaos_rehearsal_plan(
        &mut self,
        plan: &ChaosRehearsalPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_chaos_rehearsal_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn chaos_rehearsal_plans(&self) -> Result<Vec<ChaosRehearsalPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.chaos_rehearsal_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_invariant_fuzz_run_report(
        &mut self,
        report: &InvariantFuzzRunReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_invariant_fuzz_run_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn invariant_fuzz_run_reports(
        &self,
    ) -> Result<Vec<InvariantFuzzRunReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.invariant_fuzz_run_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_production_readiness_gate_report(
        &mut self,
        report: &ProductionReadinessGateReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_production_readiness_gate_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn production_readiness_gate_reports(
        &self,
    ) -> Result<Vec<ProductionReadinessGateReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.production_readiness_gate_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_chaos_execution_run(
        &mut self,
        run: &ChaosExecutionRun,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_chaos_execution_run(run),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn chaos_execution_runs(&self) -> Result<Vec<ChaosExecutionRun>, MindError> {
        match self {
            Self::Sqlite(store) => store.chaos_execution_runs(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_invariant_fuzz_execution_report(
        &mut self,
        report: &InvariantFuzzExecutionReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_invariant_fuzz_execution_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn invariant_fuzz_execution_reports(
        &self,
    ) -> Result<Vec<InvariantFuzzExecutionReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.invariant_fuzz_execution_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_readiness_waiver_proposal(
        &mut self,
        proposal: &ReadinessWaiverProposal,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_readiness_waiver_proposal(proposal),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn readiness_waiver_proposals(
        &self,
    ) -> Result<Vec<ReadinessWaiverProposal>, MindError> {
        match self {
            Self::Sqlite(store) => store.readiness_waiver_proposals(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_readiness_waiver_certificate(
        &mut self,
        certificate: &ReadinessWaiverCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_readiness_waiver_certificate(certificate),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn readiness_waiver_certificates(
        &self,
    ) -> Result<Vec<ReadinessWaiverCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.readiness_waiver_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_readiness_waiver_application_report(
        &mut self,
        report: &ReadinessWaiverApplicationReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_readiness_waiver_application_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn readiness_waiver_application_reports(
        &self,
    ) -> Result<Vec<ReadinessWaiverApplicationReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.readiness_waiver_application_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_engineering_implementation_job_plan(
        &mut self,
        plan: &EngineeringImplementationJobPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_engineering_implementation_job_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn engineering_implementation_job_plans(
        &self,
    ) -> Result<Vec<EngineeringImplementationJobPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.engineering_implementation_job_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_staging_chaos_run_report(
        &mut self,
        report: &StagingChaosRunReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_staging_chaos_run_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn staging_chaos_run_reports(
        &self,
    ) -> Result<Vec<StagingChaosRunReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.staging_chaos_run_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_mandatory_ci_gate_report(
        &mut self,
        report: &MandatoryCiGateReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_mandatory_ci_gate_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn mandatory_ci_gate_reports(
        &self,
    ) -> Result<Vec<MandatoryCiGateReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.mandatory_ci_gate_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_multi_operator_waiver_certificate(
        &mut self,
        certificate: &MultiOperatorWaiverCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_multi_operator_waiver_certificate(certificate),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn multi_operator_waiver_certificates(
        &self,
    ) -> Result<Vec<MultiOperatorWaiverCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.multi_operator_waiver_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_implementation_job_evidence_bundle(
        &mut self,
        bundle: &ImplementationJobEvidenceBundle,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_implementation_job_evidence_bundle(bundle),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn implementation_job_evidence_bundles(
        &self,
    ) -> Result<Vec<ImplementationJobEvidenceBundle>, MindError> {
        match self {
            Self::Sqlite(store) => store.implementation_job_evidence_bundles(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_implementation_evidence_automation_plan(
        &mut self,
        plan: &ImplementationEvidenceAutomationPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_implementation_evidence_automation_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn implementation_evidence_automation_plans(
        &self,
    ) -> Result<Vec<ImplementationEvidenceAutomationPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.implementation_evidence_automation_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_github_readiness_evidence_bundle(
        &mut self,
        bundle: &GitHubReadinessEvidenceBundle,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_readiness_evidence_bundle(bundle),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn github_readiness_evidence_bundles(
        &self,
    ) -> Result<Vec<GitHubReadinessEvidenceBundle>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_readiness_evidence_bundles(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_branch_protection_policy(
        &mut self,
        policy: &BranchProtectionPolicy,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_policy(policy),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn branch_protection_policies(
        &self,
    ) -> Result<Vec<BranchProtectionPolicy>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_policies(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_branch_protection_evaluation_report(
        &mut self,
        report: &BranchProtectionEvaluationReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_evaluation_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn branch_protection_evaluation_reports(
        &self,
    ) -> Result<Vec<BranchProtectionEvaluationReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_evaluation_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_live_staging_chaos_adapter_plan(
        &mut self,
        plan: &LiveStagingChaosAdapterPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_staging_chaos_adapter_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn live_staging_chaos_adapter_plans(
        &self,
    ) -> Result<Vec<LiveStagingChaosAdapterPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.live_staging_chaos_adapter_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_live_staging_chaos_adapter_receipt(
        &mut self,
        receipt: &LiveStagingChaosAdapterReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_staging_chaos_adapter_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn live_staging_chaos_adapter_receipts(
        &self,
    ) -> Result<Vec<LiveStagingChaosAdapterReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.live_staging_chaos_adapter_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_waiver_review_certificate(
        &mut self,
        certificate: &WaiverReviewCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_review_certificate(certificate),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }

    pub(super) fn waiver_review_certificates(
        &self,
    ) -> Result<Vec<WaiverReviewCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_review_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }

    pub(super) fn record_github_check_run_write_plan(
        &mut self,
        plan: &GitHubCheckRunWritePlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_check_run_write_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_check_run_write_plans(
        &self,
    ) -> Result<Vec<GitHubCheckRunWritePlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_check_run_write_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_check_run_write_receipt(
        &mut self,
        receipt: &GitHubCheckRunWriteReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_check_run_write_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_check_run_write_receipts(
        &self,
    ) -> Result<Vec<GitHubCheckRunWriteReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_check_run_write_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_branch_protection_reconcile_plan(
        &mut self,
        plan: &BranchProtectionReconcilePlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_reconcile_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn branch_protection_reconcile_plans(
        &self,
    ) -> Result<Vec<BranchProtectionReconcilePlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_reconcile_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_branch_protection_reconcile_receipt(
        &mut self,
        receipt: &BranchProtectionReconcileReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_reconcile_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn branch_protection_reconcile_receipts(
        &self,
    ) -> Result<Vec<BranchProtectionReconcileReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_reconcile_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_staging_chaos_plan(
        &mut self,
        plan: &KubernetesStagingChaosPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_staging_chaos_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_staging_chaos_plans(
        &self,
    ) -> Result<Vec<KubernetesStagingChaosPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_staging_chaos_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_staging_chaos_receipt(
        &mut self,
        receipt: &KubernetesStagingChaosReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_staging_chaos_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_staging_chaos_receipts(
        &self,
    ) -> Result<Vec<KubernetesStagingChaosReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_staging_chaos_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_reviewer_assignment_plan(
        &mut self,
        plan: &WaiverReviewerAssignmentPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_reviewer_assignment_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_reviewer_assignment_plans(
        &self,
    ) -> Result<Vec<WaiverReviewerAssignmentPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_reviewer_assignment_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_escalation_certificate(
        &mut self,
        certificate: &WaiverEscalationCertificate,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_escalation_certificate(certificate),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_escalation_certificates(
        &self,
    ) -> Result<Vec<WaiverEscalationCertificate>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_escalation_certificates(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_app_installation_token_plan(
        &mut self,
        plan: &GitHubAppInstallationTokenPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_app_installation_token_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_app_installation_token_plans(
        &self,
    ) -> Result<Vec<GitHubAppInstallationTokenPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_app_installation_token_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_app_installation_token_receipt(
        &mut self,
        receipt: &GitHubAppInstallationTokenReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_app_installation_token_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_app_installation_token_receipts(
        &self,
    ) -> Result<Vec<GitHubAppInstallationTokenReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_app_installation_token_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_action_execution_plan(
        &mut self,
        plan: &GitHubActionExecutionPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_action_execution_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_action_execution_plans(
        &self,
    ) -> Result<Vec<GitHubActionExecutionPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_action_execution_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_action_execution_receipt(
        &mut self,
        receipt: &GitHubActionExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_action_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_action_execution_receipts(
        &self,
    ) -> Result<Vec<GitHubActionExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_action_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_branch_protection_worker_plan(
        &mut self,
        plan: &BranchProtectionWorkerPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_worker_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn branch_protection_worker_plans(
        &self,
    ) -> Result<Vec<BranchProtectionWorkerPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_worker_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_branch_protection_worker_report(
        &mut self,
        report: &BranchProtectionWorkerReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_branch_protection_worker_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn branch_protection_worker_reports(
        &self,
    ) -> Result<Vec<BranchProtectionWorkerReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.branch_protection_worker_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_dry_run_execution_request(
        &mut self,
        request: &KubernetesDryRunExecutionRequest,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_dry_run_execution_request(request),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_dry_run_execution_requests(
        &self,
    ) -> Result<Vec<KubernetesDryRunExecutionRequest>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_dry_run_execution_requests(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_dry_run_execution_receipt(
        &mut self,
        receipt: &KubernetesDryRunExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_dry_run_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_dry_run_execution_receipts(
        &self,
    ) -> Result<Vec<KubernetesDryRunExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_dry_run_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_notification_plan(
        &mut self,
        plan: &WaiverNotificationPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_notification_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_notification_plans(
        &self,
    ) -> Result<Vec<WaiverNotificationPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_notification_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_notification_receipt(
        &mut self,
        receipt: &WaiverNotificationReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_notification_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_notification_receipts(
        &self,
    ) -> Result<Vec<WaiverNotificationReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_notification_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_secret_access_plan(
        &mut self,
        plan: &SecretAccessPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_secret_access_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn secret_access_plans(&self) -> Result<Vec<SecretAccessPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.secret_access_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_secret_access_receipt(
        &mut self,
        receipt: &SecretAccessReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_secret_access_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn secret_access_receipts(&self) -> Result<Vec<SecretAccessReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.secret_access_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_app_jwt_plan(
        &mut self,
        plan: &GitHubAppJwtPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_app_jwt_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_app_jwt_plans(&self) -> Result<Vec<GitHubAppJwtPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_app_jwt_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_app_jwt_receipt(
        &mut self,
        receipt: &GitHubAppJwtReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_app_jwt_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_app_jwt_receipts(&self) -> Result<Vec<GitHubAppJwtReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_app_jwt_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_connector_worker_job_plan(
        &mut self,
        plan: &ConnectorWorkerJobPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_connector_worker_job_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn connector_worker_job_plans(
        &self,
    ) -> Result<Vec<ConnectorWorkerJobPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.connector_worker_job_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_connector_worker_execution_receipt(
        &mut self,
        receipt: &ConnectorWorkerExecutionReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_connector_worker_execution_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn connector_worker_execution_receipts(
        &self,
    ) -> Result<Vec<ConnectorWorkerExecutionReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.connector_worker_execution_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_admission_audit_request(
        &mut self,
        request: &KubernetesAdmissionAuditRequest,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_admission_audit_request(request),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_admission_audit_requests(
        &self,
    ) -> Result<Vec<KubernetesAdmissionAuditRequest>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_admission_audit_requests(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_admission_audit_receipt(
        &mut self,
        receipt: &KubernetesAdmissionAuditReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_admission_audit_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_admission_audit_receipts(
        &self,
    ) -> Result<Vec<KubernetesAdmissionAuditReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_admission_audit_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_admission_audit_report(
        &mut self,
        report: &KubernetesAdmissionAuditReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_admission_audit_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_admission_audit_reports(
        &self,
    ) -> Result<Vec<KubernetesAdmissionAuditReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_admission_audit_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_notification_adapter_plan(
        &mut self,
        plan: &WaiverNotificationAdapterPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_notification_adapter_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_notification_adapter_plans(
        &self,
    ) -> Result<Vec<WaiverNotificationAdapterPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_notification_adapter_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_waiver_notification_adapter_receipt(
        &mut self,
        receipt: &WaiverNotificationAdapterReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_waiver_notification_adapter_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn waiver_notification_adapter_receipts(
        &self,
    ) -> Result<Vec<WaiverNotificationAdapterReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.waiver_notification_adapter_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_live_secret_connector_plan(
        &mut self,
        plan: &LiveSecretConnectorPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_secret_connector_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn live_secret_connector_plans(
        &self,
    ) -> Result<Vec<LiveSecretConnectorPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.live_secret_connector_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_live_secret_connector_receipt(
        &mut self,
        receipt: &LiveSecretConnectorReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_live_secret_connector_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn live_secret_connector_receipts(
        &self,
    ) -> Result<Vec<LiveSecretConnectorReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.live_secret_connector_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_token_exchange_worker_plan(
        &mut self,
        plan: &GitHubTokenExchangeWorkerPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_token_exchange_worker_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_token_exchange_worker_plans(
        &self,
    ) -> Result<Vec<GitHubTokenExchangeWorkerPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_token_exchange_worker_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_github_token_exchange_worker_receipt(
        &mut self,
        receipt: &GitHubTokenExchangeWorkerReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_github_token_exchange_worker_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn github_token_exchange_worker_receipts(
        &self,
    ) -> Result<Vec<GitHubTokenExchangeWorkerReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.github_token_exchange_worker_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_audit_log_collector_plan(
        &mut self,
        plan: &KubernetesAuditLogCollectorPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_audit_log_collector_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_audit_log_collector_plans(
        &self,
    ) -> Result<Vec<KubernetesAuditLogCollectorPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_audit_log_collector_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_audit_log_collector_report(
        &mut self,
        report: &KubernetesAuditLogCollectorReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_audit_log_collector_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_audit_log_collector_reports(
        &self,
    ) -> Result<Vec<KubernetesAuditLogCollectorReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_audit_log_collector_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_notification_delivery_client_plan(
        &mut self,
        plan: &NotificationDeliveryClientPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_notification_delivery_client_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn notification_delivery_client_plans(
        &self,
    ) -> Result<Vec<NotificationDeliveryClientPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.notification_delivery_client_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_notification_delivery_client_receipt(
        &mut self,
        receipt: &NotificationDeliveryClientReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_notification_delivery_client_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn notification_delivery_client_receipts(
        &self,
    ) -> Result<Vec<NotificationDeliveryClientReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.notification_delivery_client_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_connector_orchestration_plan(
        &mut self,
        plan: &ConnectorOrchestrationPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_connector_orchestration_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn connector_orchestration_plans(
        &self,
    ) -> Result<Vec<ConnectorOrchestrationPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.connector_orchestration_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_connector_orchestration_report(
        &mut self,
        report: &ConnectorOrchestrationReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_connector_orchestration_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn connector_orchestration_reports(
        &self,
    ) -> Result<Vec<ConnectorOrchestrationReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.connector_orchestration_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_audit_source_adapter_plan(
        &mut self,
        plan: &KubernetesAuditSourceAdapterPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_audit_source_adapter_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_audit_source_adapter_plans(
        &self,
    ) -> Result<Vec<KubernetesAuditSourceAdapterPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_audit_source_adapter_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_kubernetes_audit_source_adapter_receipt(
        &mut self,
        receipt: &KubernetesAuditSourceAdapterReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_kubernetes_audit_source_adapter_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn kubernetes_audit_source_adapter_receipts(
        &self,
    ) -> Result<Vec<KubernetesAuditSourceAdapterReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.kubernetes_audit_source_adapter_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_notification_provider_delivery_plan(
        &mut self,
        plan: &NotificationProviderDeliveryPlan,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_notification_provider_delivery_plan(plan),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn notification_provider_delivery_plans(
        &self,
    ) -> Result<Vec<NotificationProviderDeliveryPlan>, MindError> {
        match self {
            Self::Sqlite(store) => store.notification_provider_delivery_plans(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_notification_provider_delivery_receipt(
        &mut self,
        receipt: &NotificationProviderDeliveryReceipt,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_notification_provider_delivery_receipt(receipt),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn notification_provider_delivery_receipts(
        &self,
    ) -> Result<Vec<NotificationProviderDeliveryReceipt>, MindError> {
        match self {
            Self::Sqlite(store) => store.notification_provider_delivery_receipts(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
    pub(super) fn record_action_promotion_gate_report(
        &mut self,
        report: &ActionPromotionGateReport,
    ) -> Result<(), MindError> {
        match self {
            Self::Sqlite(store) => store.record_action_promotion_gate_report(report),
            Self::Memory(_) | Self::Jsonl(_) => Ok(()),
        }
    }
    pub(super) fn action_promotion_gate_reports(
        &self,
    ) -> Result<Vec<ActionPromotionGateReport>, MindError> {
        match self {
            Self::Sqlite(store) => store.action_promotion_gate_reports(),
            Self::Memory(_) | Self::Jsonl(_) => Ok(Vec::new()),
        }
    }
}
impl AppendOnlyEventStore for RuntimeEventStore {
    fn append(&mut self, commit: Commit) -> Result<EventRecord, MindError> {
        match self {
            Self::Memory(s) => s.append(commit),
            Self::Jsonl(s) => s.append(commit),
            Self::Sqlite(s) => s.append(commit),
        }
    }
    fn records_for_mind(&self, mind_id: MindId) -> Result<Vec<EventRecord>, MindError> {
        match self {
            Self::Memory(s) => s.records_for_mind(mind_id),
            Self::Jsonl(s) => s.records_for_mind(mind_id),
            Self::Sqlite(s) => s.records_for_mind(mind_id),
        }
    }
    fn all_records(&self) -> Result<Vec<EventRecord>, MindError> {
        match self {
            Self::Memory(s) => s.all_records(),
            Self::Jsonl(s) => s.all_records(),
            Self::Sqlite(s) => s.all_records(),
        }
    }
    fn signature_requirement(&self) -> SignatureRequirement {
        match self {
            Self::Memory(s) => s.signature_requirement(),
            Self::Jsonl(s) => s.signature_requirement(),
            Self::Sqlite(s) => s.signature_requirement(),
        }
    }
}

impl ReplicatedEventStore for RuntimeEventStore {
    fn append_replicated_records(&mut self, records: Vec<EventRecord>) -> Result<usize, MindError> {
        match self {
            Self::Memory(s) => s.append_replicated_records(records),
            Self::Jsonl(s) => s.append_replicated_records(records),
            Self::Sqlite(s) => s.append_replicated_records(records),
        }
    }
}

pub(super) enum RuntimeSnapshotStore {
    Memory(InMemorySnapshotStore),
    Jsonl(JsonlSnapshotStore),
    Sqlite(SqliteEventStore),
}
impl RuntimeSnapshotStore {
    pub(super) fn from_env(signature_requirement: SignatureRequirement) -> Result<Self, MindError> {
        if let Ok(path) = env::var("MIND_SNAPSHOT_DB") {
            if !path.trim().is_empty() {
                return Ok(Self::Sqlite(
                    SqliteEventStore::open(path.trim())?
                        .with_signature_requirement(signature_requirement),
                ));
            }
        }
        if let Ok(path) = env::var("MIND_EVENT_DB") {
            if !path.trim().is_empty() {
                return Ok(Self::Sqlite(
                    SqliteEventStore::open(path.trim())?
                        .with_signature_requirement(signature_requirement),
                ));
            }
        }
        match env::var("MIND_SNAPSHOT_LOG") {
            Ok(path) if !path.trim().is_empty() => Ok(Self::Jsonl(JsonlSnapshotStore::new(path)?)),
            _ => Ok(Self::Memory(InMemorySnapshotStore::new())),
        }
    }
}
impl SnapshotStore for RuntimeSnapshotStore {
    fn save_snapshot(&mut self, snapshot: SnapshotRecord) -> Result<SnapshotRecord, MindError> {
        match self {
            Self::Memory(s) => s.save_snapshot(snapshot),
            Self::Jsonl(s) => s.save_snapshot(snapshot),
            Self::Sqlite(s) => s.save_snapshot(snapshot),
        }
    }
    fn latest_snapshot_for_mind(
        &self,
        mind_id: MindId,
    ) -> Result<Option<SnapshotRecord>, MindError> {
        match self {
            Self::Memory(s) => s.latest_snapshot_for_mind(mind_id),
            Self::Jsonl(s) => s.latest_snapshot_for_mind(mind_id),
            Self::Sqlite(s) => s.latest_snapshot_for_mind(mind_id),
        }
    }
    fn snapshots_for_mind(&self, mind_id: MindId) -> Result<Vec<SnapshotRecord>, MindError> {
        match self {
            Self::Memory(s) => s.snapshots_for_mind(mind_id),
            Self::Jsonl(s) => s.snapshots_for_mind(mind_id),
            Self::Sqlite(s) => s.snapshots_for_mind(mind_id),
        }
    }
}
impl CompactingSnapshotStore for RuntimeSnapshotStore {
    fn delete_snapshot(
        &mut self,
        mind_id: MindId,
        snapshot_id: mind_core::EventId,
    ) -> Result<bool, MindError> {
        match self {
            Self::Memory(s) => s.delete_snapshot(mind_id, snapshot_id),
            Self::Jsonl(s) => s.delete_snapshot(mind_id, snapshot_id),
            Self::Sqlite(s) => s.delete_snapshot(mind_id, snapshot_id),
        }
    }
}

pub(super) enum RuntimeObservabilitySink {
    Memory(InMemoryObservabilitySink),
    Jsonl(JsonlObservabilitySink),
    Sqlite(SqliteEventStore),
    Null(NullObservabilitySink),
}
impl RuntimeObservabilitySink {
    pub(super) fn from_env() -> Result<Self, MindError> {
        if let Ok(value) = env::var("MIND_OBSERVABILITY") {
            if matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "off" | "false" | "0"
            ) {
                return Ok(Self::Null(NullObservabilitySink));
            }
        }
        if let Ok(path) = env::var("MIND_OBSERVABILITY_DB") {
            if !path.trim().is_empty() {
                return Ok(Self::Sqlite(SqliteEventStore::open(path.trim())?));
            }
        }
        if let Ok(path) = env::var("MIND_EVENT_DB") {
            if !path.trim().is_empty()
                && matches!(env::var("MIND_OBSERVABILITY_USE_EVENT_DB"), Ok(value) if is_truthy(&value))
            {
                return Ok(Self::Sqlite(SqliteEventStore::open(path.trim())?));
            }
        }
        match env::var("MIND_OBSERVABILITY_LOG") {
            Ok(path) if !path.trim().is_empty() => {
                Ok(Self::Jsonl(JsonlObservabilitySink::new(path)?))
            }
            _ => Ok(Self::Memory(InMemoryObservabilitySink::new())),
        }
    }
}
impl ObservabilitySink for RuntimeObservabilitySink {
    fn record_trace(&mut self, event: mind_core::ObservabilityEvent) -> Result<(), MindError> {
        match self {
            Self::Memory(s) => s.record_trace(event),
            Self::Jsonl(s) => s.record_trace(event),
            Self::Sqlite(s) => s.record_trace(event),
            Self::Null(s) => s.record_trace(event),
        }
    }
    fn record_audit(&mut self, event: AuditEvent) -> Result<(), MindError> {
        match self {
            Self::Memory(s) => s.record_audit(event),
            Self::Jsonl(s) => s.record_audit(event),
            Self::Sqlite(s) => s.record_audit(event),
            Self::Null(s) => s.record_audit(event),
        }
    }
    fn trace_events(&self) -> Result<Vec<mind_core::ObservabilityEvent>, MindError> {
        match self {
            Self::Memory(s) => s.trace_events(),
            Self::Jsonl(s) => s.trace_events(),
            Self::Sqlite(s) => s.trace_events(),
            Self::Null(s) => s.trace_events(),
        }
    }
    fn audit_events(&self) -> Result<Vec<AuditEvent>, MindError> {
        match self {
            Self::Memory(s) => s.audit_events(),
            Self::Jsonl(s) => s.audit_events(),
            Self::Sqlite(s) => s.audit_events(),
            Self::Null(s) => s.audit_events(),
        }
    }
}
