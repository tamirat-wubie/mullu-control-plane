"""Purpose: validate templates and dispatch them to the correct execution adapter.
Governance scope: execution-slice dispatch only.
Dependencies: template validation, executor-base typing, and canonical execution contracts.
Invariants: validation precedes dispatch, routing is explicit, and dispatcher stays free of policy, planning, replay, and state merge logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.execution import ExecutionResult

from mcoi_runtime.adapters.executor_base import (
    ExecutionAdapterError,
    ExecutionFailure,
    ExecutionRequest,
    ExecutorAdapter,
    build_failure_result,
    derive_execution_id,
    utc_now_text,
)

from .template_validator import TemplateValidationError, TemplateValidator


@dataclass(frozen=True, slots=True)
class DispatchRequest:
    goal_id: str
    route: str
    template: Mapping[str, Any]
    bindings: Mapping[str, str]


@dataclass(slots=True)
class Dispatcher:
    template_validator: TemplateValidator
    executors: Mapping[str, ExecutorAdapter] = field(default_factory=dict)
    clock: Callable[[], str] = field(default=utc_now_text)

    def dispatch(self, request: DispatchRequest) -> ExecutionResult:
        started_at = self.clock()
        template_id = request.template.get("template_id", "unknown") if isinstance(request.template, Mapping) else "unknown"
        safe_bindings = (
            request.bindings
            if isinstance(request.bindings, Mapping)
            and all(isinstance(key, str) and isinstance(value, str) for key, value in request.bindings.items())
            else {}
        )
        execution_id = derive_execution_id(request.goal_id, request.route, str(template_id), safe_bindings)

        try:
            validated_template = self.template_validator.validate(request.template, request.bindings)
        except TemplateValidationError as exc:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(code=exc.code, message=str(exc)),
                effect_name="validation_rejected",
                metadata={"route": request.route},
            )

        if request.route != validated_template.action_type.value:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="route_mismatch",
                    message="dispatch route does not match validated action type",
                    details={
                        "route": request.route,
                        "action_type": validated_template.action_type.value,
                    },
                ),
                effect_name="dispatch_rejected",
                metadata={"route": request.route},
            )

        executor = self.executors.get(request.route)
        if executor is None:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=ExecutionFailure(
                    code="route_not_found",
                    message="no executor is registered for the requested route",
                    details={"route": request.route},
                ),
                effect_name="dispatch_rejected",
                metadata={"route": request.route},
            )

        execution_request = ExecutionRequest(
            execution_id=execution_id,
            goal_id=request.goal_id,
            argv=validated_template.command_argv,
            cwd=validated_template.cwd,
            environment=validated_template.environment,
            timeout_seconds=validated_template.timeout_seconds,
        )

        try:
            return executor.execute(execution_request)
        except ExecutionAdapterError as exc:
            finished_at = self.clock()
            return build_failure_result(
                execution_id=execution_id,
                goal_id=request.goal_id,
                started_at=started_at,
                finished_at=finished_at,
                failure=exc.failure,
                effect_name="adapter_failed",
                metadata={"route": request.route},
            )
