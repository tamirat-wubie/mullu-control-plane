"""Phase 231C — Config Drift Detector.

Purpose: Detect configuration drift between expected (declared) and actual
    (runtime) state. Reports deviations with severity and remediation.
Dependencies: None (stdlib only).
Invariants:
  - Detection is non-destructive (read-only).
  - All drifts include expected vs actual values.
  - Severity is auto-classified.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class DriftSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DriftItem:
    """A single configuration drift."""
    key: str
    expected: Any
    actual: Any
    severity: DriftSeverity
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "severity": self.severity.value,
            "message": self.message,
        }


@dataclass
class DriftReport:
    """Aggregate drift detection report."""
    drifts: list[DriftItem]
    scanned_at: float = field(default_factory=time.time)

    @property
    def has_drift(self) -> bool:
        return len(self.drifts) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.CRITICAL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_drift": self.has_drift,
            "total_drifts": len(self.drifts),
            "critical": self.critical_count,
            "drifts": [d.to_dict() for d in self.drifts],
        }


class ConfigDriftDetector:
    """Detects configuration drift between expected and actual state."""

    def __init__(self):
        self._expected: dict[str, Any] = {}
        self._severity_overrides: dict[str, DriftSeverity] = {}
        self._total_scans = 0
        self._total_drifts_found = 0

    def set_expected(self, config: dict[str, Any]) -> None:
        self._expected = dict(config)

    def set_severity(self, key: str, severity: DriftSeverity) -> None:
        self._severity_overrides[key] = severity

    def _classify(self, key: str) -> DriftSeverity:
        if key in self._severity_overrides:
            return self._severity_overrides[key]
        # Default: keys with "secret", "password", "key" are critical
        lower = key.lower()
        if any(s in lower for s in ("secret", "password", "key", "token")):
            return DriftSeverity.CRITICAL
        return DriftSeverity.WARNING

    def detect(self, actual: dict[str, Any]) -> DriftReport:
        """Compare actual config against expected and report drifts."""
        self._total_scans += 1
        drifts: list[DriftItem] = []

        all_keys = set(self._expected.keys()) | set(actual.keys())
        for key in sorted(all_keys):
            expected_val = self._expected.get(key)
            actual_val = actual.get(key)

            if expected_val != actual_val:
                if key not in self._expected:
                    drift = DriftItem(
                        key=key, expected="<not set>", actual=actual_val,
                        severity=DriftSeverity.INFO,
                        message="Unexpected configuration key",
                    )
                elif key not in actual:
                    drift = DriftItem(
                        key=key, expected=expected_val, actual="<missing>",
                        severity=self._classify(key),
                        message="Missing configuration key",
                    )
                else:
                    drift = DriftItem(
                        key=key, expected=expected_val, actual=actual_val,
                        severity=self._classify(key),
                        message="Configuration value changed",
                    )
                drifts.append(drift)

        self._total_drifts_found += len(drifts)
        return DriftReport(drifts=drifts)

    def summary(self) -> dict[str, Any]:
        return {
            "expected_keys": len(self._expected),
            "total_scans": self._total_scans,
            "total_drifts_found": self._total_drifts_found,
        }
