"""Purpose: verify canonical MCOI runtime fixtures round-trip through MCOI contracts.
Governance scope: exact witness conformance for MCOI-only runtime contract surfaces.
Dependencies: shared MCOI runtime fixtures and continuity / incident / recovery contract modules.
Invariants: canonical payload witnesses preserve exact JSON rendering across bounded MCOI runtime contracts.
"""

# ruff: noqa: E402

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcoi_runtime.contracts.incident import (
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryDecision,
    RecoveryDecisionStatus,
)
from mcoi_runtime.contracts.continuity_runtime import (
    ContinuityClosureReport,
    ContinuityPlan,
    ContinuityScope,
    ContinuitySnapshot,
    ContinuityStatus,
    ContinuityViolation,
    DisruptionEvent,
    DisruptionSeverity,
    FailoverDisposition,
    FailoverRecord,
    RecoveryObjective,
    RecoveryExecution,
    RecoveryPlan,
    RecoveryStatus,
    RecoveryVerificationStatus,
    VerificationRecord,
)
from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
)
from mcoi_runtime.contracts.case_runtime import (
    CaseAssignment,
    CaseClosureDisposition,
    CaseClosureReport,
    CaseDecision,
    CaseKind,
    CaseRecord,
    CaseSeverity,
    CaseSnapshot,
    CaseStatus,
    CaseViolation,
    EvidenceCollection,
    EvidenceItem,
    EvidenceStatus,
    FindingRecord,
    FindingSeverity,
    ReviewDisposition,
    ReviewRecord,
)
from mcoi_runtime.contracts.human_workflow import (
    ApprovalBoard,
    ApprovalMode,
    BoardDecisionStatus,
    BoardMember,
    BoardVote,
    CollaborationScope,
    CollaborativeDecision,
    HandoffPacket,
    HumanTaskRecord,
    HumanTaskStatus,
    HumanWorkflowClosureReport,
    HumanWorkflowSnapshot,
    HumanWorkflowViolation,
    ReviewMode,
    ReviewPacket,
)
from mcoi_runtime.contracts.assurance_runtime import (
    AssuranceAssessment,
    AssuranceClosureReport,
    AssuranceDecision,
    AssuranceEvidenceBinding,
    AssuranceFinding,
    AssuranceLevel,
    AssuranceScope,
    AssuranceSnapshot,
    AssuranceViolation,
    AttestationRecord,
    AttestationStatus,
    CertificationRecord,
    CertificationStatus,
    EvidenceSufficiency,
    RecertificationStatus,
    RecertificationWindow,
)
from mcoi_runtime.contracts.contract_runtime import (
    BreachRecord,
    BreachSeverity,
    CommitmentKind,
    CommitmentRecord,
    ContractAssessment,
    ContractClause,
    ContractClosureReport,
    ContractSnapshot,
    ContractStatus,
    GovernanceContractRecord,
    RemedyDisposition,
    RemedyRecord,
    RenewalStatus,
    RenewalWindow,
    SLAStatus,
    SLAWindow,
)
from mcoi_runtime.contracts.asset_runtime import (
    AssetAssessment,
    AssetAssignment,
    AssetClosureReport,
    AssetDependency,
    AssetKind,
    AssetRecord,
    AssetSnapshot,
    AssetStatus,
    AssetViolation,
    ConfigurationItem,
    ConfigurationItemStatus,
    InventoryDisposition,
    InventoryRecord,
    LifecycleDisposition,
    LifecycleEvent,
    OwnershipType,
)
from mcoi_runtime.contracts.billing_runtime import (
    BillingAccount,
    BillingClosureReport,
    BillingDecision,
    BillingStatus,
    BillingViolation,
    ChargeKind,
    ChargeRecord,
    CreditDisposition,
    CreditRecord,
    DisputeRecord,
    DisputeStatus,
    InvoiceRecord,
    InvoiceStatus,
    PenaltyRecord,
    RevenueSnapshot,
)
from mcoi_runtime.contracts.settlement_runtime import (
    AgingSnapshot,
    CashApplication,
    CollectionCase,
    CollectionStatus,
    DunningNotice,
    DunningSeverity,
    PaymentMethodKind,
    PaymentRecord,
    PaymentStatus,
    RefundRecord,
    SettlementClosureReport,
    SettlementDecision,
    SettlementRecord,
    SettlementStatus,
    WriteoffDisposition,
    WriteoffRecord,
)
from mcoi_runtime.contracts.customer_runtime import (
    AccountHealthSnapshot,
    AccountHealthStatus,
    AccountRecord,
    AccountStatus,
    CustomerClosureReport,
    CustomerDecision,
    CustomerDisposition,
    CustomerRecord,
    CustomerSnapshot,
    CustomerStatus,
    CustomerViolation,
    EntitlementRecord,
    EntitlementStatus,
    ProductRecord,
    ProductStatus,
    SubscriptionRecord,
)
from mcoi_runtime.contracts.partner_runtime import (
    EcosystemAgreement,
    EcosystemRole,
    PartnerAccountLink,
    PartnerClosureReport,
    PartnerCommitment,
    PartnerDecision,
    PartnerDisposition,
    PartnerHealthSnapshot,
    PartnerHealthStatus,
    PartnerKind,
    PartnerRecord,
    PartnerSnapshot,
    PartnerStatus,
    PartnerViolation,
    RevenueShareRecord,
    RevenueShareStatus,
)
from mcoi_runtime.contracts.marketplace_runtime import (
    BundleDisposition,
    BundleRecord,
    EligibilityRule,
    EligibilityStatus,
    ListingRecord,
    MarketplaceAssessment,
    MarketplaceChannel,
    MarketplaceClosureReport,
    MarketplaceSnapshot,
    MarketplaceViolation,
    OfferingKind,
    OfferingRecord,
    OfferingStatus,
    PackageRecord,
    PricingBinding,
    PricingDisposition,
)
from mcoi_runtime.contracts.procurement_runtime import (
    ProcurementClosureReport,
    ProcurementDecision,
    ProcurementDecisionStatus,
    ProcurementRenewalWindow,
    ProcurementRequest,
    ProcurementRequestStatus,
    ProcurementSnapshot,
    PurchaseOrder,
    PurchaseOrderStatus,
    RenewalDisposition,
    VendorAssessment,
    VendorCommitment,
    VendorRecord,
    VendorRiskLevel,
    VendorStatus,
    VendorViolation,
)
from mcoi_runtime.contracts.financial_runtime import (
    ApprovalThreshold,
    ApprovalThresholdMode,
    BudgetClosureReport,
    BudgetConflict,
    BudgetConflictKind,
    BudgetDecision,
    BudgetEnvelope,
    BudgetReservation,
    BudgetScope,
    CampaignBudgetBinding,
    ChargeDisposition,
    ConnectorCostProfile,
    CostCategory,
    CostEstimate,
    FinancialHealthSnapshot,
    SpendForecast,
    SpendRecord,
    SpendStatus,
)
from mcoi_runtime.contracts.ledger_runtime import (
    AnchorDisposition,
    AnchorRecord,
    LedgerAccount,
    LedgerAssessment,
    LedgerClosureReport,
    LedgerDecision,
    LedgerNetworkKind,
    LedgerSnapshot,
    LedgerStatus,
    LedgerTransaction,
    LedgerViolation,
    LedgerViolationKind,
    SettlementProof,
    SettlementProofStatus,
    WalletRecord,
    WalletStatus,
)
from mcoi_runtime.contracts.tenant_runtime import (
    BoundaryPolicy,
    EnvironmentKind,
    EnvironmentPromotion,
    EnvironmentRecord,
    IsolationLevel,
    IsolationViolation,
    PromotionStatus,
    ScopeBoundaryKind,
    TenantClosureReport,
    TenantDecision,
    TenantHealth,
    TenantRecord,
    TenantStatus,
    WorkspaceBinding,
    WorkspaceRecord,
    WorkspaceStatus,
)
from mcoi_runtime.contracts.records_runtime import (
    DisposalDecision,
    DisposalDisposition,
    DispositionReview,
    EvidenceGrade,
    HoldStatus,
    LegalHoldRecord,
    PreservationDecision,
    RecordAuthority,
    RecordDescriptor,
    RecordKind,
    RecordLink,
    RecordSnapshot,
    RecordViolation,
    RecordsClosureReport,
    RetentionSchedule,
    RetentionStatus,
)
from mcoi_runtime.contracts.causal_runtime import (
    AttributionStrength,
    CausalAssessment,
    CausalAttribution,
    CausalClosureReport,
    CausalDecision,
    CausalEdge,
    CausalEdgeKind,
    CausalNode,
    CausalSnapshot,
    CausalStatus,
    CounterfactualScenario,
    CounterfactualStatus,
    InterventionDisposition,
    InterventionRecord,
    PropagationRecord,
)
from mcoi_runtime.contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentRecord,
    AssignmentStrategy,
    ConstraintClosureReport,
    ConstraintDefinition,
    ConstraintKind,
    ConstraintSnapshot,
    DependencyChain,
    GraphEdge,
    GraphNode,
    ScheduleSlot,
    SolveStatus,
    SolverProblem,
    SolverSolution,
)
from mcoi_runtime.contracts.access_runtime import (
    AccessAuditRecord,
    AccessDecision,
    AccessEvaluation,
    AccessRequest,
    AccessSnapshot,
    AccessViolation,
    AuthContextKind,
    DelegationRecord,
    DelegationStatus as AccessDelegationStatus,
    IdentityKind,
    IdentityRecord,
    PermissionEffect,
    PermissionRule,
    RoleBinding,
    RoleKind,
    RoleRecord,
)
from mcoi_runtime.contracts.availability import (
    AvailabilityConflict,
    AvailabilityKind,
    AvailabilityRecord,
    AvailabilityResolution,
    AvailabilityRoutingDecision,
    BusinessHoursProfile,
    MeetingDecision,
    MeetingRecord,
    MeetingRequest,
    MeetingStatus,
    ResponseExpectation,
    ResponseSLA,
    SchedulingConflictKind,
    SchedulingWindow,
    WindowType,
)
from mcoi_runtime.contracts.change_runtime import (
    ChangeApprovalBinding,
    ChangeEvidence,
    ChangeEvidenceKind,
    ChangeExecution,
    ChangeImpactAssessment,
    ChangeOutcome,
    ChangePlan,
    ChangeRequest,
    ChangeScope,
    ChangeStatus,
    ChangeStep,
    ChangeType,
    RollbackDisposition,
    RollbackPlan,
    RolloutMode,
)
from mcoi_runtime.contracts.recovery import RecoveryRecord


FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "mcoi_runtime"


def _load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _build_incident_record(payload: dict) -> IncidentRecord:
    return IncidentRecord(
        incident_id=payload["incident_id"],
        severity=IncidentSeverity(payload["severity"]),
        status=IncidentStatus(payload["status"]),
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        failure_family=payload["failure_family"],
        message=payload["message"],
        occurred_at=payload["occurred_at"],
        run_id=payload["run_id"],
        skill_id=payload["skill_id"],
        provider_id=payload["provider_id"],
        escalation_id=payload["escalation_id"],
        metadata=payload["metadata"],
    )


def _build_recovery_decision(payload: dict) -> RecoveryDecision:
    return RecoveryDecision(
        decision_id=payload["decision_id"],
        incident_id=payload["incident_id"],
        action=RecoveryAction(payload["action"]),
        status=RecoveryDecisionStatus(payload["status"]),
        reason=payload["reason"],
        autonomy_mode=payload["autonomy_mode"],
        profile_id=payload["profile_id"],
    )


def _build_recovery_attempt(payload: dict) -> RecoveryAttempt:
    return RecoveryAttempt(
        attempt_id=payload["attempt_id"],
        incident_id=payload["incident_id"],
        decision_id=payload["decision_id"],
        action=RecoveryAction(payload["action"]),
        succeeded=payload["succeeded"],
        started_at=payload["started_at"],
        finished_at=payload["finished_at"],
        error_message=payload["error_message"],
        result_run_id=payload["result_run_id"],
    )


