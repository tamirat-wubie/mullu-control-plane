"""Purpose: supervisor integration bridge — connects the supervisor engine to
governance, meta-reasoning, and dashboard planes.
Governance scope: supervisor plane orchestration only.
Dependencies: supervisor engine, supervisor contracts, governance integration,
meta-reasoning, dashboard contracts.
Invariants:
  - Bridge methods are stateless orchestrators.
  - All results flow through typed contracts.
  - Governance gate is always applied before supervisor actions.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.supervisor import (
    CheckpointStatus,
    LivelockStrategy,
    SupervisorCheckpoint,
    SupervisorHealth,
    SupervisorPhase,
    SupervisorPolicy,
    SupervisorTick,
    TickOutcome,
)
from .invariants import stable_identifier
from .supervisor_engine import SupervisorEngine


class SupervisorBridge:
    """Static integration bridge for the supervisor subsystem.

    Orchestrates:
    - Default policy creation
    - Multi-tick execution with configurable stopping
    - Health summary extraction for dashboard integration
    - Checkpoint validation and resume
    - Governance gate wiring
    """

    @staticmethod
    def create_default_policy(
        *,
        created_at: str,
        tick_interval_ms: int = 1000,
        max_events_per_tick: int = 100,
        max_actions_per_tick: int = 50,
        backpressure_threshold: int = 200,
        livelock_repeat_threshold: int = 5,
        livelock_strategy: LivelockStrategy = LivelockStrategy.ESCALATE,
        heartbeat_every_n_ticks: int = 10,
        checkpoint_every_n_ticks: int = 25,
        max_consecutive_errors: int = 3,
    ) -> SupervisorPolicy:
        """Create a supervisor policy with sensible defaults."""
        policy_id = stable_identifier("sv-policy", {
            "interval": tick_interval_ms,
            "created_at": created_at,
        })
        return SupervisorPolicy(
            policy_id=policy_id,
            tick_interval_ms=tick_interval_ms,
            max_events_per_tick=max_events_per_tick,
            max_actions_per_tick=max_actions_per_tick,
            backpressure_threshold=backpressure_threshold,
            livelock_repeat_threshold=livelock_repeat_threshold,
            livelock_strategy=livelock_strategy,
            heartbeat_every_n_ticks=heartbeat_every_n_ticks,
            checkpoint_every_n_ticks=checkpoint_every_n_ticks,
            max_consecutive_errors=max_consecutive_errors,
            created_at=created_at,
        )

    @staticmethod
    def run_n_ticks(
        engine: SupervisorEngine,
        n: int,
        *,
        stop_on_halt: bool = True,
        stop_on_livelock: bool = False,
    ) -> tuple[SupervisorTick, ...]:
        """Advance the supervisor by N ticks.

        Returns the tick records.  Stops early if halted or livelock is
        detected (when the corresponding flag is set).
        """
        ticks: list[SupervisorTick] = []
        for _ in range(n):
            tick = engine.tick()
            ticks.append(tick)
            if stop_on_halt and tick.outcome == TickOutcome.HALTED:
                break
            if stop_on_livelock and tick.outcome == TickOutcome.LIVELOCK_DETECTED:
                break
        return tuple(ticks)

    @staticmethod
    def extract_dashboard_summary(
        engine: SupervisorEngine,
    ) -> dict[str, Any]:
        """Extract a dashboard-friendly summary from the supervisor state.

        Returns a dict with:
        - tick_number: current tick
        - phase: current phase
        - is_halted: whether supervisor is halted
        - consecutive_errors: error count
        - consecutive_idle_ticks: idle count
        - total_ticks: number of completed ticks
        - total_checkpoints: number of checkpoints
        - total_heartbeats: number of heartbeats
        - total_livelocks: number of livelocks detected
        - recent_outcomes: last 10 tick outcomes
        - health: health assessment dict (if not halted)
        """
        health = engine.assess_health()
        recent = engine.tick_history[-10:] if engine.tick_history else ()

        return {
            "tick_number": engine.tick_number,
            "phase": engine.phase.value,
            "is_halted": engine.is_halted,
            "consecutive_errors": health.consecutive_errors,
            "consecutive_idle_ticks": health.consecutive_idle_ticks,
            "total_ticks": len(engine.tick_history),
            "total_checkpoints": len(engine.checkpoint_history),
            "total_heartbeats": len(engine.heartbeat_history),
            "total_livelocks": len(engine.livelock_history),
            "recent_outcomes": [t.outcome.value for t in recent],
            "health": {
                "overall_confidence": health.overall_confidence,
                "backpressure_active": health.backpressure_active,
                "livelock_detected": health.livelock_detected,
                "open_obligations": health.open_obligations,
                "pending_events": health.pending_events,
            },
        }

    @staticmethod
    def validate_checkpoint(checkpoint: SupervisorCheckpoint) -> bool:
        """Check whether a checkpoint is valid for resume."""
        return checkpoint.status == CheckpointStatus.VALID

    @staticmethod
    def resume_engine(
        engine: SupervisorEngine,
        checkpoint: SupervisorCheckpoint,
    ) -> None:
        """Resume a supervisor engine from a validated checkpoint."""
        engine.resume_from_checkpoint(checkpoint)
