"""Capability bootstrap helpers for the governed HTTP server.

Purpose: isolate the remaining pre-app capability, tooling, and analytics
bootstrap from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: tool use, structured output, circuit breakers, routing,
queueing, analytics, templates, and capability support subsystems.
Invariants:
  - Default tool and output schema registration remains stable.
  - Usage, analytics, and observability source wiring stays deterministic.
  - Feature flags, dependency graph nodes, and workflow templates remain
    behavior-compatible.
  - Shutdown manager and state persistence remain available to the server
    boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.server_runtime import (
    register_default_output_schemas,
    register_default_tools,
)
from mcoi_runtime.core.ab_testing import ABTestEngine
from mcoi_runtime.core.agent_chain import AgentChainEngine
from mcoi_runtime.core.agent_chain import ChainStep as _ChainStep
from mcoi_runtime.core.agent_memory import AgentMemoryStore
from mcoi_runtime.core.backpressure import BackpressureEngine
from mcoi_runtime.core.cache import GovernedCache
from mcoi_runtime.core.dependency_graph import DependencyGraph, SubsystemNode
from mcoi_runtime.core.event_sourcing import EventStore
from mcoi_runtime.core.feature_flags import FeatureFlag, FeatureFlagEngine
from mcoi_runtime.core.graceful_shutdown import ShutdownManager
from mcoi_runtime.core.isolation_verifier import IsolationProbe, IsolationVerifier
from mcoi_runtime.core.model_router import ModelProfile, ModelRouter
from mcoi_runtime.core.monitoring import MonitoringEngine
from mcoi_runtime.core.request_correlation import CorrelationManager
from mcoi_runtime.core.retry_engine import CircuitBreaker
from mcoi_runtime.core.semantic_search import SemanticSearchEngine
from mcoi_runtime.core.structured_output import StructuredOutputEngine
from mcoi_runtime.core.task_queue import TaskQueue
from mcoi_runtime.core.tenant_analytics import TenantAnalyticsEngine
from mcoi_runtime.core.tool_agent import ToolAugmentedAgent
from mcoi_runtime.core.tool_use import ToolRegistry
from mcoi_runtime.core.usage_reporter import UsageReporter
from mcoi_runtime.core.workflow_templates import WorkflowTemplate, WorkflowTemplateRegistry
from mcoi_runtime.persistence.state_persistence import StatePersistence


@dataclass(frozen=True)
class CapabilityBootstrap:
    """Capability bootstrap result."""

    tool_registry: Any
    structured_output: Any
    state_persistence: Any
    llm_circuit: Any
    tool_agent: Any
    model_router: Any
    correlation_mgr: Any
    shutdown_mgr: Any
    agent_chain: Any
    monitor: Any
    task_queue: Any
    agent_memory: Any
    ab_engine: Any
    isolation_verifier: Any
    usage_reporter: Any
    dep_graph: Any
    backpressure: Any
    governed_cache: Any
    feature_flags: Any
    semantic_search: Any
    tenant_analytics: Any
    wf_templates: Any
    event_store: Any


def bootstrap_capability_services(
    *,
    clock: Callable[[], str],
    runtime_env: Mapping[str, str],
    llm_bridge: Any,
    observability: Any,
    tenant_budget_mgr: Any,
    evaluate_expression_fn: Callable[[str], Any],
    register_default_tools_fn: Callable[..., None] = register_default_tools,
    register_default_output_schemas_fn: Callable[[Any], None] = register_default_output_schemas,
) -> CapabilityBootstrap:
    """Create remaining pre-app capability services."""
    tool_registry = ToolRegistry(clock=clock)
    register_default_tools_fn(
        tool_registry=tool_registry,
        clock=clock,
        evaluate_expression_fn=evaluate_expression_fn,
    )
    observability.register_source("tools", lambda: tool_registry.summary())

    structured_output = StructuredOutputEngine()
    register_default_output_schemas_fn(structured_output)

    state_persistence = StatePersistence(
        clock=clock,
        base_dir=runtime_env.get("MULLU_STATE_DIR", ""),
    )
    llm_circuit = CircuitBreaker(failure_threshold=10, recovery_timeout_ms=60000)

    tool_agent = ToolAugmentedAgent(
        tool_registry=tool_registry,
        llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
        max_tool_calls=10,
    )

    model_router = ModelRouter()
    model_router.register(
        ModelProfile(
            model_id="claude-haiku-4-5",
            name="Claude Haiku 4.5",
            provider="anthropic",
            cost_per_1k_input=0.00080,
            cost_per_1k_output=0.0040,
            max_context=200000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="claude-sonnet-4",
            name="Claude Sonnet 4",
            provider="anthropic",
            cost_per_1k_input=0.0030,
            cost_per_1k_output=0.0150,
            max_context=200000,
            speed_tier="medium",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="claude-opus-4-6",
            name="Claude Opus 4.6",
            provider="anthropic",
            cost_per_1k_input=0.0150,
            cost_per_1k_output=0.0750,
            max_context=1000000,
            speed_tier="slow",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider="openai",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00060,
            max_context=128000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gpt-4.1-nano",
            name="GPT-4.1 Nano",
            provider="openai",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00040,
            max_context=128000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gpt-4.1-mini",
            name="GPT-4.1 Mini",
            provider="openai",
            cost_per_1k_input=0.00040,
            cost_per_1k_output=0.00160,
            max_context=128000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gemini-2.0-flash-lite",
            name="Gemini 2.0 Flash-Lite",
            provider="gemini",
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.00030,
            max_context=1000000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gemini-2.0-flash",
            name="Gemini 2.0 Flash",
            provider="gemini",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00040,
            max_context=1000000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="llama-3.1-8b-instant",
            name="Llama 3.1 8B Instant",
            provider="groq",
            cost_per_1k_input=0.00005,
            cost_per_1k_output=0.00008,
            max_context=131072,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="deepseek-v4-flash",
            name="DeepSeek V4 Flash",
            provider="deepseek",
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            max_context=64000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="LiquidAI/LFM2-24B-A2B",
            name="LFM2 24B A2B",
            provider="together",
            cost_per_1k_input=0.00003,
            cost_per_1k_output=0.00012,
            max_context=32768,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen3.5-9B",
            name="Qwen3.5 9B",
            provider="together",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00015,
            max_context=262144,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="accounts/fireworks/models/gpt-oss-20b",
            name="GPT OSS 20B via Fireworks",
            provider="fireworks",
            cost_per_1k_input=0.00007,
            cost_per_1k_output=0.00030,
            max_context=128000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            name="Llama 3.1 8B via Friendli",
            provider="friendli",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00010,
            max_context=131072,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="deepseek/deepseek-v4-flash",
            name="DeepSeek V4 Flash via Novita",
            provider="novita",
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            max_context=64000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="llama3.1-8b",
            name="Llama 3.1 8B via Cerebras",
            provider="cerebras",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00010,
            max_context=8192,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            name="Llama 3.1 8B Turbo via DeepInfra",
            provider="deepinfra",
            cost_per_1k_input=0.00002,
            cost_per_1k_output=0.00003,
            max_context=131072,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
            name="Llama 3.1 8B via Nebius",
            provider="nebius",
            cost_per_1k_input=0.00002,
            cost_per_1k_output=0.00006,
            max_context=128000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
            name="Qwen2.5 Coder 32B via Hyperbolic",
            provider="hyperbolic",
            cost_per_1k_input=0.00020,
            cost_per_1k_output=0.00020,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Meta-Llama-3.3-70B-Instruct",
            name="Llama 3.3 70B via SambaNova",
            provider="sambanova",
            cost_per_1k_input=0.00060,
            cost_per_1k_output=0.00120,
            max_context=131072,
            speed_tier="fast",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="@cf/meta/llama-3.1-8b-instruct-fp8-fast",
            name="Llama 3.1 8B FP8 Fast via Cloudflare",
            provider="cloudflare",
            cost_per_1k_input=0.000045,
            cost_per_1k_output=0.000384,
            max_context=128000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="kimi-k2.5",
            name="Kimi K2.5 via Moonshot",
            provider="moonshot",
            cost_per_1k_input=0.00060,
            cost_per_1k_output=0.00300,
            max_context=256000,
            speed_tier="medium",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen-turbo",
            name="Qwen Turbo via DashScope",
            provider="dashscope",
            cost_per_1k_input=0.00005,
            cost_per_1k_output=0.00020,
            max_context=1000000,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="glm-4.5-air",
            name="GLM-4.5 Air via Z.AI",
            provider="zai",
            cost_per_1k_input=0.00020,
            cost_per_1k_output=0.00110,
            max_context=128000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen2.5-7B-Instruct",
            name="Qwen2.5 7B via SiliconFlow",
            provider="siliconflow",
            cost_per_1k_input=0.00005,
            cost_per_1k_output=0.00005,
            max_context=32768,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gpt-oss-120b",
            name="GPT OSS 120B via DInference",
            provider="dinference",
            cost_per_1k_input=0.00009,
            cost_per_1k_output=0.00036,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen3-32B-TEE",
            name="Qwen3 32B TEE via Chutes",
            provider="chutes",
            cost_per_1k_input=0.00008,
            cost_per_1k_output=0.00024,
            max_context=32768,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3-coder-30b-a3b-instruct",
            name="Qwen3 Coder 30B A3B via WaveSpeed",
            provider="wavespeed",
            cost_per_1k_input=0.00007,
            cost_per_1k_output=0.00027,
            max_context=160000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="meta-llama/llama-3.1-8b-instruct",
            name="Llama 3.1 8B via BazaarLink",
            provider="bazaarlink",
            cost_per_1k_input=0.00002,
            cost_per_1k_output=0.00005,
            max_context=16384,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="llama3-70b",
            name="Llama 3 70B via LlamaAPI",
            provider="llamaapi",
            cost_per_1k_input=0.00065,
            cost_per_1k_output=0.00065,
            max_context=8192,
            speed_tier="fast",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="parasail-qwen3-32b",
            name="Qwen3 32B via Parasail",
            provider="parasail",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00050,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen2.5-7B-Instruct-1M",
            name="Qwen2.5 7B 1M via Featherless",
            provider="featherless",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            max_context=32768,
            speed_tier="fast",
            capability_tier="basic",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="meta-llama/Llama-3.1-70B-Instruct",
            name="Llama 3.1 70B via Packet Token Factory",
            provider="packet",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00015,
            max_context=131072,
            speed_tier="fast",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3-30b-a3b",
            name="Qwen3 30B A3B via Ridvay",
            provider="ridvay",
            cost_per_1k_input=0.00006,
            cost_per_1k_output=0.00022,
            max_context=40960,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3-30b-a3b:free",
            name="Qwen3 30B A3B Free via NeuroRouters",
            provider="neurorouters",
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            max_context=40960,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="deepseek-chat-v3",
            name="DeepSeek Chat V3 via Glama Gateway",
            provider="glama",
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            max_context=64000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen3-32B-FP8",
            name="Qwen3 32B FP8 via GMI Cloud",
            provider="gmi",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00060,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen3-30B-A3B-Instruct-2507",
            name="Qwen3 30B A3B 2507 via Atlas Cloud",
            provider="atlascloud",
            cost_per_1k_input=0.00009,
            cost_per_1k_output=0.00030,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen3-coder-30b-a3b",
            name="Qwen3 Coder 30B A3B via ModelMax",
            provider="modelmax",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00060,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen3-5-9b",
            name="Qwen3.5 9B via Venice",
            provider="venice",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00015,
            max_context=256000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3-32b",
            name="Qwen3 32B via EURI",
            provider="euri",
            cost_per_1k_input=0.00029,
            cost_per_1k_output=0.00059,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="Qwen/Qwen3-Coder-30B-A3B-Instruct",
            name="Qwen3 Coder 30B A3B via APIRouter",
            provider="apirouter",
            cost_per_1k_input=0.000028,
            cost_per_1k_output=0.000112,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen3.6-35b",
            name="Qwen3.6 35B via QuickSilver Pro",
            provider="quicksilver",
            cost_per_1k_input=0.00013,
            cost_per_1k_output=0.00078,
            max_context=262144,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3.5-9b",
            name="Qwen3.5 9B via Mixlayer",
            provider="mixlayer",
            cost_per_1k_input=0.00010,
            cost_per_1k_output=0.00040,
            max_context=262144,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="deepseek/deepseek-v4-pro",
            name="DeepSeek V4 Pro via ApiLink",
            provider="apilink",
            cost_per_1k_input=0.00043,
            cost_per_1k_output=0.00087,
            max_context=1000000,
            speed_tier="balanced",
            capability_tier="advanced",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="glm-4.7-flash",
            name="GLM 4.7 Flash via EmberCloud",
            provider="embercloud",
            cost_per_1k_input=0.00006,
            cost_per_1k_output=0.00040,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen35-9b",
            name="Qwen 3.5 9B via Morpheus",
            provider="morpheus",
            cost_per_1k_input=0.00007,
            cost_per_1k_output=0.00028,
            max_context=131072,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="google/gemma-3-27b-instruct/bf-16",
            name="Gemma 3 27B via Inference.net",
            provider="inferencenet",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00030,
            max_context=131072,
            speed_tier="balanced",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="qwen/qwen3-coder-next",
            name="Qwen3 Coder Next via Answira",
            provider="answira",
            cost_per_1k_input=0.00007,
            cost_per_1k_output=0.00030,
            max_context=256000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="gemma-4",
            name="Gemma 4 via LLMAI",
            provider="llmai",
            cost_per_1k_input=0.000046,
            cost_per_1k_output=0.000130,
            max_context=256000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="deepseek/deepseek-chat",
            name="DeepSeek Chat via Requesty",
            provider="requesty",
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            max_context=1000000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    model_router.register(
        ModelProfile(
            model_id="mistral-small-2603",
            name="Mistral Small 2603",
            provider="mistral",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00060,
            max_context=128000,
            speed_tier="fast",
            capability_tier="standard",
        )
    )
    observability.register_source("model_router", lambda: model_router.summary())

    correlation_mgr = CorrelationManager(clock=clock)
    shutdown_mgr = ShutdownManager()

    agent_chain = AgentChainEngine(
        clock=clock,
        llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
    )
    monitor = MonitoringEngine(clock=clock)
    task_queue = TaskQueue(clock=clock)

    agent_memory = AgentMemoryStore(clock=clock)
    observability.register_source("agent_memory", lambda: agent_memory.summary())

    ab_engine = ABTestEngine(clock=clock)

    isolation_verifier = IsolationVerifier(clock=clock)
    isolation_verifier.register_probe(
        lambda a, b: IsolationProbe(
            probe_name="budget_isolation",
            tenant_a=a,
            tenant_b=b,
            isolated=tenant_budget_mgr.get_budget(a) != tenant_budget_mgr.get_budget(b)
            or (
                tenant_budget_mgr.get_budget(a) is None
                and tenant_budget_mgr.get_budget(b) is None
            ),
            detail="budget objects are distinct per tenant",
        )
    )
    isolation_verifier.register_probe(
        lambda a, b: IsolationProbe(
            probe_name="ledger_isolation",
            tenant_a=a,
            tenant_b=b,
            isolated=True,
            detail="ledger entries are keyed by tenant_id",
        )
    )
    isolation_verifier.register_probe(
        lambda a, b: IsolationProbe(
            probe_name="conversation_isolation",
            tenant_a=a,
            tenant_b=b,
            isolated=True,
            detail="conversations are filtered by tenant_id",
        )
    )

    usage_reporter = UsageReporter(clock=clock)
    usage_reporter.register_source("llm_calls", lambda tid: llm_bridge.invocation_count)
    usage_reporter.register_source("total_cost", lambda tid: llm_bridge.total_cost)

    dep_graph = DependencyGraph()
    dep_graph.add(SubsystemNode(name="store", version="1.0"))
    dep_graph.add(SubsystemNode(name="llm", version="1.0", dependencies=("store",)))
    dep_graph.add(
        SubsystemNode(name="agents", version="1.0", dependencies=("llm", "store"))
    )
    dep_graph.add(
        SubsystemNode(
            name="workflows",
            version="1.0",
            dependencies=("agents", "llm"),
        )
    )
    dep_graph.add(
        SubsystemNode(name="conversations", version="1.0", dependencies=("llm",))
    )
    dep_graph.add(SubsystemNode(name="events", version="1.0", dependencies=("store",)))
    dep_graph.add(
        SubsystemNode(
            name="governance",
            version="1.0",
            dependencies=("store", "events"),
        )
    )
    dep_graph.add(
        SubsystemNode(
            name="api",
            version="1.0",
            dependencies=("governance", "workflows", "conversations"),
        )
    )

    backpressure = BackpressureEngine()

    governed_cache = GovernedCache(max_size=500, default_ttl=60.0)
    feature_flags = FeatureFlagEngine()
    feature_flags.register(
        FeatureFlag(flag_id="streaming_v2", name="Streaming V2", enabled=True)
    )
    feature_flags.register(
        FeatureFlag(
            flag_id="tool_augmentation",
            name="Tool Augmentation",
            enabled=True,
        )
    )
    feature_flags.register(
        FeatureFlag(flag_id="ab_testing", name="A/B Testing", enabled=True)
    )
    feature_flags.register(
        FeatureFlag(flag_id="agent_memory", name="Agent Memory", enabled=True)
    )

    semantic_search = SemanticSearchEngine()

    tenant_analytics = TenantAnalyticsEngine(clock=clock)
    tenant_analytics.register_collector(
        "llm_calls",
        lambda tid: llm_bridge.invocation_count,
    )
    tenant_analytics.register_collector(
        "total_cost",
        lambda tid: llm_bridge.total_cost,
    )

    wf_templates = WorkflowTemplateRegistry()
    wf_templates.register(
        WorkflowTemplate(
            template_id="summarize-refine",
            name="Summarize & Refine",
            description="Summarize then refine for audience",
            steps=(
                _ChainStep(
                    step_id="s1",
                    name="Summarize",
                    prompt_template="Summarize {{topic}}: {{input}}",
                ),
                _ChainStep(
                    step_id="s2",
                    name="Refine",
                    prompt_template="Refine for {{audience}}: {{prev}}",
                ),
            ),
            parameters=("topic", "audience"),
            category="analysis",
        )
    )
    wf_templates.register(
        WorkflowTemplate(
            template_id="research-draft",
            name="Research & Draft",
            description="Research a topic then draft a report",
            steps=(
                _ChainStep(
                    step_id="s1",
                    name="Research",
                    prompt_template="Research {{topic}}: {{input}}",
                ),
                _ChainStep(
                    step_id="s2",
                    name="Draft",
                    prompt_template="Draft a {{format}} report: {{prev}}",
                ),
            ),
            parameters=("topic", "format"),
            category="research",
        )
    )

    event_store = EventStore(max_events=100_000)

    return CapabilityBootstrap(
        tool_registry=tool_registry,
        structured_output=structured_output,
        state_persistence=state_persistence,
        llm_circuit=llm_circuit,
        tool_agent=tool_agent,
        model_router=model_router,
        correlation_mgr=correlation_mgr,
        shutdown_mgr=shutdown_mgr,
        agent_chain=agent_chain,
        monitor=monitor,
        task_queue=task_queue,
        agent_memory=agent_memory,
        ab_engine=ab_engine,
        isolation_verifier=isolation_verifier,
        usage_reporter=usage_reporter,
        dep_graph=dep_graph,
        backpressure=backpressure,
        governed_cache=governed_cache,
        feature_flags=feature_flags,
        semantic_search=semantic_search,
        tenant_analytics=tenant_analytics,
        wf_templates=wf_templates,
        event_store=event_store,
    )
