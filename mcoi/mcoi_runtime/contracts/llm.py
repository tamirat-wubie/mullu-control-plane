"""Purpose: LLM adapter contracts — governed invocation parameters and budget enforcement.
Governance scope: LLM adapter contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every LLM call is governed: budgeted, ledgered, scoped.
  - No raw API keys in contracts — secrets resolved at adapter boundary.
  - Cost limits are hard ceilings, never advisory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_float


class LLMProvider(StrEnum):
    """Supported LLM provider backends."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    STUB = "stub"


class LLMRole(StrEnum):
    """Message roles for chat-style invocations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class LLMMessage(ContractRecord):
    """Single message in a chat-style invocation."""

    role: LLMRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, LLMRole):
            raise ValueError("role must be an LLMRole value")
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")


@dataclass(frozen=True, slots=True)
class LLMInvocationParams(ContractRecord):
    """Typed parameters for a governed LLM invocation.

    All LLM calls flow through governance: budget checks, scope validation,
    and ledger recording happen before any API call is made.
    """

    model_name: str
    messages: tuple[LLMMessage, ...]
    max_tokens: int = 1024
    temperature: float = 0.0
    tenant_id: str = ""
    budget_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_name", require_non_empty_text(self.model_name, "model_name"))
        if not isinstance(self.messages, tuple) or len(self.messages) == 0:
            raise ValueError("messages must be a non-empty tuple of LLMMessage")
        for msg in self.messages:
            if not isinstance(msg, LLMMessage):
                raise ValueError("each message must be an LLMMessage")
        if not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if not isinstance(self.temperature, (int, float)) or self.temperature < 0.0:
            raise ValueError("temperature must be a non-negative number")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class LLMResult(ContractRecord):
    """Result of a governed LLM invocation.

    Contains the response content, token usage, and cost tracking.
    Model outputs remain bounded_external — never auto-trusted.
    """

    content: str
    input_tokens: int
    output_tokens: int
    cost: float
    model_name: str
    provider: LLMProvider
    finished: bool = True
    error: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        if not isinstance(self.input_tokens, int) or self.input_tokens < 0:
            raise ValueError("input_tokens must be a non-negative integer")
        if not isinstance(self.output_tokens, int) or self.output_tokens < 0:
            raise ValueError("output_tokens must be a non-negative integer")
        require_non_negative_float(self.cost, "cost")
        object.__setattr__(self, "model_name", require_non_empty_text(self.model_name, "model_name"))
        if not isinstance(self.provider, LLMProvider):
            raise ValueError("provider must be an LLMProvider value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def succeeded(self) -> bool:
        return self.finished and not self.error


@dataclass(frozen=True, slots=True)
class LLMBudget(ContractRecord):
    """Budget envelope for LLM cost control.

    Hard ceiling — once exhausted, invocations are rejected.
    """

    budget_id: str
    tenant_id: str
    max_cost: float
    spent: float = 0.0
    max_tokens_per_call: int = 4096
    max_calls: int = 1000
    calls_made: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "budget_id", require_non_empty_text(self.budget_id, "budget_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        require_non_negative_float(self.max_cost, "max_cost")
        require_non_negative_float(self.spent, "spent")
        if not isinstance(self.max_tokens_per_call, int) or self.max_tokens_per_call < 1:
            raise ValueError("max_tokens_per_call must be a positive integer")
        if not isinstance(self.max_calls, int) or self.max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        if not isinstance(self.calls_made, int) or self.calls_made < 0:
            raise ValueError("calls_made must be a non-negative integer")

    @property
    def remaining(self) -> float:
        return max(0.0, self.max_cost - self.spent)

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.max_cost or self.calls_made >= self.max_calls
