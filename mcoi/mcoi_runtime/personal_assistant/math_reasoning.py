"""Purpose: math reasoning planning facade for personal assistant.
Governance scope: operator-supplied numeric scenario comparison, unit checks,
planning-only receipts, and denial of money/system/public effects.
Dependencies: personal-assistant registry contracts and governed intake.
Invariants:
  - This module does not move money, change subscriptions, write records,
    mutate connectors, submit externally, publish, deploy, or write memory.
  - Calculations use only bounded operator-supplied numeric values.
  - Raw private payloads, secrets, tokens, and credentials are rejected before
    projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


MATH_REASONING_SKILL_ID = "math.reasoning.plan"

_MATH_ACTIONS_NOT_TAKEN = (
    "payment_not_moved",
    "paid_subscription_not_changed",
    "system_of_record_not_written",
    "connector_state_not_mutated",
    "external_submission_not_sent",
    "public_post_not_created",
    "publication_not_performed",
    "deployment_not_started",
    "memory_not_written",
    "nested_mind_not_activated",
    "secret_values_not_serialized",
    "raw_private_payload_not_serialized",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_body",
        "body",
        "raw_private_connector_payload",
        "raw_connector_payload",
        "connector_response",
        "authorization",
        "cookie",
        "token",
        "secret",
        "private_key",
        "credential",
        "credentials",
    }
)
_ALLOWED_VALUE_FIELDS = frozenset({"label", "scenario_ref", "value", "unit", "source_ref", "notes"})


@dataclass(frozen=True, slots=True)
class MathReasoningProjection:
    """Planning-only math reasoning projection plus governed receipt."""

    request_id: str
    skill_id: str
    plan: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_text(self.skill_id, "skill_id"))
        if not isinstance(self.plan, Mapping):
            raise PersonalAssistantInvariantError("plan must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "plan", MappingProxyType(dict(self.plan)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready math projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
        }


def plan_math_reasoning(
    intent: GovernedIntent,
    *,
    generated_at: str,
    problem_statement: str,
    known_values: Sequence[Mapping[str, Any]] = (),
    assumptions: Sequence[str] = (),
    constraints: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    requested_result: str = "compare scenarios, check units, and explain assumptions",
    registry: PersonalAssistantSkillRegistry | None = None,
) -> MathReasoningProjection:
    """Prepare a bounded math reasoning plan without external effects."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(MATH_REASONING_SKILL_ID)
    _assert_intent_admits_math_reasoning(intent)
    timestamp = _require_text(generated_at, "generated_at")
    statement = _require_text(problem_statement, "problem_statement")
    values = _bounded_value_tuple(known_values, "known_values", max_items=24)
    assumption_list = _bounded_text_tuple(assumptions, "assumptions", allow_empty=True, max_items=20)
    constraint_list = _bounded_text_tuple(constraints, "constraints", allow_empty=True, max_items=20)
    refs = _bounded_text_tuple(evidence_refs, "evidence_refs", allow_empty=True, max_items=20)
    result_goal = _require_text(requested_result, "requested_result")
    scenario_totals = _scenario_totals(values)
    unit_checks = _unit_checks(values, scenario_totals)
    blockers = _blocking_reasons(
        values=values,
        scenario_totals=scenario_totals,
        unit_checks=unit_checks,
        evidence_refs=refs,
    )
    plan = {
        "plan_type": "math_reasoning_foundation",
        "problem_statement": statement,
        "requested_result": result_goal,
        "known_values": [dict(value) for value in values],
        "assumptions": list(assumption_list),
        "constraints": list(constraint_list),
        "scenario_totals": scenario_totals,
        "unit_checks": unit_checks,
        "comparison_summary": _comparison_summary(statement, scenario_totals, unit_checks),
        "math_decision": "planning_only",
        "answer_claim_authority": "operator_supplied_values_only" if not blockers else "awaiting_operator_values",
        "evidence_gate": {
            "operator_supplied_values_complete": not blockers,
            "evidence_refs": list(refs),
            "blocking_reasons": blockers,
            "money_movement_performed": False,
            "paid_subscription_changed": False,
            "system_of_record_written": False,
            "connector_state_mutated": False,
            "external_submission_sent": False,
            "public_post_created": False,
            "deployment_started": False,
        },
        "next_actions": blockers or ["operator may review the planning-only calculation before use"],
        "effect_boundary": "math_reasoning_planning_only_no_external_effect",
        "execution_allowed": False,
        "money_movement_allowed": False,
        "paid_subscription_allowed": False,
        "system_of_record_write_allowed": False,
        "connector_mutation_allowed": False,
        "external_submission_allowed": False,
        "public_post_allowed": False,
        "deployment_allowed": False,
        "memory_write_allowed": False,
    }
    receipt = _math_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=timestamp,
        plan=plan,
        evidence_refs=refs,
    )
    return MathReasoningProjection(intent.request_id, skill.skill_id, plan, receipt)


