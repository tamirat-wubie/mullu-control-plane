"""Certification daemon endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


@router.get("/api/v1/daemon/status")
def daemon_status():
    """Certification daemon health and run status."""
    return deps.cert_daemon.status()


@router.post("/api/v1/daemon/tick")
def daemon_tick():
    """Trigger a single certification daemon tick."""
    chain = deps.cert_daemon.tick()
    if chain is None:
        return {"ran": False, "reason": "disabled or interval not elapsed"}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
    }


@router.post("/api/v1/daemon/force")
def daemon_force():
    """Force an immediate certification run regardless of interval."""
    chain = deps.cert_daemon.force_run()
    if chain is None:
        return {"ran": False}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
    }
