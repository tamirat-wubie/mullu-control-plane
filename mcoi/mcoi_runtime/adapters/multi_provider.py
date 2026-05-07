"""Multi-Provider LLM Backends.

All providers follow the OpenAI-compatible chat completions API pattern.
Each wraps a different endpoint with the same LLMBackend protocol.

Provider credentials are injected at bootstrap or resolved from environment variables.
All providers return LLMResult with cost estimation based on token counts.

Invariants:
  - Every provider implements the LLMBackend protocol.
  - API keys are never logged or exposed through result errors.
  - Errors are typed (LLMResult with error field), never raw exceptions.
  - Cost is estimated from token counts × provider pricing.
"""

from __future__ import annotations

import os
from typing import Any

from mcoi_runtime.contracts.llm import (
    LLMInvocationParams,
    LLMProvider,
    LLMResult,
)


def _classify_provider_exception(exc: Exception) -> str:
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


def _classify_provider_payload_error(error_payload: Any) -> str:
    if isinstance(error_payload, dict):
        normalized = " ".join(
            str(error_payload.get(field, ""))
            for field in ("type", "code", "message")
        ).lower()
    else:
        normalized = str(error_payload).lower()
    if "timeout" in normalized or "timed out" in normalized:
        return "provider timeout"
    if ("rate" in normalized and "limit" in normalized) or "quota" in normalized:
        return "provider rate limited request"
    if any(
        token in normalized
        for token in ("auth", "api key", "apikey", "unauthorized", "forbidden", "invalid key", "authentication")
    ):
        return "provider authentication failed"
    return "provider rejected request"


