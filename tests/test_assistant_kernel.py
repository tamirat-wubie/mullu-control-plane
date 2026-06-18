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
from types import SimpleNamespace

from fastapi import HTTPException

from mcoi_runtime.app.routers.assistant import (
    FinanceOpsAssistantPlanRequest,
    TeamOpsAssistantPlanRequest,
    _operator_queue_item,
    compile_finance_ops_assistant_plan,
    compile_team_ops_assistant_plan,
)
from mcoi_runtime.assistant_kernel import (
    AssistantExecutionPlan,
    AssistantGoal,
    AssistantKernel,
    AssistantMemoryCandidate,
    AssistantProfile,
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
    team_ops_default_profile,
    team_ops_shared_inbox_closure_contract,
    team_ops_shared_inbox_goal,
    verify_effect_receipts,
)
from mcoi_runtime.assistant_kernel.effects import EffectReceipt
from mcoi_runtime.assistant_kernel.goals import (
    FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES,
    TEAM_OPS_SHARED_INBOX_CLOSURE_PREDICATES,
)
from mcoi_runtime.assistant_kernel.identity import FORBIDDEN_PROFILE_METADATA_KEYS, PROTECTED_FORBIDDEN_CAPABILITIES
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


ROOT = Path(__file__).resolve().parent.parent


def _finance_ops_profile_and_goal(
    invoice_ref: str = "invoice:1001",
) -> tuple[AssistantProfile, AssistantGoal]:
    profile = finance_ops_default_profile()
    goal = finance_ops_invoice_payment_goal(
        tenant_id="tenant-finance",
        owner_id="finance-owner",
        profile_id=profile.assistant_id,
        invoice_ref=invoice_ref,
        vendor_ref="vendor:acme",
        created_at="2026-05-13T10:00:00+00:00",
    )
    return profile, goal


def _active_finance_ops_consent_ledger(goal: AssistantGoal) -> ConsentLedger:
    ledger = ConsentLedger()
    ledger.grant(
        ConsentGrant(
            consent_id=consent_grant_id(
                tenant_id=goal.tenant_id,
                owner_id=goal.owner_id,
                capability_id="payment.execute.with_approval",
                scope="invoice_payment",
                granted_at="2026-05-13T10:00:00+00:00",
            ),
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
    return ledger


def _compile_finance_ops_plan(
    consent_ledger: ConsentLedger | None = None,
) -> tuple[AssistantGoal, AssistantExecutionPlan]:
    profile, goal = _finance_ops_profile_and_goal()
    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=finance_ops_payment_closure_contract(goal.goal_id),
        consent_ledger=consent_ledger,
        now="2026-05-13T10:30:00+00:00",
    )
    return goal, plan


def _team_ops_profile_and_goal(
    request_ref: str = "shared-request:1001",
) -> tuple[AssistantProfile, AssistantGoal]:
    profile = team_ops_default_profile()
    goal = team_ops_shared_inbox_goal(
        tenant_id="tenant-team",
        owner_id="ops-owner",
        profile_id=profile.assistant_id,
        inbox_ref="shared-inbox:support",
        request_ref=request_ref,
        created_at="2026-05-13T10:00:00+00:00",
    )
    return profile, goal


def _active_team_ops_consent_ledger(goal: AssistantGoal) -> ConsentLedger:
    ledger = ConsentLedger()
    ledger.grant(
        ConsentGrant(
            consent_id=consent_grant_id(
                tenant_id=goal.tenant_id,
                owner_id=goal.owner_id,
                capability_id="email.send.with_approval",
                scope="shared_inbox_external_send",
                granted_at="2026-05-13T10:00:00+00:00",
            ),
            tenant_id=goal.tenant_id,
            owner_id=goal.owner_id,
            capability_id="email.send.with_approval",
            scope="shared_inbox_external_send",
            granted_by="ops-owner",
            granted_at="2026-05-13T10:00:00+00:00",
            expires_at="2026-05-13T12:00:00+00:00",
            evidence_refs=("approval:ops-owner",),
        )
    )
    return ledger


def _compile_team_ops_plan(
    consent_ledger: ConsentLedger | None = None,
) -> tuple[AssistantGoal, AssistantExecutionPlan]:
    profile, goal = _team_ops_profile_and_goal()
    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=team_ops_shared_inbox_closure_contract(goal.goal_id),
        consent_ledger=consent_ledger,
        now="2026-05-13T10:30:00+00:00",
    )
    return goal, plan


