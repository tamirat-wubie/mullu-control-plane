"""Phase 229B — Circuit Breaker Dashboard Aggregator.

Purpose: Aggregate circuit breaker states across all subsystems into a
    unified dashboard view with health scoring and alert thresholds.
Dependencies: None (stdlib only).
Invariants:
  - Aggregation is read-only (does not modify breaker state).
  - Health score is 0-100 based on breaker states.
  - Alert thresholds are configurable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class BreakerState(Enum):
    CLOSED = "closed"       # healthy
    HALF_OPEN = "half_open"  # testing recovery
    OPEN = "open"           # tripped


@dataclass
class BreakerStatus:
    """Status of a single circuit breaker."""
    name: str
    state: BreakerState
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: float | None = None
    last_state_change_at: float = field(default_factory=time.time)

    @property
    def failure_rate(self) -> float:
        total = self.failure_count + self.success_count
        if total == 0:
            return 0.0
        return self.failure_count / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_rate": round(self.failure_rate, 4),
        }


@dataclass(frozen=True)
class AlertThresholds:
    """Alert thresholds for circuit breaker dashboard."""
    max_open_breakers: int = 2
    max_failure_rate: float = 0.5
    min_health_score: float = 50.0


class CircuitDashboard:
    """Aggregates circuit breaker states for dashboard view."""

    WEIGHTS = {
        BreakerState.CLOSED: 100.0,
        BreakerState.HALF_OPEN: 50.0,
        BreakerState.OPEN: 0.0,
    }

    def __init__(self, thresholds: AlertThresholds | None = None):
        self._thresholds = thresholds or AlertThresholds()
        self._breakers: dict[str, BreakerStatus] = {}
        self._state_history: list[dict[str, Any]] = []

    def register_breaker(self, name: str, state: BreakerState = BreakerState.CLOSED) -> BreakerStatus:
        status = BreakerStatus(name=name, state=state)
        self._breakers[name] = status
        return status

    def update_state(self, name: str, state: BreakerState) -> BreakerStatus | None:
        breaker = self._breakers.get(name)
        if not breaker:
            return None
        old_state = breaker.state
        breaker.state = state
        breaker.last_state_change_at = time.time()
        self._state_history.append({
            "name": name,
            "from": old_state.value,
            "to": state.value,
            "timestamp": time.time(),
        })
        return breaker

    def record_outcome(self, name: str, success: bool) -> None:
        breaker = self._breakers.get(name)
        if not breaker:
            return
        if success:
            breaker.success_count += 1
        else:
            breaker.failure_count += 1
            breaker.last_failure_at = time.time()

    @property
    def health_score(self) -> float:
        if not self._breakers:
            return 100.0
        total = sum(self.WEIGHTS[b.state] for b in self._breakers.values())
        return total / len(self._breakers)

    @property
    def open_count(self) -> int:
        return sum(1 for b in self._breakers.values() if b.state == BreakerState.OPEN)

    def get_alerts(self) -> list[str]:
        alerts = []
        if self.open_count > self._thresholds.max_open_breakers:
            alerts.append(f"Too many open breakers: {self.open_count}")
        if self.health_score < self._thresholds.min_health_score:
            alerts.append(f"Health score below threshold: {self.health_score:.1f}")
        for b in self._breakers.values():
            if b.failure_rate > self._thresholds.max_failure_rate:
                alerts.append(f"High failure rate on {b.name}: {b.failure_rate:.2%}")
        return alerts

    def summary(self) -> dict[str, Any]:
        return {
            "total_breakers": len(self._breakers),
            "health_score": round(self.health_score, 1),
            "open": self.open_count,
            "half_open": sum(1 for b in self._breakers.values() if b.state == BreakerState.HALF_OPEN),
            "closed": sum(1 for b in self._breakers.values() if b.state == BreakerState.CLOSED),
            "alerts": self.get_alerts(),
            "breakers": [b.to_dict() for b in self._breakers.values()],
        }
