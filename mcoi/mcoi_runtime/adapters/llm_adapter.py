"""Phase 199A — Governed LLM Adapter.

Purpose: LLM invocation adapters for Anthropic and OpenAI, governed by budget,
    scope, and ledger enforcement. Implements the ModelAdapter protocol.
Governance scope: LLM adapter execution only.
Dependencies: LLM contracts, model contracts, core invariants.
Invariants:
  - Every invocation is budget-checked before API call.
  - Cost is tracked and ledgered after every call.
  - API keys are resolved from environment — never stored in contracts.
  - Model outputs are bounded_external — validation status starts PENDING.
  - Adapter failures produce typed error results, never raw exceptions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from typing import Any, Callable, Protocol

from mcoi_runtime.contracts.llm import (
    LLMBudget,
    LLMInvocationParams,
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
)
from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


def _classify_provider_exception(exc: Exception) -> str:
    """Collapse provider exceptions into stable, non-leaking error strings."""
    error_type = type(exc).__name__
    normalized_type = error_type.lower()
    if isinstance(exc, TimeoutError) or "timeout" in normalized_type:
        return f"provider timeout ({error_type})"
    if isinstance(exc, PermissionError) or any(
        token in normalized_type for token in ("auth", "permission", "forbidden", "unauthorized")
    ):
        return f"provider access error ({error_type})"
    if isinstance(exc, ConnectionError) or isinstance(exc, OSError) or any(
        token in normalized_type for token in ("connect", "network", "request", "transport", "socket", "http", "url")
    ):
        return f"provider network error ({error_type})"
    if isinstance(exc, ValueError):
        return f"provider validation error ({error_type})"
    return f"provider error ({error_type})"


def _classify_budget_rejection(reason: str) -> str:
    """Collapse budget-manager detail into stable public denial reasons."""
    if reason == "unknown budget" or reason.startswith("unknown budget:"):
        return "unknown budget"
    if reason == "budget exhausted" or reason.startswith("budget exhausted:"):
        return "budget exhausted"
    if reason == "budget limit exceeded" or reason.startswith("would exceed budget:"):
        return "budget limit exceeded"
    return "budget rejected"


class LLMBackend(Protocol):
    """Protocol for raw LLM API backends.

    Implementations call the actual provider API.
    The governed adapter wraps these with budget/ledger enforcement.
    """

    def call(self, params: LLMInvocationParams) -> LLMResult: ...

    @property
    def provider(self) -> LLMProvider: ...


# ═══ Budget Manager ═══


class LLMBudgetManager:
    """Manages LLM cost budgets with hard enforcement.

    Budget limits are ceilings, not advisories. Once exhausted,
    all further invocations for that budget_id are rejected.
    """

    def __init__(self) -> None:
        self._budgets: dict[str, LLMBudget] = {}

    def register(self, budget: LLMBudget) -> None:
        self._budgets[budget.budget_id] = budget

    def get(self, budget_id: str) -> LLMBudget | None:
        return self._budgets.get(budget_id)

    def check(self, budget_id: str, estimated_cost: float = 0.0) -> tuple[bool, str]:
        """Check if an invocation is within budget. Returns (allowed, reason)."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            return False, "unknown budget"
        if budget.exhausted:
            return False, "budget exhausted"
        if budget.spent + estimated_cost > budget.max_cost:
            return False, "budget limit exceeded"
        return True, "within_budget"

    def record_spend(self, budget_id: str, cost: float) -> LLMBudget:
        """Record spending against a budget. Returns updated budget."""
        budget = self._budgets.get(budget_id)
        if budget is None:
            raise RuntimeCoreInvariantError("cannot record spend for unknown budget")
        updated = LLMBudget(
            budget_id=budget.budget_id,
            tenant_id=budget.tenant_id,
            max_cost=budget.max_cost,
            spent=budget.spent + cost,
            max_tokens_per_call=budget.max_tokens_per_call,
            max_calls=budget.max_calls,
            calls_made=budget.calls_made + 1,
        )
        self._budgets[budget_id] = updated
        return updated

    def list_budgets(self) -> tuple[LLMBudget, ...]:
        return tuple(sorted(self._budgets.values(), key=lambda b: b.budget_id))


# ═══ Anthropic Backend ═══


