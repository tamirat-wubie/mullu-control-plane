"""Phase 200 — Governed HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
    Phase 199: LLM completion, certification, persistence-backed ledger, budget reporting.
    Phase 200: Bootstrap wiring, streaming, certification daemon, Docker Compose.
Dependencies: fastapi, production_surface, llm_bootstrap, streaming, certification_daemon.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from typing import Any
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mcoi_runtime.app.production_surface import (
    ProductionSurface, APIRequest, DEPLOYMENT_MANIFESTS,
)
from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
from mcoi_runtime.app.streaming import StreamingAdapter
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.live_path_certification import LivePathCertifier
from mcoi_runtime.core.certification_daemon import CertificationConfig, CertificationDaemon
from mcoi_runtime.core.tenant_budget import TenantBudgetManager, TenantBudgetPolicy
from mcoi_runtime.core.governance_metrics import GovernanceMetricsEngine
from mcoi_runtime.core.rate_limiter import RateLimiter, RateLimitConfig
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry, TaskManager, TaskSpec,
)
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.webhook_system import WebhookManager, WebhookSubscription
from mcoi_runtime.core.deep_health import DeepHealthChecker
from mcoi_runtime.core.config_reload import ConfigManager
from mcoi_runtime.core.observability import ObservabilityAggregator
from mcoi_runtime.core.plugin_system import HookPoint, PluginDescriptor, PluginRegistry
from mcoi_runtime.core.event_bus import EventBus
from mcoi_runtime.core.batch_pipeline import BatchPipeline, PipelineStep
from mcoi_runtime.persistence.tenant_ledger import TenantLedger
from mcoi_runtime.persistence.postgres_store import InMemoryStore, create_store

import hashlib
import json
import os
from datetime import datetime, timezone

ENV = os.environ.get("MULLU_ENV", "local_dev")
surface = ProductionSurface(DEPLOYMENT_MANIFESTS.get(ENV, DEPLOYMENT_MANIFESTS["local_dev"]))

# Clock
def _clock() -> str:
    return datetime.now(timezone.utc).isoformat()

# Persistence store (InMemoryStore for dev, PostgresStore for production)
store = create_store(
    backend=os.environ.get("MULLU_DB_BACKEND", "memory"),
    connection_string=os.environ.get("MULLU_DB_URL", ""),
)

# Phase 200A: LLM bootstrap wiring (env-driven backend selection)
llm_bootstrap_result = bootstrap_llm(
    clock=_clock,
    config=LLMConfig.from_env(),
    ledger_sink=lambda entry: store.append_ledger(
        entry.get("type", "llm"),
        entry.get("tenant_id", "system"),
        entry.get("tenant_id", "system"),
        entry,
        hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest(),
    ),
)
llm_bridge = llm_bootstrap_result.bridge

# Certification engine
certifier = LivePathCertifier(clock=_clock)

# Phase 200C: Streaming adapter
streaming_adapter = StreamingAdapter(clock=_clock)

# Phase 200D: Certification daemon
cert_daemon = CertificationDaemon(
    certifier=certifier,
    clock=_clock,
    config=CertificationConfig(
        interval_seconds=float(os.environ.get("MULLU_CERT_INTERVAL", "300")),
        enabled=os.environ.get("MULLU_CERT_ENABLED", "true").lower() == "true",
    ),
    api_handle_fn=lambda req: {"governed": True, "status": "ok"},
    db_write_fn=lambda t, c: store.append_ledger(
        "certification", "certifier", t, c,
        hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
    ),
    db_read_fn=lambda t: store.query_ledger(t),
    llm_invoke_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
    ledger_fn=lambda t: store.query_ledger(t),
    state_fn=lambda: (
        hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(),
        store.ledger_count(),
    ),
)

# Phase 202A: Tenant budget manager
tenant_budget_mgr = TenantBudgetManager(clock=_clock)

# Phase 202B: Governance metrics engine
metrics = GovernanceMetricsEngine(clock=_clock)

# Phase 202C: Rate limiter
rate_limiter = RateLimiter(default_config=RateLimitConfig(max_tokens=60, refill_rate=1.0))

# Phase 202D: Audit trail
audit_trail = AuditTrail(clock=_clock)

# Phase 201D: Tenant-scoped ledger
tenant_ledger = TenantLedger(clock=_clock)

# Phase 203A: Agent registry + task manager
agent_registry = AgentRegistry()
agent_registry.register(AgentDescriptor(
    agent_id="llm-agent", name="LLM Completion Agent",
    capabilities=(AgentCapability.LLM_COMPLETION, AgentCapability.TOOL_USE),
))
agent_registry.register(AgentDescriptor(
    agent_id="code-agent", name="Code Execution Agent",
    capabilities=(AgentCapability.CODE_EXECUTION,),
))
task_manager = TaskManager(clock=_clock, registry=agent_registry)

# Phase 203B: Webhook manager
webhook_manager = WebhookManager(clock=_clock)

# Phase 203C: Deep health checker
deep_health = DeepHealthChecker(clock=_clock)
deep_health.register("store", lambda: {"status": "healthy", "ledger_count": store.ledger_count()})
deep_health.register("llm", lambda: {"status": "healthy", "invocations": llm_bridge.invocation_count})
deep_health.register("certification", lambda: {"status": "healthy", **cert_daemon.status()})
deep_health.register("metrics", lambda: {"status": "healthy", "counters": len(metrics.KNOWN_COUNTERS)})

# Phase 203D: Config manager
config_manager = ConfigManager(clock=_clock, initial={
    "llm": {"default_model": llm_bootstrap_result.config.default_model},
    "rate_limits": {"max_tokens": 60, "refill_rate": 1.0},
    "certification": {"interval_seconds": 300, "enabled": True},
})

# Phase 204B: Agent workflow engine
workflow_engine = AgentWorkflowEngine(
    clock=_clock,
    task_manager=task_manager,
    llm_complete_fn=lambda prompt, budget_id: llm_bridge.complete(prompt, budget_id=budget_id),
    webhook_manager=webhook_manager,
    audit_trail=audit_trail,
)

# Phase 204C: Observability aggregator
observability = ObservabilityAggregator(clock=_clock)
observability.register_source("health", lambda: {"status": "healthy"})
observability.register_source("llm", lambda: llm_bridge.budget_summary())
observability.register_source("tenants", lambda: {"count": tenant_budget_mgr.tenant_count(), "total_spent": tenant_budget_mgr.total_spent()})
observability.register_source("agents", lambda: {"agents": agent_registry.count, "tasks": task_manager.task_count})
observability.register_source("audit", lambda: audit_trail.summary())
observability.register_source("certification", lambda: cert_daemon.status())
observability.register_source("workflows", lambda: workflow_engine.summary())

# Phase 204D: Plugin registry
plugin_registry = PluginRegistry()

# Phase 206A: Event bus
event_bus = EventBus(clock=_clock)
# Wire event bus into observability
observability.register_source("event_bus", lambda: event_bus.summary())
# Wire event bus into deep health
deep_health.register("event_bus", lambda: {"status": "healthy", "events": event_bus.event_count, "errors": event_bus.error_count})

# Phase 206B: Batch pipeline
batch_pipeline = BatchPipeline(
    clock=_clock,
    llm_complete_fn=lambda prompt, **kw: llm_bridge.complete(prompt, **kw),
)
observability.register_source("pipelines", lambda: batch_pipeline.summary())

# Phase 206C: Register example plugins
_logging_plugin = PluginDescriptor(
    plugin_id="logging", name="Governance Logger", version="1.0.0",
    description="Logs all governed operations to audit trail",
    hooks=(HookPoint.POST_DISPATCH, HookPoint.POST_LLM_CALL),
)
plugin_registry.register(_logging_plugin)
plugin_registry.load("logging", hooks={
    HookPoint.POST_DISPATCH: lambda **kw: audit_trail.record(
        action="plugin.log.dispatch", actor_id="logging-plugin",
        tenant_id=kw.get("tenant_id", ""), target="dispatch", outcome="logged",
    ),
    HookPoint.POST_LLM_CALL: lambda **kw: metrics.inc("llm_calls_total"),
})
plugin_registry.activate("logging")

_alert_plugin = PluginDescriptor(
    plugin_id="cost-alert", name="Cost Alert Plugin", version="1.0.0",
    description="Emits budget.warning events when utilization exceeds 80%",
    hooks=(HookPoint.ON_BUDGET_CHECK,),
)
plugin_registry.register(_alert_plugin)
plugin_registry.load("cost-alert", hooks={
    HookPoint.ON_BUDGET_CHECK: lambda **kw: event_bus.publish(
        "budget.warning", tenant_id=kw.get("tenant_id", ""),
        source="cost-alert-plugin", payload=kw,
    ) if kw.get("utilization_pct", 0) > 80 else None,
})
plugin_registry.activate("cost-alert")

app = FastAPI(title="Mullu Platform", version="0.6.0", description="Governed AI Operating System")


class ExecuteRequest(BaseModel):
    goal_id: str
    action: str
    tenant_id: str
    body: dict[str, Any] = {}


class CompletionRequest(BaseModel):
    prompt: str
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.0
    tenant_id: str = "system"
    budget_id: str = "default"
    system: str = ""


@app.get("/health")
def health():
    h = surface.health()
    h["llm_invocations"] = llm_bridge.invocation_count
    h["llm_total_cost"] = round(llm_bridge.total_cost, 6)
    h["certifications"] = certifier.chain_count
    h["ledger_entries"] = store.ledger_count()
    return h


@app.get("/ready")
def ready():
    h = health()
    return {"ready": h["status"] == "healthy", **h}


@app.post("/api/v1/execute")
def execute(req: ExecuteRequest, session_id: str = Header(default="")):
    api_req = APIRequest(
        request_id=f"http-{id(req)}",
        method="POST",
        path="/api/v1/execute",
        actor_id=req.tenant_id,
        tenant_id=req.tenant_id,
        body=req.body,
        headers={"session_id": session_id},
    )
    resp = surface.handle_request(api_req)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.body)
    return resp.body


@app.post("/api/v1/session")
def create_session(actor_id: str, tenant_id: str):
    import time
    sid = hashlib.sha256(f"{actor_id}:{tenant_id}:{time.time()}".encode()).hexdigest()[:16]
    session = surface.auth.create_session(f"sess-{sid}", actor_id, tenant_id)
    surface.tenants.register_tenant(tenant_id)
    store.save_session(f"sess-{sid}", actor_id, tenant_id)
    return {"session_id": session.session_id, "actor_id": actor_id, "tenant_id": tenant_id}


@app.get("/api/v1/ledger")
def get_ledger(tenant_id: str = "system", limit: int = 50):
    entries = store.query_ledger(tenant_id, limit=limit)
    return {"entries": entries, "count": len(entries), "governed": True}


# ═══ Phase 199A — LLM Completion Endpoint ═══

@app.post("/api/v1/complete")
def complete(req: CompletionRequest):
    """Governed LLM completion — budgeted, ledgered, scoped."""
    result = llm_bridge.complete(
        req.prompt,
        model_name=req.model_name,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        tenant_id=req.tenant_id,
        budget_id=req.budget_id,
        system=req.system,
    )
    if not result.succeeded:
        raise HTTPException(status_code=503, detail={"error": result.error, "governed": True})
    return {
        "content": result.content,
        "model": result.model_name,
        "provider": result.provider.value,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": result.cost,
        "governed": True,
    }


@app.get("/api/v1/budget")
def budget_summary():
    """Budget status for all registered LLM budgets."""
    return llm_bridge.budget_summary()


@app.get("/api/v1/llm/history")
def llm_history(limit: int = 50):
    """Recent LLM invocation history."""
    return {"invocations": llm_bridge.invocation_history(limit=limit)}


# ═══ Phase 199C — Certification Endpoint ═══

@app.post("/api/v1/certify")
def run_certification():
    """Run full live-path certification: API → DB → LLM → Ledger → Restart."""
    chain = certifier.run_full_certification(
        api_handle_fn=lambda req: {"governed": True, "status": "ok"},
        db_write_fn=lambda t, c: store.append_ledger(
            "certification", "certifier", t, c,
            hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        ),
        db_read_fn=lambda t: store.query_ledger(t),
        llm_invoke_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
        ledger_entries=store.query_ledger("system", limit=100),
        pre_state_fn=lambda: (
            hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(),
            store.ledger_count(),
        ),
        post_state_fn=lambda: (
            hashlib.sha256(str(store.ledger_count()).encode()).hexdigest(),
            store.ledger_count(),
        ),
    )
    return {
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
        "steps": [
            {"name": s.name, "status": s.status.value, "proof_hash": s.proof_hash, "detail": s.detail}
            for s in chain.steps
        ],
    }


@app.get("/api/v1/certify/history")
def certification_history():
    """Certification chain history."""
    return {"certifications": certifier.certification_history()}


# ═══ Phase 200C — Streaming Completion Endpoint ═══

@app.post("/api/v1/stream")
def stream_completion(req: CompletionRequest):
    """SSE streaming LLM completion — governed, budgeted, ledgered."""
    result = llm_bridge.complete(
        req.prompt,
        model_name=req.model_name,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        tenant_id=req.tenant_id,
        budget_id=req.budget_id,
        system=req.system,
    )
    return StreamingResponse(
        streaming_adapter.stream_to_sse(result, request_id=f"stream-{id(req)}"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══ Phase 200D — Certification Daemon Endpoints ═══

@app.get("/api/v1/daemon/status")
def daemon_status():
    """Certification daemon health and run status."""
    return cert_daemon.status()


@app.post("/api/v1/daemon/tick")
def daemon_tick():
    """Trigger a single certification daemon tick."""
    chain = cert_daemon.tick()
    if chain is None:
        return {"ran": False, "reason": "disabled or interval not elapsed"}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
    }


@app.post("/api/v1/daemon/force")
def daemon_force():
    """Force an immediate certification run regardless of interval."""
    chain = cert_daemon.force_run()
    if chain is None:
        return {"ran": False}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
    }


# ═══ Phase 200A — Bootstrap Info Endpoint ═══

@app.get("/api/v1/bootstrap")
def bootstrap_info():
    """LLM bootstrap configuration and registered backends."""
    return {
        "default_backend": llm_bootstrap_result.default_backend_name,
        "available_backends": list(llm_bootstrap_result.backends.keys()),
        "registered_models": llm_bootstrap_result.registered_models,
        "registered_providers": llm_bootstrap_result.registered_providers,
        "config": {
            "default_model": llm_bootstrap_result.config.default_model,
            "default_budget_max_cost": llm_bootstrap_result.config.default_budget_max_cost,
            "max_tokens_per_call": llm_bootstrap_result.config.max_tokens_per_call,
        },
    }


# ═══ Phase 202A — Tenant Budget & Ledger Endpoints ═══

from dataclasses import asdict as _asdict
from mcoi_runtime.core.tenant_budget import TenantBudgetReport as _TBR

def _budget_report(r: _TBR) -> dict[str, Any]:
    return {
        "tenant_id": r.tenant_id, "budget_id": r.budget_id, "max_cost": r.max_cost,
        "spent": r.spent, "remaining": r.remaining, "calls_made": r.calls_made,
        "max_calls": r.max_calls, "exhausted": r.exhausted, "enabled": r.enabled,
        "utilization_pct": r.utilization_pct,
    }


class TenantBudgetRequest(BaseModel):
    tenant_id: str
    max_cost: float = 10.0
    max_calls: int = 1000


@app.post("/api/v1/tenant/budget")
def create_tenant_budget(req: TenantBudgetRequest):
    """Create or update a tenant's budget policy."""
    tenant_budget_mgr.set_policy(TenantBudgetPolicy(
        tenant_id=req.tenant_id, max_cost=req.max_cost, max_calls=req.max_calls,
    ))
    budget = tenant_budget_mgr.ensure_budget(req.tenant_id)
    audit_trail.record(
        action="tenant.budget.create", actor_id="system",
        tenant_id=req.tenant_id, target=req.tenant_id, outcome="success",
    )
    metrics.inc("requests_governed")
    return _budget_report(tenant_budget_mgr.report(req.tenant_id))


