mod audit_handlers;
mod auth;
mod backup_handlers;
mod connector_handlers;
mod consensus_handlers;
mod handler_helpers;
mod models;
mod provider_handlers;
mod readiness_handlers;
mod replication_handlers;
mod request_safety;
mod responses;
mod root_handlers;
mod routes;
mod runtime_config;
mod scheduler_handlers;
mod state;
mod stores;
mod system_handlers;
mod worker_handlers;

use audit_handlers::*;
use auth::{AuthConfig, RuntimeOidcDiscovery, RuntimeOidcVerifier};
use axum::{
    body::Body,
    extract::{Query, State},
    http::{
        header::{AUTHORIZATION, CONTENT_LENGTH},
        HeaderMap, HeaderValue, Request, StatusCode,
    },
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use backup_handlers::*;
use connector_handlers::*;
use consensus_handlers::*;
use handler_helpers::*;
use mind_connectors::{
    HttpOidcDiscoveryClient, HttpReplicationTransportClient, HttpSignedUrlObjectClient,
};
use mind_core::{
    apply_certified_replication_batch, apply_certified_replication_batch_idempotent,
    apply_readiness_waivers_to_gate, apply_replication_batch, attach_implementation_evidence,
    certify_consensus_retention_approval, certify_multi_operator_readiness_waiver,
    certify_readiness_waiver, certify_waiver_escalation, certify_waiver_review,
    collect_github_readiness_evidence, default_implementation_evidence_requirements,
    distributed_lease_adapter_registry, domain_job_executor_registry,
    evaluate_action_promotion_gate, evaluate_branch_protection_policy,
    evaluate_connector_orchestration, evaluate_consensus_log_compaction,
    evaluate_distributed_lease_adapter_claim, evaluate_mandatory_ci_gate,
    evaluate_native_provider_request, evaluate_production_readiness_gate,
    execute_chaos_rehearsal_plan, execute_distributed_lease_with_receipt,
    execute_domain_job_with_receipt, execute_invariant_fuzz_run, execute_job_with_receipt,
    execute_live_domain_job, execute_live_staging_chaos_adapter_dry_run,
    execute_native_provider_with_receipt, generate_creative_engineering_report,
    generate_invariant_fuzz_run, live_domain_job_executor_registry,
    native_provider_adapter_registry, plan_branch_protection_action_execution,
    plan_branch_protection_reconcile, plan_branch_protection_reconcile_worker,
    plan_connector_orchestration, plan_connector_worker_job, plan_consensus_retention_enforcement,
    plan_external_distributed_lease_claim, plan_github_app_installation_token,
    plan_github_app_jwt_from_secret, plan_github_check_run_action_execution,
    plan_github_check_run_write, plan_github_token_exchange_worker,
    plan_implementation_evidence_automation, plan_kubernetes_admission_audit,
    plan_kubernetes_audit_log_collector, plan_kubernetes_audit_source_adapter,
    plan_kubernetes_server_dry_run_execution, plan_kubernetes_staging_chaos,
    plan_live_secret_connector, plan_live_staging_chaos_adapter, plan_notification_delivery_client,
    plan_notification_provider_delivery, plan_physical_consensus_compaction, plan_secret_access,
    plan_waiver_notification_adapter, plan_waiver_notification_delivery,
    plan_waiver_reviewer_assignment, production_branch_protection_policy,
    production_chaos_rehearsal_plan, record_branch_protection_reconcile_receipt,
    record_branch_protection_worker_report, record_connector_worker_execution_receipt,
    record_github_action_execution_receipt, record_github_app_installation_token_receipt,
    record_github_app_jwt_receipt, record_github_check_run_write_receipt,
    record_github_token_exchange_worker_receipt, record_kubernetes_admission_audit_receipt,
    record_kubernetes_audit_log_collector_report, record_kubernetes_audit_source_adapter_receipt,
    record_kubernetes_server_dry_run_receipt, record_kubernetes_staging_chaos_receipt,
    record_live_secret_connector_receipt, record_notification_delivery_client_receipt,
    record_notification_provider_delivery_receipt, record_secret_access_receipt,
    record_waiver_notification_adapter_receipt, record_waiver_notification_receipt,
    report_consensus_retention_enforcement_planned, run_staging_chaos_rehearsal,
    schedule_engineering_implementation_jobs, ActionPromotionGatePolicy, ActionPromotionGateReport,
    AppendOnlyEventStore, AuditEvent, AuditEventKind, AuthorizationPolicy, BackupManifest,
    BackupObjectRef, BackupObjectVerificationReport, BackupVerificationReport,
    BranchProtectionEvaluationReport, BranchProtectionObservedState, BranchProtectionPolicy,
    BranchProtectionReconcileMode, BranchProtectionReconcilePlan, BranchProtectionReconcileReceipt,
    BranchProtectionWorkerMode, BranchProtectionWorkerPlan, BranchProtectionWorkerReport,
    ChaosExecutionMode, ChaosExecutionRun, ChaosRehearsalPlan, CloudObjectAdapter,
    CloudObjectProvider, CloudObjectStoreTarget, CloudSignedUrlReceipt, CloudSignedUrlRequest,
    CloudTransferMode, CloudUploadReceipt, ClusterHealthReport, Commit, CompactingSnapshotStore,
    ConnectorOrchestrationMode, ConnectorOrchestrationPlan, ConnectorOrchestrationReport,
    ConnectorWorkerActionKind, ConnectorWorkerExecutionReceipt, ConnectorWorkerJobPlan,
    ConnectorWorkerMode, ConsensusApplyIdempotencyDecision, ConsensusApplyReport,
    ConsensusChangeJudgment, ConsensusChangeProposal, ConsensusCommitCertificate,
    ConsensusCommitVote, ConsensusCompactionBackupGuard, ConsensusLogCompactionDecision,
    ConsensusLogCompactionPolicy, ConsensusLogEntry, ConsensusMember, ConsensusMembership,
    ConsensusPhysicalCompactionReport, ConsensusRetentionApprovalCertificate,
    ConsensusRetentionApprovalPolicy, ConsensusRetentionApprovalProposal,
    ConsensusRetentionApprovalVote, ConsensusRetentionEnforcementPlan,
    ConsensusRetentionEnforcementReport, ConsensusRetentionPolicy, CreativeEngineeringReport,
    CreativeEngineeringReportInput, DistributedEventStorePlan, DistributedLeaseAdapterRegistry,
    DistributedLeaseAdapterReport, DistributedLeaseClaimReceipt, DistributedLeaseExecutionMode,
    DistributedLeaseExecutionReceipt, DistributedLeaseServiceBoundary, DistributedNodeRole,
    DomainJobExecutionReport, Ed25519CommitSigner, EditProposal, EngineeringImplementationJob,
    EngineeringImplementationJobPlan, EventRecord, EventStoreStrategy, EvolutionEngine,
    EvolutionPlan, ExternalIdentityAssertion, FileObjectBackupStore, GitHubActionExecutionMode,
    GitHubActionExecutionPlan, GitHubActionExecutionReceipt, GitHubAppInstallationTokenPlan,
    GitHubAppInstallationTokenReceipt, GitHubAppInstallationTokenRequest, GitHubAppJwtPlan,
    GitHubAppJwtReceipt, GitHubAppTokenMode, GitHubCheckRunEvidence, GitHubCheckRunOutput,
    GitHubCheckRunWriteMode, GitHubCheckRunWritePlan, GitHubCheckRunWriteReceipt,
    GitHubPullRequestEvidence, GitHubReadinessEvidenceBundle, GitHubTokenExchangeWorkerMode,
    GitHubTokenExchangeWorkerPlan, GitHubTokenExchangeWorkerReceipt, Identity,
    IdentityBindingPolicy, IdentitySource, ImplementationEvidenceArtifact,
    ImplementationEvidenceAutomationPlan, ImplementationEvidenceKind,
    ImplementationJobEvidenceBundle, InMemoryEventStore, InMemoryObservabilitySink,
    InMemoryRateLimiter, InMemorySnapshotStore, InvariantFuzzExecutionReport,
    InvariantFuzzHarnessConfig, InvariantFuzzRunConfig, InvariantFuzzRunReport, JobExecutionMode,
    JobExecutionReceipt, JsonlEventStore, JsonlObservabilitySink, JsonlReplicationInbox,
    JsonlSnapshotStore, KubernetesAdmissionAuditPolicy, KubernetesAdmissionAuditReceipt,
    KubernetesAdmissionAuditReport, KubernetesAdmissionAuditRequest, KubernetesAdmissionOperation,
    KubernetesAuditLogCollectorMode, KubernetesAuditLogCollectorPlan,
    KubernetesAuditLogCollectorReport, KubernetesAuditSourceAdapterMode,
    KubernetesAuditSourceAdapterPlan, KubernetesAuditSourceAdapterReceipt,
    KubernetesAuditSourceKind, KubernetesChaosExecutionMode, KubernetesDryRunExecutionReceipt,
    KubernetesDryRunExecutionRequest, KubernetesStagingChaosPlan, KubernetesStagingChaosReceipt,
    LawbookMigration, LawbookMigrationOp, LiveChaosAdapterBackend, LiveChaosAdapterMode,
    LiveDomainJobExecutionReport, LiveDomainJobExecutorMode, LiveOidcRefreshReport,
    LiveSecretConnectorMode, LiveSecretConnectorPlan, LiveSecretConnectorReceipt,
    LiveStagingChaosAdapterPlan, LiveStagingChaosAdapterReceipt, LocalCloudMirrorStore,
    MandatoryCiGateInput, MandatoryCiGatePolicy, MandatoryCiGateReport, Mind, MindAction,
    MindBackup, MindError, MindId, MindProjection, MultiOperatorWaiverCertificate,
    MultiOperatorWaiverPolicy, MultiOperatorWaiverVote, NativeProviderAdapterRegistry,
    NativeProviderAdapterReport, NativeProviderExecutionReceipt, NotificationDeliveryClientMode,
    NotificationDeliveryClientPlan, NotificationDeliveryClientReceipt,
    NotificationProviderDeliveryMode, NotificationProviderDeliveryPlan,
    NotificationProviderDeliveryReceipt, NotificationProviderKind, NullObservabilitySink,
    ObservabilitySink, OidcDiscoveryConfig, OidcDiscoveryDocument, OidcDiscoveryRefreshReport,
    OidcJwksCacheEntry, OidcJwksVerifier, OidcJwksVerifierConfig, OidcJwtVerificationReport,
    PatchOp, Principal, ProductionReadinessGatePolicy, ProductionReadinessGateReport,
    ProjectionPolicy, ProjectionScope, ProviderExecutionReceipt, ProviderExecutionRequest,
    ProviderSdkAdapterReport, ProviderSdkExecutionPolicy, ProviderSdkExecutionReport,
    ProviderSdkFeatureMatrix, ProviderSdkReceipt, ReadinessWaiverApplicationReport,
    ReadinessWaiverCertificate, ReadinessWaiverProposal, ReadinessWaiverVote, ReplayAudit,
    ReplayAuditReport, ReplayEngine, ReplayReport, ReplicatedEventStore, ReplicationBatch,
    ReplicationDeliveryReceipt, ReplicationEndpoint, ReplicationEnvelope, ReplicationRetryPolicy,
    ReplicationTransportPlan, RequestSafetyConfig, Role, ScheduledJob, ScheduledJobKind,
    SchedulerLeaseClaimReport, SchedulerLeasePolicy, SchedulerLeaseRecord, SchedulerPollReport,
    SchemaMigrationReport, SecretAccessMode, SecretAccessPlan, SecretAccessReceipt,
    SecretManagerBackend, SecretReference, SignatureRequirement, SigningBackendKind,
    SigningBackendStatus, SnapshotCompactionDecision, SnapshotCompactionPolicy, SnapshotRecord,
    SnapshotStore, StagingChaosEnvironment, StagingChaosRunMode, StagingChaosRunReport,
    StagingChaosSafetyPolicy, StatePatch, TelemetryExport, TelemetryExportFormat,
    TelemetryExporter, WaiverEscalationCertificate, WaiverNotificationAdapterKind,
    WaiverNotificationAdapterMode, WaiverNotificationAdapterPlan, WaiverNotificationAdapterReceipt,
    WaiverNotificationChannel, WaiverNotificationPlan, WaiverNotificationReceipt,
    WaiverReviewCertificate, WaiverReviewComment, WaiverReviewQueueItem,
    WaiverReviewerAssignmentPlan, WaiverReviewerCandidate, WorkerDaemonConfig,
    WorkerDaemonTickReport, WorkerRunReport, WorkerRuntime, WorkerRuntimeConfig, WorkerRuntimeMode,
    PLATFORM_SCHEMA_VERSION,
};
use mind_store_sqlite::SqliteEventStore;
use models::*;
use provider_handlers::*;
use readiness_handlers::*;
use replication_handlers::*;
use request_safety::*;
use responses::*;
use root_handlers::*;
use runtime_config::*;
use scheduler_handlers::*;
use serde_json::json;
use state::AppState;
use std::{
    collections::{BTreeMap, BTreeSet},
    env,
    net::SocketAddr,
    sync::Arc,
};
use stores::*;
use system_handlers::*;
use time::{Duration, OffsetDateTime};
use tokio::net::TcpListener;
use tracing::info;
use tracing_subscriber::EnvFilter;
use worker_handlers::*;

#[tokio::main]
async fn main() {
    init_tracing_from_env();
    let (root, store, snapshots, observability, signer, signing_status) =
        initialize_runtime().expect("failed to initialize runtime");
    let root_id = root.id();
    let safety_config =
        request_safety_config_from_env().expect("invalid request safety configuration");
    let safety = InMemoryRateLimiter::new(safety_config.clone())
        .expect("invalid request safety configuration");
    let state = AppState::new(
        root,
        store,
        snapshots,
        observability,
        safety,
        safety_config,
        AuthConfig::from_env().expect("invalid authentication configuration"),
        AuthorizationPolicy::production_default(),
        signer,
        signing_status,
        object_backup_store_from_env().expect("invalid object backup store configuration"),
        oidc_discovery_from_env().expect("invalid OIDC discovery configuration"),
        cloud_mirror_from_env().expect("invalid cloud mirror configuration"),
        replication_inbox_from_env().expect("invalid replication inbox configuration"),
        replication_transport_from_env().expect("invalid replication transport configuration"),
        consensus_from_env().expect("invalid consensus membership configuration"),
        distributed_plan_from_env().expect("invalid distributed event-store plan"),
    );
    let app = routes::build_router(state);
    info!(%root_id, "nested mind API runtime initialized");
    let bind_addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    let listener = TcpListener::bind(bind_addr)
        .await
        .expect("failed to bind API listener");
    info!(%bind_addr, "mind-api listening");
    axum::serve(listener, app)
        .await
        .expect("API server stopped unexpectedly");
}
