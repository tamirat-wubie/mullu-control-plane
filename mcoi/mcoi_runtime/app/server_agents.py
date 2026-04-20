"""Agent and observability bootstrap helpers for the governed HTTP server.

Purpose: isolate agent registry, workflow, health, config, and early
observability bootstrap from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: agent protocol, workflow engine, webhook manager, health, config,
and observability subsystems.
Invariants:
  - Default agent registrations remain stable.
  - Health probe names and bounded summaries remain deterministic.
  - Config bootstrap payload stays stable for llm, rate limits, and
    certification.
  - Workflow engine wiring remains bound to task manager, webhook manager, and
    audit trail.
  - Early observability sources remain stable and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.core.agent_protocol import (
    AgentCapability,
    AgentDescriptor,
    AgentRegistry,
    TaskManager,
)
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.config_reload import ConfigManager
from mcoi_runtime.core.deep_health import DeepHealthChecker
from mcoi_runtime.core.observability import ObservabilityAggregator
from mcoi_runtime.core.webhook_system import WebhookManager


@dataclass(frozen=True)
class AgentBootstrap:
    """Agent, workflow, and observability bootstrap result."""

    agent_registry: Any
    task_manager: Any
    webhook_manager: Any
    deep_health: Any
    config_manager: Any
    workflow_engine: Any
    observability: Any


def bootstrap_agent_runtime(
    *,
    clock: Callable[[], str],
    store: Any,
    llm_bridge: Any,
    cert_daemon: Any,
    metrics: Any,
    default_model: str,
    audit_trail: Any,
    tenant_budget_mgr: Any,
    tenant_gating: Any,
    pii_scanner: Any,
    content_safety_chain: Any,
    proof_bridge: Any,
    rate_limiter: Any,
    shell_policy: Any,
    agent_registry_cls: type[Any] = AgentRegistry,
    task_manager_cls: type[Any] = TaskManager,
    webhook_manager_cls: type[Any] = WebhookManager,
    deep_health_checker_cls: type[Any] = DeepHealthChecker,
    config_manager_cls: type[Any] = ConfigManager,
    workflow_engine_cls: type[Any] = AgentWorkflowEngine,
    observability_aggregator_cls: type[Any] = ObservabilityAggregator,
    agent_descriptor_cls: type[Any] = AgentDescriptor,
) -> AgentBootstrap:
    """Create the default agent runtime and early observability surfaces."""
    agent_registry = agent_registry_cls()
    agent_registry.register(
        agent_descriptor_cls(
            agent_id="llm-agent",
            name="LLM Completion Agent",
            capabilities=(
                AgentCapability.LLM_COMPLETION,
                AgentCapability.TOOL_USE,
            ),
        )
    )
    agent_registry.register(
        agent_descriptor_cls(
            agent_id="code-agent",
            name="Code Execution Agent",
            capabilities=(AgentCapability.CODE_EXECUTION,),
        )
    )
    task_manager = task_manager_cls(clock=clock, registry=agent_registry)
    webhook_manager = webhook_manager_cls(clock=clock)

    deep_health = deep_health_checker_cls(clock=clock)
    deep_health.register(
        "store",
        lambda: {"status": "healthy", "ledger_count": store.ledger_count()},
    )
    deep_health.register(
        "llm",
        lambda: {"status": "healthy", "invocations": llm_bridge.invocation_count},
    )
    deep_health.register(
        "certification",
        lambda: {"status": "healthy", **cert_daemon.status()},
    )
    deep_health.register(
        "metrics",
        lambda: {
            "status": "healthy",
            "counters": len(getattr(metrics, "KNOWN_COUNTERS", ())),
        },
    )

    config_manager = config_manager_cls(
        clock=clock,
        initial={
            "llm": {"default_model": default_model},
            "rate_limits": {"max_tokens": 60, "refill_rate": 1.0},
            "certification": {"interval_seconds": 300, "enabled": True},
        },
    )

    workflow_engine = workflow_engine_cls(
        clock=clock,
        task_manager=task_manager,
        llm_complete_fn=lambda prompt, budget_id: llm_bridge.complete(
            prompt,
            budget_id=budget_id,
        ),
        webhook_manager=webhook_manager,
        audit_trail=audit_trail,
    )

    observability = observability_aggregator_cls(clock=clock)
    observability.register_source("health", lambda: {"status": "healthy"})
    observability.register_source("llm", lambda: llm_bridge.budget_summary())
    observability.register_source(
        "tenants",
        lambda: {
            "count": tenant_budget_mgr.tenant_count(),
            "total_spent": tenant_budget_mgr.total_spent(),
        },
    )
    observability.register_source(
        "agents",
        lambda: {"agents": agent_registry.count, "tasks": task_manager.task_count},
    )
    observability.register_source("audit", lambda: audit_trail.summary())
    observability.register_source("certification", lambda: cert_daemon.status())
    observability.register_source("workflows", lambda: workflow_engine.summary())
    observability.register_source("tenant_gating", lambda: tenant_gating.summary())
    observability.register_source(
        "pii_scanner",
        lambda: {"enabled": pii_scanner.enabled, "patterns": pii_scanner.pattern_count},
    )
    observability.register_source(
        "content_safety",
        lambda: {
            "filters": content_safety_chain.filter_count,
            "names": content_safety_chain.filter_names(),
        },
    )
    observability.register_source("proof_bridge", lambda: proof_bridge.summary())
    observability.register_source("rate_limiter", lambda: rate_limiter.status())
    observability.register_source(
        "shell_policy",
        lambda: {
            "policy_id": shell_policy.policy_id,
            "enabled": shell_policy.enabled,
            "allowed": list(shell_policy.allowed_executables),
        },
    )

    return AgentBootstrap(
        agent_registry=agent_registry,
        task_manager=task_manager,
        webhook_manager=webhook_manager,
        deep_health=deep_health,
        config_manager=config_manager,
        workflow_engine=workflow_engine,
        observability=observability,
    )
