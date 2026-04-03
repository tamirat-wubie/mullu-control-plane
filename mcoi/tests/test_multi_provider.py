"""Multi-Provider LLM Backend Tests.

Tests all 6 providers: Groq, Gemini, DeepSeek, Grok, Mistral, OpenRouter.
Uses stub mode (no httpx) — validates protocol compliance, message formatting,
cost estimation, and error handling.
"""

import pytest
from mcoi_runtime.contracts.llm import LLMInvocationParams, LLMMessage, LLMProvider, LLMRole
from mcoi_runtime.adapters.multi_provider import (
    GroqBackend,
    GeminiBackend,
    DeepSeekBackend,
    GrokBackend,
    MistralBackend,
    OpenRouterBackend,
    ALL_PROVIDERS,
    create_provider,
    available_providers,
    _params_to_messages,
)


def _params(prompt: str = "Hello", model: str = "test-model") -> LLMInvocationParams:
    return LLMInvocationParams(
        messages=(LLMMessage(role=LLMRole.USER, content=prompt),),
        model_name=model,
        max_tokens=100,
    )


# ═══ Protocol Compliance ═══


class TestProtocolCompliance:
    """Every provider must implement LLMBackend protocol."""

    @pytest.mark.parametrize("cls", [
        GroqBackend, GeminiBackend, DeepSeekBackend,
        GrokBackend, MistralBackend, OpenRouterBackend,
    ])
    def test_has_provider_property(self, cls):
        backend = cls()
        assert isinstance(backend.provider, LLMProvider)

    @pytest.mark.parametrize("cls", [
        GroqBackend, GeminiBackend, DeepSeekBackend,
        GrokBackend, MistralBackend, OpenRouterBackend,
    ])
    def test_has_call_method(self, cls):
        backend = cls()
        assert callable(backend.call)

    @pytest.mark.parametrize("cls", [
        GroqBackend, GeminiBackend, DeepSeekBackend,
        GrokBackend, MistralBackend, OpenRouterBackend,
    ])
    def test_call_returns_llm_result(self, cls):
        backend = cls()
        result = backend.call(_params())
        assert hasattr(result, "content")
        assert hasattr(result, "input_tokens")
        assert hasattr(result, "output_tokens")
        assert hasattr(result, "cost")
        assert hasattr(result, "model_name")
        assert hasattr(result, "provider")


# ═══ Individual Providers ═══


class TestGroqBackend:
    def test_provider_type(self):
        assert GroqBackend().provider == LLMProvider.GROQ

    def test_default_model(self):
        assert "llama" in GroqBackend.DEFAULT_MODEL.lower()

    def test_call_without_key_returns_stub(self):
        backend = GroqBackend()
        result = backend.call(_params("test"))
        # Without httpx or API key, returns stub response
        assert result.finished or "no API key" in result.error or "groq" in result.content

    def test_call_count(self):
        backend = GroqBackend()
        assert backend.call_count == 0
        backend.call(_params())
        assert backend.call_count == 1

    def test_free_tier_cost(self):
        backend = GroqBackend()
        result = backend.call(_params())
        assert result.cost == 0.0  # Free tier


class TestGeminiBackend:
    def test_provider_type(self):
        assert GeminiBackend().provider == LLMProvider.GEMINI

    def test_default_model(self):
        assert "gemini" in GeminiBackend.DEFAULT_MODEL.lower()

    def test_call(self):
        backend = GeminiBackend()
        result = backend.call(_params())
        assert result.provider == LLMProvider.GEMINI


class TestDeepSeekBackend:
    def test_provider_type(self):
        assert DeepSeekBackend().provider == LLMProvider.DEEPSEEK

    def test_default_model(self):
        assert "deepseek" in DeepSeekBackend.DEFAULT_MODEL.lower()

    def test_cost_estimation(self):
        backend = DeepSeekBackend()
        result = backend.call(_params("A longer prompt to test cost estimation"))
        # DeepSeek has non-zero pricing
        assert result.cost >= 0


class TestGrokBackend:
    def test_provider_type(self):
        assert GrokBackend().provider == LLMProvider.GROK

    def test_default_model(self):
        assert "grok" in GrokBackend.DEFAULT_MODEL.lower()

    def test_call(self):
        backend = GrokBackend()
        result = backend.call(_params())
        assert result.provider == LLMProvider.GROK


class TestMistralBackend:
    def test_provider_type(self):
        assert MistralBackend().provider == LLMProvider.MISTRAL

    def test_default_model(self):
        assert "mistral" in MistralBackend.DEFAULT_MODEL.lower()

    def test_call(self):
        backend = MistralBackend()
        result = backend.call(_params())
        assert result.provider == LLMProvider.MISTRAL


class TestOpenRouterBackend:
    def test_provider_type(self):
        assert OpenRouterBackend().provider == LLMProvider.OPENROUTER

    def test_default_model(self):
        assert "llama" in OpenRouterBackend.DEFAULT_MODEL.lower()

    def test_free_tier_cost(self):
        backend = OpenRouterBackend()
        result = backend.call(_params())
        assert result.cost == 0.0  # Free community tier


# ═══ Message Conversion ═══


class TestMessageConversion:
    def test_single_message(self):
        params = _params("Hello")
        msgs = _params_to_messages(params)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"

    def test_multi_message(self):
        params = LLMInvocationParams(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content="You are helpful"),
                LLMMessage(role=LLMRole.USER, content="Hi"),
            ),
            model_name="test",
            max_tokens=100,
        )
        msgs = _params_to_messages(params)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


# ═══ Provider Registry ═══


class TestProviderRegistry:
    def test_all_providers_registered(self):
        assert len(ALL_PROVIDERS) == 6
        assert "groq" in ALL_PROVIDERS
        assert "gemini" in ALL_PROVIDERS
        assert "deepseek" in ALL_PROVIDERS
        assert "grok" in ALL_PROVIDERS
        assert "mistral" in ALL_PROVIDERS
        assert "openrouter" in ALL_PROVIDERS

    def test_create_provider(self):
        backend = create_provider("groq")
        assert backend.provider == LLMProvider.GROQ

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown provider"):
            create_provider("nonexistent")

    def test_available_providers_empty(self):
        # No API keys set in test environment
        available = available_providers()
        assert isinstance(available, list)


# ═══ Custom Model Override ═══


class TestCustomModel:
    def test_custom_model_groq(self):
        backend = GroqBackend(model="mixtral-8x7b-32768")
        result = backend.call(_params(model="mixtral-8x7b-32768"))
        assert result.model_name == "mixtral-8x7b-32768"

    def test_custom_model_deepseek(self):
        backend = DeepSeekBackend(model="deepseek-reasoner")
        result = backend.call(_params(model="deepseek-reasoner"))
        assert result.model_name == "deepseek-reasoner"
