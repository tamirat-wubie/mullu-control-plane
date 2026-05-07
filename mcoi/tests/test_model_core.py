"""Purpose: verify model orchestration engine — model registry, routing, output validation.
Governance scope: model orchestration core tests only.
Dependencies: model orchestration engine, contracts.
Invariants: model outputs are bounded external; validation gates downstream use.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.model_orchestration import (
    ModelDescriptor,
    ModelOrchestrationEngine,
)


_CLOCK = "2026-03-19T00:00:00+00:00"


class FakeModelAdapter:
    def __init__(self, output_digest: str = "out-digest") -> None:
        self._digest = output_digest
        self.invoked: list[ModelInvocation] = []

    def invoke(self, invocation: ModelInvocation) -> ModelResponse:
        self.invoked.append(invocation)
        return ModelResponse(
            response_id=stable_identifier("resp", {"inv": invocation.invocation_id}),
            invocation_id=invocation.invocation_id,
            status=ModelStatus.SUCCEEDED,
            output_digest=self._digest,
            completed_at=_CLOCK,
            validation_status=ValidationStatus.PENDING,
            output_tokens=42,
        )


class AlwaysPassValidator:
    def validate(self, response: ModelResponse) -> ValidationStatus:
        return ValidationStatus.PASSED


class AlwaysFailValidator:
    def validate(self, response: ModelResponse) -> ValidationStatus:
        return ValidationStatus.FAILED


def _descriptor(model_id: str = "model-1", enabled: bool = True) -> ModelDescriptor:
    return ModelDescriptor(
        model_id=model_id,
        name="Test Model",
        provider="test-provider",
        enabled=enabled,
    )


def _invocation(model_id: str = "model-1") -> ModelInvocation:
    return ModelInvocation(
        invocation_id="inv-1",
        model_id=model_id,
        prompt_hash="prompt-hash-1",
        invoked_at=_CLOCK,
    )


def test_register_and_invoke() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    adapter = FakeModelAdapter()
    engine.register(_descriptor(), adapter)

    response = engine.invoke(_invocation())

    assert response.status is ModelStatus.SUCCEEDED
    assert len(adapter.invoked) == 1


def test_invoke_unregistered_model_fails() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)

    response = engine.invoke(_invocation("nonexistent"))

    assert response.status is ModelStatus.FAILED
    assert response.validation_status is ValidationStatus.FAILED


def test_invoke_disabled_model_fails() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(enabled=False), FakeModelAdapter())

    response = engine.invoke(_invocation())

    assert response.status is ModelStatus.FAILED


def test_output_validation_applied() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeModelAdapter(), validator=AlwaysPassValidator())

    response = engine.invoke(_invocation())

    assert response.validation_status is ValidationStatus.PASSED


def test_output_validation_fails() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeModelAdapter(), validator=AlwaysFailValidator())

    response = engine.invoke(_invocation())

    assert response.status is ModelStatus.SUCCEEDED
    assert response.validation_status is ValidationStatus.FAILED


def test_no_validator_preserves_adapter_status() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeModelAdapter())

    response = engine.invoke(_invocation())

    assert response.validation_status is ValidationStatus.PENDING


def test_duplicate_registration_rejected() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeModelAdapter())

    with pytest.raises(
        RuntimeCoreInvariantError,
        match="^model already registered$",
    ) as exc_info:
        engine.register(_descriptor(), FakeModelAdapter())
    assert "m-1" not in str(exc_info.value)


def test_list_models() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("m-a"), FakeModelAdapter())
    engine.register(_descriptor("m-b", enabled=False), FakeModelAdapter())

    assert len(engine.list_models()) == 2
    assert len(engine.list_models(enabled_only=True)) == 1


def test_get_model() -> None:
    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("m-1"), FakeModelAdapter())

    assert engine.get_model("m-1") is not None
    assert engine.get_model("nonexistent") is None


def test_adapter_exception_is_sanitized() -> None:
    class FailingAdapter:
        def invoke(self, invocation: ModelInvocation) -> ModelResponse:
            raise RuntimeError("secret provider detail")

    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FailingAdapter())

    response = engine.invoke(_invocation())

    assert response.status is ModelStatus.FAILED
    assert response.validation_status is ValidationStatus.FAILED
    assert response.metadata["exception_type"] == "RuntimeError"
    assert response.metadata["detail"] == "model adapter error (RuntimeError)"
    assert "secret provider detail" not in response.metadata["detail"]
