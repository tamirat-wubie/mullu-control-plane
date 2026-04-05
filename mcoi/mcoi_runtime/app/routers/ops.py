"""Operational / infrastructure endpoints extracted from server.py.

Covers metrics, rate-limiting, configuration management, monitoring,
deployment readiness, feature flags, dependency graphs, and all other
ops-facing routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Pydantic request models ──────────────────────────────────────────────


class ConfigUpdateRequest(BaseModel):
    changes: dict[str, Any]
    applied_by: str = "api"
    description: str = ""


class ConfigRollbackRequest(BaseModel):
    to_version: int
    applied_by: str = "api"


class CreateSnapshotRequest(BaseModel):
    snapshot_id: str
    name: str
    state: dict[str, Any] = Field(default_factory=dict)


# ═══ Governance Metrics ═══


@router.get("/api/v1/metrics")
def get_metrics():
    """Governance metrics -- counters, gauges, histograms."""
    return deps.metrics.to_dict()


# ═══ Rate Limiter ═══


@router.get("/api/v1/rate-limit/status")
def rate_limit_status():
    """Rate limiter status."""
    return deps.rate_limiter.status()


@router.get("/api/v1/rate-limits/{client_id}")
def get_rate_limit_info(client_id: str):
    """Return rate limit headers for a client."""
    deps.metrics.inc("requests_governed")
    info = deps.rate_limit_headers.peek(client_id)
    return {"headers": info.to_headers(), "is_exhausted": info.is_exhausted, "governed": True}


# ═══ Configuration ═══


@router.get("/api/v1/config")
def get_config():
    """Current runtime configuration."""
    return {
        "version": deps.config_manager.version,
        "config": deps.config_manager.get_all(),
        "hash": deps.config_manager.config_hash[:16] if deps.config_manager.config_hash else "",
    }


@router.get("/api/v1/config/history")
def config_history(limit: int = 10):
    """Configuration change history."""
    return {
        "versions": [
            {"version": v.version, "hash": v.config_hash[:16], "by": v.applied_by, "at": v.applied_at, "desc": v.description}
            for v in deps.config_manager.history(limit=limit)
        ],
    }


@router.post("/api/v1/config/update")
def update_config(req: ConfigUpdateRequest):
    """Hot-reload configuration via REST API."""
    deps.metrics.inc("requests_governed")
    result = deps.config_manager.update(
        req.changes, applied_by=req.applied_by, description=req.description,
    )
    deps.audit_trail.record(
        action="config.update", actor_id=req.applied_by,
        tenant_id="system", target="config",
        outcome="success" if result.success else "denied",
        detail={"version": result.version, "changes": list(req.changes.keys())},
    )
    deps.event_bus.publish(
        "config.updated" if result.success else "config.rejected",
        source="config_manager",
        payload={"version": result.version, "success": result.success},
    )
    return {
        "success": result.success,
        "version": result.version,
        "previous_version": result.previous_version,
        "error": result.error,
    }


@router.post("/api/v1/config/rollback")
def rollback_config(req: ConfigRollbackRequest):
    """Rollback configuration to a previous version."""
    deps.metrics.inc("requests_governed")
    result = deps.config_manager.rollback(req.to_version, applied_by=req.applied_by)
    deps.audit_trail.record(
        action="config.rollback", actor_id=req.applied_by,
        tenant_id="system", target="config",
        outcome="success" if result.success else "denied",
        detail={"to_version": req.to_version},
    )
    return {
        "success": result.success,
        "version": result.version,
        "error": result.error,
    }


@router.get("/api/v1/config/watcher")
def get_config_watcher_status():
    """Return config file watcher status."""
    deps.metrics.inc("requests_governed")
    return {"config_watcher": deps.config_watcher.summary(), "governed": True}


@router.get("/api/v1/config/drift")
def get_config_drift():
    """Return config drift detection summary."""
    deps.metrics.inc("requests_governed")
    return {"drift": deps.config_drift.summary(), "governed": True}


# ═══ Observability Dashboard ═══


@router.get("/api/v1/dashboard")
def dashboard():
    """Aggregated observability dashboard data."""
    return deps.observability.collect_all()


# ═══ Plugins ═══


@router.get("/api/v1/plugins")
def list_plugins():
    """List registered plugins."""
    return {
        "plugins": [
            {"id": p.descriptor.plugin_id, "name": p.descriptor.name, "version": p.descriptor.version, "status": p.status.value}
            for p in deps.plugin_registry.list_plugins()
        ],
        "summary": deps.plugin_registry.summary(),
    }


# ═══ Governance Guards ═══


@router.get("/api/v1/guards")
def list_guards():
    """List governance guard chain."""
    from mcoi_runtime.core.governance_guard import (
        GovernanceGuardChain, create_rate_limit_guard,
        create_budget_guard, create_tenant_guard,
    )
    chain = GovernanceGuardChain()
    chain.add(create_tenant_guard())
    chain.add(create_rate_limit_guard(deps.rate_limiter))
    chain.add(create_budget_guard(deps.tenant_budget_mgr))
    return {
        "guards": chain.guard_names(),
        "count": chain.guard_count,
    }


# ═══ Capabilities ═══


@router.get("/api/v1/capabilities")
def list_capabilities():
    """List available agent capabilities."""
    from mcoi_runtime.core.agent_protocol import AgentCapability
    return {
        "capabilities": [
            {"id": c.value, "name": c.name}
            for c in AgentCapability
        ],
    }


# ═══ Version & Release ═══


@router.get("/api/v1/version")
def api_version():
    """API version info."""
    return {
        "version": "1.0.0",
        "api_version": "v1",
        "endpoints": deps.api_versions.endpoint_count,
        "summary": deps.api_versions.summary(),
        "governed": True,
    }


@router.get("/api/v1/release")
def release_info():
    """v1.0.0 release information."""
    return {
        "version": "1.0.0",
        "phase": 210,
        "endpoints": 80,
        "tests": 43800,
        "components": {
            "llm": "GovernedLLMAdapter (Anthropic/OpenAI/Stub)",
            "agents": "AgentWorkflowEngine + TracedWorkflowEngine",
            "conversations": "ConversationStore + ChatWorkflowEngine",
            "governance": "GuardChain + AuditTrail + RateLimiter + MetricsEngine",
            "observability": "ObservabilityAggregator + HealthAggregator + CostAnalytics",
            "events": "EventBus + WebhookManager",
            "pipelines": "BatchPipeline + PromptTemplateEngine",
            "plugins": "PluginRegistry (2 active)",
            "config": "ConfigManager (versioned, hot-reload, rollback)",
            "persistence": "InMemoryStore / SQLiteStore / PostgresStore",
            "replay": "ReplayRecorder + ReplayExecutor",
            "schemas": "SchemaValidator (7 rule types)",
            "tools": "ToolRegistry + ToolAugmentedAgent",
            "streaming": "AnthropicStreamingAdapter",
            "state": "StatePersistence (atomic JSON)",
            "structured_output": "StructuredOutputEngine",
            "retry": "RetryExecutor + CircuitBreaker",
        },
        "governed": True,
    }


@router.get("/api/v1/release/latest")
def latest_release():
    """Latest release information."""
    return {
        "version": "1.2.0",
        "phase": 214,
        "endpoints": 105,
        "tests": 43950,
        "highlights": [
            "Multi-model routing (auto-select by task complexity)",
            "Request correlation (trace-ID propagation)",
            "Graceful shutdown contracts",
            "Production readiness checks",
        ],
        "governed": True,
    }


# ═══ System Snapshot ═══


@router.get("/api/v1/snapshot")
def system_snapshot():
    """Full system state export -- all subsystem summaries in one call."""
    return {
        "version": "0.6.0",
        "environment": deps.ENV,
        "store": {"ledger_count": deps.store.ledger_count()},
        "llm": {"invocations": deps.llm_bridge.invocation_count, "total_cost": deps.llm_bridge.total_cost, **deps.llm_bridge.budget_summary()},
        "certification": deps.cert_daemon.status(),
        "tenants": {"count": deps.tenant_budget_mgr.tenant_count(), "total_spent": deps.tenant_budget_mgr.total_spent()},
        "agents": {"count": deps.agent_registry.count, "tasks": deps.task_manager.task_count},
        "workflows": deps.workflow_engine.summary(),
        "pipelines": deps.batch_pipeline.summary(),
        "metrics": deps.metrics.to_dict(),
        "audit": deps.audit_trail.summary(),
        "events": deps.event_bus.summary(),
        "webhooks": deps.webhook_manager.summary(),
        "config": deps.config_manager.summary(),
        "plugins": deps.plugin_registry.summary(),
        "rate_limiter": deps.rate_limiter.status(),
        "captured_at": deps._clock(),
    }


# ═══ Production Readiness ═══


@router.get("/api/v1/readiness")
def production_readiness():
    """Production readiness checks -- verifies all subsystems are operational."""
    checks = {
        "llm_bridge": deps.llm_bridge.invocation_count >= 0,
        "store": deps.store.ledger_count() >= 0,
        "audit_trail": deps.audit_trail.entry_count >= 0,
        "event_bus": deps.event_bus.event_count >= 0,
        "metrics": deps.metrics.counter("requests_total") >= 0,
        "config": deps.config_manager.version >= 1,
        "tool_registry": deps.tool_registry.tool_count >= 1,
        "model_router": deps.model_router.model_count >= 1,
        "plugins": deps.plugin_registry.count >= 1,
        "health_agg": deps.health_agg.component_count >= 1,
        "schema_validator": deps.schema_validator.count >= 1,
        "guard_chain": deps.guard_chain.guard_count >= 1,
    }
    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
        "version": "1.3.0",
        "subsystems": len(checks),
        "governed": True,
    }


# ═══ Monitoring ═══


@router.get("/api/v1/monitor")
def monitoring_dashboard():
    """Real-time monitoring vitals."""
    vitals = deps.monitor.compute_vitals(
        active_tenants=deps.tenant_budget_mgr.tenant_count(),
        llm_calls=deps.llm_bridge.invocation_count,
        total_cost=deps.llm_bridge.total_cost,
        health_score=deps.health_agg.compute().overall_score,
        circuit_state=deps.llm_circuit.state.value,
        event_count=deps.event_bus.event_count,
    )
    return {
        "uptime_seconds": vitals.uptime_seconds,
        "requests_per_minute": vitals.requests_per_minute,
        "errors_per_minute": vitals.errors_per_minute,
        "error_rate_pct": vitals.error_rate_pct,
        "active_tenants": vitals.active_tenants,
        "llm_calls_total": vitals.llm_calls_total,
        "total_cost": vitals.total_cost,
        "health_score": vitals.health_score,
        "circuit_breaker": vitals.circuit_breaker_state,
        "events": vitals.event_bus_events,
        "captured_at": vitals.captured_at,
    }


# ═══ Shutdown / Correlation ═══


@router.get("/api/v1/shutdown/info")
def shutdown_info():
    """Graceful shutdown configuration."""
    return deps.shutdown_mgr.summary()


@router.get("/api/v1/correlation/active")
def active_correlations():
    """Active request correlations."""
    return deps.correlation_mgr.summary()


# ═══ Prometheus Metrics ═══


@router.get("/metrics")
def prometheus_metrics():
    """Export metrics in Prometheus text exposition format."""
    deps.prom_exporter.inc_counter("requests_governed_total")
    return PlainTextResponse(content=deps.prom_exporter.export(), media_type="text/plain")


# ═══ Grafana Dashboard ═══


@router.get("/api/v1/grafana/dashboard")
def get_grafana_dashboard():
    """Export the default Grafana dashboard JSON."""
    deps.metrics.inc("requests_governed")
    return deps.grafana_dashboard.generate()


# ═══ Notifications ═══


@router.get("/api/v1/notifications/summary")
def get_notification_summary():
    """Return notification dispatcher summary."""
    deps.metrics.inc("requests_governed")
    return {"notifications": deps.notification_dispatcher.summary(), "governed": True}


# ═══ Validation ═══


@router.get("/api/v1/validation/schemas")
def list_validation_schemas():
    """List registered validation schemas."""
    deps.metrics.inc("requests_governed")
    return {"validation": deps.input_validator.summary(), "governed": True}


# ═══ Idempotency ═══


@router.get("/api/v1/idempotency/summary")
def get_idempotency_summary():
    """Return idempotency store summary."""
    deps.metrics.inc("requests_governed")
    return {"idempotency": deps.idempotency_store.summary(), "governed": True}


# ═══ Compression ═══


@router.get("/api/v1/compression/summary")
def get_compression_summary():
    """Return response compression summary."""
    deps.metrics.inc("requests_governed")
    return {"compression": deps.response_compressor.summary(), "governed": True}


# ═══ Canary Deployment ═══


@router.get("/api/v1/canary")
def get_canary_status():
    """Return canary deployment status."""
    deps.metrics.inc("requests_governed")
    return {"canary": deps.canary_controller.summary(), "governed": True}


# ═══ Secret Rotation ═══


@router.get("/api/v1/secrets/summary")
def get_secrets_summary():
    """Return secret rotation engine summary."""
    deps.metrics.inc("requests_governed")
    return {"secrets": deps.secret_rotation.summary(), "governed": True}


# ═══ Request Deduplication ═══


@router.get("/api/v1/dedup/summary")
def get_dedup_summary():
    """Return request deduplication summary."""
    deps.metrics.inc("requests_governed")
    return {"dedup": deps.request_dedup.summary(), "governed": True}


# ═══ Rollback Snapshots ═══


@router.get("/api/v1/snapshots")
def list_snapshots(limit: int = 10):
    """List recent system snapshots."""
    deps.metrics.inc("requests_governed")
    snaps = deps.snapshot_mgr.list_snapshots(limit=limit)
    return {
        "snapshots": [s.to_dict() for s in snaps],
        "summary": deps.snapshot_mgr.summary(),
        "governed": True,
    }


@router.post("/api/v1/snapshots")
def create_snapshot(req: CreateSnapshotRequest):
    """Create a system state snapshot."""
    deps.metrics.inc("requests_governed")
    snap = deps.snapshot_mgr.create_snapshot(req.snapshot_id, req.name, req.state)
    return {"snapshot": snap.to_dict(), "governed": True}


# ═══ Deploy Readiness ═══


@router.get("/api/v1/deploy/readiness")
def get_deploy_readiness():
    """Run deployment readiness checks."""
    deps.metrics.inc("requests_governed")
    report = deps.deploy_checker.run_all()
    return {"readiness": report.to_dict(), "governed": True}


# ═══ API Migration ═══


@router.get("/api/v1/migrations/summary")
def get_migration_summary():
    """Return API version migration summary."""
    deps.metrics.inc("requests_governed")
    return {
        "migrations": deps.api_migration.summary(),
        "versions": [v.to_dict() for v in deps.api_migration.list_versions()],
        "governed": True,
    }


# ═══ Retry Policy ═══


@router.get("/api/v1/retries/summary")
def get_retries_summary():
    """Return governed retry policy summary."""
    deps.metrics.inc("requests_governed")
    return {"retries": deps.retry_engine.summary(), "governed": True}


# ═══ Region Routing ═══


@router.get("/api/v1/regions")
def get_regions():
    """Return multi-region routing status."""
    deps.metrics.inc("requests_governed")
    return {"regions": deps.region_router.summary(), "governed": True}


# ═══ Request Context ═══


@router.get("/api/v1/context/summary")
def get_context_summary():
    """Return request context factory summary."""
    deps.metrics.inc("requests_governed")
    return {"context": deps.request_ctx_factory.summary(), "governed": True}


# ═══ Circuit Breaker Dashboard ═══


@router.get("/api/v1/circuits/dashboard")
def get_circuit_dashboard():
    """Return circuit breaker dashboard aggregate."""
    deps.metrics.inc("requests_governed")
    return {"circuits": deps.circuit_dashboard.summary(), "governed": True}


# ═══ Cache Stats ═══


@router.get("/api/v1/cache/stats")
def cache_stats():
    """Cache statistics."""
    return deps.governed_cache.summary()


# ═══ Feature Flags ═══


@router.get("/api/v1/flags")
def list_feature_flags():
    """List feature flags."""
    return {
        "flags": [
            {"id": f.flag_id, "name": f.name, "enabled": f.enabled}
            for f in deps.feature_flags.list_flags()
        ],
        "summary": deps.feature_flags.summary(),
    }


@router.get("/api/v1/flags/{flag_id}")
def check_flag(flag_id: str, tenant_id: str = ""):
    """Check if a feature flag is enabled."""
    return {"flag_id": flag_id, "enabled": deps.feature_flags.is_enabled(flag_id, tenant_id=tenant_id)}


# ═══ Dependency Graph ═══


@router.get("/api/v1/dependencies")
def dependency_graph_endpoint():
    """Subsystem dependency graph."""
    return {
        "startup_order": deps.dep_graph.topological_sort(),
        "summary": deps.dep_graph.summary(),
    }


@router.get("/api/v1/dependencies/{name}/impact")
def dependency_impact(name: str):
    """Impact analysis if a subsystem fails."""
    impacted = deps.dep_graph.impact_of_failure(name)
    return {"subsystem": name, "impacted": impacted, "count": len(impacted)}


# ═══ Backpressure ═══


@router.get("/api/v1/backpressure")
def backpressure_status():
    """Current backpressure state."""
    return deps.backpressure.status()


# ═══ Traces Summary ═══


@router.get("/api/v1/traces/summary")
def get_traces_summary():
    """Return OpenTelemetry trace exporter summary."""
    deps.metrics.inc("requests_governed")
    return {"traces": deps.otel_exporter.summary(), "governed": True}


# ═══ Coordination Checkpoint / Restore ═══


class CoordinationCheckpointRequest(BaseModel):
    checkpoint_id: str
    lease_duration_seconds: int = 3600


class CoordinationRestoreRequest(BaseModel):
    checkpoint_id: str
    current_policy_pack_id: str = ""


@router.post("/api/v1/coordination/checkpoint")
def save_coordination_checkpoint(req: CoordinationCheckpointRequest):
    """Save a coordination engine checkpoint with governed lease."""
    deps.metrics.inc("requests_governed")
    checkpoint = deps.coordination_engine.save_checkpoint(
        req.checkpoint_id,
        lease_duration_seconds=req.lease_duration_seconds,
    )
    deps.audit_trail.record(
        action="coordination.checkpoint.save",
        actor_id="api",
        tenant_id="system",
        target=req.checkpoint_id,
        outcome="success",
        detail={
            "lease_expires_at": checkpoint.lease_expires_at,
            "delegations": len(checkpoint.delegations),
            "handoffs": len(checkpoint.handoffs),
        },
    )
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at,
        "lease_expires_at": checkpoint.lease_expires_at,
        "delegations": len(checkpoint.delegations),
        "handoffs": len(checkpoint.handoffs),
        "merges": len(checkpoint.merges),
        "conflicts": len(checkpoint.conflicts),
        "governed": True,
    }


@router.post("/api/v1/coordination/restore")
def restore_coordination_checkpoint(req: CoordinationRestoreRequest):
    """Restore coordination engine state from a governed checkpoint."""
    from mcoi_runtime.persistence.errors import PersistenceError
    deps.metrics.inc("requests_governed")
    try:
        outcome = deps.coordination_engine.restore_checkpoint(
            req.checkpoint_id,
            current_policy_pack_id=req.current_policy_pack_id or None,
        )
    except PersistenceError:
        from fastapi import HTTPException
        raise HTTPException(404, detail={
            "error": "checkpoint not found",
            "error_code": "checkpoint_not_found",
            "governed": True,
        })
    deps.audit_trail.record(
        action="coordination.checkpoint.restore",
        actor_id="api",
        tenant_id="system",
        target=req.checkpoint_id,
        outcome=outcome.status.value,
        detail={"reason": outcome.reason},
    )
    return {
        "checkpoint_id": outcome.checkpoint_id,
        "status": outcome.status.value,
        "reason": outcome.reason,
        "restored_at": outcome.restored_at,
        "governed": True,
    }


# ═══ Governance Benchmarks ═══


@router.post("/api/v1/ops/benchmarks")
def run_benchmarks():
    """Run governance performance benchmarks and return results."""
    from mcoi_runtime.core.governance_bench import run_governance_benchmarks
    suite = run_governance_benchmarks()
    return {"governed": True, **suite.summary()}


# ═══ Import Analysis ═══


@router.get("/api/v1/ops/imports")
def analyze_imports():
    """Analyze import dependencies and check for cycles.

    Note: This endpoint performs full AST analysis of all Python files.
    May take 500ms-2s on large codebases. Use sparingly.
    """
    import os as _os
    from mcoi_runtime.core.import_analyzer import ImportAnalyzer
    import mcoi_runtime
    runtime_dir = _os.path.dirname(_os.path.dirname(mcoi_runtime.__file__))
    mcoi_dir = _os.path.join(runtime_dir, "mcoi_runtime")
    analyzer = ImportAnalyzer(root_package="mcoi_runtime")
    result = analyzer.analyze_directory(mcoi_dir)
    summary = analyzer.dependency_summary(result)
    return {"governed": True, **summary}


# ═══ Proof Bridge Status ═══


@router.get("/api/v1/ops/proof-bridge")
def proof_bridge_status():
    """Get proof bridge certification status."""
    bridge = deps.get("proof_bridge")
    if bridge is None:
        return {"governed": True, "status": "not_initialized"}
    return {"governed": True, **bridge.summary()}