def _unauthenticated_request() -> object:
    return SimpleNamespace(state=SimpleNamespace(governance_context={}))


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
    assert set(PROTECTED_FORBIDDEN_CAPABILITIES).issubset(finance_profile.forbidden_capabilities)
    assert set(finance_profile.skill_ids).isdisjoint(finance_profile.allowed_capabilities)
    assert "signed_evidence_bundle" in finance_profile.evidence_required
    assert finance_profile.metadata["activation_requires_live_receipts"] is True
    assert set(finance_profile.metadata).isdisjoint(FORBIDDEN_PROFILE_METADATA_KEYS)
    assert binding.binding_hash
    assert binding.metadata["skill_capability_boundary_enforced"] is True


def test_assistant_profile_applies_protected_forbidden_capability_floor() -> None:
    profile = AssistantProfile(
        assistant_id="profile.protected-floor",
        kind="personal",
        owner_scope="single_owner",
        tenant_scope="personal_tenant",
        role="floor_test",
        skill_ids=("skill.personal.floor_review",),
        allowed_capabilities=("email.read",),
        forbidden_capabilities=(),
        memory_policy="bounded_memory",
        approval_policy="approval_required",
        budget_policy="bounded_budget",
        external_send_policy="approval_required",
        data_retention_policy="retention_policy",
        evidence_required=("approval_receipt",),
        escalation_path=("owner",),
    )

    assert profile.forbidden_capabilities == tuple(sorted(PROTECTED_FORBIDDEN_CAPABILITIES))
    assert "email.read" in profile.allowed_capabilities
    assert set(PROTECTED_FORBIDDEN_CAPABILITIES).isdisjoint(profile.allowed_capabilities)
    assert set(profile.allowed_capabilities).isdisjoint(profile.forbidden_capabilities)


def test_assistant_profile_rejects_cross_kind_skill_namespace() -> None:
    try:
        AssistantProfile(
            assistant_id="profile.cross-kind-skill",
            kind="team_ops",
            owner_scope="organization_owned",
            tenant_scope="organization_tenant",
            role="team_ops_assistant",
            skill_ids=("skill.finance_ops.invoice_intake",),
            allowed_capabilities=("email.read",),
            forbidden_capabilities=("payment.execute",),
            memory_policy="tenant_scoped_admitted_facts_only",
            approval_policy="role_bound_external_write_approval",
            budget_policy="tenant_budget_gate",
            external_send_policy="approval_required",
            data_retention_policy="tenant_retention_policy",
            evidence_required=("approval_receipt",),
            escalation_path=("team_lead",),
        )
    except RuntimeCoreInvariantError as exc:
        message = str(exc)
    else:  # pragma: no cover - cross-kind skills must fail closed.
        raise AssertionError("cross-kind skill namespace was accepted")

    assert "skill_ids must stay within assistant kind namespace" in message
    assert "capability scope conflict" not in message
    assert "assistant kind is not admitted" not in message


def test_assistant_profile_rejects_metadata_authority_claims() -> None:
    try:
        AssistantProfile(
            assistant_id="profile.metadata-overclaim",
            kind="personal",
            owner_scope="single_owner",
            tenant_scope="personal_tenant",
            role="personal_assistant",
            skill_ids=("skill.personal.inbox_triage",),
            allowed_capabilities=("email.read",),
            forbidden_capabilities=("payment.execute",),
            memory_policy="verified_preferences_only",
            approval_policy="owner_approval_for_external_write",
            budget_policy="personal_budget_awareness_only",
            external_send_policy="approval_required",
            data_retention_policy="owner_controlled_retention",
            evidence_required=("approval_receipt",),
            escalation_path=("owner",),
            metadata={"production_ready": False},
        )
    except RuntimeCoreInvariantError as exc:
        message = str(exc)
    else:  # pragma: no cover - readiness claim keys must fail closed.
        raise AssertionError("metadata readiness claim key was accepted")

    assert "metadata cannot carry authority or readiness claim keys" in message
    assert "activation_requires_live_receipts" not in FORBIDDEN_PROFILE_METADATA_KEYS
    assert "production_ready" in FORBIDDEN_PROFILE_METADATA_KEYS


