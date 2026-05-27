"""Tests for the governed organization kernel v0.

Purpose: verify organizations, departments, authority, cases, plans, evidence,
step gates, terminal closure, and learning binding are explicit and governed.
Governance scope: Organization Kernel v0 and Launch Gateway Pilot case loop.
Invariants:
  - A pilot case has five accountable departments and an owned plan.
  - Plan steps do not pass without preconditions, evidence, authority, and approval.
  - Terminal closure requires matching reconciliation or explicit non-committed disposition.
  - Learning admission binding requires an existing terminal closure.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.effect_assurance import ReconciliationStatus
from mcoi_runtime.contracts.organization_kernel import (
    ApprovalRecord,
    CaseEvidence,
    LearningAdmissionBinding,
    OrganizationEffectReconciliation,
    OrganizationPlan,
    OrganizationProfile,
    PlanStep,
    PlanStepGateDecision,
    PlanStepGateStatus,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.organization_kernel import (
    DEFAULT_ORGANIZATION_DEPARTMENT_IDS,
    OrganizationKernel,
    bootstrap_minimum_organization,
    open_launch_gateway_pilot,
)


def _clock():
    counter = [0]

    def now() -> str:
        value = counter[0]
        counter[0] += 1
        return f"2026-05-27T17:00:{value:02d}+00:00"

    return now


def _kernel() -> OrganizationKernel:
    kernel = OrganizationKernel(clock=_clock())
    bootstrap_minimum_organization(
        kernel,
        OrganizationProfile(
            org_id="org-mullu",
            tenant_id="tenant-mullu",
            name="Mullu",
            created_at="2026-05-27T17:00:00+00:00",
        ),
    )
    return kernel


def _pilot() -> tuple[OrganizationKernel, OrganizationPlan]:
    kernel = _kernel()
    _case, plan = open_launch_gateway_pilot(kernel, org_id="org-mullu")
    return kernel, plan


def _admit_all_pilot_evidence(kernel: OrganizationKernel, case_id: str) -> None:
    for requirement_id in (
        "executive_objective",
        "product_launch_boundary",
        "engineering_health_endpoint",
        "engineering_gateway_witness",
        "engineering_runtime_conformance",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    ):
        kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=f"evidence:{requirement_id}",
                case_id=case_id,
                requirement_id=requirement_id,
                submitted_by="test-harness",
                submitted_at="2026-05-27T17:01:00+00:00",
            )
        )


def _record_security_dual_control_approval(kernel: OrganizationKernel, case_id: str) -> ApprovalRecord:
    return kernel.record_approval(
        ApprovalRecord(
            approval_id="approval.security.executive",
            case_id=case_id,
            role_id="executive.owner",
            approval_scope="security_approval",
            approved_by="human-executive",
            approved_at="2026-05-27T17:02:00+00:00",
        )
    )


def _allow_all_plan_steps(kernel: OrganizationKernel, plan: OrganizationPlan) -> None:
    for step in plan.steps:
        decision = kernel.evaluate_plan_step(
            case_id=plan.case_id,
            step_id=step.step_id,
            checked_preconditions=step.preconditions,
        )
        assert decision.status is PlanStepGateStatus.ALLOWED
        assert decision.authority_rule_ids
        assert decision.evidence_refs


def _match_reconciliation(case_id: str) -> OrganizationEffectReconciliation:
    return OrganizationEffectReconciliation(
        reconciliation_id="recon.launch.match",
        case_id=case_id,
        expected_effect="gateway_pilot_published",
        observed_effect="gateway_pilot_published",
        status=ReconciliationStatus.MATCH,
        forbidden_effects_checked=True,
        evidence_refs=("evidence:terminal:gateway-pilot",),
        reconciled_at="2026-05-27T17:03:00+00:00",
    )


def test_launch_gateway_pilot_opens_planned_case_with_five_departments() -> None:
    kernel, plan = _pilot()
    organization_case = kernel.get_case(plan.case_id)

    assert kernel.department_count == 5
    assert organization_case is not None
    assert organization_case.status.value == "planned"
    assert organization_case.assigned_department_ids == DEFAULT_ORGANIZATION_DEPARTMENT_IDS
    assert len(plan.steps) == 5
    assert tuple(step.department_id for step in plan.steps) == DEFAULT_ORGANIZATION_DEPARTMENT_IDS


def test_plan_step_gate_blocks_missing_preconditions_then_missing_evidence() -> None:
    kernel, plan = _pilot()
    step = plan.steps[0]

    missing_preconditions = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id=step.step_id,
        checked_preconditions=(),
    )
    missing_evidence = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id=step.step_id,
        checked_preconditions=step.preconditions,
    )

    assert missing_preconditions.status is PlanStepGateStatus.BLOCKED
    assert missing_preconditions.reason == "preconditions_missing"
    assert missing_evidence.status is PlanStepGateStatus.BLOCKED
    assert missing_evidence.reason == "evidence_missing"
    assert missing_evidence.authority_rule_ids == ("authority.executive.objective.freeze",)


def test_plan_step_gate_allows_after_evidence_authority_and_approval() -> None:
    kernel, plan = _pilot()
    _admit_all_pilot_evidence(kernel, plan.case_id)
    approval = _record_security_dual_control_approval(kernel, plan.case_id)
    step = next(candidate for candidate in plan.steps if candidate.step_id == "security_claim_boundary")

    decision = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id=step.step_id,
        checked_preconditions=step.preconditions,
    )

    assert decision.status is PlanStepGateStatus.ALLOWED
    assert decision.reason == "allowed"
    assert decision.approval_refs == (approval.approval_id,)
    assert decision.authority_rule_ids == ("authority.security.public_claim_boundary.check",)
    assert decision.evidence_refs == ("evidence:security_public_claim_boundary", "evidence:security_approval")


def test_dual_control_blocks_self_approval_for_security_step() -> None:
    kernel, plan = _pilot()
    _admit_all_pilot_evidence(kernel, plan.case_id)
    kernel.record_approval(
        ApprovalRecord(
            approval_id="approval.security.self",
            case_id=plan.case_id,
            role_id="security_compliance.owner",
            approval_scope="security_approval",
            approved_by="human-security",
            approved_at="2026-05-27T17:02:00+00:00",
        )
    )
    step = next(candidate for candidate in plan.steps if candidate.step_id == "security_claim_boundary")

    decision = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id=step.step_id,
        checked_preconditions=step.preconditions,
    )

    assert decision.status is PlanStepGateStatus.BLOCKED
    assert decision.reason == "dual_control_missing"
    assert decision.approval_refs == ("approval.security.self",)
    assert decision.authority_rule_ids == ("authority.security.public_claim_boundary.check",)


def test_terminal_closure_requires_reconciliation_match_for_committed_case() -> None:
    kernel, plan = _pilot()
    _admit_all_pilot_evidence(kernel, plan.case_id)
    _record_security_dual_control_approval(kernel, plan.case_id)
    _allow_all_plan_steps(kernel, plan)
    mismatch = OrganizationEffectReconciliation(
        reconciliation_id="recon.launch.mismatch",
        case_id=plan.case_id,
        expected_effect="gateway_pilot_published",
        observed_effect="gateway_pilot_pending",
        status=ReconciliationStatus.MISMATCH,
        forbidden_effects_checked=True,
        evidence_refs=("evidence:terminal:gateway-pilot",),
        reconciled_at="2026-05-27T17:03:00+00:00",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="reconciliation match"):
        kernel.close_case(
            reconciliation=mismatch,
            terminal_disposition=TerminalClosureDisposition.COMMITTED,
            terminal_certificate_id="terminal.certificate.gateway-pilot.mismatch",
        )
    closure = kernel.close_case(
        reconciliation=_match_reconciliation(plan.case_id),
        terminal_disposition=TerminalClosureDisposition.COMMITTED,
        terminal_certificate_id="terminal.certificate.gateway-pilot",
    )
    closed_case = kernel.get_case(plan.case_id)

    assert closure.terminal_disposition is TerminalClosureDisposition.COMMITTED
    assert closure.evidence_refs == ("evidence:terminal:gateway-pilot",)
    assert closed_case is not None
    assert closed_case.status.value == "closed"
    assert kernel.closure_count == 1


def test_learning_admission_binding_requires_existing_terminal_closure() -> None:
    kernel, plan = _pilot()
    binding = LearningAdmissionBinding(
        binding_id="learning.binding.gateway-pilot",
        case_id=plan.case_id,
        closure_id="missing-closure",
        decision_id="learning.decision.gateway-pilot",
        admitted=True,
        created_at="2026-05-27T17:04:00+00:00",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="terminal closure unavailable"):
        kernel.bind_learning_admission(binding)
    _admit_all_pilot_evidence(kernel, plan.case_id)
    _record_security_dual_control_approval(kernel, plan.case_id)
    _allow_all_plan_steps(kernel, plan)
    closure = kernel.close_case(
        reconciliation=_match_reconciliation(plan.case_id),
        terminal_disposition=TerminalClosureDisposition.COMMITTED,
        terminal_certificate_id="terminal.certificate.gateway-pilot",
    )
    admitted = kernel.bind_learning_admission(
        LearningAdmissionBinding(
            binding_id="learning.binding.gateway-pilot",
            case_id=plan.case_id,
            closure_id=closure.closure_id,
            decision_id="learning.decision.gateway-pilot",
            admitted=True,
            created_at="2026-05-27T17:04:00+00:00",
        )
    )

    assert admitted.admitted is True
    assert admitted.closure_id == closure.closure_id
    assert kernel.list_case_events(plan.case_id)[-1].event_type == "learning_admission_bound"


def test_organization_plan_rejects_cycles() -> None:
    first = PlanStep(
        step_id="first",
        case_id="case-cycle",
        department_id="executive",
        responsible_role_id="executive.owner",
        capability_id="executive.objective.freeze",
        action="freeze_objective",
        expected_effect="objective_frozen",
        preconditions=("objective_received",),
        postconditions=("objective_frozen",),
        evidence_required=("executive_objective",),
        predecessor_step_ids=("second",),
    )
    second = PlanStep(
        step_id="second",
        case_id="case-cycle",
        department_id="product",
        responsible_role_id="product.owner",
        capability_id="product.launch_boundary.define",
        action="define_launch_boundary",
        expected_effect="launch_boundary_defined",
        preconditions=("objective_frozen",),
        postconditions=("launch_boundary_defined",),
        evidence_required=("product_launch_boundary",),
        predecessor_step_ids=("first",),
    )

    with pytest.raises(ValueError, match="cycles"):
        OrganizationPlan(
            plan_id="plan-cycle",
            case_id="case-cycle",
            steps=(first, second),
            created_at="2026-05-27T17:00:00+00:00",
        )
    assert first.step_id == "first"
    assert second.predecessor_step_ids == ("first",)


def test_allowed_step_gate_contract_requires_authority_and_evidence() -> None:
    with pytest.raises(ValueError, match="authority_rule_ids"):
        PlanStepGateDecision(
            decision_id="gate.invalid",
            case_id="case-invalid",
            step_id="step-invalid",
            status=PlanStepGateStatus.ALLOWED,
            reason="allowed",
            authority_rule_ids=(),
            evidence_refs=("evidence:one",),
            approval_refs=(),
            decided_at="2026-05-27T17:00:00+00:00",
        )
    assert PlanStepGateStatus.ALLOWED.value == "allowed"
    assert PlanStepGateStatus.BLOCKED.value == "blocked"
