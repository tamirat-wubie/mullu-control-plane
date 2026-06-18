"""Purpose: schema-backed personal-assistant preview planning.
Governance scope: governed intent, WHQR binding gaps, skill-step projection,
approval gates, receipt emission, and no-execution guarantees.
Dependencies: personal-assistant intake, skill registry contracts, and approval
matrix runtime policy.
Invariants:
  - Planning never calls connectors, sends messages, writes memory, deploys, or
    mutates a system of record.
  - Missing hard bindings produce blocked plans and explicit not-taken actions.
  - Every emitted plan has a companion receipt with replayable evidence refs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .approval_matrix import (
    PersonalAssistantApprovalMatrix,
    load_default_personal_assistant_approval_matrix,
)
from .contracts import PersonalAssistantInvariantError, SkillMode, SkillRiskLevel
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


_NO_EXECUTION_ACTIONS_NOT_TAKEN = (
    "connector_not_called",
    "external_message_not_sent",
    "connector_state_not_mutated",
    "system_of_record_not_written",
    "money_legal_public_action_not_performed",
    "deployment_not_started",
    "live_nested_mind_not_activated",
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantPlanningEnvelope:
    """Request, plan, and receipt projection for one preview compile."""

    request: Mapping[str, Any]
    plan: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready planning envelope."""
        return {
            "request": dict(self.request),
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
            "governed": True,
            "execution_allowed": False,
        }


def build_personal_assistant_preview_plan(
    intent: GovernedIntent,
    *,
    plan_id: str,
    created_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
    approval_matrix: PersonalAssistantApprovalMatrix | None = None,
) -> PersonalAssistantPlanningEnvelope:
    """Build a no-execution plan and receipt for a governed intent.

    Input contract: a validated GovernedIntent plus schema-ready ids/timestamp.
    Output contract: a JSON-ready request, plan, and receipt envelope.
    Error contract: raises PersonalAssistantInvariantError for invalid ids,
    missing registry entries, or unsafe plan state.
    """

    plan_id = _require_prefix(plan_id, "plan_id", "pa_plan_")
    created_at = _require_text(created_at, "created_at")
    skill_registry = registry or load_default_skill_registry()
    matrix = approval_matrix or load_default_personal_assistant_approval_matrix()
    selected_skills = tuple(skill_registry.get(skill_id) for skill_id in intent.requested_skill_ids)
    matrix_policy = matrix.policy_for(intent.risk_level)
    planned_mode = _matrix_mode_for_intent(intent, matrix_policy.allowed_modes)
    _assert_steps_admitted_by_matrix(intent, selected_skills, matrix)
    steps = _plan_steps(intent, selected_skills, skill_registry)
    approval_required = intent.requires_approval
    reason_codes = _approval_reason_codes(intent)
    plan = {
        "plan_id": plan_id,
        "request_id": intent.request_id,
        "created_at": created_at,
        "goal": intent.user_goal,
        "risk_level": intent.risk_level.value,
        "mode": planned_mode,
        "requires_approval": approval_required,
        "dry_run_available": True,
        "execution_allowed": False,
        "approval_gate": {
            "approval_required": approval_required,
            "approval_level": intent.risk_level.value if approval_required else "none",
            "approval_ref": _approval_ref(intent),
            "reason_codes": reason_codes,
        },
        "steps": steps,
        "actions_not_authorized": _actions_not_authorized(intent),
        "receipt_refs": [f"pa_receipt_{_suffix(plan_id)}_preview"],
        "evidence_refs": list(
            _dedupe((*intent.evidence_refs, f"proof://personal-assistant/plan/{_suffix(plan_id)}"))
        ),
        "metadata": {
            "foundation_only": True,
            "planner": "personal_assistant_preview_v1",
            "approval_matrix": _approval_matrix_plan_metadata(matrix, intent.risk_level),
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
        },
    }
    receipt = _plan_receipt(intent, plan, selected_skills, matrix)
    return PersonalAssistantPlanningEnvelope(intent.as_request_dict(), plan, receipt)


def _plan_steps(
    intent: GovernedIntent,
    selected_skills: Sequence[Any],
    registry: PersonalAssistantSkillRegistry,
) -> list[dict[str, Any]]:
    if not selected_skills:
        clarification_skill = registry.get("personal_assistant.clarification.request")
        return [_step_from_skill(intent, clarification_skill, index=1, forced_mode=RequestExecutionMode.BLOCKED)]
    forced_mode = RequestExecutionMode.BLOCKED if intent.has_missing_bindings else None
    return [
        _step_from_skill(intent, skill, index=index, forced_mode=forced_mode)
        for index, skill in enumerate(selected_skills, start=1)
    ]