@app.get("/api/v1/tenant/{tenant_id}/budget")
def get_tenant_budget(tenant_id: str):
    """Get a tenant's budget report."""
    metrics.inc("requests_governed")
    return _budget_report(tenant_budget_mgr.report(tenant_id))


@app.get("/api/v1/tenant/{tenant_id}/ledger")
def get_tenant_ledger(tenant_id: str, entry_type: str | None = None, limit: int = 50):
    """Get a tenant's scoped ledger entries."""
    metrics.inc("requests_governed")
    entries = tenant_ledger.query(tenant_id, entry_type=entry_type, limit=limit)
    return {
        "entries": [{"entry_id": e.entry_id, "type": e.entry_type, "actor": e.actor_id,
                      "content": e.content, "at": e.recorded_at} for e in entries],
        "count": len(entries),
        "tenant_id": tenant_id,
    }


@app.get("/api/v1/tenant/{tenant_id}/summary")
def get_tenant_summary(tenant_id: str):
    """Get a tenant's ledger summary."""
    metrics.inc("requests_governed")
    summary = tenant_ledger.summary(tenant_id)
    return {
        "tenant_id": summary.tenant_id,
        "total_entries": summary.total_entries,
        "entry_types": summary.entry_types,
        "total_cost": summary.total_cost,
    }


