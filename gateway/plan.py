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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from gateway.command_spine import CapabilityPassport, canonical_hash, capability_passport_for
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


class CapabilityPlanBuilder:
    """Build capability plans from direct or decomposed user goals."""

    def __init__(
        self,
        *,
        resolver: CapabilityIntentResolver | None = None,
        capability_passport_loader: Callable[[str], CapabilityPassport] | None = None,
    ) -> None:
        self._resolver = resolver or CapabilityIntentResolver()
        self._capability_passport_loader = capability_passport_loader or capability_passport_for

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
        metadata={"step_count": 1, "builder": "one_step_plan"},
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
