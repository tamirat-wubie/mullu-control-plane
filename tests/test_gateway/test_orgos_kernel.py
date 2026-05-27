"""Mullu OrgOS kernel tests.

Purpose: verify the organization kernel models departments as governed work
    surfaces with cases, authority, evidence, effect closure, and learning
    admission.
Governance scope: OrgGraph, AuthorityGraph, WorkGraph, CapabilityGraph,
    EvidenceGraph, LearningGraph, and the v0 case loop.
Dependencies: gateway.orgos_kernel and MCOI terminal closure contracts.
Invariants:
  - Departments are mandate surfaces, not personality simulations.
  - Plan steps fail closed without authority, capability, evidence, and world refs.
  - Committed closure requires matched effects and forbidden-effect checks.
  - Learning reuse requires a closed case and an admission decision.
"""

from __future__ import annotations

import pytest

from gateway.enterprise_authority import AuthorityDecision
from gateway.orgos_kernel import (
    AuthorityRule,
    EffectClosureBinding,
    JsonlOrgCaseEventLog,
    OrgCase,
    OrgCaseEventReceiptConfig,
    Organization,
    OrganizationKernel,
    OrgPlanStep,
    Role,
    default_mullu_orgos_departments,
)
from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)


NOW = "2026-05-05T12:00:00+00:00"


def test_orgos_kernel_bootstraps_five_departments_and_launch_gateway_case() -> None:
    kernel = _kernel()
    work_case = kernel.open_case(_case())
    read_model = kernel.read_model()
    departments = {item["department_id"]: item for item in read_model["org_graph"]["departments"]}

    assert set(departments) == {"executive", "product", "engineering", "security_compliance", "finance"}
    assert work_case.status == "open"
    assert work_case.case_hash
    assert departments["engineering"]["metadata"]["department_pack"] is True
    assert read_model["case_loop"]["case_count"] == 1
    assert read_model["case_loop"]["open_case_count"] == 1


def test_orgos_kernel_rejects_ownerless_authority_and_tenant_mismatch() -> None:
    kernel = OrganizationKernel(departments=default_mullu_orgos_departments())

    with pytest.raises(ValueError, match="organization_owner_role_unknown"):
        kernel.register_organization(
            Organization(
                org_id="org-mullusi",
                tenant_id="tenant-a",
                name="Mullusi",
                owner_role_id="executive_owner",
                evidence_refs=("org:evidence:charter",),
            )
        )

    kernel.register_role(
        Role(
            role_id="engineering_owner",
            department_id="engineering",
            permissions=("gateway.health.check",),
            approval_limit_risk="high",
            evidence_refs=("role:evidence:engineering",),
        )
    )
    with pytest.raises(ValueError, match="authority_rule_action_outside_role_permissions"):
        kernel.register_authority_rule(
            AuthorityRule(
                rule_id="rule-invalid",
                role_id="engineering_owner",
                action="payment.prepare",
                resource_type="gateway_runtime",
                max_risk="high",
                requires_dual_control=False,
                separation_of_duty=(),
                evidence_refs=("authority:evidence:invalid",),
            )
        )

    kernel.register_role(
        Role(
            role_id="executive_owner",
            department_id="executive",
            permissions=("objective.freeze",),
            approval_limit_risk="critical",
            evidence_refs=("role:evidence:executive",),
        )
    )
    kernel.register_organization(
        Organization(
            org_id="org-mullusi",
            tenant_id="tenant-a",
            name="Mullusi",
            owner_role_id="executive_owner",
            evidence_refs=("org:evidence:charter",),
        )
    )
    with pytest.raises(ValueError, match="case_tenant_mismatch"):
        kernel.open_case(
            OrgCase(
                case_id="case-wrong-tenant",
                org_id="org-mullusi",
                tenant_id="tenant-b",
                department_id="engineering",
                case_type="launch_gateway_pilot",
                goal="Launch Gateway Pilot",
                risk_tier="high",
                owner_role_id="engineering_owner",
                status="open",
                evidence_refs=("case:intake:wrong-tenant",),
            )
        )


