"""Phase 210B — Health Aggregation.

Purpose: Unified system health score computed from all subsystem health.
    Provides a single numeric health score (0.0-1.0) plus detailed
    component breakdown for monitoring dashboards.
Governance scope: health computation only — read-only.
Dependencies: deep_health, certification_daemon, metrics, event_bus.
Invariants:
  - Health score is always between 0.0 and 1.0.
  - Score computation is deterministic for same inputs.
  - Component weights are explicit and auditable.
  - Zero-weight components are excluded from score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ComponentScore:
    """Health score for a single component."""

    name: str
    score: float  # 0.0-1.0
    weight: float  # Contribution to overall score
    status: str  # "healthy", "degraded", "unhealthy"
    detail: str


@dataclass(frozen=True, slots=True)
class AggregatedHealth:
    """Unified system health report."""

    overall_score: float
    status: str  # "healthy" (>=0.8), "degraded" (>=0.5), "unhealthy" (<0.5)
    components: tuple[ComponentScore, ...]
    checked_at: str


class HealthAggregator:
    """Computes unified system health from component scores."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._components: dict[str, tuple[Callable[[], dict[str, Any]], float]] = {}

    def register(self, name: str, check_fn: Callable[[], dict[str, Any]], weight: float = 1.0) -> None:
        """Register a health component with a weight."""
        self._components[name] = (check_fn, weight)

    def compute(self) -> AggregatedHealth:
        """Compute unified health score."""
        scores: list[ComponentScore] = []
        total_weight = 0.0
        weighted_sum = 0.0

        for name in sorted(self._components):
            check_fn, weight = self._components[name]
            try:
                result = check_fn()
                raw_status = result.get("status", "healthy")
                score = {"healthy": 1.0, "degraded": 0.5, "unhealthy": 0.0}.get(raw_status, 0.0)
                detail = result.get("detail", "")
            except Exception as exc:
                score = 0.0
                raw_status = "unhealthy"
                detail = str(exc)

            scores.append(ComponentScore(
                name=name, score=score, weight=weight,
                status=raw_status, detail=str(detail),
            ))
            total_weight += weight
            weighted_sum += score * weight

        overall = weighted_sum / total_weight if total_weight > 0 else 1.0

        if overall >= 0.8:
            status = "healthy"
        elif overall >= 0.5:
            status = "degraded"
        else:
            status = "unhealthy"

        return AggregatedHealth(
            overall_score=round(overall, 4),
            status=status,
            components=tuple(scores),
            checked_at=self._clock(),
        )

    @property
    def component_count(self) -> int:
        return len(self._components)
