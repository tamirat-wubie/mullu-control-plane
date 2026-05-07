"""Purpose: integration facade for governed engineering puzzle workflows.
Governance scope: event-spine binding for goal decisions and candidate
judgments produced by the engineering puzzle kernel.
Dependencies: engineering puzzle kernel, event spine, event contracts.
Invariants:
  - Integration emits an append-only event for every public operation.
  - The pure kernel remains the authority for puzzle state transitions.
  - Event payloads include verdict, goal, candidate, and history-depth context.
  - Invalid event spine instances are rejected before any workflow call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from mcoi_runtime.contracts.engineering_puzzle import (
    CandidateArrangement,
    EngineeringPuzzle,
    JudgmentEnvelope,
)
from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType

from .engineering_puzzle_kernel import handle_goal_delta, solve_engineering_puzzle
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(
    event_spine: EventSpineEngine,
    *,
    action: str,
    correlation_id: str,
    payload: dict,
    clock: Callable[[], str],
) -> EventRecord:
    emitted_at = clock()
    event_payload = dict(payload)
    event_payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier(
            "evt-epk",
            {
                "action": action,
                "correlation_id": correlation_id,
                "emitted_at": emitted_at,
            },
        ),
        event_type=EventType.CUSTOM,
        source=EventSource.SUPERVISOR,
        correlation_id=correlation_id,
        payload=event_payload,
        emitted_at=emitted_at,
    )
    event_spine.emit(event)
    return event


class EngineeringPuzzleIntegration:
    """Event-spine facade for engineering puzzle kernel operations."""

    def __init__(
        self,
        event_spine: EventSpineEngine,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _default_clock

    def decide_goal_delta(
        self,
        puzzle: EngineeringPuzzle,
        proposed_goal: str,
        *,
        satisfaction_predicate_equivalent: bool,
        new_episode_model_hash: str = "",
        fork_event_id: str = "",
    ) -> dict[str, object]:
        """Classify a goal delta and emit lineage for the decision."""

        decision = handle_goal_delta(
            puzzle,
            proposed_goal,
            satisfaction_predicate_equivalent=satisfaction_predicate_equivalent,
            new_episode_model_hash=new_episode_model_hash,
            fork_event_id=fork_event_id,
        )
        action = (
            "engineering_goal_clarified"
            if decision.closed_puzzle is None
            else "engineering_goal_mutated"
        )
        event = _emit(
            self._events,
            action=action,
            correlation_id=decision.active_puzzle.episode_model_hash,
            payload={
                "old_goal": puzzle.goal,
                "active_goal": decision.active_puzzle.goal,
                "proposed_goal": proposed_goal,
                "verdict": decision.judgment.verdict.value,
                "kind": decision.kind.value,
                "active_history_depth": len(decision.active_puzzle.history),
                "closed_history_depth": (
                    None
                    if decision.closed_puzzle is None
                    else len(decision.closed_puzzle.history)
                ),
            },
            clock=self._clock,
        )
        return {
            "decision": decision,
            "event": event,
            "active_puzzle": decision.active_puzzle,
            "closed_puzzle": decision.closed_puzzle,
            "judgment": decision.judgment,
        }

    def judge_candidate(
        self,
        puzzle: EngineeringPuzzle,
        candidate: CandidateArrangement,
        *,
        confidence_floor: float,
    ) -> dict[str, EngineeringPuzzle | JudgmentEnvelope | EventRecord]:
        """Judge a candidate through the kernel and emit the resulting verdict."""

        next_puzzle, judgment = solve_engineering_puzzle(
            puzzle,
            candidate,
            confidence_floor=confidence_floor,
        )
        event = _emit(
            self._events,
            action="engineering_candidate_judged",
            correlation_id=puzzle.episode_model_hash,
            payload={
                "candidate_id": candidate.candidate_id,
                "goal": puzzle.goal,
                "verdict": judgment.verdict.value,
                "confidence": judgment.confidence,
                "margin": judgment.margin,
                "fragile": judgment.fragile,
                "history_depth_before": len(puzzle.history),
                "history_depth_after": len(next_puzzle.history),
                "committed": next_puzzle.state != puzzle.state,
                "authority_ref": candidate.authority_ref,
                "governance_certified": candidate.governance_certified,
            },
            clock=self._clock,
        )
        return {
            "puzzle": next_puzzle,
            "judgment": judgment,
            "event": event,
        }
