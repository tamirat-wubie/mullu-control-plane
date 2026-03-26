"""Phase 198A — Real HTTP Server (FastAPI).

Purpose: HTTP boundary for the governed platform. All requests enter governed execution.
Dependencies: fastapi, production_surface.
Run: uvicorn mcoi_runtime.app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
from typing import Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mcoi_runtime.app.production_surface import (
    ProductionSurface, APIRequest, DEPLOYMENT_MANIFESTS,
)

import os

ENV = os.environ.get("MULLU_ENV", "local_dev")
surface = ProductionSurface(DEPLOYMENT_MANIFESTS.get(ENV, DEPLOYMENT_MANIFESTS["local_dev"]))

app = FastAPI(title="Mullu Platform", version="0.1.0", description="Governed AI Operating System")

class ExecuteRequest(BaseModel):
    goal_id: str
    action: str
    tenant_id: str
    body: dict[str, Any] = {}

@app.get("/health")
def health():
    return surface.health()

@app.get("/ready")
def ready():
    h = surface.health()
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
    import hashlib, time
    sid = hashlib.sha256(f"{actor_id}:{tenant_id}:{time.time()}".encode()).hexdigest()[:16]
    session = surface.auth.create_session(f"sess-{sid}", actor_id, tenant_id)
    surface.tenants.register_tenant(tenant_id)
    return {"session_id": session.session_id, "actor_id": actor_id, "tenant_id": tenant_id}

@app.get("/api/v1/ledger")
def get_ledger(session_id: str = Header(default="")):
    # Simple ledger view — in production would be paginated
    return {"entries": len(surface.api._responses), "governed": True}
