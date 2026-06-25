"""Purpose: assistant kernel plan compiler.
Governance scope: identity/profile binding, capability selection, consent,
    approval controls, temporal idempotency, effect reconciliation, and closure.
Dependencies: assistant kernel contracts and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Plan compilation does not execute effects.
  - Missing capability, forbidden capability, or missing consent blocks the plan.
  - External-effect plans declare approval, idempotency, reconciliation, and
    signed evidence controls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from mcoi_runtime.assistant_kernel.capability_selection import CapabilitySelection, select_capabilities
from mcoi_runtime.assistant_kernel.closure import ClosureContract
from mcoi_runtime.assistant_kernel.consent import ConsentLedger
from mcoi_runtime.assistant_kernel.goals import AssistantGoal
from mcoi_runtime.assistant_kernel.identity import AssistantProfile
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


EXTERNAL_EFFECT_CAPABILITIES = frozenset(
    {
        "calendar.invite",
        "calendar.reschedule",
        "calendar.schedule",
        "email.send.with_approval",
        "messaging.chat.send.with_approval",
        "messaging.sms.send.with_approval",
        "payment.execute.with_approval",
        "phone.call.place.with_approval",
    }
)
_CAPABILITY_CLOSURE_BINDINGS = {
    "messaging.thread.read": ("thread_context_bound",),
    "email.read": ("shared_request_intake_recorded",),
    "email.draft": ("draft_response_prepared",),
    "task.assign": ("owner_assignment_recorded",),
    "email.send.with_approval": ("external_send_approval_valid", "message_send_receipt_exists"),
    "invoice.extract": ("invoice_identity_verified",),
    "vendor.verify": ("vendor_identity_verified",),
    "po.match": ("duplicate_payment_check_passed",),
    "budget.check": ("budget_available",),
    "approval.request": ("approval_valid",),
    "payment.execute.with_approval": ("payment_receipt_exists",),
    "payment.reconcile": ("ledger_reconciliation_exists",),
    "evidence.export": ("signed_evidence_bundle_exists",),
}


@dataclass(frozen=True, slots=True)
class AssistantPlanStep:
    """One non-executing assistant plan step."""

    step_id: str
    order: int
    capability_id: str
    requires_approval: bool
    closure_predicates: tuple[str, ...]
    evidence_required: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", ensure_non_empty_text("step_id", self.step_id))
        if not isinstance(self.order, int) or isinstance(self.order, bool) or self.order <= 0:
            raise RuntimeCoreInvariantError("order must be a positive integer")
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not isinstance(self.requires_approval, bool):
            raise RuntimeCoreInvariantError("requires_approval must be boolean")
        object.__setattr__(self, "closure_predicates", tuple(self.closure_predicates))
        object.__setattr__(self, "evidence_required", tuple(self.evidence_required))


@dataclass(frozen=True, slots=True)
class AssistantExecutionPlan:
    """Compiled assistant plan awaiting execution by governed runtime surfaces."""

    plan_id: str
    goal_id: str
    profile_id: str
    blocked: bool
    blocked_reasons: tuple[str, ...]
    steps: tuple[AssistantPlanStep, ...]
    required_controls: tuple[str, ...]
    closure_contract: ClosureContract
    plan_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", ensure_non_empty_text("plan_id", self.plan_id))
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "profile_id", ensure_non_empty_text("profile_id", self.profile_id))
        if not isinstance(self.blocked, bool):
            raise RuntimeCoreInvariantError("blocked must be boolean")
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "required_controls", tuple(self.required_controls))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented plan projection."""
        return _json_ready(asdict(self))


