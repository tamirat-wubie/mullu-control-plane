"""Agent and observability bootstrap helpers for the governed HTTP server.

Purpose: isolate agent registry, workflow, health, config, and early
observability bootstrap from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: agent protocol, workflow engine, health, config, and observability.
Invariants:
  - Default agent registrations remain stable.
  - Health probe names and bounded summaries remain deterministic.
  - Config bootstrap payload stays stable for llm, rate limits, and certification.
  - Workflow engine wiring remains bound to task manager, webhook manager, and audit trail.
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
from mcoi_runtime.governance.network.webhook import WebhookManager


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


def _bounded_detail(value: Any) -> Any:
    """Return a small JSON-safe health payload."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _bounded_detail(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_bounded_detail(child) for child in list(value)[:20]]
    return str(type(value).__name__)


def _store_deep_health(store: Any) -> dict[str, Any]:
    """Readiness probe for durable store connectivity and basic shape.

    ``ledger_count`` is intentionally used as a real read round-trip. For the
    PostgreSQL store, a missing live connection is unhealthy before trying the
    query, and the schema_version table is read when available so migration
    drift is surfaced by the same probe without mutating state.
    """
    backend = type(store).__name__
    if backend == "PostgresStore" and getattr(store, "_conn", None) is None:
        return {
            "status": "unhealthy",
            "backend": backend,
            "detail": "connection_unavailable",
        }

    detail: dict[str, Any] = {
        "status": "healthy",
        "backend": backend,
        "ledger_count": store.ledger_count(),
    }
    for method_name in ("request_count", "active_session_count", "llm_invocation_count"):
        method = getattr(store, method_name, None)
        if callable(method):
            detail[method_name] = method()
    if backend == "PostgresStore":
        detail.update(_postgres_schema_readiness(store))
    return detail


def _postgres_schema_readiness(store: Any) -> dict[str, Any]:
    """Best-effort read-only PostgreSQL schema-version probe."""
    connection = getattr(store, "_connection", None)
    if not callable(connection):
        return {"schema_version_checked": False}
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        row = cur.fetchone()
    return {
        "schema_version_checked": True,
        "schema_version": int(row[0] if row else 0),
    }


def _llm_deep_health(llm_bridge: Any) -> dict[str, Any]:
    """Readiness fact for the LLM bridge."""
    backends = getattr(llm_bridge, "_backends", {}) or {}
    default = backends.get("default")
    if default is None:
        return {"status": "unhealthy", "detail": "no_default_backend"}
    provider = getattr(getattr(default, "provider", None), "value", "unknown")
    return {
        "status": "healthy",
        "provider": provider,
        "invocations": getattr(llm_bridge, "invocation_count", 0),
    }


def _proof_bridge_deep_health(proof_bridge: Any) -> dict[str, Any]:
    """Readiness probe for the proof bridge: proves it is callable."""
    summary = proof_bridge.summary()
    return {"status": "healthy", "receipt_count": summary.get("receipt_count", summary.get("proofs", 0))}


def _audit_deep_health(audit_trail: Any) -> dict[str, Any]:
    """Readiness probe for the audit trail: integrity of the hash chain."""
    summary = audit_trail.summary()
    chain_valid = bool(summary.get("chain_valid", True))
    return {
        "status": "healthy" if chain_valid else "unhealthy",
        "chain_valid": chain_valid,
        "entry_count": summary.get("entry_count", summary.get("count", 0)),
    }


def _rate_limiter_deep_health(rate_limiter: Any) -> dict[str, Any]:
    """Readiness probe for the rate limiter without evaluating a request."""
    return {"status": "healthy", **_bounded_detail(rate_limiter.status())}


def _tenant_budget_deep_health(tenant_budget_mgr: Any) -> dict[str, Any]:
    """Readiness probe for the tenant budget manager."""
    return {
        "status": "healthy",
        "tenant_count": tenant_budget_mgr.tenant_count(),
        "total_spent": tenant_budget_mgr.total_spent(),
    }


def _tenant_gating_deep_health(tenant_gating: Any) -> dict[str, Any]:
    """Readiness probe for tenant lifecycle gating state."""
    return {"status": "healthy", **_bounded_detail(tenant_gating.summary())}


def _content_safety_deep_health(content_safety_chain: Any) -> dict[str, Any]:
    """Readiness probe for the input/output safety chain."""
    filter_count = int(getattr(content_safety_chain, "filter_count", 0))
    return {
        "status": "healthy" if filter_count > 0 else "unhealthy",
        "filter_count": filter_count,
        "filters_configured": filter_count > 0,
    }


def _pii_scanner_deep_health(pii_scanner: Any) -> dict[str, Any]:
    """Readiness probe for PII scanner configuration."""
    return {
        "status": "healthy" if getattr(pii_scanner, "enabled", False) else "degraded",
        "enabled": bool(getattr(pii_scanner, "enabled", False)),
        "pattern_count": int(getattr(pii_scanner, "pattern_count", 0)),
    }


def _shell_policy_deep_health(shell_policy: Any) -> dict[str, Any]:
    """Readiness probe for shell policy posture without exposing command paths."""
    allowed = getattr(shell_policy, "allowed_executables", ()) or ()
    return {
        "status": "healthy" if getattr(shell_policy, "enabled", False) else "degraded",
        "policy_id": str(getattr(shell_policy, "policy_id", "")),
        "enabled": bool(getattr(shell_policy, "enabled", False)),
        "allowed_executable_count": len(tuple(allowed)),
    }


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
            capabilities=(AgentCapability.LLM_COMPLETION, AgentCapability.TOOL_USE),
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
    deep_health.register("store", lambda: _store_deep_health(store))
    deep_health.register("llm", lambda: _llm_deep_health(llm_bridge))
    deep_health.register("certification", lambda: {"status": "healthy", **cert_daemon.status()})
    deep_health.register(
        "metrics",
        lambda: {"status": "healthy", "counters": len(getattr(metrics, "KNOWN_COUNTERS", ()))},
    )
    deep_health.register("proof_bridge", lambda: _proof_bridge_deep_health(proof_bridge))
    deep_health.register("audit", lambda: _audit_deep_health(audit_trail))
    deep_health.register("rate_limiter", lambda: _rate_limiter_deep_health(rate_limiter))
    deep_health.register("tenant_budget", lambda: _tenant_budget_deep_health(tenant_budget_mgr))
    deep_health.register("tenant_gating", lambda: _tenant_gating_deep_health(tenant_gating))
    deep_health.register("content_safety", lambda: _content_safety_deep_health(content_safety_chain))
    deep_health.register("pii_scanner", lambda: _pii_scanner_deep_health(pii_scanner))
    deep_health.register("shell_policy", lambda: _shell_policy_deep_health(shell_policy))

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
        llm_complete_fn=lambda prompt, budget_id: llm_bridge.complete(prompt, budget_id=budget_id),
        webhook_manager=webhook_manager,
        audit_trail=audit_trail,
    )

    observability = observability_aggregator_cls(clock=clock)
    observability.register_source("health", lambda: {"status": "healthy"})
    observability.register_source("llm", lambda: llm_bridge.budget_summary())
    observability.register_source(
        "tenants",
        lambda: {"count": tenant_budget_mgr.tenant_count(), "total_spent": tenant_budget_mgr.total_spent()},
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
        lambda: {"filters": content_safety_chain.filter_count, "names": content_safety_chain.filter_names()},
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
