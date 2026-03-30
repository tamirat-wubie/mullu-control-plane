"""Phase 199A — LLM Integration Bridge.

Purpose: Connects governed LLM adapters to the production surface, dispatcher,
    and ledger. Provides high-level LLM operations for the operator loop.
Governance scope: LLM integration wiring only.
Dependencies: llm_adapter, production_surface, model_orchestration.
Invariants:
  - All LLM calls flow through governance (budget + ledger).
  - Integration never bypasses budget enforcement.
  - Ledger entries are mandatory for every invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.contracts.llm import (
    LLMBudget,
    LLMInvocationParams,
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
)
from mcoi_runtime.adapters.llm_adapter import (
    GovernedLLMAdapter,
    LLMBackend,
    LLMBudgetManager,
    StubLLMBackend,
)


@dataclass(frozen=True, slots=True)
class LLMInvocationRecord:
    """Immutable record of a governed LLM invocation for ledger/audit."""

    invocation_id: str
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost: float
    succeeded: bool
    budget_id: str
    tenant_id: str
    timestamp: str


class LLMIntegrationBridge:
    """Bridges LLM adapters to the governed platform.

    Provides:
    - Governed prompt completion (budget-checked, ledgered)
    - Multi-provider routing (Anthropic, OpenAI, stub)
    - Budget management and reporting
    - Invocation history for audit
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        default_backend: LLMBackend | None = None,
        ledger_sink: Callable[[dict[str, Any]], None] | None = None,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self._clock = clock
        self._budget_manager = budget_manager or LLMBudgetManager()
        self._backends: dict[str, LLMBackend] = {}
        self._adapters: dict[str, GovernedLLMAdapter] = {}
        self._invocation_records: list[LLMInvocationRecord] = []
        self._ledger_sink = ledger_sink

        # Register default backend
        if default_backend is not None:
            self.register_backend("default", default_backend)

    def register_backend(self, name: str, backend: LLMBackend) -> None:
        """Register a named LLM backend (anthropic, openai, stub, etc.)."""
        self._backends[name] = backend
        self._adapters[name] = GovernedLLMAdapter(
            backend=backend,
            budget_manager=self._budget_manager,
            clock=self._clock,
            ledger_sink=self._ledger_sink,
        )

    def register_budget(self, budget: LLMBudget) -> None:
        """Register a cost budget for LLM invocations."""
        self._budget_manager.register(budget)

    def complete(
        self,
        prompt: str,
        *,
        model_name: str = "claude-sonnet-4-20250514",
        backend_name: str = "default",
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tenant_id: str = "",
        budget_id: str = "",
    ) -> LLMResult:
        """High-level governed completion — the primary LLM entry point.

        Builds messages, enforces budget, calls backend, records to ledger.
        """
        adapter = self._adapters.get(backend_name)
        if adapter is None:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.STUB,
                finished=False,
                error=f"unknown backend: {backend_name}",
            )

        messages: list[LLMMessage] = []
        if system:
            messages.append(LLMMessage(role=LLMRole.SYSTEM, content=system))
        messages.append(LLMMessage(role=LLMRole.USER, content=prompt))

        params = LLMInvocationParams(
            model_name=model_name,
            messages=tuple(messages),
            max_tokens=max_tokens,
            temperature=temperature,
            tenant_id=tenant_id,
            budget_id=budget_id,
        )

        result = adapter.invoke_llm(params)

        # Record for audit
        record = LLMInvocationRecord(
            invocation_id=f"llm-{len(self._invocation_records) + 1}",
            model_name=model_name,
            provider=adapter._backend.provider.value,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=result.cost,
            succeeded=result.succeeded,
            budget_id=budget_id,
            tenant_id=tenant_id,
            timestamp=self._clock(),
        )
        self._invocation_records.append(record)

        return result

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model_name: str = "claude-sonnet-4-20250514",
        backend_name: str = "default",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        tenant_id: str = "",
        budget_id: str = "",
    ) -> LLMResult:
        """Multi-turn chat completion — governed, budgeted, ledgered."""
        adapter = self._adapters.get(backend_name)
        if adapter is None:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.STUB,
                finished=False,
                error=f"unknown backend: {backend_name}",
            )

        llm_messages = tuple(
            LLMMessage(role=LLMRole(m["role"]), content=m["content"])
            for m in messages
        )

        params = LLMInvocationParams(
            model_name=model_name,
            messages=llm_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tenant_id=tenant_id,
            budget_id=budget_id,
        )

        return adapter.invoke_llm(params)

    # ═══ Reporting ═══

    @property
    def invocation_count(self) -> int:
        return len(self._invocation_records)

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self._invocation_records)

    def budget_summary(self) -> dict[str, Any]:
        """Budget status for all registered budgets."""
        budgets = self._budget_manager.list_budgets()
        return {
            "budgets": [
                {
                    "budget_id": b.budget_id,
                    "tenant_id": b.tenant_id,
                    "max_cost": b.max_cost,
                    "spent": b.spent,
                    "remaining": b.remaining,
                    "calls_made": b.calls_made,
                    "max_calls": b.max_calls,
                    "exhausted": b.exhausted,
                }
                for b in budgets
            ],
            "total_spent": sum(b.spent for b in budgets),
        }

    def invocation_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent invocation records for audit."""
        records = self._invocation_records[-limit:]
        return [
            {
                "id": r.invocation_id,
                "model": r.model_name,
                "provider": r.provider,
                "tokens": r.input_tokens + r.output_tokens,
                "cost": r.cost,
                "succeeded": r.succeeded,
                "at": r.timestamp,
            }
            for r in records
        ]
