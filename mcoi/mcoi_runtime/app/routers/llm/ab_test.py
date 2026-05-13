"""A/B testing endpoints across LLM models."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.llm._common import deps
from mcoi_runtime.app.routers.llm._models import ABTestRequest

router = APIRouter()


# ═══ Phase 216B — A/B Testing Endpoint ═══


@router.post("/api/v1/ab-test")
def run_ab_test(req: ABTestRequest):
    """Run an A/B test across models."""
    deps.metrics.inc("requests_governed")
    model_fns = {}
    for mid in (req.model_ids or ["default"]):
        model_fns[mid] = lambda p, m=mid: deps.llm_bridge.complete(p, model_name=m, budget_id="default")

    result = deps.ab_engine.run_experiment(req.prompt, model_fns, criteria=req.criteria)
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


@router.get("/api/v1/ab-test/summary")
def ab_test_summary():
    """A/B testing summary with win rates."""
    return deps.ab_engine.summary()