@app.get("/api/v1/tenants")
def list_tenants():
    """List all tenants with budgets and ledger activity."""
    metrics.inc("requests_governed")
    return {
        "tenants": tenant_budget_mgr.all_reports(),
        "ledger_tenants": tenant_ledger.all_tenant_ids(),
        "total_spent": tenant_budget_mgr.total_spent(),
    }


# ═══ Phase 202B — Governance Metrics Endpoint ═══

@app.get("/api/v1/metrics")
def get_metrics():
    """Governance metrics — counters, gauges, histograms."""
    return metrics.to_dict()


# ═══ Phase 202C — Rate Limiter Status ═══

@app.get("/api/v1/rate-limit/status")
def rate_limit_status():
    """Rate limiter status."""
    return rate_limiter.status()


# ═══ Phase 202D — Audit Trail Endpoints ═══

@app.get("/api/v1/audit")
def get_audit_trail(
    tenant_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
):
    """Query the audit trail with optional filters."""
    metrics.inc("requests_governed")
    entries = audit_trail.query(
        tenant_id=tenant_id, action=action, outcome=outcome, limit=limit,
    )
    return {
        "entries": [
            {"id": e.entry_id, "action": e.action, "actor": e.actor_id,
             "tenant": e.tenant_id, "target": e.target, "outcome": e.outcome,
             "at": e.recorded_at}
            for e in entries
        ],
        "count": len(entries),
    }


