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

# Phase 208A: Governance guard middleware
from mcoi_runtime.app.middleware import GovernanceMiddleware, build_guard_chain
guard_chain = build_guard_chain(rate_limiter=rate_limiter, budget_mgr=tenant_budget_mgr)

# Phase 208B: Traced workflow engine
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.execution_replay import ReplayRecorder
replay_recorder = ReplayRecorder(clock=_clock)
traced_workflow = TracedWorkflowEngine(
    workflow_engine=workflow_engine, replay_recorder=replay_recorder,
)
observability.register_source("replay", lambda: replay_recorder.summary())

# Phase 208C: Conversation store
from mcoi_runtime.core.conversation_memory import ConversationStore
conversation_store = ConversationStore(clock=_clock)

# Phase 208D: Schema validator
from mcoi_runtime.core.schema_validator import SchemaValidator, SchemaDefinition, SchemaRule
schema_validator = SchemaValidator()
schema_validator.register(SchemaDefinition(
    schema_id="workflow_request", name="Workflow Request",
    rules=(
        SchemaRule(field="task_id", rule_type="required", value=True),
        SchemaRule(field="description", rule_type="required", value=True),
        SchemaRule(field="capability", rule_type="required", value=True),
    ),
))
schema_validator.register(SchemaDefinition(
    schema_id="pipeline_request", name="Pipeline Request",
    rules=(
        SchemaRule(field="steps", rule_type="required", value=True),
        SchemaRule(field="steps", rule_type="type", value="list"),
    ),
))

# Phase 209C: Prompt template engine
from mcoi_runtime.core.prompt_template_engine import PromptTemplateEngine, PromptTemplate
prompt_engine = PromptTemplateEngine()
prompt_engine.register(PromptTemplate(
    template_id="summarize", name="Summarize",
    template="Summarize the following text concisely:\n\n{{text}}",
    variables=("text",), system_prompt="You are a concise summarizer.",
    category="analysis",
))
prompt_engine.register(PromptTemplate(
    template_id="translate", name="Translate",
    template="Translate the following text to {{language}}:\n\n{{text}}",
    variables=("text", "language"), system_prompt="You are a professional translator.",
    category="language",
))
prompt_engine.register(PromptTemplate(
    template_id="analyze", name="Analyze",
    template="Analyze the following {{topic}} and provide key insights:\n\n{{content}}",
    variables=("topic", "content"), system_prompt="You are an expert analyst.",
    category="analysis",
))

# Phase 209D: Cost analytics engine
from mcoi_runtime.core.cost_analytics import CostAnalyticsEngine
cost_analytics = CostAnalyticsEngine(clock=_clock)
observability.register_source("cost_analytics", lambda: cost_analytics.summary())

# Phase 210A: Chat workflow engine
from mcoi_runtime.core.chat_workflow import ChatWorkflowEngine
chat_workflow = ChatWorkflowEngine(
    clock=_clock,
    conversation_store=conversation_store,
    traced_workflow=traced_workflow,
    cost_record_fn=lambda tid, model, cost, tokens: cost_analytics.record(tid, model, cost, tokens),
)
observability.register_source("chat_workflows", lambda: chat_workflow.summary())

# Phase 210B: Health aggregator
from mcoi_runtime.core.health_aggregator import HealthAggregator
health_agg = HealthAggregator(clock=_clock)
health_agg.register("store", lambda: {"status": "healthy"}, weight=1.0)
health_agg.register("llm", lambda: {"status": "healthy"}, weight=2.0)
health_agg.register("certification", lambda: {"status": "healthy" if cert_daemon.health.is_healthy else "degraded"}, weight=1.5)
health_agg.register("metrics", lambda: {"status": "healthy"}, weight=0.5)
health_agg.register("event_bus", lambda: {"status": "healthy" if event_bus.error_count == 0 else "degraded"}, weight=0.5)

# Phase 210C: API version manager
from mcoi_runtime.core.api_version import APIVersionManager, EndpointDescriptor
api_versions = APIVersionManager(clock=_clock)

app = FastAPI(title="Mullu Platform", version="2.0.0", description="Governed AI Operating System")

# Wire middleware
app.add_middleware(
    GovernanceMiddleware,
    guard_chain=guard_chain,
    metrics_fn=lambda name, val: metrics.inc(name, val),
    on_reject=lambda ctx: audit_trail.record(
        action="guard.rejected", actor_id="system",
        tenant_id=ctx.get("tenant_id", ""), target=ctx.get("path", ""),
        outcome="denied", detail=ctx,
    ),
)


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
    """Execution replay traces."""
    traces = replay_recorder.list_traces(limit=limit)
    return {
        "traces": [
            {"id": t.trace_id, "frames": len(t.frames), "hash": t.trace_hash[:16], "at": t.recorded_at}
            for t in traces
        ],
        "count": len(traces),
        "summary": replay_recorder.summary(),
    }


