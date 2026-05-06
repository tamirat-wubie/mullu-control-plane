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
    CaseClosureDisposition,
    CaseClosureReport,
    CaseDecision,
    CaseKind,
    CaseRecord,
    CaseSeverity,
    CaseStatus,
    EvidenceItem,
    EvidenceStatus,
    ReviewDisposition,
    ReviewRecord,
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


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("case_closure_report.json", _build_case_closure_report),
        ("case_decision.json", _build_case_decision),
        ("case_record.json", _build_case_record),
        ("conflict_record.json", _build_conflict_record),
        ("delegation_request.json", _build_delegation_request),
        ("delegation_result.json", _build_delegation_result),
        ("continuity_closure_report.json", _build_continuity_closure_report),
        ("continuity_plan.json", _build_continuity_plan),
        ("continuity_snapshot.json", _build_continuity_snapshot),
        ("continuity_violation.json", _build_continuity_violation),
        ("disruption_event.json", _build_disruption_event),
        ("evidence_item.json", _build_evidence_item),
        ("failover_record.json", _build_failover_record),
        ("handoff_record.json", _build_handoff_record),
        ("incident_record.json", _build_incident_record),
        ("merge_decision.json", _build_merge_decision),
        ("recovery_objective.json", _build_recovery_objective),
        ("recovery_execution.json", _build_recovery_execution),
        ("recovery_decision.json", _build_recovery_decision),
        ("recovery_attempt.json", _build_recovery_attempt),
        ("recovery_plan.json", _build_recovery_plan),
        ("recovery_record.json", _build_recovery_record),
        ("review_record.json", _build_review_record),
        ("verification_record.json", _build_verification_record),
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
