"""Purpose: model orchestration core — model registry, invocation routing, output validation.
Governance scope: model orchestration plane core logic only.
Dependencies: model contracts, invariant helpers.
Invariants:
  - Model outputs are bounded external inferences, never trusted directly.
  - Invocation requires prompt policy check (caller responsibility).
  - Output validation status gates downstream use.
  - Cost controls are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .provider_registry import ProviderRegistry


class ModelAdapter(Protocol):
    """Protocol for model-specific invocation adapters."""

    def invoke(self, invocation: ModelInvocation) -> ModelResponse: ...


class OutputValidator(Protocol):
    """Protocol for validating model output before downstream use."""

    def validate(self, response: ModelResponse) -> ValidationStatus: ...


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """Registered model with routing metadata."""

    model_id: str
    name: str
    provider: str
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    enabled: bool = True

    def __post_init__(self) -> None:
        for field_name in ("model_id", "name", "provider"):
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))
        if self.cost_per_input_token < 0:
            raise RuntimeCoreInvariantError("cost_per_input_token must be non-negative")
        if self.cost_per_output_token < 0:
            raise RuntimeCoreInvariantError("cost_per_output_token must be non-negative")


class ModelOrchestrationEngine:
    """Model registry, invocation routing, and output validation.

    This engine:
    - Maintains a typed model registry
    - Routes invocations to registered adapters
    - Validates model state before invocation
    - Applies output validation after invocation
    - Tracks cost estimates
    - Returns typed results — model outputs are NEVER trusted directly
    """

    def __init__(self, *, clock: Callable[[], str], provider_registry: ProviderRegistry | None = None) -> None:
        self._clock = clock
        self._models: dict[str, ModelDescriptor] = {}
        self._adapters: dict[str, ModelAdapter] = {}
        self._validators: dict[str, OutputValidator] = {}
        self._provider_registry = provider_registry
        self._model_provider_map: dict[str, str] = {}  # model_id -> provider_id

    def register(
        self,
        descriptor: ModelDescriptor,
        adapter: ModelAdapter,
        validator: OutputValidator | None = None,
        *,
        provider_id: str | None = None,
    ) -> ModelDescriptor:
        if descriptor.model_id in self._models:
            raise RuntimeCoreInvariantError(
                f"model already registered: {descriptor.model_id}"
            )
        self._models[descriptor.model_id] = descriptor
        self._adapters[descriptor.model_id] = adapter
        if validator is not None:
            self._validators[descriptor.model_id] = validator
        if provider_id is not None:
            self._model_provider_map[descriptor.model_id] = provider_id
        return descriptor

    def get_model(self, model_id: str) -> ModelDescriptor | None:
        ensure_non_empty_text("model_id", model_id)
        return self._models.get(model_id)

    def list_models(self, *, enabled_only: bool = False) -> tuple[ModelDescriptor, ...]:
        models = sorted(self._models.values(), key=lambda m: m.model_id)
        if enabled_only:
            models = [m for m in models if m.enabled]
        return tuple(models)

    def invoke(self, invocation: ModelInvocation) -> ModelResponse:
        """Invoke a registered model.

        Validates: model exists, model is enabled, provider is invocable,
        adapter is available. After invocation, updates provider health.
        """
        provider_id = self._model_provider_map.get(invocation.model_id)

        model = self._models.get(invocation.model_id)
        if model is None:
            return self._failure_response(invocation, error_status=ModelStatus.FAILED, validation=ValidationStatus.FAILED)

        if not model.enabled:
            return self._failure_response(invocation, error_status=ModelStatus.FAILED, validation=ValidationStatus.FAILED)

        # Provider registry check
        if self._provider_registry is not None and provider_id is not None:
            ok, reason = self._provider_registry.check_invocable(provider_id)
            if not ok:
                return self._failure_response(invocation, error_status=ModelStatus.FAILED, validation=ValidationStatus.FAILED)

        adapter = self._adapters.get(invocation.model_id)
        if adapter is None:
            return self._failure_response(invocation, error_status=ModelStatus.FAILED, validation=ValidationStatus.FAILED)

        try:
            response = adapter.invoke(invocation)
        except RuntimeCoreInvariantError:
            raise  # Invariant violations must propagate — never swallow governance errors
        except Exception as exc:
            if self._provider_registry is not None and provider_id is not None:
                self._provider_registry.record_failure(provider_id, f"adapter_exception:{type(exc).__name__}")
            return self._failure_response(
                invocation,
                error_status=ModelStatus.FAILED,
                validation=ValidationStatus.FAILED,
                failure_metadata={"exception_type": type(exc).__name__, "detail": str(exc)},
            )

        # Update provider health
        if self._provider_registry is not None and provider_id is not None:
            if response.status is ModelStatus.SUCCEEDED:
                self._provider_registry.record_success(provider_id)
            else:
                self._provider_registry.record_failure(provider_id, "model_invocation_failed")

        # Apply output validation if validator is registered
        validator = self._validators.get(invocation.model_id)
        if validator is not None and response.status is ModelStatus.SUCCEEDED:
            final_validation = validator.validate(response)
            if final_validation is not response.validation_status:
                # Re-create response with updated validation status
                response = ModelResponse(
                    response_id=response.response_id,
                    invocation_id=response.invocation_id,
                    status=response.status,
                    output_digest=response.output_digest,
                    completed_at=response.completed_at,
                    validation_status=final_validation,
                    output_tokens=response.output_tokens,
                    actual_cost=response.actual_cost,
                    metadata=response.metadata,
                )

        return response

    def _failure_response(
        self,
        invocation: ModelInvocation,
        *,
        error_status: ModelStatus,
        validation: ValidationStatus,
        failure_metadata: dict[str, str] | None = None,
    ) -> ModelResponse:
        response_id = stable_identifier("model-resp", {
            "invocation_id": invocation.invocation_id,
            "status": error_status.value,
        })
        return ModelResponse(
            response_id=response_id,
            invocation_id=invocation.invocation_id,
            status=error_status,
            output_digest="none",
            completed_at=self._clock(),
            validation_status=validation,
            metadata=failure_metadata or {},
        )