def _assert_intent_admits_math_reasoning(intent: GovernedIntent) -> None:
    if MATH_REASONING_SKILL_ID not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(f"{MATH_REASONING_SKILL_ID} is not requested by intent {intent.request_id}")
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block math reasoning")


def _blocking_reasons(
    *,
    values: tuple[Mapping[str, Any], ...],
    scenario_totals: list[dict[str, str]],
    unit_checks: list[dict[str, Any]],
    evidence_refs: tuple[str, ...],
) -> list[str]:
    blockers: list[str] = []
    if not values:
        blockers.append("known_values_missing")
    if len({value["scenario_ref"] for value in values}) < 2:
        blockers.append("scenario_refs_insufficient")
    if any(check["status"] != "pass" for check in unit_checks):
        blockers.append("unit_mismatch")
    if not scenario_totals:
        blockers.append("scenario_totals_missing")
    if not evidence_refs:
        blockers.append("evidence_refs_missing")
    return blockers


def _scenario_totals(values: tuple[Mapping[str, Any], ...]) -> list[dict[str, str]]:
    totals: dict[tuple[str, str], Decimal] = {}
    for value in values:
        key = (str(value["scenario_ref"]), str(value["unit"]))
        totals[key] = totals.get(key, Decimal("0")) + Decimal(str(value["value"]))
    return [
        {"scenario_ref": scenario_ref, "unit": unit, "total": _decimal_text(total)}
        for (scenario_ref, unit), total in sorted(totals.items())
    ]


def _unit_checks(values: tuple[Mapping[str, Any], ...], scenario_totals: list[dict[str, str]]) -> list[dict[str, Any]]:
    units_by_scenario: dict[str, set[str]] = {}
    for value in values:
        units_by_scenario.setdefault(str(value["scenario_ref"]), set()).add(str(value["unit"]))
    all_units = {total["unit"] for total in scenario_totals}
    return [
        {
            "check_id": "scenario_units_consistent",
            "status": "pass" if len(all_units) <= 1 and all(len(units) == 1 for units in units_by_scenario.values()) else "blocked",
            "observed_units": sorted(all_units),
            "message": "all scenario totals use one unit" if len(all_units) <= 1 else "scenario totals use multiple units",
        }
    ]


def _comparison_summary(statement: str, scenario_totals: list[dict[str, str]], unit_checks: list[dict[str, Any]]) -> str:
    if not scenario_totals:
        return f"Math problem '{statement}' is awaiting operator-supplied numeric values."
    if any(check["status"] != "pass" for check in unit_checks):
        return f"Math problem '{statement}' has blocked unit checks; compare only after units are reconciled."
    if len(scenario_totals) < 2:
        return f"Math problem '{statement}' has one scenario total and needs another scenario for comparison."
    first, second = scenario_totals[0], scenario_totals[1]
    delta = Decimal(second["total"]) - Decimal(first["total"])
    return (
        f"Compare {first['scenario_ref']}={first['total']} {first['unit']} "
        f"to {second['scenario_ref']}={second['total']} {second['unit']}; "
        f"delta={_decimal_text(delta)} {first['unit']} using operator-supplied values only."
    )