class AssistantKernel:
    """Contract-first assistant kernel for profile-bound plan compilation."""

    def compile_plan(
        self,
        *,
        profile: AssistantProfile,
        goal: AssistantGoal,
        closure_contract: ClosureContract,
        consent_ledger: ConsentLedger | None = None,
        now: str = "",
    ) -> AssistantExecutionPlan:
        """Compile a goal into a governed execution plan."""
        if goal.profile_id != profile.assistant_id:
            raise RuntimeCoreInvariantError("goal profile_id does not match assistant profile")
        selection = select_capabilities(profile, goal.required_capabilities)
        external_capabilities = tuple(
            capability for capability in goal.required_capabilities if capability in EXTERNAL_EFFECT_CAPABILITIES
        )
        blocked_reasons = list(_selection_blockers(selection))
        blocked_reasons.extend(_external_effect_blockers(profile, external_capabilities, consent_ledger, goal, now))
        blocked = bool(blocked_reasons)
        steps = () if blocked else _plan_steps(goal.required_capabilities)
        required_controls = _required_controls(goal, selection.approval_required_capabilities, external_capabilities)
        plan = AssistantExecutionPlan(
            plan_id=stable_identifier(
                "assistant-plan",
                {
                    "goal_id": goal.goal_id,
                    "profile_id": profile.assistant_id,
                    "capabilities": goal.required_capabilities,
                    "blocked_reasons": tuple(blocked_reasons),
                },
            ),
            goal_id=goal.goal_id,
            profile_id=profile.assistant_id,
            blocked=blocked,
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
            steps=steps,
            required_controls=required_controls,
            closure_contract=closure_contract,
            metadata={
                "intent": goal.intent,
                "risk_tier": goal.risk_tier,
                "plan_is_not_execution": True,
                "skill_capability_boundary_enforced": True,
            },
        )
        plan = replace(
            plan,
            metadata={
                **plan.metadata,
                "life_meaning_judgment_required": True,
                "life_meaning_judgment_ref": _assistant_life_meaning_judgment_ref(plan.plan_id),
            },
        )
        return _stamp_plan(plan)


def _selection_blockers(selection: CapabilitySelection) -> tuple[str, ...]:
    blockers: list[str] = []
    blockers.extend(f"missing_capability:{capability}" for capability in selection.missing_capabilities)
    blockers.extend(f"forbidden_capability:{capability}" for capability in selection.forbidden_capabilities)
    return tuple(blockers)


def _external_effect_blockers(
    profile: AssistantProfile,
    external_capabilities: tuple[str, ...],
    consent_ledger: ConsentLedger | None,
    goal: AssistantGoal,
    now: str,
) -> tuple[str, ...]:
    if not external_capabilities:
        return ()
    if profile.external_send_policy == "deny":
        return tuple(f"external_effect_denied:{capability}" for capability in external_capabilities)
    if consent_ledger is None:
        return tuple(f"active_consent_required:{capability}" for capability in external_capabilities)
    timestamp = ensure_non_empty_text("now", now)
    blockers: list[str] = []
    for capability in external_capabilities:
        decision = consent_ledger.authorize(
            tenant_id=goal.tenant_id,
            owner_id=goal.owner_id,
            capability_id=capability,
            now=timestamp,
        )
        if not decision.allowed:
            blockers.append(f"{decision.reason}:{capability}")
    return tuple(blockers)


def _plan_steps(capabilities: tuple[str, ...]) -> tuple[AssistantPlanStep, ...]:
    steps: list[AssistantPlanStep] = []
    for index, capability in enumerate(capabilities, start=1):
        predicates = _CAPABILITY_CLOSURE_BINDINGS.get(capability, ())
        evidence_required = tuple(f"evidence:{predicate}" for predicate in predicates)
        steps.append(
            AssistantPlanStep(
                step_id=stable_identifier(
                    "assistant-plan-step",
                    {"order": index, "capability_id": capability, "predicates": predicates},
                ),
                order=index,
                capability_id=capability,
                requires_approval=capability in EXTERNAL_EFFECT_CAPABILITIES,
                closure_predicates=predicates,
                evidence_required=evidence_required,
            )
        )
    return tuple(steps)


def _required_controls(
    goal: AssistantGoal,
    approval_required_capabilities: tuple[str, ...],
    external_capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    controls = [
        "assistant_identity_binding",
        "capability_selection",
        "policy_gate",
        "terminal_closure",
        "two_confirmation_closure",
    ]
    if goal.risk_tier in {"high", "critical"}:
        controls.extend(["fresh_approval", "signed_evidence_bundle"])
    if approval_required_capabilities:
        controls.append("approval_receipt")
    if external_capabilities:
        controls.extend(["active_consent", "temporal_idempotency", "effect_reconciliation"])
    if goal.risk_tier == "critical":
        controls.append("operator_review")
    return tuple(dict.fromkeys(controls))


def _stamp_plan(plan: AssistantExecutionPlan) -> AssistantExecutionPlan:
    unstamped = replace(plan, plan_hash="")
    return replace(plan, plan_hash=stable_identifier("assistant-plan-hash", asdict(unstamped)))


def _assistant_life_meaning_judgment_ref(plan_id: str) -> str:
    return f"life-meaning:assistant-plan:{ensure_non_empty_text('plan_id', plan_id)}"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
