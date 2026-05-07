"""Purpose: verify canonical MCOI runtime fixtures round-trip through MCOI contracts.
Governance scope: exact witness conformance for MCOI-only runtime contract surfaces.
Dependencies: shared MCOI runtime fixtures and continuity / incident / recovery contract modules.
Invariants: canonical payload witnesses preserve exact JSON rendering across bounded MCOI runtime contracts.
"""

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


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("aging_snapshot.json", _build_aging_snapshot),
        ("asset_assessment.json", _build_asset_assessment),
        ("asset_assignment.json", _build_asset_assignment),
        ("asset_closure_report.json", _build_asset_closure_report),
        ("asset_dependency.json", _build_asset_dependency),
        ("asset_record.json", _build_asset_record),
        ("asset_snapshot.json", _build_asset_snapshot),
        ("asset_violation.json", _build_asset_violation),
        ("billing_account.json", _build_billing_account),
        ("billing_closure_report.json", _build_billing_closure_report),
        ("billing_decision.json", _build_billing_decision),
        ("billing_violation.json", _build_billing_violation),
        ("breach_record.json", _build_breach_record),
        ("cash_application.json", _build_cash_application),
        ("charge_record.json", _build_charge_record),
        ("commitment_record.json", _build_commitment_record),
        ("collection_case.json", _build_collection_case),
        ("configuration_item.json", _build_configuration_item),
        ("contract_assessment.json", _build_contract_assessment),
        ("contract_clause.json", _build_contract_clause),
        ("contract_closure_report.json", _build_contract_closure_report),
        ("contract_snapshot.json", _build_contract_snapshot),
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
        ("board_member.json", _build_board_member),
        ("board_vote.json", _build_board_vote),
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
        ("review_packet.json", _build_review_packet),
        ("review_record.json", _build_review_record),
        ("recertification_window.json", _build_recertification_window),
        ("renewal_window.json", _build_renewal_window),
        ("settlement_closure_report.json", _build_settlement_closure_report),
        ("settlement_decision.json", _build_settlement_decision),
        ("settlement_record.json", _build_settlement_record),
        ("sla_window.json", _build_sla_window),
        ("subscription_record.json", _build_subscription_record),
        ("verification_record.json", _build_verification_record),
        ("vendor_assessment.json", _build_vendor_assessment),
        ("vendor_commitment.json", _build_vendor_commitment),
        ("vendor_record.json", _build_vendor_record),
        ("vendor_violation.json", _build_vendor_violation),
        ("writeoff_record.json", _build_writeoff_record),
        ("account_health_snapshot.json", _build_account_health_snapshot),
        ("account_record.json", _build_account_record),
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