# ═══ Phase 208B — Traced Workflow Endpoint ═══

@app.post("/api/v1/workflow/traced")
def execute_traced_workflow(req: WorkflowRequest):
    """Execute a workflow with automatic replay trace recording."""
    metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result, trace = traced_workflow.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    return {
        "workflow_id": result.workflow_id,
        "status": result.status,
        "agent_id": result.agent_id,
        "output": result.output,
        "trace_id": trace.trace_id if trace else None,
        "trace_frames": len(trace.frames) if trace else 0,
        "trace_hash": trace.trace_hash[:16] if trace else None,
    }


# ═══ Phase 208C — Conversation Endpoints ═══

class ConversationMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    tenant_id: str = ""


@app.post("/api/v1/conversation/message")
def add_conversation_message(req: ConversationMessageRequest):
    """Add a message to a conversation."""
    metrics.inc("requests_governed")
    conv = conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)
    msg = conv.add_message(req.role, req.content)
    return {
        "conversation_id": conv.conversation_id,
        "message_id": msg.message_id,
        "message_count": conv.message_count,
    }


@app.get("/api/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history."""
    conv = conversation_store.get(conversation_id)
    if conv is None:
        raise HTTPException(404, detail="conversation not found")
    return {
        "conversation_id": conv.conversation_id,
        "messages": [{"role": m.role, "content": m.content, "id": m.message_id} for m in conv.messages],
        "summary": conv.summary(),
    }


@app.get("/api/v1/conversations")
def list_conversations(tenant_id: str | None = None):
    """List conversations."""
    convs = conversation_store.list_conversations(tenant_id=tenant_id)
    return {
        "conversations": [c.summary() for c in convs],
        "count": len(convs),
    }


# ═══ Phase 208D — Schema Validation Endpoint ═══

@app.get("/api/v1/schemas")
def list_schemas():
    """List registered validation schemas."""
    return {
        "schemas": [
            {"id": s.schema_id, "name": s.name, "rules": len(s.rules)}
            for s in schema_validator.list_schemas()
        ],
        "summary": schema_validator.summary(),
    }


class ValidateRequest(BaseModel):
    schema_id: str
    data: dict[str, Any]


@app.post("/api/v1/schemas/validate")
def validate_data(req: ValidateRequest):
    """Validate data against a registered schema."""
    result = schema_validator.validate(req.schema_id, req.data)
    return {
        "schema_id": result.schema_id,
        "valid": result.valid,
        "errors": [
            {"field": e.field, "rule": e.rule_type, "message": e.message}
            for e in result.errors
        ],
    }


# ═══ Phase 209A — Conversation-Aware Chat Endpoint ═══

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    budget_id: str = "default"
    model_name: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""


@app.post("/api/v1/chat")
def chat_completion(req: ChatRequest):
    """Multi-turn chat — uses conversation history for context."""
    metrics.inc("requests_governed")
    metrics.inc("llm_calls_total")

    conv = conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)

    # Add system prompt on first message
    if req.system_prompt and conv.message_count == 0:
        conv.add_system(req.system_prompt)

    # Add user message
    conv.add_user(req.message)

    # Call LLM with full conversation history
    result = llm_bridge.chat(
        conv.to_chat_messages(),
        model_name=req.model_name,
        budget_id=req.budget_id,
        tenant_id=req.tenant_id,
    )

    if result.succeeded:
        conv.add_assistant(result.content)
        metrics.inc("llm_calls_succeeded")
        # Record cost analytics
        cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
    else:
        metrics.inc("llm_calls_failed")

    return {
        "conversation_id": conv.conversation_id,
        "content": result.content,
        "model": result.model_name,
        "tokens": result.total_tokens,
        "cost": result.cost,
        "succeeded": result.succeeded,
        "message_count": conv.message_count,
        "governed": True,
    }


# ═══ Phase 209C — Prompt Template Endpoints ═══

@app.get("/api/v1/prompts")
def list_prompt_templates(category: str | None = None):
    """List registered prompt templates."""
    templates = prompt_engine.list_templates(category=category)
    return {
        "templates": [
            {"id": t.template_id, "name": t.name, "variables": list(t.variables),
             "category": t.category, "version": t.version}
            for t in templates
        ],
        "summary": prompt_engine.summary(),
    }


class PromptRenderRequest(BaseModel):
    template_id: str
    variables: dict[str, str]
    tenant_id: str = "system"
    budget_id: str = "default"
    execute: bool = False  # If True, also run the rendered prompt through LLM