class AnthropicBackend:
    """Anthropic API backend using the anthropic SDK.

    Resolves API key from ANTHROPIC_API_KEY env var.
    Falls back to dry-run mode if SDK not installed.
    """

    def __init__(self, *, api_key: str | None = None, default_model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._default_model = default_model
        self._client: Any = None
        self._sdk_available = importlib.util.find_spec("anthropic") is not None

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._sdk_available:
                raise RuntimeCoreInvariantError("anthropic SDK not installed — pip install anthropic")
            if not self._api_key:
                raise RuntimeCoreInvariantError("ANTHROPIC_API_KEY not set")
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def call(self, params: LLMInvocationParams) -> LLMResult:
        model = params.model_name or self._default_model

        # Build messages (separate system from user/assistant)
        system_content = ""
        messages: list[dict[str, str]] = []
        for msg in params.messages:
            if msg.role == LLMRole.SYSTEM:
                system_content = msg.content
            else:
                messages.append({"role": msg.role.value, "content": msg.content})

        if not messages:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=LLMProvider.ANTHROPIC,
                finished=True,
                error="no user/assistant messages provided",
            )

        try:
            client = self._get_client()
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": params.max_tokens,
                "messages": messages,
            }
            if system_content:
                kwargs["system"] = system_content
            if params.temperature > 0:
                kwargs["temperature"] = params.temperature

            response = client.messages.create(**kwargs)

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self._estimate_cost(model, input_tokens, output_tokens)

            return LLMResult(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                model_name=model,
                provider=LLMProvider.ANTHROPIC,
                finished=True,
            )

        except RuntimeCoreInvariantError:
            raise
        except Exception as exc:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=LLMProvider.ANTHROPIC,
                finished=False,
                error=_classify_provider_exception(exc),
            )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on known Anthropic pricing (per million tokens)."""
        pricing = {
            "claude-sonnet-4-20250514": (3.0, 15.0),
            "claude-haiku-4-5-20251001": (0.80, 4.0),
            "claude-opus-4-6": (15.0, 75.0),
        }
        input_rate, output_rate = pricing.get(model, (3.0, 15.0))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


# ═══ OpenAI Backend ═══


class OpenAIBackend:
    """OpenAI API backend using the openai SDK.

    Resolves API key from OPENAI_API_KEY env var.
    """

    def __init__(self, *, api_key: str | None = None, default_model: str = "gpt-4o") -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._default_model = default_model
        self._client: Any = None
        self._sdk_available = importlib.util.find_spec("openai") is not None

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._sdk_available:
                raise RuntimeCoreInvariantError("openai SDK not installed — pip install openai")
            if not self._api_key:
                raise RuntimeCoreInvariantError("OPENAI_API_KEY not set")
            import openai
            self._client = openai.OpenAI(api_key=self._api_key)
        return self._client

    def call(self, params: LLMInvocationParams) -> LLMResult:
        model = params.model_name or self._default_model

        messages: list[dict[str, str]] = []
        for msg in params.messages:
            messages.append({"role": msg.role.value, "content": msg.content})

        if not messages:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=LLMProvider.OPENAI,
                finished=True,
                error="no messages provided",
            )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
            )

            choice = response.choices[0]
            content = choice.message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            cost = self._estimate_cost(model, input_tokens, output_tokens)

            return LLMResult(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                model_name=model,
                provider=LLMProvider.OPENAI,
                finished=True,
            )

        except RuntimeCoreInvariantError:
            raise
        except Exception as exc:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=LLMProvider.OPENAI,
                finished=False,
                error=_classify_provider_exception(exc),
            )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on known OpenAI pricing (per million tokens)."""
        pricing = {
            "gpt-4o": (2.50, 10.0),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.0, 30.0),
        }
        input_rate, output_rate = pricing.get(model, (2.50, 10.0))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


# ═══ Gemini Backend (Tier 2 — hosted free-tier) ═══


