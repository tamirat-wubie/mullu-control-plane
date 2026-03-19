"""Purpose: canonical model invocation and response contracts for the model orchestration plane.
Governance scope: model orchestration plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Model outputs are bounded external inferences, never trusted directly.
  - Every invocation produces a typed response.
  - Output validation status gates downstream use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class ModelStatus(StrEnum):
    """Outcome of a model invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ValidationStatus(StrEnum):
    """Whether the model output passed validation."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ModelInvocation(ContractRecord):
    """Record of a model invocation request.

    Maps to schemas/model_invocation.schema.json.
    """

    invocation_id: str
    model_id: str
    prompt_hash: str
    invoked_at: str
    input_tokens: int | None = None
    cost_estimate: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("invocation_id", "model_id", "prompt_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "invoked_at", require_datetime_text(self.invoked_at, "invoked_at"))
        if self.input_tokens is not None:
            if not isinstance(self.input_tokens, int) or self.input_tokens < 0:
                raise ValueError("input_tokens must be a non-negative integer")
        if self.cost_estimate is not None:
            if not isinstance(self.cost_estimate, (int, float)) or self.cost_estimate < 0:
                raise ValueError("cost_estimate must be a non-negative number")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ModelResponse(ContractRecord):
    """Record of a model invocation response.

    Maps to schemas/model_response.schema.json.
    Model outputs are bounded_external trust class — never promoted to trusted
    knowledge without passing the learning admission gate.
    """

    response_id: str
    invocation_id: str
    status: ModelStatus
    output_digest: str
    completed_at: str
    validation_status: ValidationStatus
    output_tokens: int | None = None
    actual_cost: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("response_id", "invocation_id", "output_digest"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, ModelStatus):
            raise ValueError("status must be a ModelStatus value")
        object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))
        if not isinstance(self.validation_status, ValidationStatus):
            raise ValueError("validation_status must be a ValidationStatus value")
        if self.output_tokens is not None:
            if not isinstance(self.output_tokens, int) or self.output_tokens < 0:
                raise ValueError("output_tokens must be a non-negative integer")
        if self.actual_cost is not None:
            if not isinstance(self.actual_cost, (int, float)) or self.actual_cost < 0:
                raise ValueError("actual_cost must be a non-negative number")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