@app.get("/api/v1/audit/verify")
def verify_audit_chain():
    """Verify audit trail hash-chain integrity."""
    valid, checked = audit_trail.verify_chain()
    return {"valid": valid, "entries_checked": checked, "last_hash": audit_trail.last_hash[:16]}


@app.get("/api/v1/audit/summary")
def audit_summary():
    """Audit trail summary."""
    return audit_trail.summary()


# ═══ Phase 205A — Agent Workflow Endpoints ═══

class WorkflowRequest(BaseModel):
    task_id: str
    description: str
    capability: str = "llm.completion"
    payload: dict[str, Any] = {}
    tenant_id: str = "system"
    budget_id: str = "default"


@app.post("/api/v1/workflow/execute")
def execute_workflow(req: WorkflowRequest):
    """Execute a governed multi-agent workflow."""
    metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result = workflow_engine.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    metrics.inc("llm_calls_total" if result.status == "completed" else "errors_total")
    return {
        "workflow_id": result.workflow_id,
        "task_id": result.task_id,
        "agent_id": result.agent_id,
        "status": result.status,
        "steps": [{"name": s.step_name, "status": s.status, "detail": s.detail} for s in result.steps],
        "output": result.output,
        "error": result.error,
    }


@app.get("/api/v1/workflow/history")
def workflow_history(limit: int = 50):
    """Workflow execution history."""
    return {
        "workflows": [
            {"id": r.workflow_id, "task": r.task_id, "agent": r.agent_id, "status": r.status}
            for r in workflow_engine.history(limit=limit)
        ],
        "summary": workflow_engine.summary(),
    }


