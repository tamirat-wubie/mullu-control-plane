"""Phase 164 — Customer Success Automation 2.0."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SIGNAL_TYPES = (
    "adoption_weak",
    "renewal_risk",
    "expansion_ready",
    "stakeholder_disengaged",
    "maturity_plateau",
)

MATURITY_STAGES = ("onboarding", "adopting", "mature", "champion")


@dataclass
class CustomerHealthSignal:
    account_id: str
    signal_type: str  # one of SIGNAL_TYPES
    severity: str  # low / medium / high / critical
    detail: str

    def __post_init__(self) -> None:
        if self.signal_type not in SIGNAL_TYPES:
            raise ValueError(f"Invalid signal_type {self.signal_type!r}")
        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError(f"Invalid severity {self.severity!r}")


class CSAutomationEngine:
    """Detects customer health signals and tracks maturity."""

    def __init__(self) -> None:
        self._signals: list[CustomerHealthSignal] = []

    # ---- detectors ----------------------------------------------------------

    def detect_weak_adoption(
        self,
        account_id: str,
        dashboard_views: int,
        workflow_completions: int,
        copilot_queries: int,
    ) -> CustomerHealthSignal | None:
        total = dashboard_views + workflow_completions + copilot_queries
        if total >= 30:
            return None
        severity = "critical" if total < 5 else "high" if total < 15 else "medium"
        sig = CustomerHealthSignal(
            account_id=account_id,
            signal_type="adoption_weak",
            severity=severity,
            detail=f"Low activity: views={dashboard_views}, workflows={workflow_completions}, copilot={copilot_queries}",
        )
        self._signals.append(sig)
        return sig

    def detect_renewal_risk(
        self,
        account_id: str,
        satisfaction: float,
        support_tickets: int,
        days_to_renewal: int,
    ) -> CustomerHealthSignal | None:
        risk = False
        severity = "medium"
        if satisfaction < 6.0:
            risk = True
            severity = "high" if satisfaction < 4.0 else "medium"
        if support_tickets > 10 and days_to_renewal < 90:
            risk = True
            severity = "high"
        if satisfaction < 4.0 and days_to_renewal < 60:
            severity = "critical"
        if not risk:
            return None
        sig = CustomerHealthSignal(
            account_id=account_id,
            signal_type="renewal_risk",
            severity=severity,
            detail=f"satisfaction={satisfaction}, tickets={support_tickets}, days_to_renewal={days_to_renewal}",
        )
        self._signals.append(sig)
        return sig

    def suggest_expansion(
        self,
        account_id: str,
        activation_rate: float,
        months_active: int,
        current_pack: str,
    ) -> CustomerHealthSignal | None:
        if activation_rate < 0.75 or months_active < 3:
            return None
        severity = "low" if activation_rate < 0.9 else "medium"
        sig = CustomerHealthSignal(
            account_id=account_id,
            signal_type="expansion_ready",
            severity=severity,
            detail=f"activation={activation_rate:.0%}, months={months_active}, pack={current_pack}",
        )
        self._signals.append(sig)
        return sig

    def detect_stakeholder_risk(
        self,
        account_id: str,
        executive_logins_30d: int,
        last_review_days_ago: int,
    ) -> CustomerHealthSignal | None:
        if executive_logins_30d >= 2 and last_review_days_ago <= 30:
            return None
        severity = "medium"
        if executive_logins_30d == 0 and last_review_days_ago > 60:
            severity = "critical"
        elif executive_logins_30d == 0 or last_review_days_ago > 45:
            severity = "high"
        sig = CustomerHealthSignal(
            account_id=account_id,
            signal_type="stakeholder_disengaged",
            severity=severity,
            detail=f"exec_logins_30d={executive_logins_30d}, last_review={last_review_days_ago}d ago",
        )
        self._signals.append(sig)
        return sig

    def track_maturity(
        self,
        account_id: str,
        months_active: int,
        workflows_completed: int,
        packs_active: int,
    ) -> str:
        if months_active >= 12 and workflows_completed >= 200 and packs_active >= 3:
            return "champion"
        if months_active >= 6 and workflows_completed >= 50 and packs_active >= 2:
            return "mature"
        if months_active >= 2 and workflows_completed >= 10:
            return "adopting"
        return "onboarding"

    def all_signals(
        self, account_id: str, metrics: dict[str, Any]
    ) -> list[CustomerHealthSignal]:
        signals: list[CustomerHealthSignal] = []
        s = self.detect_weak_adoption(
            account_id,
            metrics.get("dashboard_views", 0),
            metrics.get("workflow_completions", 0),
            metrics.get("copilot_queries", 0),
        )
        if s:
            signals.append(s)
        s = self.detect_renewal_risk(
            account_id,
            metrics.get("satisfaction", 10.0),
            metrics.get("support_tickets", 0),
            metrics.get("days_to_renewal", 365),
        )
        if s:
            signals.append(s)
        s = self.suggest_expansion(
            account_id,
            metrics.get("activation_rate", 0.0),
            metrics.get("months_active", 0),
            metrics.get("current_pack", ""),
        )
        if s:
            signals.append(s)
        s = self.detect_stakeholder_risk(
            account_id,
            metrics.get("executive_logins_30d", 5),
            metrics.get("last_review_days_ago", 0),
        )
        if s:
            signals.append(s)
        return signals

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sig in self._signals:
            counts[sig.signal_type] = counts.get(sig.signal_type, 0) + 1
        return counts
