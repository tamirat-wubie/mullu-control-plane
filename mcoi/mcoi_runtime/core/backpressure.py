"""Phase 218C — Backpressure Engine.

Purpose: Request throttling with load-adaptive backpressure.
    When system load exceeds thresholds, progressively delays
    or rejects requests to prevent cascading failures.
Governance scope: load management only.
Invariants:
  - Backpressure levels are computed from current load metrics.
  - Shed decisions are deterministic for same load.
  - Recovery is automatic when load decreases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PressureLevel(StrEnum):
    NORMAL = "normal"       # < 60% capacity
    ELEVATED = "elevated"   # 60-80% — start delaying
    HIGH = "high"           # 80-95% — aggressive throttling
    CRITICAL = "critical"   # > 95% — shed non-essential requests


@dataclass(frozen=True, slots=True)
class BackpressureState:
    """Current backpressure state."""

    level: PressureLevel
    load_pct: float
    should_shed: bool
    delay_ms: float
    reason: str


class BackpressureEngine:
    """Load-adaptive backpressure for governed systems."""

    def __init__(
        self,
        *,
        elevated_threshold: float = 60.0,
        high_threshold: float = 80.0,
        critical_threshold: float = 95.0,
    ) -> None:
        self._elevated = elevated_threshold
        self._high = high_threshold
        self._critical = critical_threshold
        self._current_load: float = 0.0

    def update_load(self, load_pct: float) -> None:
        """Update current system load percentage (0-100)."""
        self._current_load = max(0.0, min(100.0, load_pct))

    def evaluate(self, is_essential: bool = True) -> BackpressureState:
        """Evaluate backpressure for a request."""
        load = self._current_load

        if load >= self._critical:
            return BackpressureState(
                level=PressureLevel.CRITICAL, load_pct=load,
                should_shed=not is_essential, delay_ms=1000.0,
                reason=f"critical load ({load:.1f}%)",
            )
        if load >= self._high:
            return BackpressureState(
                level=PressureLevel.HIGH, load_pct=load,
                should_shed=False, delay_ms=500.0,
                reason=f"high load ({load:.1f}%)",
            )
        if load >= self._elevated:
            return BackpressureState(
                level=PressureLevel.ELEVATED, load_pct=load,
                should_shed=False, delay_ms=100.0,
                reason=f"elevated load ({load:.1f}%)",
            )
        return BackpressureState(
            level=PressureLevel.NORMAL, load_pct=load,
            should_shed=False, delay_ms=0.0,
            reason="normal",
        )

    @property
    def current_level(self) -> PressureLevel:
        return self.evaluate().level

    def status(self) -> dict[str, Any]:
        state = self.evaluate()
        return {
            "level": state.level.value,
            "load_pct": state.load_pct,
            "delay_ms": state.delay_ms,
        }