def _build_recovery_record(payload: dict) -> RecoveryRecord:
    return RecoveryRecord(
        recovery_id=payload["recovery_id"],
        execution_id=payload["execution_id"],
        trace_id=payload["trace_id"],
        recorded_at=payload["recorded_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_delegation_request(payload: dict) -> DelegationRequest:
    return DelegationRequest(
        delegation_id=payload["delegation_id"],
        delegator_id=payload["delegator_id"],
        delegate_id=payload["delegate_id"],
        goal_id=payload["goal_id"],
        action_scope=payload["action_scope"],
        deadline=payload["deadline"],
        metadata=payload["metadata"],
    )


def _build_delegation_result(payload: dict) -> DelegationResult:
    return DelegationResult(
        delegation_id=payload["delegation_id"],
        status=DelegationStatus(payload["status"]),
        reason=payload["reason"],
        resolved_at=payload["resolved_at"],
    )


def _build_handoff_record(payload: dict) -> HandoffRecord:
    return HandoffRecord(
        handoff_id=payload["handoff_id"],
        from_party=payload["from_party"],
        to_party=payload["to_party"],
        goal_id=payload["goal_id"],
        context_ids=tuple(payload["context_ids"]),
        handed_off_at=payload["handed_off_at"],
        metadata=payload["metadata"],
    )


def _build_merge_decision(payload: dict) -> MergeDecision:
    return MergeDecision(
        merge_id=payload["merge_id"],
        goal_id=payload["goal_id"],
        source_ids=tuple(payload["source_ids"]),
        outcome=MergeOutcome(payload["outcome"]),
        reason=payload["reason"],
        resolved_at=payload["resolved_at"],
    )


def _build_conflict_record(payload: dict) -> ConflictRecord:
    return ConflictRecord(
        conflict_id=payload["conflict_id"],
        goal_id=payload["goal_id"],
        conflicting_ids=tuple(payload["conflicting_ids"]),
        strategy=ConflictStrategy(payload["strategy"]),
        resolved=payload["resolved"],
        resolution_id=payload["resolution_id"],
        metadata=payload["metadata"],
    )


def _build_case_record(payload: dict) -> CaseRecord:
    return CaseRecord(
        case_id=payload["case_id"],
        tenant_id=payload["tenant_id"],
        kind=CaseKind(payload["kind"]),
        severity=CaseSeverity(payload["severity"]),
        status=CaseStatus(payload["status"]),
        title=payload["title"],
        description=payload["description"],
        opened_by=payload["opened_by"],
        opened_at=payload["opened_at"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_case_assignment(payload: dict) -> CaseAssignment:
    return CaseAssignment(
        assignment_id=payload["assignment_id"],
        case_id=payload["case_id"],
        assignee_id=payload["assignee_id"],
        role=payload["role"],
        assigned_at=payload["assigned_at"],
        metadata=payload["metadata"],
    )


def _build_evidence_item(payload: dict) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=payload["evidence_id"],
        case_id=payload["case_id"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        status=EvidenceStatus(payload["status"]),
        title=payload["title"],
        description=payload["description"],
        submitted_by=payload["submitted_by"],
        submitted_at=payload["submitted_at"],
        metadata=payload["metadata"],
    )


def _build_evidence_collection(payload: dict) -> EvidenceCollection:
    return EvidenceCollection(
        collection_id=payload["collection_id"],
        case_id=payload["case_id"],
        title=payload["title"],
        evidence_ids=tuple(payload["evidence_ids"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_review_record(payload: dict) -> ReviewRecord:
    return ReviewRecord(
        review_id=payload["review_id"],
        case_id=payload["case_id"],
        evidence_id=payload["evidence_id"],
        reviewer_id=payload["reviewer_id"],
        disposition=ReviewDisposition(payload["disposition"]),
        notes=payload["notes"],
        reviewed_at=payload["reviewed_at"],
        metadata=payload["metadata"],
    )


def _build_finding_record(payload: dict) -> FindingRecord:
    return FindingRecord(
        finding_id=payload["finding_id"],
        case_id=payload["case_id"],
        severity=FindingSeverity(payload["severity"]),
        title=payload["title"],
        description=payload["description"],
        evidence_ids=tuple(payload["evidence_ids"]),
        remediation=payload["remediation"],
        found_at=payload["found_at"],
        metadata=payload["metadata"],
    )


def _build_case_decision(payload: dict) -> CaseDecision:
    return CaseDecision(
        decision_id=payload["decision_id"],
        case_id=payload["case_id"],
        disposition=CaseClosureDisposition(payload["disposition"]),
        decided_by=payload["decided_by"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_case_snapshot(payload: dict) -> CaseSnapshot:
    return CaseSnapshot(
        snapshot_id=payload["snapshot_id"],
        scope_ref_id=payload["scope_ref_id"],
        total_cases=payload["total_cases"],
        open_cases=payload["open_cases"],
        total_evidence=payload["total_evidence"],
        total_reviews=payload["total_reviews"],
        total_findings=payload["total_findings"],
        total_decisions=payload["total_decisions"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_case_violation(payload: dict) -> CaseViolation:
    return CaseViolation(
        violation_id=payload["violation_id"],
        case_id=payload["case_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_case_closure_report(payload: dict) -> CaseClosureReport:
    return CaseClosureReport(
        report_id=payload["report_id"],
        case_id=payload["case_id"],
        tenant_id=payload["tenant_id"],
        disposition=CaseClosureDisposition(payload["disposition"]),
        total_evidence=payload["total_evidence"],
        total_reviews=payload["total_reviews"],
        total_findings=payload["total_findings"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_continuity_plan(payload: dict) -> ContinuityPlan:
    return ContinuityPlan(
        plan_id=payload["plan_id"],
        name=payload["name"],
        tenant_id=payload["tenant_id"],
        scope=ContinuityScope(payload["scope"]),
        status=ContinuityStatus(payload["status"]),
        scope_ref_id=payload["scope_ref_id"],
        rto_minutes=payload["rto_minutes"],
        rpo_minutes=payload["rpo_minutes"],
        failover_target_ref=payload["failover_target_ref"],
        owner_ref=payload["owner_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_recovery_plan(payload: dict) -> RecoveryPlan:
    return RecoveryPlan(
        recovery_plan_id=payload["recovery_plan_id"],
        plan_id=payload["plan_id"],
        name=payload["name"],
        tenant_id=payload["tenant_id"],
        status=RecoveryStatus(payload["status"]),
        priority=payload["priority"],
        description=payload["description"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_failover_record(payload: dict) -> FailoverRecord:
    return FailoverRecord(
        failover_id=payload["failover_id"],
        plan_id=payload["plan_id"],
        disruption_id=payload["disruption_id"],
        disposition=FailoverDisposition(payload["disposition"]),
        source_ref=payload["source_ref"],
        target_ref=payload["target_ref"],
        initiated_at=payload["initiated_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_disruption_event(payload: dict) -> DisruptionEvent:
    return DisruptionEvent(
        disruption_id=payload["disruption_id"],
        tenant_id=payload["tenant_id"],
        scope=ContinuityScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        severity=DisruptionSeverity(payload["severity"]),
        description=payload["description"],
        detected_at=payload["detected_at"],
        resolved_at=payload["resolved_at"],
        metadata=payload["metadata"],
    )


def _build_recovery_objective(payload: dict) -> RecoveryObjective:
    return RecoveryObjective(
        objective_id=payload["objective_id"],
        plan_id=payload["plan_id"],
        name=payload["name"],
        target_minutes=payload["target_minutes"],
        actual_minutes=payload["actual_minutes"],
        met=payload["met"],
        evaluated_at=payload["evaluated_at"],
        metadata=payload["metadata"],
    )


def _build_recovery_execution(payload: dict) -> RecoveryExecution:
    return RecoveryExecution(
        execution_id=payload["execution_id"],
        recovery_plan_id=payload["recovery_plan_id"],
        disruption_id=payload["disruption_id"],
        status=RecoveryStatus(payload["status"]),
        executed_by=payload["executed_by"],
        started_at=payload["started_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_verification_record(payload: dict) -> VerificationRecord:
    return VerificationRecord(
        verification_id=payload["verification_id"],
        execution_id=payload["execution_id"],
        status=RecoveryVerificationStatus(payload["status"]),
        verified_by=payload["verified_by"],
        confidence=payload["confidence"],
        reason=payload["reason"],
        verified_at=payload["verified_at"],
        metadata=payload["metadata"],
    )


def _build_continuity_snapshot(payload: dict) -> ContinuitySnapshot:
    return ContinuitySnapshot(
        snapshot_id=payload["snapshot_id"],
        total_plans=payload["total_plans"],
        total_active_plans=payload["total_active_plans"],
        total_recovery_plans=payload["total_recovery_plans"],
        total_disruptions=payload["total_disruptions"],
        total_failovers=payload["total_failovers"],
        total_recoveries=payload["total_recoveries"],
        total_verifications=payload["total_verifications"],
        total_violations=payload["total_violations"],
        total_objectives=payload["total_objectives"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_continuity_violation(payload: dict) -> ContinuityViolation:
    return ContinuityViolation(
        violation_id=payload["violation_id"],
        plan_id=payload["plan_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_continuity_closure_report(payload: dict) -> ContinuityClosureReport:
    return ContinuityClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_plans=payload["total_plans"],
        total_disruptions=payload["total_disruptions"],
        total_failovers=payload["total_failovers"],
        total_recoveries=payload["total_recoveries"],
        total_verifications_passed=payload["total_verifications_passed"],
        total_verifications_failed=payload["total_verifications_failed"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_human_task_record(payload: dict) -> HumanTaskRecord:
    return HumanTaskRecord(
        task_id=payload["task_id"],
        tenant_id=payload["tenant_id"],
        assignee_ref=payload["assignee_ref"],
        status=HumanTaskStatus(payload["status"]),
        scope=CollaborationScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        title=payload["title"],
        description=payload["description"],
        due_at=payload["due_at"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_review_packet(payload: dict) -> ReviewPacket:
    return ReviewPacket(
        packet_id=payload["packet_id"],
        tenant_id=payload["tenant_id"],
        scope=CollaborationScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        review_mode=ReviewMode(payload["review_mode"]),
        title=payload["title"],
        reviewer_count=payload["reviewer_count"],
        reviews_completed=payload["reviews_completed"],
        reviews_approved=payload["reviews_approved"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_approval_board(payload: dict) -> ApprovalBoard:
    return ApprovalBoard(
        board_id=payload["board_id"],
        tenant_id=payload["tenant_id"],
        name=payload["name"],
        approval_mode=ApprovalMode(payload["approval_mode"]),
        quorum_required=payload["quorum_required"],
        scope=CollaborationScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        member_count=payload["member_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_board_member(payload: dict) -> BoardMember:
    return BoardMember(
        member_id=payload["member_id"],
        board_id=payload["board_id"],
        identity_ref=payload["identity_ref"],
        role=payload["role"],
        added_at=payload["added_at"],
        metadata=payload["metadata"],
    )


def _build_board_vote(payload: dict) -> BoardVote:
    return BoardVote(
        vote_id=payload["vote_id"],
        board_id=payload["board_id"],
        member_id=payload["member_id"],
        scope_ref_id=payload["scope_ref_id"],
        approved=payload["approved"],
        reason=payload["reason"],
        voted_at=payload["voted_at"],
        metadata=payload["metadata"],
    )


def _build_collaborative_decision(payload: dict) -> CollaborativeDecision:
    return CollaborativeDecision(
        decision_id=payload["decision_id"],
        board_id=payload["board_id"],
        scope_ref_id=payload["scope_ref_id"],
        status=BoardDecisionStatus(payload["status"]),
        total_votes=payload["total_votes"],
        approvals=payload["approvals"],
        rejections=payload["rejections"],
        decided_by=payload["decided_by"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_handoff_packet(payload: dict) -> HandoffPacket:
    return HandoffPacket(
        handoff_id=payload["handoff_id"],
        tenant_id=payload["tenant_id"],
        scope=CollaborationScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        from_ref=payload["from_ref"],
        to_ref=payload["to_ref"],
        direction=payload["direction"],
        reason=payload["reason"],
        handed_at=payload["handed_at"],
        metadata=payload["metadata"],
    )


def _build_human_workflow_snapshot(payload: dict) -> HumanWorkflowSnapshot:
    return HumanWorkflowSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_tasks=payload["total_tasks"],
        total_review_packets=payload["total_review_packets"],
        total_boards=payload["total_boards"],
        total_members=payload["total_members"],
        total_votes=payload["total_votes"],
        total_decisions=payload["total_decisions"],
        total_handoffs=payload["total_handoffs"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_human_workflow_violation(payload: dict) -> HumanWorkflowViolation:
    return HumanWorkflowViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        scope_ref_id=payload["scope_ref_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_human_workflow_closure_report(payload: dict) -> HumanWorkflowClosureReport:
    return HumanWorkflowClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_tasks=payload["total_tasks"],
        total_review_packets=payload["total_review_packets"],
        total_boards=payload["total_boards"],
        total_decisions_approved=payload["total_decisions_approved"],
        total_decisions_rejected=payload["total_decisions_rejected"],
        total_handoffs=payload["total_handoffs"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_attestation_record(payload: dict) -> AttestationRecord:
    return AttestationRecord(
        attestation_id=payload["attestation_id"],
        tenant_id=payload["tenant_id"],
        scope=AssuranceScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        level=AssuranceLevel(payload["level"]),
        status=AttestationStatus(payload["status"]),
        attested_by=payload["attested_by"],
        attested_at=payload["attested_at"],
        expires_at=payload["expires_at"],
        metadata=payload["metadata"],
    )


def _build_certification_record(payload: dict) -> CertificationRecord:
    return CertificationRecord(
        certification_id=payload["certification_id"],
        tenant_id=payload["tenant_id"],
        scope=AssuranceScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        status=CertificationStatus(payload["status"]),
        level=AssuranceLevel(payload["level"]),
        certified_by=payload["certified_by"],
        certified_at=payload["certified_at"],
        expires_at=payload["expires_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_assessment(payload: dict) -> AssuranceAssessment:
    return AssuranceAssessment(
        assessment_id=payload["assessment_id"],
        tenant_id=payload["tenant_id"],
        scope=AssuranceScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        level=AssuranceLevel(payload["level"]),
        sufficiency=EvidenceSufficiency(payload["sufficiency"]),
        confidence=payload["confidence"],
        assessed_by=payload["assessed_by"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_evidence_binding(payload: dict) -> AssuranceEvidenceBinding:
    return AssuranceEvidenceBinding(
        binding_id=payload["binding_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        bound_at=payload["bound_at"],
        metadata=payload["metadata"],
    )


def _build_recertification_window(payload: dict) -> RecertificationWindow:
    return RecertificationWindow(
        window_id=payload["window_id"],
        certification_id=payload["certification_id"],
        status=RecertificationStatus(payload["status"]),
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_finding(payload: dict) -> AssuranceFinding:
    return AssuranceFinding(
        finding_id=payload["finding_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        description=payload["description"],
        impact_level=AssuranceLevel(payload["impact_level"]),
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_decision(payload: dict) -> AssuranceDecision:
    return AssuranceDecision(
        decision_id=payload["decision_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        level=AssuranceLevel(payload["level"]),
        decided_by=payload["decided_by"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_snapshot(payload: dict) -> AssuranceSnapshot:
    return AssuranceSnapshot(
        snapshot_id=payload["snapshot_id"],
        scope_ref_id=payload["scope_ref_id"],
        total_attestations=payload["total_attestations"],
        granted_attestations=payload["granted_attestations"],
        total_certifications=payload["total_certifications"],
        active_certifications=payload["active_certifications"],
        total_assessments=payload["total_assessments"],
        total_evidence_bindings=payload["total_evidence_bindings"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_violation(payload: dict) -> AssuranceViolation:
    return AssuranceViolation(
        violation_id=payload["violation_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_assurance_closure_report(payload: dict) -> AssuranceClosureReport:
    return AssuranceClosureReport(
        report_id=payload["report_id"],
        target_id=payload["target_id"],
        target_type=payload["target_type"],
        tenant_id=payload["tenant_id"],
        final_level=AssuranceLevel(payload["final_level"]),
        total_evidence_bindings=payload["total_evidence_bindings"],
        total_assessments=payload["total_assessments"],
        total_findings=payload["total_findings"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_governance_contract_record(payload: dict) -> GovernanceContractRecord:
    return GovernanceContractRecord(
        contract_id=payload["contract_id"],
        tenant_id=payload["tenant_id"],
        counterparty=payload["counterparty"],
        status=ContractStatus(payload["status"]),
        title=payload["title"],
        description=payload["description"],
        effective_at=payload["effective_at"],
        expires_at=payload["expires_at"],
        metadata=payload["metadata"],
    )


def _build_contract_clause(payload: dict) -> ContractClause:
    return ContractClause(
        clause_id=payload["clause_id"],
        contract_id=payload["contract_id"],
        title=payload["title"],
        description=payload["description"],
        commitment_kind=CommitmentKind(payload["commitment_kind"]),
        metadata=payload["metadata"],
    )


def _build_commitment_record(payload: dict) -> CommitmentRecord:
    return CommitmentRecord(
        commitment_id=payload["commitment_id"],
        contract_id=payload["contract_id"],
        clause_id=payload["clause_id"],
        tenant_id=payload["tenant_id"],
        kind=CommitmentKind(payload["kind"]),
        target_value=payload["target_value"],
        scope_ref_id=payload["scope_ref_id"],
        scope_ref_type=payload["scope_ref_type"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_sla_window(payload: dict) -> SLAWindow:
    return SLAWindow(
        window_id=payload["window_id"],
        commitment_id=payload["commitment_id"],
        status=SLAStatus(payload["status"]),
        opens_at=payload["opens_at"],
        closes_at=payload["closes_at"],
        actual_value=payload["actual_value"],
        compliance=payload["compliance"],
        metadata=payload["metadata"],
    )


def _build_breach_record(payload: dict) -> BreachRecord:
    return BreachRecord(
        breach_id=payload["breach_id"],
        commitment_id=payload["commitment_id"],
        contract_id=payload["contract_id"],
        tenant_id=payload["tenant_id"],
        severity=BreachSeverity(payload["severity"]),
        description=payload["description"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_remedy_record(payload: dict) -> RemedyRecord:
    return RemedyRecord(
        remedy_id=payload["remedy_id"],
        breach_id=payload["breach_id"],
        tenant_id=payload["tenant_id"],
        disposition=RemedyDisposition(payload["disposition"]),
        amount=payload["amount"],
        description=payload["description"],
        applied_at=payload["applied_at"],
        metadata=payload["metadata"],
    )


def _build_renewal_window(payload: dict) -> RenewalWindow:
    return RenewalWindow(
        window_id=payload["window_id"],
        contract_id=payload["contract_id"],
        status=RenewalStatus(payload["status"]),
        opens_at=payload["opens_at"],
        closes_at=payload["closes_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_contract_assessment(payload: dict) -> ContractAssessment:
    return ContractAssessment(
        assessment_id=payload["assessment_id"],
        contract_id=payload["contract_id"],
        tenant_id=payload["tenant_id"],
        total_commitments=payload["total_commitments"],
        healthy_commitments=payload["healthy_commitments"],
        at_risk_commitments=payload["at_risk_commitments"],
        breached_commitments=payload["breached_commitments"],
        overall_compliance=payload["overall_compliance"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_contract_snapshot(payload: dict) -> ContractSnapshot:
    return ContractSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_contracts=payload["total_contracts"],
        active_contracts=payload["active_contracts"],
        total_commitments=payload["total_commitments"],
        total_sla_windows=payload["total_sla_windows"],
        total_breaches=payload["total_breaches"],
        total_remedies=payload["total_remedies"],
        total_renewals=payload["total_renewals"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_contract_closure_report(payload: dict) -> ContractClosureReport:
    return ContractClosureReport(
        report_id=payload["report_id"],
        contract_id=payload["contract_id"],
        tenant_id=payload["tenant_id"],
        final_status=ContractStatus(payload["final_status"]),
        total_commitments=payload["total_commitments"],
        total_breaches=payload["total_breaches"],
        total_remedies=payload["total_remedies"],
        total_renewals=payload["total_renewals"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_asset_record(payload: dict) -> AssetRecord:
    return AssetRecord(
        asset_id=payload["asset_id"],
        name=payload["name"],
        tenant_id=payload["tenant_id"],
        kind=AssetKind(payload["kind"]),
        status=AssetStatus(payload["status"]),
        ownership=OwnershipType(payload["ownership"]),
        owner_ref=payload["owner_ref"],
        vendor_ref=payload["vendor_ref"],
        value=payload["value"],
        registered_at=payload["registered_at"],
        metadata=payload["metadata"],
    )


def _build_configuration_item(payload: dict) -> ConfigurationItem:
    return ConfigurationItem(
        ci_id=payload["ci_id"],
        asset_id=payload["asset_id"],
        name=payload["name"],
        status=ConfigurationItemStatus(payload["status"]),
        environment_ref=payload["environment_ref"],
        workspace_ref=payload["workspace_ref"],
        version=payload["version"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_inventory_record(payload: dict) -> InventoryRecord:
    return InventoryRecord(
        inventory_id=payload["inventory_id"],
        asset_id=payload["asset_id"],
        tenant_id=payload["tenant_id"],
        disposition=InventoryDisposition(payload["disposition"]),
        total_quantity=payload["total_quantity"],
        assigned_quantity=payload["assigned_quantity"],
        available_quantity=payload["available_quantity"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
    )


def _build_asset_assignment(payload: dict) -> AssetAssignment:
    return AssetAssignment(
        assignment_id=payload["assignment_id"],
        asset_id=payload["asset_id"],
        scope_ref_id=payload["scope_ref_id"],
        scope_ref_type=payload["scope_ref_type"],
        assigned_by=payload["assigned_by"],
        assigned_at=payload["assigned_at"],
        metadata=payload["metadata"],
    )


def _build_asset_dependency(payload: dict) -> AssetDependency:
    return AssetDependency(
        dependency_id=payload["dependency_id"],
        asset_id=payload["asset_id"],
        depends_on_asset_id=payload["depends_on_asset_id"],
        description=payload["description"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_lifecycle_event(payload: dict) -> LifecycleEvent:
    return LifecycleEvent(
        event_id=payload["event_id"],
        asset_id=payload["asset_id"],
        disposition=LifecycleDisposition(payload["disposition"]),
        description=payload["description"],
        performed_by=payload["performed_by"],
        performed_at=payload["performed_at"],
        metadata=payload["metadata"],
    )


def _build_asset_assessment(payload: dict) -> AssetAssessment:
    return AssetAssessment(
        assessment_id=payload["assessment_id"],
        asset_id=payload["asset_id"],
        health_score=payload["health_score"],
        risk_score=payload["risk_score"],
        assessed_by=payload["assessed_by"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_asset_snapshot(payload: dict) -> AssetSnapshot:
    return AssetSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_assets=payload["total_assets"],
        total_active=payload["total_active"],
        total_retired=payload["total_retired"],
        total_config_items=payload["total_config_items"],
        total_inventory=payload["total_inventory"],
        total_assignments=payload["total_assignments"],
        total_dependencies=payload["total_dependencies"],
        total_violations=payload["total_violations"],
        total_asset_value=payload["total_asset_value"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_asset_violation(payload: dict) -> AssetViolation:
    return AssetViolation(
        violation_id=payload["violation_id"],
        asset_id=payload["asset_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_asset_closure_report(payload: dict) -> AssetClosureReport:
    return AssetClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_assets=payload["total_assets"],
        total_active=payload["total_active"],
        total_retired=payload["total_retired"],
        total_assignments=payload["total_assignments"],
        total_dependencies=payload["total_dependencies"],
        total_asset_value=payload["total_asset_value"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_billing_account(payload: dict) -> BillingAccount:
    return BillingAccount(
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        counterparty=payload["counterparty"],
        status=BillingStatus(payload["status"]),
        currency=payload["currency"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_invoice_record(payload: dict) -> InvoiceRecord:
    return InvoiceRecord(
        invoice_id=payload["invoice_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        status=InvoiceStatus(payload["status"]),
        total_amount=payload["total_amount"],
        currency=payload["currency"],
        issued_at=payload["issued_at"],
        due_at=payload["due_at"],
        metadata=payload["metadata"],
    )


def _build_charge_record(payload: dict) -> ChargeRecord:
    return ChargeRecord(
        charge_id=payload["charge_id"],
        invoice_id=payload["invoice_id"],
        kind=ChargeKind(payload["kind"]),
        description=payload["description"],
        amount=payload["amount"],
        scope_ref_id=payload["scope_ref_id"],
        scope_ref_type=payload["scope_ref_type"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_credit_record(payload: dict) -> CreditRecord:
    return CreditRecord(
        credit_id=payload["credit_id"],
        account_id=payload["account_id"],
        breach_id=payload["breach_id"],
        disposition=CreditDisposition(payload["disposition"]),
        amount=payload["amount"],
        reason=payload["reason"],
        applied_at=payload["applied_at"],
        metadata=payload["metadata"],
    )


def _build_penalty_record(payload: dict) -> PenaltyRecord:
    return PenaltyRecord(
        penalty_id=payload["penalty_id"],
        account_id=payload["account_id"],
        breach_id=payload["breach_id"],
        amount=payload["amount"],
        reason=payload["reason"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_dispute_record(payload: dict) -> DisputeRecord:
    return DisputeRecord(
        dispute_id=payload["dispute_id"],
        invoice_id=payload["invoice_id"],
        account_id=payload["account_id"],
        status=DisputeStatus(payload["status"]),
        reason=payload["reason"],
        amount=payload["amount"],
        opened_at=payload["opened_at"],
        resolved_at=payload["resolved_at"],
        metadata=payload["metadata"],
    )


def _build_revenue_snapshot(payload: dict) -> RevenueSnapshot:
    return RevenueSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_accounts=payload["total_accounts"],
        total_invoices=payload["total_invoices"],
        total_charges=payload["total_charges"],
        total_credits=payload["total_credits"],
        total_penalties=payload["total_penalties"],
        total_disputes=payload["total_disputes"],
        total_recognized_revenue=payload["total_recognized_revenue"],
        total_pending_revenue=payload["total_pending_revenue"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_billing_decision(payload: dict) -> BillingDecision:
    return BillingDecision(
        decision_id=payload["decision_id"],
        account_id=payload["account_id"],
        description=payload["description"],
        decided_by=payload["decided_by"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_billing_violation(payload: dict) -> BillingViolation:
    return BillingViolation(
        violation_id=payload["violation_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_billing_closure_report(payload: dict) -> BillingClosureReport:
    return BillingClosureReport(
        report_id=payload["report_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        total_invoices=payload["total_invoices"],
        total_charges=payload["total_charges"],
        total_credits=payload["total_credits"],
        total_penalties=payload["total_penalties"],
        total_disputes=payload["total_disputes"],
        total_revenue=payload["total_revenue"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_payment_record(payload: dict) -> PaymentRecord:
    return PaymentRecord(
        payment_id=payload["payment_id"],
        invoice_id=payload["invoice_id"],
        account_id=payload["account_id"],
        amount=payload["amount"],
        currency=payload["currency"],
        method=PaymentMethodKind(payload["method"]),
        status=PaymentStatus(payload["status"]),
        reference=payload["reference"],
        received_at=payload["received_at"],
        metadata=payload["metadata"],
    )


def _build_settlement_record(payload: dict) -> SettlementRecord:
    return SettlementRecord(
        settlement_id=payload["settlement_id"],
        invoice_id=payload["invoice_id"],
        account_id=payload["account_id"],
        total_amount=payload["total_amount"],
        paid_amount=payload["paid_amount"],
        credit_applied=payload["credit_applied"],
        outstanding=payload["outstanding"],
        status=SettlementStatus(payload["status"]),
        currency=payload["currency"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_collection_case(payload: dict) -> CollectionCase:
    return CollectionCase(
        case_id=payload["case_id"],
        invoice_id=payload["invoice_id"],
        account_id=payload["account_id"],
        status=CollectionStatus(payload["status"]),
        outstanding_amount=payload["outstanding_amount"],
        dunning_count=payload["dunning_count"],
        opened_at=payload["opened_at"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_dunning_notice(payload: dict) -> DunningNotice:
    return DunningNotice(
        notice_id=payload["notice_id"],
        case_id=payload["case_id"],
        account_id=payload["account_id"],
        severity=DunningSeverity(payload["severity"]),
        message=payload["message"],
        sent_at=payload["sent_at"],
        metadata=payload["metadata"],
    )


def _build_cash_application(payload: dict) -> CashApplication:
    return CashApplication(
        application_id=payload["application_id"],
        settlement_id=payload["settlement_id"],
        payment_id=payload["payment_id"],
        amount=payload["amount"],
        applied_at=payload["applied_at"],
        metadata=payload["metadata"],
    )


def _build_refund_record(payload: dict) -> RefundRecord:
    return RefundRecord(
        refund_id=payload["refund_id"],
        payment_id=payload["payment_id"],
        account_id=payload["account_id"],
        amount=payload["amount"],
        reason=payload["reason"],
        refunded_at=payload["refunded_at"],
        metadata=payload["metadata"],
    )


def _build_writeoff_record(payload: dict) -> WriteoffRecord:
    return WriteoffRecord(
        writeoff_id=payload["writeoff_id"],
        settlement_id=payload["settlement_id"],
        account_id=payload["account_id"],
        amount=payload["amount"],
        disposition=WriteoffDisposition(payload["disposition"]),
        reason=payload["reason"],
        written_off_at=payload["written_off_at"],
        metadata=payload["metadata"],
    )


def _build_aging_snapshot(payload: dict) -> AgingSnapshot:
    return AgingSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_settlements=payload["total_settlements"],
        total_open=payload["total_open"],
        total_partial=payload["total_partial"],
        total_settled=payload["total_settled"],
        total_disputed=payload["total_disputed"],
        total_written_off=payload["total_written_off"],
        total_outstanding=payload["total_outstanding"],
        total_collected=payload["total_collected"],
        total_refunded=payload["total_refunded"],
        total_collection_cases=payload["total_collection_cases"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_settlement_decision(payload: dict) -> SettlementDecision:
    return SettlementDecision(
        decision_id=payload["decision_id"],
        settlement_id=payload["settlement_id"],
        description=payload["description"],
        decided_by=payload["decided_by"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_settlement_closure_report(payload: dict) -> SettlementClosureReport:
    return SettlementClosureReport(
        report_id=payload["report_id"],
        account_id=payload["account_id"],
        total_settlements=payload["total_settlements"],
        total_payments=payload["total_payments"],
        total_refunds=payload["total_refunds"],
        total_writeoffs=payload["total_writeoffs"],
        total_collection_cases=payload["total_collection_cases"],
        total_collected=payload["total_collected"],
        total_outstanding=payload["total_outstanding"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_customer_record(payload: dict) -> CustomerRecord:
    return CustomerRecord(
        customer_id=payload["customer_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        status=CustomerStatus(payload["status"]),
        tier=payload["tier"],
        account_count=payload["account_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_account_record(payload: dict) -> AccountRecord:
    return AccountRecord(
        account_id=payload["account_id"],
        customer_id=payload["customer_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        status=AccountStatus(payload["status"]),
        contract_ref=payload["contract_ref"],
        entitlement_count=payload["entitlement_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_product_record(payload: dict) -> ProductRecord:
    return ProductRecord(
        product_id=payload["product_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        status=ProductStatus(payload["status"]),
        category=payload["category"],
        base_price=payload["base_price"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_subscription_record(payload: dict) -> SubscriptionRecord:
    return SubscriptionRecord(
        subscription_id=payload["subscription_id"],
        account_id=payload["account_id"],
        product_id=payload["product_id"],
        tenant_id=payload["tenant_id"],
        status=AccountStatus(payload["status"]),
        quantity=payload["quantity"],
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_entitlement_record(payload: dict) -> EntitlementRecord:
    return EntitlementRecord(
        entitlement_id=payload["entitlement_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        service_ref=payload["service_ref"],
        status=EntitlementStatus(payload["status"]),
        granted_at=payload["granted_at"],
        expires_at=payload["expires_at"],
        metadata=payload["metadata"],
    )


def _build_account_health_snapshot(payload: dict) -> AccountHealthSnapshot:
    return AccountHealthSnapshot(
        snapshot_id=payload["snapshot_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        health_status=AccountHealthStatus(payload["health_status"]),
        health_score=payload["health_score"],
        sla_breaches=payload["sla_breaches"],
        open_cases=payload["open_cases"],
        billing_issues=payload["billing_issues"],
        entitlement_count=payload["entitlement_count"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_customer_decision(payload: dict) -> CustomerDecision:
    return CustomerDecision(
        decision_id=payload["decision_id"],
        tenant_id=payload["tenant_id"],
        customer_id=payload["customer_id"],
        account_id=payload["account_id"],
        disposition=CustomerDisposition(payload["disposition"]),
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_customer_violation(payload: dict) -> CustomerViolation:
    return CustomerViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_customer_snapshot(payload: dict) -> CustomerSnapshot:
    return CustomerSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_customers=payload["total_customers"],
        total_accounts=payload["total_accounts"],
        total_products=payload["total_products"],
        total_subscriptions=payload["total_subscriptions"],
        total_entitlements=payload["total_entitlements"],
        total_health_snapshots=payload["total_health_snapshots"],
        total_decisions=payload["total_decisions"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_customer_closure_report(payload: dict) -> CustomerClosureReport:
    return CustomerClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_customers=payload["total_customers"],
        total_accounts=payload["total_accounts"],
        total_products=payload["total_products"],
        total_subscriptions=payload["total_subscriptions"],
        total_entitlements=payload["total_entitlements"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_partner_record(payload: dict) -> PartnerRecord:
    return PartnerRecord(
        partner_id=payload["partner_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        kind=PartnerKind(payload["kind"]),
        status=PartnerStatus(payload["status"]),
        tier=payload["tier"],
        account_link_count=payload["account_link_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_partner_account_link(payload: dict) -> PartnerAccountLink:
    return PartnerAccountLink(
        link_id=payload["link_id"],
        partner_id=payload["partner_id"],
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        role=EcosystemRole(payload["role"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_ecosystem_agreement(payload: dict) -> EcosystemAgreement:
    return EcosystemAgreement(
        agreement_id=payload["agreement_id"],
        partner_id=payload["partner_id"],
        tenant_id=payload["tenant_id"],
        title=payload["title"],
        contract_ref=payload["contract_ref"],
        revenue_share_pct=payload["revenue_share_pct"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_revenue_share_record(payload: dict) -> RevenueShareRecord:
    return RevenueShareRecord(
        share_id=payload["share_id"],
        partner_id=payload["partner_id"],
        agreement_id=payload["agreement_id"],
        tenant_id=payload["tenant_id"],
        gross_amount=payload["gross_amount"],
        share_amount=payload["share_amount"],
        share_pct=payload["share_pct"],
        status=RevenueShareStatus(payload["status"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_partner_commitment(payload: dict) -> PartnerCommitment:
    return PartnerCommitment(
        commitment_id=payload["commitment_id"],
        partner_id=payload["partner_id"],
        tenant_id=payload["tenant_id"],
        description=payload["description"],
        target_value=payload["target_value"],
        actual_value=payload["actual_value"],
        met=payload["met"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_partner_health_snapshot(payload: dict) -> PartnerHealthSnapshot:
    return PartnerHealthSnapshot(
        snapshot_id=payload["snapshot_id"],
        partner_id=payload["partner_id"],
        tenant_id=payload["tenant_id"],
        health_status=PartnerHealthStatus(payload["health_status"]),
        health_score=payload["health_score"],
        sla_breaches=payload["sla_breaches"],
        open_cases=payload["open_cases"],
        billing_issues=payload["billing_issues"],
        commitment_failures=payload["commitment_failures"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_partner_decision(payload: dict) -> PartnerDecision:
    return PartnerDecision(
        decision_id=payload["decision_id"],
        tenant_id=payload["tenant_id"],
        partner_id=payload["partner_id"],
        disposition=PartnerDisposition(payload["disposition"]),
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_partner_violation(payload: dict) -> PartnerViolation:
    return PartnerViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        partner_id=payload["partner_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_partner_snapshot(payload: dict) -> PartnerSnapshot:
    return PartnerSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_partners=payload["total_partners"],
        total_links=payload["total_links"],
        total_agreements=payload["total_agreements"],
        total_revenue_shares=payload["total_revenue_shares"],
        total_commitments=payload["total_commitments"],
        total_health_snapshots=payload["total_health_snapshots"],
        total_decisions=payload["total_decisions"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_partner_closure_report(payload: dict) -> PartnerClosureReport:
    return PartnerClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_partners=payload["total_partners"],
        total_links=payload["total_links"],
        total_agreements=payload["total_agreements"],
        total_revenue_shares=payload["total_revenue_shares"],
        total_commitments=payload["total_commitments"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_offering_record(payload: dict) -> OfferingRecord:
    return OfferingRecord(
        offering_id=payload["offering_id"],
        product_id=payload["product_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        kind=OfferingKind(payload["kind"]),
        status=OfferingStatus(payload["status"]),
        version_ref=payload["version_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_package_record(payload: dict) -> PackageRecord:
    return PackageRecord(
        package_id=payload["package_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        offering_count=payload["offering_count"],
        status=OfferingStatus(payload["status"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_bundle_record(payload: dict) -> BundleRecord:
    return BundleRecord(
        bundle_id=payload["bundle_id"],
        package_id=payload["package_id"],
        offering_id=payload["offering_id"],
        tenant_id=payload["tenant_id"],
        disposition=BundleDisposition(payload["disposition"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_listing_record(payload: dict) -> ListingRecord:
    return ListingRecord(
        listing_id=payload["listing_id"],
        offering_id=payload["offering_id"],
        tenant_id=payload["tenant_id"],
        channel=MarketplaceChannel(payload["channel"]),
        active=payload["active"],
        listed_at=payload["listed_at"],
        metadata=payload["metadata"],
    )


def _build_eligibility_rule(payload: dict) -> EligibilityRule:
    return EligibilityRule(
        rule_id=payload["rule_id"],
        offering_id=payload["offering_id"],
        tenant_id=payload["tenant_id"],
        account_segment=payload["account_segment"],
        status=EligibilityStatus(payload["status"]),
        reason=payload["reason"],
        evaluated_at=payload["evaluated_at"],
        metadata=payload["metadata"],
    )


def _build_pricing_binding(payload: dict) -> PricingBinding:
    return PricingBinding(
        binding_id=payload["binding_id"],
        offering_id=payload["offering_id"],
        tenant_id=payload["tenant_id"],
        base_price=payload["base_price"],
        effective_price=payload["effective_price"],
        disposition=PricingDisposition(payload["disposition"]),
        contract_ref=payload["contract_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_marketplace_assessment(payload: dict) -> MarketplaceAssessment:
    return MarketplaceAssessment(
        assessment_id=payload["assessment_id"],
        tenant_id=payload["tenant_id"],
        total_offerings=payload["total_offerings"],
        active_offerings=payload["active_offerings"],
        total_listings=payload["total_listings"],
        active_listings=payload["active_listings"],
        total_packages=payload["total_packages"],
        coverage_score=payload["coverage_score"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_marketplace_snapshot(payload: dict) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_offerings=payload["total_offerings"],
        total_packages=payload["total_packages"],
        total_bundles=payload["total_bundles"],
        total_listings=payload["total_listings"],
        total_eligibility_rules=payload["total_eligibility_rules"],
        total_pricing_bindings=payload["total_pricing_bindings"],
        total_assessments=payload["total_assessments"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_marketplace_violation(payload: dict) -> MarketplaceViolation:
    return MarketplaceViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_marketplace_closure_report(payload: dict) -> MarketplaceClosureReport:
    return MarketplaceClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_offerings=payload["total_offerings"],
        total_packages=payload["total_packages"],
        total_bundles=payload["total_bundles"],
        total_listings=payload["total_listings"],
        total_eligibility_rules=payload["total_eligibility_rules"],
        total_pricing_bindings=payload["total_pricing_bindings"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_vendor_record(payload: dict) -> VendorRecord:
    return VendorRecord(
        vendor_id=payload["vendor_id"],
        name=payload["name"],
        tenant_id=payload["tenant_id"],
        status=VendorStatus(payload["status"]),
        risk_level=VendorRiskLevel(payload["risk_level"]),
        category=payload["category"],
        registered_at=payload["registered_at"],
        metadata=payload["metadata"],
    )


def _build_procurement_request(payload: dict) -> ProcurementRequest:
    return ProcurementRequest(
        request_id=payload["request_id"],
        vendor_id=payload["vendor_id"],
        tenant_id=payload["tenant_id"],
        status=ProcurementRequestStatus(payload["status"]),
        description=payload["description"],
        estimated_amount=payload["estimated_amount"],
        currency=payload["currency"],
        requested_by=payload["requested_by"],
        requested_at=payload["requested_at"],
        metadata=payload["metadata"],
    )


def _build_purchase_order(payload: dict) -> PurchaseOrder:
    return PurchaseOrder(
        po_id=payload["po_id"],
        request_id=payload["request_id"],
        vendor_id=payload["vendor_id"],
        tenant_id=payload["tenant_id"],
        status=PurchaseOrderStatus(payload["status"]),
        amount=payload["amount"],
        currency=payload["currency"],
        issued_at=payload["issued_at"],
        metadata=payload["metadata"],
    )


def _build_vendor_assessment(payload: dict) -> VendorAssessment:
    return VendorAssessment(
        assessment_id=payload["assessment_id"],
        vendor_id=payload["vendor_id"],
        risk_level=VendorRiskLevel(payload["risk_level"]),
        performance_score=payload["performance_score"],
        fault_count=payload["fault_count"],
        assessed_by=payload["assessed_by"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_vendor_commitment(payload: dict) -> VendorCommitment:
    return VendorCommitment(
        commitment_id=payload["commitment_id"],
        vendor_id=payload["vendor_id"],
        contract_ref=payload["contract_ref"],
        description=payload["description"],
        target_value=payload["target_value"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_procurement_decision(payload: dict) -> ProcurementDecision:
    return ProcurementDecision(
        decision_id=payload["decision_id"],
        request_id=payload["request_id"],
        status=ProcurementDecisionStatus(payload["status"]),
        decided_by=payload["decided_by"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_procurement_renewal_window(payload: dict) -> ProcurementRenewalWindow:
    return ProcurementRenewalWindow(
        renewal_id=payload["renewal_id"],
        vendor_id=payload["vendor_id"],
        contract_ref=payload["contract_ref"],
        disposition=RenewalDisposition(payload["disposition"]),
        opens_at=payload["opens_at"],
        closes_at=payload["closes_at"],
        metadata=payload["metadata"],
    )


def _build_vendor_violation(payload: dict) -> VendorViolation:
    return VendorViolation(
        violation_id=payload["violation_id"],
        vendor_id=payload["vendor_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_procurement_snapshot(payload: dict) -> ProcurementSnapshot:
    return ProcurementSnapshot(
        snapshot_id=payload["snapshot_id"],
        total_vendors=payload["total_vendors"],
        total_requests=payload["total_requests"],
        total_purchase_orders=payload["total_purchase_orders"],
        total_assessments=payload["total_assessments"],
        total_commitments=payload["total_commitments"],
        total_renewals=payload["total_renewals"],
        total_violations=payload["total_violations"],
        total_procurement_value=payload["total_procurement_value"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_procurement_closure_report(payload: dict) -> ProcurementClosureReport:
    return ProcurementClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_vendors=payload["total_vendors"],
        total_requests=payload["total_requests"],
        total_purchase_orders=payload["total_purchase_orders"],
        total_fulfilled=payload["total_fulfilled"],
        total_cancelled=payload["total_cancelled"],
        total_procurement_value=payload["total_procurement_value"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_budget_envelope(payload: dict) -> BudgetEnvelope:
    return BudgetEnvelope(
        budget_id=payload["budget_id"],
        name=payload["name"],
        scope=BudgetScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        currency=payload["currency"],
        limit_amount=payload["limit_amount"],
        reserved_amount=payload["reserved_amount"],
        consumed_amount=payload["consumed_amount"],
        warning_threshold=payload["warning_threshold"],
        hard_stop_threshold=payload["hard_stop_threshold"],
        active=payload["active"],
        tags=tuple(payload["tags"]),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
    )


def _build_spend_record(payload: dict) -> SpendRecord:
    return SpendRecord(
        spend_id=payload["spend_id"],
        budget_id=payload["budget_id"],
        category=CostCategory(payload["category"]),
        status=SpendStatus(payload["status"]),
        amount=payload["amount"],
        currency=payload["currency"],
        campaign_ref=payload["campaign_ref"],
        step_ref=payload["step_ref"],
        connector_ref=payload["connector_ref"],
        reason=payload["reason"],
        created_at=payload["created_at"],
    )


def _build_cost_estimate(payload: dict) -> CostEstimate:
    return CostEstimate(
        estimate_id=payload["estimate_id"],
        category=CostCategory(payload["category"]),
        estimated_amount=payload["estimated_amount"],
        currency=payload["currency"],
        confidence=payload["confidence"],
        connector_ref=payload["connector_ref"],
        campaign_ref=payload["campaign_ref"],
        step_ref=payload["step_ref"],
        created_at=payload["created_at"],
    )


def _build_connector_cost_profile(payload: dict) -> ConnectorCostProfile:
    return ConnectorCostProfile(
        profile_id=payload["profile_id"],
        connector_ref=payload["connector_ref"],
        cost_per_call=payload["cost_per_call"],
        cost_per_unit=payload["cost_per_unit"],
        currency=payload["currency"],
        unit_name=payload["unit_name"],
        monthly_minimum=payload["monthly_minimum"],
        monthly_cap=payload["monthly_cap"],
        tier=payload["tier"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_campaign_budget_binding(payload: dict) -> CampaignBudgetBinding:
    return CampaignBudgetBinding(
        binding_id=payload["binding_id"],
        campaign_id=payload["campaign_id"],
        budget_id=payload["budget_id"],
        allocated_amount=payload["allocated_amount"],
        consumed_amount=payload["consumed_amount"],
        currency=payload["currency"],
        active=payload["active"],
        created_at=payload["created_at"],
    )


def _build_approval_threshold(payload: dict) -> ApprovalThreshold:
    return ApprovalThreshold(
        threshold_id=payload["threshold_id"],
        budget_id=payload["budget_id"],
        mode=ApprovalThresholdMode(payload["mode"]),
        amount=payload["amount"],
        currency=payload["currency"],
        approver_ref=payload["approver_ref"],
        auto_approve_below=payload["auto_approve_below"],
        created_at=payload["created_at"],
    )


def _build_budget_reservation(payload: dict) -> BudgetReservation:
    return BudgetReservation(
        reservation_id=payload["reservation_id"],
        budget_id=payload["budget_id"],
        amount=payload["amount"],
        currency=payload["currency"],
        category=CostCategory(payload["category"]),
        campaign_ref=payload["campaign_ref"],
        step_ref=payload["step_ref"],
        connector_ref=payload["connector_ref"],
        active=payload["active"],
        reason=payload["reason"],
        created_at=payload["created_at"],
        expires_at=payload["expires_at"],
    )


def _build_spend_forecast(payload: dict) -> SpendForecast:
    return SpendForecast(
        forecast_id=payload["forecast_id"],
        budget_id=payload["budget_id"],
        projected_amount=payload["projected_amount"],
        currency=payload["currency"],
        period_start=payload["period_start"],
        period_end=payload["period_end"],
        confidence=payload["confidence"],
        breakdown=payload["breakdown"],
        created_at=payload["created_at"],
    )


def _build_budget_conflict(payload: dict) -> BudgetConflict:
    return BudgetConflict(
        conflict_id=payload["conflict_id"],
        budget_id=payload["budget_id"],
        kind=BudgetConflictKind(payload["kind"]),
        description=payload["description"],
        severity=payload["severity"],
        detected_at=payload["detected_at"],
    )


def _build_budget_decision(payload: dict) -> BudgetDecision:
    return BudgetDecision(
        decision_id=payload["decision_id"],
        budget_id=payload["budget_id"],
        disposition=ChargeDisposition(payload["disposition"]),
        requested_amount=payload["requested_amount"],
        available_amount=payload["available_amount"],
        currency=payload["currency"],
        reason=payload["reason"],
        reservation_id=payload["reservation_id"],
        approval_required=payload["approval_required"],
        approver_ref=payload["approver_ref"],
        decided_at=payload["decided_at"],
    )


def _build_financial_health_snapshot(payload: dict) -> FinancialHealthSnapshot:
    return FinancialHealthSnapshot(
        snapshot_id=payload["snapshot_id"],
        budget_id=payload["budget_id"],
        limit_amount=payload["limit_amount"],
        consumed_amount=payload["consumed_amount"],
        reserved_amount=payload["reserved_amount"],
        available_amount=payload["available_amount"],
        utilization=payload["utilization"],
        currency=payload["currency"],
        warning_triggered=payload["warning_triggered"],
        hard_stop_triggered=payload["hard_stop_triggered"],
        active_reservations=payload["active_reservations"],
        total_spend_records=payload["total_spend_records"],
        captured_at=payload["captured_at"],
    )


def _build_budget_closure_report(payload: dict) -> BudgetClosureReport:
    return BudgetClosureReport(
        report_id=payload["report_id"],
        budget_id=payload["budget_id"],
        limit_amount=payload["limit_amount"],
        total_consumed=payload["total_consumed"],
        total_released=payload["total_released"],
        total_reservations=payload["total_reservations"],
        total_spend_records=payload["total_spend_records"],
        currency=payload["currency"],
        under_budget=payload["under_budget"],
        overspend_amount=payload["overspend_amount"],
        warnings_issued=payload["warnings_issued"],
        hard_stops_triggered=payload["hard_stops_triggered"],
        closed_at=payload["closed_at"],
    )


def _build_ledger_account(payload: dict) -> LedgerAccount:
    return LedgerAccount(
        account_id=payload["account_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        status=LedgerStatus(payload["status"]),
        network=LedgerNetworkKind(payload["network"]),
        balance=payload["balance"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_transaction(payload: dict) -> LedgerTransaction:
    return LedgerTransaction(
        transaction_id=payload["transaction_id"],
        tenant_id=payload["tenant_id"],
        from_account=payload["from_account"],
        to_account=payload["to_account"],
        amount=payload["amount"],
        reference_ref=payload["reference_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_settlement_proof(payload: dict) -> SettlementProof:
    return SettlementProof(
        proof_id=payload["proof_id"],
        tenant_id=payload["tenant_id"],
        transaction_ref=payload["transaction_ref"],
        status=SettlementProofStatus(payload["status"]),
        proof_hash=payload["proof_hash"],
        verified_at=payload["verified_at"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_anchor_record(payload: dict) -> AnchorRecord:
    return AnchorRecord(
        anchor_id=payload["anchor_id"],
        tenant_id=payload["tenant_id"],
        source_ref=payload["source_ref"],
        content_hash=payload["content_hash"],
        disposition=AnchorDisposition(payload["disposition"]),
        anchor_ref=payload["anchor_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_wallet_record(payload: dict) -> WalletRecord:
    return WalletRecord(
        wallet_id=payload["wallet_id"],
        tenant_id=payload["tenant_id"],
        identity_ref=payload["identity_ref"],
        status=WalletStatus(payload["status"]),
        public_key_ref=payload["public_key_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_decision(payload: dict) -> LedgerDecision:
    return LedgerDecision(
        decision_id=payload["decision_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        disposition=payload["disposition"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_snapshot(payload: dict) -> LedgerSnapshot:
    return LedgerSnapshot(
        snapshot_id=payload["snapshot_id"],
        tenant_id=payload["tenant_id"],
        total_accounts=payload["total_accounts"],
        total_transactions=payload["total_transactions"],
        total_proofs=payload["total_proofs"],
        total_anchors=payload["total_anchors"],
        total_wallets=payload["total_wallets"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_violation(payload: dict) -> LedgerViolation:
    return LedgerViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        kind=LedgerViolationKind(payload["kind"]),
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_assessment(payload: dict) -> LedgerAssessment:
    return LedgerAssessment(
        assessment_id=payload["assessment_id"],
        tenant_id=payload["tenant_id"],
        total_confirmed=payload["total_confirmed"],
        total_failed=payload["total_failed"],
        total_disputed=payload["total_disputed"],
        integrity_score=payload["integrity_score"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_ledger_closure_report(payload: dict) -> LedgerClosureReport:
    return LedgerClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_accounts=payload["total_accounts"],
        total_transactions=payload["total_transactions"],
        total_proofs=payload["total_proofs"],
        total_anchors=payload["total_anchors"],
        total_violations=payload["total_violations"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_tenant_record(payload: dict) -> TenantRecord:
    return TenantRecord(
        tenant_id=payload["tenant_id"],
        name=payload["name"],
        status=TenantStatus(payload["status"]),
        isolation_level=IsolationLevel(payload["isolation_level"]),
        owner=payload["owner"],
        workspace_ids=tuple(payload["workspace_ids"]),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
    )


def _build_workspace_record(payload: dict) -> WorkspaceRecord:
    return WorkspaceRecord(
        workspace_id=payload["workspace_id"],
        tenant_id=payload["tenant_id"],
        name=payload["name"],
        status=WorkspaceStatus(payload["status"]),
        isolation_level=IsolationLevel(payload["isolation_level"]),
        environment_ids=tuple(payload["environment_ids"]),
        resource_bindings=tuple(payload["resource_bindings"]),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
    )


def _build_environment_record(payload: dict) -> EnvironmentRecord:
    return EnvironmentRecord(
        environment_id=payload["environment_id"],
        workspace_id=payload["workspace_id"],
        kind=EnvironmentKind(payload["kind"]),
        name=payload["name"],
        promoted_from=payload["promoted_from"],
        connector_ids=tuple(payload["connector_ids"]),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
    )


def _build_boundary_policy(payload: dict) -> BoundaryPolicy:
    return BoundaryPolicy(
        policy_id=payload["policy_id"],
        tenant_id=payload["tenant_id"],
        boundary_kind=ScopeBoundaryKind(payload["boundary_kind"]),
        isolation_level=IsolationLevel(payload["isolation_level"]),
        enforced=payload["enforced"],
        description=payload["description"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_workspace_binding(payload: dict) -> WorkspaceBinding:
    return WorkspaceBinding(
        binding_id=payload["binding_id"],
        workspace_id=payload["workspace_id"],
        resource_ref_id=payload["resource_ref_id"],
        resource_type=ScopeBoundaryKind(payload["resource_type"]),
        environment_id=payload["environment_id"],
        bound_at=payload["bound_at"],
    )


def _build_environment_promotion(payload: dict) -> EnvironmentPromotion:
    return EnvironmentPromotion(
        promotion_id=payload["promotion_id"],
        source_environment_id=payload["source_environment_id"],
        target_environment_id=payload["target_environment_id"],
        status=PromotionStatus(payload["status"]),
        compliance_check_passed=payload["compliance_check_passed"],
        promoted_by=payload["promoted_by"],
        requested_at=payload["requested_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_isolation_violation(payload: dict) -> IsolationViolation:
    return IsolationViolation(
        violation_id=payload["violation_id"],
        tenant_id=payload["tenant_id"],
        workspace_id=payload["workspace_id"],
        boundary_kind=ScopeBoundaryKind(payload["boundary_kind"]),
        violating_resource_ref=payload["violating_resource_ref"],
        description=payload["description"],
        escalated=payload["escalated"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_tenant_health(payload: dict) -> TenantHealth:
    return TenantHealth(
        tenant_id=payload["tenant_id"],
        total_workspaces=payload["total_workspaces"],
        active_workspaces=payload["active_workspaces"],
        total_environments=payload["total_environments"],
        total_bindings=payload["total_bindings"],
        total_violations=payload["total_violations"],
        compliance_pct=payload["compliance_pct"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_tenant_decision(payload: dict) -> TenantDecision:
    return TenantDecision(
        decision_id=payload["decision_id"],
        tenant_id=payload["tenant_id"],
        title=payload["title"],
        description=payload["description"],
        confidence=payload["confidence"],
        decided_by=payload["decided_by"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_tenant_closure_report(payload: dict) -> TenantClosureReport:
    return TenantClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_workspaces=payload["total_workspaces"],
        total_environments=payload["total_environments"],
        total_bindings=payload["total_bindings"],
        total_promotions=payload["total_promotions"],
        total_violations=payload["total_violations"],
        total_decisions=payload["total_decisions"],
        compliance_pct=payload["compliance_pct"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_record_descriptor(payload: dict) -> RecordDescriptor:
    return RecordDescriptor(
        record_id=payload["record_id"],
        tenant_id=payload["tenant_id"],
        kind=RecordKind(payload["kind"]),
        title=payload["title"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        authority=RecordAuthority(payload["authority"]),
        evidence_grade=EvidenceGrade(payload["evidence_grade"]),
        classification=payload["classification"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_retention_schedule(payload: dict) -> RetentionSchedule:
    return RetentionSchedule(
        schedule_id=payload["schedule_id"],
        record_id=payload["record_id"],
        tenant_id=payload["tenant_id"],
        retention_days=payload["retention_days"],
        status=RetentionStatus(payload["status"]),
        disposal_disposition=DisposalDisposition(payload["disposal_disposition"]),
        scope_ref_id=payload["scope_ref_id"],
        created_at=payload["created_at"],
        expires_at=payload["expires_at"],
        metadata=payload["metadata"],
    )


def _build_legal_hold_record(payload: dict) -> LegalHoldRecord:
    return LegalHoldRecord(
        hold_id=payload["hold_id"],
        record_id=payload["record_id"],
        tenant_id=payload["tenant_id"],
        reason=payload["reason"],
        authority=RecordAuthority(payload["authority"]),
        status=HoldStatus(payload["status"]),
        placed_at=payload["placed_at"],
        released_at=payload["released_at"],
        metadata=payload["metadata"],
    )


def _build_disposition_review(payload: dict) -> DispositionReview:
    return DispositionReview(
        review_id=payload["review_id"],
        record_id=payload["record_id"],
        reviewer_id=payload["reviewer_id"],
        decision=DisposalDisposition(payload["decision"]),
        reason=payload["reason"],
        reviewed_at=payload["reviewed_at"],
        metadata=payload["metadata"],
    )


def _build_record_link(payload: dict) -> RecordLink:
    return RecordLink(
        link_id=payload["link_id"],
        record_id=payload["record_id"],
        target_type=payload["target_type"],
        target_id=payload["target_id"],
        relationship=payload["relationship"],
        created_at=payload["created_at"],
    )


def _build_record_snapshot(payload: dict) -> RecordSnapshot:
    return RecordSnapshot(
        snapshot_id=payload["snapshot_id"],
        scope_ref_id=payload["scope_ref_id"],
        total_records=payload["total_records"],
        total_schedules=payload["total_schedules"],
        total_holds=payload["total_holds"],
        active_holds=payload["active_holds"],
        total_links=payload["total_links"],
        total_disposals=payload["total_disposals"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_record_violation(payload: dict) -> RecordViolation:
    return RecordViolation(
        violation_id=payload["violation_id"],
        record_id=payload["record_id"],
        tenant_id=payload["tenant_id"],
        operation=payload["operation"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_preservation_decision(payload: dict) -> PreservationDecision:
    return PreservationDecision(
        decision_id=payload["decision_id"],
        record_id=payload["record_id"],
        preserve=payload["preserve"],
        reason=payload["reason"],
        authority=RecordAuthority(payload["authority"]),
        decided_at=payload["decided_at"],
    )


def _build_disposal_decision(payload: dict) -> DisposalDecision:
    return DisposalDecision(
        decision_id=payload["decision_id"],
        record_id=payload["record_id"],
        tenant_id=payload["tenant_id"],
        disposition=DisposalDisposition(payload["disposition"]),
        reason=payload["reason"],
        authority=RecordAuthority(payload["authority"]),
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_records_closure_report(payload: dict) -> RecordsClosureReport:
    return RecordsClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_records=payload["total_records"],
        total_preserved=payload["total_preserved"],
        total_disposed=payload["total_disposed"],
        total_held=payload["total_held"],
        total_violations=payload["total_violations"],
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
    )


def _build_change_request(payload: dict) -> ChangeRequest:
    return ChangeRequest(
        change_id=payload["change_id"],
        recommendation_id=payload["recommendation_id"],
        change_type=ChangeType(payload["change_type"]),
        scope=ChangeScope(payload["scope"]),
        scope_ref_id=payload["scope_ref_id"],
        title=payload["title"],
        description=payload["description"],
        status=ChangeStatus(payload["status"]),
        rollout_mode=RolloutMode(payload["rollout_mode"]),
        priority=payload["priority"],
        requested_by=payload["requested_by"],
        reason=payload["reason"],
        approval_required=payload["approval_required"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_change_plan(payload: dict) -> ChangePlan:
    return ChangePlan(
        plan_id=payload["plan_id"],
        change_id=payload["change_id"],
        title=payload["title"],
        step_ids=tuple(payload["step_ids"]),
        rollout_mode=RolloutMode(payload["rollout_mode"]),
        estimated_duration_seconds=payload["estimated_duration_seconds"],
        rollback_plan_id=payload["rollback_plan_id"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_change_step(payload: dict) -> ChangeStep:
    return ChangeStep(
        step_id=payload["step_id"],
        plan_id=payload["plan_id"],
        change_id=payload["change_id"],
        ordinal=payload["ordinal"],
        action=payload["action"],
        target_ref_id=payload["target_ref_id"],
        description=payload["description"],
        status=ChangeStatus(payload["status"]),
        started_at=payload["started_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_change_execution(payload: dict) -> ChangeExecution:
    return ChangeExecution(
        execution_id=payload["execution_id"],
        change_id=payload["change_id"],
        plan_id=payload["plan_id"],
        status=ChangeStatus(payload["status"]),
        steps_total=payload["steps_total"],
        steps_completed=payload["steps_completed"],
        steps_failed=payload["steps_failed"],
        rollout_mode=RolloutMode(payload["rollout_mode"]),
        started_at=payload["started_at"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_change_approval_binding(payload: dict) -> ChangeApprovalBinding:
    return ChangeApprovalBinding(
        approval_id=payload["approval_id"],
        change_id=payload["change_id"],
        approved_by=payload["approved_by"],
        approved=payload["approved"],
        reason=payload["reason"],
        approved_at=payload["approved_at"],
    )


def _build_change_evidence(payload: dict) -> ChangeEvidence:
    return ChangeEvidence(
        evidence_id=payload["evidence_id"],
        change_id=payload["change_id"],
        kind=ChangeEvidenceKind(payload["kind"]),
        metric_name=payload["metric_name"],
        metric_value=payload["metric_value"],
        description=payload["description"],
        collected_at=payload["collected_at"],
        metadata=payload["metadata"],
    )


def _build_rollback_plan(payload: dict) -> RollbackPlan:
    return RollbackPlan(
        rollback_id=payload["rollback_id"],
        change_id=payload["change_id"],
        disposition=RollbackDisposition(payload["disposition"]),
        rollback_steps=tuple(payload["rollback_steps"]),
        reason=payload["reason"],
        triggered_at=payload["triggered_at"],
        completed_at=payload["completed_at"],
    )


def _build_change_outcome(payload: dict) -> ChangeOutcome:
    return ChangeOutcome(
        outcome_id=payload["outcome_id"],
        change_id=payload["change_id"],
        execution_id=payload["execution_id"],
        status=ChangeStatus(payload["status"]),
        success=payload["success"],
        improvement_observed=payload["improvement_observed"],
        improvement_pct=payload["improvement_pct"],
        rollback_disposition=RollbackDisposition(payload["rollback_disposition"]),
        evidence_count=payload["evidence_count"],
        completed_at=payload["completed_at"],
        metadata=payload["metadata"],
    )


def _build_change_impact_assessment(payload: dict) -> ChangeImpactAssessment:
    return ChangeImpactAssessment(
        assessment_id=payload["assessment_id"],
        change_id=payload["change_id"],
        metric_name=payload["metric_name"],
        baseline_value=payload["baseline_value"],
        current_value=payload["current_value"],
        improvement_pct=payload["improvement_pct"],
        confidence=payload["confidence"],
        assessment_window_seconds=payload["assessment_window_seconds"],
        assessed_at=payload["assessed_at"],
    )


def _build_causal_node(payload: dict) -> CausalNode:
    return CausalNode(
        node_id=payload["node_id"],
        tenant_id=payload["tenant_id"],
        display_name=payload["display_name"],
        status=CausalStatus(payload["status"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_causal_edge(payload: dict) -> CausalEdge:
    return CausalEdge(
        edge_id=payload["edge_id"],
        tenant_id=payload["tenant_id"],
        cause_ref=payload["cause_ref"],
        effect_ref=payload["effect_ref"],
        kind=CausalEdgeKind(payload["kind"]),
        strength=AttributionStrength(payload["strength"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_intervention_record(payload: dict) -> InterventionRecord:
    return InterventionRecord(
        intervention_id=payload["intervention_id"],
        tenant_id=payload["tenant_id"],
        target_node_ref=payload["target_node_ref"],
        disposition=InterventionDisposition(payload["disposition"]),
        expected_effect=payload["expected_effect"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_counterfactual_scenario(payload: dict) -> CounterfactualScenario:
    return CounterfactualScenario(
        scenario_id=payload["scenario_id"],
        tenant_id=payload["tenant_id"],
        intervention_ref=payload["intervention_ref"],
        premise=payload["premise"],
        status=CounterfactualStatus(payload["status"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_causal_attribution(payload: dict) -> CausalAttribution:
    return CausalAttribution(
        attribution_id=payload["attribution_id"],
        tenant_id=payload["tenant_id"],
        outcome_ref=payload["outcome_ref"],
        cause_ref=payload["cause_ref"],
        strength=AttributionStrength(payload["strength"]),
        evidence_count=payload["evidence_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_propagation_record(payload: dict) -> PropagationRecord:
    return PropagationRecord(
        propagation_id=payload["propagation_id"],
        tenant_id=payload["tenant_id"],
        source_ref=payload["source_ref"],
        target_ref=payload["target_ref"],
        hop_count=payload["hop_count"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_causal_decision(payload: dict) -> CausalDecision:
    return CausalDecision(
        decision_id=payload["decision_id"],
        tenant_id=payload["tenant_id"],
        attribution_ref=payload["attribution_ref"],
        disposition=payload["disposition"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
        metadata=payload["metadata"],
    )


def _build_causal_assessment(payload: dict) -> CausalAssessment:
    return CausalAssessment(
        assessment_id=payload["assessment_id"],
        tenant_id=payload["tenant_id"],
        total_nodes=payload["total_nodes"],
        total_edges=payload["total_edges"],
        total_interventions=payload["total_interventions"],
        attribution_coverage=payload["attribution_coverage"],
        assessed_at=payload["assessed_at"],
        metadata=payload["metadata"],
    )


def _build_causal_snapshot(payload: dict) -> CausalSnapshot:
    return CausalSnapshot(
        snapshot_id=payload["snapshot_id"],
        tenant_id=payload["tenant_id"],
        total_nodes=payload["total_nodes"],
        total_edges=payload["total_edges"],
        total_interventions=payload["total_interventions"],
        total_counterfactuals=payload["total_counterfactuals"],
        total_attributions=payload["total_attributions"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_causal_closure_report(payload: dict) -> CausalClosureReport:
    return CausalClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_nodes=payload["total_nodes"],
        total_edges=payload["total_edges"],
        total_interventions=payload["total_interventions"],
        total_attributions=payload["total_attributions"],
        total_violations=payload["total_violations"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_constraint_definition(payload: dict) -> ConstraintDefinition:
    return ConstraintDefinition(
        constraint_id=payload["constraint_id"],
        tenant_id=payload["tenant_id"],
        kind=ConstraintKind(payload["kind"]),
        expression=payload["expression"],
        variable_refs=payload["variable_refs"],
        priority=payload["priority"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_solver_problem(payload: dict) -> SolverProblem:
    return SolverProblem(
        problem_id=payload["problem_id"],
        tenant_id=payload["tenant_id"],
        algorithm=AlgorithmKind(payload["algorithm"]),
        constraint_count=payload["constraint_count"],
        variable_count=payload["variable_count"],
        status=SolveStatus(payload["status"]),
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_solver_solution(payload: dict) -> SolverSolution:
    return SolverSolution(
        solution_id=payload["solution_id"],
        tenant_id=payload["tenant_id"],
        problem_ref=payload["problem_ref"],
        status=SolveStatus(payload["status"]),
        objective_value=payload["objective_value"],
        iterations=payload["iterations"],
        duration_ms=payload["duration_ms"],
        solved_at=payload["solved_at"],
        metadata=payload["metadata"],
    )


def _build_graph_node(payload: dict) -> GraphNode:
    return GraphNode(
        node_id=payload["node_id"],
        tenant_id=payload["tenant_id"],
        label=payload["label"],
        weight=payload["weight"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_graph_edge(payload: dict) -> GraphEdge:
    return GraphEdge(
        edge_id=payload["edge_id"],
        tenant_id=payload["tenant_id"],
        from_node=payload["from_node"],
        to_node=payload["to_node"],
        weight=payload["weight"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_schedule_slot(payload: dict) -> ScheduleSlot:
    return ScheduleSlot(
        slot_id=payload["slot_id"],
        tenant_id=payload["tenant_id"],
        resource_ref=payload["resource_ref"],
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        priority=payload["priority"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_assignment_record(payload: dict) -> AssignmentRecord:
    return AssignmentRecord(
        assignment_id=payload["assignment_id"],
        tenant_id=payload["tenant_id"],
        resource_ref=payload["resource_ref"],
        task_ref=payload["task_ref"],
        strategy=AssignmentStrategy(payload["strategy"]),
        cost=payload["cost"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_dependency_chain(payload: dict) -> DependencyChain:
    return DependencyChain(
        chain_id=payload["chain_id"],
        tenant_id=payload["tenant_id"],
        source_ref=payload["source_ref"],
        target_ref=payload["target_ref"],
        lag=payload["lag"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_constraint_snapshot(payload: dict) -> ConstraintSnapshot:
    return ConstraintSnapshot(
        snapshot_id=payload["snapshot_id"],
        tenant_id=payload["tenant_id"],
        total_constraints=payload["total_constraints"],
        total_problems=payload["total_problems"],
        total_solutions=payload["total_solutions"],
        total_nodes=payload["total_nodes"],
        total_edges=payload["total_edges"],
        total_violations=payload["total_violations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_constraint_closure_report(payload: dict) -> ConstraintClosureReport:
    return ConstraintClosureReport(
        report_id=payload["report_id"],
        tenant_id=payload["tenant_id"],
        total_constraints=payload["total_constraints"],
        total_problems=payload["total_problems"],
        total_solutions=payload["total_solutions"],
        total_assignments=payload["total_assignments"],
        total_violations=payload["total_violations"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_availability_record(payload: dict) -> AvailabilityRecord:
    return AvailabilityRecord(
        record_id=payload["record_id"],
        identity_ref=payload["identity_ref"],
        kind=AvailabilityKind(payload["kind"]),
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        timezone=payload["timezone"],
        priority_floor=payload["priority_floor"],
        channels_allowed=tuple(payload["channels_allowed"]),
        channels_blocked=tuple(payload["channels_blocked"]),
        reason=payload["reason"],
        active=payload["active"],
        created_at=payload["created_at"],
    )


def _build_scheduling_window(payload: dict) -> SchedulingWindow:
    return SchedulingWindow(
        window_id=payload["window_id"],
        identity_ref=payload["identity_ref"],
        window_type=WindowType(payload["window_type"]),
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        timezone=payload["timezone"],
        capacity=payload["capacity"],
        reserved=payload["reserved"],
        metadata=payload["metadata"],
    )


def _build_business_hours_profile(payload: dict) -> BusinessHoursProfile:
    return BusinessHoursProfile(
        profile_id=payload["profile_id"],
        identity_ref=payload["identity_ref"],
        timezone=payload["timezone"],
        weekday_start_hour=payload["weekday_start_hour"],
        weekday_end_hour=payload["weekday_end_hour"],
        weekend_available=payload["weekend_available"],
        quiet_start_hour=payload["quiet_start_hour"],
        quiet_end_hour=payload["quiet_end_hour"],
        emergency_override=payload["emergency_override"],
        created_at=payload["created_at"],
    )


def _build_meeting_record(payload: dict) -> MeetingRecord:
    return MeetingRecord(
        meeting_id=payload["meeting_id"],
        title=payload["title"],
        organizer_ref=payload["organizer_ref"],
        participant_refs=tuple(payload["participant_refs"]),
        status=MeetingStatus(payload["status"]),
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        timezone=payload["timezone"],
        location=payload["location"],
        campaign_ref=payload["campaign_ref"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_meeting_request(payload: dict) -> MeetingRequest:
    return MeetingRequest(
        request_id=payload["request_id"],
        organizer_ref=payload["organizer_ref"],
        participant_refs=tuple(payload["participant_refs"]),
        duration_minutes=payload["duration_minutes"],
        earliest_start=payload["earliest_start"],
        latest_end=payload["latest_end"],
        preferred_timezone=payload["preferred_timezone"],
        campaign_ref=payload["campaign_ref"],
        title=payload["title"],
        created_at=payload["created_at"],
    )


def _build_meeting_decision(payload: dict) -> MeetingDecision:
    return MeetingDecision(
        decision_id=payload["decision_id"],
        request_id=payload["request_id"],
        meeting_id=payload["meeting_id"],
        scheduled=payload["scheduled"],
        reason=payload["reason"],
        proposed_start=payload["proposed_start"],
        proposed_end=payload["proposed_end"],
        conflicts=tuple(payload["conflicts"]),
        decided_at=payload["decided_at"],
    )


def _build_response_sla(payload: dict) -> ResponseSLA:
    return ResponseSLA(
        sla_id=payload["sla_id"],
        identity_ref=payload["identity_ref"],
        expectation=ResponseExpectation(payload["expectation"]),
        max_response_seconds=payload["max_response_seconds"],
        escalation_after_seconds=payload["escalation_after_seconds"],
        escalation_target=payload["escalation_target"],
        channel_preference=payload["channel_preference"],
        created_at=payload["created_at"],
    )


def _build_availability_conflict(payload: dict) -> AvailabilityConflict:
    return AvailabilityConflict(
        conflict_id=payload["conflict_id"],
        identity_ref=payload["identity_ref"],
        kind=SchedulingConflictKind(payload["kind"]),
        conflicting_window_ids=tuple(payload["conflicting_window_ids"]),
        description=payload["description"],
        severity=payload["severity"],
        detected_at=payload["detected_at"],
    )


def _build_availability_routing_decision(payload: dict) -> AvailabilityRoutingDecision:
    return AvailabilityRoutingDecision(
        decision_id=payload["decision_id"],
        identity_ref=payload["identity_ref"],
        resolution=AvailabilityResolution(payload["resolution"]),
        channel_chosen=payload["channel_chosen"],
        fallback_identity_ref=payload["fallback_identity_ref"],
        contact_at=payload["contact_at"],
        reason=payload["reason"],
        priority_used=payload["priority_used"],
        decided_at=payload["decided_at"],
    )


def _build_identity_record(payload: dict) -> IdentityRecord:
    return IdentityRecord(
        identity_id=payload["identity_id"],
        name=payload["name"],
        kind=IdentityKind(payload["kind"]),
        tenant_id=payload["tenant_id"],
        enabled=payload["enabled"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_role_record(payload: dict) -> RoleRecord:
    return RoleRecord(
        role_id=payload["role_id"],
        name=payload["name"],
        kind=RoleKind(payload["kind"]),
        permissions=tuple(payload["permissions"]),
        description=payload["description"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_permission_rule(payload: dict) -> PermissionRule:
    return PermissionRule(
        rule_id=payload["rule_id"],
        resource_type=payload["resource_type"],
        action=payload["action"],
        effect=PermissionEffect(payload["effect"]),
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        conditions=payload["conditions"],
        created_at=payload["created_at"],
    )


def _build_role_binding(payload: dict) -> RoleBinding:
    return RoleBinding(
        binding_id=payload["binding_id"],
        identity_id=payload["identity_id"],
        role_id=payload["role_id"],
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        bound_at=payload["bound_at"],
    )


def _build_delegation_record(payload: dict) -> DelegationRecord:
    return DelegationRecord(
        delegation_id=payload["delegation_id"],
        from_identity_id=payload["from_identity_id"],
        to_identity_id=payload["to_identity_id"],
        role_id=payload["role_id"],
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        status=AccessDelegationStatus(payload["status"]),
        expires_at=payload["expires_at"],
        delegated_at=payload["delegated_at"],
        revoked_at=payload["revoked_at"],
        metadata=payload["metadata"],
    )


def _build_access_request(payload: dict) -> AccessRequest:
    return AccessRequest(
        request_id=payload["request_id"],
        identity_id=payload["identity_id"],
        resource_type=payload["resource_type"],
        action=payload["action"],
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        requested_at=payload["requested_at"],
    )


def _build_access_evaluation(payload: dict) -> AccessEvaluation:
    return AccessEvaluation(
        evaluation_id=payload["evaluation_id"],
        request_id=payload["request_id"],
        decision=AccessDecision(payload["decision"]),
        matching_rule_ids=tuple(payload["matching_rule_ids"]),
        matching_role_ids=tuple(payload["matching_role_ids"]),
        reason=payload["reason"],
        evaluated_at=payload["evaluated_at"],
    )


def _build_access_violation(payload: dict) -> AccessViolation:
    return AccessViolation(
        violation_id=payload["violation_id"],
        identity_id=payload["identity_id"],
        resource_type=payload["resource_type"],
        action=payload["action"],
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        reason=payload["reason"],
        detected_at=payload["detected_at"],
        metadata=payload["metadata"],
    )


def _build_access_snapshot(payload: dict) -> AccessSnapshot:
    return AccessSnapshot(
        snapshot_id=payload["snapshot_id"],
        scope_ref_id=payload["scope_ref_id"],
        total_identities=payload["total_identities"],
        total_roles=payload["total_roles"],
        total_bindings=payload["total_bindings"],
        total_rules=payload["total_rules"],
        active_delegations=payload["active_delegations"],
        total_violations=payload["total_violations"],
        total_evaluations=payload["total_evaluations"],
        captured_at=payload["captured_at"],
        metadata=payload["metadata"],
    )


def _build_access_audit_record(payload: dict) -> AccessAuditRecord:
    return AccessAuditRecord(
        audit_id=payload["audit_id"],
        identity_id=payload["identity_id"],
        action=payload["action"],
        resource_type=payload["resource_type"],
        decision=AccessDecision(payload["decision"]),
        scope_kind=AuthContextKind(payload["scope_kind"]),
        scope_ref_id=payload["scope_ref_id"],
        recorded_at=payload["recorded_at"],
        metadata=payload["metadata"],
    )


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("access_request.json", _build_access_request),
        ("access_evaluation.json", _build_access_evaluation),
        ("access_violation.json", _build_access_violation),
        ("access_snapshot.json", _build_access_snapshot),
        ("access_audit_record.json", _build_access_audit_record),
        ("aging_snapshot.json", _build_aging_snapshot),
        ("asset_assessment.json", _build_asset_assessment),
        ("asset_assignment.json", _build_asset_assignment),
        ("asset_closure_report.json", _build_asset_closure_report),
        ("asset_dependency.json", _build_asset_dependency),
        ("asset_record.json", _build_asset_record),
        ("asset_snapshot.json", _build_asset_snapshot),
        ("asset_violation.json", _build_asset_violation),
        ("identity_record.json", _build_identity_record),
        ("role_record.json", _build_role_record),
        ("permission_rule.json", _build_permission_rule),
        ("role_binding.json", _build_role_binding),
        ("delegation_record.json", _build_delegation_record),
        ("availability_record.json", _build_availability_record),
        ("scheduling_window.json", _build_scheduling_window),
        ("business_hours_profile.json", _build_business_hours_profile),
        ("meeting_record.json", _build_meeting_record),
        ("meeting_request.json", _build_meeting_request),
        ("meeting_decision.json", _build_meeting_decision),
        ("response_sla.json", _build_response_sla),
        ("availability_conflict.json", _build_availability_conflict),
        ("availability_routing_decision.json", _build_availability_routing_decision),
        ("billing_account.json", _build_billing_account),
        ("billing_closure_report.json", _build_billing_closure_report),
        ("billing_decision.json", _build_billing_decision),
        ("billing_violation.json", _build_billing_violation),
        ("breach_record.json", _build_breach_record),
        ("cash_application.json", _build_cash_application),
        ("charge_record.json", _build_charge_record),
        ("change_request.json", _build_change_request),
        ("change_plan.json", _build_change_plan),
        ("change_step.json", _build_change_step),
        ("change_execution.json", _build_change_execution),
        ("change_approval_binding.json", _build_change_approval_binding),
        ("change_evidence.json", _build_change_evidence),
        ("rollback_plan.json", _build_rollback_plan),
        ("change_outcome.json", _build_change_outcome),
        ("change_impact_assessment.json", _build_change_impact_assessment),
        ("causal_node.json", _build_causal_node),
        ("causal_edge.json", _build_causal_edge),
        ("intervention_record.json", _build_intervention_record),
        ("counterfactual_scenario.json", _build_counterfactual_scenario),
        ("causal_attribution.json", _build_causal_attribution),
        ("propagation_record.json", _build_propagation_record),
        ("causal_decision.json", _build_causal_decision),
        ("causal_assessment.json", _build_causal_assessment),
        ("causal_snapshot.json", _build_causal_snapshot),
        ("causal_closure_report.json", _build_causal_closure_report),
        ("constraint_definition.json", _build_constraint_definition),
        ("solver_problem.json", _build_solver_problem),
        ("solver_solution.json", _build_solver_solution),
        ("graph_node.json", _build_graph_node),
        ("graph_edge.json", _build_graph_edge),
        ("schedule_slot.json", _build_schedule_slot),
        ("assignment_record.json", _build_assignment_record),
        ("dependency_chain.json", _build_dependency_chain),
        ("constraint_snapshot.json", _build_constraint_snapshot),
        ("constraint_closure_report.json", _build_constraint_closure_report),
        ("commitment_record.json", _build_commitment_record),
        ("collection_case.json", _build_collection_case),
        ("configuration_item.json", _build_configuration_item),
        ("contract_assessment.json", _build_contract_assessment),
        ("contract_clause.json", _build_contract_clause),
        ("contract_closure_report.json", _build_contract_closure_report),
        ("contract_snapshot.json", _build_contract_snapshot),
        ("connector_cost_profile.json", _build_connector_cost_profile),
        ("cost_estimate.json", _build_cost_estimate),
        ("credit_record.json", _build_credit_record),
        ("assurance_assessment.json", _build_assurance_assessment),
        ("assurance_closure_report.json", _build_assurance_closure_report),
        ("assurance_decision.json", _build_assurance_decision),
        ("assurance_evidence_binding.json", _build_assurance_evidence_binding),
        ("assurance_finding.json", _build_assurance_finding),
        ("assurance_snapshot.json", _build_assurance_snapshot),
        ("assurance_violation.json", _build_assurance_violation),
        ("attestation_record.json", _build_attestation_record),
        ("approval_board.json", _build_approval_board),
        ("approval_threshold.json", _build_approval_threshold),
        ("board_member.json", _build_board_member),
        ("board_vote.json", _build_board_vote),
        ("budget_closure_report.json", _build_budget_closure_report),
        ("budget_conflict.json", _build_budget_conflict),
        ("budget_decision.json", _build_budget_decision),
        ("budget_envelope.json", _build_budget_envelope),
        ("budget_reservation.json", _build_budget_reservation),
        ("campaign_budget_binding.json", _build_campaign_budget_binding),
        ("case_assignment.json", _build_case_assignment),
        ("case_closure_report.json", _build_case_closure_report),
        ("case_decision.json", _build_case_decision),
        ("case_record.json", _build_case_record),
        ("case_snapshot.json", _build_case_snapshot),
        ("case_violation.json", _build_case_violation),
        ("certification_record.json", _build_certification_record),
        ("collaborative_decision.json", _build_collaborative_decision),
        ("conflict_record.json", _build_conflict_record),
        ("delegation_request.json", _build_delegation_request),
        ("delegation_result.json", _build_delegation_result),
        ("continuity_closure_report.json", _build_continuity_closure_report),
        ("continuity_plan.json", _build_continuity_plan),
        ("continuity_snapshot.json", _build_continuity_snapshot),
        ("continuity_violation.json", _build_continuity_violation),
        ("customer_closure_report.json", _build_customer_closure_report),
        ("customer_decision.json", _build_customer_decision),
        ("customer_record.json", _build_customer_record),
        ("customer_snapshot.json", _build_customer_snapshot),
        ("customer_violation.json", _build_customer_violation),
        ("governance_contract_record.json", _build_governance_contract_record),
        ("disruption_event.json", _build_disruption_event),
        ("dispute_record.json", _build_dispute_record),
        ("dunning_notice.json", _build_dunning_notice),
        ("entitlement_record.json", _build_entitlement_record),
        ("evidence_collection.json", _build_evidence_collection),
        ("evidence_item.json", _build_evidence_item),
        ("failover_record.json", _build_failover_record),
        ("finding_record.json", _build_finding_record),
        ("handoff_record.json", _build_handoff_record),
        ("handoff_packet.json", _build_handoff_packet),
        ("human_task_record.json", _build_human_task_record),
        ("human_workflow_closure_report.json", _build_human_workflow_closure_report),
        ("human_workflow_snapshot.json", _build_human_workflow_snapshot),
        ("human_workflow_violation.json", _build_human_workflow_violation),
        ("incident_record.json", _build_incident_record),
        ("inventory_record.json", _build_inventory_record),
        ("invoice_record.json", _build_invoice_record),
        ("lifecycle_event.json", _build_lifecycle_event),
        ("ledger_account.json", _build_ledger_account),
        ("ledger_assessment.json", _build_ledger_assessment),
        ("ledger_closure_report.json", _build_ledger_closure_report),
        ("ledger_decision.json", _build_ledger_decision),
        ("ledger_snapshot.json", _build_ledger_snapshot),
        ("ledger_transaction.json", _build_ledger_transaction),
        ("ledger_violation.json", _build_ledger_violation),
        ("listing_record.json", _build_listing_record),
        ("merge_decision.json", _build_merge_decision),
        ("marketplace_assessment.json", _build_marketplace_assessment),
        ("marketplace_closure_report.json", _build_marketplace_closure_report),
        ("marketplace_snapshot.json", _build_marketplace_snapshot),
        ("marketplace_violation.json", _build_marketplace_violation),
        ("payment_record.json", _build_payment_record),
        ("package_record.json", _build_package_record),
        ("penalty_record.json", _build_penalty_record),
        ("partner_account_link.json", _build_partner_account_link),
        ("partner_closure_report.json", _build_partner_closure_report),
        ("partner_commitment.json", _build_partner_commitment),
        ("partner_decision.json", _build_partner_decision),
        ("partner_health_snapshot.json", _build_partner_health_snapshot),
        ("partner_record.json", _build_partner_record),
        ("partner_snapshot.json", _build_partner_snapshot),
        ("partner_violation.json", _build_partner_violation),
        ("pricing_binding.json", _build_pricing_binding),
        ("procurement_closure_report.json", _build_procurement_closure_report),
        ("procurement_decision.json", _build_procurement_decision),
        ("procurement_renewal_window.json", _build_procurement_renewal_window),
        ("procurement_request.json", _build_procurement_request),
        ("procurement_snapshot.json", _build_procurement_snapshot),
        ("product_record.json", _build_product_record),
        ("purchase_order.json", _build_purchase_order),
        ("offering_record.json", _build_offering_record),
        ("bundle_record.json", _build_bundle_record),
        ("eligibility_rule.json", _build_eligibility_rule),
        ("ecosystem_agreement.json", _build_ecosystem_agreement),
        ("recovery_objective.json", _build_recovery_objective),
        ("recovery_execution.json", _build_recovery_execution),
        ("recovery_decision.json", _build_recovery_decision),
        ("recovery_attempt.json", _build_recovery_attempt),
        ("recovery_plan.json", _build_recovery_plan),
        ("recovery_record.json", _build_recovery_record),
        ("revenue_share_record.json", _build_revenue_share_record),
        ("revenue_snapshot.json", _build_revenue_snapshot),
        ("refund_record.json", _build_refund_record),
        ("remedy_record.json", _build_remedy_record),
        ("record_descriptor.json", _build_record_descriptor),
        ("retention_schedule.json", _build_retention_schedule),
        ("legal_hold_record.json", _build_legal_hold_record),
        ("disposition_review.json", _build_disposition_review),
        ("record_link.json", _build_record_link),
        ("record_snapshot.json", _build_record_snapshot),
        ("record_violation.json", _build_record_violation),
        ("preservation_decision.json", _build_preservation_decision),
        ("disposal_decision.json", _build_disposal_decision),
        ("records_closure_report.json", _build_records_closure_report),
        ("review_packet.json", _build_review_packet),
        ("review_record.json", _build_review_record),
        ("recertification_window.json", _build_recertification_window),
        ("renewal_window.json", _build_renewal_window),
        ("anchor_record.json", _build_anchor_record),
        ("settlement_closure_report.json", _build_settlement_closure_report),
        ("settlement_decision.json", _build_settlement_decision),
        ("settlement_proof.json", _build_settlement_proof),
        ("settlement_record.json", _build_settlement_record),
        ("sla_window.json", _build_sla_window),
        ("spend_forecast.json", _build_spend_forecast),
        ("spend_record.json", _build_spend_record),
        ("subscription_record.json", _build_subscription_record),
        ("tenant_closure_report.json", _build_tenant_closure_report),
        ("tenant_decision.json", _build_tenant_decision),
        ("tenant_health.json", _build_tenant_health),
        ("tenant_record.json", _build_tenant_record),
        ("workspace_binding.json", _build_workspace_binding),
        ("workspace_record.json", _build_workspace_record),
        ("environment_promotion.json", _build_environment_promotion),
        ("environment_record.json", _build_environment_record),
        ("boundary_policy.json", _build_boundary_policy),
        ("isolation_violation.json", _build_isolation_violation),
        ("verification_record.json", _build_verification_record),
        ("vendor_assessment.json", _build_vendor_assessment),
        ("vendor_commitment.json", _build_vendor_commitment),
        ("vendor_record.json", _build_vendor_record),
        ("vendor_violation.json", _build_vendor_violation),
        ("wallet_record.json", _build_wallet_record),
        ("writeoff_record.json", _build_writeoff_record),
        ("account_health_snapshot.json", _build_account_health_snapshot),
        ("account_record.json", _build_account_record),
        ("financial_health_snapshot.json", _build_financial_health_snapshot),
    ],
)
def test_mcoi_runtime_fixture_round_trips_exactly_through_mcoi_contracts(
    fixture_name: str,
    builder,
) -> None:
    fixture_payload = _load_fixture(fixture_name)
    contract = builder(fixture_payload)

    rendered = contract.to_json_dict()

    assert isinstance(rendered, dict)
    assert rendered == fixture_payload
    assert json.loads(contract.to_json()) == fixture_payload
