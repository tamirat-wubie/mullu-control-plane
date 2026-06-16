"""Gateway capability plan contracts.

Purpose: Represent one-step and multi-step user goals as governed capability
    plans before execution.
Governance scope: capability admission, dependency validation, risk
    aggregation, and evidence obligation projection.
Dependencies: gateway command spine capability passports and intent resolver.
Invariants:
  - Every plan step names a registered capability passport.
  - Step dependencies must reference earlier declared steps.
  - Plan risk is the maximum step risk.
  - Plan evidence is the union of step evidence obligations.
  - Plan previews expose budget/tool guard state without execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from gateway.command_spine import (
    CapabilityPassport,
    canonical_hash,
    capability_passport_for,
    capability_passport_from_registry_entry,
)
from gateway.intent_resolver import CapabilityIntentResolver


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class CapabilityPlanStep:
    """One governed capability invocation in a plan."""

    step_id: str
    capability_id: str
    params: dict[str, Any]
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityPlan:
    """Typed plan created from a user goal."""

    plan_id: str
    tenant_id: str
    identity_id: str
    goal: str
    steps: tuple[CapabilityPlanStep, ...]
    risk_tier: str
    approval_required: bool
    evidence_required: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CapabilityPlanPreviewStep:
    """Redacted step shape for plan review before execution."""

    step_id: str
    capability_id: str
    depends_on: tuple[str, ...]
    param_names: tuple[str, ...]
    params_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preview step data without raw params."""
        return {
            "step_id": self.step_id,
            "capability_id": self.capability_id,
            "depends_on": list(self.depends_on),
            "param_names": list(self.param_names),
            "params_hash": self.params_hash,
        }


