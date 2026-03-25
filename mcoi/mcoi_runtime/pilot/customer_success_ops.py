"""Phase 135C+F — Customer Success Runtime and Renewal/Expansion Execution."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

@dataclass
class CustomerHealthRecord:
    customer_id: str
    pack: str
    onboarding_complete: bool = False
    adoption_score: float = 0.0  # 0-10
    risk_flags: list[str] = field(default_factory=list)
    renewal_ready: bool = False
    expansion_ready: bool = False
    stakeholder_engaged: bool = True
    unresolved_blockers: int = 0
    last_review_at: str = ""

    @property
    def health_status(self) -> str:
        if self.unresolved_blockers > 3 or self.adoption_score < 4.0:
            return "critical"
        if not self.onboarding_complete or self.adoption_score < 6.0 or self.risk_flags:
            return "at_risk"
        if self.adoption_score >= 8.0 and self.stakeholder_engaged:
            return "champion"
        return "healthy"

    @property
    def renewal_risk(self) -> str:
        if self.health_status == "critical": return "high"
        if self.health_status == "at_risk": return "medium"
        return "low"

@dataclass(frozen=True)
class RenewalAction:
    customer_id: str
    action: str  # "review_scheduled", "risk_intervention", "expansion_proposed", "renewed", "churned"
    detail: str
    created_at: str = ""

class CustomerSuccessEngine:
    def __init__(self):
        self._customers: dict[str, CustomerHealthRecord] = {}
        self._actions: list[RenewalAction] = []

    def register_customer(self, customer_id: str, pack: str) -> CustomerHealthRecord:
        record = CustomerHealthRecord(customer_id=customer_id, pack=pack)
        self._customers[customer_id] = record
        return record

    def update_health(self, customer_id: str, **kwargs: Any) -> CustomerHealthRecord:
        if customer_id not in self._customers:
            raise ValueError(f"Unknown customer: {customer_id}")
        rec = self._customers[customer_id]
        for k, v in kwargs.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        return rec

    def record_action(self, customer_id: str, action: str, detail: str) -> RenewalAction:
        entry = RenewalAction(customer_id, action, detail, datetime.now(timezone.utc).isoformat())
        self._actions.append(entry)
        return entry

    def at_risk_customers(self) -> list[CustomerHealthRecord]:
        return [c for c in self._customers.values() if c.health_status in ("at_risk", "critical")]

    def expansion_candidates(self) -> list[CustomerHealthRecord]:
        return [c for c in self._customers.values() if c.health_status == "champion" and c.expansion_ready]

    @property
    def customer_count(self) -> int:
        return len(self._customers)

    def dashboard(self) -> dict[str, Any]:
        statuses = {}
        for c in self._customers.values():
            s = c.health_status
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "total_customers": self.customer_count,
            "by_status": statuses,
            "at_risk": len(self.at_risk_customers()),
            "expansion_candidates": len(self.expansion_candidates()),
            "total_actions": len(self._actions),
        }