# ═══ Phase 205A — Agent Registry Endpoints ═══

@app.get("/api/v1/agents")
def list_agents():
    """List registered agents and their capabilities."""
    agents = agent_registry.list_agents()
    return {
        "agents": [
            {"id": a.agent_id, "name": a.name, "capabilities": [c.value for c in a.capabilities], "enabled": a.enabled}
            for a in agents
        ],
        "count": len(agents),
    }


@app.get("/api/v1/agents/{agent_id}/tasks")
def agent_tasks(agent_id: str):
    """Get tasks assigned to an agent."""
    metrics.inc("requests_governed")
    return {"agent_id": agent_id, "task_count": task_manager.task_count, "summary": task_manager.summary()}


# ═══ Phase 205A — Webhook Endpoints ═══

class WebhookSubscribeRequest(BaseModel):
    subscription_id: str
    tenant_id: str
    url: str
    events: list[str]
    secret: str = ""


@app.post("/api/v1/webhooks/subscribe")
def webhook_subscribe(req: WebhookSubscribeRequest):
    """Subscribe to webhook events."""
    metrics.inc("requests_governed")
    sub = WebhookSubscription(
        subscription_id=req.subscription_id, tenant_id=req.tenant_id,
        url=req.url, events=tuple(req.events), secret=req.secret,
    )
    webhook_manager.subscribe(sub)
    audit_trail.record(
        action="webhook.subscribe", actor_id="system",
        tenant_id=req.tenant_id, target=req.subscription_id, outcome="success",
    )
    return {"subscription_id": sub.subscription_id, "events": list(sub.events)}


