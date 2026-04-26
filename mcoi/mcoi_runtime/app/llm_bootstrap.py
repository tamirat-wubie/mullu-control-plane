"""Phase 200A - LLM Bootstrap Wiring.

Purpose: Wire LLM backends into the runtime based on environment configuration.
    Registers model adapters with ModelOrchestrationEngine and provider registry.
Governance scope: LLM wiring at bootstrap time only.
Dependencies: llm_adapter, llm_integration, model_orchestration, provider_registry.
Invariants:
  - Backend selection is explicit and environment-driven.
  - No API calls at bootstrap time - adapters are created but not invoked.
  - Stub backend is always available as fallback.
  - Budget registration is explicit - no implicit spending authority.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.adapters.llm_adapter import (
    AnthropicBackend,
    GeminiBackend,
    GovernedLLMAdapter,
    LLMBackend,
    LLMBudgetManager,
    OllamaBackend,
    OpenAIBackend,
    StubLLMBackend,
)
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.core.model_orchestration import (
    ModelAlreadyRegisteredError,
    ModelDescriptor,
    ModelOrchestrationEngine,
)
from mcoi_runtime.core.provider_registry import ProviderRegistry


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """Environment-driven LLM configuration."""

    default_backend: str = "stub"  # "anthropic", "openai", "gemini", "ollama", "stub"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    default_budget_max_cost: float = 100.0
    default_budget_max_calls: int = 10000
    max_tokens_per_call: int = 4096

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Build LLM config from environment variables.

        Fail-closed in pilot/production environments: refuses to boot with
        the stub backend (which produces deterministic fake responses).
        """
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
        env = os.environ.get("MULLU_ENV", "").lower()

        # Auto-detect default backend from available keys (Tier 1 first)
        default_backend = os.environ.get("MULLU_LLM_BACKEND", "")
        if not default_backend:
            if anthropic_key:
                default_backend = "anthropic"
            elif openai_key:
                default_backend = "openai"
            elif gemini_key:
                default_backend = "gemini"
            elif ollama_url:
                default_backend = "ollama"
            else:
                default_backend = "stub"

        # Fail-closed: stub backend is forbidden in pilot/production.
        # The stub returns deterministic fake responses suitable only
        # for testing — running it under a "production" label is a
        # silent governance failure (audit trail records "real" calls
        # that never happened).
        if default_backend == "stub" and env in ("pilot", "production"):
            raise RuntimeError(
                f"MULLU_LLM_BACKEND='stub' is forbidden in {env!r} environment. "
                "Set MULLU_LLM_BACKEND explicitly or provide an API key "
                "(ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY) "
                "or OLLAMA_BASE_URL."
            )

        return cls(
            default_backend=default_backend,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            gemini_api_key=gemini_key,
            ollama_base_url=ollama_url,
            default_model=os.environ.get("MULLU_LLM_MODEL", "claude-sonnet-4-20250514"),
            default_budget_max_cost=float(os.environ.get("MULLU_LLM_BUDGET_MAX_COST", "100.0")),
            default_budget_max_calls=int(os.environ.get("MULLU_LLM_BUDGET_MAX_CALLS", "10000")),
            max_tokens_per_call=int(os.environ.get("MULLU_LLM_MAX_TOKENS", "4096")),
        )


@dataclass
class LLMBootstrapResult:
    """Result of LLM bootstrap wiring."""

    bridge: LLMIntegrationBridge
    budget_manager: LLMBudgetManager
    backends: dict[str, LLMBackend]
    default_backend_name: str
    config: LLMConfig
    registered_models: list[str] = field(default_factory=list)
    registered_providers: list[str] = field(default_factory=list)
    skipped_model_registrations: list[dict[str, str]] = field(default_factory=list)
    model_registration_failures: list[dict[str, str]] = field(default_factory=list)


