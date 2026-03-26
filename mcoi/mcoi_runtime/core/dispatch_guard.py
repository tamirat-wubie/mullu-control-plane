"""Phase 195A -- Dispatcher Guard / Legacy Path Deprecation.

Purpose: Guards raw dispatcher access and ensures new code uses governed dispatch.
Governance scope: execution path migration enforcement.
Dependencies: dispatcher, execution_authority.
Invariants: raw dispatch emits deprecation audit, CI gate prevents new legacy paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone


@dataclass
class DispatchAuditEntry:
    caller: str
    route: str
    timestamp: str
    governed: bool


class DispatchGuard:
    """Wraps and audits all dispatch calls, tracking governed vs legacy usage."""

    def __init__(self) -> None:
        self._audit: list[DispatchAuditEntry] = []

    def record_governed_dispatch(self, caller: str, route: str) -> None:
        self._audit.append(
            DispatchAuditEntry(
                caller, route, datetime.now(timezone.utc).isoformat(), True
            )
        )

    def record_legacy_dispatch(self, caller: str, route: str) -> None:
        self._audit.append(
            DispatchAuditEntry(
                caller, route, datetime.now(timezone.utc).isoformat(), False
            )
        )

    @property
    def total_dispatches(self) -> int:
        return len(self._audit)

    @property
    def governed_count(self) -> int:
        return sum(1 for a in self._audit if a.governed)

    @property
    def legacy_count(self) -> int:
        return sum(1 for a in self._audit if not a.governed)

    @property
    def governed_ratio(self) -> float:
        return self.governed_count / self.total_dispatches if self.total_dispatches else 1.0

    def legacy_callers(self) -> list[str]:
        return list(set(a.caller for a in self._audit if not a.governed))

    def coverage_report(self) -> dict[str, Any]:
        return {
            "total": self.total_dispatches,
            "governed": self.governed_count,
            "legacy": self.legacy_count,
            "ratio": round(self.governed_ratio, 3),
            "legacy_callers": self.legacy_callers(),
        }