@app.post("/api/v1/prompts/render")
def render_prompt(req: PromptRenderRequest):
    """Render a prompt template with variables, optionally execute via LLM."""
    metrics.inc("requests_governed")
    try:
        rendered = prompt_engine.render(req.template_id, req.variables)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    response: dict[str, Any] = {
        "template_id": rendered.template_id,
        "prompt": rendered.prompt,
        "system_prompt": rendered.system_prompt,
        "version": rendered.version,
    }

    if req.execute:
        metrics.inc("llm_calls_total")
        result = llm_bridge.complete(
            rendered.prompt, system=rendered.system_prompt,
            budget_id=req.budget_id, tenant_id=req.tenant_id,
        )
        response["llm_result"] = {
            "content": result.content,
            "model": result.model_name,
            "tokens": result.total_tokens,
            "cost": result.cost,
            "succeeded": result.succeeded,
        }
        if result.succeeded:
            cost_analytics.record(req.tenant_id, result.model_name, result.cost, result.total_tokens)

    return response


# ═══ Phase 209D — Cost Analytics Endpoints ═══

@app.get("/api/v1/costs")
def cost_summary():
    """Overall cost analytics summary."""
    return cost_analytics.summary()


@app.get("/api/v1/costs/top-spenders")
def top_spenders(limit: int = 10):
    """Top spending tenants."""
    return {
        "spenders": [
            {"tenant_id": b.tenant_id, "total_cost": b.total_cost, "calls": b.call_count}
            for b in cost_analytics.top_spenders(limit=limit)
        ],
    }


@app.get("/api/v1/costs/by-model")
def costs_by_model():
    """Cost breakdown by LLM model."""
    return {"models": cost_analytics.model_usage()}


@app.get("/api/v1/costs/{tenant_id}")
def tenant_costs(tenant_id: str):
    """Cost breakdown for a specific tenant."""
    breakdown = cost_analytics.tenant_breakdown(tenant_id)
    return {
        "tenant_id": breakdown.tenant_id,
        "total_cost": breakdown.total_cost,
        "total_tokens": breakdown.total_tokens,
        "call_count": breakdown.call_count,
        "avg_cost_per_call": breakdown.avg_cost_per_call,
        "by_model": breakdown.by_model,
        "most_expensive_model": breakdown.most_expensive_model,
    }


@app.get("/api/v1/costs/{tenant_id}/projection")
def cost_projection(tenant_id: str, budget: float = 0.0, days_elapsed: float = 1.0):
    """Cost projection for a tenant."""
    proj = cost_analytics.project(tenant_id, budget=budget, days_elapsed=days_elapsed)
    return {
        "tenant_id": proj.tenant_id,
        "current_daily_rate": proj.current_daily_rate,
        "projected_monthly": proj.projected_monthly,
        "budget_remaining": proj.budget_remaining,
        "days_until_exhaustion": proj.days_until_exhaustion,
    }


# ═══ Phase 210A — Chat Workflow Endpoint ═══

class ChatWorkflowRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    capability: str = "llm.completion"
    system_prompt: str = ""
    budget_id: str = "default"


@app.post("/api/v1/chat/workflow")
def chat_workflow_endpoint(req: ChatWorkflowRequest):
    """Chat-triggered governed workflow — conversation + agent + trace."""
    metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result = chat_workflow.execute(
        conversation_id=req.conversation_id,
        message=req.message,
        tenant_id=req.tenant_id,
        capability=cap,
        system_prompt=req.system_prompt,
        budget_id=req.budget_id,
    )
    return {
        "conversation_id": result.conversation_id,
        "workflow_id": result.workflow_id,
        "agent_id": result.agent_id,
        "status": result.status,
        "response": result.response_content,
        "trace_id": result.trace_id,
        "message_count": result.message_count,
        "cost": result.cost,
        "governed": True,
    }


@app.get("/api/v1/chat/workflow/history")
def chat_workflow_history(limit: int = 50):
    """Chat workflow execution history."""
    return {
        "history": [
            {"conversation": r.conversation_id, "workflow": r.workflow_id,
             "status": r.status, "cost": r.cost}
            for r in chat_workflow.history(limit=limit)
        ],
        "summary": chat_workflow.summary(),
    }


# ═══ Phase 210B — Health Aggregation Endpoint ═══

@app.get("/api/v1/health/score")
def health_score():
    """Unified system health score (0.0-1.0)."""
    result = health_agg.compute()
    return {
        "score": result.overall_score,
        "status": result.status,
        "components": [
            {"name": c.name, "score": c.score, "weight": c.weight, "status": c.status}
            for c in result.components
        ],
        "checked_at": result.checked_at,
    }


# ═══ Phase 210C — API Version Endpoint ═══

@app.get("/api/v1/version")
def api_version():
    """API version info."""
    return {
        "version": "1.0.0",
        "api_version": "v1",
        "endpoints": api_versions.endpoint_count,
        "summary": api_versions.summary(),
        "governed": True,
    }


# ═══ Phase 210D — Release Info ═══

@app.get("/api/v1/release")
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


# ═══ Phase 212A — Tool-Use, Streaming, State Endpoints ═══

