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
        hysteresis_band: float = 5.0,
    ) -> None:
        self._elevated = elevated_threshold
        self._high = high_threshold
        self._critical = critical_threshold
        self._hysteresis = hysteresis_band
        self._current_load: float = 0.0
        self._previous_level: PressureLevel = PressureLevel.NORMAL

    def update_load(self, load_pct: float) -> None:
        """Update current system load percentage (0-100)."""
        self._current_load = max(0.0, min(100.0, load_pct))

    def evaluate(self, is_essential: bool = True) -> BackpressureState:
        """Evaluate backpressure for a request.

        Uses hysteresis to prevent oscillation at threshold boundaries.
        A level only drops when load falls below (threshold - hysteresis_band).
        """
        load = self._current_load
        h = self._hysteresis
        prev = self._previous_level

        # Determine new level with hysteresis on the downward transition
        if load >= self._critical:
            level = PressureLevel.CRITICAL
        elif load >= self._high or (prev == PressureLevel.CRITICAL and load >= self._critical - h):
            level = PressureLevel.HIGH if prev != PressureLevel.CRITICAL else PressureLevel.CRITICAL if load >= self._critical - h else PressureLevel.HIGH
        elif load >= self._elevated or (prev == PressureLevel.HIGH and load >= self._high - h):
            level = PressureLevel.ELEVATED if prev != PressureLevel.HIGH else PressureLevel.HIGH if load >= self._high - h else PressureLevel.ELEVATED
        elif prev == PressureLevel.ELEVATED and load >= self._elevated - h:
            level = PressureLevel.ELEVATED
        else:
            level = PressureLevel.NORMAL

        self._previous_level = level

        delay_map = {
            PressureLevel.CRITICAL: 1000.0,
            PressureLevel.HIGH: 500.0,
            PressureLevel.ELEVATED: 100.0,
            PressureLevel.NORMAL: 0.0,
        }
        shed = level == PressureLevel.CRITICAL and not is_essential
        return BackpressureState(
            level=level, load_pct=load,
            should_shed=shed, delay_ms=delay_map[level],
            reason={
                PressureLevel.NORMAL: "normal load",
                PressureLevel.ELEVATED: "elevated load",
                PressureLevel.HIGH: "high load",
                PressureLevel.CRITICAL: "critical load",
            }[level],
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