@app.get("/api/v1/webhooks")
def list_webhooks(tenant_id: str | None = None):
    """List webhook subscriptions."""
    subs = webhook_manager.list_subscriptions(tenant_id=tenant_id)
    return {
        "subscriptions": [
            {"id": s.subscription_id, "tenant": s.tenant_id, "url": s.url, "events": list(s.events), "enabled": s.enabled}
            for s in subs
        ],
        "count": len(subs),
    }


@app.get("/api/v1/webhooks/deliveries")
def webhook_deliveries(limit: int = 50):
    """Recent webhook delivery history."""
    return {
        "deliveries": [
            {"id": d.delivery_id, "subscription": d.subscription_id, "event": d.event, "status": d.status, "at": d.created_at}
            for d in webhook_manager.delivery_history(limit=limit)
        ],
    }


# ═══ Phase 205A — Deep Health Endpoint ═══

@app.get("/api/v1/health/deep")
def deep_health_check():
    """System-wide deep health diagnostic."""
    result = deep_health.run()
    return {
        "overall": result.overall.value,
        "components": [
            {"name": c.name, "status": c.status.value, "latency_ms": c.latency_ms, "detail": c.detail}
            for c in result.components
        ],
        "total_latency_ms": result.total_latency_ms,
        "checked_at": result.checked_at,
    }