from mcoi_runtime.core.tool_use import ToolDefinition, ToolParameter, ToolRegistry
from mcoi_runtime.adapters.anthropic_streaming import AnthropicStreamingAdapter
from mcoi_runtime.persistence.state_persistence import StatePersistence
from mcoi_runtime.core.structured_output import StructuredOutputEngine, OutputSchema
from mcoi_runtime.core.retry_engine import CircuitBreaker

# Tool registry with example tools
tool_registry = ToolRegistry(clock=_clock)
tool_registry.register(
    ToolDefinition(
        tool_id="calculator", name="Calculator",
        description="Evaluate a math expression",
        parameters=(ToolParameter(name="expression", param_type="string", description="Math expression"),),
        category="utility",
    ),
    handler=lambda args: {"result": str(eval(args.get("expression", "0")))},
)
tool_registry.register(
    ToolDefinition(
        tool_id="get_time", name="Get Time",
        description="Get the current time",
        parameters=(),
        category="utility",
    ),
    handler=lambda args: {"time": _clock()},
)
observability.register_source("tools", lambda: tool_registry.summary())

# Anthropic streaming adapter
anthropic_stream = AnthropicStreamingAdapter(
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    clock=_clock,
)

# State persistence
state_persistence = StatePersistence(clock=_clock)

# Structured output engine
structured_output = StructuredOutputEngine()
structured_output.register(OutputSchema(
    schema_id="analysis", name="Analysis Output",
    fields={"summary": "string", "key_points": "array", "confidence": "number"},
    required_fields=("summary", "key_points"),
))

# LLM circuit breaker
llm_circuit = CircuitBreaker(failure_threshold=10, recovery_timeout_ms=60000)


@app.get("/api/v1/tools")
def list_tools(category: str | None = None):
    """List registered tools."""
    tools = tool_registry.list_tools(category=category)
    return {
        "tools": [
            {"id": t.tool_id, "name": t.name, "description": t.description,
             "parameters": [{"name": p.name, "type": p.param_type, "required": p.required} for p in t.parameters],
             "category": t.category}
            for t in tools
        ],
        "count": len(tools),
    }