def _classify_bootstrap_exception(exc: Exception) -> str:
    """Return a bounded bootstrap wiring failure detail."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"model registration timeout ({exc_type})"
    return f"model registration error ({exc_type})"


def bootstrap_llm(
    *,
    clock: Callable[[], str],
    config: LLMConfig | None = None,
    provider_registry: ProviderRegistry | None = None,
    model_engine: ModelOrchestrationEngine | None = None,
    ledger_sink: Callable[[dict[str, Any]], None] | None = None,
) -> LLMBootstrapResult:
    """Wire LLM backends into the runtime.

    1. Creates backends based on config (env-driven)
    2. Registers backends with LLMIntegrationBridge
    3. Registers providers with ProviderRegistry (if provided)
    4. Registers models with ModelOrchestrationEngine (if provided)
    5. Sets up default budget

    No API calls are made at bootstrap time.
    """
    llm_config = config or LLMConfig.from_env()
    budget_manager = LLMBudgetManager()
    backends: dict[str, LLMBackend] = {}

    # Always register stub backend
    stub = StubLLMBackend()
    backends["stub"] = stub

    # Register Anthropic backend if key available
    if llm_config.anthropic_api_key:
        anthropic = AnthropicBackend(
            api_key=llm_config.anthropic_api_key,
            default_model=llm_config.default_model if "claude" in llm_config.default_model else "claude-sonnet-4-20250514",
        )
        backends["anthropic"] = anthropic

    # Register OpenAI backend if key available
    if llm_config.openai_api_key:
        openai = OpenAIBackend(
            api_key=llm_config.openai_api_key,
            default_model=llm_config.default_model if "gpt" in llm_config.default_model else "gpt-4o",
        )
        backends["openai"] = openai

    # Register Gemini backend if key available (Tier 2)
    if llm_config.gemini_api_key:
        gemini = GeminiBackend(
            api_key=llm_config.gemini_api_key,
            default_model=llm_config.default_model if "gemini" in llm_config.default_model else "gemini-2.0-flash",
        )
        backends["gemini"] = gemini

    # Register Ollama backend if URL configured (Tier 3)
    if llm_config.ollama_base_url:
        ollama = OllamaBackend(
            base_url=llm_config.ollama_base_url,
            default_model=llm_config.default_model if llm_config.default_backend == "ollama" else "llama3.2",
        )
        backends["ollama"] = ollama

    # Determine default backend
    default_name = llm_config.default_backend
    if default_name not in backends:
        default_name = "stub"

    # Create bridge with default backend and shared budget manager
    bridge = LLMIntegrationBridge(
        clock=clock,
        default_backend=backends[default_name],
        ledger_sink=ledger_sink,
        budget_manager=budget_manager,
    )

    # Register all other backends
    for name, backend in backends.items():
        if name != default_name:
            bridge.register_backend(name, backend)

    # Register default budget
    default_budget = LLMBudget(
        budget_id="default",
        tenant_id="system",
        max_cost=llm_config.default_budget_max_cost,
        max_calls=llm_config.default_budget_max_calls,
        max_tokens_per_call=llm_config.max_tokens_per_call,
    )
    bridge.register_budget(default_budget)

    result = LLMBootstrapResult(
        bridge=bridge,
        budget_manager=budget_manager,
        backends=backends,
        default_backend_name=default_name,
        config=llm_config,
    )

    # Register with provider registry if available
    if provider_registry is not None:
        _register_providers(provider_registry, backends, llm_config, result)

    # Register with model orchestration engine if available
    if model_engine is not None:
        _register_models(model_engine, backends, budget_manager, clock, llm_config, result)

    return result


def _register_providers(
    registry: ProviderRegistry,
    backends: dict[str, LLMBackend],
    config: LLMConfig,
    result: LLMBootstrapResult,
) -> None:
    """Register LLM backends as providers in the provider registry."""
    provider_configs = {
        "anthropic": {
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com",
            "rate_limit": 60,
            "cost_limit": 1.0,
        },
        "openai": {
            "name": "OpenAI",
            "base_url": "https://api.openai.com",
            "rate_limit": 60,
            "cost_limit": 1.0,
        },
        "stub": {
            "name": "Stub LLM",
            "base_url": "local://stub",
            "rate_limit": 1000,
            "cost_limit": 0.01,
        },
    }

    for backend_name in backends:
        pconf = provider_configs.get(backend_name, provider_configs["stub"])
        provider_id = f"llm-{backend_name}"

        scope = CredentialScope(
            scope_id=f"scope-{backend_name}",
            provider_id=provider_id,
            allowed_base_urls=(pconf["base_url"],),
            allowed_operations=("messages.create", "chat.completions.create"),
            rate_limit_per_minute=pconf["rate_limit"],
            cost_limit_per_invocation=pconf["cost_limit"],
        )

        descriptor = ProviderDescriptor(
            provider_id=provider_id,
            name=pconf["name"],
            provider_class=ProviderClass.MODEL,
            credential_scope_id=scope.scope_id,
            enabled=True,
            base_url=pconf["base_url"],
        )

        registry.register(descriptor, scope)
        result.registered_providers.append(provider_id)


def _register_models(
    engine: ModelOrchestrationEngine,
    backends: dict[str, LLMBackend],
    budget_manager: LLMBudgetManager,
    clock: Callable[[], str],
    config: LLMConfig,
    result: LLMBootstrapResult,
) -> None:
    """Register LLM models with ModelOrchestrationEngine."""
    model_definitions = [
        # Anthropic models
        ("claude-sonnet-4-20250514", "Claude Sonnet 4", "anthropic", 3.0, 15.0),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "anthropic", 0.80, 4.0),
        ("claude-opus-4-6", "Claude Opus 4.6", "anthropic", 15.0, 75.0),
        # OpenAI models
        ("gpt-4o", "GPT-4o", "openai", 2.50, 10.0),
        ("gpt-4o-mini", "GPT-4o Mini", "openai", 0.15, 0.60),
    ]

    for model_id, name, provider_name, input_cost, output_cost in model_definitions:
        if provider_name not in backends:
            continue  # Skip models whose backend isn't available

        descriptor = ModelDescriptor(
            model_id=model_id,
            name=name,
            provider=provider_name,
            cost_per_input_token=input_cost / 1_000_000,  # Per token, not per million
            cost_per_output_token=output_cost / 1_000_000,
        )

        adapter = GovernedLLMAdapter(
            backend=backends[provider_name],
            budget_manager=budget_manager,
            clock=clock,
        )

        provider_id = f"llm-{provider_name}"

        try:
            engine.register(descriptor, adapter, provider_id=provider_id)
            result.registered_models.append(model_id)
        except ModelAlreadyRegisteredError:
            result.skipped_model_registrations.append({
                "model_id": model_id,
                "provider": provider_name,
                "error_code": "model_already_registered",
                "reason": "model already registered",
            })
        except RuntimeCoreInvariantError:
            raise
        except Exception as exc:
            result.model_registration_failures.append({
                "model_id": model_id,
                "provider": provider_name,
                "error_code": "model_registration_failed",
                "error_type": type(exc).__name__,
                "reason": _classify_bootstrap_exception(exc),
            })
