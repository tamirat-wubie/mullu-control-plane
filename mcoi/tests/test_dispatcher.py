"""Purpose: verify validation-first execution dispatch for the MCOI runtime.
Governance scope: execution-slice tests only.
Dependencies: canonical execution contracts, executor-base typing, and the execution-slice dispatcher.
Invariants: dispatch validates before routing, rejects wrong routes explicitly, and returns typed execution results only.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.adapters.executor_base import ExecutionAdapterError, ExecutionFailure, ExecutionRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.dispatcher import DispatchRequest, Dispatcher
from mcoi_runtime.core.template_validator import TemplateValidator


@dataclass
class FakeExecutor:
    calls: int = 0
    last_request: ExecutionRequest | None = None
    should_fail: bool = False

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.last_request = request
        if self.should_fail:
            raise ExecutionAdapterError(
                ExecutionFailure(code="executor_failed", message="executor rejected request")
            )
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="process_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-03-18T12:00:00+00:00",
            finished_at="2026-03-18T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


def test_dispatcher_validates_before_executor_dispatch() -> None:
    executor = FakeExecutor()
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": executor},
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    result = dispatcher.dispatch(
        DispatchRequest(
            goal_id="goal-1",
            route="shell_command",
            template={
                "template_id": "template-1",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={},
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].details["code"] == "missing_parameter"
    assert executor.calls == 0
    assert executor.last_request is None


def test_dispatcher_routes_validated_templates_to_registered_executors() -> None:
    executor = FakeExecutor()
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": executor},
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    result = dispatcher.dispatch(
        DispatchRequest(
            goal_id="goal-2",
            route="shell_command",
            template={
                "template_id": "template-2",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
        )
    )

    assert result.status is ExecutionOutcome.SUCCEEDED
    assert executor.calls == 1
    assert executor.last_request is not None
    assert executor.last_request.argv == ("python", "-c", "print('hello')")


def test_dispatcher_rejects_wrong_adapter_routes_explicitly() -> None:
    executor = FakeExecutor()
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"filesystem_observe": executor},
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    result = dispatcher.dispatch(
        DispatchRequest(
            goal_id="goal-3",
            route="filesystem_observe",
            template={
                "template_id": "template-3",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
        )
    )

    assert result.status is ExecutionOutcome.FAILED
    assert result.actual_effects[0].details["code"] == "route_mismatch"
    assert result.actual_effects[0].details["details"]["route"] == "filesystem_observe"
    assert executor.calls == 0