def test_plan_step_gate_denies_missing_authority_capability_evidence_and_world_refs() -> None:
    kernel = _kernel_with_plan()

    decision = kernel.evaluate_plan_step(
        "step-gateway-health",
        authority_decision=None,
        policy_allowed=True,
        world_refs=(),
        certified_capabilities=(),
        evidence_refs=(),
        approval_refs=(),
    )

    assert decision.verdict == "deny"
    assert "authority_decision_missing" in decision.reasons
    assert "capability_not_certified" in decision.reasons
    assert "world_preconditions_missing" in decision.reasons
    assert "evidence_missing" in decision.reasons
    assert "approval_missing_for_high_risk" in decision.reasons
    assert "authority_decision" in decision.required_controls


def test_plan_step_gate_denies_cross_tenant_or_unbound_authority() -> None:
    kernel = _kernel_with_plan()

    decision = kernel.evaluate_plan_step(
        "step-gateway-health",
        authority_decision=_authority_decision_with(
            decision_id="authority-decision-tenant-b",
            tenant_id="tenant-b",
            matched_grant_ids=("grant-external",),
        ),
        policy_allowed=True,
        world_refs=("world:runtime-target-bound",),
        certified_capabilities=("gateway.health.check",),
        evidence_refs=("runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"),
        approval_refs=("approval:engineering_owner",),
    )

    assert decision.verdict == "deny"
    assert "authority_tenant_mismatch" in decision.reasons
    assert "authority_rule_not_bound_to_step" in decision.reasons
    assert "authority_rule_binding" in decision.required_controls


def test_plan_step_gate_allows_certified_authorized_gateway_step() -> None:
    kernel = _kernel_with_plan()

    decision = _allow_gateway_step(kernel)
    read_model = kernel.read_model()

    assert decision.verdict == "allow"
    assert decision.reasons == ("admissible_for_bounded_execution",)
    assert decision.metadata["authority_decision_id"] == "authority-decision-gateway-1"
    assert read_model["case_loop"]["executing_case_count"] == 1
    assert read_model["authority_graph"]["gate_decisions"][0]["decision_hash"]
    assert "world:runtime-target-bound" in read_model["world_graph"]["world_refs_observed_by_cases"]


def test_case_closure_requires_effect_reconciliation_match_for_committed() -> None:
    kernel = _kernel_with_executing_case()

    denied = kernel.close_case(
        EffectClosureBinding(
            case_id="case-launch-gateway",
            expected_effects=("gateway_published",),
            observed_effects=("runtime_pending",),
            forbidden_effects_checked=True,
            evidence_refs=("evidence:gateway-witness", "evidence:runtime-conformance"),
            effect_reconciliation_ref="recon-gateway-1",
            terminal_disposition="committed",
        ),
        terminal_certificate=_terminal_certificate(),
    )
    allowed = kernel.close_case(
        EffectClosureBinding(
            case_id="case-launch-gateway",
            expected_effects=("gateway_published",),
            observed_effects=("gateway_published",),
            forbidden_effects_checked=True,
            evidence_refs=("evidence:gateway-witness", "evidence:runtime-conformance"),
            effect_reconciliation_ref="recon-gateway-1",
            terminal_disposition="committed",
        ),
        terminal_certificate=_terminal_certificate(),
    )
    read_model = kernel.read_model()

    assert denied.verdict == "deny"
    assert "effect_reconciliation_not_match" in denied.reasons
    assert denied.resulting_status == "awaiting_evidence"
    assert allowed.verdict == "allow"
    assert allowed.resulting_status == "closed"
    assert read_model["case_loop"]["closed_case_count"] == 1


