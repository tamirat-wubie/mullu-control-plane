"""Phase 216C — Tenant Isolation Verification.

Purpose: Security audit contracts that verify tenant data isolation.
    Runs probe tests to confirm no cross-tenant data leakage exists.
Governance scope: verification only — read-only probes.
Dependencies: tenant_budget, tenant_ledger, conversation_memory.
Invariants:
  - Probes never modify tenant data.
  - Cross-tenant access attempts return empty, not errors.
  - All probe results are auditable.
  - Verification is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def _bounded_probe_error(exc: Exception) -> str:
    """Return a stable probe failure label without raw backend detail."""
    return f"probe error ({type(exc).__name__})"


@dataclass(frozen=True, slots=True)
class IsolationProbe:
    """Result of a single isolation probe."""

    probe_name: str
    tenant_a: str
    tenant_b: str
    isolated: bool
    detail: str


@dataclass(frozen=True, slots=True)
class IsolationReport:
    """Full tenant isolation verification report."""

    probes: tuple[IsolationProbe, ...]
    all_isolated: bool
    probes_run: int
    probes_passed: int
    verified_at: str


class IsolationVerifier:
    """Verifies tenant data isolation across subsystems."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._probe_fns: list[Callable[[str, str], IsolationProbe]] = []
        self._reports: list[IsolationReport] = []

    def register_probe(self, probe_fn: Callable[[str, str], IsolationProbe]) -> None:
        """Register an isolation probe function."""
        self._probe_fns.append(probe_fn)

    def verify(self, tenant_a: str, tenant_b: str) -> IsolationReport:
        """Run all probes between two tenants."""
        probes: list[IsolationProbe] = []
        for fn in self._probe_fns:
            try:
                probe = fn(tenant_a, tenant_b)
                probes.append(probe)
            except Exception as exc:
                probes.append(IsolationProbe(
                    probe_name="error", tenant_a=tenant_a, tenant_b=tenant_b,
                    isolated=False, detail=_bounded_probe_error(exc),
                ))

        passed = sum(1 for p in probes if p.isolated)
        report = IsolationReport(
            probes=tuple(probes), all_isolated=all(p.isolated for p in probes),
            probes_run=len(probes), probes_passed=passed,
            verified_at=self._clock(),
        )
        self._reports.append(report)
        return report

    def history(self, limit: int = 20) -> list[IsolationReport]:
        return self._reports[-limit:]

    @property
    def probe_count(self) -> int:
        return len(self._probe_fns)

    def summary(self) -> dict[str, Any]:
        total_reports = len(self._reports)
        all_passed = sum(1 for r in self._reports if r.all_isolated)
        return {
            "probes_registered": self.probe_count,
            "reports": total_reports,
            "all_passed": all_passed,
        }