def test_assistant_profiles_read_model_bounded() -> None:
    profile_models = tuple(profile.to_dict() for profile in builtin_assistant_profiles())
    finance_profile = next(
        profile for profile in profile_models if profile["assistant_id"] == "finance_ops.default"
    )
    exposed_fields = {field for profile in profile_models for field in profile}

    assert len(profile_models) == 6
    assert "payment.execute.with_approval" in finance_profile["allowed_capabilities"]
    assert "payment.execute" in finance_profile["forbidden_capabilities"]
    assert "signed_evidence_bundle" in finance_profile["evidence_required"]
    assert "execution_authority_granted" not in exposed_fields
    assert all(profile["owner_scope"] for profile in profile_models)


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


def test_finance_ops_plan_requires_active_consent() -> None:
    _, plan = _compile_finance_ops_plan()

    assert plan.blocked is True
    assert plan.steps == ()
    assert "active_consent_required:payment.execute.with_approval" in plan.blocked_reasons
    assert "terminal_closure" in plan.required_controls
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.plan_hash


def test_finance_ops_plan_projects_operator_queue() -> None:
    profile, goal = _finance_ops_profile_and_goal()
    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=finance_ops_payment_closure_contract(goal.goal_id),
        consent_ledger=_active_finance_ops_consent_ledger(goal),
        now="2026-05-13T10:30:00+00:00",
    )
    queue_item = _operator_queue_item(
        plan=plan,
        tenant_id=goal.tenant_id,
        owner_id=goal.owner_id,
    )

    assert plan.blocked is False
    assert queue_item["state"] == "ready_for_governed_dispatch"
    assert queue_item["plan_id"] == plan.plan_id
    assert queue_item["step_count"] == len(plan.steps)
    assert queue_item["required_controls"] == list(plan.required_controls)
    assert queue_item["execution_authority_granted"] is False


def test_assistant_kernel_compiles_team_ops_plan_with_consent_and_controls() -> None:
    profile, goal = _team_ops_profile_and_goal()

    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=team_ops_shared_inbox_closure_contract(goal.goal_id),
        consent_ledger=_active_team_ops_consent_ledger(goal),
        now="2026-05-13T10:30:00+00:00",
    )
    send_step = next(step for step in plan.steps if step.capability_id == "email.send.with_approval")

    assert plan.blocked is False
    assert len(plan.steps) == len(goal.required_capabilities)
    assert tuple(step.capability_id for step in plan.steps) == goal.required_capabilities
    assert send_step.requires_approval is True
    assert send_step.closure_predicates == ("external_send_approval_valid", "message_send_receipt_exists")
    assert "active_consent" in plan.required_controls
    assert "temporal_idempotency" in plan.required_controls
    assert "effect_reconciliation" in plan.required_controls
    assert "fresh_approval" in plan.required_controls
    assert goal.metadata["classification_skill_id"] == "skill.team_ops.shared_inbox_triage"
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.plan_hash


def test_team_ops_plan_requires_active_external_send_consent() -> None:
    _, plan = _compile_team_ops_plan()

    assert plan.blocked is True
    assert plan.steps == ()
    assert "active_consent_required:email.send.with_approval" in plan.blocked_reasons
    assert "terminal_closure" in plan.required_controls
    assert "active_consent" in plan.required_controls
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.plan_hash


def test_team_ops_plan_projects_operator_queue() -> None:
    profile, goal = _team_ops_profile_and_goal()
    plan = AssistantKernel().compile_plan(
        profile=profile,
        goal=goal,
        closure_contract=team_ops_shared_inbox_closure_contract(goal.goal_id),
        consent_ledger=_active_team_ops_consent_ledger(goal),
        now="2026-05-13T10:30:00+00:00",
    )
    queue_item = _operator_queue_item(
        plan=plan,
        tenant_id=goal.tenant_id,
        owner_id=goal.owner_id,
    )

    assert plan.blocked is False
    assert queue_item["state"] == "ready_for_governed_dispatch"
    assert queue_item["plan_id"] == plan.plan_id
    assert queue_item["step_count"] == len(plan.steps)
    assert queue_item["required_controls"] == list(plan.required_controls)
    assert queue_item["execution_authority_granted"] is False


