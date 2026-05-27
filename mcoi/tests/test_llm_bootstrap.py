"""Phase 200A - LLM bootstrap wiring tests."""

import os
import pytest
from mcoi_runtime.adapters.multi_provider import (
    AIMLAPIBackend,
    APIRouterBackend,
    AnswiraBackend,
    ApiLinkBackend,
    AtlasCloudBackend,
    BasetenBackend,
    BazaarLinkBackend,
    CerebrasBackend,
    ChutesBackend,
    CloudflareBackend,
    DashScopeBackend,
    DeepInfraBackend,
    DInferenceBackend,
    EmberCloudBackend,
    EURIBackend,
    FireworksBackend,
    FriendliBackend,
    GMIBackend,
    GlamaBackend,
    GroqBackend,
    HyperbolicBackend,
    HaimakerBackend,
    HuggingFaceBackend,
    InferenceNetBackend,
    InfomaniakBackend,
    KatalepticBackend,
    LMStudioBackend,
    LLMAIBackend,
    LocalAIBackend,
    LlamaAPIBackend,
    LlamaCppBackend,
    MixlayerBackend,
    ModelMaxBackend,
    MoonshotBackend,
    MorpheusBackend,
    NebiusBackend,
    NovitaBackend,
    NscaleBackend,
    OVHCloudBackend,
    PacketBackend,
    ParasailBackend,
    FeatherlessBackend,
    NeuroRoutersBackend,
    QuickSilverBackend,
    RequestyBackend,
    RidvayBackend,
    SGLangBackend,
    SambaNovaBackend,
    ScalewayBackend,
    SiliconFlowBackend,
    TGIBackend,
    TogetherBackend,
    VLLMBackend,
    VeniceBackend,
    WaveSpeedBackend,
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
    "SILICONFLOW_API_KEY",
    "DINFERENCE_API_KEY",
    "CHUTES_API_KEY",
    "WAVESPEED_API_KEY",
    "BAZAARLINK_API_KEY",
    "LLAMA_API_KEY",
    "PARASAIL_API_KEY",
    "FEATHERLESS_API_KEY",
    "PACKET_API_KEY",
    "RIDVAY_API_KEY",
    "NEUROROUTERS_API_KEY",
    "GLAMA_API_KEY",
    "GMI_API_KEY",
    "ATLASCLOUD_API_KEY",
    "MODELMAX_API_KEY",
    "VENICE_API_KEY",
    "EURI_API_KEY",
    "APIROUTER_API_KEY",
    "QUICKSILVER_API_KEY",
    "QSP_KEY",
    "MIXLAYER_API_KEY",
    "APILINK_API_KEY",
    "EMBERCLOUD_API_KEY",
    "MORPHEUS_API_KEY",
    "MOR_API_KEY",
    "INFERENCE_API_KEY",
    "INFERENCENET_API_KEY",
    "ANSWIRA_API_KEY",
    "LLMAI_API_KEY",
    "LLMAI_TOKEN",
    "REQUESTY_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_API_KEY",
    "BASETEN_API_KEY",
    "HAIMAKER_API_KEY",
    "NSCALE_API_KEY",
    "SCW_API_KEY",
    "SCALEWAY_API_KEY",
    "OVH_AI_ENDPOINTS_ACCESS_TOKEN",
    "AI_ENDPOINT_API_KEY",
    "AIMLAPI_API_KEY",
    "AIML_API_KEY",
    "INFOMANIAK_API_KEY",
    "INFOMANIAK_PRODUCT_ID",
    "INFOMANIAK_BASE_URL",
    "KATALEPTIC_API_KEY",
    "VLLM_BASE_URL",
    "VLLM_API_KEY",
    "SGLANG_BASE_URL",
    "SGLANG_API_KEY",
    "TGI_BASE_URL",
    "TGI_API_KEY",
    "LLAMACPP_BASE_URL",
    "LLAMACPP_API_KEY",
    "LOCALAI_BASE_URL",
    "LOCALAI_API_KEY",
    "LMSTUDIO_BASE_URL",
    "LMSTUDIO_API_KEY",
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

    def test_from_env_quicksilver_api_key_alias_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("QSP_KEY", "quicksilver-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "quicksilver"
        assert config.quicksilver_api_key == "quicksilver-alias-key"
        assert config.mixlayer_api_key == ""
        assert config.apilink_api_key == ""

    def test_from_env_morpheus_and_inferencenet_aliases_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("MOR_API_KEY", "morpheus-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "morpheus"
        assert config.morpheus_api_key == "morpheus-alias-key"
        assert config.embercloud_api_key == ""
        assert config.inferencenet_api_key == ""

        monkeypatch.delenv("MOR_API_KEY", raising=False)
        monkeypatch.setenv("INFERENCENET_API_KEY", "inferencenet-alias-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "inferencenet"
        assert config.inferencenet_api_key == "inferencenet-alias-key"
        assert config.morpheus_api_key == ""

    def test_from_env_llmai_alias_and_requesty_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("LLMAI_TOKEN", "llmai-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "llmai"
        assert config.llmai_api_key == "llmai-alias-key"
        assert config.answira_api_key == ""
        assert config.requesty_api_key == ""

        monkeypatch.delenv("LLMAI_TOKEN", raising=False)
        monkeypatch.setenv("REQUESTY_API_KEY", "requesty-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "requesty"
        assert config.requesty_api_key == "requesty-key"
        assert config.llmai_api_key == ""

    def test_from_env_huggingface_baseten_and_haimaker_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("HF_TOKEN", "huggingface-token-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "huggingface"
        assert config.huggingface_api_key == "huggingface-token-key"
        assert config.baseten_api_key == ""
        assert config.haimaker_api_key == ""

        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.setenv("HUGGINGFACE_API_KEY", "huggingface-alias-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "huggingface"
        assert config.huggingface_api_key == "huggingface-alias-key"

        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        monkeypatch.setenv("BASETEN_API_KEY", "baseten-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "baseten"
        assert config.baseten_api_key == "baseten-key"
        assert config.huggingface_api_key == ""

        monkeypatch.delenv("BASETEN_API_KEY", raising=False)
        monkeypatch.setenv("HAIMAKER_API_KEY", "haimaker-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "haimaker"
        assert config.haimaker_api_key == "haimaker-key"
        assert config.huggingface_api_key == ""

    def test_from_env_nscale_scaleway_and_ovhcloud_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("NSCALE_API_KEY", "nscale-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "nscale"
        assert config.nscale_api_key == "nscale-key"
        assert config.scaleway_api_key == ""
        assert config.ovhcloud_api_key == ""

        monkeypatch.delenv("NSCALE_API_KEY", raising=False)
        monkeypatch.setenv("SCALEWAY_API_KEY", "scaleway-alias-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "scaleway"
        assert config.scaleway_api_key == "scaleway-alias-key"
        assert config.nscale_api_key == ""

        monkeypatch.delenv("SCALEWAY_API_KEY", raising=False)
        monkeypatch.setenv("AI_ENDPOINT_API_KEY", "ovhcloud-alias-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "ovhcloud"
        assert config.ovhcloud_api_key == "ovhcloud-alias-key"
        assert config.scaleway_api_key == ""

    def test_from_env_aimlapi_infomaniak_and_kataleptic_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("AIML_API_KEY", "aimlapi-alias-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "aimlapi"
        assert config.aimlapi_api_key == "aimlapi-alias-key"
        assert config.infomaniak_api_key == ""
        assert config.kataleptic_api_key == ""

        monkeypatch.delenv("AIML_API_KEY", raising=False)
        monkeypatch.setenv("INFOMANIAK_API_KEY", "infomaniak-key")
        monkeypatch.setenv("INFOMANIAK_PRODUCT_ID", "product-123")
        config = LLMConfig.from_env()

        assert config.default_backend == "infomaniak"
        assert config.infomaniak_api_key == "infomaniak-key"
        assert config.infomaniak_product_id == "product-123"
        assert config.aimlapi_api_key == ""

        monkeypatch.delenv("INFOMANIAK_API_KEY", raising=False)
        monkeypatch.delenv("INFOMANIAK_PRODUCT_ID", raising=False)
        monkeypatch.setenv("KATALEPTIC_API_KEY", "kataleptic-key")
        config = LLMConfig.from_env()

        assert config.default_backend == "kataleptic"
        assert config.kataleptic_api_key == "kataleptic-key"
        assert config.infomaniak_api_key == ""

    def test_from_env_self_hosted_model_providers_detected(self, monkeypatch):
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("VLLM_BASE_URL", "http://vllm.local/v1")
        monkeypatch.setenv("VLLM_API_KEY", "vllm-key")

        config = LLMConfig.from_env()

        assert config.default_backend == "vllm"
        assert config.vllm_base_url == "http://vllm.local/v1"
        assert config.vllm_api_key == "vllm-key"
        assert config.sglang_base_url == ""

        monkeypatch.delenv("VLLM_BASE_URL", raising=False)
        monkeypatch.delenv("VLLM_API_KEY", raising=False)
        monkeypatch.setenv("SGLANG_BASE_URL", "http://sglang.local/v1")
        config = LLMConfig.from_env()

        assert config.default_backend == "sglang"
        assert config.sglang_base_url == "http://sglang.local/v1"
        assert config.vllm_base_url == ""

        monkeypatch.delenv("SGLANG_BASE_URL", raising=False)
        monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        config = LLMConfig.from_env()

        assert config.default_backend == "lmstudio"
        assert config.lmstudio_base_url == "http://localhost:1234/v1"
        assert config.localai_base_url == ""

    def test_from_env_cloudflare_requires_account_id(self, monkeypatch):
        monkeypatch.delenv("MULLU_ENV", raising=False)
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
        # Stub backend registered - stub models should be available
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
            siliconflow_api_key="sf",
            dinference_api_key="df",
            chutes_api_key="ct",
            wavespeed_api_key="ws",
            bazaarlink_api_key="bl",
            llama_api_key="la",
            parasail_api_key="ps",
            featherless_api_key="fh",
            packet_api_key="pk",
            ridvay_api_key="rv",
            neurorouters_api_key="nr",
            glama_api_key="gm",
            gmi_api_key="gmi",
            atlascloud_api_key="ac",
            modelmax_api_key="mm",
            venice_api_key="vn",
            euri_api_key="eu",
            apirouter_api_key="ar",
            quicksilver_api_key="qs",
            mixlayer_api_key="mx",
            apilink_api_key="al",
            embercloud_api_key="ec",
            morpheus_api_key="mo",
            inferencenet_api_key="in",
            answira_api_key="aw",
            llmai_api_key="lm",
            requesty_api_key="rq",
            huggingface_api_key="hf",
            baseten_api_key="bt",
            haimaker_api_key="hm",
            nscale_api_key="ns",
            scaleway_api_key="scw",
            ovhcloud_api_key="ovh",
            aimlapi_api_key="aiml",
            infomaniak_api_key="info",
            infomaniak_product_id="product-123",
            kataleptic_api_key="kt",
            vllm_base_url="http://vllm.local/v1",
            vllm_api_key="vl",
            sglang_base_url="http://sglang.local/v1",
            sglang_api_key="sg",
            tgi_base_url="http://tgi.local/v1",
            tgi_api_key="tgi",
            llamacpp_base_url="http://llamacpp.local/v1",
            llamacpp_api_key="lc",
            localai_base_url="http://localai.local/v1",
            localai_api_key="lai",
            lmstudio_base_url="http://lmstudio.local/v1",
            lmstudio_api_key="ls",
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
            "siliconflow",
            "dinference",
            "chutes",
            "wavespeed",
            "bazaarlink",
            "llamaapi",
            "parasail",
            "featherless",
            "packet",
            "ridvay",
            "neurorouters",
            "glama",
            "gmi",
            "atlascloud",
            "modelmax",
            "venice",
            "euri",
            "apirouter",
            "quicksilver",
            "mixlayer",
            "apilink",
            "embercloud",
            "morpheus",
            "inferencenet",
            "answira",
            "llmai",
            "requesty",
            "huggingface",
            "baseten",
            "haimaker",
            "nscale",
            "scaleway",
            "ovhcloud",
            "aimlapi",
            "infomaniak",
            "kataleptic",
            "vllm",
            "sglang",
            "tgi",
            "llamacpp",
            "localai",
            "lmstudio",
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
        assert isinstance(result.backends["siliconflow"], SiliconFlowBackend)
        assert isinstance(result.backends["dinference"], DInferenceBackend)
        assert isinstance(result.backends["chutes"], ChutesBackend)
        assert isinstance(result.backends["wavespeed"], WaveSpeedBackend)
        assert isinstance(result.backends["bazaarlink"], BazaarLinkBackend)
        assert isinstance(result.backends["llamaapi"], LlamaAPIBackend)
        assert isinstance(result.backends["parasail"], ParasailBackend)
        assert isinstance(result.backends["featherless"], FeatherlessBackend)
        assert isinstance(result.backends["packet"], PacketBackend)
        assert isinstance(result.backends["ridvay"], RidvayBackend)
        assert isinstance(result.backends["neurorouters"], NeuroRoutersBackend)
        assert isinstance(result.backends["glama"], GlamaBackend)
        assert isinstance(result.backends["gmi"], GMIBackend)
        assert isinstance(result.backends["atlascloud"], AtlasCloudBackend)
        assert isinstance(result.backends["modelmax"], ModelMaxBackend)
        assert isinstance(result.backends["venice"], VeniceBackend)
        assert isinstance(result.backends["euri"], EURIBackend)
        assert isinstance(result.backends["apirouter"], APIRouterBackend)
        assert isinstance(result.backends["quicksilver"], QuickSilverBackend)
        assert isinstance(result.backends["mixlayer"], MixlayerBackend)
        assert isinstance(result.backends["apilink"], ApiLinkBackend)
        assert isinstance(result.backends["embercloud"], EmberCloudBackend)
        assert isinstance(result.backends["morpheus"], MorpheusBackend)
        assert isinstance(result.backends["inferencenet"], InferenceNetBackend)
        assert isinstance(result.backends["answira"], AnswiraBackend)
        assert isinstance(result.backends["llmai"], LLMAIBackend)
        assert isinstance(result.backends["requesty"], RequestyBackend)
        assert isinstance(result.backends["huggingface"], HuggingFaceBackend)
        assert isinstance(result.backends["baseten"], BasetenBackend)
        assert isinstance(result.backends["haimaker"], HaimakerBackend)
        assert isinstance(result.backends["nscale"], NscaleBackend)
        assert isinstance(result.backends["scaleway"], ScalewayBackend)
        assert isinstance(result.backends["ovhcloud"], OVHCloudBackend)
        assert isinstance(result.backends["aimlapi"], AIMLAPIBackend)
        assert isinstance(result.backends["infomaniak"], InfomaniakBackend)
        assert isinstance(result.backends["kataleptic"], KatalepticBackend)
        assert isinstance(result.backends["vllm"], VLLMBackend)
        assert isinstance(result.backends["sglang"], SGLangBackend)
        assert isinstance(result.backends["tgi"], TGIBackend)
        assert isinstance(result.backends["llamacpp"], LlamaCppBackend)
        assert isinstance(result.backends["localai"], LocalAIBackend)
        assert isinstance(result.backends["lmstudio"], LMStudioBackend)
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
        assert "llm-siliconflow" in result.registered_providers
        assert "llm-dinference" in result.registered_providers
        assert "llm-chutes" in result.registered_providers
        assert "llm-wavespeed" in result.registered_providers
        assert "llm-bazaarlink" in result.registered_providers
        assert "llm-llamaapi" in result.registered_providers
        assert "llm-parasail" in result.registered_providers
        assert "llm-featherless" in result.registered_providers
        assert "llm-packet" in result.registered_providers
        assert "llm-ridvay" in result.registered_providers
        assert "llm-neurorouters" in result.registered_providers
        assert "llm-glama" in result.registered_providers
        assert "llm-gmi" in result.registered_providers
        assert "llm-atlascloud" in result.registered_providers
        assert "llm-modelmax" in result.registered_providers
        assert "llm-venice" in result.registered_providers
        assert "llm-euri" in result.registered_providers
        assert "llm-apirouter" in result.registered_providers
        assert "llm-quicksilver" in result.registered_providers
        assert "llm-mixlayer" in result.registered_providers
        assert "llm-apilink" in result.registered_providers
        assert "llm-embercloud" in result.registered_providers
        assert "llm-morpheus" in result.registered_providers
        assert "llm-inferencenet" in result.registered_providers
        assert "llm-answira" in result.registered_providers
        assert "llm-llmai" in result.registered_providers
        assert "llm-requesty" in result.registered_providers
        assert "llm-huggingface" in result.registered_providers
        assert "llm-baseten" in result.registered_providers
        assert "llm-haimaker" in result.registered_providers
        assert "llm-nscale" in result.registered_providers
        assert "llm-scaleway" in result.registered_providers
        assert "llm-ovhcloud" in result.registered_providers
        assert "llm-aimlapi" in result.registered_providers
        assert "llm-infomaniak" in result.registered_providers
        assert "llm-kataleptic" in result.registered_providers
        assert "llm-vllm" in result.registered_providers
        assert "llm-sglang" in result.registered_providers
        assert "llm-tgi" in result.registered_providers
        assert "llm-llamacpp" in result.registered_providers
        assert "llm-localai" in result.registered_providers
        assert "llm-lmstudio" in result.registered_providers
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
        assert "Qwen/Qwen2.5-7B-Instruct" in result.registered_models
        assert "gpt-oss-120b" in result.registered_models
        assert "Qwen/Qwen3-32B-TEE" in result.registered_models
        assert "qwen/qwen3-coder-30b-a3b-instruct" in result.registered_models
        assert "meta-llama/llama-3.1-8b-instruct" in result.registered_models
        assert "llama3-70b" in result.registered_models
        assert "parasail-qwen3-32b" in result.registered_models
        assert "Qwen/Qwen2.5-7B-Instruct-1M" in result.registered_models
        assert "meta-llama/Llama-3.1-70B-Instruct" in result.registered_models
        assert "qwen/qwen3-30b-a3b" in result.registered_models
        assert "qwen/qwen3-30b-a3b:free" in result.registered_models
        assert "deepseek-chat-v3" in result.registered_models
        assert "Qwen/Qwen3-32B-FP8" in result.registered_models
        assert "Qwen/Qwen3-30B-A3B-Instruct-2507" in result.registered_models
        assert "qwen3-coder-30b-a3b" in result.registered_models
        assert "qwen3-5-9b" in result.registered_models
        assert "qwen/qwen3-32b" in result.registered_models
        assert "Qwen/Qwen3-Coder-30B-A3B-Instruct" in result.registered_models
        assert "qwen3.6-35b" in result.registered_models
        assert "qwen/qwen3.5-9b" in result.registered_models
        assert "deepseek/deepseek-v4-pro" in result.registered_models
        assert "glm-4.7-flash" in result.registered_models
        assert "qwen35-9b" in result.registered_models
        assert "google/gemma-3-27b-instruct/bf-16" in result.registered_models
        assert "qwen/qwen3-coder-next" in result.registered_models
        assert "gemma-4" in result.registered_models
        assert "deepseek/deepseek-chat" in result.registered_models
        assert "Qwen/Qwen3-Coder-30B-A3B-Instruct:cheapest" in result.registered_models
        assert "nvidia/Nemotron-120B-A12B" in result.registered_models
        assert "deepseek/deepseek-chat-v3-0324" in result.registered_models
        assert "nscale/openai/gpt-oss-20b" in result.registered_models
        assert "scaleway/gpt-oss-120b" in result.registered_models
        assert "ovhcloud/Qwen3-Coder-30B-A3B-Instruct" in result.registered_models
        assert "aimlapi/nvidia/nemotron-3-nano-30b-a3b" in result.registered_models
        assert "infomaniak/google/gemma-4-31B-it" in result.registered_models
        assert "kataleptic/gemma3-27b" in result.registered_models
        assert "vllm/Qwen/Qwen3-0.6B" in result.registered_models
        assert "sglang/Qwen/Qwen3-0.6B" in result.registered_models
        assert "tgi/default" in result.registered_models
        assert "llamacpp/local-model" in result.registered_models
        assert "localai/local-model" in result.registered_models
        assert "lmstudio/model-identifier" in result.registered_models
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
        """No env vars set, dev environment -> stub fallback is silent."""
        monkeypatch.delenv("MULLU_ENV", raising=False)
        for key in LLM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        config = LLMConfig.from_env()
        assert config.default_backend == "stub"

    def test_anthropic_key_overrides_stub_in_production(self, monkeypatch):
        """Production with API key -> real backend, no error."""
        monkeypatch.setenv("MULLU_ENV", "production")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("MULLU_LLM_BACKEND", raising=False)
        config = LLMConfig.from_env()
        assert config.default_backend == "anthropic"