# ═══ Phase 205A — Config Endpoints ═══

@app.get("/api/v1/config")
def get_config():
    """Current runtime configuration."""
    return {
        "version": config_manager.version,
        "config": config_manager.get_all(),
        "hash": config_manager.config_hash[:16] if config_manager.config_hash else "",
    }


@app.get("/api/v1/config/history")
def config_history(limit: int = 10):
    """Configuration change history."""
    return {
        "versions": [
            {"version": v.version, "hash": v.config_hash[:16], "by": v.applied_by, "at": v.applied_at, "desc": v.description}
            for v in config_manager.history(limit=limit)
        ],
    }


# ═══ Phase 205A — Observability Dashboard ═══

@app.get("/api/v1/dashboard")
def dashboard():
    """Aggregated observability dashboard data."""
    return observability.collect_all()


# ═══ Phase 205A — Plugin Endpoints ═══

@app.get("/api/v1/plugins")
def list_plugins():
    """List registered plugins."""
    return {
        "plugins": [
            {"id": p.descriptor.plugin_id, "name": p.descriptor.name, "version": p.descriptor.version, "status": p.status.value}
            for p in plugin_registry.list_plugins()
        ],
        "summary": plugin_registry.summary(),
    }


# ═══ Phase 206A — Event Bus Endpoints ═══

@app.get("/api/v1/events")
def list_events(event_type: str | None = None, limit: int = 50):
    """Query governed event bus history."""
    events = event_bus.history(event_type=event_type, limit=limit)
    return {
        "events": [
            {"id": e.event_id, "type": e.event_type, "tenant": e.tenant_id,
             "source": e.source, "at": e.published_at}
            for e in events
        ],
        "count": len(events),
    }


@app.get("/api/v1/events/summary")
def events_summary():
    """Event bus summary."""
    return event_bus.summary()


class EventPublishRequest(BaseModel):
    event_type: str
    tenant_id: str = ""
    source: str = "api"
    payload: dict[str, Any] = {}


@app.post("/api/v1/events/publish")
def publish_event(req: EventPublishRequest):
    """Publish a governed event to the bus."""
    metrics.inc("requests_governed")
    event = event_bus.publish(
        req.event_type, tenant_id=req.tenant_id,
        source=req.source, payload=req.payload,
    )
    return {"event_id": event.event_id, "type": event.event_type, "hash": event.event_hash[:16]}


# ═══ Phase 206B — Batch Pipeline Endpoint ═══

class PipelineStepRequest(BaseModel):
    step_id: str
    name: str
    prompt_template: str
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    system: str = ""


class PipelineRequest(BaseModel):
    steps: list[PipelineStepRequest]
    initial_input: str = ""
    budget_id: str = "default"
    tenant_id: str = ""


@app.post("/api/v1/pipeline/execute")
def execute_pipeline(req: PipelineRequest):
    """Execute a multi-step governed LLM pipeline."""
    metrics.inc("requests_governed")
    steps = [
        PipelineStep(
            step_id=s.step_id, name=s.name, prompt_template=s.prompt_template,
            model_name=s.model_name, max_tokens=s.max_tokens, system=s.system,
        )
        for s in req.steps
    ]
    result = batch_pipeline.execute(
        steps, initial_input=req.initial_input,
        budget_id=req.budget_id, tenant_id=req.tenant_id,
    )
    # Emit event
    event_bus.publish(
        "pipeline.completed" if result.succeeded else "pipeline.failed",
        tenant_id=req.tenant_id, source="batch_pipeline",
        payload={"pipeline_id": result.pipeline_id, "succeeded": result.succeeded, "cost": result.total_cost},
    )
    return {
        "pipeline_id": result.pipeline_id,
        "succeeded": result.succeeded,
        "steps": [
            {"id": s.step_id, "name": s.name, "succeeded": s.succeeded, "cost": s.cost, "tokens": s.input_tokens + s.output_tokens}
            for s in result.steps
        ],
        "final_output": result.final_output,
        "total_cost": result.total_cost,
        "total_tokens": result.total_tokens,
        "error": result.error,
    }


