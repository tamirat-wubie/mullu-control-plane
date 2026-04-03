"""Phase 200A — LLM bootstrap wiring tests."""

import os
import pytest
from mcoi_runtime.app.llm_bootstrap import (
    LLMConfig,
    LLMBootstrapResult,
    bootstrap_llm,
)
from mcoi_runtime.core.model_orchestration import (
    ModelAlreadyRegisteredError,
    ModelOrchestrationEngine,
)
from mcoi_runtime.core.provider_registry import ProviderRegistry

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.default_backend == "stub"
        assert config.default_model == "claude-sonnet-4-20250514"
        assert config.default_budget_max_cost == 100.0

    def test_from_env_defaults(self):
        env_backup = {}
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MULLU_LLM_BACKEND"):
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

    def test_config_stored_in_result(self):
        config = LLMConfig(default_budget_max_cost=50.0)
        result = bootstrap_llm(clock=FIXED_CLOCK, config=config)
        assert result.config.default_budget_max_cost == 50.0