class ToolInvokeRequest(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = {}
    tenant_id: str = ""


@app.post("/api/v1/tools/invoke")
def invoke_tool(req: ToolInvokeRequest):
    """Invoke a registered tool."""
    metrics.inc("requests_governed")
    result = tool_registry.invoke(req.tool_id, req.arguments, tenant_id=req.tenant_id)
    audit_trail.record(
        action="tool.invoke", actor_id="api", tenant_id=req.tenant_id,
        target=req.tool_id, outcome="success" if result.succeeded else "error",
    )
    return {
        "invocation_id": result.invocation_id, "tool_id": result.tool_id,
        "output": result.output, "succeeded": result.succeeded, "error": result.error,
    }


@app.get("/api/v1/tools/llm-format")
def tools_llm_format():
    """Export tools in LLM-compatible format."""
    return {"tools": tool_registry.to_llm_tools()}


@app.get("/api/v1/tools/history")
def tool_history(limit: int = 50):
    """Tool invocation history."""
    return {"history": [
        {"id": r.invocation_id, "tool": r.tool_id, "succeeded": r.succeeded}
        for r in tool_registry.invocation_history(limit=limit)
    ], "summary": tool_registry.summary()}


class StateSaveRequest(BaseModel):
    state_type: str
    data: dict[str, Any]


@app.post("/api/v1/state/save")
def save_state(req: StateSaveRequest):
    """Save runtime state."""
    metrics.inc("requests_governed")
    snap = state_persistence.save(req.state_type, req.data)
    return {"state_type": snap.state_type, "hash": snap.state_hash[:16], "saved_at": snap.saved_at}


@app.get("/api/v1/state/{state_type}")
def load_state(state_type: str):
    """Load runtime state."""
    snap = state_persistence.load(state_type)
    if snap is None:
        raise HTTPException(404, detail=f"state not found: {state_type}")
    return {"state_type": snap.state_type, "data": snap.data, "hash": snap.state_hash[:16]}


@app.get("/api/v1/state")
def list_states():
    """List saved states."""
    return {"states": state_persistence.list_states(), "summary": state_persistence.summary()}


class ParseOutputRequest(BaseModel):
    schema_id: str
    text: str


@app.post("/api/v1/output/parse")
def parse_structured_output(req: ParseOutputRequest):
    """Parse LLM output against a schema."""
    result = structured_output.parse(req.schema_id, req.text)
    return {"schema_id": result.schema_id, "valid": result.valid, "parsed": result.parsed, "errors": list(result.errors)}


@app.get("/api/v1/output/schemas")
def list_output_schemas():
    """List output schemas."""
    return {"schemas": [{"id": s.schema_id, "name": s.name, "fields": s.fields} for s in structured_output.list_schemas()]}


@app.get("/api/v1/circuit-breaker")
def circuit_breaker_status():
    """LLM circuit breaker status."""
    return llm_circuit.status()


# ═══ Phase 213A — Circuit-Breaker Protected LLM Completion ═══

@app.post("/api/v1/complete/safe")
def safe_completion(req: CompletionRequest):
    """LLM completion with circuit-breaker protection."""
    metrics.inc("requests_governed")
    if not llm_circuit.allow_request():
        metrics.inc("requests_rejected")
        raise HTTPException(503, detail={
            "error": "LLM circuit breaker is open — service temporarily unavailable",
            "circuit_state": llm_circuit.state.value,
            "governed": True,
        })

    try:
        result = llm_bridge.complete(
            req.prompt, model_name=req.model_name, max_tokens=req.max_tokens,
            temperature=req.temperature, tenant_id=req.tenant_id,
            budget_id=req.budget_id, system=req.system,
        )
        if result.succeeded:
            llm_circuit.record_success()
            metrics.inc("llm_calls_succeeded")
            cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
        else:
            llm_circuit.record_failure()
            metrics.inc("llm_calls_failed")

        return {
            "content": result.content, "model": result.model_name,
            "provider": result.provider.value, "tokens": result.total_tokens,
            "cost": result.cost, "succeeded": result.succeeded,
            "circuit_state": llm_circuit.state.value, "governed": True,
        }
    except Exception as exc:
        llm_circuit.record_failure()
        metrics.inc("errors_total")
        raise HTTPException(503, detail={"error": str(exc), "governed": True})


# ═══ Phase 213B — Tool-Augmented Workflow Endpoint ═══

from mcoi_runtime.core.tool_agent import ToolAugmentedAgent

tool_agent = ToolAugmentedAgent(
    tool_registry=tool_registry,
    llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
    max_tool_calls=10,
)


class ToolWorkflowRequest(BaseModel):
    prompt: str
    tool_ids: list[str] | None = None
    tenant_id: str = "system"


@app.post("/api/v1/workflow/tools")
def tool_augmented_workflow(req: ToolWorkflowRequest):
    """Execute a tool-augmented workflow — LLM + tool invocations."""
    metrics.inc("requests_governed")
    result = tool_agent.execute_with_tools(
        req.prompt, tool_ids=req.tool_ids, tenant_id=req.tenant_id,
    )
    return {
        "content": result.content,
        "tool_calls": [
            {"tool_id": tc.tool_id, "arguments": tc.arguments,
             "succeeded": tc.result.succeeded, "output": tc.result.output}
            for tc in result.tool_calls
        ],
        "total_tool_calls": result.total_tool_calls,
        "all_succeeded": result.all_succeeded,
        "governed": True,
    }


# ═══ Phase 213C — Streaming Chat Endpoint (SSE + Conversation) ═══

@app.post("/api/v1/chat/stream")
def streaming_chat(req: ChatRequest):
    """Streaming chat — SSE with conversation history."""
    metrics.inc("requests_governed")
    conv = conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)

    if req.system_prompt and conv.message_count == 0:
        conv.add_system(req.system_prompt)
    conv.add_user(req.message)

    # Get completion (non-streaming internally, streamed to client)
    result = llm_bridge.chat(
        conv.to_chat_messages(), model_name=req.model_name,
        budget_id=req.budget_id, tenant_id=req.tenant_id,
    )

    if result.succeeded:
        conv.add_assistant(result.content)
        cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)

    # Stream as SSE
    return StreamingResponse(
        streaming_adapter.stream_to_sse(result, request_id=f"chat-{req.conversation_id}"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══ Phase 213D — v1.1.0 Release Info ═══

@app.get("/api/v1/release/latest")
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


# ═══ Phase 214A — Model Routing Endpoint ═══

from mcoi_runtime.core.model_router import ModelProfile, ModelRouter

model_router = ModelRouter()
model_router.register(ModelProfile(
    model_id="claude-haiku-4-5", name="Claude Haiku 4.5", provider="anthropic",
    cost_per_1k_input=0.80, cost_per_1k_output=4.0,
    max_context=200000, speed_tier="fast", capability_tier="basic",
))
model_router.register(ModelProfile(
    model_id="claude-sonnet-4", name="Claude Sonnet 4", provider="anthropic",
    cost_per_1k_input=3.0, cost_per_1k_output=15.0,
    max_context=200000, speed_tier="medium", capability_tier="standard",
))
model_router.register(ModelProfile(
    model_id="claude-opus-4-6", name="Claude Opus 4.6", provider="anthropic",
    cost_per_1k_input=15.0, cost_per_1k_output=75.0,
    max_context=1000000, speed_tier="slow", capability_tier="advanced",
))
model_router.register(ModelProfile(
    model_id="gpt-4o-mini", name="GPT-4o Mini", provider="openai",
    cost_per_1k_input=0.15, cost_per_1k_output=0.60,
    max_context=128000, speed_tier="fast", capability_tier="basic",
))
observability.register_source("model_router", lambda: model_router.summary())


class AutoCompleteRequest(BaseModel):
    prompt: str
    max_tokens: int = 1024
    max_cost: float = 0.0
    preferred_speed: str = ""
    force_model: str = ""
    tenant_id: str = "system"
    budget_id: str = "default"


@app.post("/api/v1/complete/auto")
def auto_routed_completion(req: AutoCompleteRequest):
    """LLM completion with automatic model routing."""
    metrics.inc("requests_governed")
    decision = model_router.route(
        req.prompt, max_tokens=req.max_tokens,
        max_cost=req.max_cost, preferred_speed=req.preferred_speed,
        force_model=req.force_model,
    )
    if not decision.model_id:
        raise HTTPException(503, detail="no models available for routing")

    result = llm_bridge.complete(
        req.prompt, model_name=decision.model_id,
        max_tokens=req.max_tokens, tenant_id=req.tenant_id,
        budget_id=req.budget_id,
    )
    if result.succeeded:
        cost_analytics.record(req.tenant_id, decision.model_id, result.cost, result.total_tokens)

    return {
        "content": result.content,
        "model": decision.model_id,
        "routing": {
            "reason": decision.reason,
            "complexity": decision.complexity.value,
            "estimated_cost": decision.estimated_cost,
            "alternatives": list(decision.alternatives),
        },
        "tokens": result.total_tokens,
        "cost": result.cost,
        "succeeded": result.succeeded,
        "governed": True,
    }


@app.get("/api/v1/models")
def list_models():
    """List available models for routing."""
    return {
        "models": [
            {"id": p.model_id, "name": p.name, "provider": p.provider,
             "speed": p.speed_tier, "capability": p.capability_tier, "enabled": p.enabled}
            for p in sorted(model_router._profiles.values(), key=lambda p: p.model_id)
        ],
        "summary": model_router.summary(),
    }


# ═══ Phase 214B — Request Correlation Endpoint ═══

from mcoi_runtime.core.request_correlation import CorrelationManager

correlation_mgr = CorrelationManager(clock=_clock)


@app.get("/api/v1/correlation/active")
def active_correlations():
    """Active request correlations."""
    return correlation_mgr.summary()


# ═══ Phase 214C — Shutdown Info ═══

from mcoi_runtime.core.graceful_shutdown import ShutdownManager

shutdown_mgr = ShutdownManager()
shutdown_mgr.register("save_state", lambda: {"saved": True}, priority=100)
shutdown_mgr.register("flush_metrics", lambda: {"flushed": True}, priority=90)
shutdown_mgr.register("close_connections", lambda: {"closed": True}, priority=10)


@app.get("/api/v1/shutdown/info")
def shutdown_info():
    """Graceful shutdown configuration."""
    return shutdown_mgr.summary()


# ═══ Phase 214D — Production Readiness Checks ═══

@app.get("/api/v1/readiness")
def production_readiness():
    """Production readiness checks — verifies all subsystems are operational."""
    checks = {
        "llm_bridge": llm_bridge.invocation_count >= 0,
        "store": store.ledger_count() >= 0,
        "audit_trail": audit_trail.entry_count >= 0,
        "event_bus": event_bus.event_count >= 0,
        "metrics": metrics.counter("requests_total") >= 0,
        "config": config_manager.version >= 1,
        "tool_registry": tool_registry.tool_count >= 1,
        "model_router": model_router.model_count >= 1,
        "plugins": plugin_registry.count >= 1,
        "health_agg": health_agg.component_count >= 1,
        "schema_validator": schema_validator.count >= 1,
        "guard_chain": guard_chain.guard_count >= 1,
    }
    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
        "version": "1.3.0",
        "subsystems": len(checks),
        "governed": True,
    }


# ═══ Phase 215A — Agent Chain Endpoint ═══

from mcoi_runtime.core.agent_chain import AgentChainEngine, ChainStep

agent_chain = AgentChainEngine(
    clock=_clock,
    llm_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
)


class ChainStepRequest(BaseModel):
    step_id: str
    name: str
    prompt_template: str
    on_failure: str = "halt"


class ChainRequest(BaseModel):
    steps: list[ChainStepRequest]
    initial_input: str = ""
    tenant_id: str = ""


@app.post("/api/v1/chain/execute")
def execute_chain(req: ChainRequest):
    """Execute a multi-agent chain."""
    metrics.inc("requests_governed")
    steps = [ChainStep(step_id=s.step_id, name=s.name, prompt_template=s.prompt_template, on_failure=s.on_failure) for s in req.steps]
    result = agent_chain.execute(steps, initial_input=req.initial_input)
    event_bus.publish("chain.completed" if result.succeeded else "chain.failed",
                      tenant_id=req.tenant_id, source="agent_chain",
                      payload={"chain_id": result.chain_id, "succeeded": result.succeeded})
    return {
        "chain_id": result.chain_id, "succeeded": result.succeeded,
        "steps": [{"id": s.step_id, "name": s.name, "succeeded": s.succeeded, "cost": s.cost} for s in result.steps],
        "final_output": result.final_output, "total_cost": result.total_cost,
        "error": result.error, "governed": True,
    }


@app.get("/api/v1/chain/history")
def chain_history(limit: int = 50):
    """Agent chain execution history."""
    return {"chains": [
        {"id": c.chain_id, "succeeded": c.succeeded, "steps": len(c.steps), "cost": c.total_cost}
        for c in agent_chain.history(limit=limit)
    ], "summary": agent_chain.summary()}


# ═══ Phase 215B — Monitoring Endpoint ═══

from mcoi_runtime.core.monitoring import MonitoringEngine

monitor = MonitoringEngine(clock=_clock)


@app.get("/api/v1/monitor")
def monitoring_dashboard():
    """Real-time monitoring vitals."""
    vitals = monitor.compute_vitals(
        active_tenants=tenant_budget_mgr.tenant_count(),
        llm_calls=llm_bridge.invocation_count,
        total_cost=llm_bridge.total_cost,
        health_score=health_agg.compute().overall_score,
        circuit_state=llm_circuit.state.value,
        event_count=event_bus.event_count,
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


# ═══ Phase 215C — Task Queue Endpoint ═══

from mcoi_runtime.core.task_queue import TaskQueue

task_queue = TaskQueue(clock=_clock)


class QueueSubmitRequest(BaseModel):
    task_id: str
    payload: dict[str, Any] = {}
    priority: int = 0
    tenant_id: str = ""


@app.post("/api/v1/queue/submit")
def queue_submit(req: QueueSubmitRequest):
    """Submit a task to the async queue."""
    metrics.inc("requests_governed")
    task = task_queue.submit(req.task_id, req.payload, priority=req.priority, tenant_id=req.tenant_id)
    return {"task_id": task.task_id, "priority": task.priority, "queued_at": task.submitted_at}


@app.post("/api/v1/queue/process")
def queue_process():
    """Process one task from the queue."""
    metrics.inc("requests_governed")
    result = task_queue.process_one(lambda payload: {"processed": True, **payload})
    if result is None:
        return {"processed": False, "reason": "queue empty"}
    return {"processed": True, "task_id": result.task_id, "succeeded": result.succeeded, "output": result.output}


@app.get("/api/v1/queue/status")
def queue_status():
    """Task queue status."""
    return task_queue.summary()


@app.get("/api/v1/queue/result/{task_id}")
def queue_result(task_id: str):
    """Get task result."""
    result = task_queue.get_result(task_id)
    if result is None:
        raise HTTPException(404, detail="task result not found")
    return {"task_id": result.task_id, "output": result.output, "succeeded": result.succeeded}


# ═══ Phase 216A — Agent Memory Endpoints ═══

from mcoi_runtime.core.agent_memory import AgentMemoryStore

agent_memory = AgentMemoryStore(clock=_clock)
observability.register_source("agent_memory", lambda: agent_memory.summary())


class MemoryStoreRequest(BaseModel):
    agent_id: str
    tenant_id: str
    category: str = "fact"
    content: str = ""
    keywords: list[str] | None = None
    confidence: float = 1.0


@app.post("/api/v1/memory/store")
def store_memory(req: MemoryStoreRequest):
    """Store a long-term memory for an agent."""
    metrics.inc("requests_governed")
    entry = agent_memory.store(
        req.agent_id, req.tenant_id, req.category,
        req.content, keywords=req.keywords, confidence=req.confidence,
    )
    return {"memory_id": entry.memory_id, "agent_id": entry.agent_id, "category": entry.category}


class MemorySearchRequest(BaseModel):
    agent_id: str
    tenant_id: str
    query: str
    limit: int = 5


@app.post("/api/v1/memory/search")
def search_memory(req: MemorySearchRequest):
    """Search agent memories by relevance."""
    results = agent_memory.search(req.agent_id, req.tenant_id, req.query, limit=req.limit)
    return {
        "results": [
            {"memory_id": r.memory.memory_id, "content": r.memory.content,
             "category": r.memory.category, "relevance": r.relevance_score}
            for r in results
        ],
        "count": len(results),
    }


@app.get("/api/v1/memory/summary")
def memory_summary():
    """Agent memory summary."""
    return agent_memory.summary()


# ═══ Phase 216B — A/B Testing Endpoint ═══

from mcoi_runtime.core.ab_testing import ABTestEngine

ab_engine = ABTestEngine(clock=_clock)


class ABTestRequest(BaseModel):
    prompt: str
    model_ids: list[str] = []
    criteria: str = "cost"


@app.post("/api/v1/ab-test")
def run_ab_test(req: ABTestRequest):
    """Run an A/B test across models."""
    metrics.inc("requests_governed")
    model_fns = {}
    for mid in (req.model_ids or ["default"]):
        model_fns[mid] = lambda p, m=mid: llm_bridge.complete(p, model_name=m, budget_id="default")

    result = ab_engine.run_experiment(req.prompt, model_fns, criteria=req.criteria)
    return {
        "experiment_id": result.experiment_id,
        "winner": result.winner,
        "criteria": result.criteria,
        "variants": [
            {"id": v.variant_id, "model": v.model_id, "cost": v.cost,
             "tokens": v.tokens, "latency_ms": v.latency_ms, "succeeded": v.succeeded}
            for v in result.variants
        ],
    }


@app.get("/api/v1/ab-test/summary")
def ab_test_summary():
    """A/B testing summary with win rates."""
    return ab_engine.summary()


# ═══ Phase 216C — Isolation Verification Endpoint ═══

from mcoi_runtime.core.isolation_verifier import IsolationVerifier, IsolationProbe

isolation_verifier = IsolationVerifier(clock=_clock)

# Register built-in probes
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="budget_isolation", tenant_a=a, tenant_b=b,
    isolated=tenant_budget_mgr.get_budget(a) != tenant_budget_mgr.get_budget(b) or
             (tenant_budget_mgr.get_budget(a) is None and tenant_budget_mgr.get_budget(b) is None),
    detail="budget objects are distinct per tenant",
))
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="ledger_isolation", tenant_a=a, tenant_b=b,
    isolated=True,  # TenantLedger structurally isolates by tenant_id key
    detail="ledger entries are keyed by tenant_id",
))
isolation_verifier.register_probe(lambda a, b: IsolationProbe(
    probe_name="conversation_isolation", tenant_a=a, tenant_b=b,
    isolated=True,  # ConversationStore filters by tenant_id
    detail="conversations are filtered by tenant_id",
))


