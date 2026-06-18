"""Purpose: schedule/resource planning facade for personal assistant.
Governance scope: operator-supplied time windows, work-item capacity planning,
preview-only receipts, and denial of calendar/task/system/public effects.
Dependencies: personal-assistant registry contracts and governed intake.
Invariants:
  - This module does not create events, write tasks, message people, move
    money, mutate connectors, submit externally, publish, deploy, or write
    memory.
  - Planning uses only bounded operator-supplied windows and work items.
  - Raw private payloads, secrets, tokens, and credentials are rejected before
    projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


PLANNING_OPTIMIZE_SCHEDULE_SKILL_ID = "planning.optimize_schedule"

_PLANNING_ACTIONS_NOT_TAKEN = (
    "calendar_event_not_created",
    "calendar_event_not_moved",
    "calendar_event_not_cancelled",
    "invite_not_sent",
    "task_not_written",
    "task_system_not_mutated",
    "person_not_messaged",
    "system_of_record_not_written",
    "connector_state_not_mutated",
    "external_submission_not_sent",
    "public_post_not_created",
    "payment_not_moved",
    "paid_subscription_not_changed",
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
_ALLOWED_WINDOW_FIELDS = frozenset({"window_ref", "label", "start", "end", "capacity_minutes", "source_ref", "notes"})
_ALLOWED_ITEM_FIELDS = frozenset(
    {
        "item_ref",
        "title",
        "estimated_minutes",
        "priority",
        "earliest_start",
        "due",
        "required_window_ref",
        "source_ref",
        "notes",
    }
)


@dataclass(frozen=True, slots=True)
class PlanningScheduleProjection:
    """Planning-only schedule/resource projection plus governed receipt."""

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
        """Return a deterministic JSON-ready planning projection."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "plan": dict(self.plan),
            "receipt": dict(self.receipt),
        }