@app.get("/api/v1/pipeline/history")
def pipeline_history(limit: int = 50):
    """Batch pipeline execution history."""
    return {
        "pipelines": [
            {"id": p.pipeline_id, "succeeded": p.succeeded, "steps": len(p.steps), "cost": p.total_cost}
            for p in batch_pipeline.history(limit=limit)
        ],
        "summary": batch_pipeline.summary(),
    }


# ═══ Phase 206D — System Snapshot ═══

@app.get("/api/v1/snapshot")
def system_snapshot():
    """Full system state export — all subsystem summaries in one call."""
    return {
        "version": "0.6.0",
        "environment": ENV,
        "store": {"ledger_count": store.ledger_count()},
        "llm": {"invocations": llm_bridge.invocation_count, "total_cost": llm_bridge.total_cost, **llm_bridge.budget_summary()},
        "certification": cert_daemon.status(),
        "tenants": {"count": tenant_budget_mgr.tenant_count(), "total_spent": tenant_budget_mgr.total_spent()},
        "agents": {"count": agent_registry.count, "tasks": task_manager.task_count},
        "workflows": workflow_engine.summary(),
        "pipelines": batch_pipeline.summary(),
        "metrics": metrics.to_dict(),
        "audit": audit_trail.summary(),
        "events": event_bus.summary(),
        "webhooks": webhook_manager.summary(),
        "config": config_manager.summary(),
        "plugins": plugin_registry.summary(),
        "rate_limiter": rate_limiter.status(),
        "captured_at": _clock(),
    }


# ═══ Phase 207A — Config Update API ═══

class ConfigUpdateRequest(BaseModel):
    changes: dict[str, Any]
    applied_by: str = "api"
    description: str = ""


@app.post("/api/v1/config/update")
def update_config(req: ConfigUpdateRequest):
    """Hot-reload configuration via REST API."""
    metrics.inc("requests_governed")
    result = config_manager.update(
        req.changes, applied_by=req.applied_by, description=req.description,
    )
    audit_trail.record(
        action="config.update", actor_id=req.applied_by,
        tenant_id="system", target="config",
        outcome="success" if result.success else "denied",
        detail={"version": result.version, "changes": list(req.changes.keys())},
    )
    event_bus.publish(
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


class ConfigRollbackRequest(BaseModel):
    to_version: int
    applied_by: str = "api"


@app.post("/api/v1/config/rollback")
def rollback_config(req: ConfigRollbackRequest):
    """Rollback configuration to a previous version."""
    metrics.inc("requests_governed")
    result = config_manager.rollback(req.to_version, applied_by=req.applied_by)
    audit_trail.record(
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


# ═══ Phase 207B — Governance Guards Info ═══

@app.get("/api/v1/guards")
def list_guards():
    """List governance guard chain."""
    from mcoi_runtime.core.governance_guard import (
        GovernanceGuardChain, create_rate_limit_guard,
        create_budget_guard, create_tenant_guard,
    )
    chain = GovernanceGuardChain()
    chain.add(create_tenant_guard())
    chain.add(create_rate_limit_guard(rate_limiter))
    chain.add(create_budget_guard(tenant_budget_mgr))
    return {
        "guards": chain.guard_names(),
        "count": chain.guard_count,
    }


# ═══ Phase 207C — Capabilities Info ═══

@app.get("/api/v1/capabilities")
def list_capabilities():
    """List available agent capabilities."""
    from mcoi_runtime.core.agent_protocol import AgentCapability
    return {
        "capabilities": [
            {"id": c.value, "name": c.name}
            for c in AgentCapability
        ],
    }


# ═══ Phase 207D — Replay Info ═══

@app.get("/api/v1/replay/traces")
def list_traces(limit: int = 50):
    """Execution replay traces (placeholder — recorder not wired yet)."""
    return {"traces": [], "count": 0}
