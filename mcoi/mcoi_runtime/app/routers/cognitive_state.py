"""Read-only cognitive plan-context endpoint (Stage D).

Purpose: expose a snapshot of the dormant organs' state per capability_id, so
operators can inspect what the cognitive loop has actually learned. This is
the READ-back half of the cognitive loop campaign: Stage A (shadow OBSERVE),
Stage B (enforce DECIDE), and Stage C (live LEARN write-back) all wrote to
or refused based on these organs without ever exposing them to a router.
Governance scope: observability only. The endpoint NEVER mutates an organ,
never gates a dispatch, never changes any other response. Disabled by default
via MULLU_COGNITIVE_LOOP_READ; when disabled the endpoint returns 503 (the
route exists - operators can discover it - but answers with a stable
"disabled" body), keeping the live path byte-identical to today.
Dependencies: cognitive_runtime bundle on deps (mounted by
cognitive_runtime_integration); env flag validated via cognitive_live_integration.
Invariants:
  * Read-only and side-effect free; cannot dispatch, mutate organs, or change
    governance behavior of any other route.
  * Fail-OPEN: a missing runtime, a malformed organ, or an internal error all
    degrade to a safe response (503 disabled, or 200 with defaults) - never a
    500 spurious crash.
  * Static contract strings; passes the reflective-contract guard.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from mcoi_runtime.app.cognitive_live_integration import (
    plan_context_disabled_detail,
    read_plan_context,
    validate_read_config,
)
from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


def _read_enabled() -> bool:
    return validate_read_config(os.environ).enabled


def _inc_metric(name: str) -> None:
    try:
        deps.metrics.inc(name)
    except Exception:  # noqa: BLE001 - observability metric must not break the route
        return


@router.get("/api/v1/cognitive-loop/plan-context/{capability_id}")
def cognitive_plan_context(capability_id: str) -> dict[str, object]:
    """Read-only snapshot of organ state for ``capability_id`` (Stage D).

    The response is bounded, deterministic in shape, and carries no execution
    authority. When the read flag is off, returns 503 with a stable disabled
    detail (so the contract is discoverable but the feature is observably
    off). When on, returns the CognitivePlanContext fields as JSON.
    """
    _inc_metric("requests_governed")
    if not _read_enabled():
        raise HTTPException(status_code=503, detail=plan_context_disabled_detail())
    context = read_plan_context(deps, capability_id=capability_id)
    if context is None:
        # Bundle missing or a top-level read error: report empty-but-known
        # shape rather than 500, so the operator distinguishes "off" (503)
        # from "no organs mounted in this build" (200 with empty defaults).
        return {
            "governed": True,
            "execution_authority": False,
            "capability_id": capability_id,
            "available": False,
            "confidence": 0.5,
            "degraded": False,
            "prior_outcomes_count": 0,
            "prior_success_count": 0,
            "learned_factor_adjustments": [],
            "learned_adjustment_count": 0,
            "world_entity_count": 0,
            "world_snapshot_hash": None,
        }
    return {
        "governed": True,
        "execution_authority": False,
        "available": True,
        "capability_id": context.capability_id,
        "confidence": context.confidence,
        "degraded": context.degraded,
        "prior_outcomes_count": context.prior_outcomes_count,
        "prior_success_count": context.prior_success_count,
        "learned_factor_adjustments": [
            {"factor": factor, "value": value}
            for factor, value in context.learned_factor_adjustments
        ],
        "learned_adjustment_count": context.learned_adjustment_count,
        "world_entity_count": context.world_entity_count,
        "world_snapshot_hash": context.world_snapshot_hash,
    }
