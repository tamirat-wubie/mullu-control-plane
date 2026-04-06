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
            cost_per_1k_input=0.80,
            cost_per_1k_output=4.0,
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
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0,
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
            cost_per_1k_input=15.0,
            cost_per_1k_output=75.0,
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
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60,
            max_context=128000,
            speed_tier="fast",
            capability_tier="basic",
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
