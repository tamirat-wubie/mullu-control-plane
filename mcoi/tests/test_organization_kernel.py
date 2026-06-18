"""Tests for the governed organization kernel v0.

Purpose: verify organizations, departments, authority, cases, plans, evidence,
step gates, terminal closure, and learning binding are explicit and governed.
Governance scope: Organization Kernel v0 and Launch Gateway Pilot case loop.
Invariants:
  - A pilot case has five accountable departments and an owned plan.
  - Plan steps do not pass without preconditions, evidence, authority, and approval.
  - Terminal closure requires matching reconciliation or explicit non-committed disposition.
  - Learning admission binding requires an existing terminal closure and admitted case evidence.
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
    PlanStepWorkerDispatchReceipt,
    PlanStepWorkerLeaseReceipt,
    PlanStepWorkerReceiptBinding,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.organization_kernel import (
    DEFAULT_ORGANIZATION_DEPARTMENT_IDS,
    LEARNING_ADMISSION_DECISION_REQUIREMENT,
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
        LEARNING_ADMISSION_DECISION_REQUIREMENT,
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


def _latest_gate_evidence_refs(kernel: OrganizationKernel, case_id: str) -> tuple[str, ...]:
    state = kernel.snapshot_state()
    decisions = {decision.decision_id: decision for decision in state.gate_decisions}
    refs: list[str] = []
    for latest in state.latest_gate_decisions:
        if latest.case_id != case_id:
            continue
        decision = decisions[latest.decision_id]
        for evidence_ref in decision.evidence_refs:
            if evidence_ref not in refs:
                refs.append(evidence_ref)
    return tuple(refs)


def _match_reconciliation(case_id: str, evidence_refs: tuple[str, ...]) -> OrganizationEffectReconciliation:
    return OrganizationEffectReconciliation(
        reconciliation_id="recon.launch.match",
        case_id=case_id,
        expected_effect="gateway_pilot_published",
        observed_effect="gateway_pilot_published",
        status=ReconciliationStatus.MATCH,
        forbidden_effects_checked=True,
        evidence_refs=evidence_refs,
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


def test_plan_step_gate_binds_latest_admitted_evidence_for_requirement() -> None:
    kernel, plan = _pilot()
    _admit_all_pilot_evidence(kernel, plan.case_id)
    _record_security_dual_control_approval(kernel, plan.case_id)
    kernel.admit_case_evidence(
        CaseEvidence(
            evidence_ref="evidence:security_public_claim_boundary:v2",
            case_id=plan.case_id,
            requirement_id="security_public_claim_boundary",
            submitted_by="test-harness",
            submitted_at="2026-05-27T17:03:00+00:00",
        )
    )
    step = next(candidate for candidate in plan.steps if candidate.step_id == "security_claim_boundary")

    decision = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id=step.step_id,
        checked_preconditions=step.preconditions,
    )

    assert decision.status is PlanStepGateStatus.ALLOWED
    assert decision.reason == "allowed"
    assert "evidence:security_public_claim_boundary:v2" in decision.evidence_refs
    assert "evidence:security_public_claim_boundary" not in decision.evidence_refs


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
    closure_evidence_refs = _latest_gate_evidence_refs(kernel, plan.case_id)
    mismatch = OrganizationEffectReconciliation(
        reconciliation_id="recon.launch.mismatch",
        case_id=plan.case_id,
        expected_effect="gateway_pilot_published",
        observed_effect="gateway_pilot_pending",
        status=ReconciliationStatus.MISMATCH,
        forbidden_effects_checked=True,
        evidence_refs=closure_evidence_refs,
        reconciled_at="2026-05-27T17:03:00+00:00",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="reconciliation match"):
        kernel.close_case(
            reconciliation=mismatch,
            terminal_disposition=TerminalClosureDisposition.COMMITTED,
            terminal_certificate_id="terminal.certificate.gateway-pilot.mismatch",
        )
    closure = kernel.close_case(
        reconciliation=_match_reconciliation(plan.case_id, closure_evidence_refs),
        terminal_disposition=TerminalClosureDisposition.COMMITTED,
        terminal_certificate_id="terminal.certificate.gateway-pilot",
    )
    closed_case = kernel.get_case(plan.case_id)

    assert closure.terminal_disposition is TerminalClosureDisposition.COMMITTED
    assert closure.evidence_refs == closure_evidence_refs
    assert closed_case is not None
    assert closed_case.status.value == "closed"
    assert kernel.closure_count == 1


def test_terminal_closure_requires_latest_gate_evidence_refs() -> None:
    kernel, plan = _pilot()
    _admit_all_pilot_evidence(kernel, plan.case_id)
    _record_security_dual_control_approval(kernel, plan.case_id)
    _allow_all_plan_steps(kernel, plan)

    with pytest.raises(RuntimeCoreInvariantError, match="gate evidence refs"):
        kernel.close_case(
            reconciliation=_match_reconciliation(
                plan.case_id,
                ("evidence:terminal:gateway-pilot",),
            ),
            terminal_disposition=TerminalClosureDisposition.COMMITTED,
            terminal_certificate_id="terminal.certificate.gateway-pilot",
        )

    assert kernel.closure_count == 0


def test_learning_admission_binding_requires_existing_terminal_closure() -> None:
    kernel, plan = _pilot()
    binding = LearningAdmissionBinding(
        binding_id="learning.binding.gateway-pilot",
        case_id=plan.case_id,
        closure_id="missing-closure",
        decision_id="learning.decision.gateway-pilot",
        admitted=True,
        evidence_refs=("evidence:learning_admission_decision",),
        created_at="2026-05-27T17:04:00+00:00",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="terminal closure unavailable"):
        kernel.bind_learning_admission(binding)
    _admit_all_pilot_evidence(kernel, plan.case_id)
    _record_security_dual_control_approval(kernel, plan.case_id)
    _allow_all_plan_steps(kernel, plan)
    closure = kernel.close_case(
        reconciliation=_match_reconciliation(plan.case_id, _latest_gate_evidence_refs(kernel, plan.case_id)),
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
            evidence_refs=("evidence:learning_admission_decision",),
            created_at="2026-05-27T17:04:00+00:00",
        )
    )

    assert admitted.admitted is True
    assert admitted.closure_id == closure.closure_id
    assert admitted.evidence_refs == ("evidence:learning_admission_decision",)
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


_ENGINEERING_WITNESS_REQUIREMENTS = (
    ("engineering_health_endpoint", "/health"),
    ("engineering_gateway_witness", "/gateway/witness"),
    ("engineering_runtime_conformance", "/runtime/conformance"),
)


def _ensure_worker_lease_evidence(kernel: OrganizationKernel, case_id: str) -> None:
    if any(evidence.evidence_ref == "evidence:product_launch_boundary" for evidence in kernel.snapshot_state().case_evidence):
        return
    kernel.admit_case_evidence(
        CaseEvidence(
            evidence_ref="evidence:product_launch_boundary",
            case_id=case_id,
            requirement_id="product_launch_boundary",
            submitted_by="test-harness",
            submitted_at="2026-05-27T17:01:00+00:00",
        )
    )


def _record_engineering_dispatch_receipt(
    kernel: OrganizationKernel,
    case_id: str,
    requirement_id: str,
) -> tuple[str, str, str]:
    _ensure_worker_lease_evidence(kernel, case_id)
    lease_id = f"lease.eng.gateway.{requirement_id}"
    dispatch_request_id = f"req.{requirement_id}"
    dispatch_receipt_id = f"receipt.{requirement_id}"
    lease = kernel.create_worker_lease_receipt(
        PlanStepWorkerLeaseReceipt(
            lease_id=lease_id,
            case_id=case_id,
            step_id="engineering_runtime_witness",
            capability_id="engineering.gateway_runtime.verify",
            responsible_role_id="engineering.owner",
            requested_by_role_id="engineering.owner",
            dispatch_lease_preview_id=f"dispatch-lease-preview.{requirement_id}",
            queued_action="bind_worker_receipt",
            capability_action="verify_gateway_runtime",
            expected_effect="gateway_runtime_witnessed",
            evidence_refs=("evidence:product_launch_boundary",),
            timeout_seconds=900,
            budget_ref="budget:gateway-pilot",
            created_at="2026-05-27T17:02:00+00:00",
        )
    )
    kernel.record_worker_dispatch_receipt(
        PlanStepWorkerDispatchReceipt(
            dispatch_receipt_id=dispatch_receipt_id,
            dispatch_request_id=dispatch_request_id,
            case_id=case_id,
            step_id="engineering_runtime_witness",
            worker_lease_id=lease.lease_id,
            capability_id="engineering.gateway_runtime.verify",
            responsible_role_id="engineering.owner",
            requested_by_role_id="engineering.owner",
            worker_id="worker:gateway-runtime",
            dispatch_intent="request_gateway_runtime_verification",
            expected_effect=lease.expected_effect,
            evidence_refs=lease.evidence_refs,
            lease_created_at=lease.created_at,
            dispatched_at="2026-05-27T17:02:30+00:00",
        )
    )
    return lease_id, dispatch_request_id, dispatch_receipt_id


def _bind_engineering_worker_receipts(kernel: OrganizationKernel, case_id: str) -> None:
    for requirement_id, route in _ENGINEERING_WITNESS_REQUIREMENTS:
        lease_id, dispatch_request_id, dispatch_receipt_id = _record_engineering_dispatch_receipt(
            kernel,
            case_id,
            requirement_id,
        )
        kernel.bind_worker_receipt_evidence(
            PlanStepWorkerReceiptBinding(
                binding_id=f"binding.{requirement_id}",
                case_id=case_id,
                step_id="engineering_runtime_witness",
                requirement_id=requirement_id,
                worker_lease_id=lease_id,
                dispatch_request_id=dispatch_request_id,
                dispatch_receipt_id=dispatch_receipt_id,
                worker_output_hash=f"hash-{requirement_id}",
                receipt_evidence_refs=(f"worker-evidence:{route}",),
                admitted_evidence_ref=f"evidence:{requirement_id}",
                bound_at="2026-05-27T17:03:00+00:00",
            )
        )


def test_worker_receipts_satisfy_engineering_gate_evidence() -> None:
    kernel, plan = _pilot()
    _bind_engineering_worker_receipts(kernel, plan.case_id)

    decision = kernel.evaluate_plan_step(
        case_id=plan.case_id,
        step_id="engineering_runtime_witness",
        checked_preconditions=("launch_boundary_defined",),
    )

    assert decision.status is PlanStepGateStatus.ALLOWED
    assert decision.reason == "allowed"
    assert set(decision.evidence_refs) == {
        "evidence:engineering_health_endpoint",
        "evidence:engineering_gateway_witness",
        "evidence:engineering_runtime_conformance",
    }


def test_terminal_closure_requires_worker_bound_gate_evidence_refs() -> None:
    kernel, plan = _pilot()
    _bind_engineering_worker_receipts(kernel, plan.case_id)
    for requirement_id in (
        "executive_objective",
        "security_public_claim_boundary",
        "security_approval",
        "finance_budget_check",
    ):
        kernel.admit_case_evidence(
            CaseEvidence(
                evidence_ref=f"evidence:{requirement_id}",
                case_id=plan.case_id,
                requirement_id=requirement_id,
                submitted_by="test-harness",
                submitted_at="2026-05-27T17:01:00+00:00",
            )
        )
    _record_security_dual_control_approval(kernel, plan.case_id)
    _allow_all_plan_steps(kernel, plan)
    closure_evidence_refs = _latest_gate_evidence_refs(kernel, plan.case_id)
    missing_worker_gateway_witness = tuple(
        evidence_ref
        for evidence_ref in closure_evidence_refs
        if evidence_ref != "evidence:engineering_gateway_witness"
    )

    with pytest.raises(RuntimeCoreInvariantError, match="gate evidence refs"):
        kernel.close_case(
            reconciliation=_match_reconciliation(plan.case_id, missing_worker_gateway_witness),
            terminal_disposition=TerminalClosureDisposition.COMMITTED,
            terminal_certificate_id="terminal.certificate.gateway-pilot",
        )
    closure = kernel.close_case(
        reconciliation=_match_reconciliation(plan.case_id, closure_evidence_refs),
        terminal_disposition=TerminalClosureDisposition.COMMITTED,
        terminal_certificate_id="terminal.certificate.gateway-pilot",
    )

    assert "evidence:engineering_gateway_witness" in closure.evidence_refs
    assert kernel.closure_count == 1


def test_worker_receipt_admitted_as_case_evidence_with_provenance() -> None:
    kernel, plan = _pilot()
    lease_id, dispatch_request_id, dispatch_receipt_id = _record_engineering_dispatch_receipt(
        kernel,
        plan.case_id,
        "engineering_health_endpoint",
    )
    binding = kernel.bind_worker_receipt_evidence(
        PlanStepWorkerReceiptBinding(
            binding_id="binding.eng.health",
            case_id=plan.case_id,
            step_id="engineering_runtime_witness",
            requirement_id="engineering_health_endpoint",
            worker_lease_id=lease_id,
            dispatch_request_id=dispatch_request_id,
            dispatch_receipt_id=dispatch_receipt_id,
            worker_output_hash="hash-health",
            receipt_evidence_refs=("worker-evidence:/health",),
            admitted_evidence_ref="evidence:engineering_health_endpoint",
            bound_at="2026-05-27T17:03:00+00:00",
        )
    )

    state = kernel.snapshot_state()
    assert binding in state.worker_receipt_bindings
    admitted = [e for e in state.case_evidence if e.evidence_ref == "evidence:engineering_health_endpoint"]
    assert len(admitted) == 1
    assert admitted[0].requirement_id == "engineering_health_endpoint"
    assert admitted[0].submitted_by == f"worker_mesh:{lease_id}"
    assert admitted[0].metadata["source"] == "worker_dispatch_receipt"
    assert admitted[0].metadata["dispatch_receipt_id"] == dispatch_receipt_id
    assert admitted[0].metadata["worker_dispatch_receipt_required"] is True
    assert admitted[0].metadata["worker_receipt_is_terminal_closure"] is False
    bound_events = [e for e in kernel.list_case_events(plan.case_id) if e.event_type == "plan_step_worker_receipt_bound"]
    assert len(bound_events) == 1


def test_worker_receipt_requires_recorded_dispatch_receipt() -> None:
    kernel, plan = _pilot()

    with pytest.raises(RuntimeCoreInvariantError, match="dispatch receipt unavailable"):
        kernel.bind_worker_receipt_evidence(
            PlanStepWorkerReceiptBinding(
                binding_id="binding.eng.health",
                case_id=plan.case_id,
                step_id="engineering_runtime_witness",
                requirement_id="engineering_health_endpoint",
                worker_lease_id="lease.eng.gateway.engineering_health_endpoint",
                dispatch_request_id="req.engineering_health_endpoint",
                dispatch_receipt_id="receipt.engineering_health_endpoint",
                worker_output_hash="hash-health",
                receipt_evidence_refs=("worker-evidence:/health",),
                admitted_evidence_ref="evidence:engineering_health_endpoint",
                bound_at="2026-05-27T17:03:00+00:00",
            )
        )


def test_worker_receipt_rejects_dispatch_identity_mismatch() -> None:
    kernel, plan = _pilot()
    lease_id, dispatch_request_id, dispatch_receipt_id = _record_engineering_dispatch_receipt(
        kernel,
        plan.case_id,
        "engineering_health_endpoint",
    )

    with pytest.raises(RuntimeCoreInvariantError, match="dispatch request mismatch"):
        kernel.bind_worker_receipt_evidence(
            PlanStepWorkerReceiptBinding(
                binding_id="binding.eng.health",
                case_id=plan.case_id,
                step_id="engineering_runtime_witness",
                requirement_id="engineering_health_endpoint",
                worker_lease_id=lease_id,
                dispatch_request_id=f"{dispatch_request_id}.tampered",
                dispatch_receipt_id=dispatch_receipt_id,
                worker_output_hash="hash-health",
                receipt_evidence_refs=("worker-evidence:/health",),
                admitted_evidence_ref="evidence:engineering_health_endpoint",
                bound_at="2026-05-27T17:03:00+00:00",
            )
        )


def test_worker_receipt_contract_requires_receipt_evidence_refs() -> None:
    with pytest.raises(ValueError, match="at least one item"):
        PlanStepWorkerReceiptBinding(
            binding_id="binding.empty",
            case_id="case.launch_gateway_pilot",
            step_id="engineering_runtime_witness",
            requirement_id="engineering_health_endpoint",
            worker_lease_id="lease.x",
            dispatch_request_id="req.x",
            dispatch_receipt_id="receipt.x",
            worker_output_hash="hash-x",
            receipt_evidence_refs=(),
            admitted_evidence_ref="evidence:engineering_health_endpoint",
            bound_at="2026-05-27T17:03:00+00:00",
        )


def test_worker_receipt_rejects_requirement_outside_plan_step() -> None:
    kernel, plan = _pilot()
    with pytest.raises(RuntimeCoreInvariantError):
        kernel.bind_worker_receipt_evidence(
            PlanStepWorkerReceiptBinding(
                binding_id="binding.cross",
                case_id=plan.case_id,
                step_id="engineering_runtime_witness",
                requirement_id="finance_budget_check",
                worker_lease_id="lease.x",
                dispatch_request_id="req.x",
                dispatch_receipt_id="receipt.x",
                worker_output_hash="hash-x",
                receipt_evidence_refs=("worker-evidence:budget",),
                admitted_evidence_ref="evidence:finance_budget_check",
                bound_at="2026-05-27T17:03:00+00:00",
            )
        )


def test_worker_receipt_binding_survives_state_round_trip() -> None:
    kernel, plan = _pilot()
    _bind_engineering_worker_receipts(kernel, plan.case_id)
    state = kernel.snapshot_state()

    restored = OrganizationKernel(clock=_clock())
    restored.restore_state(state)

    assert restored.snapshot_state() == state
