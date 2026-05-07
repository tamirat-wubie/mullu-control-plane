"""Purpose: provider cost routing engine — score, rank, and select providers.
Governance scope: cost-aware provider selection logic only.
Dependencies:
  - mcoi_runtime.contracts.provider_routing — RoutingStrategy, RoutingConstraints,
    ProviderCandidate, RoutingDecision, RoutingOutcome
  - mcoi_runtime.core.invariants — stable_identifier
Invariants:
  - Router is stateless except for audit trail.
  - No auto-execution from routing alone.
  - All scores bounded [0.0, 1.0].
  - No network, no IO.
  - Clock injected for determinism.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.provider_routing import (
    ProviderCandidate,
    RoutingConstraints,
    RoutingDecision,
    RoutingOutcome,
    RoutingStrategy,
)
from .invariants import stable_identifier


_COST_NORMALIZATION = 10_000.0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class ProviderCostRouter:
    """Score, rank, and select providers using cost-aware composite scoring."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._routing_history: list[RoutingDecision] = []
        self._outcomes: list[RoutingOutcome] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def routing_count(self) -> int:
        return len(self._routing_history)

    @property
    def outcome_count(self) -> int:
        return len(self._outcomes)

    @property
    def routing_outcomes(self) -> tuple:
        """All recorded routing outcomes (immutable copy)."""
        return tuple(self._outcomes)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_provider(
        self,
        provider_id: str,
        context_type: str,
        *,
        estimated_cost: float,
        health_score: float,
        preference_score: float,
        strategy: RoutingStrategy,
    ) -> float:
        """Return a composite score in [0.0, 1.0] for a provider given the strategy."""
        cost_score = _clamp(max(0.0, 1.0 - estimated_cost / _COST_NORMALIZATION))

        if strategy == RoutingStrategy.CHEAPEST:
            raw = 0.7 * cost_score + 0.2 * health_score + 0.1 * preference_score
        elif strategy == RoutingStrategy.MOST_RELIABLE:
            raw = 0.1 * cost_score + 0.6 * health_score + 0.3 * preference_score
        elif strategy == RoutingStrategy.BALANCED:
            raw = 0.34 * cost_score + 0.33 * health_score + 0.33 * preference_score
        elif strategy == RoutingStrategy.LEARNED:
            raw = 0.2 * cost_score + 0.3 * health_score + 0.5 * preference_score
        else:
            raise ValueError("unsupported routing strategy")

        return _clamp(raw)

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_providers(
        self,
        provider_entries: tuple[tuple[str, float, float, float], ...],
        context_type: str,
        constraints: RoutingConstraints,
    ) -> tuple[ProviderCandidate, ...]:
        """Score, filter, sort, and rank provider entries.

        Each entry is ``(provider_id, estimated_cost, health_score, preference_score)``.
        Returns a tuple of :class:`ProviderCandidate` sorted by composite score descending.
        """
        now = self._clock()
        strategy = constraints.strategy

        scored: list[tuple[str, float, float, float, float]] = []
        for provider_id, estimated_cost, health_score, preference_score in provider_entries:
            # Apply constraint filters (fields are non-optional on RoutingConstraints)
            if estimated_cost > constraints.max_cost_per_invocation:
                continue
            if health_score < constraints.min_provider_health_score:
                continue
            if preference_score < constraints.min_preference_score:
                continue
            # min_sample_count cannot be checked here — caller pre-filters

            composite = self.score_provider(
                provider_id,
                context_type,
                estimated_cost=estimated_cost,
                health_score=health_score,
                preference_score=preference_score,
                strategy=strategy,
            )
            scored.append((provider_id, estimated_cost, health_score, preference_score, composite))

        # Sort descending by composite score, then by provider_id for determinism
        scored.sort(key=lambda entry: (-entry[4], entry[0]))

        candidates: list[ProviderCandidate] = []
        for rank, (pid, est_cost, h_score, p_score, composite) in enumerate(scored, start=1):
            candidate_id = stable_identifier(
                "route-cand",
                {"provider_id": pid, "context_type": context_type, "rank": rank},
            )
            candidates.append(
                ProviderCandidate(
                    candidate_id=candidate_id,
                    provider_id=pid,
                    context_type=context_type,
                    estimated_cost=est_cost,
                    health_score=h_score,
                    preference_score=p_score,
                    composite_score=composite,
                    rank=rank,
                    scored_at=now,
                ),
            )

        return tuple(candidates)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_provider(
        self,
        provider_entries: tuple[tuple[str, float, float, float], ...],
        context_type: str,
        constraints: RoutingConstraints,
    ) -> RoutingDecision:
        """Select the top-ranked provider from entries after filtering.

        Raises :class:`ValueError` if no candidates pass the constraint filters.
        """
        candidates = self.rank_providers(provider_entries, context_type, constraints)
        if not candidates:
            raise ValueError("no provider candidates pass the routing constraints")

        selected = candidates[0]
        now = self._clock()

        decision_id = stable_identifier(
            "route-dec",
            {
                "context_type": context_type,
                "selected": selected.provider_id,
                "decided_at": now,
            },
        )

        decision = RoutingDecision(
            decision_id=decision_id,
            constraints_id=constraints.constraints_id,
            candidates=candidates,
            selected_provider_id=selected.provider_id,
            selected_cost=selected.estimated_cost,
            rationale="top-ranked provider selected",
            decided_at=now,
        )

        self._routing_history.append(decision)
        return decision

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        decision_id: str,
        provider_id: str,
        actual_cost: float,
        success: bool,
    ) -> RoutingOutcome:
        """Record the outcome of a routing decision."""
        now = self._clock()

        outcome_id = stable_identifier(
            "route-out",
            {
                "decision_id": decision_id,
                "provider_id": provider_id,
                "recorded_at": now,
            },
        )

        outcome = RoutingOutcome(
            outcome_id=outcome_id,
            decision_id=decision_id,
            provider_id=provider_id,
            actual_cost=actual_cost,
            success=success,
            recorded_at=now,
        )

        self._outcomes.append(outcome)
        return outcome