def _math_receipt(
    *,
    intent: GovernedIntent,
    skill_id: str,
    risk_level: str,
    generated_at: str,
    plan: Mapping[str, Any],
    evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    suffix = _request_suffix(intent.request_id)
    blocked = bool(plan["evidence_gate"]["blocking_reasons"])
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": ["problem_statement", "operator_supplied_known_values", "assumptions", "constraints"],
        "connectors_used": [],
        "decision": "blocked" if blocked else "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["calculation_plan_created", "scenario_totals_projected", "unit_check_recorded", "receipt_created"],
        "actions_not_taken": list(_MATH_ACTIONS_NOT_TAKEN),
        "redactions": ["private_numbers_operator_supplied", "secret_values_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "none",
        },
        "timestamp": generated_at,
        "evidence_refs": _evidence_refs(intent, evidence_refs, suffix),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/math/{suffix}"],
        "outcome": "AwaitingEvidence" if blocked else "SolvedVerified",
        "metadata": {
            "math_decision": plan["math_decision"],
            "answer_claim_authority": plan["answer_claim_authority"],
            "blocking_reasons": list(plan["evidence_gate"]["blocking_reasons"]),
            "math_execution_boundary": "planning_only",
            "live_connector_execution_allowed": False,
            "money_movement_allowed": False,
            "paid_subscription_allowed": False,
            "system_of_record_write_allowed": False,
            "connector_mutation_allowed": False,
            "external_submission_allowed": False,
            "public_post_allowed": False,
            "deployment_allowed": False,
            "memory_write_allowed": False,
        },
    }


def _evidence_refs(intent: GovernedIntent, evidence_refs: tuple[str, ...], suffix: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in (*intent.evidence_refs, *evidence_refs):
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    refs.append(f"proof://personal-assistant/math/{suffix}")
    return refs


def _bounded_value_tuple(
    values: Sequence[Mapping[str, Any]],
    field_name: str,
    *,
    max_items: int,
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a mapping")
        normalized.append(MappingProxyType(_bounded_known_value(value, f"{field_name}[{index}]")))
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    return tuple(normalized)


def _bounded_known_value(value: Mapping[str, Any], field_name: str) -> dict[str, str]:
    unexpected = sorted(set(value) - _ALLOWED_VALUE_FIELDS)
    if unexpected:
        raise PersonalAssistantInvariantError(f"{field_name}: unsupported known value fields {unexpected}")
    numeric_value = _decimal_value(value.get("value"), f"{field_name}.value")
    return {
        "label": _require_text(value.get("label"), f"{field_name}.label"),
        "scenario_ref": _require_text(value.get("scenario_ref"), f"{field_name}.scenario_ref"),
        "value": _decimal_text(numeric_value),
        "unit": _require_text(value.get("unit"), f"{field_name}.unit"),
        "source_ref": _require_text(value.get("source_ref", "operator_supplied"), f"{field_name}.source_ref"),
        "notes": _optional_text(str(value.get("notes", "")), f"{field_name}.notes"),
    }


def _bounded_text_tuple(
    values: Sequence[str],
    field_name: str,
    *,
    allow_empty: bool,
    max_items: int,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        text = _require_text(value, f"{field_name}[{index}]")
        if text not in normalized:
            normalized.append(text)
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _decimal_value(value: Any, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PersonalAssistantInvariantError(f"{field_name} must be numeric") from exc
    if parsed.is_nan() or parsed.is_infinite():
        raise PersonalAssistantInvariantError(f"{field_name} must be finite")
    if abs(parsed) > Decimal("1000000000000"):
        raise PersonalAssistantInvariantError(f"{field_name} exceeds bounded planning range")
    return parsed


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def _optional_text(value: str, field_name: str) -> str:
    if value == "":
        return ""
    return _require_text(value, field_name)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if len(value) > 2000:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max length")
    normalized_name = field_name.lower().rsplit(".", 1)[-1].split("[", 1)[0]
    if normalized_name in _RAW_PRIVATE_FIELD_NAMES:
        raise PersonalAssistantInvariantError(f"{field_name}: raw private field is forbidden")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "math"