def _step_from_skill(
    intent: GovernedIntent,
    skill: Any,
    *,
    index: int,
    forced_mode: RequestExecutionMode | None,
) -> dict[str, Any]:
    if forced_mode is not None:
        mode = forced_mode.value
    elif skill.risk_level is SkillRiskLevel.P5:
        mode = RequestExecutionMode.BLOCKED.value
    else:
        mode = _mode_for_skill(skill.mode, intent.execution_mode)
    return {
        "step_id": f"step_{index:02d}_{skill.skill_id.replace('.', '_')}",
        "skill_id": skill.skill_id,
        "capability_refs": list(skill.capability_refs),
        "mode": mode,
        "risk_level": skill.risk_level.value,
        "action": _action_for_skill(skill),
        "approval_required": bool(skill.requires_approval or skill.risk_level.requires_explicit_approval),
        "produces_receipt": True,
        "effect_boundary": _effect_boundary_label(skill),
    }


def _mode_for_skill(skill_mode: SkillMode, intent_mode: RequestExecutionMode) -> str:
    if intent_mode is RequestExecutionMode.EXECUTE_WITH_APPROVAL:
        return RequestExecutionMode.EXECUTE_WITH_APPROVAL.value
    if skill_mode is SkillMode.DRAFT_ONLY:
        return RequestExecutionMode.DRAFT.value
    if skill_mode is SkillMode.READ_ONLY or skill_mode is SkillMode.PLANNING_ONLY:
        return RequestExecutionMode.PREVIEW.value
    if skill_mode is SkillMode.APPROVAL_REQUIRED:
        return RequestExecutionMode.EXECUTE_WITH_APPROVAL.value
    return RequestExecutionMode.BLOCKED.value


def _matrix_mode_for_intent(intent: GovernedIntent, allowed_modes: Sequence[str]) -> str:
    if intent.has_missing_bindings:
        mode = RequestExecutionMode.BLOCKED.value
    elif intent.risk_level is SkillRiskLevel.P5:
        mode = RequestExecutionMode.BLOCKED.value
    else:
        mode = intent.execution_mode.value
    if mode == RequestExecutionMode.BLOCKED.value and intent.has_missing_bindings:
        return mode
    if mode not in allowed_modes:
        raise PersonalAssistantInvariantError(
            f"{intent.risk_level.value}: planner mode {mode} is not allowed by approval matrix"
        )
    return mode


def _assert_steps_admitted_by_matrix(
    intent: GovernedIntent,
    selected_skills: Sequence[Any],
    matrix: PersonalAssistantApprovalMatrix,
) -> None:
    for skill in selected_skills:
        policy = matrix.policy_for(skill.risk_level)
        step_mode = (
            RequestExecutionMode.BLOCKED.value
            if intent.has_missing_bindings or skill.risk_level is SkillRiskLevel.P5
            else _mode_for_skill(skill.mode, intent.execution_mode)
        )
        if step_mode == RequestExecutionMode.BLOCKED.value and intent.has_missing_bindings:
            continue
        if step_mode not in policy.allowed_modes:
            raise PersonalAssistantInvariantError(
                f"{skill.skill_id}: planner mode {step_mode} is not allowed by approval matrix "
                f"for {skill.risk_level.value}"
            )
        if skill.risk_level.requires_explicit_approval and not policy.explicit_approval_required:
            raise PersonalAssistantInvariantError(
                f"{skill.skill_id}: approval matrix does not require explicit approval"
            )
        if skill.risk_level is SkillRiskLevel.P5 and step_mode != RequestExecutionMode.BLOCKED.value:
            raise PersonalAssistantInvariantError(f"{skill.skill_id}: P5 planner step must be blocked")


def _action_for_skill(skill: Any) -> str:
    if skill.allowed_actions:
        return str(skill.allowed_actions[0])
    return "plan"


def _effect_boundary_label(skill: Any) -> str:
    boundary = skill.effect_boundary
    if boundary.money_legal_public_allowed:
        return "money_legal_public_boundary"
    if boundary.external_write_allowed:
        return "external_write_boundary"
    if boundary.internal_write_allowed:
        return "internal_write_boundary"
    if boundary.draft_only:
        return "draft_only_boundary"
    if boundary.read_only:
        return "read_only_boundary"
    return "planning_boundary"


