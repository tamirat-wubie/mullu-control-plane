"""Purpose: define the minimal execution adapter contract for the MCOI runtime.
Governance scope: execution-slice adapter typing only.
Dependencies: canonical execution contracts and runtime-core invariant helpers.
Invariants: adapters receive typed requests, return typed execution results, and expose failures explicitly without policy or state mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, freeze_mapping, stable_identifier


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: str
    goal_id: str
    argv: tuple[str, ...]
    cwd: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise RuntimeCoreInvariantError("execution_id must be a non-empty string")
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise RuntimeCoreInvariantError("goal_id must be a non-empty string")
        if not self.argv:
            raise RuntimeCoreInvariantError("argv must contain at least one item")
        for item in self.argv:
            if not isinstance(item, str) or not item.strip():
                raise RuntimeCoreInvariantError("argv items must be non-empty strings")
        if self.cwd is not None and (not isinstance(self.cwd, str) or not self.cwd.strip()):
            raise RuntimeCoreInvariantError("cwd must be a non-empty string when provided")
        environment = dict(self.environment)
        for key, value in environment.items():
            if not isinstance(key, str) or not key.strip():
                raise RuntimeCoreInvariantError("environment keys must be non-empty strings")
            if not isinstance(value, str):
                raise RuntimeCoreInvariantError("environment values must be strings")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise RuntimeCoreInvariantError("timeout_seconds must be greater than zero when provided")
        object.__setattr__(self, "environment", freeze_mapping(environment))


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise RuntimeCoreInvariantError("code must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise RuntimeCoreInvariantError("message must be a non-empty string")
        object.__setattr__(self, "details", freeze_mapping(dict(self.details)))


class ExecutionAdapterError(RuntimeError):
    def __init__(self, failure: ExecutionFailure) -> None:
        self.failure = failure
        super().__init__(f"{failure.code}: {failure.message}")


class ExecutorAdapter(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


def derive_execution_id(goal_id: str, route: str, template_id: str, bindings: Mapping[str, str]) -> str:
    return stable_identifier(
        "execution",
        {
            "goal_id": goal_id,
            "route": route,
            "template_id": template_id,
            "bindings": {key: bindings[key] for key in sorted(bindings)},
        },
    )


def build_execution_result(
    *,
    execution_id: str,
    goal_id: str,
    status: ExecutionOutcome,
    actual_effects: tuple[EffectRecord, ...],
    started_at: str,
    finished_at: str,
    metadata: Mapping[str, Any] | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        goal_id=goal_id,
        status=status,
        actual_effects=actual_effects,
        assumed_effects=(),
        started_at=started_at,
        finished_at=finished_at,
        metadata=dict(metadata or {}),
    )


def build_failure_result(
    *,
    execution_id: str,
    goal_id: str,
    started_at: str,
    finished_at: str,
    failure: ExecutionFailure,
    effect_name: str,
    status: ExecutionOutcome = ExecutionOutcome.FAILED,
    metadata: Mapping[str, Any] | None = None,
) -> ExecutionResult:
    return build_execution_result(
        execution_id=execution_id,
        goal_id=goal_id,
        status=status,
        actual_effects=(
            EffectRecord(
                name=effect_name,
                details={
                    "code": failure.code,
                    "message": failure.message,
                    "details": dict(failure.details),
                },
            ),
        ),
        started_at=started_at,
        finished_at=finished_at,
        metadata=metadata,
    )
