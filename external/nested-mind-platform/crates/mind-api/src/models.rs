//! Purpose: request and query model boundary for the Nested Mind API.
//! Governance scope: API payload deserialization contracts and serde defaults.
//! Dependencies: serde deserialization, API-local default helpers, and mind-core request contracts.
//! Invariants: payload defaults remain explicit; model fields are visible only to sibling API modules.

use serde::Deserialize;

use super::*;

#[derive(Debug, Deserialize)]
pub(super) struct ProjectionQuery {
    #[serde(default)]
    pub(super) scope: ProjectionScope,
}
#[derive(Debug, Deserialize)]
pub(super) struct AuditQuery {
    #[serde(default)]
    pub(super) from_snapshot: bool,
}
#[derive(Debug, Deserialize)]
pub(super) struct TelemetryExportQuery {
    #[serde(default)]
    pub(super) format: TelemetryExportFormat,
    #[serde(default = "default_true")]
    pub(super) include_traces: bool,
    #[serde(default = "default_true")]
    pub(super) include_audits: bool,
    #[serde(default)]
    pub(super) limit: Option<usize>,
}
#[derive(Debug, Deserialize)]
pub(super) struct PatchRequest {
    #[serde(default)]
    pub(super) actor: Option<String>,
    pub(super) reason: String,
    pub(super) ops: Vec<PatchOp>,
}
#[derive(Debug, Deserialize)]
pub(super) struct ChildRequest {
    #[serde(default)]
    pub(super) actor: Option<String>,
    pub(super) reason: String,
    pub(super) kind: String,
}
#[derive(Debug, Deserialize)]
pub(super) struct LawbookMigrationRequest {
    #[serde(default)]
    pub(super) actor: Option<String>,
    pub(super) reason: String,
    pub(super) operations: Vec<LawbookMigrationOp>,
    #[serde(default)]
    pub(super) allow_foundation_removal: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct JwtVerificationRequest {
    pub(super) jwt: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct SignedUrlBackupRequest {
    #[serde(default = "default_cloud_provider")]
    pub(super) provider: CloudObjectProvider,
    pub(super) url: String,
    pub(super) bucket: String,
    pub(super) key: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct ScheduleJobRequest {
    pub(super) kind: ScheduledJobKind,
    pub(super) target: String,
    #[serde(default)]
    pub(super) payload: serde_json::Value,
    #[serde(default)]
    pub(super) due_in_seconds: u64,
    #[serde(default = "default_job_attempts")]
    pub(super) max_attempts: u32,
}

#[derive(Debug, Deserialize)]
pub(super) struct DueJobsRequest {
    #[serde(default = "default_scheduler_poll_limit")]
    pub(super) limit: usize,
}

#[derive(Debug, Deserialize)]
pub(super) struct SchedulerClaimRequest {
    pub(super) worker_id: String,
    #[serde(default = "default_scheduler_poll_limit")]
    pub(super) limit: usize,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub(super) struct WorkerRunRequest {
    pub(super) worker_id: String,
    #[serde(default = "default_scheduler_poll_limit")]
    pub(super) limit: usize,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
    #[serde(default)]
    pub(super) execute_and_mark_succeeded: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct WorkerTickRequest {
    pub(super) worker_id: String,
    #[serde(default = "default_scheduler_poll_limit")]
    pub(super) limit: usize,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
    #[serde(default)]
    pub(super) execute_and_mark_succeeded: bool,
    #[serde(default)]
    pub(super) tick_index: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub(super) struct JobExecutionReceiptRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease: Option<SchedulerLeaseRecord>,
    #[serde(default)]
    pub(super) execute_and_mark_succeeded: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct DistributedLeaseClaimApiRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub(super) struct DomainJobExecutionRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease: Option<SchedulerLeaseRecord>,
    #[serde(default)]
    pub(super) execute_and_mark_succeeded: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct LiveDomainJobExecutionRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease: Option<SchedulerLeaseRecord>,
    #[serde(default)]
    pub(super) mode: Option<LiveDomainJobExecutorMode>,
}

#[derive(Debug, Deserialize)]
pub(super) struct DistributedLeaseAdapterClaimApiRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub(super) struct DistributedLeaseExecutionApiRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    #[serde(default)]
    pub(super) lease_seconds: Option<u64>,
    #[serde(default)]
    pub(super) mode: Option<DistributedLeaseExecutionMode>,
}

#[derive(Debug, Deserialize)]
pub(super) struct NativeProviderExecutionApiRequest {
    pub(super) request: ProviderExecutionRequest,
    #[serde(default)]
    pub(super) allow_dry_run: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct ProviderSdkExecutionApiRequest {
    pub(super) request: ProviderExecutionRequest,
    #[serde(default)]
    pub(super) policy: Option<ProviderSdkExecutionPolicy>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConsensusRetentionEnforcementRequest {
    pub(super) decision: ConsensusLogCompactionDecision,
    pub(super) backup_verification: BackupVerificationReport,
    #[serde(default)]
    pub(super) delete_apply_reports: bool,
    #[serde(default)]
    pub(super) keep_latest_apply_reports: Option<usize>,
    #[serde(default)]
    pub(super) apply: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConsensusRetentionApprovalApiRequest {
    pub(super) plan: ConsensusRetentionEnforcementPlan,
    #[serde(default)]
    pub(super) proposed_by: Option<String>,
    #[serde(default)]
    pub(super) votes: Vec<ConsensusRetentionApprovalVote>,
    #[serde(default)]
    pub(super) minimum_approvals: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub(super) struct PhysicalConsensusCompactionRequest {
    pub(super) decision: ConsensusLogCompactionDecision,
    pub(super) backup_verification: BackupVerificationReport,
    #[serde(default)]
    pub(super) apply: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConsensusLogCompactionRequest {
    #[serde(default)]
    pub(super) keep_latest_committed: Option<usize>,
    #[serde(default)]
    pub(super) min_committed_entries_between_compactions: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConsensusApplyRequest {
    pub(super) certificate: ConsensusCommitCertificate,
    #[serde(default)]
    pub(super) follower_id: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConsensusCommitRequest {
    pub(super) operation_kind: String,
    #[serde(default)]
    pub(super) operation: serde_json::Value,
    #[serde(default)]
    pub(super) voters: Vec<String>,
    #[serde(default)]
    pub(super) previous_entry_hash: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ChaosRehearsalApiRequest {
    #[serde(default)]
    pub(super) mind_id: Option<MindId>,
}

#[derive(Debug, Deserialize)]
pub(super) struct InvariantFuzzApiRequest {
    #[serde(default)]
    pub(super) mind_id: Option<MindId>,
    #[serde(default)]
    pub(super) config: Option<InvariantFuzzRunConfig>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ReadinessGateApiRequest {
    pub(super) creative_report: CreativeEngineeringReport,
    #[serde(default)]
    pub(super) chaos_plan: Option<ChaosRehearsalPlan>,
    #[serde(default)]
    pub(super) fuzz_report: Option<InvariantFuzzRunReport>,
    #[serde(default)]
    pub(super) policy: Option<ProductionReadinessGatePolicy>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ChaosExecutionApiRequest {
    pub(super) plan: ChaosRehearsalPlan,
    #[serde(default)]
    pub(super) mode: Option<ChaosExecutionMode>,
}

#[derive(Debug, Deserialize)]
pub(super) struct InvariantFuzzExecutionApiRequest {
    pub(super) report: InvariantFuzzRunReport,
    #[serde(default)]
    pub(super) config: Option<InvariantFuzzHarnessConfig>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ReadinessWaiverProposalApiRequest {
    pub(super) gate: ProductionReadinessGateReport,
    #[serde(default)]
    pub(super) blocker_ids: Vec<mind_core::EventId>,
    pub(super) proposed_by: String,
    pub(super) reason: String,
    pub(super) risk_owner: String,
    #[serde(default)]
    pub(super) expires_in_seconds: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ReadinessWaiverCertificateApiRequest {
    pub(super) proposal: ReadinessWaiverProposal,
    #[serde(default)]
    pub(super) votes: Vec<ReadinessWaiverVote>,
    #[serde(default = "default_required_approvals")]
    pub(super) required_approvals: usize,
}

#[derive(Debug, Deserialize)]
pub(super) struct ReadinessWaiverApplicationApiRequest {
    pub(super) gate: ProductionReadinessGateReport,
    #[serde(default)]
    pub(super) certificates: Vec<ReadinessWaiverCertificate>,
}

#[derive(Debug, Deserialize)]
pub(super) struct EngineeringImplementationJobsApiRequest {
    pub(super) report: CreativeEngineeringReport,
    #[serde(default = "default_engineering_job_limit")]
    pub(super) limit: usize,
    #[serde(default)]
    pub(super) due_in_seconds: i64,
}

#[derive(Debug, Deserialize)]
pub(super) struct StagingChaosApiRequest {
    pub(super) plan: ChaosRehearsalPlan,
    pub(super) environment: StagingChaosEnvironment,
    #[serde(default)]
    pub(super) mode: Option<StagingChaosRunMode>,
    #[serde(default)]
    pub(super) policy: Option<StagingChaosSafetyPolicy>,
}

#[derive(Debug, Deserialize)]
pub(super) struct MandatoryCiGateApiRequest {
    pub(super) input: MandatoryCiGateInput,
    #[serde(default)]
    pub(super) policy: Option<MandatoryCiGatePolicy>,
}

#[derive(Debug, Deserialize)]
pub(super) struct MultiOperatorWaiverApiRequest {
    pub(super) proposal: ReadinessWaiverProposal,
    pub(super) gate: ProductionReadinessGateReport,
    #[serde(default)]
    pub(super) votes: Vec<MultiOperatorWaiverVote>,
    #[serde(default)]
    pub(super) policy: Option<MultiOperatorWaiverPolicy>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ImplementationEvidenceApiRequest {
    pub(super) job: EngineeringImplementationJob,
    #[serde(default)]
    pub(super) artifacts: Vec<ImplementationEvidenceArtifact>,
    #[serde(default)]
    pub(super) required_kinds: Vec<ImplementationEvidenceKind>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ImplementationEvidenceAutomationApiRequest {
    pub(super) plan: EngineeringImplementationJobPlan,
    pub(super) repository: String,
    #[serde(default = "default_base_branch")]
    pub(super) base_branch: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubEvidenceApiRequest {
    pub(super) pull_request: GitHubPullRequestEvidence,
    #[serde(default)]
    pub(super) check_runs: Vec<GitHubCheckRunEvidence>,
    #[serde(default)]
    pub(super) required_check_names: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionPolicyApiRequest {
    pub(super) repository: String,
    #[serde(default = "default_base_branch")]
    pub(super) branch: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionEvaluationApiRequest {
    pub(super) policy: BranchProtectionPolicy,
    pub(super) observed: BranchProtectionObservedState,
}

#[derive(Debug, Deserialize)]
pub(super) struct LiveStagingChaosAdapterApiRequest {
    pub(super) rehearsal: ChaosRehearsalPlan,
    #[serde(default)]
    pub(super) staging_report: Option<StagingChaosRunReport>,
    #[serde(default)]
    pub(super) backend: Option<LiveChaosAdapterBackend>,
    #[serde(default)]
    pub(super) mode: Option<LiveChaosAdapterMode>,
}

#[derive(Debug, Deserialize)]
pub(super) struct LiveStagingChaosAdapterReceiptApiRequest {
    pub(super) plan: LiveStagingChaosAdapterPlan,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverReviewCertificateApiRequest {
    pub(super) item: WaiverReviewQueueItem,
    #[serde(default)]
    pub(super) comments: Vec<WaiverReviewComment>,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubCheckRunWritePlanApiRequest {
    pub(super) repository: String,
    pub(super) head_sha: String,
    pub(super) name: String,
    pub(super) output: GitHubCheckRunOutput,
    #[serde(default)]
    pub(super) conclusion: Option<mind_core::GitHubCheckConclusion>,
    #[serde(default)]
    pub(super) details_url: Option<String>,
    #[serde(default)]
    pub(super) external_id: Option<String>,
    #[serde(default = "default_github_app_slug")]
    pub(super) app_slug: String,
    #[serde(default)]
    pub(super) mode: GitHubCheckRunWriteMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubCheckRunWriteReceiptApiRequest {
    pub(super) plan: GitHubCheckRunWritePlan,
    #[serde(default)]
    pub(super) github_check_run_id: Option<u64>,
    #[serde(default)]
    pub(super) html_url: Option<String>,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionReconcileApiRequest {
    pub(super) policy: BranchProtectionPolicy,
    #[serde(default)]
    pub(super) observed: Option<BranchProtectionObservedState>,
    #[serde(default)]
    pub(super) mode: BranchProtectionReconcileMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionReconcileReceiptApiRequest {
    pub(super) plan: BranchProtectionReconcilePlan,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesStagingChaosPlanApiRequest {
    pub(super) rehearsal: ChaosRehearsalPlan,
    #[serde(default)]
    pub(super) adapter_plan: Option<LiveStagingChaosAdapterPlan>,
    #[serde(default = "default_staging_namespace")]
    pub(super) namespace: String,
    #[serde(default = "default_chaos_service_account")]
    pub(super) service_account: String,
    #[serde(default)]
    pub(super) mode: KubernetesChaosExecutionMode,
    #[serde(default)]
    pub(super) approval_certificate_hash: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesStagingChaosReceiptApiRequest {
    pub(super) plan: KubernetesStagingChaosPlan,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverReviewerAssignmentApiRequest {
    pub(super) item: WaiverReviewQueueItem,
    #[serde(default)]
    pub(super) candidates: Vec<WaiverReviewerCandidate>,
    #[serde(default)]
    pub(super) escalation_targets: BTreeMap<mind_core::WaiverOperatorRole, String>,
    #[serde(default = "default_escalation_after_hours")]
    pub(super) escalation_after_hours: i64,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverEscalationApiRequest {
    pub(super) plan: WaiverReviewerAssignmentPlan,
    pub(super) reason: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubAppInstallationTokenApiRequest {
    pub(super) app_id: u64,
    pub(super) installation_id: u64,
    pub(super) repository: String,
    pub(super) private_key_fingerprint: String,
    #[serde(default)]
    pub(super) permissions: BTreeMap<String, String>,
    #[serde(default)]
    pub(super) repositories: Vec<String>,
    #[serde(default = "default_github_token_ttl_seconds")]
    pub(super) token_ttl_seconds: i64,
    #[serde(default)]
    pub(super) mode: GitHubAppTokenMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubAppInstallationTokenReceiptApiRequest {
    pub(super) plan: GitHubAppInstallationTokenPlan,
    #[serde(default)]
    pub(super) token_fingerprint: Option<String>,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubActionExecutionPlanApiRequest {
    pub(super) token_plan: GitHubAppInstallationTokenPlan,
    #[serde(default)]
    pub(super) check_run_plan: Option<GitHubCheckRunWritePlan>,
    #[serde(default)]
    pub(super) branch_protection_plan: Option<BranchProtectionReconcilePlan>,
    #[serde(default)]
    pub(super) mode: GitHubActionExecutionMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubActionExecutionReceiptApiRequest {
    pub(super) plan: GitHubActionExecutionPlan,
    pub(super) token_receipt: GitHubAppInstallationTokenReceipt,
    #[serde(default)]
    pub(super) http_status: Option<u16>,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionWorkerPlanApiRequest {
    pub(super) plans: Vec<BranchProtectionReconcilePlan>,
    #[serde(default)]
    pub(super) mode: BranchProtectionWorkerMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct BranchProtectionWorkerReportApiRequest {
    pub(super) plan: BranchProtectionWorkerPlan,
    #[serde(default)]
    pub(super) receipts: Vec<BranchProtectionReconcileReceipt>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesDryRunExecutionApiRequest {
    pub(super) plan: KubernetesStagingChaosPlan,
    #[serde(default = "default_kubernetes_context")]
    pub(super) context_name: String,
    #[serde(default = "default_kubernetes_field_manager")]
    pub(super) field_manager: String,
    #[serde(default)]
    pub(super) response_payload: Option<serde_json::Value>,
    #[serde(default)]
    pub(super) warnings: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverNotificationPlanApiRequest {
    pub(super) assignment: WaiverReviewerAssignmentPlan,
    #[serde(default)]
    pub(super) channel: Option<WaiverNotificationChannel>,
    pub(super) subject: String,
    pub(super) body: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverNotificationReceiptApiRequest {
    pub(super) plan: WaiverNotificationPlan,
    #[serde(default)]
    pub(super) delivered_to: Vec<String>,
    #[serde(default)]
    pub(super) provider_message_id: Option<String>,
    #[serde(default)]
    pub(super) response_hash: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct SecretAccessApiRequest {
    pub(super) backend: SecretManagerBackend,
    pub(super) locator: String,
    pub(super) key_id: String,
    pub(super) purpose: String,
    #[serde(default)]
    pub(super) mode: SecretAccessMode,
    #[serde(default)]
    pub(super) allowed_fingerprint: Option<String>,
    #[serde(default)]
    pub(super) version: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct SecretAccessReceiptApiRequest {
    pub(super) plan: SecretAccessPlan,
    #[serde(default)]
    pub(super) material_fingerprint: Option<String>,
    #[serde(default)]
    pub(super) secret_version: Option<String>,
    #[serde(default)]
    pub(super) metadata: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubAppJwtPlanApiRequest {
    pub(super) app_id: u64,
    pub(super) installation_id: u64,
    pub(super) secret_plan: SecretAccessPlan,
    #[serde(default = "default_github_jwt_ttl")]
    pub(super) ttl_seconds: i64,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubAppJwtReceiptApiRequest {
    pub(super) plan: GitHubAppJwtPlan,
    pub(super) secret_receipt: SecretAccessReceipt,
    #[serde(default)]
    pub(super) jwt_fingerprint: Option<String>,
    #[serde(default)]
    pub(super) signer_response_hash: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConnectorWorkerPlanApiRequest {
    pub(super) job: ScheduledJob,
    pub(super) worker_id: String,
    pub(super) action_kind: ConnectorWorkerActionKind,
    #[serde(default)]
    pub(super) mode: ConnectorWorkerMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConnectorWorkerReceiptApiRequest {
    pub(super) plan: ConnectorWorkerJobPlan,
    #[serde(default)]
    pub(super) external_receipt_hash: Option<String>,
    #[serde(default)]
    pub(super) response_hash: Option<String>,
    #[serde(default)]
    pub(super) errors: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesAdmissionAuditApiRequest {
    pub(super) dry_run_request: KubernetesDryRunExecutionRequest,
    pub(super) dry_run_receipt: KubernetesDryRunExecutionReceipt,
    pub(super) operation: KubernetesAdmissionOperation,
    pub(super) object_hash: String,
    pub(super) user: String,
    #[serde(default)]
    pub(super) audit_uid: Option<String>,
    #[serde(default)]
    pub(super) annotations: BTreeMap<String, String>,
    #[serde(default)]
    pub(super) warnings: Vec<String>,
    #[serde(default = "default_true")]
    pub(super) admitted: bool,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverNotificationAdapterPlanApiRequest {
    pub(super) notification_plan: WaiverNotificationPlan,
    pub(super) adapter_kind: WaiverNotificationAdapterKind,
    pub(super) endpoint_reference: String,
    pub(super) request_template_hash: String,
    #[serde(default)]
    pub(super) mode: WaiverNotificationAdapterMode,
}

#[derive(Debug, Deserialize)]
pub(super) struct WaiverNotificationAdapterReceiptApiRequest {
    pub(super) adapter_plan: WaiverNotificationAdapterPlan,
    #[serde(default)]
    pub(super) notification_receipt: Option<WaiverNotificationReceipt>,
    #[serde(default)]
    pub(super) provider_message_id: Option<String>,
    #[serde(default)]
    pub(super) provider_response_hash: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct LiveSecretConnectorPlanApiRequest {
    pub(super) access_plan: SecretAccessPlan,
    #[serde(default)]
    pub(super) mode: LiveSecretConnectorMode,
    #[serde(default)]
    pub(super) request_template: serde_json::Value,
}

#[derive(Debug, Deserialize)]
pub(super) struct LiveSecretConnectorReceiptApiRequest {
    pub(super) plan: LiveSecretConnectorPlan,
    pub(super) access_receipt: SecretAccessReceipt,
    #[serde(default)]
    pub(super) provider_request_id: Option<String>,
    #[serde(default)]
    pub(super) provider_response_hash: Option<String>,
    #[serde(default)]
    pub(super) warnings: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubTokenExchangeWorkerPlanApiRequest {
    pub(super) repository: String,
    pub(super) installation_id: u64,
    pub(super) jwt_receipt: GitHubAppJwtReceipt,
    pub(super) secret_connector: LiveSecretConnectorReceipt,
    #[serde(default)]
    pub(super) mode: GitHubTokenExchangeWorkerMode,
    pub(super) permissions_hash: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct GitHubTokenExchangeWorkerReceiptApiRequest {
    pub(super) plan: GitHubTokenExchangeWorkerPlan,
    pub(super) token_receipt: GitHubAppInstallationTokenReceipt,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesAuditLogCollectorPlanApiRequest {
    pub(super) admission_report: KubernetesAdmissionAuditReport,
    pub(super) namespace: String,
    #[serde(default)]
    pub(super) mode: KubernetesAuditLogCollectorMode,
    #[serde(default)]
    pub(super) previous_watermark: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesAuditLogCollectorReportApiRequest {
    pub(super) plan: KubernetesAuditLogCollectorPlan,
    pub(super) admission_receipt: KubernetesAdmissionAuditReceipt,
    pub(super) observed_event_count: u64,
    #[serde(default)]
    pub(super) audit_uids: Vec<String>,
    #[serde(default)]
    pub(super) new_watermark: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct NotificationDeliveryClientPlanApiRequest {
    pub(super) adapter_plan: WaiverNotificationAdapterPlan,
    #[serde(default)]
    pub(super) mode: NotificationDeliveryClientMode,
    pub(super) endpoint_reference: String,
    #[serde(default)]
    pub(super) request_template: serde_json::Value,
}

#[derive(Debug, Deserialize)]
pub(super) struct NotificationDeliveryClientReceiptApiRequest {
    pub(super) plan: NotificationDeliveryClientPlan,
    pub(super) adapter_receipt: WaiverNotificationAdapterReceipt,
    #[serde(default)]
    pub(super) provider_message_id: Option<String>,
    #[serde(default)]
    pub(super) provider_response_hash: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConnectorOrchestrationPlanApiRequest {
    pub(super) worker_id: String,
    pub(super) purpose: String,
    #[serde(default)]
    pub(super) mode: ConnectorOrchestrationMode,
    #[serde(default)]
    pub(super) required_artifacts: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ConnectorOrchestrationReportApiRequest {
    pub(super) plan: ConnectorOrchestrationPlan,
    #[serde(default)]
    pub(super) secret_receipts: Vec<LiveSecretConnectorReceipt>,
    #[serde(default)]
    pub(super) token_receipts: Vec<GitHubTokenExchangeWorkerReceipt>,
    #[serde(default)]
    pub(super) audit_reports: Vec<KubernetesAuditLogCollectorReport>,
    #[serde(default)]
    pub(super) notification_receipts: Vec<NotificationDeliveryClientReceipt>,
    #[serde(default)]
    pub(super) external_artifacts: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesAuditSourceAdapterPlanApiRequest {
    pub(super) collector_plan: KubernetesAuditLogCollectorPlan,
    pub(super) kind: KubernetesAuditSourceKind,
    #[serde(default)]
    pub(super) mode: KubernetesAuditSourceAdapterMode,
    pub(super) source_reference: String,
    #[serde(default)]
    pub(super) request_template: serde_json::Value,
}

#[derive(Debug, Deserialize)]
pub(super) struct KubernetesAuditSourceAdapterReceiptApiRequest {
    pub(super) plan: KubernetesAuditSourceAdapterPlan,
    pub(super) collector_report: KubernetesAuditLogCollectorReport,
    #[serde(default)]
    pub(super) provider_response_hash: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct NotificationProviderDeliveryPlanApiRequest {
    pub(super) client_plan: NotificationDeliveryClientPlan,
    pub(super) provider_kind: NotificationProviderKind,
    #[serde(default)]
    pub(super) mode: NotificationProviderDeliveryMode,
    pub(super) endpoint_reference: String,
    #[serde(default)]
    pub(super) request_template: serde_json::Value,
}

#[derive(Debug, Deserialize)]
pub(super) struct NotificationProviderDeliveryReceiptApiRequest {
    pub(super) plan: NotificationProviderDeliveryPlan,
    pub(super) client_receipt: NotificationDeliveryClientReceipt,
    #[serde(default)]
    pub(super) provider_message_id: Option<String>,
    #[serde(default)]
    pub(super) provider_response_hash: Option<String>,
    #[serde(default)]
    pub(super) failures: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ActionPromotionGateApiRequest {
    #[serde(default)]
    pub(super) policy: ActionPromotionGatePolicy,
    pub(super) orchestration: ConnectorOrchestrationReport,
    #[serde(default)]
    pub(super) audit_source_receipts: Vec<KubernetesAuditSourceAdapterReceipt>,
    #[serde(default)]
    pub(super) notification_provider_receipts: Vec<NotificationProviderDeliveryReceipt>,
}

fn default_github_jwt_ttl() -> i64 {
    540
}

fn default_required_approvals() -> usize {
    1
}
fn default_engineering_job_limit() -> usize {
    5
}
fn default_base_branch() -> String {
    "main".to_owned()
}
fn default_github_app_slug() -> String {
    "nested-mind-readiness".to_owned()
}
fn default_staging_namespace() -> String {
    "nested-mind-staging".to_owned()
}
fn default_chaos_service_account() -> String {
    "nested-mind-chaos".to_owned()
}
fn default_escalation_after_hours() -> i64 {
    24
}
fn default_github_token_ttl_seconds() -> i64 {
    3600
}
fn default_kubernetes_context() -> String {
    "staging".to_owned()
}
fn default_kubernetes_field_manager() -> String {
    "nested-mind-platform".to_owned()
}

fn default_true() -> bool {
    true
}

fn default_job_attempts() -> u32 {
    3
}

fn default_scheduler_poll_limit() -> usize {
    10
}

fn default_cloud_provider() -> CloudObjectProvider {
    CloudObjectProvider::S3Compatible
}