def test_assistant_plan_never_grants_execution_authority() -> None:
    blocked_goal, blocked_plan = _compile_finance_ops_plan()
    ready_profile, ready_goal = _finance_ops_profile_and_goal()
    ready_plan = AssistantKernel().compile_plan(
        profile=ready_profile,
        goal=ready_goal,
        closure_contract=finance_ops_payment_closure_contract(ready_goal.goal_id),
        consent_ledger=_active_finance_ops_consent_ledger(ready_goal),
        now="2026-05-13T10:30:00+00:00",
    )
    blocked_queue_item = _operator_queue_item(
        plan=blocked_plan,
        tenant_id=blocked_goal.tenant_id,
        owner_id=blocked_goal.owner_id,
    )
    ready_queue_item = _operator_queue_item(
        plan=ready_plan,
        tenant_id=ready_goal.tenant_id,
        owner_id=ready_goal.owner_id,
    )

    assert blocked_queue_item["execution_authority_granted"] is False
    assert ready_queue_item["execution_authority_granted"] is False
    assert blocked_queue_item["state"] == "blocked"
    assert ready_queue_item["state"] == "ready_for_governed_dispatch"
    assert blocked_plan.metadata["plan_is_not_execution"] is True
    assert ready_plan.metadata["plan_is_not_execution"] is True


def test_assistant_plan_errors_sanitized() -> None:
    try:
        compile_finance_ops_assistant_plan(
            FinanceOpsAssistantPlanRequest(
                tenant_id="tenant-finance",
                owner_id="finance-owner",
                invoice_ref="",
                vendor_ref="vendor:acme",
                created_at="2026-05-13T10:00:00+00:00",
            )
        )
    except HTTPException as exc:
        detail = exc.detail
    else:  # pragma: no cover - the invariant above must fail closed.
        raise AssertionError("invalid assistant plan was accepted")

    assert detail == {
        "error": "invalid assistant plan",
        "error_code": "invalid_assistant_plan",
        "governed": True,
    }
    assert "invoice:1001" not in str(detail)
    assert "vendor:acme" not in str(detail)


def test_team_ops_plan_errors_sanitized() -> None:
    try:
        compile_team_ops_assistant_plan(
            TeamOpsAssistantPlanRequest(
                tenant_id="tenant-team",
                owner_id="ops-owner",
                inbox_ref="",
                request_ref="shared-request:1001",
                created_at="2026-05-13T10:00:00+00:00",
            ),
            _unauthenticated_request(),
        )
    except HTTPException as exc:
        detail = exc.detail
    else:  # pragma: no cover - the invariant above must fail closed.
        raise AssertionError("invalid TeamOps assistant plan was accepted")

    assert detail == {
        "error": "invalid assistant plan",
        "error_code": "invalid_assistant_plan",
        "governed": True,
    }
    assert "shared-request:1001" not in str(detail)
    assert "tenant-team" not in str(detail)


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


def test_team_ops_closure_requires_two_confirmed_predicates() -> None:
    contract = team_ops_shared_inbox_closure_contract("goal-teamops-1")
    first_pass = tuple(
        closure_observation(
            predicate_id=predicate,
            status="passed",
            observed_at="2026-05-13T10:00:00+00:00",
            evidence_refs=(f"evidence:{predicate}:1",),
        )
        for predicate in TEAM_OPS_SHARED_INBOX_CLOSURE_PREDICATES
    )
    unstable = evaluate_closure(contract, first_pass)
    second_pass = tuple(
        closure_observation(
            predicate_id=predicate,
            status="passed",
            observed_at="2026-05-13T10:05:00+00:00",
            evidence_refs=(f"evidence:{predicate}:2",),
        )
        for predicate in TEAM_OPS_SHARED_INBOX_CLOSURE_PREDICATES
    )
    closed = evaluate_closure(contract, (*first_pass, *second_pass))

    assert unstable.closed is False
    assert unstable.reason == "closure_confirmation_unstable"
    assert set(unstable.unstable_predicates) == set(TEAM_OPS_SHARED_INBOX_CLOSURE_PREDICATES)
    assert closed.closed is True
    assert closed.reason == "closure_verified"
    assert closed.confirmation_counts["message_send_receipt_exists"] == 2
    assert len(closed.evidence_refs) == len(TEAM_OPS_SHARED_INBOX_CLOSURE_PREDICATES) * 2


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
