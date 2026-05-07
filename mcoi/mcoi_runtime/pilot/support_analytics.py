"""Phase 135E — Incident / Support Analytics."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

@dataclass
class SupportTicket:
    ticket_id: str
    customer_id: str
    pack: str
    category: str  # from ISSUE_CLASSIFICATION keys
    severity: str  # "critical", "high", "medium", "low"
    status: str = "open"  # "open", "in_progress", "resolved", "closed"
    created_at: str = ""
    resolved_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())

class SupportAnalyticsEngine:
    def __init__(self):
        self._tickets: list[SupportTicket] = []

    def create_ticket(self, ticket_id: str, customer_id: str, pack: str, category: str, severity: str) -> SupportTicket:
        ticket = SupportTicket(ticket_id, customer_id, pack, category, severity)
        self._tickets.append(ticket)
        return ticket

    def resolve_ticket(self, ticket_id: str) -> SupportTicket:
        for t in self._tickets:
            if t.ticket_id == ticket_id:
                t.status = "resolved"
                t.resolved_at = datetime.now(timezone.utc).isoformat()
                return t
        raise ValueError("unknown ticket")

    def by_customer(self, customer_id: str) -> list[SupportTicket]:
        return [t for t in self._tickets if t.customer_id == customer_id]

    def by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self._tickets:
            counts[t.category] = counts.get(t.category, 0) + 1
        return counts

    def open_count(self) -> int:
        return sum(1 for t in self._tickets if t.status == "open")

    def repeat_issues(self) -> dict[str, int]:
        customer_counts: dict[str, int] = {}
        for t in self._tickets:
            customer_counts[t.customer_id] = customer_counts.get(t.customer_id, 0) + 1
        return {k: v for k, v in customer_counts.items() if v > 2}

    def dashboard(self) -> dict[str, Any]:
        return {
            "total_tickets": len(self._tickets),
            "open": self.open_count(),
            "by_category": self.by_category(),
            "repeat_issue_customers": len(self.repeat_issues()),
            "by_severity": {s: sum(1 for t in self._tickets if t.severity == s) for s in ("critical", "high", "medium", "low")},
        }
