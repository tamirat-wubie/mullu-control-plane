"""Purpose: verify Gemini and Ollama LLM backend contracts and bootstrap wiring.
Governance scope: Tier 2/3 provider backend tests only.
Dependencies: LLM adapter backends, contracts, bootstrap.
Invariants: backends conform to LLMBackend protocol; costs are correct;
  errors never propagate as exceptions.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mcoi_runtime.adapters.llm_adapter import GeminiBackend, OllamaBackend
from mcoi_runtime.contracts.llm import (
    LLMInvocationParams,
    LLMMessage,
    LLMProvider,
    LLMRole,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_params(prompt: str = "Hello", model: str = "") -> LLMInvocationParams:
    return LLMInvocationParams(
        model_name=model or "test-model",
        messages=(LLMMessage(role=LLMRole.USER, content=prompt),),
        max_tokens=256,
    )


# --- LLMProvider enum ---


def test_llm_provider_declares_hosted_provider_mesh() -> None:
    expected_providers = {
        LLMProvider.ANTHROPIC,
        LLMProvider.OPENAI,
        LLMProvider.GEMINI,
        LLMProvider.GROQ,
        LLMProvider.DEEPSEEK,
        LLMProvider.TOGETHER,
        LLMProvider.FIREWORKS,
        LLMProvider.FRIENDLI,
        LLMProvider.NOVITA,
        LLMProvider.CEREBRAS,
        LLMProvider.GROK,
        LLMProvider.MISTRAL,
        LLMProvider.OPENROUTER,
        LLMProvider.OLLAMA,
        LLMProvider.STUB,
    }
    assert len(LLMProvider) == len(expected_providers)
    assert expected_providers == set(LLMProvider)


# --- GeminiBackend ---


def test_gemini_provider_is_gemini() -> None:
    backend = GeminiBackend(api_key="test-key")
    assert backend.provider == LLMProvider.GEMINI


def test_gemini_missing_sdk_returns_error() -> None:
    backend = GeminiBackend(api_key="test-key")
    backend._sdk_available = False
    with pytest.raises(Exception, match="google-generativeai SDK"):
        backend._get_model("gemini-2.0-flash")


def test_gemini_missing_key_returns_error() -> None:
    backend = GeminiBackend(api_key="")
    backend._sdk_available = True
    with pytest.raises(Exception, match="GEMINI_API_KEY"):
        backend._get_model("gemini-2.0-flash")


def test_gemini_cost_flash_is_low() -> None:
    backend = GeminiBackend(api_key="test-key")
    cost = backend._estimate_cost("gemini-2.0-flash", 1000, 500)
    assert cost < 0.001  # Very cheap


def test_gemini_cost_flash_lite_is_lower_than_flash() -> None:
    backend = GeminiBackend(api_key="test-key")
    flash_cost = backend._estimate_cost("gemini-2.0-flash", 1000, 500)
    lite_cost = backend._estimate_cost("gemini-2.0-flash-lite", 1000, 500)
    assert lite_cost > 0.0
    assert lite_cost < flash_cost


def test_gemini_default_model() -> None:
    backend = GeminiBackend(api_key="test-key")
    assert backend._default_model == "gemini-2.0-flash"


def test_gemini_custom_model() -> None:
    backend = GeminiBackend(api_key="test-key", default_model="gemini-1.5-pro")
    assert backend._default_model == "gemini-1.5-pro"


def test_gemini_call_error_returns_llm_result() -> None:
    backend = GeminiBackend(api_key="test-key")
    backend._sdk_available = True

    with patch.object(backend, "_get_model", side_effect=RuntimeError("connection failed")):
        result = backend.call(_make_params())
        assert not result.succeeded
        assert result.error == "provider error (RuntimeError)"
        assert "connection failed" not in result.error
        assert result.provider == LLMProvider.GEMINI


# --- OllamaBackend ---


def test_ollama_provider_is_ollama() -> None:
    backend = OllamaBackend()
    assert backend.provider == LLMProvider.OLLAMA


def test_ollama_default_model() -> None:
    backend = OllamaBackend()
    assert backend._default_model == "llama3.2"


def test_ollama_custom_model() -> None:
    backend = OllamaBackend(default_model="mistral")
    assert backend._default_model == "mistral"


def test_ollama_default_url() -> None:
    backend = OllamaBackend()
    assert backend._base_url == "http://localhost:11434"


def test_ollama_custom_url() -> None:
    backend = OllamaBackend(base_url="http://gpu-server:11434")
    assert backend._base_url == "http://gpu-server:11434"


def test_ollama_cost_is_always_zero() -> None:
    """Ollama is local inference — cost is always zero."""
    backend = OllamaBackend()
    # Simulate a successful call result
    params = _make_params()
    # Connection will fail (no Ollama running), but verify cost model
    result = backend.call(params)
    assert result.cost == 0.0


def test_ollama_connection_error_returns_llm_result() -> None:
    backend = OllamaBackend(base_url="http://localhost:99999")
    result = backend.call(_make_params())
    assert not result.succeeded
    assert result.error  # Some connection error
    assert result.provider == LLMProvider.OLLAMA
    assert result.cost == 0.0


def test_ollama_timeout_error_is_redacted() -> None:
    backend = OllamaBackend()
    with patch("urllib.request.urlopen", side_effect=TimeoutError("secret timeout detail")):
        result = backend.call(_make_params())
    assert not result.succeeded
    assert result.error == "provider timeout (TimeoutError)"
    assert "secret timeout detail" not in result.error


# --- Bootstrap wiring ---


def test_bootstrap_registers_gemini_backend() -> None:
    from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm

    config = LLMConfig(
        default_backend="gemini",
        gemini_api_key="test-gemini-key",
    )
    result = bootstrap_llm(clock=lambda: _CLOCK, config=config)
    assert "gemini" in result.backends
    assert isinstance(result.backends["gemini"], GeminiBackend)
    assert result.default_backend_name == "gemini"


def test_bootstrap_registers_ollama_backend() -> None:
    from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm

    config = LLMConfig(
        default_backend="ollama",
        ollama_base_url="http://localhost:11434",
    )
    result = bootstrap_llm(clock=lambda: _CLOCK, config=config)
    assert "ollama" in result.backends
    assert isinstance(result.backends["ollama"], OllamaBackend)
    assert result.default_backend_name == "ollama"


def test_bootstrap_all_providers_registered() -> None:
    from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm

    config = LLMConfig(
        default_backend="stub",
        anthropic_api_key="ak",
        openai_api_key="ok",
        gemini_api_key="gk",
        ollama_base_url="http://localhost:11434",
    )
    result = bootstrap_llm(clock=lambda: _CLOCK, config=config)
    assert set(result.backends.keys()) == {"stub", "anthropic", "openai", "gemini", "ollama"}


def test_bootstrap_no_gemini_without_key() -> None:
    from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm

    config = LLMConfig(default_backend="stub")
    result = bootstrap_llm(clock=lambda: _CLOCK, config=config)
    assert "gemini" not in result.backends
    assert "ollama" not in result.backends
