"""Engineering puzzle kernel endpoints.

Purpose: FastAPI router for governed arrangement-search workflows.
Governance scope: HTTP request adaptation only; kernel execution remains in
EngineeringPuzzleControlSurface and the pure core kernel.
Dependencies: router dependency container, engineering puzzle control adapter.
Invariants:
  - Routes require an explicitly registered engineering_puzzle_control surface.
  - Payload validation failures return 400 with the violated field.
  - Missing control-surface wiring returns 503 instead of silently fabricating state.
  - Responses are JSON-safe envelopes emitted by the control adapter.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.engineering_puzzle_control import EngineeringPuzzleControlSurface
from mcoi_runtime.app.routers.deps import deps


router = APIRouter()


def _engineering_puzzle_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


class GoalDeltaRequest(BaseModel):
    """Request to classify and apply an episode goal delta."""

    puzzle: dict[str, Any]
    proposed_goal: str
    satisfaction_predicate_equivalent: bool = False
    new_episode_model_hash: str = ""
    fork_event_id: str = ""


class CandidateJudgmentRequest(BaseModel):
    """Request to judge a candidate arrangement through the kernel."""

    puzzle: dict[str, Any]
    candidate: dict[str, Any]
    confidence_floor: float = 0.0


def _control_surface() -> EngineeringPuzzleControlSurface:
    try:
        control = deps.get("engineering_puzzle_control")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="engineering_puzzle_control dependency not registered",
        ) from exc
    if not isinstance(control, EngineeringPuzzleControlSurface):
        raise HTTPException(
            status_code=500,
            detail="Dependency 'engineering_puzzle_control' has invalid type",
        )
    return control


@router.post("/api/v1/engineering-puzzle/goal-delta")
def decide_goal_delta(req: GoalDeltaRequest) -> dict[str, Any]:
    """Classify a goal delta as clarification or mutation."""

    try:
        return _control_surface().decide_goal_delta(
            {
                "puzzle": req.puzzle,
                "proposed_goal": req.proposed_goal,
                "satisfaction_predicate_equivalent": req.satisfaction_predicate_equivalent,
                "new_episode_model_hash": req.new_episode_model_hash,
                "fork_event_id": req.fork_event_id,
            }
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_engineering_puzzle_error_detail(
                "invalid engineering puzzle goal delta",
                "invalid_goal_delta",
            ),
        ) from exc


@router.post("/api/v1/engineering-puzzle/candidates/judge")
def judge_candidate(req: CandidateJudgmentRequest) -> dict[str, Any]:
    """Judge a candidate arrangement through governed search."""

    try:
        return _control_surface().judge_candidate(
            {
                "puzzle": req.puzzle,
                "candidate": req.candidate,
                "confidence_floor": req.confidence_floor,
            }
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_engineering_puzzle_error_detail(
                "invalid engineering puzzle candidate judgment",
                "invalid_candidate_judgment",
            ),
        ) from exc