def _openai_compatible_call(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    provider: LLMProvider,
    cost_per_1m_input: float,
    cost_per_1m_output: float,
) -> LLMResult:
    """Generic OpenAI-compatible API call.

    Most modern LLM providers use the same chat/completions endpoint format.
    This function handles the common pattern.
    """
    if not api_key:
        return LLMResult(
            content="", input_tokens=0, output_tokens=0, cost=0.0,
            model_name=model, provider=provider, finished=False,
            error="provider credentials unavailable",
        )

    try:
        import httpx
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=60.0,
        )
        data = response.json()

        if "error" in data:
            return LLMResult(
                content="", input_tokens=0, output_tokens=0, cost=0.0,
                model_name=model, provider=provider, finished=False,
                error=_classify_provider_payload_error(data["error"]),
            )

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens * cost_per_1m_input + output_tokens * cost_per_1m_output) / 1_000_000

        return LLMResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            model_name=model,
            provider=provider,
            finished=True,
        )
    except ImportError:
        # httpx not available — return stub response for testing
        total_chars = sum(len(m.get("content", "")) for m in messages)
        input_tokens = max(1, total_chars // 4)
        output_tokens = max(1, 20)
        cost = (input_tokens * cost_per_1m_input + output_tokens * cost_per_1m_output) / 1_000_000
        return LLMResult(
            content="provider stub response",
            input_tokens=input_tokens, output_tokens=output_tokens, cost=cost,
            model_name=model, provider=provider, finished=True,
        )
    except Exception as exc:
        return LLMResult(
            content="", input_tokens=0, output_tokens=0, cost=0.0,
            model_name=model, provider=provider, finished=False,
            error=_classify_provider_exception(exc),
        )


def _params_to_messages(params: LLMInvocationParams) -> list[dict[str, str]]:
    """Convert LLMInvocationParams to OpenAI-format messages."""
    return [
        {"role": m.role.value if hasattr(m, "role") else "user",
         "content": m.content if hasattr(m, "content") else str(m)}
        for m in params.messages
    ]


# ═══ Groq (Llama 4, free tier) ═══


class GroqBackend:
    """Groq — hardware-accelerated inference for open-weight models.

    Free tier with rate limits. Fastest inference available.
    Models: llama-4-scout-17b, llama-4-maverick-17b, mixtral-8x7b
    """

    provider = LLMProvider.GROQ
    DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "GROQ_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.groq.com/openai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.11,
            cost_per_1m_output=0.34,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══ Google Gemini (1K free/day) ═══


class GeminiBackend:
    """Google Gemini — generous free tier (1K requests/day).

    Models: gemini-2.5-pro, gemini-2.0-flash, gemini-2.0-flash-lite
    """

    provider = LLMProvider.GEMINI
    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "GEMINI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        # Gemini uses generativelanguage.googleapis.com, but also supports OpenAI-compat
        return _openai_compatible_call(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.40,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══ DeepSeek (V3.2 / R1, best price-performance) ═══


class DeepSeekBackend:
    """DeepSeek — best price-performance ratio.

    Models: deepseek-chat (V3.2), deepseek-reasoner (R1)
    """

    provider = LLMProvider.DEEPSEEK
    DEFAULT_MODEL = "deepseek-v4-flash"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "DEEPSEEK_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.deepseek.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.14,
            cost_per_1m_output=0.28,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# --- Additional hosted OpenAI-compatible providers ---


class TogetherBackend:
    """Together hosted open-model inference."""

    provider = LLMProvider.TOGETHER
    DEFAULT_MODEL = "LiquidAI/LFM2-24B-A2B"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "TOGETHER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.together.xyz/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.03,
            cost_per_1m_output=0.12,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class FireworksBackend:
    """Fireworks hosted open-model inference."""

    provider = LLMProvider.FIREWORKS
    DEFAULT_MODEL = "accounts/fireworks/models/gpt-oss-20b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "FIREWORKS_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.07,
            cost_per_1m_output=0.30,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class FriendliBackend:
    """Friendli serverless OpenAI-compatible endpoint."""

    provider = LLMProvider.FRIENDLI
    DEFAULT_MODEL = "meta-llama-3.1-8b-instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "FRIENDLI_TOKEN") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.friendli.ai/serverless/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.10,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class NovitaBackend:
    """Novita OpenAI-compatible endpoint for inexpensive hosted models."""

    provider = LLMProvider.NOVITA
    DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "NOVITA_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.novita.ai/openai",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.14,
            cost_per_1m_output=0.28,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class CerebrasBackend:
    """Cerebras fast OpenAI-compatible inference endpoint."""

    provider = LLMProvider.CEREBRAS
    DEFAULT_MODEL = "llama3.1-8b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "CEREBRAS_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.cerebras.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.10,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class DeepInfraBackend:
    """DeepInfra OpenAI-compatible endpoint for broad low-cost model coverage."""

    provider = LLMProvider.DEEPINFRA
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "DEEPINFRA_TOKEN") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.deepinfra.com/v1/openai",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("DEEPINFRA_API_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.02,
            cost_per_1m_output=0.03,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class NebiusBackend:
    """Nebius Studio OpenAI-compatible low-cost endpoint."""

    provider = LLMProvider.NEBIUS
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "NEBIUS_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.tokenfactory.nebius.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.02,
            cost_per_1m_output=0.06,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class HyperbolicBackend:
    """Hyperbolic OpenAI-compatible endpoint for inexpensive open models."""

    provider = LLMProvider.HYPERBOLIC
    DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "HYPERBOLIC_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.hyperbolic.xyz/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.20,
            cost_per_1m_output=0.20,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class SambaNovaBackend:
    """SambaNova Cloud OpenAI-compatible endpoint for fast open models."""

    provider = LLMProvider.SAMBANOVA
    DEFAULT_MODEL = "Meta-Llama-3.3-70B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "SAMBANOVA_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.sambanova.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.60,
            cost_per_1m_output=1.20,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class CloudflareBackend:
    """Cloudflare Workers AI OpenAI-compatible endpoint."""

    provider = LLMProvider.CLOUDFLARE
    DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct-fp8-fast"

    def __init__(
        self,
        *,
        model: str = "",
        api_key: str | None = None,
        api_key_env: str = "CLOUDFLARE_API_TOKEN",
        account_id: str = "",
        account_id_env: str = "CLOUDFLARE_ACCOUNT_ID",
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._account_id = account_id
        self._account_id_env = account_id_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        account_id = self._account_id or os.environ.get(self._account_id_env, "")
        if not account_id:
            return LLMResult(
                content="", input_tokens=0, output_tokens=0, cost=0.0,
                model_name=params.model_name or self._model, provider=self.provider,
                finished=False, error="provider account unavailable",
            )
        return _openai_compatible_call(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("CLOUDFLARE_API_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.045,
            cost_per_1m_output=0.384,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class MoonshotBackend:
    """Moonshot Kimi OpenAI-compatible endpoint for agentic coding models."""

    provider = LLMProvider.MOONSHOT
    DEFAULT_MODEL = "kimi-k2.5"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "MOONSHOT_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.moonshot.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.60,
            cost_per_1m_output=3.00,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class DashScopeBackend:
    """Alibaba Cloud DashScope OpenAI-compatible endpoint for Qwen models."""

    provider = LLMProvider.DASHSCOPE
    DEFAULT_MODEL = "qwen-turbo"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "DASHSCOPE_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.05,
            cost_per_1m_output=0.20,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class ZAIBackend:
    """Z.AI OpenAI-compatible endpoint for GLM models."""

    provider = LLMProvider.ZAI
    DEFAULT_MODEL = "glm-4.5-air"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "ZAI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.z.ai/api/paas/v4",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.20,
            cost_per_1m_output=1.10,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class SiliconFlowBackend:
    """SiliconFlow OpenAI-compatible endpoint for inexpensive Qwen models."""

    provider = LLMProvider.SILICONFLOW
    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "SILICONFLOW_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.siliconflow.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.05,
            cost_per_1m_output=0.05,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class DInferenceBackend:
    """DInference OpenAI-compatible endpoint for inexpensive GPT OSS models."""

    provider = LLMProvider.DINFERENCE
    DEFAULT_MODEL = "gpt-oss-120b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "DINFERENCE_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.dinference.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.09,
            cost_per_1m_output=0.36,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class ChutesBackend:
    """Chutes OpenAI-compatible endpoint for inexpensive open-weight models."""

    provider = LLMProvider.CHUTES
    DEFAULT_MODEL = "Qwen/Qwen3-32B-TEE"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "CHUTES_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://llm.chutes.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.08,
            cost_per_1m_output=0.24,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class WaveSpeedBackend:
    """WaveSpeed OpenAI-compatible endpoint for inexpensive Qwen coder models."""

    provider = LLMProvider.WAVESPEED
    DEFAULT_MODEL = "qwen/qwen3-coder-30b-a3b-instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "WAVESPEED_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://llm.wavespeed.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.07,
            cost_per_1m_output=0.27,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class BazaarLinkBackend:
    """BazaarLink OpenAI-compatible endpoint for inexpensive Llama models."""

    provider = LLMProvider.BAZAARLINK
    DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "BAZAARLINK_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://bazaarlink.ai/api/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.02,
            cost_per_1m_output=0.05,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class LlamaAPIBackend:
    """LlamaAPI OpenAI-compatible endpoint for inexpensive Llama models."""

    provider = LLMProvider.LLAMAAPI
    DEFAULT_MODEL = "llama3-70b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "LLAMA_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.llama-api.com",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.65,
            cost_per_1m_output=0.65,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# --- xAI Grok (real-time X data) ---


class GrokBackend:
    """xAI Grok — real-time X (Twitter) data access.

    Models: grok-3-mini, grok-3
    $25 free credit on signup.
    """

    provider = LLMProvider.GROK
    DEFAULT_MODEL = "grok-3-mini"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "XAI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.x.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.30,
            cost_per_1m_output=0.50,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══ Mistral (cheapest paid option) ═══


class MistralBackend:
    """Mistral — cheapest paid LLM provider.

    Models: mistral-small-latest, open-mistral-nemo, mistral-large-latest
    Nemo at $0.02/M tokens is essentially free for most workloads.
    """

    provider = LLMProvider.MISTRAL
    DEFAULT_MODEL = "mistral-small-latest"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "MISTRAL_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.mistral.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.30,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══ OpenRouter (multi-provider gateway) ═══


class OpenRouterBackend:
    """OpenRouter — unified gateway to 100+ models.

    Routes to the cheapest/fastest available provider per model.
    Community-funded free tier for popular models.
    """

    provider = LLMProvider.OPENROUTER
    DEFAULT_MODEL = "meta-llama/llama-4-scout"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "OPENROUTER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.0,
            cost_per_1m_output=0.0,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══ Provider Registry ═══


ALL_PROVIDERS: dict[str, type] = {
    "groq": GroqBackend,
    "gemini": GeminiBackend,
    "deepseek": DeepSeekBackend,
    "together": TogetherBackend,
    "fireworks": FireworksBackend,
    "friendli": FriendliBackend,
    "novita": NovitaBackend,
    "cerebras": CerebrasBackend,
    "deepinfra": DeepInfraBackend,
    "nebius": NebiusBackend,
    "hyperbolic": HyperbolicBackend,
    "sambanova": SambaNovaBackend,
    "cloudflare": CloudflareBackend,
    "moonshot": MoonshotBackend,
    "dashscope": DashScopeBackend,
    "zai": ZAIBackend,
    "siliconflow": SiliconFlowBackend,
    "dinference": DInferenceBackend,
    "chutes": ChutesBackend,
    "wavespeed": WaveSpeedBackend,
    "bazaarlink": BazaarLinkBackend,
    "llamaapi": LlamaAPIBackend,
    "grok": GrokBackend,
    "mistral": MistralBackend,
    "openrouter": OpenRouterBackend,
}


def create_provider(name: str, **kwargs: Any) -> Any:
    """Create a provider backend by name."""
    cls = ALL_PROVIDERS.get(name)
    if cls is None:
        raise ValueError("unsupported provider")
    return cls(**kwargs)


def available_providers() -> list[str]:
    """List providers that have API keys configured."""
    env_map = {
        "groq": ("GROQ_API_KEY",),
        "gemini": ("GEMINI_API_KEY",),
        "deepseek": ("DEEPSEEK_API_KEY",),
        "together": ("TOGETHER_API_KEY",),
        "fireworks": ("FIREWORKS_API_KEY",),
        "friendli": ("FRIENDLI_TOKEN", "FRIENDLI_API_KEY"),
        "novita": ("NOVITA_API_KEY",),
        "cerebras": ("CEREBRAS_API_KEY",),
        "deepinfra": ("DEEPINFRA_TOKEN", "DEEPINFRA_API_KEY"),
        "nebius": ("NEBIUS_API_KEY",),
        "hyperbolic": ("HYPERBOLIC_API_KEY",),
        "sambanova": ("SAMBANOVA_API_KEY",),
        "cloudflare": ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY"),
        "moonshot": ("MOONSHOT_API_KEY",),
        "dashscope": ("DASHSCOPE_API_KEY",),
        "zai": ("ZAI_API_KEY",),
        "siliconflow": ("SILICONFLOW_API_KEY",),
        "dinference": ("DINFERENCE_API_KEY",),
        "chutes": ("CHUTES_API_KEY",),
        "wavespeed": ("WAVESPEED_API_KEY",),
        "bazaarlink": ("BAZAARLINK_API_KEY",),
        "llamaapi": ("LLAMA_API_KEY",),
        "grok": ("XAI_API_KEY",),
        "mistral": ("MISTRAL_API_KEY",),
        "openrouter": ("OPENROUTER_API_KEY",),
    }
    available = [name for name, env_vars in env_map.items() if any(os.environ.get(env_var) for env_var in env_vars)]
    if "cloudflare" in available and not os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        available.remove("cloudflare")
    return available
