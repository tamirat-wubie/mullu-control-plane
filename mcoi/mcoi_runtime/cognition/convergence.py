"""
Convergence Detector for the SCCCE cognitive cycle.

A cycle has converged when total tension stops decreasing meaningfully.
Three termination conditions, in priority order:

  1. ZERO_TENSION   — total tension is exactly 0; nothing left to resolve
  2. STABLE         — total tension change between iterations is below
                      epsilon for `stable_iterations` consecutive checks
  3. MAX_ITERATIONS — hit the iteration ceiling without converging
                      (this is BUDGET_UNKNOWN — the cycle is incomplete)

Convergence is a property of the tension trajectory, not the symbol field
contents. A cycle can converge with non-zero tension if the remaining
tension cannot be reduced (e.g. all pending validations are blocked on
external evidence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from mcoi_runtime.cognition.tension import TensionSnapshot


class ConvergenceReason(Enum):
    NOT_CONVERGED = "not_converged"
    ZERO_TENSION = "zero_tension"
    STABLE = "stable"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class ConvergenceState:
    converged: bool = False
    reason: ConvergenceReason = ConvergenceReason.NOT_CONVERGED
    iterations: int = 0
    tension_history: list[float] = field(default_factory=list)
    final_tension: float = 0.0


@dataclass
class ConvergenceDetector:
    """Tracks tension over iterations and decides when to stop."""

    epsilon: float = 1e-6
    max_iterations: int = 50
    stable_iterations: int = 3

    def __post_init__(self) -> None:
        if self.epsilon < 0:
            raise ValueError("epsilon must be non-negative")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.stable_iterations < 1:
            raise ValueError("stable_iterations must be >= 1")

    def evaluate(
        self,
        snapshot: TensionSnapshot,
        prior: ConvergenceState | None = None,
    ) -> ConvergenceState:
        """Update convergence state with the latest tension snapshot."""
        state = (
            ConvergenceState()
            if prior is None
            else ConvergenceState(
                converged=prior.converged,
                reason=prior.reason,
                iterations=prior.iterations,
                tension_history=list(prior.tension_history),
                final_tension=prior.final_tension,
            )
        )
        state.iterations += 1
        state.tension_history.append(snapshot.total)
        state.final_tension = snapshot.total

        # 1. Zero tension — fastest exit
        if snapshot.total == 0.0:
            state.converged = True
            state.reason = ConvergenceReason.ZERO_TENSION
            return state

        # 2. Stability — last `stable_iterations` deltas all below epsilon
        if len(state.tension_history) > self.stable_iterations:
            recent = state.tension_history[-(self.stable_iterations + 1):]
            deltas = [
                abs(recent[i + 1] - recent[i])
                for i in range(len(recent) - 1)
            ]
            if all(d <= self.epsilon for d in deltas):
                state.converged = True
                state.reason = ConvergenceReason.STABLE
                return state

        # 3. Iteration ceiling — budget exhausted without convergence
        if state.iterations >= self.max_iterations:
            state.converged = True
            state.reason = ConvergenceReason.MAX_ITERATIONS
            return state

        state.converged = False
        state.reason = ConvergenceReason.NOT_CONVERGED
        return state