@dataclass(frozen=True, slots=True)
class CapabilityPlanPreview:
    """Read-only plan review envelope emitted before execution authority."""

    preview_id: str
    plan_id: str
    tenant_id: str
    identity_id: str
    goal_hash: str
    step_count: int
    steps: tuple[CapabilityPlanPreviewStep, ...]
    risk_tier: str
    approval_required: bool
    evidence_required: tuple[str, ...]
    budget: dict[str, Any]
    tools: tuple[dict[str, Any], ...]
    execution_allowed: bool
    safe_default: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preview data without raw goal text or params."""
        return {
            "preview_id": self.preview_id,
            "plan_id": self.plan_id,
            "tenant_id": self.tenant_id,
            "identity_id": self.identity_id,
            "goal_hash": self.goal_hash,
            "step_count": self.step_count,
            "steps": [step.to_dict() for step in self.steps],
            "risk_tier": self.risk_tier,
            "approval_required": self.approval_required,
            "evidence_required": list(self.evidence_required),
            "budget": dict(self.budget),
            "tools": [dict(tool) for tool in self.tools],
            "execution_allowed": self.execution_allowed,
            "safe_default": self.safe_default,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


class CapabilityPlanBuilder:
    """Build capability plans from direct or decomposed user goals."""

    def __init__(
        self,
        *,
        resolver: CapabilityIntentResolver | None = None,
        capability_passport_loader: Callable[[str], CapabilityPassport] | None = None,
        capability_admission_gate: Any | None = None,
    ) -> None:
        if capability_passport_loader is not None and capability_admission_gate is not None:
            raise ValueError("capability plan builder requires one capability authority")
        self._resolver = resolver or CapabilityIntentResolver()
        self._capability_passport_loader = (
            capability_passport_loader
            or _passport_loader_from_admission_gate(capability_admission_gate)
            or capability_passport_for
        )
        self._admission_source = (
            "governed_capability_registry"
            if capability_admission_gate is not None
            else "capability_passport"
        )

    def build(
        self,
        *,
        message: str,
        tenant_id: str,
        identity_id: str,
    ) -> CapabilityPlan | None:
        """Build a governed capability plan or return None for conversation."""
        proposed_steps = self._decompose(message)
        if not proposed_steps:
            intent = self._resolver.resolve(message)
            if intent is None:
                return None
            proposed_steps = (
                CapabilityPlanStep(
                    step_id="step-1",
                    capability_id=intent.capability_id,
                    params=dict(intent.params),
                ),
            )

        validated_steps = _validate_steps_with_loader(proposed_steps, self._capability_passport_loader)
        risk_tier = _max_risk(validated_steps, self._capability_passport_loader)
        evidence_required = _union_evidence(validated_steps, self._capability_passport_loader)
        step_contracts = _step_contracts(validated_steps, self._capability_passport_loader)
        plan_id = _stable_plan_id(
            tenant_id=tenant_id,
            identity_id=identity_id,
            goal=message,
            steps=validated_steps,
        )
        return CapabilityPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            goal=message,
            steps=validated_steps,
            risk_tier=risk_tier,
            approval_required=risk_tier in {"medium", "high"},
            evidence_required=evidence_required,
            metadata={
                "step_count": len(validated_steps),
                "builder": "deterministic_capability_plan_builder",
                "admission_source": self._admission_source,
                "step_contracts": list(step_contracts),
            },
        )

    def _decompose(self, message: str) -> tuple[CapabilityPlanStep, ...]:
        """Decompose simple compound goals into ordered capability steps."""
        segments = _split_goal_segments(message)
        if len(segments) < 2:
            return ()
        steps: list[CapabilityPlanStep] = []
        previous_step_id = ""
        for segment in segments:
            intent = self._resolver.resolve(segment)
            if intent is None:
                continue
            step_id = f"step-{len(steps) + 1}"
            params = dict(intent.params)
            if previous_step_id and intent.capability_id in {
                "creative.document_generate",
                "enterprise.notification_send",
                "enterprise.task_schedule",
            }:
                params.setdefault("source", f"{previous_step_id}.output")
            depends_on = (previous_step_id,) if previous_step_id else ()
            steps.append(CapabilityPlanStep(
                step_id=step_id,
                capability_id=intent.capability_id,
                params=params,
                depends_on=depends_on,
            ))
            previous_step_id = step_id
        return tuple(steps) if len(steps) > 1 else ()


def one_step_plan(
    *,
    capability_id: str,
    params: dict[str, Any],
    tenant_id: str,
    identity_id: str,
    goal: str,
) -> CapabilityPlan:
    """Build a one-step plan from an already typed capability."""
    step = CapabilityPlanStep(step_id="step-1", capability_id=capability_id, params=dict(params))
    validated_steps = _validate_steps((step,))
    risk_tier = _max_risk(validated_steps)
    step_contracts = _step_contracts(validated_steps, capability_passport_for)
    return CapabilityPlan(
        plan_id=_stable_plan_id(
            tenant_id=tenant_id,
            identity_id=identity_id,
            goal=goal,
            steps=validated_steps,
        ),
        tenant_id=tenant_id,
        identity_id=identity_id,
        goal=goal,
        steps=validated_steps,
        risk_tier=risk_tier,
        approval_required=risk_tier in {"medium", "high"},
        evidence_required=_union_evidence(validated_steps),
        metadata={"step_count": 1, "builder": "one_step_plan", "step_contracts": list(step_contracts)},
    )


def preview_for_plan(
    *,
    plan: CapabilityPlan,
    created_at: str,
    capability_passport_loader: Callable[[str], CapabilityPassport] = capability_passport_for,
) -> CapabilityPlanPreview:
    """Build a read-only, redacted preview for a governed capability plan.

    Input contract: ``plan`` has already passed capability passport validation.
    Output contract: the preview exposes topology, risk, evidence, and hashes,
    never the raw goal text or raw step params.
    Error contract: total for valid ``CapabilityPlan`` instances.
    """
    steps = tuple(
        CapabilityPlanPreviewStep(
            step_id=step.step_id,
            capability_id=step.capability_id,
            depends_on=tuple(step.depends_on),
            param_names=tuple(sorted(str(name) for name in step.params)),
            params_hash=canonical_hash(step.params),
        )
        for step in plan.steps
    )
    goal_hash = canonical_hash({"goal": plan.goal})
    step_contracts = _preview_step_contracts(plan, capability_passport_loader)
    budget = _preview_budget(step_contracts)
    tools = _preview_tools(step_contracts)
    preview_payload = {
        "plan_id": plan.plan_id,
        "goal_hash": goal_hash,
        "steps": [step.to_dict() for step in steps],
        "risk_tier": plan.risk_tier,
        "approval_required": plan.approval_required,
        "budget": budget,
        "tools": list(tools),
        "created_at": created_at,
    }
    return CapabilityPlanPreview(
        preview_id=f"plan-preview-{canonical_hash(preview_payload)[:16]}",
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        identity_id=plan.identity_id,
        goal_hash=goal_hash,
        step_count=len(steps),
        steps=steps,
        risk_tier=plan.risk_tier,
        approval_required=plan.approval_required,
        evidence_required=tuple(plan.evidence_required),
        budget=budget,
        tools=tools,
        execution_allowed=False,
        safe_default="await_approval_or_explicit_execution",
        created_at=created_at,
        metadata={
            "builder": str(plan.metadata.get("builder", "")),
            "admission_source": str(plan.metadata.get("admission_source", "")),
            "step_contracts": list(step_contracts),
            "read_only": True,
        },
    )


def _validate_steps(steps: tuple[CapabilityPlanStep, ...]) -> tuple[CapabilityPlanStep, ...]:
    return _validate_steps_with_loader(steps, capability_passport_for)


def _validate_steps_with_loader(
    steps: tuple[CapabilityPlanStep, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport],
) -> tuple[CapabilityPlanStep, ...]:
    if not steps:
        raise ValueError("capability plan requires at least one step")
    declared: set[str] = set()
    for step in steps:
        if not step.step_id:
            raise ValueError("capability plan step_id is required")
        if step.step_id in declared:
            raise ValueError(f"duplicate capability plan step_id: {step.step_id}")
        capability_passport_loader(step.capability_id)
        missing_dependencies = [dep for dep in step.depends_on if dep not in declared]
        if missing_dependencies:
            raise ValueError(f"step {step.step_id} has unknown dependency: {missing_dependencies[0]}")
        declared.add(step.step_id)
    return steps


def _passport_loader_from_admission_gate(
    capability_admission_gate: Any | None,
) -> Callable[[str], CapabilityPassport] | None:
    if capability_admission_gate is None:
        return None
    admit = getattr(capability_admission_gate, "admit", None)
    capability_for_intent = getattr(capability_admission_gate, "capability_for_intent", None)
    if not callable(admit) or not callable(capability_for_intent):
        raise ValueError("capability admission gate must expose admit and capability_for_intent")

    def load_passport(capability_id: str) -> CapabilityPassport:
        decision = admit(command_id=f"plan-builder:{capability_id}", intent_name=capability_id)
        status = getattr(getattr(decision, "status", ""), "value", getattr(decision, "status", ""))
        if status != "accepted":
            reason = str(getattr(decision, "reason", "") or "capability registry admission rejected")
            raise ValueError(f"capability plan admission rejected for {capability_id}: {reason}")
        return capability_passport_from_registry_entry(capability_for_intent(capability_id))

    return load_passport


def _max_risk(
    steps: tuple[CapabilityPlanStep, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport] = capability_passport_for,
) -> str:
    risk = "low"
    for step in steps:
        passport = capability_passport_loader(step.capability_id)
        if _RISK_ORDER.get(passport.risk_tier, 1) > _RISK_ORDER.get(risk, 0):
            risk = passport.risk_tier
    return risk


def _union_evidence(
    steps: tuple[CapabilityPlanStep, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport] = capability_passport_for,
) -> tuple[str, ...]:
    evidence: list[str] = []
    for step in steps:
        passport = capability_passport_loader(step.capability_id)
        for item in passport.evidence_required:
            if item not in evidence:
                evidence.append(item)
    return tuple(evidence)


def _step_contracts(
    steps: tuple[CapabilityPlanStep, ...],
    capability_passport_loader: Callable[[str], CapabilityPassport],
) -> tuple[dict[str, Any], ...]:
    contracts: list[dict[str, Any]] = []
    for step in steps:
        passport = capability_passport_loader(step.capability_id)
        contracts.append({
            "step_id": step.step_id,
            "capability_id": step.capability_id,
            "risk_tier": passport.risk_tier,
            "requires": list(passport.requires),
            "authority_required": list(passport.authority_required),
            "external_system": passport.external_system,
            "mutates_world": passport.mutates_world,
            "max_estimated_cost_units": _cost_model_max_estimated_cost(passport.cost_model),
        })
    return tuple(contracts)


def _preview_step_contracts(
    plan: CapabilityPlan,
    capability_passport_loader: Callable[[str], CapabilityPassport] = capability_passport_for,
) -> tuple[dict[str, Any], ...]:
    raw_contracts = plan.metadata.get("step_contracts")
    if isinstance(raw_contracts, list) and raw_contracts:
        return tuple(dict(contract) for contract in raw_contracts if isinstance(contract, dict))
    return _step_contracts(plan.steps, capability_passport_loader)


def _preview_budget(step_contracts: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    budget_contracts = tuple(
        contract
        for contract in step_contracts
        if "budget_reserved" in _string_tuple(contract.get("requires"))
    )
    budget_step_ids = tuple(
        str(contract.get("step_id", ""))
        for contract in budget_contracts
    )
    all_step_ids = tuple(str(contract.get("step_id", "")) for contract in step_contracts)
    not_required_step_ids = tuple(step_id for step_id in all_step_ids if step_id not in budget_step_ids)
    budget_required = bool(budget_step_ids)
    cost_estimates = tuple(
        estimate
        for estimate in (_contract_max_estimated_cost(contract) for contract in budget_contracts)
        if estimate is not None
    )
    unknown_estimate_count = max(0, len(budget_contracts) - len(cost_estimates))
    estimated_cost_units = sum(cost_estimates) if cost_estimates else None
    estimate_state = "not_required"
    estimate_source = "capability_passport"
    if budget_required and estimated_cost_units is None:
        estimate_state = "not_calculated"
        estimate_source = "runtime_budget_gate_required"
    elif budget_required and unknown_estimate_count:
        estimate_state = "partial"
        estimate_source = "capability_cost_model"
    elif budget_required:
        estimate_state = "estimated"
        estimate_source = "capability_cost_model"
    return {
        "budget_required": budget_required,
        "budget_gate": "budget_reserved" if budget_required else "not_required",
        "estimate_state": estimate_state,
        "estimate_source": estimate_source,
        "estimated_cost_units": estimated_cost_units,
        "used_cost_units": 0,
        "used_cost_source": "preview_execution_not_started",
        "limit_cost_units": None,
        "remaining_cost_units": None,
        "currency": "cost_units",
        "required_by_steps": list(budget_step_ids),
        "not_required_by_steps": list(not_required_step_ids),
        "execution_spend_allowed": False,
    }


def _preview_tools(step_contracts: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    tools: list[dict[str, Any]] = []
    for contract in step_contracts:
        requires = _string_tuple(contract.get("requires"))
        external_system = str(contract.get("external_system", ""))
        mutates_world = bool(contract.get("mutates_world", False))
        budget_required = "budget_reserved" in requires
        permission_state = "read_only" if "read_only" in requires and not mutates_world else "preview_only"
        if budget_required or mutates_world:
            permission_state = "approval_required"
        estimated_cost_units = _contract_max_estimated_cost(contract)
        tools.append({
            "step_id": str(contract.get("step_id", "")),
            "capability_id": str(contract.get("capability_id", "")),
            "tool_name": external_system or str(contract.get("capability_id", "")),
            "tool_type": "external_system" if external_system else "local_capability",
            "permission_state": permission_state,
            "budget_required": budget_required,
            "estimated_cost_units": estimated_cost_units,
            "external_system": external_system,
            "mutates_world": mutates_world,
            "authority_required": list(_string_tuple(contract.get("authority_required"))),
            "requires": list(requires),
            "execution_allowed": False,
        })
    return tuple(tools)


def _cost_model_max_estimated_cost(cost_model: Mapping[str, Any]) -> float | None:
    return _nonnegative_number(cost_model.get("max_estimated_cost"))


def _contract_max_estimated_cost(contract: Mapping[str, Any]) -> float | None:
    return _nonnegative_number(contract.get("max_estimated_cost_units"))


def _nonnegative_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


def _stable_plan_id(
    *,
    tenant_id: str,
    identity_id: str,
    goal: str,
    steps: tuple[CapabilityPlanStep, ...],
) -> str:
    payload = {
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "goal": goal,
        "steps": [
            {
                "step_id": step.step_id,
                "capability_id": step.capability_id,
                "params": step.params,
                "depends_on": step.depends_on,
            }
            for step in steps
        ],
    }
    return f"plan-{canonical_hash(payload)[:16]}"


def _split_goal_segments(message: str) -> tuple[str, ...]:
    segments = [
        segment.strip(" .")
        for segment in message.replace(" then ", " and ").split(" and ")
        if segment.strip(" .")
    ]
    return tuple(segments)
