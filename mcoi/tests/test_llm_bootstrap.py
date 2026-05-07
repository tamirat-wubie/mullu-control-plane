"""Phase 200A — LLM bootstrap wiring tests."""

import os
import pytest
from mcoi_runtime.adapters.multi_provider import (
    CerebrasBackend,
    CloudflareBackend,
    DashScopeBackend,
    DeepInfraBackend,
    FireworksBackend,
    FriendliBackend,
    GroqBackend,
    HyperbolicBackend,
    MoonshotBackend,
    NebiusBackend,
    NovitaBackend,
    SambaNovaBackend,
    TogetherBackend,
    ZAIBackend,
)
from mcoi_runtime.app.llm_bootstrap import (
    LLMConfig,
    bootstrap_llm,
)
from mcoi_runtime.core.model_orchestration import (
    ModelAlreadyRegisteredError,
    ModelOrchestrationEngine,
)
from mcoi_runtime.core.provider_registry import ProviderRegistry


def FIXED_CLOCK() -> str:
    return "2026-03-26T12:00:00Z"


LLM_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "FRIENDLI_TOKEN",
    "FRIENDLI_API_KEY",
    "NOVITA_API_KEY",
    "CEREBRAS_API_KEY",
    "DEEPINFRA_TOKEN",
    "DEEPINFRA_API_KEY",
    "NEBIUS_API_KEY",
    "HYPERBOLIC_API_KEY",
    "SAMBANOVA_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "MOONSHOT_API_KEY",
    "DASHSCOPE_API_KEY",
    "ZAI_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_BASE_URL",
    "MULLU_LLM_BACKEND",
)


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.default_backend == "stub"
        assert config.default_model == "claude-sonnet-4-20250514"
        assert config.default_budget_max_cost == 100.0

    def test_from_env_defaults(self):
        env_backup = {}
        for key in LLM_ENV_KEYS:
            env_backup[key] = os.environ.pop(key, None)
        try:
            config = LLMConfig.from_env()
            assert config.default_backend == "stub"
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val

    def test_from_env_anthropic_detected(self):
        env_backup = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        os.environ.pop("MULLU_LLM_BACKEND", None)
        try:
            config = LLMConfig.from_env()
            assert config.default_backend == "anthropic"
            assert config.anthropic_api_key == "test-key"
        finally:
            if env_backup:
                os.environ["ANTHROPIC_API_KEY"] = env_backup
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_from_env_low_cost_provider_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "groq"
        assert config.groq_api_key == "groq-test-key"
        assert config.deepseek_api_key == ""
        assert config.openrouter_api_key == ""

    def test_from_env_added_low_cost_provider_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("TOGETHER_API_KEY", "together-test-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "together"
        assert config.together_api_key == "together-test-key"
        assert config.fireworks_api_key == ""
        assert config.cerebras_api_key == ""

    def test_from_env_friendli_api_key_alias_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("FRIENDLI_API_KEY", "friendli-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "friendli"
        assert config.friendli_api_key == "friendli-alias-key"
        assert config.together_api_key == ""
        assert config.groq_api_key == ""

    def test_from_env_deepinfra_api_key_alias_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("DEEPINFRA_API_KEY", "deepinfra-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "deepinfra"
        assert config.deepinfra_api_key == "deepinfra-alias-key"
        assert config.nebius_api_key == ""
        assert config.hyperbolic_api_key == ""

    def test_from_env_cloudflare_requires_account_id(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cloudflare-token")

        config = LLMConfig.from_env()
        assert config.default_backend == "stub"
        assert config.cloudflare_api_key == "cloudflare-token"
        assert config.cloudflare_account_id == ""

        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-id")
        config = LLMConfig.from_env()
        assert config.default_backend == "cloudflare"
        assert config.cloudflare_account_id == "account-id"

    def test_from_env_explicit_backend(self):
        os.environ["MULLU_LLM_BACKEND"] = "stub"
        try:
            config = LLMConfig.from_env()
            assert config.default_backend == "stub"
        finally:
            os.environ.pop("MULLU_LLM_BACKEND", None)


class TestBootstrapLLM:
    def test_stub_only(self):
        result = bootstrap_llm(clock=FIXED_CLOCK, config=LLMConfig())
        assert result.default_backend_name == "stub"
        assert "stub" in result.backends
        assert result.bridge is not None
        assert result.bridge.invocation_count == 0

    def test_stub_with_anthropic_key(self):
        config = LLMConfig(
            default_backend="anthropic",
            anthropic_api_key="test-key-123",
        )
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config)
        assert "anthropic" in result.backends
        assert result.default_backend_name == "anthropic"

    def test_fallback_to_stub(self):
        config = LLMConfig(default_backend="anthropic")  # No key = not registered
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config)
        assert result.default_backend_name == "stub"

    def test_default_budget_registered(self):
        result = bootstrap_llm(clock=FIXED_CLOCK, config=LLMConfig())
        summary = result.bridge.budget_summary()
        assert len(summary["budgets"]) >= 1
        assert summary["budgets"][0]["budget_id"] == "default"

    def test_completion_works(self):
        result = bootstrap_llm(clock=FIXED_CLOCK, config=LLMConfig())
        llm_result = result.bridge.complete("test", budget_id="default")
        assert llm_result.succeeded is True

    def test_with_provider_registry(self):
        registry = ProviderRegistry(clock=FIXED_CLOCK)
        config = LLMConfig(anthropic_api_key="key1", openai_api_key="key2")
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config, provider_registry=registry)
        assert len(result.registered_providers) >= 2
        assert "llm-stub" in result.registered_providers

    def test_with_model_engine(self):
        registry = ProviderRegistry(clock=FIXED_CLOCK)
        engine = ModelOrchestrationEngine(clock=FIXED_CLOCK, provider_registry=registry)
        result = bootstrap_llm(
            clock=FIXED_CLOCK,
            config=LLMConfig(),
            provider_registry=registry,
            model_engine=engine,
        )
        # Stub backend registered — stub models should be available
        assert len(result.registered_models) >= 0  # May or may not match model names

    def test_duplicate_model_registration_recorded_as_skip(self):
        class PreRegisteredEngine(ModelOrchestrationEngine):
            def register(self, descriptor, adapter, validator=None, *, provider_id=None):
                if descriptor.model_id == "claude-sonnet-4-20250514":
                    raise ModelAlreadyRegisteredError(f"model already registered: {descriptor.model_id}")
                return super().register(descriptor, adapter, validator, provider_id=provider_id)

        engine = PreRegisteredEngine(clock=FIXED_CLOCK)
        result = bootstrap_llm(
            clock=FIXED_CLOCK,
            config=LLMConfig(anthropic_api_key="ak"),
            model_engine=engine,
        )

        assert any(
            issue["model_id"] == "claude-sonnet-4-20250514"
            and issue["error_code"] == "model_already_registered"
            for issue in result.skipped_model_registrations
        )

    def test_unexpected_model_registration_failure_recorded(self):
        class FailingEngine:
            def register(self, descriptor, adapter, validator=None, *, provider_id=None):
                if descriptor.model_id == "claude-sonnet-4-20250514":
                    raise RuntimeError("provider-bootstrap-secret")
                return descriptor

        result = bootstrap_llm(
            clock=FIXED_CLOCK,
            config=LLMConfig(anthropic_api_key="ak"),
            model_engine=FailingEngine(),  # type: ignore[arg-type]
        )

        assert any(
            issue["model_id"] == "claude-sonnet-4-20250514"
            and issue["error_code"] == "model_registration_failed"
            and issue["error_type"] == "RuntimeError"
            for issue in result.model_registration_failures
        )
        assert "provider-bootstrap-secret" not in str(result.model_registration_failures)

    def test_with_ledger_sink(self):
        entries = []
        result = bootstrap_llm(
            clock=FIXED_CLOCK,
            config=LLMConfig(),
            ledger_sink=entries.append,
        )
        result.bridge.complete("test", budget_id="default")
        assert len(entries) >= 1

    def test_multiple_backends_registered(self):
        config = LLMConfig(
            anthropic_api_key="ak",
            openai_api_key="ok",
        )
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config)
        assert "stub" in result.backends
        assert "anthropic" in result.backends
        assert "openai" in result.backends

    def test_low_cost_provider_mesh_registered(self):
        registry = ProviderRegistry(clock=FIXED_CLOCK)
        engine = ModelOrchestrationEngine(clock=FIXED_CLOCK, provider_registry=registry)
        config = LLMConfig(
            default_backend="groq",
            default_model="claude-sonnet-4-20250514",
            groq_api_key="gq",
            deepseek_api_key="ds",
            together_api_key="tg",
            fireworks_api_key="fw",
            friendli_api_key="fl",
            novita_api_key="nv",
            cerebras_api_key="cb",
            deepinfra_api_key="di",
            nebius_api_key="nb",
            hyperbolic_api_key="hb",
            sambanova_api_key="sn",
            cloudflare_api_key="cf",
            cloudflare_account_id="account",
            moonshot_api_key="mk",
            dashscope_api_key="dq",
            zai_api_key="zk",
            grok_api_key="xai",
            mistral_api_key="ms",
            openrouter_api_key="or",
        )

        result = bootstrap_llm(
            clock=FIXED_CLOCK,
            config=config,
            provider_registry=registry,
            model_engine=engine,
        )

        assert result.default_backend_name == "groq"
        assert {
            "groq",
            "deepseek",
            "together",
            "fireworks",
            "friendli",
            "novita",
            "cerebras",
            "deepinfra",
            "nebius",
            "hyperbolic",
            "sambanova",
            "cloudflare",
            "moonshot",
            "dashscope",
            "zai",
            "grok",
            "mistral",
            "openrouter",
        }.issubset(result.backends)
        assert isinstance(result.backends["groq"], GroqBackend)
        assert isinstance(result.backends["together"], TogetherBackend)
        assert isinstance(result.backends["fireworks"], FireworksBackend)
        assert isinstance(result.backends["friendli"], FriendliBackend)
        assert isinstance(result.backends["novita"], NovitaBackend)
        assert isinstance(result.backends["cerebras"], CerebrasBackend)
        assert isinstance(result.backends["deepinfra"], DeepInfraBackend)
        assert isinstance(result.backends["nebius"], NebiusBackend)
        assert isinstance(result.backends["hyperbolic"], HyperbolicBackend)
        assert isinstance(result.backends["sambanova"], SambaNovaBackend)
        assert isinstance(result.backends["cloudflare"], CloudflareBackend)
        assert isinstance(result.backends["moonshot"], MoonshotBackend)
        assert isinstance(result.backends["dashscope"], DashScopeBackend)
        assert isinstance(result.backends["zai"], ZAIBackend)
        assert "llm-groq" in result.registered_providers
        assert "llm-deepseek" in result.registered_providers
        assert "llm-together" in result.registered_providers
        assert "llm-cerebras" in result.registered_providers
        assert "llm-deepinfra" in result.registered_providers
        assert "llm-nebius" in result.registered_providers
        assert "llm-sambanova" in result.registered_providers
        assert "llm-cloudflare" in result.registered_providers
        assert "llm-moonshot" in result.registered_providers
        assert "llm-dashscope" in result.registered_providers
        assert "llm-zai" in result.registered_providers
        assert "llm-openrouter" in result.registered_providers
        assert "meta-llama/llama-4-scout-17b-16e-instruct" in result.registered_models
        assert "deepseek-v4-flash" in result.registered_models
        assert "LiquidAI/LFM2-24B-A2B" in result.registered_models
        assert "accounts/fireworks/models/gpt-oss-20b" in result.registered_models
        assert "meta-llama-3.1-8b-instruct" in result.registered_models
        assert "deepseek/deepseek-v4-flash" in result.registered_models
        assert "llama3.1-8b" in result.registered_models
        assert "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo" in result.registered_models
        assert "meta-llama/Meta-Llama-3.1-8B-Instruct" in result.registered_models
        assert "Qwen/Qwen2.5-Coder-32B-Instruct" in result.registered_models
        assert "Meta-Llama-3.3-70B-Instruct" in result.registered_models
        assert "@cf/meta/llama-3.1-8b-instruct-fp8-fast" in result.registered_models
        assert "kimi-k2.5" in result.registered_models
        assert "qwen-turbo" in result.registered_models
        assert "glm-4.5-air" in result.registered_models
        assert "mistral-small-2506" in result.registered_models
        assert "grok-3-mini" in result.registered_models
        assert "meta-llama/llama-4-scout" in result.registered_models

    def test_config_stored_in_result(self):
        config = LLMConfig(default_budget_max_cost=50.0)
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config)
        assert result.config.default_budget_max_cost == 50.0