def _approval_reason_codes(intent: GovernedIntent) -> list[str]:
    reasons = [binding.reason_code for binding in intent.missing_bindings]
    if intent.requires_approval:
        reasons.append("risk_level_requires_explicit_approval")
    if not reasons:
        reasons.append("no_effect_bearing_execution_authorized")
    return list(_dedupe(reasons))


def _approval_ref(intent: GovernedIntent) -> str:
    if not intent.requires_approval:
        return ""
    return f"governance/personal_assistant_approval_matrix.yaml#{intent.risk_level.value}"


def _actions_not_authorized(intent: GovernedIntent) -> list[str]:
    blocked = list(intent.blocked_actions)
    blocked.extend(_NO_EXECUTION_ACTIONS_NOT_TAKEN)
    if intent.has_missing_bindings:
        blocked.append("plan_execution_blocked_until_clarification")
    return list(_dedupe(blocked))


def _plan_receipt(
    intent: GovernedIntent,
    plan: Mapping[str, Any],
    selected_skills: Sequence[Any],
    matrix: PersonalAssistantApprovalMatrix,
) -> dict[str, Any]:
    receipt_id = str(plan["receipt_refs"][0])
    primary_skill_id = selected_skills[0].skill_id if selected_skills else "personal_assistant.clarification.request"
    connectors = []
    for skill in selected_skills:
        connectors.extend(skill.connectors)
    decision = "blocked" if intent.has_missing_bindings else ("approval_required" if intent.requires_approval else "allowed")
    outcome = "AwaitingEvidence" if intent.has_missing_bindings or intent.requires_approval else "SolvedVerified"
    return {
        "receipt_id": receipt_id,
        "request_id": intent.request_id,
        "skill_id": primary_skill_id,
        "mode": str(plan["mode"]),
        "risk_level": _max_receipt_risk(intent, selected_skills).value,
        "inputs_used": ["governed_intent", "skill_registry", "approval_matrix"],
        "connectors_used": list(_dedupe(connectors)),
        "decision": decision,
        "approval_required": bool(intent.requires_approval),
        "approval_ref": str(plan["approval_gate"]["approval_ref"]),
        "actions_taken": ["request_interpreted", "skill_plan_preview_created", "receipt_created"],
        "actions_not_taken": list(plan["actions_not_authorized"]),
        "redactions": ["raw_private_payload_not_serialized", "secret_values_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only" if connectors else "no_connector_payload",
            "body_projection": "none",
        },
        "timestamp": str(plan["created_at"]),
        "evidence_refs": list(plan["evidence_refs"]),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/plan/{_suffix(str(plan['plan_id']))}"],
        "outcome": outcome,
        "metadata": {
            "foundation_only": True,
            "execution_allowed": False,
            "approval_matrix_ref": matrix.matrix_id,
            "approval_matrix": _approval_matrix_plan_metadata(matrix, intent.risk_level),
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "deployment_mutation_allowed": False,
        },
    }


def _approval_matrix_plan_metadata(
    matrix: PersonalAssistantApprovalMatrix,
    risk_level: SkillRiskLevel,
) -> dict[str, Any]:
    read_model = matrix.read_model()
    policy = matrix.policy_for(risk_level)
    return {
        "schema_version": read_model["schema_version"],
        "matrix_id": read_model["matrix_id"],
        "foundation_mode_required": read_model["foundation_mode_required"],
        "risk_level": policy.level.value,
        "risk_allowed_modes": list(policy.allowed_modes),
        "explicit_approval_required": policy.explicit_approval_required,
        "effect_bearing": policy.effect_bearing,
        "execution_allowed_by_matrix": read_model["execution_allowed_by_matrix"],
        "approval_is_execution": read_model["approval_is_execution"],
        "overclaim_blocks": dict(read_model["overclaim_blocks"]),
    }


def _max_receipt_risk(intent: GovernedIntent, selected_skills: Sequence[Any]) -> SkillRiskLevel:
    risks = [intent.risk_level]
    risks.extend(skill.risk_level for skill in selected_skills)
    return max(risks, key=lambda risk: risk.order)


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        text = _require_text(value, "dedupe_value")
        if text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _require_prefix(value: str, field_name: str, prefix: str) -> str:
    text = _require_text(value, field_name)
    if not text.startswith(prefix):
        raise PersonalAssistantInvariantError(f"{field_name} must start with {prefix}")
    return text


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value


def _suffix(value: str) -> str:
    return value.removeprefix("pa_plan_").replace(".", "_")
