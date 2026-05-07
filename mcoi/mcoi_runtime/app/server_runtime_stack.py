"""Runtime stack composition helpers for the governed server.

Purpose: isolate the sequential agent, subsystem, operational, and capability
bootstrap composition from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: server agent, subsystem, operational, and capability helpers.
Invariants:
  - Runtime bootstrap order remains deterministic.
  - Downstream bootstraps receive the same upstream wiring as before.
  - Selected server-exported globals preserve identity across the composition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.server_agents import bootstrap_agent_runtime
from mcoi_runtime.app.server_capabilities import bootstrap_capability_services
from mcoi_runtime.app.server_services import bootstrap_operational_services
from mcoi_runtime.app.server_subsystems import bootstrap_subsystems


@dataclass(frozen=True)
class ServerRuntimeStackBootstrap:
    """Runtime stack composition result."""

    agent_bootstrap: Any
    subsystem_bootstrap: Any
    operational_bootstrap: Any
    capability_bootstrap: Any
    observability: Any
    access_runtime: Any
    guard_chain: Any
    shutdown_mgr: Any
    state_persistence: Any


def bootstrap_server_runtime_stack(
    *,
    clock: Callable[[], str],
    env: str,
    runtime_env: Mapping[str, str],
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
    jwt_authenticator: Any,
    evaluate_expression_fn: Callable[..., Any],
    bootstrap_agent_runtime_fn: Callable[..., Any] = bootstrap_agent_runtime,
    bootstrap_subsystems_fn: Callable[..., Any] = bootstrap_subsystems,
    bootstrap_operational_services_fn: Callable[..., Any] = bootstrap_operational_services,
    bootstrap_capability_services_fn: Callable[..., Any] = bootstrap_capability_services,
) -> ServerRuntimeStackBootstrap:
    """Compose the runtime stack for the governed server."""
    agent_bootstrap = bootstrap_agent_runtime_fn(
        clock=clock,
        store=store,
        llm_bridge=llm_bridge,
        cert_daemon=cert_daemon,
        metrics=metrics,
        default_model=default_model,
        audit_trail=audit_trail,
        tenant_budget_mgr=tenant_budget_mgr,
        tenant_gating=tenant_gating,
        pii_scanner=pii_scanner,
        content_safety_chain=content_safety_chain,
        proof_bridge=proof_bridge,
        rate_limiter=rate_limiter,
        shell_policy=shell_policy,
    )
    observability = agent_bootstrap.observability

    subsystem_bootstrap = bootstrap_subsystems_fn(
        clock=clock,
        runtime_env=runtime_env,
        llm_bridge=llm_bridge,
        audit_trail=audit_trail,
        observability=observability,
        deep_health=agent_bootstrap.deep_health,
    )

    operational_bootstrap = bootstrap_operational_services_fn(
        clock=clock,
        env=env,
        runtime_env=runtime_env,
        cert_daemon=cert_daemon,
        workflow_engine=agent_bootstrap.workflow_engine,
        event_bus=subsystem_bootstrap.event_bus,
        observability=observability,
        audit_trail=audit_trail,
        metrics=metrics,
        tenant_budget_mgr=tenant_budget_mgr,
        rate_limiter=rate_limiter,
        jwt_authenticator=jwt_authenticator,
        tenant_gating=tenant_gating,
        access_runtime=subsystem_bootstrap.access_runtime,
        content_safety_chain=content_safety_chain,
        temporal_runtime=subsystem_bootstrap.temporal_runtime,
    )

    capability_bootstrap = bootstrap_capability_services_fn(
        clock=clock,
        runtime_env=runtime_env,
        llm_bridge=llm_bridge,
        observability=observability,
        tenant_budget_mgr=tenant_budget_mgr,
        evaluate_expression_fn=evaluate_expression_fn,
    )

    return ServerRuntimeStackBootstrap(
        agent_bootstrap=agent_bootstrap,
        subsystem_bootstrap=subsystem_bootstrap,
        operational_bootstrap=operational_bootstrap,
        capability_bootstrap=capability_bootstrap,
        observability=observability,
        access_runtime=subsystem_bootstrap.access_runtime,
        guard_chain=operational_bootstrap.guard_chain,
        shutdown_mgr=capability_bootstrap.shutdown_mgr,
        state_persistence=capability_bootstrap.state_persistence,
    )