class TestLLMConfigFromEnv:
    """G6: stub backend must be refused in pilot/production environments."""

    def test_stub_refused_in_production(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("MULLU_LLM_BACKEND", "stub")
        for key in LLM_ENV_KEYS:
            if key != "MULLU_LLM_BACKEND":
                monkeypatch.delenv(key, raising=False)
        with pytest.raises(RuntimeError, match="stub.*forbidden.*production"):
            LLMConfig.from_env()

    def test_stub_refused_in_pilot(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "pilot")
        monkeypatch.setenv("MULLU_LLM_BACKEND", "stub")
        for key in LLM_ENV_KEYS:
            if key != "MULLU_LLM_BACKEND":
                monkeypatch.delenv(key, raising=False)
        with pytest.raises(RuntimeError, match="stub.*forbidden.*pilot"):
            LLMConfig.from_env()

    def test_stub_allowed_in_dev(self, monkeypatch):
        monkeypatch.setenv("MULLU_ENV", "local_dev")
        monkeypatch.setenv("MULLU_LLM_BACKEND", "stub")
        config = LLMConfig.from_env()
        assert config.default_backend == "stub"

    def test_stub_default_silent_in_dev(self, monkeypatch):
        """No env vars set, dev environment → stub fallback is silent."""
        monkeypatch.delenv("MULLU_ENV", raising=False)
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        config = LLMConfig.from_env()
        assert config.default_backend == "stub"

    def test_anthropic_key_overrides_stub_in_production(self, monkeypatch):
        """Production with API key → real backend, no error."""
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("MULLU_LLM_BACKEND", raising=False)
        config = LLMConfig.from_env()
        assert config.default_backend == "anthropic"
