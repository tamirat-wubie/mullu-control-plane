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
from mcoi_runtime.adapters.multi_provider import (
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
    DeepSeekBackend,
    DeepInfraBackend,
    DInferenceBackend,
    EmberCloudBackend,
    EURIBackend,
    FeatherlessBackend,
    FireworksBackend,
    FriendliBackend,
    GMIBackend,
    GlamaBackend,
    GrokBackend,
    GroqBackend,
    HyperbolicBackend,
    HaimakerBackend,
    HuggingFaceBackend,
    InferenceNetBackend,
    LLMAIBackend,
    LlamaAPIBackend,
    MixlayerBackend,
    MistralBackend,
    ModelMaxBackend,
    MoonshotBackend,
    MorpheusBackend,
    NebiusBackend,
    NovitaBackend,
    OpenRouterBackend,
    PacketBackend,
    ParasailBackend,
    NeuroRoutersBackend,
    QuickSilverBackend,
    RequestyBackend,
    RidvayBackend,
    SambaNovaBackend,
    SiliconFlowBackend,
    TogetherBackend,
    VeniceBackend,
    WaveSpeedBackend,
    ZAIBackend,
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

    default_backend: str = "stub"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    together_api_key: str = ""
    fireworks_api_key: str = ""
    friendli_api_key: str = ""
    novita_api_key: str = ""
    cerebras_api_key: str = ""
    deepinfra_api_key: str = ""
    nebius_api_key: str = ""
    hyperbolic_api_key: str = ""
    sambanova_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""
    moonshot_api_key: str = ""
    dashscope_api_key: str = ""
    zai_api_key: str = ""
    siliconflow_api_key: str = ""
    dinference_api_key: str = ""
    chutes_api_key: str = ""
    wavespeed_api_key: str = ""
    bazaarlink_api_key: str = ""
    llama_api_key: str = ""
    parasail_api_key: str = ""
    featherless_api_key: str = ""
    packet_api_key: str = ""
    ridvay_api_key: str = ""
    neurorouters_api_key: str = ""
    glama_api_key: str = ""
    gmi_api_key: str = ""
    atlascloud_api_key: str = ""
    modelmax_api_key: str = ""
    venice_api_key: str = ""
    euri_api_key: str = ""
    apirouter_api_key: str = ""
    quicksilver_api_key: str = ""
    mixlayer_api_key: str = ""
    apilink_api_key: str = ""
    embercloud_api_key: str = ""
    morpheus_api_key: str = ""
    inferencenet_api_key: str = ""
    answira_api_key: str = ""
    llmai_api_key: str = ""
    requesty_api_key: str = ""
    huggingface_api_key: str = ""
    baseten_api_key: str = ""
    haimaker_api_key: str = ""
    grok_api_key: str = ""
    mistral_api_key: str = ""
    openrouter_api_key: str = ""
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
        groq_key = os.environ.get("GROQ_API_KEY", "")
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        together_key = os.environ.get("TOGETHER_API_KEY", "")
        fireworks_key = os.environ.get("FIREWORKS_API_KEY", "")
        friendli_key = os.environ.get("FRIENDLI_TOKEN", "") or os.environ.get("FRIENDLI_API_KEY", "")
        novita_key = os.environ.get("NOVITA_API_KEY", "")
        cerebras_key = os.environ.get("CEREBRAS_API_KEY", "")
        deepinfra_key = os.environ.get("DEEPINFRA_TOKEN", "") or os.environ.get("DEEPINFRA_API_KEY", "")
        nebius_key = os.environ.get("NEBIUS_API_KEY", "")
        hyperbolic_key = os.environ.get("HYPERBOLIC_API_KEY", "")
        sambanova_key = os.environ.get("SAMBANOVA_API_KEY", "")
        cloudflare_key = os.environ.get("CLOUDFLARE_API_TOKEN", "") or os.environ.get("CLOUDFLARE_API_KEY", "")
        cloudflare_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        moonshot_key = os.environ.get("MOONSHOT_API_KEY", "")
        dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
        zai_key = os.environ.get("ZAI_API_KEY", "")
        siliconflow_key = os.environ.get("SILICONFLOW_API_KEY", "")
        dinference_key = os.environ.get("DINFERENCE_API_KEY", "")
        chutes_key = os.environ.get("CHUTES_API_KEY", "")
        wavespeed_key = os.environ.get("WAVESPEED_API_KEY", "")
        bazaarlink_key = os.environ.get("BAZAARLINK_API_KEY", "")
        llama_key = os.environ.get("LLAMA_API_KEY", "")
        parasail_key = os.environ.get("PARASAIL_API_KEY", "")
        featherless_key = os.environ.get("FEATHERLESS_API_KEY", "")
        packet_key = os.environ.get("PACKET_API_KEY", "")
        ridvay_key = os.environ.get("RIDVAY_API_KEY", "")
        neurorouters_key = os.environ.get("NEUROROUTERS_API_KEY", "")
        glama_key = os.environ.get("GLAMA_API_KEY", "")
        gmi_key = os.environ.get("GMI_API_KEY", "")
        atlascloud_key = os.environ.get("ATLASCLOUD_API_KEY", "")
        modelmax_key = os.environ.get("MODELMAX_API_KEY", "")
        venice_key = os.environ.get("VENICE_API_KEY", "")
        euri_key = os.environ.get("EURI_API_KEY", "")
        apirouter_key = os.environ.get("APIROUTER_API_KEY", "")
        quicksilver_key = os.environ.get("QUICKSILVER_API_KEY", "") or os.environ.get("QSP_KEY", "")
        mixlayer_key = os.environ.get("MIXLAYER_API_KEY", "")
        apilink_key = os.environ.get("APILINK_API_KEY", "")
        embercloud_key = os.environ.get("EMBERCLOUD_API_KEY", "")
        morpheus_key = os.environ.get("MORPHEUS_API_KEY", "") or os.environ.get("MOR_API_KEY", "")
        inferencenet_key = os.environ.get("INFERENCE_API_KEY", "") or os.environ.get("INFERENCENET_API_KEY", "")
        answira_key = os.environ.get("ANSWIRA_API_KEY", "")
        llmai_key = os.environ.get("LLMAI_API_KEY", "") or os.environ.get("LLMAI_TOKEN", "")
        requesty_key = os.environ.get("REQUESTY_API_KEY", "")
        huggingface_key = os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACE_API_KEY", "")
        baseten_key = os.environ.get("BASETEN_API_KEY", "")
        haimaker_key = os.environ.get("HAIMAKER_API_KEY", "")
        grok_key = os.environ.get("XAI_API_KEY", "")
        mistral_key = os.environ.get("MISTRAL_API_KEY", "")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
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
            elif groq_key:
                default_backend = "groq"
            elif deepseek_key:
                default_backend = "deepseek"
            elif together_key:
                default_backend = "together"
            elif fireworks_key:
                default_backend = "fireworks"
            elif friendli_key:
                default_backend = "friendli"
            elif novita_key:
                default_backend = "novita"
            elif cerebras_key:
                default_backend = "cerebras"
            elif deepinfra_key:
                default_backend = "deepinfra"
            elif nebius_key:
                default_backend = "nebius"
            elif hyperbolic_key:
                default_backend = "hyperbolic"
            elif sambanova_key:
                default_backend = "sambanova"
            elif cloudflare_key and cloudflare_account_id:
                default_backend = "cloudflare"
            elif moonshot_key:
                default_backend = "moonshot"
            elif dashscope_key:
                default_backend = "dashscope"
            elif zai_key:
                default_backend = "zai"
            elif siliconflow_key:
                default_backend = "siliconflow"
            elif dinference_key:
                default_backend = "dinference"
            elif chutes_key:
                default_backend = "chutes"
            elif wavespeed_key:
                default_backend = "wavespeed"
            elif bazaarlink_key:
                default_backend = "bazaarlink"
            elif llama_key:
                default_backend = "llamaapi"
            elif parasail_key:
                default_backend = "parasail"
            elif featherless_key:
                default_backend = "featherless"
            elif packet_key:
                default_backend = "packet"
            elif ridvay_key:
                default_backend = "ridvay"
            elif neurorouters_key:
                default_backend = "neurorouters"
            elif glama_key:
                default_backend = "glama"
            elif gmi_key:
                default_backend = "gmi"
            elif atlascloud_key:
                default_backend = "atlascloud"
            elif modelmax_key:
                default_backend = "modelmax"
            elif venice_key:
                default_backend = "venice"
            elif euri_key:
                default_backend = "euri"
            elif apirouter_key:
                default_backend = "apirouter"
            elif quicksilver_key:
                default_backend = "quicksilver"
            elif mixlayer_key:
                default_backend = "mixlayer"
            elif apilink_key:
                default_backend = "apilink"
            elif embercloud_key:
                default_backend = "embercloud"
            elif morpheus_key:
                default_backend = "morpheus"
            elif inferencenet_key:
                default_backend = "inferencenet"
            elif answira_key:
                default_backend = "answira"
            elif llmai_key:
                default_backend = "llmai"
            elif requesty_key:
                default_backend = "requesty"
            elif huggingface_key:
                default_backend = "huggingface"
            elif baseten_key:
                default_backend = "baseten"
            elif haimaker_key:
                default_backend = "haimaker"
            elif mistral_key:
                default_backend = "mistral"
            elif grok_key:
                default_backend = "grok"
            elif openrouter_key:
                default_backend = "openrouter"
            elif ollama_url:
                default_backend = "ollama"
            else:
                default_backend = "stub"

        # Fail-closed: stub backend is forbidden in pilot/production.
        # The stub returns deterministic fake responses suitable only
        # for testing - running it under a "production" label is a
        # silent governance failure (audit trail records "real" calls
        # that never happened).
        if default_backend == "stub" and env in ("pilot", "production"):
            raise RuntimeError(
                f"MULLU_LLM_BACKEND='stub' is forbidden in {env!r} environment. "
                "Set MULLU_LLM_BACKEND explicitly or provide an API key "
                "(ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, "
                "GROQ_API_KEY, DEEPSEEK_API_KEY, TOGETHER_API_KEY, "
                "FIREWORKS_API_KEY, FRIENDLI_TOKEN, NOVITA_API_KEY, "
                "CEREBRAS_API_KEY, DEEPINFRA_TOKEN, NEBIUS_API_KEY, "
                "HYPERBOLIC_API_KEY, SAMBANOVA_API_KEY, CLOUDFLARE_API_TOKEN "
                "with CLOUDFLARE_ACCOUNT_ID, MOONSHOT_API_KEY, DASHSCOPE_API_KEY, "
                "ZAI_API_KEY, SILICONFLOW_API_KEY, DINFERENCE_API_KEY, "
                "CHUTES_API_KEY, WAVESPEED_API_KEY, BAZAARLINK_API_KEY, "
                "LLAMA_API_KEY, PARASAIL_API_KEY, FEATHERLESS_API_KEY, "
                "PACKET_API_KEY, RIDVAY_API_KEY, NEUROROUTERS_API_KEY, "
                "GLAMA_API_KEY, GMI_API_KEY, ATLASCLOUD_API_KEY, "
                "MODELMAX_API_KEY, VENICE_API_KEY, EURI_API_KEY, "
                "APIROUTER_API_KEY, QUICKSILVER_API_KEY, QSP_KEY, "
                "MIXLAYER_API_KEY, APILINK_API_KEY, "
                "EMBERCLOUD_API_KEY, MORPHEUS_API_KEY, MOR_API_KEY, "
                "INFERENCE_API_KEY, INFERENCENET_API_KEY, "
                "ANSWIRA_API_KEY, LLMAI_API_KEY, LLMAI_TOKEN, REQUESTY_API_KEY, "
                "HF_TOKEN, HUGGINGFACE_API_KEY, BASETEN_API_KEY, HAIMAKER_API_KEY, "
                "XAI_API_KEY, MISTRAL_API_KEY, "
                "OPENROUTER_API_KEY) "
                "or OLLAMA_BASE_URL."
            )

        return cls(
            default_backend=default_backend,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            gemini_api_key=gemini_key,
            groq_api_key=groq_key,
            deepseek_api_key=deepseek_key,
            together_api_key=together_key,
            fireworks_api_key=fireworks_key,
            friendli_api_key=friendli_key,
            novita_api_key=novita_key,
            cerebras_api_key=cerebras_key,
            deepinfra_api_key=deepinfra_key,
            nebius_api_key=nebius_key,
            hyperbolic_api_key=hyperbolic_key,
            sambanova_api_key=sambanova_key,
            cloudflare_api_key=cloudflare_key,
            cloudflare_account_id=cloudflare_account_id,
            moonshot_api_key=moonshot_key,
            dashscope_api_key=dashscope_key,
            zai_api_key=zai_key,
            siliconflow_api_key=siliconflow_key,
            dinference_api_key=dinference_key,
            chutes_api_key=chutes_key,
            wavespeed_api_key=wavespeed_key,
            bazaarlink_api_key=bazaarlink_key,
            llama_api_key=llama_key,
            parasail_api_key=parasail_key,
            featherless_api_key=featherless_key,
            packet_api_key=packet_key,
            ridvay_api_key=ridvay_key,
            neurorouters_api_key=neurorouters_key,
            glama_api_key=glama_key,
            gmi_api_key=gmi_key,
            atlascloud_api_key=atlascloud_key,
            modelmax_api_key=modelmax_key,
            venice_api_key=venice_key,
            euri_api_key=euri_key,
            apirouter_api_key=apirouter_key,
            quicksilver_api_key=quicksilver_key,
            mixlayer_api_key=mixlayer_key,
            apilink_api_key=apilink_key,
            embercloud_api_key=embercloud_key,
            morpheus_api_key=morpheus_key,
            inferencenet_api_key=inferencenet_key,
            answira_api_key=answira_key,
            llmai_api_key=llmai_key,
            requesty_api_key=requesty_key,
            huggingface_api_key=huggingface_key,
            baseten_api_key=baseten_key,
            haimaker_api_key=haimaker_key,
            grok_api_key=grok_key,
            mistral_api_key=mistral_key,
            openrouter_api_key=openrouter_key,
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


def _select_provider_default_model(default_model: str, markers: tuple[str, ...], fallback: str) -> str:
    """Select a default model only when it belongs to the target provider."""
    normalized = default_model.lower()
    if any(marker in normalized for marker in markers):
        return default_model
    return fallback


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

    # Register low-cost hosted OpenAI-compatible backends when keys are available
    if llm_config.groq_api_key:
        groq = GroqBackend(
            api_key=llm_config.groq_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("llama", "qwen", "gpt-oss", "groq/"),
                GroqBackend.DEFAULT_MODEL,
            ),
        )
        backends["groq"] = groq

    if llm_config.deepseek_api_key:
        deepseek = DeepSeekBackend(
            api_key=llm_config.deepseek_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek",),
                DeepSeekBackend.DEFAULT_MODEL,
            ),
        )
        backends["deepseek"] = deepseek

    if llm_config.together_api_key:
        together = TogetherBackend(
            api_key=llm_config.together_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("lfm", "liquid", "qwen", "openai/gpt-oss", "together/"),
                TogetherBackend.DEFAULT_MODEL,
            ),
        )
        backends["together"] = together

    if llm_config.fireworks_api_key:
        fireworks = FireworksBackend(
            api_key=llm_config.fireworks_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("accounts/fireworks/", "fireworks/", "gpt-oss"),
                FireworksBackend.DEFAULT_MODEL,
            ),
        )
        backends["fireworks"] = fireworks

    if llm_config.friendli_api_key:
        friendli = FriendliBackend(
            api_key=llm_config.friendli_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama", "qwen/", "deepseek-ai/", "friendli/"),
                FriendliBackend.DEFAULT_MODEL,
            ),
        )
        backends["friendli"] = friendli

    if llm_config.novita_api_key:
        novita = NovitaBackend(
            api_key=llm_config.novita_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek/", "openai/gpt-oss", "meta-llama/", "zai-org/", "novita/"),
                NovitaBackend.DEFAULT_MODEL,
            ),
        )
        backends["novita"] = novita

    if llm_config.cerebras_api_key:
        cerebras = CerebrasBackend(
            api_key=llm_config.cerebras_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("llama", "qwen", "gpt-oss", "zai-glm"),
                CerebrasBackend.DEFAULT_MODEL,
            ),
        )
        backends["cerebras"] = cerebras

    if llm_config.deepinfra_api_key:
        deepinfra = DeepInfraBackend(
            api_key=llm_config.deepinfra_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama/", "deepseek-ai/", "qwen/", "mistralai/", "deepinfra/"),
                DeepInfraBackend.DEFAULT_MODEL,
            ),
        )
        backends["deepinfra"] = deepinfra

    if llm_config.nebius_api_key:
        nebius = NebiusBackend(
            api_key=llm_config.nebius_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama/", "deepseek-ai/", "mistralai/", "microsoft/", "nebius/"),
                NebiusBackend.DEFAULT_MODEL,
            ),
        )
        backends["nebius"] = nebius

    if llm_config.hyperbolic_api_key:
        hyperbolic = HyperbolicBackend(
            api_key=llm_config.hyperbolic_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama/", "deepseek-ai/", "qwen/", "moonshotai/", "hyperbolic/"),
                HyperbolicBackend.DEFAULT_MODEL,
            ),
        )
        backends["hyperbolic"] = hyperbolic

    if llm_config.sambanova_api_key:
        sambanova = SambaNovaBackend(
            api_key=llm_config.sambanova_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama", "deepseek", "qwen", "sambanova/"),
                SambaNovaBackend.DEFAULT_MODEL,
            ),
        )
        backends["sambanova"] = sambanova

    if llm_config.cloudflare_api_key and llm_config.cloudflare_account_id:
        cloudflare = CloudflareBackend(
            api_key=llm_config.cloudflare_api_key,
            account_id=llm_config.cloudflare_account_id,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("@cf/", "cloudflare/"),
                CloudflareBackend.DEFAULT_MODEL,
            ),
        )
        backends["cloudflare"] = cloudflare

    if llm_config.moonshot_api_key:
        moonshot = MoonshotBackend(
            api_key=llm_config.moonshot_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("kimi", "moonshot"),
                MoonshotBackend.DEFAULT_MODEL,
            ),
        )
        backends["moonshot"] = moonshot

    if llm_config.dashscope_api_key:
        dashscope = DashScopeBackend(
            api_key=llm_config.dashscope_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "dashscope"),
                DashScopeBackend.DEFAULT_MODEL,
            ),
        )
        backends["dashscope"] = dashscope

    if llm_config.zai_api_key:
        zai = ZAIBackend(
            api_key=llm_config.zai_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("glm", "zai", "z.ai"),
                ZAIBackend.DEFAULT_MODEL,
            ),
        )
        backends["zai"] = zai

    if llm_config.siliconflow_api_key:
        siliconflow = SiliconFlowBackend(
            api_key=llm_config.siliconflow_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek-ai/", "openai/gpt-oss", "siliconflow/"),
                SiliconFlowBackend.DEFAULT_MODEL,
            ),
        )
        backends["siliconflow"] = siliconflow

    if llm_config.dinference_api_key:
        dinference = DInferenceBackend(
            api_key=llm_config.dinference_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("gpt-oss", "glm-", "minimax", "dinference/"),
                DInferenceBackend.DEFAULT_MODEL,
            ),
        )
        backends["dinference"] = dinference

    if llm_config.chutes_api_key:
        chutes = ChutesBackend(
            api_key=llm_config.chutes_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek-ai/", "zai-org/", "minimaxai/", "chutes/"),
                ChutesBackend.DEFAULT_MODEL,
            ),
        )
        backends["chutes"] = chutes

    if llm_config.wavespeed_api_key:
        wavespeed = WaveSpeedBackend(
            api_key=llm_config.wavespeed_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek/", "llama", "wavespeed/"),
                WaveSpeedBackend.DEFAULT_MODEL,
            ),
        )
        backends["wavespeed"] = wavespeed

    if llm_config.bazaarlink_api_key:
        bazaarlink = BazaarLinkBackend(
            api_key=llm_config.bazaarlink_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama/", "llama", "bazaarlink/"),
                BazaarLinkBackend.DEFAULT_MODEL,
            ),
        )
        backends["bazaarlink"] = bazaarlink

    if llm_config.llama_api_key:
        llamaapi = LlamaAPIBackend(
            api_key=llm_config.llama_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("llama", "meta-llama/"),
                LlamaAPIBackend.DEFAULT_MODEL,
            ),
        )
        backends["llamaapi"] = llamaapi

    if llm_config.parasail_api_key:
        parasail = ParasailBackend(
            api_key=llm_config.parasail_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("parasail-", "qwen", "llama", "deepseek"),
                ParasailBackend.DEFAULT_MODEL,
            ),
        )
        backends["parasail"] = parasail

    if llm_config.featherless_api_key:
        featherless = FeatherlessBackend(
            api_key=llm_config.featherless_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "meta-llama/", "mistral", "deepseek", "featherless/"),
                FeatherlessBackend.DEFAULT_MODEL,
            ),
        )
        backends["featherless"] = featherless

    if llm_config.packet_api_key:
        packet = PacketBackend(
            api_key=llm_config.packet_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("meta-llama/", "llama", "qwen/", "mistral", "packet/"),
                PacketBackend.DEFAULT_MODEL,
            ),
        )
        backends["packet"] = packet

    if llm_config.ridvay_api_key:
        ridvay = RidvayBackend(
            api_key=llm_config.ridvay_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "meta-llama/", "deepseek", "ridvay/"),
                RidvayBackend.DEFAULT_MODEL,
            ),
        )
        backends["ridvay"] = ridvay

    if llm_config.neurorouters_api_key:
        neurorouters = NeuroRoutersBackend(
            api_key=llm_config.neurorouters_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "meta-llama/", "deepseek", "neurorouters/"),
                NeuroRoutersBackend.DEFAULT_MODEL,
            ),
        )
        backends["neurorouters"] = neurorouters

    if llm_config.glama_api_key:
        glama = GlamaBackend(
            api_key=llm_config.glama_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek", "qwen", "llama", "mistral", "glama/"),
                GlamaBackend.DEFAULT_MODEL,
            ),
        )
        backends["glama"] = glama

    if llm_config.gmi_api_key:
        gmi = GMIBackend(
            api_key=llm_config.gmi_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek", "gpt-oss", "gmi/"),
                GMIBackend.DEFAULT_MODEL,
            ),
        )
        backends["gmi"] = gmi

    if llm_config.atlascloud_api_key:
        atlascloud = AtlasCloudBackend(
            api_key=llm_config.atlascloud_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek", "llama", "atlascloud/"),
                AtlasCloudBackend.DEFAULT_MODEL,
            ),
        )
        backends["atlascloud"] = atlascloud

    if llm_config.modelmax_api_key:
        modelmax = ModelMaxBackend(
            api_key=llm_config.modelmax_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "deepseek", "llama", "modelmax/"),
                ModelMaxBackend.DEFAULT_MODEL,
            ),
        )
        backends["modelmax"] = modelmax

    if llm_config.venice_api_key:
        venice = VeniceBackend(
            api_key=llm_config.venice_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "deepseek", "llama", "mistral", "venice"),
                VeniceBackend.DEFAULT_MODEL,
            ),
        )
        backends["venice"] = venice

    if llm_config.euri_api_key:
        euri = EURIBackend(
            api_key=llm_config.euri_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "gpt", "gemini", "llama", "groq/", "euri/"),
                EURIBackend.DEFAULT_MODEL,
            ),
        )
        backends["euri"] = euri

    if llm_config.apirouter_api_key:
        apirouter = APIRouterBackend(
            api_key=llm_config.apirouter_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek-ai/", "pro/moonshotai/", "pro/zai-org/", "minimaxai/"),
                APIRouterBackend.DEFAULT_MODEL,
            ),
        )
        backends["apirouter"] = apirouter

    if llm_config.quicksilver_api_key:
        quicksilver = QuickSilverBackend(
            api_key=llm_config.quicksilver_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "deepseek", "kimi", "quicksilver"),
                QuickSilverBackend.DEFAULT_MODEL,
            ),
        )
        backends["quicksilver"] = quicksilver

    if llm_config.mixlayer_api_key:
        mixlayer = MixlayerBackend(
            api_key=llm_config.mixlayer_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "deepseek", "kimi", "meta/", "mixlayer/"),
                MixlayerBackend.DEFAULT_MODEL,
            ),
        )
        backends["mixlayer"] = mixlayer

    if llm_config.apilink_api_key:
        apilink = ApiLinkBackend(
            api_key=llm_config.apilink_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek/", "google/", "openai/", "anthropic/", "apilink/"),
                ApiLinkBackend.DEFAULT_MODEL,
            ),
        )
        backends["apilink"] = apilink

    if llm_config.embercloud_api_key:
        embercloud = EmberCloudBackend(
            api_key=llm_config.embercloud_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("glm", "qwen", "kimi", "ember"),
                EmberCloudBackend.DEFAULT_MODEL,
            ),
        )
        backends["embercloud"] = embercloud

    if llm_config.morpheus_api_key:
        morpheus = MorpheusBackend(
            api_key=llm_config.morpheus_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen", "gpt-oss", "gemma", "glm", "morpheus"),
                MorpheusBackend.DEFAULT_MODEL,
            ),
        )
        backends["morpheus"] = morpheus

    if llm_config.inferencenet_api_key:
        inferencenet = InferenceNetBackend(
            api_key=llm_config.inferencenet_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("inference-net/", "google/gemma", "schematron", "cliptagger"),
                InferenceNetBackend.DEFAULT_MODEL,
            ),
        )
        backends["inferencenet"] = inferencenet

    if llm_config.answira_api_key:
        answira = AnswiraBackend(
            api_key=llm_config.answira_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("qwen/", "zai-org/", "glm", "answira"),
                AnswiraBackend.DEFAULT_MODEL,
            ),
        )
        backends["answira"] = answira

    if llm_config.llmai_api_key:
        llmai = LLMAIBackend(
            api_key=llm_config.llmai_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("gemma", "deepseek", "qwen", "glm", "kimi", "llmai"),
                LLMAIBackend.DEFAULT_MODEL,
            ),
        )
        backends["llmai"] = llmai

    if llm_config.requesty_api_key:
        requesty = RequestyBackend(
            api_key=llm_config.requesty_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek/", "zai/", "fireworks/", "anthropic/", "openai/"),
                RequestyBackend.DEFAULT_MODEL,
            ),
        )
        backends["requesty"] = requesty

    if llm_config.huggingface_api_key:
        huggingface = HuggingFaceBackend(
            api_key=llm_config.huggingface_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("Qwen/", "openai/", "deepseek-ai/", "zai-org/", "huggingface"),
                HuggingFaceBackend.DEFAULT_MODEL,
            ),
        )
        backends["huggingface"] = huggingface

    if llm_config.baseten_api_key:
        baseten = BasetenBackend(
            api_key=llm_config.baseten_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("nvidia/", "openai/", "deepseek-ai/", "MiniMaxAI/", "moonshotai/", "zai-org/"),
                BasetenBackend.DEFAULT_MODEL,
            ),
        )
        backends["baseten"] = baseten

    if llm_config.haimaker_api_key:
        haimaker = HaimakerBackend(
            api_key=llm_config.haimaker_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("deepseek/", "openai/", "qwen/", "haimaker"),
                HaimakerBackend.DEFAULT_MODEL,
            ),
        )
        backends["haimaker"] = haimaker

    if llm_config.grok_api_key:
        grok = GrokBackend(
            api_key=llm_config.grok_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("grok",),
                GrokBackend.DEFAULT_MODEL,
            ),
        )
        backends["grok"] = grok

    if llm_config.mistral_api_key:
        mistral = MistralBackend(
            api_key=llm_config.mistral_api_key,
            model=_select_provider_default_model(
                llm_config.default_model,
                ("mistral", "magistral", "ministral", "codestral", "devstral"),
                MistralBackend.DEFAULT_MODEL,
            ),
        )
        backends["mistral"] = mistral

    if llm_config.openrouter_api_key:
        openrouter_model = (
            llm_config.default_model
            if llm_config.default_backend == "openrouter"
            else OpenRouterBackend.DEFAULT_MODEL
        )
        openrouter = OpenRouterBackend(
            api_key=llm_config.openrouter_api_key,
            model=openrouter_model,
        )
        backends["openrouter"] = openrouter

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
        "gemini": {
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com",
            "rate_limit": 60,
            "cost_limit": 0.25,
        },
        "groq": {
            "name": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "deepseek": {
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "together": {
            "name": "Together",
            "base_url": "https://api.together.xyz/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "fireworks": {
            "name": "Fireworks",
            "base_url": "https://api.fireworks.ai/inference/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "friendli": {
            "name": "Friendli",
            "base_url": "https://api.friendli.ai/serverless/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "novita": {
            "name": "Novita",
            "base_url": "https://api.novita.ai/openai",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "cerebras": {
            "name": "Cerebras",
            "base_url": "https://api.cerebras.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "deepinfra": {
            "name": "DeepInfra",
            "base_url": "https://api.deepinfra.com/v1/openai",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "nebius": {
            "name": "Nebius",
            "base_url": "https://api.tokenfactory.nebius.com/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "hyperbolic": {
            "name": "Hyperbolic",
            "base_url": "https://api.hyperbolic.xyz/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "sambanova": {
            "name": "SambaNova",
            "base_url": "https://api.sambanova.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "cloudflare": {
            "name": "Cloudflare Workers AI",
            "base_url": (
                f"https://api.cloudflare.com/client/v4/accounts/{config.cloudflare_account_id}/ai/v1"
                if config.cloudflare_account_id
                else "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
            ),
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "moonshot": {
            "name": "Moonshot Kimi",
            "base_url": "https://api.moonshot.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "dashscope": {
            "name": "Alibaba DashScope",
            "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "zai": {
            "name": "Z.AI",
            "base_url": "https://api.z.ai/api/paas/v4",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "siliconflow": {
            "name": "SiliconFlow",
            "base_url": "https://api.siliconflow.com/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "dinference": {
            "name": "DInference",
            "base_url": "https://api.dinference.com/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "chutes": {
            "name": "Chutes",
            "base_url": "https://llm.chutes.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "wavespeed": {
            "name": "WaveSpeed",
            "base_url": "https://llm.wavespeed.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "bazaarlink": {
            "name": "BazaarLink",
            "base_url": "https://bazaarlink.ai/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "llamaapi": {
            "name": "LlamaAPI",
            "base_url": "https://api.llama-api.com",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "parasail": {
            "name": "Parasail",
            "base_url": "https://api.parasail.io/v1",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "featherless": {
            "name": "Featherless",
            "base_url": "https://api.featherless.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.05,
        },
        "packet": {
            "name": "Packet Token Factory",
            "base_url": "https://dash.packet.ai/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "ridvay": {
            "name": "Ridvay",
            "base_url": "https://api.ridvay.com/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "neurorouters": {
            "name": "NeuroRouters",
            "base_url": "https://neurorouters.com/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.05,
        },
        "glama": {
            "name": "Glama Gateway",
            "base_url": "https://gateway.glama.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "gmi": {
            "name": "GMI Cloud",
            "base_url": "https://api.gmi-serving.com/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "atlascloud": {
            "name": "Atlas Cloud",
            "base_url": "https://api.atlascloud.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "modelmax": {
            "name": "ModelMax",
            "base_url": "https://api.modelmax.io/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "venice": {
            "name": "Venice",
            "base_url": "https://api.venice.ai/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "euri": {
            "name": "EURI",
            "base_url": "https://api.euron.one/api/v1/euri",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "apirouter": {
            "name": "APIRouter",
            "base_url": "https://apirouter.chat/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "quicksilver": {
            "name": "QuickSilver Pro",
            "base_url": "https://api.quicksilverpro.io/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "mixlayer": {
            "name": "Mixlayer",
            "base_url": "https://models.mixlayer.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "apilink": {
            "name": "ApiLink",
            "base_url": "https://api.apilink.io/v1",
            "rate_limit": 60,
            "cost_limit": 0.25,
        },
        "embercloud": {
            "name": "EmberCloud",
            "base_url": "https://api.embercloud.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "morpheus": {
            "name": "Morpheus",
            "base_url": "https://api.mor.org/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "inferencenet": {
            "name": "Inference.net",
            "base_url": "https://api.inference.net/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "answira": {
            "name": "Answira",
            "base_url": "https://answira.ai/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "llmai": {
            "name": "LLMAI",
            "base_url": "https://api.llmai.dev/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "requesty": {
            "name": "Requesty",
            "base_url": "https://router.requesty.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "huggingface": {
            "name": "Hugging Face",
            "base_url": "https://router.huggingface.co/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "baseten": {
            "name": "Baseten",
            "base_url": "https://inference.baseten.co/v1",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "haimaker": {
            "name": "haimaker",
            "base_url": "https://api.haimaker.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "grok": {
            "name": "xAI Grok",
            "base_url": "https://api.x.ai/v1",
            "rate_limit": 60,
            "cost_limit": 0.50,
        },
        "mistral": {
            "name": "Mistral",
            "base_url": "https://api.mistral.ai/v1",
            "rate_limit": 120,
            "cost_limit": 0.50,
        },
        "openrouter": {
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "rate_limit": 120,
            "cost_limit": 0.25,
        },
        "ollama": {
            "name": "Ollama",
            "base_url": config.ollama_base_url or "http://localhost:11434",
            "rate_limit": 1000,
            "cost_limit": 0.0,
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
        ("gpt-4.1-mini", "GPT-4.1 Mini", "openai", 0.40, 1.60),
        ("gpt-4.1-nano", "GPT-4.1 Nano", "openai", 0.10, 0.40),
        # Google Gemini low-cost models
        ("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini", 0.10, 0.40),
        ("gemini-2.0-flash-lite", "Gemini 2.0 Flash-Lite", "gemini", 0.075, 0.30),
        ("gemini-1.5-flash", "Gemini 1.5 Flash", "gemini", 0.075, 0.30),
        # OpenAI-compatible low-cost providers
        ("meta-llama/llama-4-scout-17b-16e-instruct", "Llama 4 Scout 17B", "groq", 0.11, 0.34),
        ("llama-3.1-8b-instant", "Llama 3.1 8B Instant", "groq", 0.05, 0.08),
        ("openai/gpt-oss-20b", "GPT OSS 20B", "groq", 0.075, 0.30),
        ("openai/gpt-oss-120b", "GPT OSS 120B", "groq", 0.15, 0.60),
        ("deepseek-v4-flash", "DeepSeek V4 Flash", "deepseek", 0.14, 0.28),
        ("deepseek-reasoner", "DeepSeek Reasoner", "deepseek", 0.14, 0.28),
        ("LiquidAI/LFM2-24B-A2B", "LFM2 24B A2B", "together", 0.03, 0.12),
        ("Qwen/Qwen3.5-9B", "Qwen3.5 9B", "together", 0.10, 0.15),
        ("accounts/fireworks/models/gpt-oss-20b", "GPT OSS 20B via Fireworks", "fireworks", 0.07, 0.30),
        ("accounts/fireworks/models/llama-v3p1-8b-instruct", "Llama 3.1 8B via Fireworks", "fireworks", 0.10, 0.10),
        ("meta-llama-3.1-8b-instruct", "Llama 3.1 8B via Friendli", "friendli", 0.10, 0.10),
        ("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash via Novita", "novita", 0.14, 0.28),
        ("llama3.1-8b", "Llama 3.1 8B via Cerebras", "cerebras", 0.10, 0.10),
        ("meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "Llama 3.1 8B Turbo via DeepInfra", "deepinfra", 0.02, 0.03),
        ("meta-llama/Meta-Llama-3.1-8B-Instruct", "Llama 3.1 8B via Nebius", "nebius", 0.02, 0.06),
        ("Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen2.5 Coder 32B via Hyperbolic", "hyperbolic", 0.20, 0.20),
        ("Meta-Llama-3.3-70B-Instruct", "Llama 3.3 70B via SambaNova", "sambanova", 0.60, 1.20),
        ("@cf/meta/llama-3.1-8b-instruct-fp8-fast", "Llama 3.1 8B FP8 Fast via Cloudflare", "cloudflare", 0.045, 0.384),
        ("kimi-k2.5", "Kimi K2.5 via Moonshot", "moonshot", 0.60, 3.00),
        ("qwen-turbo", "Qwen Turbo via DashScope", "dashscope", 0.05, 0.20),
        ("glm-4.5-air", "GLM-4.5 Air via Z.AI", "zai", 0.20, 1.10),
        ("Qwen/Qwen2.5-7B-Instruct", "Qwen2.5 7B via SiliconFlow", "siliconflow", 0.05, 0.05),
        ("gpt-oss-120b", "GPT OSS 120B via DInference", "dinference", 0.09, 0.36),
        ("Qwen/Qwen3-32B-TEE", "Qwen3 32B TEE via Chutes", "chutes", 0.08, 0.24),
        ("qwen/qwen3-coder-30b-a3b-instruct", "Qwen3 Coder 30B A3B via WaveSpeed", "wavespeed", 0.07, 0.27),
        ("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B via BazaarLink", "bazaarlink", 0.02, 0.05),
        ("llama3-70b", "Llama 3 70B via LlamaAPI", "llamaapi", 0.65, 0.65),
        ("parasail-qwen3-32b", "Qwen3 32B via Parasail", "parasail", 0.10, 0.50),
        ("Qwen/Qwen2.5-7B-Instruct-1M", "Qwen2.5 7B 1M via Featherless", "featherless", 0.0, 0.0),
        ("meta-llama/Llama-3.1-70B-Instruct", "Llama 3.1 70B via Packet Token Factory", "packet", 0.15, 0.15),
        ("qwen/qwen3-30b-a3b", "Qwen3 30B A3B via Ridvay", "ridvay", 0.06, 0.22),
        ("qwen/qwen3-30b-a3b:free", "Qwen3 30B A3B Free via NeuroRouters", "neurorouters", 0.0, 0.0),
        ("deepseek-chat-v3", "DeepSeek Chat V3 via Glama Gateway", "glama", 0.14, 0.28),
        ("Qwen/Qwen3-32B-FP8", "Qwen3 32B FP8 via GMI Cloud", "gmi", 0.10, 0.60),
        ("Qwen/Qwen3-30B-A3B-Instruct-2507", "Qwen3 30B A3B 2507 via Atlas Cloud", "atlascloud", 0.09, 0.30),
        ("qwen3-coder-30b-a3b", "Qwen3 Coder 30B A3B via ModelMax", "modelmax", 0.15, 0.60),
        ("qwen3-5-9b", "Qwen3.5 9B via Venice", "venice", 0.10, 0.15),
        ("qwen/qwen3-32b", "Qwen3 32B via EURI", "euri", 0.29, 0.59),
        (
            "Qwen/Qwen3-Coder-30B-A3B-Instruct",
            "Qwen3 Coder 30B A3B via APIRouter",
            "apirouter",
            0.028,
            0.112,
        ),
        ("qwen3.6-35b", "Qwen3.6 35B via QuickSilver Pro", "quicksilver", 0.13, 0.78),
        ("qwen/qwen3.5-9b", "Qwen3.5 9B via Mixlayer", "mixlayer", 0.10, 0.40),
        ("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro via ApiLink", "apilink", 0.43, 0.87),
        ("glm-4.7-flash", "GLM 4.7 Flash via EmberCloud", "embercloud", 0.06, 0.40),
        ("qwen35-9b", "Qwen 3.5 9B via Morpheus", "morpheus", 0.05, 0.15),
        (
            "google/gemma-3-27b-instruct/bf-16",
            "Gemma 3 27B via Inference.net",
            "inferencenet",
            0.15,
            0.30,
        ),
        ("qwen/qwen3-coder-next", "Qwen3 Coder Next via Answira", "answira", 0.07, 0.30),
        ("gemma-4", "Gemma 4 via LLMAI", "llmai", 0.046, 0.130),
        ("deepseek/deepseek-chat", "DeepSeek Chat via Requesty", "requesty", 0.14, 0.28),
        (
            "Qwen/Qwen3-Coder-30B-A3B-Instruct:cheapest",
            "Qwen3 Coder 30B A3B via Hugging Face",
            "huggingface",
            0.07,
            0.26,
        ),
        ("nvidia/Nemotron-120B-A12B", "Nemotron Super via Baseten", "baseten", 0.30, 0.75),
        ("deepseek/deepseek-chat-v3-0324", "DeepSeek Chat V3 0324 via haimaker", "haimaker", 0.14, 0.28),
        ("mistral-small-2506", "Mistral Small 2506", "mistral", 0.10, 0.30),
        ("mistral-small-2603", "Mistral Small 2603", "mistral", 0.15, 0.60),
        ("grok-3-mini", "Grok 3 Mini", "grok", 0.30, 0.50),
        ("meta-llama/llama-4-scout", "Llama 4 Scout via OpenRouter", "openrouter", 0.0, 0.0),
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
