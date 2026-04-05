"""Phase 225A — SLA Monitoring Engine.

Purpose: Track service level agreements (SLAs) with target metrics,
    violation detection, and compliance reporting.
Dependencies: None (stdlib only).
Invariants:
  - SLA targets are immutable once created.
  - Violations are recorded with timestamp and context.
  - Compliance percentage is always 0-100.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class SLAMetricType(Enum):
    LATENCY_P99 = "latency_p99"
    UPTIME = "uptime"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


@dataclass(frozen=True)
class SLATarget:
    """Defines an SLA target for a metric."""
    sla_id: str
    name: str
    metric_type: SLAMetricType
    threshold: float  # e.g. 99.9 for uptime, 200 for latency_ms
    comparison: str  # "lte" (<=), "gte" (>=)
    description: str = ""

    def is_met(self, value: float) -> bool:
        if self.comparison == "lte":
            return value <= self.threshold
        elif self.comparison == "gte":
            return value >= self.threshold
        return False


@dataclass
class SLAViolation:
    """Records an SLA violation."""
    sla_id: str
    actual_value: float
    threshold: float
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)


class SLAMonitor:
    """Monitors SLA targets and detects violations."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._targets: dict[str, SLATarget] = {}
        self._violations: list[SLAViolation] = []
        self._check_counts: dict[str, int] = {}
        self._pass_counts: dict[str, int] = {}

    def add_target(self, target: SLATarget) -> None:
        self._targets[target.sla_id] = target
        self._check_counts[target.sla_id] = 0
        self._pass_counts[target.sla_id] = 0

    def check(self, sla_id: str, value: float, **context: Any) -> bool:
        target = self._targets.get(sla_id)
        if not target:
            raise ValueError("unknown SLA")
        self._check_counts[sla_id] = self._check_counts.get(sla_id, 0) + 1
        if target.is_met(value):
            self._pass_counts[sla_id] = self._pass_counts.get(sla_id, 0) + 1
            return True
        self._violations.append(SLAViolation(
            sla_id=sla_id, actual_value=value,
            threshold=target.threshold, timestamp=time.time(),
            context=context,
        ))
        return False

    def compliance(self, sla_id: str) -> float:
        checks = self._check_counts.get(sla_id, 0)
        if checks == 0:
            return 100.0
        passes = self._pass_counts.get(sla_id, 0)
        return (passes / checks) * 100.0

    def violations(self, sla_id: str | None = None) -> list[SLAViolation]:
        if sla_id:
            return [v for v in self._violations if v.sla_id == sla_id]
        return list(self._violations)

    @property
    def target_count(self) -> int:
        return len(self._targets)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    def summary(self) -> dict[str, Any]:
        return {
            "targets": self.target_count,
            "total_violations": self.violation_count,
            "compliance": {
                sla_id: self.compliance(sla_id)
                for sla_id in self._targets
            },
        }
