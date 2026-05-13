"""Assistant kernel contract tests.

Purpose: verify assistant profiles, consent, planning, effects, memory, and
closure contracts for the first governed assistant operating layer.
Governance scope: skill/capability separation, external-effect consent,
approval controls, two-confirmation closure, and profile registry artifacts.
Dependencies: mcoi_runtime.assistant_kernel.
Invariants:
  - FinanceOps is the first flagship assistant pack.
  - Planning is not execution.
  - Closure requires signed evidence and two confirmations.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mcoi_runtime.assistant_kernel import (
    AssistantKernel,
    AssistantMemoryCandidate,
    AssistantScheduleRequest,
    ConsentGrant,
    ConsentLedger,
    admit_memory_candidate,
    bind_assistant_identity,
    builtin_assistant_profiles,
    closure_observation,
    consent_grant_id,
    evaluate_closure,
    expectation_for_predicate,
    finance_ops_default_profile,
    finance_ops_invoice_payment_goal,
    finance_ops_payment_closure_contract,
    make_inbox_item,
    schedule_assistant_action,
    verify_effect_receipts,
)
from mcoi_runtime.assistant_kernel.effects import EffectReceipt
from mcoi_runtime.assistant_kernel.goals import FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES


ROOT = Path(__file__).resolve().parent.parent


def test_builtin_finance_ops_profile_preserves_skill_capability_boundary() -> None:
    profiles = builtin_assistant_profiles()
    finance_profile = finance_ops_default_profile()
    binding = bind_assistant_identity(
        finance_profile,
        owner_id="finance-owner",
        tenant_id="tenant-finance",
        created_at="2026-05-13T10:00:00+00:00",
    )

    assert len(profiles) == 6
    assert finance_profile.assistant_id == "finance_ops.default"
    assert "payment.execute.with_approval" in finance_profile.allowed_capabilities
    assert "payment.execute" in finance_profile.forbidden_capabilities
    assert "policy.modify" in finance_profile.forbidden_capabilities
    assert set(finance_profile.skill_ids).isdisjoint(finance_profile.allowed_capabilities)
    assert "signed_evidence_bundle" in finance_profile.evidence_required
    assert binding.binding_hash
    assert binding.metadata["skill_capability_boundary_enforced"] is True


def test_assistant_kernel_compiles_finance_ops_plan_with_consent_and_controls() -> None:
    profile = finance_ops_default_profile()
    goal = finance_ops_invoice_payment_goal(
        tenant_id="tenant-finance",
        owner_id="finance-owner",
        profile_id=profile.assistant_id,
        invoice_ref="invoice:1001",
        vendor_ref="vendor:acme",
        created_at="2026-05-13T10:00:00+00:00",
    )
    ledger = ConsentLedger()
    consent_id = consent_grant_id(
        tenant_id=goal.tenant_id,
        owner_id=goal.owner_id,
        capability_id="payment.execute.with_approval",
        scope="invoice_payment",
        granted_at="2026-05-13T10:00:00+00:00",
    )
    ledger.grant(
        ConsentGrant(
            consent_id=consent_id,
            tenant_id=goal.tenant_id,
            owner_id=goal.owner_id,
            capability_id="payment.execute.with_approval",
            scope="invoice_payment",
            granted_by="finance-owner",
            granted_at="2026-05-13T10:00:00+00:00",
            expires_at="2026-05-13T12:00:00+00:00",
            evidence_refs=("approval:finance-owner",),
        )
    )

    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=finance_ops_payment_closure_contract(goal.goal_id),
        consent_ledger=ledger,
        now="2026-05-13T10:30:00+00:00",
    )

    assert plan.blocked is False
    assert len(plan.steps) == len(goal.required_capabilities)
    assert plan.steps[-1].capability_id == "evidence.export"
    assert any(step.capability_id == "payment.execute.with_approval" and step.requires_approval for step in plan.steps)
    assert "active_consent" in plan.required_controls
    assert "temporal_idempotency" in plan.required_controls
    assert "effect_reconciliation" in plan.required_controls
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.plan_hash


def test_assistant_kernel_blocks_missing_capability_before_execution() -> None:
    profile = finance_ops_default_profile()
    narrowed_profile = replace(
        profile,
        allowed_capabilities=tuple(
            capability for capability in profile.allowed_capabilities if capability != "vendor.verify"
        ),
    )
    goal = finance_ops_invoice_payment_goal(
        tenant_id="tenant-finance",
        owner_id="finance-owner",
        profile_id=narrowed_profile.assistant_id,
        invoice_ref="invoice:1002",
        vendor_ref="vendor:acme",
        created_at="2026-05-13T10:00:00+00:00",
    )

    plan = AssistantKernel().compile_plan(
        profile=narrowed_profile,
        goal=goal,
        closure_contract=finance_ops_payment_closure_contract(goal.goal_id),
    )

    assert plan.blocked is True
    assert "missing_capability:vendor.verify" in plan.blocked_reasons
    assert "active_consent_required:payment.execute.with_approval" in plan.blocked_reasons
    assert plan.steps == ()
    assert "terminal_closure" in plan.required_controls
    assert plan.plan_hash


def test_finance_ops_closure_requires_two_confirmed_predicates() -> None:
    contract = finance_ops_payment_closure_contract("goal-finance-1")
    first_pass = tuple(
        closure_observation(
            predicate_id=predicate,
            status="passed",
            observed_at="2026-05-13T10:00:00+00:00",
            evidence_refs=(f"evidence:{predicate}:1",),
        )
        for predicate in FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES
    )
    unstable = evaluate_closure(contract, first_pass)
    second_pass = tuple(
        closure_observation(
            predicate_id=predicate,
            status="passed",
            observed_at="2026-05-13T10:05:00+00:00",
            evidence_refs=(f"evidence:{predicate}:2",),
        )
        for predicate in FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES
    )
    closed = evaluate_closure(contract, (*first_pass, *second_pass))

    assert unstable.closed is False
    assert unstable.reason == "closure_confirmation_unstable"
    assert set(unstable.unstable_predicates) == set(FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES)
    assert closed.closed is True
    assert closed.reason == "closure_verified"
    assert closed.confirmation_counts["signed_evidence_bundle_exists"] == 2
    assert len(closed.evidence_refs) == len(FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES) * 2


def test_assistant_support_contracts_keep_observations_and_effects_explicit() -> None:
    inbox_item = make_inbox_item(
        tenant_id="tenant-finance",
        owner_id="finance-owner",
        channel="email",
        source_ref="gmail:message-1",
        received_at="2026-05-13T09:00:00+00:00",
        summary="Invoice approval request",
        evidence_refs=("email:gmail-message-1",),
    )
    admission = admit_memory_candidate(
        AssistantMemoryCandidate(
            tenant_id="tenant-finance",
            owner_id="finance-owner",
            memory_class="finance_case_memory",
            fact="Vendor ACME invoice 1001 was reviewed by finance owner.",
            source="closure:finance-goal-1",
            verification_status="verified",
            evidence_refs=("closure:finance-goal-1",),
        )
    )
    scheduled = schedule_assistant_action(
        AssistantScheduleRequest(
            tenant_id="tenant-finance",
            owner_id="finance-owner",
            capability_id="payment.reconcile",
            run_at="2026-05-13T11:00:00+00:00",
            requested_at="2026-05-13T10:00:00+00:00",
            approval_required=False,
        )
    )
    expectation = expectation_for_predicate(
        capability_id="payment.reconcile",
        predicate_id="ledger_reconciliation_exists",
    )
    verification = verify_effect_receipts(
        (expectation,),
        (
            EffectReceipt(
                receipt_id="receipt-reconcile-1",
                capability_id="payment.reconcile",
                predicate_id="ledger_reconciliation_exists",
                status="passed",
                observed_at="2026-05-13T11:05:00+00:00",
                evidence_refs=("ledger:reconciliation-1",),
            ),
        ),
    )

    assert inbox_item.item_id.startswith("assistant-inbox-")
    assert inbox_item.channel == "email"
    assert admission.accepted is True
    assert admission.memory_id.startswith("assistant-memory-")
    assert scheduled.state == "scheduled"
    assert scheduled.idempotency_key.startswith("assistant-idempotency-")
    assert verification.passed is True
    assert verification.evidence_refs == ("ledger:reconciliation-1",)


def test_assistant_profile_registry_files_expose_required_policy_keys() -> None:
    profile_dir = ROOT / "assistant_profiles"
    required_keys = (
        "assistant_id:",
        "owner_scope:",
        "tenant_scope:",
        "allowed_capabilities:",
        "forbidden_capabilities:",
        "memory_policy:",
        "approval_policy:",
        "budget_policy:",
        "external_send_policy:",
        "data_retention_policy:",
        "evidence_required:",
        "escalation_path:",
    )
    profile_files = sorted(profile_dir.glob("*.default.yaml"))
    finance_text = (profile_dir / "finance_ops.default.yaml").read_text(encoding="utf-8")

    assert len(profile_files) == 6
    assert all(all(key in path.read_text(encoding="utf-8") for key in required_keys) for path in profile_files)
    assert "payment.execute.with_approval" in finance_text
    assert "signed_evidence_bundle" in finance_text
    assert "dual_approval_required" in finance_text