class GeminiBackend:
    """Google Gemini API backend using the google-generativeai SDK.

    Tier 2 provider: cheap bulk inference, dev/testing, overflow fallback.
    Resolves API key from GEMINI_API_KEY env var.
    Falls back gracefully if SDK not installed.
    """

    def __init__(self, *, api_key: str | None = None, default_model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._default_model = default_model
        self._client: Any = None
        self._sdk_available = False
        try:
            import google.generativeai  # noqa: F401
            self._sdk_available = True
        except ImportError:
            pass

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GEMINI

    def _get_model(self, model_name: str) -> Any:
        if not self._sdk_available:
            raise RuntimeCoreInvariantError("google-generativeai SDK not installed — pip install google-generativeai")
        if not self._api_key:
            raise RuntimeCoreInvariantError("GEMINI_API_KEY not set")
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        return genai.GenerativeModel(model_name)

    def call(self, params: LLMInvocationParams) -> LLMResult:
        model_name = params.model_name or self._default_model

        # Build content from messages
        contents: list[dict[str, Any]] = []
        system_instruction = ""
        for msg in params.messages:
            if msg.role == LLMRole.SYSTEM:
                system_instruction = msg.content
            else:
                role = "model" if msg.role == LLMRole.ASSISTANT else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        if not contents:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.GEMINI,
                finished=True,
                error="no user/assistant messages provided",
            )

        try:
            model = self._get_model(model_name)
            gen_config: dict[str, Any] = {"max_output_tokens": params.max_tokens}
            if params.temperature > 0:
                gen_config["temperature"] = params.temperature

            response = model.generate_content(
                contents,
                generation_config=gen_config,
                **({"system_instruction": system_instruction} if system_instruction else {}),
            )

            content = response.text if hasattr(response, "text") else ""
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            cost = self._estimate_cost(model_name, input_tokens, output_tokens)

            return LLMResult(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                model_name=model_name,
                provider=LLMProvider.GEMINI,
                finished=True,
            )

        except RuntimeCoreInvariantError:
            raise
        except Exception as exc:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.GEMINI,
                finished=False,
                error=_classify_provider_exception(exc),
            )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on Gemini pricing (per million tokens).

        Flash models on the free tier are effectively zero cost.
        """
        pricing = {
            "gemini-2.0-flash": (0.10, 0.40),
            "gemini-2.0-flash-lite": (0.0, 0.0),
            "gemini-1.5-flash": (0.075, 0.30),
            "gemini-1.5-pro": (1.25, 5.0),
            "gemini-2.5-pro-preview-05-06": (1.25, 10.0),
        }
        input_rate, output_rate = pricing.get(model, (0.10, 0.40))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


# ═══ Ollama Backend (Tier 3 — local/private fallback) ═══


class OllamaBackend:
    """Ollama local model backend using the HTTP API.

    Tier 3 provider: private/internal workloads, offline fallback, local experiments.
    No SDK dependency — uses urllib for HTTP requests.
    Cost is always zero (local inference).
    """

    def __init__(self, *, base_url: str = "", default_model: str = "llama3.2") -> None:
        self._base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._default_model = default_model

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA

    def call(self, params: LLMInvocationParams) -> LLMResult:
        model_name = params.model_name or self._default_model

        messages: list[dict[str, str]] = []
        for msg in params.messages:
            messages.append({"role": msg.role.value, "content": msg.content})

        if not messages:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.OLLAMA,
                finished=True,
                error="no messages provided",
            )

        try:
            import json as _json
            import urllib.request
            import urllib.error

            payload = _json.dumps({
                "model": model_name,
                "messages": messages,
                "stream": False,
                **({"options": {"num_predict": params.max_tokens}} if params.max_tokens else {}),
                **({"options": {"temperature": params.temperature}} if params.temperature > 0 else {}),
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=60)
            data = _json.loads(resp.read())

            content = data.get("message", {}).get("content", "")
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)

            return LLMResult(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.OLLAMA,
                finished=True,
            )

        except Exception as exc:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model_name,
                provider=LLMProvider.OLLAMA,
                finished=False,
                error=_classify_provider_exception(exc),
            )


# ═══ Stub Backend (for testing without real API) ═══


class StubLLMBackend:
    """Deterministic LLM backend for testing.

    No real API calls. Returns predictable content based on input hash.
    """

    def __init__(self, *, response_prefix: str = "stub-llm-response") -> None:
        self._prefix = response_prefix
        self._call_count = 0

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.STUB

    @property
    def call_count(self) -> int:
        return self._call_count

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        content_hash = hashlib.sha256(
            "|".join(m.content for m in params.messages).encode()
        ).hexdigest()[:16]

        content = f"{self._prefix}:{content_hash}"
        # Simulate token usage proportional to message length
        total_chars = sum(len(m.content) for m in params.messages)
        input_tokens = max(1, total_chars // 4)
        output_tokens = max(1, len(content) // 4)

        return LLMResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=0.001 * (input_tokens + output_tokens) / 1000,
            model_name=params.model_name,
            provider=LLMProvider.STUB,
            finished=True,
        )


# ═══ Governed LLM Adapter ═══


class GovernedLLMAdapter:
    """Governed LLM adapter wrapping any LLMBackend with budget and ledger enforcement.

    This is the ModelAdapter-compatible wrapper that integrates with
    ModelOrchestrationEngine. It:
    1. Checks budget before invocation
    2. Calls the underlying backend
    3. Records cost against the budget
    4. Produces a ledger entry
    5. Returns a ModelResponse with PENDING validation status

    Model outputs are bounded_external — downstream validation required.
    """

    def __init__(
        self,
        *,
        backend: LLMBackend,
        budget_manager: LLMBudgetManager,
        clock: Callable[[], str],
        ledger_sink: Callable[[dict[str, Any]], None] | None = None,
        pii_scanner: Any | None = None,
        content_safety_chain: Any | None = None,
    ) -> None:
        self._backend = backend
        self._budget_manager = budget_manager
        self._clock = clock
        self._ledger_sink = ledger_sink
        self._pii_scanner = pii_scanner
        self._content_safety_chain = content_safety_chain
        self._invocations: list[dict[str, Any]] = []

    @property
    def invocation_count(self) -> int:
        return len(self._invocations)

    @property
    def total_cost(self) -> float:
        return sum(inv.get("cost", 0.0) for inv in self._invocations)

    def invoke_llm(self, params: LLMInvocationParams) -> LLMResult:
        """Governed LLM invocation — budget check → call → record → ledger.

        This is the high-level entry point for governed LLM calls.
        """
        # Budget gate
        if params.budget_id:
            allowed, reason = self._budget_manager.check(params.budget_id)
            if not allowed:
                return LLMResult(
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    model_name=params.model_name,
                    provider=self._backend.provider,
                    finished=False,
                    error=f"budget_rejected: {_classify_budget_rejection(reason)}",
                )

        # Content safety gate (pre-call)
        if self._content_safety_chain is not None:
            prompt_text = " ".join(
                m.content if hasattr(m, "content") else m.get("content", "") if isinstance(m, dict) else str(m)
                for m in params.messages
            )
            safety_result = self._content_safety_chain.evaluate(prompt_text)
            if safety_result.verdict.value == "blocked":
                return LLMResult(
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    model_name=params.model_name,
                    provider=self._backend.provider,
                    finished=False,
                    error="content_safety_blocked",
                )

        # Backend call
        result = self._backend.call(params)

        # Lambda_output_safety on output (post-call)
        if result.succeeded and result.content:
            from dataclasses import replace
            from mcoi_runtime.governance.guards.content_safety import evaluate_output_safety

            output_safety = evaluate_output_safety(
                result.content,
                chain=self._content_safety_chain,
                pii_scanner=self._pii_scanner,
            )
            if not output_safety.allowed:
                result = replace(result, content="", error=output_safety.reason)
            elif output_safety.content != result.content:
                result = replace(result, content=output_safety.content)

        # Record cost
        if params.budget_id and result.succeeded:
            self._budget_manager.record_spend(params.budget_id, result.cost)

        # Ledger entry
        record = {
            "type": "llm_invocation",
            "model": params.model_name,
            "provider": self._backend.provider.value,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost": result.cost,
            "succeeded": result.succeeded,
            "budget_id": params.budget_id,
            "tenant_id": params.tenant_id,
            "at": self._clock(),
        }
        self._invocations.append(record)
        if self._ledger_sink is not None:
            self._ledger_sink(record)

        return result

    def invoke(self, invocation: ModelInvocation) -> ModelResponse:
        """ModelAdapter protocol compliance — adapts ModelInvocation to LLM call.

        Extracts prompt from metadata, builds LLMInvocationParams, calls invoke_llm,
        and wraps result as ModelResponse.
        """
        # Extract LLM params from invocation metadata
        messages_raw = invocation.metadata.get("messages", ())
        model_name = invocation.metadata.get("model_name", invocation.model_id)
        max_tokens = invocation.metadata.get("max_tokens", 1024)
        temperature = invocation.metadata.get("temperature", 0.0)
        budget_id = invocation.metadata.get("budget_id", "")
        tenant_id = invocation.metadata.get("tenant_id", "")

        # Build LLM messages
        llm_messages: list[LLMMessage] = []
        for msg_data in messages_raw:
            if isinstance(msg_data, LLMMessage):
                llm_messages.append(msg_data)
            elif isinstance(msg_data, dict):
                llm_messages.append(LLMMessage(
                    role=LLMRole(msg_data.get("role", "user")),
                    content=msg_data.get("content", ""),
                ))

        if not llm_messages:
            # Fallback: use prompt_hash as the user message
            llm_messages.append(LLMMessage(role=LLMRole.USER, content=invocation.prompt_hash))

        params = LLMInvocationParams(
            model_name=model_name,
            messages=tuple(llm_messages),
            max_tokens=max_tokens,
            temperature=temperature,
            tenant_id=tenant_id,
            budget_id=budget_id,
        )

        result = self.invoke_llm(params)

        # Build ModelResponse
        output_digest = hashlib.sha256(result.content.encode("utf-8")).hexdigest()
        response_id = stable_identifier("llm-resp", {
            "invocation_id": invocation.invocation_id,
            "model": model_name,
        })

        status = ModelStatus.SUCCEEDED if result.succeeded else ModelStatus.FAILED

        return ModelResponse(
            response_id=response_id,
            invocation_id=invocation.invocation_id,
            status=status,
            output_digest=output_digest,
            completed_at=self._clock(),
            validation_status=ValidationStatus.PENDING,
            output_tokens=result.output_tokens,
            actual_cost=result.cost,
            metadata={
                "content": result.content,
                "input_tokens": result.input_tokens,
                "provider": result.provider.value,
                "error": result.error,
            },
        )
