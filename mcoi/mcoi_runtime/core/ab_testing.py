"""Phase 216B — Multi-Model A/B Testing Framework.

Purpose: Compare LLM model performance side-by-side.
    Runs the same prompt through multiple models and collects
    metrics for quality, speed, and cost comparison.
Governance scope: A/B test execution and result collection only.
Dependencies: none (pure comparison logic).
Invariants:
  - Each experiment has a control and one or more variants.
  - Results are collected independently per variant.
  - Winning model is determined by configurable criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ABVariant:
    """Single variant in an A/B experiment."""

    variant_id: str
    model_id: str
    content: str
    tokens: int
    cost: float
    latency_ms: float
    succeeded: bool


@dataclass(frozen=True, slots=True)
class ABExperiment:
    """Complete A/B experiment result."""

    experiment_id: str
    prompt: str
    variants: tuple[ABVariant, ...]
    winner: str  # variant_id of the winner
    criteria: str  # "cost", "quality", "speed"


class ABTestEngine:
    """Runs A/B experiments across multiple models."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._counter = 0
        self._history: list[ABExperiment] = []

    def run_experiment(
        self,
        prompt: str,
        model_fns: dict[str, Callable[[str], Any]],
        *,
        criteria: str = "cost",
    ) -> ABExperiment:
        """Run prompt through multiple models and compare."""
        self._counter += 1
        exp_id = f"ab-{self._counter}"
        variants: list[ABVariant] = []

        import time
        for variant_id, fn in model_fns.items():
            start = time.monotonic()
            try:
                result = fn(prompt)
                latency = (time.monotonic() - start) * 1000
                variants.append(ABVariant(
                    variant_id=variant_id,
                    model_id=variant_id,
                    content=getattr(result, "content", str(result)),
                    tokens=getattr(result, "total_tokens", 0),
                    cost=getattr(result, "cost", 0.0),
                    latency_ms=round(latency, 2),
                    succeeded=getattr(result, "succeeded", True),
                ))
            except Exception as exc:
                latency = (time.monotonic() - start) * 1000
                variants.append(ABVariant(
                    variant_id=variant_id, model_id=variant_id,
                    content="", tokens=0, cost=0.0,
                    latency_ms=round(latency, 2), succeeded=False,
                ))

        # Determine winner
        succeeded = [v for v in variants if v.succeeded]
        if not succeeded:
            winner = ""
        elif criteria == "cost":
            winner = min(succeeded, key=lambda v: v.cost).variant_id
        elif criteria == "speed":
            winner = min(succeeded, key=lambda v: v.latency_ms).variant_id
        else:  # quality = longest response as proxy
            winner = max(succeeded, key=lambda v: len(v.content)).variant_id

        experiment = ABExperiment(
            experiment_id=exp_id, prompt=prompt,
            variants=tuple(variants), winner=winner, criteria=criteria,
        )
        self._history.append(experiment)
        return experiment

    def history(self, limit: int = 50) -> list[ABExperiment]:
        return self._history[-limit:]

    @property
    def total_experiments(self) -> int:
        return len(self._history)

    def win_rates(self) -> dict[str, float]:
        """Win rate per model across all experiments."""
        wins: dict[str, int] = {}
        total = 0
        for exp in self._history:
            if exp.winner:
                wins[exp.winner] = wins.get(exp.winner, 0) + 1
                total += 1
        return {k: round(v / max(total, 1), 4) for k, v in wins.items()}

    def summary(self) -> dict[str, Any]:
        return {
            "total_experiments": self.total_experiments,
            "win_rates": self.win_rates(),
        }
