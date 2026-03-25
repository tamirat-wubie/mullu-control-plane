"""Phase 134A — Target Account Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TargetAccount:
    account_id: str
    company_name: str
    industry: str
    primary_pack: str
    employee_count: int = 0
    pain_score: float = 0.0  # 0-10
    urgency_score: float = 0.0  # 0-10
    connector_fit: float = 0.0  # 0-1
    sponsor_identified: bool = False
    expansion_packs: tuple[str, ...] = ()

    @property
    def composite_score(self) -> float:
        return round(
            (self.pain_score / 10) * 0.3 +
            (self.urgency_score / 10) * 0.25 +
            self.connector_fit * 0.2 +
            (1.0 if self.sponsor_identified else 0.0) * 0.15 +
            min(1.0, len(self.expansion_packs) / 3) * 0.1,
            3
        )

    @property
    def tier(self) -> str:
        s = self.composite_score
        if s >= 0.7: return "tier_1"
        if s >= 0.5: return "tier_2"
        return "tier_3"

ICP_DEFINITIONS = {
    "regulated_ops": {
        "title": "Regulated Operations",
        "ideal_size": "500-10000 employees",
        "industries": ("financial_services", "healthcare", "energy", "government", "insurance"),
        "pain_signals": ("audit_findings", "compliance_gaps", "remediation_backlogs", "evidence_collection_manual", "reporting_delays"),
        "decision_makers": ("Chief Compliance Officer", "VP Audit", "Head of Risk"),
    },
    "enterprise_service": {
        "title": "Enterprise IT/Service",
        "ideal_size": "1000-50000 employees",
        "industries": ("technology", "financial_services", "healthcare", "manufacturing", "retail"),
        "pain_signals": ("sla_breaches", "incident_volume", "visibility_gaps", "manual_escalation", "slow_resolution"),
        "decision_makers": ("CIO", "VP IT Operations", "Head of Service Management"),
    },
    "financial_control": {
        "title": "Financial Control",
        "ideal_size": "200-20000 employees",
        "industries": ("fintech", "financial_services", "marketplace", "saas", "insurance"),
        "pain_signals": ("settlement_delays", "dispute_volume", "collections_aging", "revenue_leakage", "audit_prep_burden"),
        "decision_makers": ("CFO", "VP Finance", "Revenue Controller", "Head of Billing"),
    },
    "factory_quality": {
        "title": "Factory/Manufacturing",
        "ideal_size": "500-50000 employees",
        "industries": ("discrete_manufacturing", "process_manufacturing", "automotive", "aerospace", "pharma"),
        "pain_signals": ("downtime_costs", "quality_escapes", "yield_loss", "maintenance_backlogs", "compliance_audits"),
        "decision_makers": ("VP Manufacturing", "Plant Manager", "Quality Director", "Operations Excellence Lead"),
    },
}

class TargetAccountEngine:
    def __init__(self):
        self._accounts: list[TargetAccount] = []

    def add_account(self, account: TargetAccount) -> None:
        self._accounts.append(account)

    def rank(self) -> list[TargetAccount]:
        return sorted(self._accounts, key=lambda a: a.composite_score, reverse=True)

    def by_pack(self, pack: str) -> list[TargetAccount]:
        return [a for a in self._accounts if a.primary_pack == pack]

    def tier_1_accounts(self) -> list[TargetAccount]:
        return [a for a in self._accounts if a.tier == "tier_1"]

    @property
    def total(self) -> int:
        return len(self._accounts)

    def summary(self) -> dict[str, Any]:
        ranked = self.rank()
        return {
            "total": self.total,
            "tier_1": len(self.tier_1_accounts()),
            "by_pack": {p: len(self.by_pack(p)) for p in ICP_DEFINITIONS},
            "top_5": [(a.company_name, a.primary_pack, a.composite_score) for a in ranked[:5]],
        }