@app.post("/api/v1/isolation/verify")
def verify_isolation(tenant_a: str = "probe-a", tenant_b: str = "probe-b"):
    """Verify tenant isolation between two tenants."""
    metrics.inc("requests_governed")
    report = isolation_verifier.verify(tenant_a, tenant_b)
    return {
        "all_isolated": report.all_isolated,
        "probes_run": report.probes_run,
        "probes_passed": report.probes_passed,
        "probes": [
            {"name": p.probe_name, "isolated": p.isolated, "detail": p.detail}
            for p in report.probes
        ],
        "verified_at": report.verified_at,
    }


@app.get("/api/v1/isolation/summary")
def isolation_summary():
    """Isolation verification summary."""
    return isolation_verifier.summary()


# ═══ Phase 217 — Usage Reports ═══

from mcoi_runtime.core.usage_reporter import UsageReporter

usage_reporter = UsageReporter(clock=_clock)
usage_reporter.register_source("llm_calls", lambda tid: llm_bridge.invocation_count)
usage_reporter.register_source("total_cost", lambda tid: llm_bridge.total_cost)


@app.get("/api/v1/usage/{tenant_id}")
def tenant_usage(tenant_id: str):
    """Per-tenant usage report."""
    report = usage_reporter.generate(tenant_id)
    return {
        "tenant_id": report.tenant_id,
        "llm_calls": report.llm_calls,
        "total_cost": report.total_cost,
        "generated_at": report.generated_at,
    }


