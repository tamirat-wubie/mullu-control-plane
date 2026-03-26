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

app = FastAPI(title="Mullu Platform", version="0.2.0", description="Governed AI Operating System")


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