def test_learning_binding_requires_closed_case_and_admission_decision() -> None:
    kernel = _kernel_with_plan()

    with pytest.raises(ValueError, match="learning_requires_closed_case"):
        kernel.bind_learning_admission("case-launch-gateway", _learning_decision(LearningAdmissionStatus.ADMIT))

    premature = kernel.close_case(
        EffectClosureBinding(
            case_id="case-launch-gateway",
            expected_effects=("gateway_published",),
            observed_effects=("gateway_published",),
            forbidden_effects_checked=True,
            evidence_refs=("evidence:gateway-witness", "evidence:runtime-conformance"),
            effect_reconciliation_ref="recon-gateway-1",
            terminal_disposition="committed",
        ),
        terminal_certificate=_terminal_certificate(),
    )
    _allow_gateway_step(kernel)
    kernel.close_case(
        EffectClosureBinding(
            case_id="case-launch-gateway",
            expected_effects=("gateway_published",),
            observed_effects=("gateway_published",),
            forbidden_effects_checked=True,
            evidence_refs=("evidence:gateway-witness", "evidence:runtime-conformance"),
            effect_reconciliation_ref="recon-gateway-1",
            terminal_disposition="committed",
        ),
        terminal_certificate=_terminal_certificate(),
    )
    binding = kernel.bind_learning_admission(
        "case-launch-gateway",
        _learning_decision(LearningAdmissionStatus.ADMIT),
    )
    read_model = kernel.read_model()

    assert premature.verdict == "deny"
    assert "case_not_ready_for_closure" in premature.reasons
    assert "authority_decision_not_bound_to_case" in premature.reasons
    assert binding.reusable is True
    assert binding.knowledge_id == "knowledge-launch-gateway-pilot"
    assert binding.binding_hash
    assert read_model["learning_graph"]["reusable_knowledge_ids"] == ["knowledge-launch-gateway-pilot"]
    assert read_model["case_loop"]["closed_case_count"] == 1


def test_jsonl_case_event_log_preserves_hash_chain(tmp_path) -> None:
    path = tmp_path / "orgos-events.jsonl"
    log = JsonlOrgCaseEventLog(path, clock=lambda: NOW, receipt_config=_receipt_config("secret-a"))

    first = log.record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="case_opened",
        actor_id="engineering_owner",
        payload={"status": "open"},
        evidence_refs=("case:intake:launch-gateway",),
    )
    second = log.record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="plan_step_added",
        actor_id="engineering_owner",
        payload={"step_id": "step-gateway-health"},
        evidence_refs=("runtime_health_ref",),
    )
    page = JsonlOrgCaseEventLog(path, clock=lambda: NOW, receipt_config=_receipt_config("secret-a")).list(
        case_id="case-launch-gateway"
    )

    assert path.exists()
    assert not path.with_name("orgos-events.jsonl.lock").exists()
    assert page.total == 2
    assert page.events[0].event_id == second.event_id
    assert page.events[1].event_id == first.event_id
    assert second.prev_event_hash == first.event_hash
    assert first.prev_event_hash == "genesis"
    assert first.event_hash != second.event_hash
    assert second.receipt.signature.startswith("hmac-sha256:")
    assert second.receipt.external_anchor_status == "not_requested"
    assert second.receipt.payload_hash
    assert second.receipt.receipt_hash


def test_jsonl_case_event_log_rejects_wrong_receipt_secret(tmp_path) -> None:
    path = tmp_path / "orgos-events.jsonl"
    JsonlOrgCaseEventLog(path, clock=lambda: NOW, receipt_config=_receipt_config("secret-a")).record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="case_opened",
        actor_id="engineering_owner",
        payload={"status": "open"},
        evidence_refs=("case:intake:launch-gateway",),
    )

    with pytest.raises(ValueError, match="receipt signature"):
        JsonlOrgCaseEventLog(path, clock=lambda: NOW, receipt_config=_receipt_config("secret-b")).list()


def _kernel() -> OrganizationKernel:
    kernel = OrganizationKernel(departments=default_mullu_orgos_departments())
    for role in (
        Role(
            role_id="executive_owner",
            department_id="executive",
            permissions=("objective.freeze", "approval.grant"),
            approval_limit_risk="critical",
            evidence_refs=("role:evidence:executive",),
        ),
        Role(
            role_id="engineering_owner",
            department_id="engineering",
            permissions=("gateway.health.check", "runtime.conformance.collect"),
            approval_limit_risk="high",
            evidence_refs=("role:evidence:engineering",),
        ),
    ):
        kernel.register_role(role)
    kernel.register_organization(
        Organization(
            org_id="org-mullusi",
            tenant_id="tenant-a",
            name="Mullusi",
            owner_role_id="executive_owner",
            evidence_refs=("org:evidence:charter",),
        )
    )
    kernel.register_authority_rule(
        AuthorityRule(
            rule_id="rule-engineering-gateway",
            role_id="engineering_owner",
            action="gateway.health.check",
            resource_type="gateway_runtime",
            max_risk="high",
            requires_dual_control=True,
            separation_of_duty=("executive_owner",),
            evidence_refs=("authority:evidence:engineering-rule",),
        )
    )
    return kernel


