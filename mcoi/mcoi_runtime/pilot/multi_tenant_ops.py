"""Phase 129B+D — Multi-Customer Operations and Tenant Health."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

@dataclass
class TenantHealthScore:
    tenant_id: str
    connector_health: float = 1.0  # 0-1
    workflow_completion_rate: float = 1.0
    slo_compliance: float = 1.0
    support_ticket_count: int = 0
    operator_satisfaction: float = 8.0

    @property
    def composite_score(self) -> float:
        weights = {"connector": 0.25, "workflow": 0.25, "slo": 0.2, "support": 0.15, "satisfaction": 0.15}
        support_score = max(0, 1.0 - self.support_ticket_count * 0.1)
        sat_score = min(1.0, self.operator_satisfaction / 10.0)
        return round(
            self.connector_health * weights["connector"] +
            self.workflow_completion_rate * weights["workflow"] +
            self.slo_compliance * weights["slo"] +
            support_score * weights["support"] +
            sat_score * weights["satisfaction"],
            3
        )

    @property
    def status(self) -> str:
        s = self.composite_score
        if s >= 0.9: return "healthy"
        if s >= 0.7: return "attention"
        if s >= 0.5: return "at_risk"
        return "critical"

@dataclass
class RenewalRisk:
    tenant_id: str
    days_until_renewal: int
    health_score: float
    support_tickets_last_30: int
    satisfaction_trend: str  # "improving", "stable", "declining"

    @property
    def risk_level(self) -> str:
        if self.health_score < 0.6 or self.satisfaction_trend == "declining":
            return "high"
        if self.health_score < 0.8 or self.support_tickets_last_30 > 5:
            return "medium"
        return "low"

class MultiTenantOperations:
    """Manages operations across multiple paying tenants."""

    def __init__(self):
        self._tenants: dict[str, TenantHealthScore] = {}
        self._renewals: dict[str, RenewalRisk] = {}
        self._support_queue: list[dict[str, Any]] = []

    def register_tenant(self, tenant_id: str) -> TenantHealthScore:
        health = TenantHealthScore(tenant_id=tenant_id)
        self._tenants[tenant_id] = health
        return health

    def update_health(self, tenant_id: str, **kwargs: Any) -> TenantHealthScore:
        if tenant_id not in self._tenants:
            raise ValueError(f"Unknown tenant: {tenant_id}")
        health = self._tenants[tenant_id]
        for k, v in kwargs.items():
            if hasattr(health, k):
                setattr(health, k, v)
        return health

    def register_renewal(self, tenant_id: str, days_until: int, satisfaction_trend: str = "stable") -> RenewalRisk:
        health = self._tenants.get(tenant_id)
        score = health.composite_score if health else 0.5
        tickets = health.support_ticket_count if health else 0
        risk = RenewalRisk(tenant_id, days_until, score, tickets, satisfaction_trend)
        self._renewals[tenant_id] = risk
        return risk

    def add_support_ticket(self, tenant_id: str, subject: str, severity: str = "medium") -> dict[str, Any]:
        ticket = {
            "tenant_id": tenant_id,
            "subject": subject,
            "severity": severity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "open",
        }
        self._support_queue.append(ticket)
        if tenant_id in self._tenants:
            self._tenants[tenant_id].support_ticket_count += 1
        return ticket

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)

    @property
    def at_risk_tenants(self) -> tuple[str, ...]:
        return tuple(t for t, h in self._tenants.items() if h.status in ("at_risk", "critical"))

    @property
    def high_risk_renewals(self) -> tuple[str, ...]:
        return tuple(t for t, r in self._renewals.items() if r.risk_level == "high")

    def dashboard(self) -> dict[str, Any]:
        return {
            "total_tenants": self.tenant_count,
            "healthy": sum(1 for h in self._tenants.values() if h.status == "healthy"),
            "attention": sum(1 for h in self._tenants.values() if h.status == "attention"),
            "at_risk": len(self.at_risk_tenants),
            "open_tickets": sum(1 for t in self._support_queue if t["status"] == "open"),
            "high_risk_renewals": len(self.high_risk_renewals),
        }
