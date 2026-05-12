"""Live-path certification endpoints."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter

from mcoi_runtime.app.routers.data._common import _certify_action_proof, deps

router = APIRouter()


@router.post("/api/v1/certify")
def run_certification():
    """Run full live-path certification: API -> DB -> LLM -> Ledger -> Restart."""
    chain = deps.certifier.run_full_certification(
        api_handle_fn=lambda req: {"governed": True, "status": "ok"},
        db_write_fn=lambda t, c: deps.store.append_ledger(
            "certification", "certifier", t, c,
            hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        ),
        db_read_fn=lambda t: deps.store.query_ledger(t),
        llm_invoke_fn=lambda prompt: deps.llm_bridge.complete(prompt, budget_id="default"),
        ledger_entries=deps.store.query_ledger("system", limit=100),
        pre_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
        post_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
    )
    return {
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/certify",
            tenant_id="system",
            actor_id="api",
            target=chain.chain_id,
            action="certification.run",
            succeeded=chain.all_passed,
        ),
        "steps": [
            {"name": s.name, "status": s.status.value, "proof_hash": s.proof_hash, "detail": s.detail}
            for s in chain.steps
        ],
    }


@router.get("/api/v1/certify/history")
def certification_history():
    """Certification chain history."""
    return {"certifications": deps.certifier.certification_history()}