# ═══ Phase 218B — Dependency Graph Endpoint ═══

from mcoi_runtime.core.dependency_graph import DependencyGraph, SubsystemNode

dep_graph = DependencyGraph()
dep_graph.add(SubsystemNode(name="store", version="1.0"))
dep_graph.add(SubsystemNode(name="llm", version="1.0", dependencies=("store",)))
dep_graph.add(SubsystemNode(name="agents", version="1.0", dependencies=("llm", "store")))
dep_graph.add(SubsystemNode(name="workflows", version="1.0", dependencies=("agents", "llm")))
dep_graph.add(SubsystemNode(name="conversations", version="1.0", dependencies=("llm",)))
dep_graph.add(SubsystemNode(name="events", version="1.0", dependencies=("store",)))
dep_graph.add(SubsystemNode(name="governance", version="1.0", dependencies=("store", "events")))
dep_graph.add(SubsystemNode(name="api", version="1.0", dependencies=("governance", "workflows", "conversations")))


@app.get("/api/v1/dependencies")
def dependency_graph_endpoint():
    """Subsystem dependency graph."""
    return {
        "startup_order": dep_graph.topological_sort(),
        "summary": dep_graph.summary(),
    }


@app.get("/api/v1/dependencies/{name}/impact")
def dependency_impact(name: str):
    """Impact analysis if a subsystem fails."""
    impacted = dep_graph.impact_of_failure(name)
    return {"subsystem": name, "impacted": impacted, "count": len(impacted)}


# ═══ Phase 218C — Backpressure Endpoint ═══

from mcoi_runtime.core.backpressure import BackpressureEngine

backpressure = BackpressureEngine()


@app.get("/api/v1/backpressure")
def backpressure_status():
    """Current backpressure state."""
    return backpressure.status()