def _kernel_with_plan() -> OrganizationKernel:
    kernel = _kernel()
    kernel.open_case(_case())
    kernel.add_plan_step(_step())
    return kernel


def _kernel_with_executing_case() -> OrganizationKernel:
    kernel = _kernel_with_plan()
    _allow_gateway_step(kernel)
    return kernel


def _case() -> OrgCase:
    return OrgCase(
        case_id="case-launch-gateway",
        org_id="org-mullusi",
        tenant_id="tenant-a",
        department_id="engineering",
        case_type="launch_gateway_pilot",
        goal="Launch Gateway Pilot",
        risk_tier="high",
        owner_role_id="engineering_owner",
        status="open",
        evidence_refs=("case:intake:launch-gateway",),
    )


def _step() -> OrgPlanStep:
    return OrgPlanStep(
        step_id="step-gateway-health",
        case_id="case-launch-gateway",
        department_id="engineering",
        capability_id="gateway.health.check",
        risk_tier="high",
        preconditions=("world:runtime-target-bound",),
        postconditions=("gateway_published",),
        evidence_required=("runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"),
        approvals_required=("approval:engineering_owner",),
        expected_effects=("gateway_published",),
        forbidden_effects=("secret_exposed", "unverified_public_claim"),
        rollback_plan_id="rollback:gateway-pilot",
    )


def _allow_gateway_step(kernel: OrganizationKernel):
    return kernel.evaluate_plan_step(
        "step-gateway-health",
        authority_decision=_authority_decision(),
        policy_allowed=True,
        world_refs=("world:runtime-target-bound",),
        certified_capabilities=("gateway.health.check",),
        evidence_refs=("runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"),
        approval_refs=("approval:engineering_owner",),
    )


def _authority_decision() -> AuthorityDecision:
    return _authority_decision_with()


def _authority_decision_with(
    *,
    decision_id: str = "authority-decision-gateway-1",
    tenant_id: str = "tenant-a",
    matched_grant_ids: tuple[str, ...] = ("rule-engineering-gateway",),
) -> AuthorityDecision:
    return AuthorityDecision(
        decision_id=decision_id,
        request_id="authority-request-gateway-1",
        actor_id="engineering_owner",
        tenant_id=tenant_id,
        verdict="allow",
        reason="authority_grant_satisfied",
        required_controls=("terminal_closure",),
        matched_grant_ids=matched_grant_ids,
        evidence_refs=("authority:evidence:engineering-rule",),
    )


def _terminal_certificate() -> TerminalClosureCertificate:
    return TerminalClosureCertificate(
        certificate_id="terminal-gateway-1",
        command_id="command-gateway-1",
        execution_id="execution-gateway-1",
        disposition=TerminalClosureDisposition.COMMITTED,
        verification_result_id="verification-gateway-1",
        effect_reconciliation_id="recon-gateway-1",
        evidence_refs=("evidence:gateway-witness", "evidence:runtime-conformance"),
        closed_at=NOW,
    )


def _learning_decision(status: LearningAdmissionStatus) -> LearningAdmissionDecision:
    return LearningAdmissionDecision(
        admission_id=f"learning-admission-{status.value}",
        knowledge_id="knowledge-launch-gateway-pilot",
        status=status,
        reasons=(DecisionReason(message="closure-derived knowledge admitted", code="orgos.learning"),),
        issued_at=NOW,
    )


def _receipt_config(secret: str) -> OrgCaseEventReceiptConfig:
    return OrgCaseEventReceiptConfig(
        signing_secret=secret,
        signature_key_id="orgos-event-test",
        lock_timeout_seconds=1.0,
        stale_lock_seconds=1.0,
    )
