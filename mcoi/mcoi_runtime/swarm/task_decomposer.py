"""Task decomposer for governed swarm goals.

Purpose: turn explicit goal task specs into typed swarm tasks without adding
implicit authority.
Governance scope: OCE, RAG, and CDCV across goal-to-task transitions.
Dependencies: swarm contracts.
Invariants: every task is caused by a goal spec and side effects remain denied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import SwarmGoal, SwarmInvariantViolation, SwarmTask, SwarmTaskRisk

_TASK_SPEC_FIELDS = frozenset(
    {
        "task_id",
        "required_role",
        "required_capabilities",
        "input_refs",
        "expected_output",
        "risk",
        "deadline",
        "side_effects_allowed",
        "requires_receipt",
    }
)


class TaskDecomposer:
    """Compile explicit task specifications into auditable tasks."""

    def decompose(self, goal: SwarmGoal) -> tuple[SwarmTask, ...]:
        """Return deterministic task objects for a goal."""

        tasks: list[SwarmTask] = []
        for index, spec in enumerate(goal.task_specs, start=1):
            _reject_unsupported_fields(spec)
            task_id = _optional_text(spec, "task_id") or f"{goal.goal_id}_task_{index:03d}"
            required_role = _required_text(spec, "required_role")
            required_capabilities = _text_sequence(spec, "required_capabilities", default=())
            input_refs = _text_sequence(spec, "input_refs", default=())
            expected_output = _required_text(spec, "expected_output")
            risk = _task_risk(spec)
            deadline = _optional_text(spec, "deadline")
            side_effects_allowed = _optional_bool(spec, "side_effects_allowed", default=False)
            if side_effects_allowed:
                raise SwarmInvariantViolation("task decomposition cannot grant side effects")
            tasks.append(
                SwarmTask(
                    task_id=task_id,
                    goal_id=goal.goal_id,
                    tenant_id=goal.tenant_id,
                    required_role=required_role,
                    required_capabilities=required_capabilities,
                    input_refs=input_refs,
                    expected_output=expected_output,
                    risk=risk,
                    deadline=deadline,
                    requires_receipt=_optional_bool(spec, "requires_receipt", default=True),
                    side_effects_allowed=False,
                )
            )
        return tuple(tasks)


def _reject_unsupported_fields(spec: Mapping[str, object]) -> None:
    unsupported = tuple(sorted(set(spec).difference(_TASK_SPEC_FIELDS)))
    if unsupported:
        raise SwarmInvariantViolation(f"unsupported task spec field: {unsupported[0]}")


def _required_text(spec: Mapping[str, object], field_name: str) -> str:
    if field_name not in spec:
        raise SwarmInvariantViolation(f"{field_name} must be present")
    return _text_value(spec[field_name], field_name)


def _optional_text(spec: Mapping[str, object], field_name: str) -> str | None:
    if field_name not in spec or spec[field_name] is None:
        return None
    return _text_value(spec[field_name], field_name)


def _text_value(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise SwarmInvariantViolation(f"{field_name} must be a string")
    return value


def _text_sequence(
    spec: Mapping[str, object],
    field_name: str,
    *,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if field_name not in spec:
        return default
    value = spec[field_name]
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SwarmInvariantViolation(f"{field_name} must be a sequence of strings")
    values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SwarmInvariantViolation(f"{field_name}[{index}] must be a string")
        values.append(item)
    return tuple(values)


def _optional_bool(spec: Mapping[str, object], field_name: str, *, default: bool) -> bool:
    if field_name not in spec:
        return default
    value = spec[field_name]
    if not isinstance(value, bool):
        raise SwarmInvariantViolation(f"{field_name} must be a boolean")
    return value


def _task_risk(spec: Mapping[str, object]) -> SwarmTaskRisk:
    value = spec.get("risk", SwarmTaskRisk.LOW.value)
    if isinstance(value, SwarmTaskRisk):
        return value
    if not isinstance(value, str):
        raise SwarmInvariantViolation("risk must be a string")
    try:
        return SwarmTaskRisk(value)
    except ValueError as exc:
        raise SwarmInvariantViolation(f"risk must be one of: {', '.join(risk.value for risk in SwarmTaskRisk)}") from exc
