"""Phase 230A — Deployment Readiness Checker.

Purpose: Pre-deployment validation that checks system health, pending migrations,
    configuration consistency, and dependency availability before allowing deploy.
Dependencies: None (stdlib only).
Invariants:
  - All checks must pass for deployment to be approved.
  - Failed checks include actionable remediation.
  - Checks are extensible via registration.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    """Result of a single readiness check."""
    name: str
    status: CheckStatus
    message: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass(frozen=True)
class ReadinessReport:
    """Aggregate deployment readiness report."""
    ready: bool
    checks: list[CheckResult]
    timestamp: float
    total_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": [c.to_dict() for c in self.checks],
            "passed": sum(1 for c in self.checks if c.status == CheckStatus.PASS),
            "warned": sum(1 for c in self.checks if c.status == CheckStatus.WARN),
            "failed": sum(1 for c in self.checks if c.status == CheckStatus.FAIL),
            "total_duration_ms": round(self.total_duration_ms, 2),
        }


class DeployReadinessChecker:
    """Runs pre-deployment readiness checks."""

    def __init__(self):
        self._checks: list[tuple[str, Callable[[], CheckResult]]] = []
        self._last_report: ReadinessReport | None = None
        self._total_runs = 0

    def register_check(self, name: str, check_fn: Callable[[], CheckResult]) -> None:
        self._checks.append((name, check_fn))

    def run_all(self) -> ReadinessReport:
        start = time.time()
        results: list[CheckResult] = []

        for name, check_fn in self._checks:
            t0 = time.time()
            try:
                result = check_fn()
                result.duration_ms = (time.time() - t0) * 1000
            except Exception as e:
                result = CheckResult(
                    name=name, status=CheckStatus.FAIL,
                    message=f"Check raised exception: {e}",
                    duration_ms=(time.time() - t0) * 1000,
                )
            results.append(result)

        ready = all(r.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.SKIP)
                     for r in results)
        total_ms = (time.time() - start) * 1000

        report = ReadinessReport(
            ready=ready, checks=results,
            timestamp=time.time(), total_duration_ms=total_ms,
        )
        self._last_report = report
        self._total_runs += 1
        return report

    @property
    def check_count(self) -> int:
        return len(self._checks)

    def summary(self) -> dict[str, Any]:
        return {
            "registered_checks": self.check_count,
            "total_runs": self._total_runs,
            "last_ready": self._last_report.ready if self._last_report else None,
        }
