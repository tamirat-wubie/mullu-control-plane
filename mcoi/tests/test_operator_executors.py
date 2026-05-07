"""Tests for governed operator executor failure redaction."""

from __future__ import annotations

from types import SimpleNamespace

from mcoi_runtime.adapters.executor_base import ExecutionAdapterError, ExecutionFailure
from mcoi_runtime.app.operator_executors import _GovernedStepExecutor
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.skill import SkillOutcomeStatus
from mcoi_runtime.core.template_validator import TemplateValidationError


class _ValidatorStub:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self._exc = exc

    def validate(self, template, bindings) -> None:
        if self._exc is not None:
            raise self._exc


class _DispatcherStub:
    def __init__(self, *, exc: Exception | None = None, result=None) -> None:
        self._exc = exc
        self._result = result or SimpleNamespace(
            status=ExecutionOutcome.SUCCEEDED,
            execution_id="exec-1",
        )

    def dispatch(self, request):
        if self._exc is not None:
            raise self._exc
        return self._result


def _runtime(*, validator_exc: Exception | None = None, dispatch_exc: Exception | None = None):
    return SimpleNamespace(
        template_validator=_ValidatorStub(exc=validator_exc),
        dispatcher=_DispatcherStub(exc=dispatch_exc),
        governed_dispatcher=None,
    )


class TestGovernedStepExecutorFailures:
    def test_governed_step_executor_bounds_validation_errors(self):
        runtime = _runtime(
            validator_exc=TemplateValidationError("missing_binding", "binding resolution failed: secret path"),
        )
        outcome = _GovernedStepExecutor(runtime=runtime).execute_step(
            step_id="step-1",
            action_type="shell_command",
            input_bindings={"msg": "hello"},
        )
        assert outcome.status is SkillOutcomeStatus.FAILED
        assert outcome.error_message == "validation:missing_binding:binding resolution failed"
        assert "secret path" not in outcome.error_message

    def test_governed_step_executor_bounds_adapter_failure_codes(self):
        runtime = _runtime(
            dispatch_exc=ExecutionAdapterError(
                ExecutionFailure(
                    code="executor_unavailable",
                    message="secret filesystem path C:\\hidden",
                )
            ),
        )
        outcome = _GovernedStepExecutor(runtime=runtime).execute_step(
            step_id="step-2",
            action_type="shell_command",
            input_bindings={"msg": "hello"},
        )
        assert outcome.status is SkillOutcomeStatus.FAILED
        assert outcome.error_message == "dispatch_error:executor_unavailable"
        assert "secret filesystem path" not in outcome.error_message

    def test_governed_step_executor_bounds_unexpected_dispatch_failures(self):
        runtime = _runtime(dispatch_exc=RuntimeError("secret dispatch token"))
        outcome = _GovernedStepExecutor(runtime=runtime).execute_step(
            step_id="step-3",
            action_type="shell_command",
            input_bindings={"msg": "hello"},
        )
        assert outcome.status is SkillOutcomeStatus.FAILED
        assert outcome.error_message == "dispatch_error:RuntimeError"
        assert "secret dispatch token" not in outcome.error_message
