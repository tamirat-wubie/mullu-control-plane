"""Multi-Provider LLM Backends.

All providers follow the OpenAI-compatible chat completions API pattern.
Each wraps a different endpoint with the same LLMBackend protocol.

Provider credentials are injected at bootstrap or resolved from environment variables.
All providers return LLMResult with cost estimation based on token counts.

Invariants:
  - Every provider implements the LLMBackend protocol.
  - API keys are never logged or exposed through result errors.
  - Errors are typed (LLMResult with error field), never raw exceptions.
  - Cost is estimated from token counts x provider pricing.
"""

from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import urlsplit

from mcoi_runtime.contracts.llm import (
    LLMInvocationParams,
    LLMProvider,
    LLMResult,
)
from mcoi_runtime.adapters.proxy_policy import assert_proxy_environment_allowed

_HOSTED_PROVIDER_STUB_DENY_ENVS = frozenset({"pilot", "production", "prod"})


def _validate_provider_base_url(base_url: str) -> str:
    """Return a structurally valid provider base URL without credentials."""

    value = str(base_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("provider base_url must be a non-empty string")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("provider base_url must not contain control characters")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError("provider base_url must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("provider base_url must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("provider base_url must not include query or fragment")
    return value


def _response_status_code(response: Any) -> int:
    status_code = getattr(response, "status_code", 200)
    if not isinstance(status_code, int):
        raise ValueError("provider response status_code must be an integer")
    return status_code


def _response_json_payload(response: Any) -> Any:
    try:
        return response.json()
    except Exception as exc:
        raise ValueError("provider response must contain valid JSON") from exc


def _provider_failure(
    *,
    model: str,
    provider: LLMProvider,
    error: str,
) -> LLMResult:
    return LLMResult(
        content="",
        input_tokens=0,
        output_tokens=0,
        cost=0.0,
        model_name=model,
        provider=provider,
        finished=False,
        error=error,
    )


def _hosted_provider_stub_denial() -> str | None:
    env = os.environ.get("MULLU_ENV", "").strip().lower()
    if env in _HOSTED_PROVIDER_STUB_DENY_ENVS:
        return "provider dependency unavailable; hosted provider stub fallback is forbidden"
    return None


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


def _response_choice_content(data: Mapping[str, Any]) -> str:
    """Return validated assistant content from one provider response."""

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("provider response invalid")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ValueError("provider response invalid")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("provider response invalid")
    content = message.get("content", "")
    if not isinstance(content, str):
        raise ValueError("provider response invalid")
    return content


def _response_usage_tokens(data: Mapping[str, Any], field_name: str) -> int:
    """Return one non-negative integer usage counter from provider response."""

    usage = data.get("usage", {})
    if usage is None:
        return 0
    if not isinstance(usage, Mapping):
        raise ValueError("provider response invalid")
    value = usage.get(field_name, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("provider response invalid")
    return value


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
    try:
        provider_base_url = _validate_provider_base_url(base_url)
    except ValueError:
        return _provider_failure(
            model=model,
            provider=provider,
            error="provider base_url invalid",
        )

    if not api_key:
        return _provider_failure(
            model=model,
            provider=provider,
            error="provider credentials unavailable",
        )

    try:
        import httpx
        assert_proxy_environment_allowed()
        response = httpx.post(
            f"{provider_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=60.0,
            trust_env=False,
        )
        status_code = _response_status_code(response)
        try:
            data = _response_json_payload(response)
        except ValueError:
            return _provider_failure(
                model=model,
                provider=provider,
                error="provider response invalid",
            )
        if not isinstance(data, dict):
            return _provider_failure(
                model=model,
                provider=provider,
                error="provider response invalid",
            )

        if status_code < 200 or status_code >= 300:
            payload_error = data.get("error", data)
            return _provider_failure(
                model=model,
                provider=provider,
                error=_classify_provider_payload_error(payload_error),
            )

        if "error" in data:
            return _provider_failure(
                model=model,
                provider=provider,
                error=_classify_provider_payload_error(data["error"]),
            )

        try:
            content = _response_choice_content(data)
            input_tokens = _response_usage_tokens(data, "prompt_tokens")
            output_tokens = _response_usage_tokens(data, "completion_tokens")
        except ValueError:
            return _provider_failure(
                model=model,
                provider=provider,
                error="provider response invalid",
            )
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
        denial = _hosted_provider_stub_denial()
        if denial is not None:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=provider,
                finished=False,
                error=denial,
            )

        # httpx not available - return bounded local/test stub response
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


class _SelfHostedOpenAICompatibleBackend:
    """Base adapter for private OpenAI-compatible model servers."""

    provider = LLMProvider.STUB
    DEFAULT_MODEL = "local-model"
    ROUTING_MODEL = "selfhosted/local-model"
    MODEL_ALIASES: Mapping[str, str] = {}
    DEFAULT_BASE_URL = "http://localhost:8000/v1"
    API_KEY_ENV = ""
    BASE_URL_ENV = ""
    API_KEY_FALLBACK = "local"

    def __init__(
        self,
        *,
        model: str = "",
        base_url: str = "",
        api_key: str | None = None,
        api_key_env: str = "",
        base_url_env: str = "",
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key or ""
        self._api_key_env = api_key_env or self.API_KEY_ENV
        self._base_url_env = base_url_env or self.BASE_URL_ENV
        self._call_count = 0

    def _resolved_base_url(self) -> str:
        configured_base_url = self._base_url or os.environ.get(self._base_url_env, "")
        return (configured_base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def _resolved_api_key(self) -> str:
        return self._api_key or os.environ.get(self._api_key_env, "") or self.API_KEY_FALLBACK

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url=self._resolved_base_url(),
            api_key=self._resolved_api_key(),
            model=model,
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


class VLLMBackend(_SelfHostedOpenAICompatibleBackend):
    """vLLM private OpenAI-compatible server for open-weight models."""

    provider = LLMProvider.VLLM
    DEFAULT_MODEL = "Qwen/Qwen3-0.6B"
    ROUTING_MODEL = "vllm/Qwen/Qwen3-0.6B"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:8000/v1"
    API_KEY_ENV = "VLLM_API_KEY"
    BASE_URL_ENV = "VLLM_BASE_URL"
    API_KEY_FALLBACK = "vllm"


class SGLangBackend(_SelfHostedOpenAICompatibleBackend):
    """SGLang private OpenAI-compatible server for open-weight models."""

    provider = LLMProvider.SGLANG
    DEFAULT_MODEL = "Qwen/Qwen3-0.6B"
    ROUTING_MODEL = "sglang/Qwen/Qwen3-0.6B"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:30000/v1"
    API_KEY_ENV = "SGLANG_API_KEY"
    BASE_URL_ENV = "SGLANG_BASE_URL"
    API_KEY_FALLBACK = "sglang"


class TGIBackend(_SelfHostedOpenAICompatibleBackend):
    """Hugging Face TGI Messages API server."""

    provider = LLMProvider.TGI
    DEFAULT_MODEL = "tgi"
    ROUTING_MODEL = "tgi/default"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:3000/v1"
    API_KEY_ENV = "TGI_API_KEY"
    BASE_URL_ENV = "TGI_BASE_URL"
    API_KEY_FALLBACK = "-"


class LlamaCppBackend(_SelfHostedOpenAICompatibleBackend):
    """llama.cpp llama-server OpenAI-compatible endpoint."""

    provider = LLMProvider.LLAMACPP
    DEFAULT_MODEL = "local-model"
    ROUTING_MODEL = "llamacpp/local-model"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:8080/v1"
    API_KEY_ENV = "LLAMACPP_API_KEY"
    BASE_URL_ENV = "LLAMACPP_BASE_URL"
    API_KEY_FALLBACK = "llamacpp"


class LocalAIBackend(_SelfHostedOpenAICompatibleBackend):
    """LocalAI OpenAI-compatible endpoint for private model servers."""

    provider = LLMProvider.LOCALAI
    DEFAULT_MODEL = "local-model"
    ROUTING_MODEL = "localai/local-model"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:8080/v1"
    API_KEY_ENV = "LOCALAI_API_KEY"
    BASE_URL_ENV = "LOCALAI_BASE_URL"
    API_KEY_FALLBACK = "localai"


class LMStudioBackend(_SelfHostedOpenAICompatibleBackend):
    """LM Studio local OpenAI-compatible endpoint for loaded models."""

    provider = LLMProvider.LMSTUDIO
    DEFAULT_MODEL = "model-identifier"
    ROUTING_MODEL = "lmstudio/model-identifier"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}
    DEFAULT_BASE_URL = "http://localhost:1234/v1"
    API_KEY_ENV = "LMSTUDIO_API_KEY"
    BASE_URL_ENV = "LMSTUDIO_BASE_URL"
    API_KEY_FALLBACK = "lm-studio"


# Groq (Llama 4, free tier)
class GroqBackend:
    """Groq - hardware-accelerated inference for open-weight models.

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


# Google Gemini (1K free/day)
class GeminiBackend:
    """Google Gemini - generous free tier (1K requests/day).

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


# DeepSeek (V3.2 / R1, best price-performance)
class DeepSeekBackend:
    """DeepSeek - best price-performance ratio.

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


class ParasailBackend:
    """Parasail OpenAI-compatible endpoint for inexpensive Qwen models."""

    provider = LLMProvider.PARASAIL
    DEFAULT_MODEL = "parasail-qwen3-32b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "PARASAIL_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.parasail.io/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.50,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class FeatherlessBackend:
    """Featherless OpenAI-compatible endpoint for flat-rate open-weight models."""

    provider = LLMProvider.FEATHERLESS
    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct-1M"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "FEATHERLESS_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.featherless.ai/v1",
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


class PacketBackend:
    """Packet Token Factory OpenAI-compatible endpoint for inexpensive Llama models."""

    provider = LLMProvider.PACKET
    DEFAULT_MODEL = "meta-llama/Llama-3.1-70B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "PACKET_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://dash.packet.ai/api/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.15,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class RidvayBackend:
    """Ridvay OpenAI-compatible endpoint for Qwen and open-weight models."""

    provider = LLMProvider.RIDVAY
    DEFAULT_MODEL = "qwen/qwen3-30b-a3b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "RIDVAY_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.ridvay.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.06,
            cost_per_1m_output=0.22,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class NeuroRoutersBackend:
    """NeuroRouters OpenAI-compatible endpoint for routed free-tier models."""

    provider = LLMProvider.NEUROROUTERS
    DEFAULT_MODEL = "qwen/qwen3-30b-a3b:free"

    def __init__(
        self,
        *,
        model: str = "",
        api_key: str | None = None,
        api_key_env: str = "NEUROROUTERS_API_KEY",
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://neurorouters.com/api/v1",
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


class GlamaBackend:
    """Glama Gateway OpenAI-compatible endpoint for hosted model routing."""

    provider = LLMProvider.GLAMA
    DEFAULT_MODEL = "deepseek-chat-v3"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "GLAMA_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://gateway.glama.ai/v1",
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


class GMIBackend:
    """GMI Cloud OpenAI-compatible endpoint for inexpensive Qwen models."""

    provider = LLMProvider.GMI
    DEFAULT_MODEL = "Qwen/Qwen3-32B-FP8"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "GMI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.gmi-serving.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.60,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class AtlasCloudBackend:
    """Atlas Cloud OpenAI-compatible endpoint for inexpensive Qwen models."""

    provider = LLMProvider.ATLASCLOUD
    DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "ATLASCLOUD_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.atlascloud.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.09,
            cost_per_1m_output=0.30,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class ModelMaxBackend:
    """ModelMax OpenAI-compatible gateway for inexpensive Qwen coder models."""

    provider = LLMProvider.MODELMAX
    DEFAULT_MODEL = "qwen3-coder-30b-a3b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "MODELMAX_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.modelmax.io/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.60,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class VeniceBackend:
    """Venice OpenAI-compatible endpoint for inexpensive private Qwen models."""

    provider = LLMProvider.VENICE
    DEFAULT_MODEL = "qwen3-5-9b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "VENICE_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.venice.ai/api/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.15,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class EURIBackend:
    """EURI OpenAI-compatible gateway for inexpensive hosted models."""

    provider = LLMProvider.EURI
    DEFAULT_MODEL = "qwen/qwen3-32b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "EURI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.euron.one/api/v1/euri",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.29,
            cost_per_1m_output=0.59,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class APIRouterBackend:
    """APIRouter OpenAI-compatible gateway for low-cost Qwen and DeepSeek models."""

    provider = LLMProvider.APIROUTER
    DEFAULT_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "APIROUTER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://apirouter.chat/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.028,
            cost_per_1m_output=0.112,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class QuickSilverBackend:
    """QuickSilver Pro OpenAI-compatible endpoint for long-context Qwen models."""

    provider = LLMProvider.QUICKSILVER
    DEFAULT_MODEL = "qwen3.6-35b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "QUICKSILVER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.quicksilverpro.io/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("QSP_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.13,
            cost_per_1m_output=0.78,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class MixlayerBackend:
    """Mixlayer OpenAI-compatible endpoint for low-cost open model routing."""

    provider = LLMProvider.MIXLAYER
    DEFAULT_MODEL = "qwen/qwen3.5-9b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "MIXLAYER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://models.mixlayer.ai/v1",
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


class ApiLinkBackend:
    """ApiLink OpenAI-compatible gateway for hosted model routing."""

    provider = LLMProvider.APILINK
    DEFAULT_MODEL = "deepseek/deepseek-v4-pro"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "APILINK_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.apilink.io/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.43,
            cost_per_1m_output=0.870,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class EmberCloudBackend:
    """EmberCloud OpenAI-compatible endpoint for low-cost GLM models."""

    provider = LLMProvider.EMBERCLOUD
    DEFAULT_MODEL = "glm-4.7-flash"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "EMBERCLOUD_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.embercloud.ai/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.06,
            cost_per_1m_output=0.40,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class MorpheusBackend:
    """Morpheus OpenAI-compatible marketplace for low-cost hosted models."""

    provider = LLMProvider.MORPHEUS
    DEFAULT_MODEL = "qwen35-9b"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "MORPHEUS_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.mor.org/api/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("MOR_API_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.05,
            cost_per_1m_output=0.15,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class InferenceNetBackend:
    """Inference.net OpenAI-compatible endpoint for Gemma and workhorse models."""

    provider = LLMProvider.INFERENCENET
    DEFAULT_MODEL = "google/gemma-3-27b-instruct/bf-16"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "INFERENCE_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.inference.net/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("INFERENCENET_API_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.30,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class AnswiraBackend:
    """Answira OpenAI-compatible EU-hosted endpoint for Qwen coding models."""

    provider = LLMProvider.ANSWIRA
    DEFAULT_MODEL = "qwen/qwen3-coder-next"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "ANSWIRA_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://answira.ai/api/v1",
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


class LLMAIBackend:
    """LLMAI OpenAI-compatible gateway for low-cost Gemma and DeepSeek models."""

    provider = LLMProvider.LLMAI
    DEFAULT_MODEL = "gemma-4"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "LLMAI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.llmai.dev/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, "") or os.environ.get("LLMAI_TOKEN", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.046,
            cost_per_1m_output=0.130,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class RequestyBackend:
    """Requesty OpenAI-compatible gateway for cached long-context routing."""

    provider = LLMProvider.REQUESTY
    DEFAULT_MODEL = "deepseek/deepseek-chat"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "REQUESTY_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://router.requesty.ai/v1",
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


class HuggingFaceBackend:
    """Hugging Face router OpenAI-compatible endpoint for cheap hosted models."""

    provider = LLMProvider.HUGGINGFACE
    DEFAULT_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct:cheapest"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "HF_TOKEN") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://router.huggingface.co/v1",
            api_key=self._api_key
            or os.environ.get(self._api_key_env, "")
            or os.environ.get("HUGGINGFACE_API_KEY", ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.07,
            cost_per_1m_output=0.26,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class BasetenBackend:
    """Baseten Model APIs OpenAI-compatible endpoint for managed workhorse models."""

    provider = LLMProvider.BASETEN
    DEFAULT_MODEL = "nvidia/Nemotron-120B-A12B"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "BASETEN_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://inference.baseten.co/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=params.model_name or self._model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.30,
            cost_per_1m_output=0.75,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class HaimakerBackend:
    """haimaker OpenAI-compatible endpoint for cheap DeepSeek routing."""

    provider = LLMProvider.HAIMAKER
    DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324"

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "HAIMAKER_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        return _openai_compatible_call(
            base_url="https://api.haimaker.ai/v1",
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


class NscaleBackend:
    """Nscale Serverless Inference OpenAI-compatible endpoint for cheap GPT OSS models."""

    provider = LLMProvider.NSCALE
    DEFAULT_MODEL = "openai/gpt-oss-20b"
    ROUTING_MODEL = "nscale/openai/gpt-oss-20b"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "NSCALE_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url="https://inference.api.nscale.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=model,
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


class ScalewayBackend:
    """Scaleway Generative APIs OpenAI-compatible endpoint for EU-hosted models."""

    provider = LLMProvider.SCALEWAY
    DEFAULT_MODEL = "gpt-oss-120b"
    ROUTING_MODEL = "scaleway/gpt-oss-120b"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "SCW_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url="https://api.scaleway.ai/v1",
            api_key=self._api_key
            or os.environ.get(self._api_key_env, "")
            or os.environ.get("SCALEWAY_API_KEY", ""),
            model=model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.60,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class OVHCloudBackend:
    """OVHcloud AI Endpoints OpenAI-compatible endpoint for low-cost code models."""

    provider = LLMProvider.OVHCLOUD
    DEFAULT_MODEL = "Qwen3-Coder-30B-A3B-Instruct"
    ROUTING_MODEL = "ovhcloud/Qwen3-Coder-30B-A3B-Instruct"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(
        self,
        *,
        model: str = "",
        api_key: str | None = None,
        api_key_env: str = "OVH_AI_ENDPOINTS_ACCESS_TOKEN",
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
            api_key=self._api_key
            or os.environ.get(self._api_key_env, "")
            or os.environ.get("AI_ENDPOINT_API_KEY", ""),
            model=model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.06,
            cost_per_1m_output=0.22,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class AIMLAPIBackend:
    """AIMLAPI OpenAI-compatible endpoint for low-cost Nemotron models."""

    provider = LLMProvider.AIMLAPI
    DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
    ROUTING_MODEL = "aimlapi/nvidia/nemotron-3-nano-30b-a3b"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "AIMLAPI_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url="https://api.aimlapi.com/v1",
            api_key=self._api_key
            or os.environ.get(self._api_key_env, "")
            or os.environ.get("AIML_API_KEY", ""),
            model=model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.065,
            cost_per_1m_output=0.26,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class InfomaniakBackend:
    """Infomaniak product-scoped OpenAI-compatible endpoint."""

    provider = LLMProvider.INFOMANIAK
    DEFAULT_MODEL = "google/gemma-4-31B-it"
    ROUTING_MODEL = "infomaniak/google/gemma-4-31B-it"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(
        self,
        *,
        model: str = "",
        api_key: str | None = None,
        api_key_env: str = "INFOMANIAK_API_KEY",
        product_id: str = "",
        base_url: str = "",
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._product_id = product_id
        self._base_url = self.resolve_base_url(base_url, product_id)
        self._call_count = 0

    @staticmethod
    def resolve_base_url(base_url: str = "", product_id: str = "") -> str:
        if base_url:
            return base_url.rstrip("/")
        if product_id:
            return f"https://api.infomaniak.com/2/ai/{product_id}/openai/v1"
        return ""

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        api_key = self._api_key or os.environ.get(self._api_key_env, "")
        base_url = self._base_url or self.resolve_base_url(
            os.environ.get("INFOMANIAK_BASE_URL", ""),
            os.environ.get("INFOMANIAK_PRODUCT_ID", ""),
        )
        if not base_url:
            return LLMResult(
                content="",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                model_name=model,
                provider=self.provider,
                finished=False,
                error="provider base URL unavailable",
            )
        return _openai_compatible_call(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.20,
            cost_per_1m_output=0.40,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class KatalepticBackend:
    """Kataleptic OpenAI-compatible endpoint for curated low-cost models."""

    provider = LLMProvider.KATALEPTIC
    DEFAULT_MODEL = "gemma3-27b"
    ROUTING_MODEL = "kataleptic/gemma3-27b"
    MODEL_ALIASES = {ROUTING_MODEL: DEFAULT_MODEL}

    def __init__(self, *, model: str = "", api_key: str | None = None, api_key_env: str = "KATALEPTIC_API_KEY") -> None:
        self._model = model or self.DEFAULT_MODEL
        self._default_model = self._model
        self._api_key = api_key or ""
        self._api_key_env = api_key_env
        self._call_count = 0

    def call(self, params: LLMInvocationParams) -> LLMResult:
        self._call_count += 1
        requested_model = params.model_name or self._model
        model = self.MODEL_ALIASES.get(requested_model, requested_model)
        return _openai_compatible_call(
            base_url="https://api.kataleptic.com/v1",
            api_key=self._api_key or os.environ.get(self._api_key_env, ""),
            model=model,
            messages=_params_to_messages(params),
            max_tokens=params.max_tokens,
            temperature=0.0,
            provider=self.provider,
            cost_per_1m_input=0.15,
            cost_per_1m_output=0.20,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


# --- xAI Grok (real-time X data) ---
class GrokBackend:
    """xAI Grok - real-time X (Twitter) data access.

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


# Mistral (cheapest paid option)
class MistralBackend:
    """Mistral - cheapest paid LLM provider.

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


# OpenRouter (multi-provider gateway)
class OpenRouterBackend:
    """OpenRouter - unified gateway to 100+ models.

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


# Provider Registry
PROVIDER_ENV_MAP: Mapping[str, tuple[str, ...]] = {
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
    "parasail": ("PARASAIL_API_KEY",),
    "featherless": ("FEATHERLESS_API_KEY",),
    "packet": ("PACKET_API_KEY",),
    "ridvay": ("RIDVAY_API_KEY",),
    "neurorouters": ("NEUROROUTERS_API_KEY",),
    "glama": ("GLAMA_API_KEY",),
    "gmi": ("GMI_API_KEY",),
    "atlascloud": ("ATLASCLOUD_API_KEY",),
    "modelmax": ("MODELMAX_API_KEY",),
    "venice": ("VENICE_API_KEY",),
    "euri": ("EURI_API_KEY",),
    "apirouter": ("APIROUTER_API_KEY",),
    "quicksilver": ("QUICKSILVER_API_KEY", "QSP_KEY"),
    "mixlayer": ("MIXLAYER_API_KEY",),
    "apilink": ("APILINK_API_KEY",),
    "embercloud": ("EMBERCLOUD_API_KEY",),
    "morpheus": ("MORPHEUS_API_KEY", "MOR_API_KEY"),
    "inferencenet": ("INFERENCE_API_KEY", "INFERENCENET_API_KEY"),
    "answira": ("ANSWIRA_API_KEY",),
    "llmai": ("LLMAI_API_KEY", "LLMAI_TOKEN"),
    "requesty": ("REQUESTY_API_KEY",),
    "huggingface": ("HF_TOKEN", "HUGGINGFACE_API_KEY"),
    "baseten": ("BASETEN_API_KEY",),
    "haimaker": ("HAIMAKER_API_KEY",),
    "nscale": ("NSCALE_API_KEY",),
    "scaleway": ("SCW_API_KEY", "SCALEWAY_API_KEY"),
    "ovhcloud": ("OVH_AI_ENDPOINTS_ACCESS_TOKEN", "AI_ENDPOINT_API_KEY"),
    "aimlapi": ("AIMLAPI_API_KEY", "AIML_API_KEY"),
    "infomaniak": ("INFOMANIAK_API_KEY",),
    "kataleptic": ("KATALEPTIC_API_KEY",),
    "grok": ("XAI_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}

PROVIDER_DEPENDENCY_GROUPS: Mapping[str, tuple[tuple[str, ...], ...]] = {
    "cloudflare": (("CLOUDFLARE_ACCOUNT_ID",),),
    "infomaniak": (("INFOMANIAK_BASE_URL", "INFOMANIAK_PRODUCT_ID"),),
}

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
    "parasail": ParasailBackend,
    "featherless": FeatherlessBackend,
    "packet": PacketBackend,
    "ridvay": RidvayBackend,
    "neurorouters": NeuroRoutersBackend,
    "glama": GlamaBackend,
    "gmi": GMIBackend,
    "atlascloud": AtlasCloudBackend,
    "modelmax": ModelMaxBackend,
    "venice": VeniceBackend,
    "euri": EURIBackend,
    "apirouter": APIRouterBackend,
    "quicksilver": QuickSilverBackend,
    "mixlayer": MixlayerBackend,
    "apilink": ApiLinkBackend,
    "embercloud": EmberCloudBackend,
    "morpheus": MorpheusBackend,
    "inferencenet": InferenceNetBackend,
    "answira": AnswiraBackend,
    "llmai": LLMAIBackend,
    "requesty": RequestyBackend,
    "huggingface": HuggingFaceBackend,
    "baseten": BasetenBackend,
    "haimaker": HaimakerBackend,
    "nscale": NscaleBackend,
    "scaleway": ScalewayBackend,
    "ovhcloud": OVHCloudBackend,
    "aimlapi": AIMLAPIBackend,
    "infomaniak": InfomaniakBackend,
    "kataleptic": KatalepticBackend,
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
    return [
        provider_name
        for provider_name, health in provider_configuration_health().items()
        if health["status"] == "ready"
    ]


def provider_configuration_health(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, object]]:
    """Return secret-safe provider readiness from environment configuration only."""
    env = os.environ if environ is None else environ
    health: dict[str, dict[str, object]] = {}
    for provider_name, credential_keys in PROVIDER_ENV_MAP.items():
        credential_configured = any(env.get(key) for key in credential_keys)
        dependency_groups = PROVIDER_DEPENDENCY_GROUPS.get(provider_name, ())
        dependencies_configured = all(any(env.get(key) for key in group) for group in dependency_groups)
        if credential_configured and dependencies_configured:
            status = "ready"
        elif credential_configured:
            status = "missing_dependency"
        else:
            status = "missing_credentials"
        health[provider_name] = {
            "status": status,
            "configured": status == "ready",
            "credential_keys": credential_keys,
            "dependency_groups": dependency_groups,
        }
    return health