def plan_schedule_optimization(
    intent: GovernedIntent,
    *,
    generated_at: str,
    objective: str,
    time_windows: Sequence[Mapping[str, Any]] = (),
    work_items: Sequence[Mapping[str, Any]] = (),
    assumptions: Sequence[str] = (),
    constraints: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    requested_result: str = "assign work items to available windows and identify blockers",
    registry: PersonalAssistantSkillRegistry | None = None,
) -> PlanningScheduleProjection:
    """Prepare a schedule/resource plan without writing calendar or task state."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(PLANNING_OPTIMIZE_SCHEDULE_SKILL_ID)
    _assert_intent_admits_planning(intent)
    timestamp = _require_text(generated_at, "generated_at")
    goal = _require_text(objective, "objective")
    windows = _bounded_window_tuple(time_windows, "time_windows", max_items=24)
    items = _bounded_item_tuple(work_items, "work_items", max_items=48)
    assumption_list = _bounded_text_tuple(assumptions, "assumptions", allow_empty=True, max_items=20)
    constraint_list = _bounded_text_tuple(constraints, "constraints", allow_empty=True, max_items=20)
    refs = _bounded_text_tuple(evidence_refs, "evidence_refs", allow_empty=True, max_items=20)
    result_goal = _require_text(requested_result, "requested_result")
    assignment_plan, capacity_summary = _assignment_projection(windows, items)
    blockers = _blocking_reasons(
        windows=windows,
        items=items,
        assignments=assignment_plan,
        evidence_refs=refs,
    )
    plan = {
        "plan_type": "planning_schedule_foundation",
        "objective": goal,
        "requested_result": result_goal,
        "time_windows": [dict(window) for window in windows],
        "work_items": [dict(item) for item in items],
        "assumptions": list(assumption_list),
        "constraints": list(constraint_list),
        "assignment_plan": assignment_plan,
        "capacity_summary": capacity_summary,
        "planning_summary": _planning_summary(goal, assignment_plan, capacity_summary),
        "planning_decision": "preview_only",
        "answer_claim_authority": "operator_supplied_schedule_values_only" if not blockers else "awaiting_operator_schedule_values",
        "evidence_gate": {
            "operator_supplied_schedule_complete": not blockers,
            "evidence_refs": list(refs),
            "blocking_reasons": blockers,
            "calendar_event_created": False,
            "calendar_event_moved": False,
            "calendar_event_cancelled": False,
            "invite_sent": False,
            "task_written": False,
            "task_system_mutated": False,
            "person_messaged": False,
            "system_of_record_written": False,
            "connector_state_mutated": False,
            "external_submission_sent": False,
            "public_post_created": False,
            "payment_moved": False,
            "deployment_started": False,
        },
        "next_actions": blockers or ["operator may review the schedule preview before creating events or tasks"],
        "effect_boundary": "schedule_planning_preview_only_no_external_effect",
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "calendar_write_allowed": False,
        "task_write_allowed": False,
        "invite_allowed": False,
        "message_person_allowed": False,
        "system_of_record_write_allowed": False,
        "connector_mutation_allowed": False,
        "external_submission_allowed": False,
        "public_post_allowed": False,
        "money_movement_allowed": False,
        "paid_subscription_allowed": False,
        "deployment_allowed": False,
        "memory_write_allowed": False,
        "public_readiness_claim_allowed": False,
        "customer_readiness_claim_allowed": False,
        "nested_mind_live_activation_allowed": False,
    }
    receipt = _planning_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        generated_at=timestamp,
        plan=plan,
        evidence_refs=refs,
    )
    return PlanningScheduleProjection(intent.request_id, skill.skill_id, plan, receipt)


def _assert_intent_admits_planning(intent: GovernedIntent) -> None:
    if PLANNING_OPTIMIZE_SCHEDULE_SKILL_ID not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(f"{PLANNING_OPTIMIZE_SCHEDULE_SKILL_ID} is not requested by intent {intent.request_id}")
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block schedule planning")


def _assignment_projection(
    windows: tuple[Mapping[str, Any], ...],
    items: tuple[Mapping[str, Any], ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = {str(window["window_ref"]): int(window["capacity_minutes"]) for window in windows}
    assigned = {str(window["window_ref"]): 0 for window in windows}
    ordered_items = sorted(
        enumerate(items),
        key=lambda pair: (str(pair[1]["due"] or "9999-12-31T23:59:59"), int(pair[1]["priority"]), pair[0]),
    )
    assignments_by_item: dict[str, dict[str, Any]] = {}
    for _, item in ordered_items:
        estimate = int(item["estimated_minutes"])
        candidate_windows = _candidate_windows(windows, item)
        chosen_ref = ""
        reason = "capacity_unavailable"
        for window in candidate_windows:
            window_ref = str(window["window_ref"])
            if remaining[window_ref] >= estimate:
                chosen_ref = window_ref
                remaining[window_ref] -= estimate
                assigned[window_ref] += estimate
                reason = "assigned"
                break
        assignments_by_item[str(item["item_ref"])] = {
            "item_ref": item["item_ref"],
            "title": item["title"],
            "window_ref": chosen_ref,
            "estimated_minutes": str(estimate),
            "status": "assigned" if chosen_ref else "blocked",
            "reason": reason,
        }
    assignment_plan = [assignments_by_item[str(item["item_ref"])] for item in items]
    capacity_summary = [
        {
            "window_ref": window["window_ref"],
            "label": window["label"],
            "capacity_minutes": str(window["capacity_minutes"]),
            "assigned_minutes": str(assigned[str(window["window_ref"])]),
            "remaining_minutes": str(remaining[str(window["window_ref"])]),
            "status": "within_capacity" if remaining[str(window["window_ref"])] >= 0 else "over_capacity",
        }
        for window in windows
    ]
    return assignment_plan, capacity_summary


def _candidate_windows(windows: tuple[Mapping[str, Any], ...], item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    required_ref = str(item.get("required_window_ref", ""))
    candidates = [window for window in windows if not required_ref or str(window["window_ref"]) == required_ref]
    return sorted(candidates, key=lambda window: (str(window["start"]), str(window["window_ref"])))


def _blocking_reasons(
    *,
    windows: tuple[Mapping[str, Any], ...],
    items: tuple[Mapping[str, Any], ...],
    assignments: list[Mapping[str, Any]],
    evidence_refs: tuple[str, ...],
) -> list[str]:
    blockers: list[str] = []
    if not windows:
        blockers.append("time_windows_missing")
    if not items:
        blockers.append("work_items_missing")
    if any(assignment["status"] != "assigned" for assignment in assignments):
        blockers.append("capacity_assignment_blocked")
    if not evidence_refs:
        blockers.append("evidence_refs_missing")
    return blockers


def _planning_summary(
    objective: str,
    assignments: list[Mapping[str, Any]],
    capacity_summary: list[Mapping[str, Any]],
) -> str:
    if not assignments:
        return f"Planning objective '{objective}' is awaiting operator-supplied work items."
    assigned_count = sum(1 for assignment in assignments if assignment["status"] == "assigned")
    blocked_count = len(assignments) - assigned_count
    remaining_total = sum(int(window["remaining_minutes"]) for window in capacity_summary)
    return (
        f"Schedule preview for '{objective}' assigns {assigned_count} item(s), blocks {blocked_count} item(s), "
        f"and leaves {remaining_total} minute(s) of operator-supplied capacity."
    )


def _planning_receipt(
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
        "inputs_used": ["objective", "operator_supplied_time_windows", "operator_supplied_work_items", "assumptions", "constraints"],
        "connectors_used": [],
        "decision": "blocked" if blocked else "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": ["schedule_plan_created", "capacity_projection_recorded", "assignment_preview_created", "receipt_created"],
        "actions_not_taken": list(_PLANNING_ACTIONS_NOT_TAKEN),
        "redactions": ["private_schedule_values_operator_supplied", "secret_values_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "no_connector_payload",
            "body_projection": "none",
        },
        "timestamp": generated_at,
        "evidence_refs": _evidence_refs(intent, evidence_refs, suffix),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/planning/{suffix}"],
        "outcome": "AwaitingEvidence" if blocked else "SolvedVerified",
        "metadata": {
            "planning_decision": plan["planning_decision"],
            "answer_claim_authority": plan["answer_claim_authority"],
            "blocking_reasons": list(plan["evidence_gate"]["blocking_reasons"]),
            "planning_execution_boundary": "preview_only",
            "live_connector_execution_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "invite_allowed": False,
            "message_person_allowed": False,
            "system_of_record_write_allowed": False,
            "connector_mutation_allowed": False,
            "external_submission_allowed": False,
            "public_post_allowed": False,
            "money_movement_allowed": False,
            "deployment_allowed": False,
            "memory_write_allowed": False,
            "public_readiness_claim_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
        },
    }


def _evidence_refs(intent: GovernedIntent, evidence_refs: tuple[str, ...], suffix: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in (*intent.evidence_refs, *evidence_refs):
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    refs.append(f"proof://personal-assistant/planning/{suffix}")
    return refs


def _bounded_window_tuple(
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
        normalized.append(MappingProxyType(_bounded_window(value, f"{field_name}[{index}]")))
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    return tuple(normalized)


def _bounded_window(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    unexpected = sorted(set(value) - _ALLOWED_WINDOW_FIELDS)
    if unexpected:
        raise PersonalAssistantInvariantError(f"{field_name}: unsupported time window fields {unexpected}")
    return {
        "window_ref": _require_text(value.get("window_ref"), f"{field_name}.window_ref"),
        "label": _require_text(value.get("label"), f"{field_name}.label"),
        "start": _require_text(value.get("start"), f"{field_name}.start"),
        "end": _require_text(value.get("end"), f"{field_name}.end"),
        "capacity_minutes": _bounded_int(value.get("capacity_minutes"), f"{field_name}.capacity_minutes", minimum=1, maximum=1440),
        "source_ref": _require_text(value.get("source_ref", "operator_supplied"), f"{field_name}.source_ref"),
        "notes": _optional_text(str(value.get("notes", "")), f"{field_name}.notes"),
    }


def _bounded_item_tuple(
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
        normalized.append(MappingProxyType(_bounded_item(value, f"{field_name}[{index}]")))
    if len(normalized) > max_items:
        raise PersonalAssistantInvariantError(f"{field_name} exceeds max_items={max_items}")
    return tuple(normalized)


def _bounded_item(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    unexpected = sorted(set(value) - _ALLOWED_ITEM_FIELDS)
    if unexpected:
        raise PersonalAssistantInvariantError(f"{field_name}: unsupported work item fields {unexpected}")
    return {
        "item_ref": _require_text(value.get("item_ref"), f"{field_name}.item_ref"),
        "title": _require_text(value.get("title"), f"{field_name}.title"),
        "estimated_minutes": _bounded_int(value.get("estimated_minutes"), f"{field_name}.estimated_minutes", minimum=1, maximum=1440),
        "priority": _bounded_int(value.get("priority", 3), f"{field_name}.priority", minimum=1, maximum=5),
        "earliest_start": _optional_text(str(value.get("earliest_start", "")), f"{field_name}.earliest_start"),
        "due": _optional_text(str(value.get("due", "")), f"{field_name}.due"),
        "required_window_ref": _optional_text(str(value.get("required_window_ref", "")), f"{field_name}.required_window_ref"),
        "source_ref": _require_text(value.get("source_ref", "operator_supplied"), f"{field_name}.source_ref"),
        "notes": _optional_text(str(value.get("notes", "")), f"{field_name}.notes"),
    }


def _bounded_int(value: Any, field_name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be an integer")
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise PersonalAssistantInvariantError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise PersonalAssistantInvariantError(f"{field_name} must be in [{minimum}, {maximum}]")
    return parsed


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
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "planning"
